"""
Scrapes SoundCloud Top Charts using Playwright.
Extracts top artist usernames and track URLs from the public web interface.

@dogu - 2025-04-20
EDIT: Churned, 'i just can't win but ill figure it out.'
"""

import time
from typing import List, Dict
from playwright.sync_api import sync_playwright

def scrape_top_chart_playwright(genre: str = "all-music", region: str = "all-countries", limit: int = 20) -> List[Dict[str, str]]:
    url = f"https://soundcloud.com/charts/top?genre={genre}&region={region}"
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url, timeout=60000)

        # waiting for initial content to load
        page.wait_for_selector("div.chartTracks", timeout=15000)

        # scrolling to bottom to trigger lazy loading
        page.mouse.wheel(0, 2000)
        time.sleep(2)

        # debugging effort 'lol'
        page.screenshot(path="soundcloud_chart_debug.png", full_page=True)

        cards = page.query_selector_all("li.chartTracks__item")

        for card in cards[:limit]:
            user_tag = card.query_selector("a.chartTrack__username")
            track_tag = card.query_selector("a.chartTrack__title")

            if user_tag and track_tag:
                artist = user_tag.inner_text().strip().lstrip("@")
                href = track_tag.get_attribute("href")
                results.append({
                    "artist": artist,
                    "track_url": f"https://soundcloud.com{href}",
                    "snapshot_ts": int(time.time()),
                })

        browser.close()
    return results


# -------main-------
if __name__ == "__main__":
    data = scrape_top_chart_playwright()
    print(f"Found {len(data)} artists.")
    for artist in data[:3]:
        print(artist)