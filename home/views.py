import json
import asyncio
from datetime import datetime
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
from home.models import ProcessTwoJobs, EmailDetails
from home.toolbox import links_determiner_assistant, run_assistant, filter_links, clean_url, \
    generate_emails, validate_email_with_api
import logging
import codecs

logging.basicConfig(level=logging.INFO)


def home(request):
    return render(request, 'index.html')


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


@csrf_exempt
@login_required(login_url='login')
def add_jobs(request):
    if request.method == "POST":
        urls = request.POST.get('urls')
        status = 0
        now = datetime.now().strftime('%Y-%m-%d')
        instance = ProcessTwoJobs.objects.create(
            urls=urls,
            status=status,
            created_at=now
        )
        instance.save()
        return render(request, 'add_jobs.html')
    else:
        return render(request, 'add_jobs.html')


class SignUpView(CreateView):
    form_class = CustomSignupForm
    success_url = reverse_lazy('login')
    template_name = 'registration.html'


@csrf_exempt
@login_required(login_url='login')
def view_jobs(request):
    jobs = ProcessTwoJobs.objects.all().order_by('-id')
    return render(request, 'jobs.html', {'jobs': jobs})


@csrf_exempt
@login_required(login_url='login')
def add_and_review(request, pk):
    job = ProcessTwoJobs.objects.get(id=pk)
    if request.method == 'POST':
        unique_links = request.POST.get('links')
        unique_emails = request.POST.get('emails')
        job.unique_links = str(unique_links.split('\n'))
        job.unique_emails = str(unique_emails.split('\n'))
        job.save()
        context = {'links': '\n'.join(eval(job.unique_links)), 'emails': '\n'.join(eval(job.unique_emails))}
        return render(request, 'add_and_review.html', context=context)
    else:
        context = {'links': '\n'.join(eval(job.unique_links)), 'emails': '\n'.join(eval(job.unique_emails))}
        return render(request, 'add_and_review.html', context=context)


@csrf_exempt
@login_required(login_url='login')
def validate_emails(request):
    emails = []
    json_responses = []
    if request.method == 'POST':
        if 'form1' in request.POST:
            input1 = request.POST.get('input1')
            input2 = request.POST.get('input2')
            input3 = request.POST.get('input3')
            result = generate_emails(input1, input2, input3)
            emails.extend(result)
            # return render(request, 'validate_email.html')
        elif 'form2' in request.POST:
            email = request.POST.get('email')
            emails.append(email)
            # return render(request, 'validate_email.html')
        email_results = validate_email_with_api(emails)  # return tuple ( inputEmail , jsonResponse )
        for email_result in email_results:
            json_responses.append(email_result[1])
            try:
                email_obj = EmailDetails.objects.get(input_emails=email_result[0])
            except:
                email_obj = None
            if not email_obj:
                obj = EmailDetails.objects.create(input_emails=email_result[0], email_detail=email_result[1])
                obj.save()

        extracted_data = [{"address": entry.get("address"), "status": entry.get("status")} for entry in json_responses]

        return render(request, 'validate_email.html', context={'extracted_data', extracted_data})



    else:
        return render(request, 'validate_email.html')


def logout_view(request):
    logout(request)
    return redirect('login')
