import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse


def fetch_and_parse(url):
    """Fetches the webpage and parses it for internal links."""
    try:
        response = requests.get(url, allow_redirects=True, timeout=5, verify=False)
        if response.status_code == 200:
            if response.history and urlparse(response.url).scheme == 'https':
                return 'https', response.text
            elif response.status_code == 200:
                return urlparse(response.url).scheme, response.text
        else:
            return url, 'page not found.'
    except requests.RequestException:
        return None, None


def count_internal_links(html, domain):
    """Counts the number of internal links present in the HTML content."""
    if not html:
        return 0
    soup = BeautifulSoup(html, 'html.parser')
    links = soup.find_all('a', href=True)
    return sum(1 for link in links if domain in link['href'])


def evaluate_preference(domain):
    """Evaluates the protocol preference for the given domain."""

    http_url = f'http://{domain}'
    https_url = f'https://{domain}'

    http_protocol, http_html = fetch_and_parse(http_url)
    https_protocol, https_html = fetch_and_parse(https_url)

    if http_html == 'page not found.' and https_html == 'page not found.':
        return 'page not found.', False

    if http_protocol == 'https':
        return 'https', domain
        # return f"{domain} clearly prefers HTTPS due to auto-redirect."

    http_links = count_internal_links(http_html, domain)
    https_links = count_internal_links(https_html, domain)

    if http_links >= 5 or https_links >= 5:
        preferred_protocol = 'HTTP' if http_links > https_links else 'HTTPS'
        # return f"{domain} prefers {preferred_protocol} based on internal links count."
        return preferred_protocol.lower(), domain

    # return f"{domain} preference could not be determined based on the criteria."
    return 'https', domain
