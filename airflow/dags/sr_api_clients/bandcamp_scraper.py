"""
Scrapes Bandcamp using Playwright.
Extracts artist usernames.

@dogu - 2025-04-20
"""

from playwright.async_api import async_playwright
import asyncio

async def scrape_bandcamp_albums():
    album_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        await page.goto("https://bandcamp.com/discover", timeout=60000)

        # scrolling for lazy loading
        for _ in range(5):
            await page.mouse.wheel(0, 2000)
            await asyncio.sleep(1.5)

        # tiles appearing...?
        await page.wait_for_selector("a.result-image", timeout=15000)
        tiles = await page.query_selector_all("a.result-image")

        print(f"🔍 Total result-image anchors: {len(tiles)}")

        for tile in tiles:
            href = await tile.get_attribute("href")
            if not href or "/album/" not in href:
                continue

            img = await tile.query_selector("img")
            title = await img.get_attribute("alt") if img else "Unknown Title"

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

# Run the function
if __name__ == "__main__":
    albums = asyncio.run(scrape_bandcamp_albums())
    for a in albums:
        print(a)
