import json
import asyncio
import aiohttp
import re
from urllib.parse import urljoin

import scrapy
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
import requests
from bs4 import BeautifulSoup
from django.contrib.auth import logout
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView
from home.forms import CustomSignupForm
from home.toolbox import links_determiner_assistant, run_assistant, filter_links, get_links_and_emails, clean_url
import logging
from urllib.parse import urlparse
import socket
import ssl
from home.url_determiner import evaluate_preference
import codecs

logging.basicConfig(level=logging.INFO)


def home(request):
    return render(request, 'index.html')


# def get_longer_url_text(url):
#     http_url = 'http://' + url
#     https_url = 'https://' + url
#     try:
#         response_http = requests.get(http_url, verify=False)
#         response_https = requests.get(https_url, verify=False)
#     except requests.exceptions.RequestException as e:
#         print("Error making requests:", e)
#         return None
#     # if len(response_http.text) > len(response_https.text):
#     #     return http_url
#     # else:
#     #     return https_url
#     soup1 = BeautifulSoup(response_http.text, 'html.parser')
#     http_links = list(set([link.get('href') for link in soup1.find_all('a')]))
#     http_links = [urljoin(response_http.url, link) for link in http_links if link and not link.startswith('mailto:')]
#     http_links = filter_links(http_links, response_http.url)
#
#     soup2 = BeautifulSoup(response_https.text, 'html.parser')
#     https_links = list(set([link.get('href') for link in soup2.find_all('a')]))
#     https_links = [urljoin(response_https.url, link) for link in https_links if link and not link.startswith('mailto:')]
#     https_links = filter_links(https_links, response_https.url)
#
#     if len(http_links) == len(https_links):
#         return https_url
#     elif len(http_links) > len(https_links):
#         return http_url
#     else:
#         return https_url

# def has_valid_ssl(url):
#     try:
#         ctx = ssl.create_default_context()
#         with ctx.wrap_socket(socket.socket(), server_hostname=url) as s:
#             s.connect((url, 443))
#         # print(url+" has valid SSL")
#         return True
#
#     except Exception as e:
#         return False
#         # print(url+": has INVALID SSL, error:"+str(e))


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
        # protocol, domain = evaluate_preference(clean_website_url)
        # website_url = f'{protocol}://{domain}'
        ssl_info = check_ssl(clean_website_url)
        if ssl_info:
            website_url = f'https://www.{clean_website_url}'
        else:
            website_url = f'http://www.{clean_website_url}'

        try:
            if asyncio.get_event_loop().is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                data_dict = loop.run_until_complete(parse(website_url))
            else:
                data_dict = asyncio.run(parse(website_url))
        except RuntimeError as e:
            if str(e) == 'Event loop is closed':
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                data_dict = loop.run_until_complete(parse(website_url))
            else:
                raise e

        # if hasattr(asyncio, 'run'):
        #     data_dict = asyncio.run(parse(website_url))
        # else:
        #     loop = asyncio.new_event_loop()
        #     asyncio.set_event_loop(loop)
        #     try:
        #         data_dict = loop.run_until_complete(parse(website_url))
        #     finally:
        #         loop.close()

        # Extract necessary data from the parsed result
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

        final_json = codecs.decode(json.dumps(data_dict.get('data')), 'unicode_escape')
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
        return render(request, 'scraper_runner.html', context=context)
    else:
        return render(request, 'scraper_runner.html')


# async def fetch_page_content(page_link):
#     headers = {
#         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
#     }
#
#     try:
#         response = requests.get(page_link, verify=False, headers=headers)
#         soup = BeautifulSoup(response.content, 'html.parser')
#         for script_or_style in soup(["script", "style"]):
#             script_or_style.decompose()
#         text = soup.get_text()
#         clean_text = re.sub(r'\s+', ' ', text)
#         # clean_text = remove_html_tags(str())
#         return clean_text.strip()
#
#     except Exception as e:
#         print(f"Error fetching page: {e}")
#         return None

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
    # pages_text = []
    assistant_page_links = []
    # response = requests.get(website_url, verify=False)
    # page_response = Selector(text=response.text)
    # links = list(set(page_response.css('a::attr(href)').getall()))
    # try:
    try:
        response = requests.get(website_url, allow_redirects=True, verify=False, headers=headers)
    except:
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

        api_hunter_url = f'https://api.hunter.io/v2/domain-search?domain={website_url}&limit=100&api_key=8081bb56d8a84310a6e2ce9ac4950b270a3127e7'
        response = requests.get(api_hunter_url, verify=False, headers=headers)
        # data = await get_api_hunter_data(response, [text[1] for text in pages_text if text])
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

    # except Exception as e:
    #     print(e)
    #     data_dict = {
    #         'links': '',
    #         'json_response': '',
    #         'data': {"page_available": False},
    #         'pages_text': ''
    #     }
    #     return data_dict


async def get_api_hunter_data(response, pages_text):
    final_json = await run_assistant(response, pages_text)  # TODO : RUN ASSISTANT AND GET FINAL JSON
    return final_json


@csrf_exempt
@login_required(login_url='login')
def scrape_email_and_links(request):
    if request.method == "POST":
        website_url = request.POST.get('website').rstrip('/')
        if not website_url.startswith('http'):
            website_url = 'http://' + website_url
        unique_links, unique_mails = get_links_and_emails(website_url)
        context = {
            'website_url': website_url,
            'unique_links': unique_links,
            'unique_mails': unique_mails
        }
        return render(request, 'scrape_emails_and_links.html',
                      context=context
                      )
    else:
        return render(request, 'scrape_emails_and_links.html')


class SignUpView(CreateView):
    form_class = CustomSignupForm
    success_url = reverse_lazy('login')
    template_name = 'registration.html'


def logout_view(request):
    logout(request)
    return redirect('login')
