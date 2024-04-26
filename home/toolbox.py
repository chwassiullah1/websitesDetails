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
    excluded_substrings = ['youtube', 'linkedin', 'facebook', 'instagram', 'twitter', 'x.com', 'javascript: void(0);',
                           'javascript:;']
    parsed_website_url = urlparse(website_url)
    website_domain = parsed_website_url.netloc.replace('www.', '')
    filtered_links = []
    for link in links:
        parsed_link = urlparse(link)
        link_domain = parsed_link.netloc.replace('www.', '')
        if not any(substring in link for substring in excluded_substrings) and link_domain == website_domain:
            filtered_links.append(link)

    if website_url not in filtered_links:
        filtered_links.append(website_url)
    return filtered_links


def company_longest_name(company_legal_name):
    company_names = company_legal_name
    if type(company_names) == list:
        longest_name = ""
        for name in company_names:
            if len(name) > len(longest_name):
                longest_name = name
        company_legal_name = longest_name
    return company_legal_name


def company_shortest_name(company_short_name):
    company_short_names = company_short_name
    shortest_name = None
    if type(company_short_names) == list:
        for name in company_short_names:
            if name and (shortest_name is None or len(name) < len(shortest_name)):
                shortest_name = name
        company_short_name = shortest_name
    return company_short_name


# def remove_duplicate_products(data):
#     products = data.get("product", [])
#     if products:
#         products = list(set([product.lower() for product in products]))
#         products = [product.title() for product in products]
#         data["product"] = products
#         return data
#     else:
#         data["product"] = []
#         return data


def similarity_ratio(a, b):
    return fuzz.token_sort_ratio(a, b)


def standardize_value(value):
    if isinstance(value, bool):
        return str(value).lower()
    else:
        return value.strip() if isinstance(value, str) else value


def remove_duplicates_addresses(address):
    addresses = address
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
    return unique_addresses


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


# OLD CODE
# def merge_all_pages_jsons(json_list):
#     merged_json = {}
#     if json_list:
#         for json_obj in json_list:
#             json_obj = json.loads(json_obj)
#             for key, value in json_obj.items():
#                 if value is not None:
#                     if key not in merged_json:
#                         merged_json[key] = standardize_value(value)
#                     else:
#                         if isinstance(value, list):
#                             if all(isinstance(item, dict) for item in value):
#                                 if isinstance(merged_json[key], str):
#                                     merged_json[key] = json.loads(merged_json[key])
#                                 merged_json[key].extend([dict(items) for items in set(
#                                     tuple((k, standardize_value(v)) for k, v in d.items() if
#                                           standardize_value(v) is not None) for d in
#                                     merged_json[key] + value)])
#                                 # Remove duplicates
#                                 merged_json[key] = remove_duplicates(merged_json[key])
#                             else:
#                                 merged_json[key].extend(
#                                     list(set(standardize_value(v) for v in value)))
#                                 # Remove duplicates
#                                 merged_json[key] = remove_duplicates(merged_json[key])
#                         elif isinstance(value, dict):
#                             if isinstance(merged_json[key], str):
#                                 merged_json[key] = json.loads(merged_json[key])
#                             merged_json[key] = merge_all_pages_jsons([merged_json[key], value])
#                         else:
#                             standardized_value = standardize_value(value)
#                             if isinstance(merged_json[key], list):
#                                 if standardized_value not in merged_json[key]:
#                                     merged_json[key].append(standardized_value)
#                             else:
#                                 if standardized_value != merged_json[key]:
#                                     merged_json[key] = [merged_json[key], standardized_value]
#         return json.dumps(merged_json).strip()

# old code 2
# def merge_dicts(dict1, dict2):
#     merged_dict = {**dict1, **dict2}
#     for key, value in merged_dict.items():
#         if isinstance(value, list):
#             if all(isinstance(item, dict) for item in value):
#                 merged_dict[key] = [merge_dicts(d1, d2) for d1, d2 in zip(dict1.get(key, []), value)]
#             else:
#                 merged_dict[key] = remove_duplicates(value)
#     return merged_dict
#
#
# def merge_all_pages_jsons(json_list):
#     merged_json = {}
#     company_legal_name = []
#     company_short_name = []
#     for json_obj in json_list:
#         try:
#             json_obj = json.loads(json_obj.replace('null', '""'))
#         except json.JSONDecodeError:
#             continue
#
#         # Check if 'company_legal_name' is present in the current JSON object
#         if 'company_legal_name' in json_obj:
#             if json_obj['company_legal_name'] is not None:
#                 company_legal_name.append(json_obj['company_legal_name'])
#
#         if 'company_short_name' in json_obj:
#             if json_obj['company_short_name'] is not None:
#                 company_short_name.append(json_obj['company_short_name'])
#
#         # Merge the current JSON object with the merged JSON
#         for key, value in json_obj.items():
#             # Handle None values consistently
#             if value is None:
#                 continue
#             existing_value = merged_json.get(key)
#             if isinstance(value, list):
#                 if all(isinstance(item, dict) for item in value):
#                     if isinstance(existing_value, str):
#                         if existing_value:
#                             existing_value = json.loads(existing_value)
#                     if isinstance(existing_value, list) and all(
#                             isinstance(item, dict) for item in existing_value):
#                         merged_json[key] = [merge_dicts(d1, d2) for d1, d2 in zip(existing_value, value)]
#                     else:
#                         merged_json[key] = []
#                 merged_json[key] = remove_duplicates(
#                     [standardize_value(v) for v in (existing_value or []) + value])
#             elif isinstance(value, dict):
#                 if existing_value is None:
#                     merged_json[key] = value
#                 else:
#                     try:
#                         merged_json[key] = merge_dicts(existing_value, value)
#                     except TypeError:
#                         pass
#             else:
#                 if existing_value is None or existing_value != standardize_value(value):
#                     merged_json[key] = standardize_value(value)
#
#     if company_legal_name is not None:
#         merged_json['company_legal_name'] = company_legal_name
#
#     if company_short_name is not None:
#         merged_json['company_short_name'] = company_short_name
#
#     return json.dumps(merged_json).strip()


