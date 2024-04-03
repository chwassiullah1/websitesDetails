import asyncio
import json
import re
from urllib.parse import urlparse
from fuzzywuzzy import fuzz
from openai import AsyncOpenAI, OpenAI
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import logging

logging.basicConfig(level=logging.INFO)

api_key = ''


def remove_html_tags(text):
    clean_text = re.sub('<[^<]+?>', '', text)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    return clean_text.strip()


def filter_links(links, website_url):
    excluded_substrings = ['youtube', 'linkedin', 'facebook', 'instagram', 'twitter', 'x.com']
    parsed_website_url = urlparse(website_url)
    website_domain = parsed_website_url.netloc
    filtered_links = []
    for link in links:
        parsed_link = urlparse(link)
        link_domain = parsed_link.netloc
        if any(substring in link_domain for substring in excluded_substrings) or link_domain == website_domain:
            filtered_links.append(link)

    if website_url not in filtered_links:
        filtered_links.append(website_url)
    return filtered_links


def company_longest_name(final_json):
    data = json.loads(final_json)
    company_names = data.get("company_legal_name", [])

    if type(company_names) == list:
        longest_name = ""
        for name in company_names:
            if len(name) > len(longest_name):
                longest_name = name
        data["company_legal_name"] = longest_name
    else:
        data["company_legal_name"] = company_names
    return data


def company_shortest_name(data):
    company_short_names = data.get("company_short_name", [])
    shortest_name = None
    if type(company_short_names) == list:
        for name in company_short_names:
            if name and (shortest_name is None or len(name) < len(shortest_name)):
                shortest_name = name
        data["company_short_name"] = shortest_name

    else:
        data["company_short_name"] = company_short_names
    return data


def remove_duplicate_products(data):
    products = data.get("product", [])
    if products:
        products = list(set([product.lower() for product in products]))
        products = [product.title() for product in products]
        data["product"] = products
        return data
    else:
        data["product"] = []
        return data


def similarity_ratio(a, b):
    return fuzz.token_sort_ratio(a, b)


def standardize_value(value):
    if isinstance(value, bool):
        return str(value).lower()
    else:
        return value.strip() if isinstance(value, str) else value


def remove_duplicates_addresses(data):
    addresses = data.get("address", [])
    unique_addresses = []
    for address_data in addresses:
        new_address = address_data["street_and_city_and_state"].strip().lower()
        new_country = address_data["country"].lower()
        new_iso_code = address_data["two_digit_iso_country_code"].lower()

        is_unique = True
        for unique_address_data in unique_addresses:
            existing_address = unique_address_data["street_and_city_and_state"]
            existing_country = unique_address_data["country"]
            existing_iso_code = unique_address_data["two_digit_iso_country_code"]
            address_similarity = similarity_ratio(new_address, existing_address)
            country_similarity = similarity_ratio(new_country, existing_country)
            iso_code_similarity = similarity_ratio(new_iso_code, existing_iso_code)
            if address_similarity >= 80 or country_similarity >= 80 or iso_code_similarity >= 80:
                is_unique = False
                break

        if is_unique:
            unique_addresses.append({
                "street_and_city_and_state": new_address,
                "country": new_country,
                "two_digit_iso_country_code": new_iso_code
            })
    data['address'] = unique_addresses
    return data


def merge_website_pages_json_api_hunter_json(api_hunter_json_str, website_pages_merged_json_str):
    data = json.loads(api_hunter_json_str)
    keys = ['domain', 'disposable', 'webmail', 'accept_all', 'pattern', 'organization', 'linkedin', 'instagram',
            'technologies', 'emails', 'twitter', 'youtube', 'facebook']
    result_dict = {key: data['data'][key] for key in keys}
    email_values = list(set([email['value'] for email in result_dict['emails']]))
    result_dict['e-mail'] = email_values
    del result_dict['emails']

    website_pages_merged_json = json.loads(website_pages_merged_json_str)
    for key, value in result_dict.items():
        if key in website_pages_merged_json:
            if isinstance(website_pages_merged_json[key], list):
                website_pages_merged_json[key] = list(set(website_pages_merged_json[key] + value))
            elif isinstance(website_pages_merged_json[key], dict):
                for k, v in value.items():
                    if k in website_pages_merged_json[key]:
                        website_pages_merged_json[key][k] = list(set(website_pages_merged_json[key][k] + v))
                    else:
                        website_pages_merged_json[key][k] = v
            else:
                website_pages_merged_json[key] = value
        else:
            website_pages_merged_json[key] = value
    return website_pages_merged_json


