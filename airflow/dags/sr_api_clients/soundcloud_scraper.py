"""
Scrapes SoundCloud artist's profile page for statistics.

@dogu - 2025-04-23
EDIT: 'Think I am figuring this web scraping thing out.
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

def load_soundcloud_search_results(query: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)  # headless=True in prod.
        page = browser.new_page()
        
        search_url = f"https://soundcloud.com/search/people?q={query}"
        page.goto(search_url, timeout=60000)

        try:
            page.wait_for_selector('button#onetrust-accept-btn-handler', timeout=5000)
            page.click('button#onetrust-accept-btn-handler')
            print("✅ Cookie acceptance button clicked.")
        except:
            print("⚠️ No cookie banner found or already accepted.")

        # full HTML
        html = page.content()

        browser.close()
        return html
    
def parse_soundcloud_srp(html, artist_name):
    """
    Parses a SoundCloud Search Results Page (SRP) and returns artist profile candidates.

    Parameters:
        html (str): HTML content of the SRP.
        artist_name (str): Original artist name we are searching for.

    Returns:
        list of dict: Each dict contains 'display_name' and 'profile_url'.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    results = []

    for link in soup.select('a.sc-link-dark.sc-link-primary'):
        display_name = link.text.strip()
        profile_url = link.get('href')

        if not profile_url:
            continue
        if not profile_url.startswith("https://"):
            profile_url = f"https://soundcloud.com{profile_url}"

        results.append({
            "display_name": display_name,
            "profile_url": profile_url
        })

    return results

def navigate_to_soundcloud_profile(query: str, artist_name: str) -> str:
    """
    Launches a browser, searches SoundCloud for the artist name,
    clicks the best matching result, and returns the resulting profile URL.

    Parameters:
        query (str): Search query.
        artist_name (str): Expected artist display name.

    Returns:
        str: URL of the artist's profile page if found, else None.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        page = browser.new_page()

        search_url = f"https://soundcloud.com/search/people?q={query}"
        page.goto(search_url, timeout=60000)

        try:
            page.wait_for_selector('button#onetrust-accept-btn-handler', timeout=5000)
            page.click('button#onetrust-accept-btn-handler')
        except:
            pass

        page.wait_for_selector('a.sc-link-dark.sc-link-primary', timeout=10000)
        links = page.query_selector_all('a.sc-link-dark.sc-link-primary')

        for link in links:
            name = link.inner_text().strip()
            href = link.get_attribute('href')
            if name.lower() == artist_name.lower():
                profile_url = f"https://soundcloud.com{href}" if not href.startswith("https://") else href
                print(f"🎯 Navigating to artist profile: {profile_url}")
                page.goto(profile_url)
                page.wait_for_timeout(3000)
                final_url = page.url
                browser.close()
                return final_url

        print("❌ No exact match found.")
        browser.close()
        return None
    
# ------ TESTING ------ 
if __name__ == "__main__":
    test_query = "Kilcasca"
    expected_display_name = "insyt."

    profile_url = navigate_to_soundcloud_profile(test_query, expected_display_name)

    if profile_url:
        print(f"✅ Successfully navigated to: {profile_url}")
    else:
        print("❌ Artist profile could not be found.")
