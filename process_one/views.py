import json
import asyncio
import aiohttp
import re
from urllib.parse import urljoin
import scrapy
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
import requests
from bs4 import BeautifulSoup
from home.toolbox import links_determiner_assistant, run_assistant, filter_links, clean_url
import logging
import codecs
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO)
from process_one.models import DomainsData


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


@csrf_exempt
@login_required(login_url='login')
def run_scraper(request):
    if request.method == "POST":
        website_url = request.POST.get('website')
        clean_website_url = clean_url(website_url)
        query = {
            "data": {"domain": clean_website_url, "$options": "i"}  # Case-insensitive search
        }
        existing_domain = DomainsData.objects.filter(**query).first()
        if not existing_domain:
            ssl_info = check_ssl(clean_website_url)
            if ssl_info:
                website_url = f'https://www.{clean_website_url}'
            else:
                website_url = f'http://www.{clean_website_url}'
            if hasattr(asyncio, 'run'):
                data_dict = asyncio.run(parse(website_url))
            else:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    data_dict = loop.run_until_complete(parse(website_url))
                finally:
                    loop.close()
            links = list(set(data_dict.get('links', [])))
            json_response = data_dict.get('json_response')
            pages_text = data_dict.get('pages_text', [])
            pages_text = list(filter(None, pages_text))
            home_page_text, about_page_text, products_page_text, contact_page_text = '', '', '', ''
            home_page_json, about_page_json, products_page_json, contact_page_json = {}, {}, {}, {}
            for text in pages_text:
                if text[0] == 'home_page':
                    home_page_text = text[1]
                elif text[0] == 'about_page':
                    about_page_text = text[1]
                elif text[0] == 'contact_page':
                    contact_page_text = text[1]
                elif text[0] == 'products_page':
                    products_page_text = text[1]

            pages_json_with_key = data_dict.get('pages_json_with_key', [])
            pages_json_with_key = list(filter(None, pages_json_with_key))
            for json_str in pages_json_with_key:
                if json_str[0] == 'home_page':
                    home_page_json = json_str[1]
                elif json_str[0] == 'about_page':
                    about_page_json = json_str[1]
                elif json_str[0] == 'contact_page':
                    contact_page_json = json_str[1]
                elif json_str[0] == 'products_page':
                    products_page_json = json_str[1]
            final_json = codecs.decode(data_dict.get('data'), 'unicode_escape')
            context = {'final_json': final_json, 'raw_links': links,
                       'raw_link_json': json_response,
                       'home_page_text': home_page_text,
                       'about_page_text': about_page_text,
                       'products_page_text': products_page_text,
                       'contact_page_text': contact_page_text,
                       'home_page_json': home_page_json,
                       'about_page_json': about_page_json,
                       'contact_page_json': contact_page_json,
                       'products_page_json': products_page_json,
                       'website_url': website_url,
                       }
            if final_json:
                final_json_data = json.loads(final_json)
                instance = DomainsData.objects.create(data=final_json_data)
                instance.save()
                context['message'] = 'Domain Added to database..'
        else:
            context = {'message': 'Domain Already exist..!'}
        return render(request, 'scraper_runner.html', context=context)
    else:
        return render(request, 'scraper_runner.html')


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
            'data': '{"page_available": "false"}',
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
    # else:
    #     data_dict = {
    #         'links': '',
    #         'json_response': '{"page_available": "false"}',
    #         'data': '',
    #         'pages_text': ''
    #     }
    #     return data_dict


async def get_api_hunter_data(response, pages_text):
    final_json = await run_assistant(response, pages_text)  # TODO : RUN ASSISTANT AND GET FINAL JSON
    return final_json


# Create your views here.
def search_data(request):
    if request.method == "POST":
        country = request.POST.get('country')
        street_and_city_and_state = request.POST.get('street_and_city_and_state')
        two_digit_iso_country_code = request.POST.get('two_digit_iso_country_code')
        product = request.POST.get('product')
        service = request.POST.get('service')
        company_headquarter_country_iso_code = request.POST.get('company_headquarter_country_iso_code')
        sector = request.POST.get('sector')
        entity_type = request.POST.get('entity_type')
        client = MongoClient('mongodb://localhost:27017/')
        db = client['domains_data']
        collection = db['domains_data']
        query = {}
        address_query = {}
        if country:
            address_query['country'] = country
        if street_and_city_and_state:
            address_query['street_and_city_and_state'] = street_and_city_and_state
        if two_digit_iso_country_code:
            address_query['two_digit_iso_country_code'] = two_digit_iso_country_code
        if address_query:
            query['data.address'] = {'$elemMatch': address_query}
        if product:
            query['data.product'] = product
        if service:
            query['data.service'] = service
        if company_headquarter_country_iso_code:
            query['data.company_headquarter_country_iso_code'] = company_headquarter_country_iso_code
        if sector:
            query['data.sector'] = sector
        if entity_type:
            query['data.entity_type'] = entity_type
        if country or street_and_city_and_state or two_digit_iso_country_code or company_headquarter_country_iso_code or product or service or sector or entity_type:
            results = collection.find(query)
            json_list = []
            documents = list(results)
            for document in documents:
                json_string = json.dumps(document.get('data'), ensure_ascii=False)
                decoded_json_string = json_string.encode('latin1').decode('utf-8')
                decoded_document = json.loads(decoded_json_string)
                json_list.append(decoded_document)
            if json_list:
                context = {'json_data': json_list}
            else:
                context = {'json_data': ''}
        else:
            context = {'json_data': ''}
        return render(request, 'search_data.html', context=context)
    else:
        context = {'json_data': ''}
        return render(request, 'search_data.html', context=context)
