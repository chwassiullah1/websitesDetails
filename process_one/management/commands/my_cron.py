from django.core.management.base import BaseCommand
import json
import asyncio
import aiohttp
import re
from urllib.parse import urljoin
import scrapy
import requests
from bs4 import BeautifulSoup
from home.toolbox import links_determiner_assistant, run_assistant, filter_links, clean_url
import logging
import codecs
from process_one.models import DomainsData
from home.models import DomainQueue
from django.utils import timezone
import time

logging.basicConfig(level=logging.INFO)


class Command(BaseCommand):
    help = 'Custom cron job command'

    def handle(self, *args, **options):
        while True:
            try:
                domains = DomainQueue.objects.filter(processed=0)
                if domains:
                    for domain in domains:
                        start_time = timezone.now()
                        clean_website_url = clean_url(domain.domain)
                        query = {
                            "data": {"domain": clean_website_url, "$options": "i"}
                        }
                        existing_domain = DomainsData.objects.filter(**query).first()
                        if not existing_domain:
                            ssl_info = check_ssl(clean_website_url)
                            if ssl_info:
                                website_url = f'https://www.{clean_website_url}'
                            else:
                                website_url = f'http://www.{clean_website_url}'
                            try:
                                data_dict = run_asyncio_task(parse(website_url))
                                final_json = codecs.decode(data_dict.get('data'), 'unicode_escape')
                                final_json_data = json.loads(final_json)
                                instance = DomainsData.objects.create(data=final_json_data)
                                instance.save()
                                end_time = timezone.now()
                                DomainQueue.objects.filter(id=domain.id).update(processed=1,
                                                                                process_start=start_time,
                                                                                process_finished=end_time)
                                self.stdout.write(self.style.SUCCESS('Successfully updated DomainQueue Model'))
                            except Exception as e:
                                self.stdout.write(self.style.ERROR(f'Error: {e}'))
                        else:
                            self.stdout.write(self.style.SUCCESS('Record already processed...!'))
                else:
                    self.stdout.write(self.style.ERROR('NO RECORDS FOUND...!'))
                    time.sleep(120)
            except Exception as e:
                self.stdout.write(self.style.ERROR(F'{e}'))
                time.sleep(120)
                continue


def check_ssl(url):
    url = 'https://w3techs.com/sites/info/{}'.format(url)
    response = requests.get(url=url)
    response = scrapy.Selector(text=response.text)
    ssl_text = response.xpath("//div[p/a/text()='SSL Certificate Authority']/following-sibling::p[1]/text()").get(
        '').strip()
    if ssl_text == 'Invalid Domain':
        return False
    else:
        return True


def run_asyncio_task(coro):
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


async def fetch_page_content(page_link):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(page_link[1], ssl=False, allow_redirects=True) as response:
                if response.status == 200:
                    # Try to decode the response text with UTF-8
                    try:
                        html = await response.text(encoding='utf-8')
                    except UnicodeDecodeError:
                        # If decoding with UTF-8 fails, try with ISO-8859-1
                        html = await response.text(encoding='ISO-8859-1')

                    soup = BeautifulSoup(html, 'html.parser')
                    for script_or_style in soup(["script", "style"]):
                        script_or_style.decompose()
                    text = soup.get_text()
                    clean_text = re.sub(r'\s+', ' ', text)
                    data = page_link[0], clean_text.strip()
                    return data
                else:
                    print(f"Error fetching page: {response.status}")
                    return ''
    except Exception as e:
        print(f"Error: {e}")
        return ''


async def parse(website_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }
    assistant_page_links = []
    try:
        response = requests.get(website_url, allow_redirects=True, verify=False, headers=headers)
    except Exception as e:
        print(e)
        data_dict = {
            'links': '',
            'json_response': '',
            'data': {"page_available": False},
            'pages_text': ''
        }
        return data_dict
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        links = list(set([link.get('href') for link in soup.find_all('a')]))
        if not links:
            links = list(set([link.get('href') for link in soup.find_all('area')]))
        links = [urljoin(response.url, link) for link in links if link and not link.startswith('mailto:')]
        links = filter_links(links, website_url)

        json_response = links_determiner_assistant(','.join(links))  # assistant 1
        json_response = json.loads(json_response)
        data = 'home_page', website_url
        assistant_page_links.append(data)
        about_us_page = json_response.get('about_page', '')
        if about_us_page:
            data = 'about_page', about_us_page
            assistant_page_links.append(data)

        products_page = json_response.get('products_page', '')
        if products_page:
            data = 'products_page', products_page
            assistant_page_links.append(data)

        contact_page = json_response.get('contact_page', '')
        if contact_page:
            data = 'contact_page', contact_page
            assistant_page_links.append(data)

        tasks = [fetch_page_content(page_link) for page_link in assistant_page_links]
        pages_text = await asyncio.gather(*tasks)
        pages_text = list(filter(None, pages_text))
        api_hunter_url = f'https://api.hunter.io/v2/domain-search?domain={website_url}&limit=100&api_key=8081bb56d8a84310a6e2ce9ac4950b270a3127e7'
        response = requests.get(api_hunter_url, verify=False, headers=headers)
        data, pages_json_with_key = await get_api_hunter_data(response, pages_text)
        data_dict = {
            'links': links,
            'json_response': json_response,
            'data': data,
            'pages_json_with_key': pages_json_with_key,
            'pages_text': pages_text
        }
        return data_dict
    else:
        data_dict = {
            'links': '',
            'json_response': {"page_available": False},
            'data': '',
            'pages_text': ''
        }
        return data_dict


async def get_api_hunter_data(response, pages_text):
    final_json = await run_assistant(response, pages_text)  # TODO : RUN ASSISTANT AND GET FINAL JSON
    return final_json