# def remove_duplicates(lst):
#     seen = set()
#     result = []
#     for item in lst:
#         if isinstance(item, dict):
#             items = tuple(sorted(item.items()))
#             if items not in seen:
#                 seen.add(items)
#                 result.append(item)
#         elif isinstance(item, str):
#             if item not in seen:
#                 seen.add(item)
#                 result.append(item)
#     return result

def merge_all_pages_jsons(json_list):
    company_legal_name = []
    company_short_name = []
    company_founded_year = []
    product = []
    service = []
    company_code = []
    address = []
    e_mail = []
    company_phone_numbers = []
    company_description = []
    company_headquarter_country_iso_code = []
    naics_code = []
    sector = []
    entity_type = []
    is_exporter_or_importer = []
    merged_data = dict()
    for item in json_list:
        if item:
            item = json.loads(item.lower())
            if item.get('company_legal_name'):
                company_legal_name.append(item.get('company_legal_name'))
            if item.get('company_short_name'):
                company_short_name.append(item.get('company_short_name'))
            if item.get('company_founded_year'):
                company_founded_year.append(item.get('company_founded_year'))
            if item.get('product'):
                product.extend(item.get('product'))
            if item.get('service'):
                service.extend(item.get('service'))
            if item.get('company_code'):
                company_code.append(item.get('company_code'))
            if item.get('address'):
                address.extend(item.get('address'))
            if item.get('e-mail'):
                e_mail.extend(item.get('e-mail'))
            if item.get('company_phone_numbers'):
                company_phone_numbers.extend(item.get('company_phone_numbers'))
            if item.get('company_description'):
                company_description.append(item.get('company_description'))
            if item.get('company_headquarter_country_iso_code'):
                company_headquarter_country_iso_code.append(item.get('company_headquarter_country_iso_code'))
            if item.get('naics_code'):
                naics_code.append(item.get('naics_code'))
            if item.get('sector'):
                sector.append(item.get('sector'))
            if item.get('entity_type'):
                entity_type.append(item.get('entity_type'))
            if item.get('is_exporter_or_importer'):
                is_exporter_or_importer.append(item.get('is_exporter_or_importer'))

    merged_data["company_legal_name"] = company_longest_name(company_legal_name)
    merged_data["company_short_name"] = company_shortest_name(company_short_name)
    company_founded_year = [int(year) for year in company_founded_year if year.isdigit()]
    if company_founded_year:
        company_founded_year = min(company_founded_year)
    else:
        company_founded_year = ''
    merged_data["company_founded_year"] = company_founded_year
    merged_data["product"] = list(set(product))
    merged_data["service"] = list(set(service))
    merged_data["company_code"] = list(set(company_code))
    unique_combinations = {tuple(sorted(d.items())) for d in address if isinstance(d, dict)}
    unique_address = [dict(comb) for comb in unique_combinations]
    merged_data["address"] = unique_address
    merged_data["e-mail"] = list(set(e_mail))
    merged_data["company_phone_numbers"] = list(set(company_phone_numbers))
    merged_data["company_description"] = list(set(company_description))
    merged_data["company_headquarter_country_iso_code"] = list(set(company_headquarter_country_iso_code))
    merged_data["naics_code"] = list(set(naics_code))
    merged_data["sector"] = list(set(sector))
    merged_data["entity_type"] = ', '.join(set(entity_type)) if len(set(entity_type)) == 1 else list(set(entity_type))
    merged_data["is_exporter_or_importer"] = list(set(is_exporter_or_importer))
    return json.dumps(merged_data)


# TODO :  OPEN API ASSISTANT

async def run_assistant(response, pages_text):
    pages_json_with_key = await main(pages_text)
    website_pages_merged_json_str = merge_all_pages_jsons([js_str[1] for js_str in pages_json_with_key if js_str])
    if not website_pages_merged_json_str == '{"page_available": False}':
        api_hunter_json_str = response.text

        all_json_merged = merge_website_pages_json_api_hunter_json(api_hunter_json_str,
                                                                   website_pages_merged_json_str)
        all_json_merged = json.dumps(all_json_merged, ensure_ascii=False, indent=4).lower()
        return all_json_merged, pages_json_with_key
    else:
        return {"page_available": False}


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
        content=text[1],
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
        data = text[0], response_text.replace('```json', '').replace('```', '').strip()
        return data
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
