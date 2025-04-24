"""
Scrapes SoundCloud artist's profile page for statistics.

@dogu - 2025-04-23
EDIT: 'Think I am figuring this web scraping thing out.
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time
import json

def load_soundcloud_search_results(query: str, page) -> str:
    """
    Loads SoundCloud search results for a given query using an existing page instance.
    """
    search_url = f"https://soundcloud.com/search/people?q={query}"
    page.goto(search_url, timeout=60000)

    try:
        page.wait_for_selector('button#onetrust-accept-btn-handler', timeout=5000)
        page.click('button#onetrust-accept-btn-handler')
        print("✅ Cookie acceptance button clicked.")
    except:
        print("⚠️ No cookie banner found or already accepted.")

    return page.content()
    
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

# helper for `navigate_to_soundcloud_profile`
import time
from playwright.sync_api import Page

def auto_scroll_tracks(page: Page,
                       item_selector: str = "a.sc-link-primary.soundTitle__title.sc-link-dark.sc-text-h4",
                       pause_ms: int = 2000,
                       max_cycles: int = 50) -> int:
    """
    Scrolls the SoundCloud /tracks page until no new tracks load.

    Parameters:
        page (Page): Playwright page at the artist’s /tracks URL.
        item_selector (str): CSS selector for each track link element.
        pause_ms (int): Milliseconds to wait after each scroll.
        max_cycles (int): Safety cap on scroll iterations.

    Returns:
        int: Total number of track items found on the page.
    """
    # initial count
    prev_count = -1
    curr_count = len(page.query_selector_all(item_selector))
    cycles = 0

    while curr_count != prev_count and cycles < max_cycles:
        prev_count = curr_count
        cycles += 1

        # scroll to bottom
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(pause_ms / 1000)

        curr_count = len(page.query_selector_all(item_selector))

    print(f"⏹️ Scrolled {cycles} times; loaded {curr_count} tracks total.")
    return curr_count

def navigate_to_soundcloud_profile(query: str, artist_name: str) -> dict:
    """
    Finds the exact SoundCloud profile for `artist_name` via a SRP search of `query`,
    navigates to their /tracks page, scrolls to load all tracks, then aggregates
    total plays and comments in one JS evaluation.

    Returns:
        {
          "profile_url": str,
          "tracks_url": str,
          "total_plays": int,
          "total_comments": int
        }
        or None if no exact profile match is found.
    """
    from playwright.sync_api import sync_playwright
    from bs4 import BeautifulSoup

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # block all images, fonts, stylesheets for speed
        page.route(
            "**/*",
            lambda route, request: route.abort()
            if request.resource_type in ["image", "font", "stylesheet"]
            else route.continue_()
        )

        html = load_soundcloud_search_results(query, page)
        results = parse_soundcloud_srp(html, artist_name)

        clean = artist_name.strip().lower()
        artist_profile_url = next(
            (r["profile_url"] for r in results
             if r["display_name"].strip().lower() == clean),
            None
        )
        if not artist_profile_url:
            print("❌ No exact match found.")
            browser.close()
            return None

        tracks_url = f"{artist_profile_url}/tracks"
        page.goto(tracks_url, timeout=60000)

        # tight infinite-scroll to load every card
        prev_height = -1
        while True:
            height = page.evaluate("() => document.body.scrollHeight")
            if height == prev_height:
                break
            prev_height = height
            page.evaluate("h => window.scrollTo(0, h)", height)
            page.wait_for_timeout(500)

        # one JS round-trip to sum plays & comments
        result = page.evaluate("""
          () => {
            let plays = 0, comments = 0;
            document.querySelectorAll("div.sound__body").forEach(card => {
              card.querySelectorAll("ul.soundStats li").forEach(li => {
                const t = li.getAttribute("title") || "";
                const n = parseInt(
                  t.replace(/[^0-9,]/g,"")
                   .replace(/,/g,""),
                  10
                ) || 0;
                if (t.includes("play"))    plays    += n;
                if (t.includes("comment")) comments += n;
              });
            });
            return { plays, comments };
          }
        """)

        browser.close()
        return {
            "profile_url":    artist_profile_url,
            "tracks_url":     tracks_url,
            "total_plays":    result["plays"],
            "total_comments": result["comments"]
        }

    
# ------ TESTING ------ 
if __name__ == "__main__":
    import json

    test_query        = "insyt."   # soundcloud search q= 
    expected_name     = "insyt."   # must exactly match the display_name on SC

    result = navigate_to_soundcloud_profile(test_query, expected_name)
    if result:
        print("🎉 SCRAPE RESULT:")
        print(json.dumps(result, indent=2))
    else:
        print("❌ Artist profile could not be found or scraped.")