def merge_all_pages_jsons(json_list):
    merged_json = {}
    if json_list:
        for json_obj in json_list:
            json_obj = json.loads(json_obj)
            for key, value in json_obj.items():
                if value is not None:
                    if key not in merged_json:
                        merged_json[key] = standardize_value(value)
                    else:
                        if isinstance(value, list):
                            if all(isinstance(item, dict) for item in value):
                                if isinstance(merged_json[key], str):
                                    merged_json[key] = json.loads(merged_json[key])
                                merged_json[key].extend([dict(items) for items in set(
                                    tuple((k, standardize_value(v)) for k, v in d.items() if
                                          standardize_value(v) is not None) for d in
                                    merged_json[key] + value)])
                                # Remove duplicates
                                merged_json[key] = remove_duplicates(merged_json[key])
                            else:
                                merged_json[key].extend(
                                    list(set(standardize_value(v) for v in value)))
                                # Remove duplicates
                                merged_json[key] = remove_duplicates(merged_json[key])
                        elif isinstance(value, dict):
                            if isinstance(merged_json[key], str):
                                merged_json[key] = json.loads(merged_json[key])
                            merged_json[key] = merge_all_pages_jsons([merged_json[key], value])
                        else:
                            standardized_value = standardize_value(value)
                            if isinstance(merged_json[key], list):
                                if standardized_value not in merged_json[key]:
                                    merged_json[key].append(standardized_value)
                            else:
                                if standardized_value != merged_json[key]:
                                    merged_json[key] = [merged_json[key], standardized_value]
        return json.dumps(merged_json).strip()


def remove_duplicates(lst):
    seen = set()
    result = []
    for item in lst:
        if isinstance(item, dict):
            items = tuple(sorted(item.items()))
            if items not in seen:
                seen.add(items)
                result.append(item)
        elif isinstance(item, str):
            if item not in seen:
                seen.add(item)
                result.append(item)
    return result


# TODO :  OPEN API ASSISTANT

async def run_assistant(response, pages_text):
    pages_json = await main(pages_text)
    website_pages_merged_json_str = merge_all_pages_jsons(pages_json)
    api_hunter_json_str = response.text
    all_json_merged = merge_website_pages_json_api_hunter_json(api_hunter_json_str,
                                                               website_pages_merged_json_str)
    all_json_merged = json.dumps(all_json_merged, ensure_ascii=False, indent=4)
    all_json_merged = company_longest_name(all_json_merged)
    all_json_merged = company_shortest_name(all_json_merged)
    all_json_merged = remove_duplicate_products(all_json_merged)
    return all_json_merged


async def main(pages_text):
    try:
        print("Starting main coroutine")
        tasks = [process_text(text) for text in pages_text]
        results = await asyncio.gather(*tasks)
        print("Main coroutine completed")
        return results
    except Exception as e:
        print("Error in main coroutine:", e)


async def process_text(text):
    client = AsyncOpenAI(api_key=api_key)
    thread = await client.beta.threads.create()
    message = await client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=text,
    )

    run = await client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id='asst_YKEOLC7zGJlJkMfCRCpygGzb',
    )

    while True:
        keep_retrieving_run = await client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id
        )
        print(f"Run status: {keep_retrieving_run.status}")
        if keep_retrieving_run.status == "completed":
            break
        await asyncio.sleep(1)
    all_messages = await client.beta.threads.messages.list(
        thread_id=thread.id
    )
    if all_messages:
        response_text = all_messages.data[0].content[0].text.value
        return response_text.replace('```json', '').replace('```', '').strip()
    else:
        return {}


def links_determiner_assistant(content):
    client = OpenAI(api_key=api_key)
    thread = client.beta.threads.create()
    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=content,
    )

    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id='asst_o4yfPHxGuXT2YB1vQSsptQ3f',
    )

    while run.status != "completed":
        keep_retrieving_run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id
        )
        print(f"Run status: {keep_retrieving_run.status}")

        if keep_retrieving_run.status == "completed":
            print("\n")
            break
    all_messages = client.beta.threads.messages.list(
        thread_id=thread.id
    )
    if all_messages:
        return all_messages.data[0].content[0].text.value


    else:
        return {}


def get_links_and_emails(website_url):
    options = Options()
    options.add_argument('--headless')  # Headless mode
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    driver.get(website_url)
    links = []
    mails = []
    emails = driver.find_elements(By.XPATH, '//a[contains(@href, "mailto:")]')
    for email in emails:
        mails.append(email.get_attribute('href').replace('mailto:', ''))
    raw_links = driver.find_elements(By.XPATH, '//a[not(contains(@href, "mailto:"))]')
    excluded_substrings = ['youtube', 'linkedin', 'facebook', 'instagram', 'twitter', 'x.com']
    if raw_links:
        for raw_link in raw_links:
            href = raw_link.get_attribute('href')
            if not href:
                continue
            domain = urlparse(website_url).netloc
            if 'javascript:;' in href or domain in href or any(substring in href for substring in excluded_substrings):
                continue
            else:
                links.append(href)
    driver.quit()
    links = list(filter(None, links))
    return list(set(links)), list(set(mails))


def clean_url(url):
    if not urlparse(url).scheme:
        url = 'http://' + url
    parsed_url = urlparse(url)
    domain = '{uri.netloc}'.format(uri=parsed_url)
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain
