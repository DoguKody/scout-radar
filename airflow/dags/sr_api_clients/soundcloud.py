"""
SoundCloud client for ScoutRadar.
Uses public sandbox access for /charts discovery.

@dogu - 2025-04-20
EDIT: Churned, 'what t$ is going on with API access in the music tech space?!'
"""

import os, time, requests
from typing import Dict, Any, List

# ---- SoundCloud sandbox access (public credentials) ----
BASE_URL = "https://api-v2.soundcloud.com"
CLIENT_ID = os.getenv("SOUNDCLOUD_CLIENT_ID", "2t9loNQH90kzJcsFCODdigxfp325aq4z")  # fallback public

def _get(endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Low-level GET with retry and CLIENT_ID injection."""
    params = params or {}
    params["client_id"] = CLIENT_ID
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    r = requests.get(url, params=params, timeout=10)
    if r.status_code == 429:
        time.sleep(2)
        return _get(endpoint, params)
    r.raise_for_status()
    return r.json()

def discover_artists_from_charts(genre: str = "soundcloud:genres:hiphop", kind: str = "trending", limit: int = 20) -> List[Dict[str, Any]]:
    """
    Returns artist payloads from the SoundCloud charts.
    genre: genre tag (e.g., soundcloud:genres:hiphop, ...:electronic)
    kind: 'top', 'trending'
    """
    data = _get("charts", {"genre": genre, "kind": kind, "limit": limit})
    artists = []
    seen = set()
    for item in data.get("collection", []):
        user = item.get("track", {}).get("user")
        if user and user["id"] not in seen:
            user["snapshot_ts"] = int(time.time())
            artists.append(user)
            seen.add(user["id"])
    return artists