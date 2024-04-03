import json
import asyncio
import aiohttp
import re
from urllib.parse import urljoin
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

from home.url_determiner import evaluate_preference
import codecs

logging.basicConfig(level=logging.INFO)


def home(request):
    return render(request, 'index.html')


@csrf_exempt
@login_required(login_url='login')
def run_scraper(request):
    if request.method == "POST":
        website_url = request.POST.get('website')
        clean_website_url = clean_url(website_url)
        protocol, domain = evaluate_preference(clean_website_url)
        website_url = f'{protocol}://{domain}'
        # parsed_url = urlparse(website_url)

        # if not parsed_url.scheme and parsed_url.path.startswith('www'):
        #     website_url = "http://" + parsed_url.path
        # elif not parsed_url.scheme and not parsed_url.path.startswith('www'):
        #     website_url = "http://www." + parsed_url.path
        # elif not parsed_url.netloc or not parsed_url.netloc.startswith("www."):
        #     website_url = parsed_url.scheme + "://www." + (parsed_url.netloc or '') + parsed_url.path

        # if not website_url.startswith('http'):
        #     website_url = 'http://' + website_url
        if hasattr(asyncio, 'run'):
            data_dict = asyncio.run(parse(website_url))
        else:
            # loop = asyncio.new_event_loop()
            # data_dict = loop.run_until_complete(parse(website_url))
            # loop.close()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                data_dict = loop.run_until_complete(parse(website_url))
            except Exception as e:
                print(e)
            finally:
                loop.close()

        links = data_dict.get('links')
        links = list(set(links))
        json_response = data_dict.get('json_response')
        data = data_dict.get('data')
        pages_text = data_dict.get('pages_text')
        home_page_text = ''
        about_page_text = ''
        products_page_text = ''
        contact_page_text = ''
        for text in pages_text:
            if text[0] == 'home_page':
                home_page_text = text[1]
            elif text[0] == 'about_page':
                about_page_text = text[1]
            elif text[0] == 'contact_page':
                contact_page_text = text[1]
            elif text[0] == 'products_page':
                products_page_text = text[1]
        final_json = codecs.decode(json.dumps(data), 'unicode_escape')
        context = {'final_json': final_json, 'raw_links': links,
                   'raw_link_json': json_response,
                   'home_page_text': home_page_text,
                   'about_page_text': about_page_text,
                   'products_page_text': products_page_text,
                   'contact_page_text': contact_page_text,
                   'website_url': website_url,
                   }
        return render(request, 'scraper_runner.html',
                      context=context
                      )
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
                    html = await response.text()
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
        print(f"Error fetching page: {e}")
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
    try:
        response = requests.get(website_url, allow_redirects=True, verify=False, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            links = list(set([link.get('href') for link in soup.find_all('a')]))
            links = [urljoin(response.url, link) for link in links]
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
            data = await get_api_hunter_data(response, [text[1] for text in pages_text])
            data_dict = {
                'links': links,
                'json_response': json_response,
                'data': data,
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


    except Exception as e:
        print(e)
        data_dict = {
            'links': '',
            'json_response': '',
            'data': {"page_available": False},
            'pages_text': ''
        }
        return data_dict


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
