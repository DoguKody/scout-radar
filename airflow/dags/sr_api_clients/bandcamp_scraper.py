"""
Scrapes Bandcamp using Playwright.
Extracts artist usernames.

@dogu - 2025-04-20
"""

import asyncio
from playwright.async_api import async_playwright
import json

async def scrape_bandcamp_albums():
    """
    Scrapes Bandcamp Discover page and returns only album tiles (filtering out merch, tracks, sample packs, etc.).
    """

    album_data = []

    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Bandcamp Discover page
        print("Navigating to Bandcamp Discover page...")
        await page.goto("https://bandcamp.com/discover", timeout=60000)

        await page.wait_for_timeout(5000)  # Let Vue hydrate fully
        dump = await page.evaluate("""() => {
            return {
            keys: Object.keys(window),
            state: window.__BC_DISCOVER_STATE__ || null,
            }
        }""")
        print("🧠 Injected keys:", dump["keys"])
        print("📦 Discover state (truncated):", json.dumps(dump["state"], indent=2)[:1000])
        print("🚨 No state object found. Dumping keys for inspection:")
        for key in dump["keys"]:
            if "state" in key.lower():
                print("-", key)

        await page.wait_for_timeout(5000)  # Let JS load, no selector wait
        html = await page.content()
        #print("🖥️ FULL HTML snapshot:\n", html[:2000])

        # waitinjg for all tiles to load
        print("Waiting for result-image anchors to load...")
        await page.wait_for_selector('a.result-image', timeout=60000)

        # tile anchors
        tiles = await page.query_selector_all('a.result-image')
        print(f"Found {len(tiles)} tiles.")

        for tile in tiles:
            html = await tile.inner_html()
            print("Tile HTML:\n", html[:500])
            href = await tile.get_attribute('href')
            if href and "/album/" in href:
                img = await tile.query_selector('img')
                title = await img.get_attribute('alt') if img else "Unknown Title"

                # inferring artist from the Bandcamp subdomain
                try:
                    artist = href.split("https://")[1].split(".bandcamp")[0]
                except Exception:
                    artist = "Unknown Artist"

                album_data.append({
                    "title": title,
                    "artist": artist,
                    "url": href
                })

        await browser.close()

    return album_data

if __name__ == "__main__":
    scraped = asyncio.run(scrape_bandcamp_albums())
    for item in scraped:
        print(item)
