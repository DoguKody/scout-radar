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
    Loads SoundCloud search results for a given query, finds the best matching artist name,
    and returns their profile URL if found.

    Parameters:
        query (str): Search query to input.
        artist_name (str): Target artist name to match.

    Returns:
        str: Full profile URL of the matching artist, or None if not found.
    """
    html = load_soundcloud_search_results(query)
    results = parse_soundcloud_srp(html, artist_name)
    print(results)

    # normalization
    clean_artist = artist_name.strip().lower()

    for result in results:
        display = result["display_name"].strip().lower()
        print(display)
        if display == clean_artist:
            print(f"✅ Exact match found: {result['display_name']} → {result['profile_url']}")
            return result["profile_url"]

    print("❌ No exact match found.")
    return None

    
# ------ TESTING ------ 
if __name__ == "__main__":
    test_query = "Chai Sully"
    expected_display_name = "Chai Sully" 

    profile_url = navigate_to_soundcloud_profile(test_query, expected_display_name)

    if profile_url:
        print(f"✅ Successfully navigated to: {profile_url}")
    else:
        print("❌ Artist profile could not be found.")