"""
Scrapes SoundCloud Top Charts (non-auth).
Extracts top artist usernames and track URLs from the public web interface.

@dogu - 2025-04-20
"""

import time
import requests
from bs4 import BeautifulSoup
from typing import List, Dict

BASE_URL = "https://soundcloud.com/charts/top"
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def scrape_top_chart(genre: str = "all-music", region: str = "all-countries", limit: int = 20) -> List[Dict[str, str]]:
    """
    Scrapes top chart for given genre/region (HTML version).
    Returns a list of dicts with artist username and track URL.
    """
    url = f"{BASE_URL}?genre={genre}&region={region}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()

    # trying to debug
    with open("soundcloud_debug.html", "w") as f:
        f.write(r.text)

    soup = BeautifulSoup(r.text, "html.parser")
    artist_cards = soup.select("li.chartTracks__item")

    results = []
    for card in artist_cards[:limit]:
        user_tag = card.select_one("a.chartTrack__username")
        track_tag = card.select_one("a.chartTrack__title")

        if user_tag and track_tag:
            results.append({
                "artist": user_tag.text.strip().lstrip("@"),
                "track_url": "https://soundcloud.com" + track_tag["href"],
                "snapshot_ts": int(time.time()),
            })
    return results

# -------main-------
if __name__ == "__main__":
    results = scrape_top_chart()
    print(f"Found {len(results)} artists.")
    for artist in results[:3]:  # Show first 3
        print(artist)
