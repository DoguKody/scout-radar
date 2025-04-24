"""
Scrapes SoundCloud artist's profile page for statistics.

@dogu - 2025-04-23
EDIT: 'Think I am figuring this web scraping thing out.
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

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

def navigate_to_soundcloud_profile(query: str, artist_name: str) -> str:
    """
    Reuses browser and page from prior functions to load the profile and scrape track data.
    """
    from playwright.sync_api import sync_playwright
    from bs4 import BeautifulSoup

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        page = browser.new_page()

        html = load_soundcloud_search_results(query, page)
        results = parse_soundcloud_srp(html, artist_name)

        clean_artist = artist_name.strip().lower()
        artist_profile_url = None

        for result in results:
            display = result["display_name"].strip().lower()
            if display == clean_artist:
                artist_profile_url = result["profile_url"]
                break

        if not artist_profile_url:
            print("❌ No exact match found.")
            browser.close()
            return None

        tracks_url = f"{artist_profile_url}/tracks"
        page.goto(tracks_url, timeout=60000)
        track_count = auto_scroll_tracks(page)

        if track_count == 0:
            print("⚠️ No tracks found—check item_selector or page load.")
        else:
            print(f"✅ {track_count} tracks loaded, proceeding to scrape stats.")

        # not all track card has had its stats injected, we have to wait
        bodies = page.query_selector_all("div.sound__body")
        for i, body in enumerate(bodies, start=1):
            body.scroll_into_view_if_needed()
            # waiting for *its* stats UL to appear (or time out)
            try:
                page.wait_for_selector(
                    f"div.sound__body:nth-of-type({i}) ul.soundStats.sc-ministats-group",
                    timeout=5000
                )
            except:
                print(f"⚠️ stats for track #{i} didn’t appear in time")

        html = page.content()
        #print(html)
        soup = BeautifulSoup(html, "html.parser")

        import re
        from playwright.sync_api import TimeoutError

        # #vibecoding this part ;)
        # 1️⃣ Grab each track card
        bodies = page.query_selector_all("div.sound__body")
        print(f"👀 Found {len(bodies)} track wrappers")

        total_plays = 0
        total_comments = 0

        # 2️⃣ For each card, scroll into view and wait for its stats UL
        for idx, body in enumerate(bodies, start=1):
            body.scroll_into_view_if_needed()

            title_handle = body.query_selector("a.sc-link-primary.soundTitle__title span")
            track_title = title_handle.inner_text().strip() if title_handle else f"(track #{idx})"
            print(f"🔍 Scraping stats for track #{idx}: “{track_title}”")

            try:
                stats_ul = body.wait_for_selector(
                    "ul.soundStats.sc-ministats-group",
                    timeout=8000
                )
            except TimeoutError:
                print(f"⚠️ stats for track #{idx} never appeared, skipping")
                continue

            # extract play count
            play_li = stats_ul.query_selector("li[title*='play']")
            if play_li:
                raw = play_li.get_attribute("title")           # e.g. "2,082 plays"
                m = re.search(r"([\d,]+)", raw)                 # capture all digits & commas
                if m:
                    plays = int(m.group(1).replace(",", ""))   # "2,082" → 2082
                    total_plays += plays
                    print(f"▶️ Track #{idx} plays: {plays}")

            # extract comment count
            comment_li = stats_ul.query_selector("li[title*='comment']")
            if comment_li:
                raw = comment_li.get_attribute("title")         # e.g. "1 comment"
                m = re.search(r"(\d+)", raw)
                if m:
                    comments = int(m.group(1))
                    total_comments += comments
                    print(f"💬 Track #{idx} comments: {comments}")

        browser.close()
        return {
            "profile_url": artist_profile_url,
            "tracks_url": tracks_url,
            "total_plays": total_plays,
            "total_comments": total_comments
        }

    
# ------ TESTING ------ 
if __name__ == "__main__":
    test_query = "insyt."
    artist_name = "insyt."

    result = navigate_to_soundcloud_profile(test_query, artist_name)

    if result:
        print("\n🎉 SUCCESSFUL SCRAPE:")
        print(f"🌐 Profile URL: {result['profile_url']}")
        print(f"🎵 Tracks URL: {result['tracks_url']}")
        print(f"📊 Total Plays: {result['total_plays']}")
        print(f"💬 Total Comments: {result['total_comments']}")
    else:
        print("\n❌ Failed to retrieve artist profile and track stats.")