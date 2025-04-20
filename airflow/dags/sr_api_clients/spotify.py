"""
Spotify client for ScoutRadar.
Will fetch artists from a few breakout playlists.

@dogu - 2025-04-19
EDIT: Purged due to API access limitations.
"""

import os, time, requests
from typing import Dict, Any, List

# work both locally and on GC-Composer
try:
    from airflow.models import Variable           # composer
    _get_var = lambda k: Variable.get(k)
except Exception:
    _get_var = lambda k: os.getenv(k)             # local env‑vars

AUTH_URL  = "https://accounts.spotify.com/api/token"
BASE_URL  = "https://api.spotify.com/v1"

PLAYLISTS = [
    "37i9dQZF1DXaYrZ0yhCs6T",  # Fresh Finds
    "37i9dQZF1DWY6vTWIdZ54A",  # Canada Rising
    "37i9dQZF1DX4Wsb4d7NKfP",  # Fresh Finds Hip-Hop
]

# ---------- auth ----------
def _access_token() -> str:
    cid, secret = _get_var("SPOTIFY_CLIENT_ID"), _get_var("SPOTIFY_CLIENT_SECRET")
    r = requests.post(
        AUTH_URL,
        data={"grant_type": "client_credentials"},
        auth=(cid, secret),
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]

# ---------- helper ----------
def _get(endpoint: str, params: Dict[str, Any] = None, token: str = None):
    headers = {"Authorization": f"Bearer {token or _access_token()}"}
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    r = requests.get(url, headers=headers, params=params, timeout=10)
    if r.status_code == 429:
        time.sleep(int(r.headers.get("Retry-After", "1")))
        return _get(endpoint, params, token)  # retry
    r.raise_for_status()
    return r.json()

# ---------- public function ----------
def discover_artists(limit_per_playlist: int = 100) -> List[Dict[str, Any]]:
    """
    Return raw artist JSON objects, each tagged with snapshot_ts.
    """
    token = _access_token()
    artist_ids, artists = set(), []

    # collecting unique artist IDs from the playlists
    for pl in PLAYLISTS:
        response = _get(f"playlists/{pl}/tracks", {"limit": limit_per_playlist}, token)
        for item in response["items"]:
            artist_ids.update(a["id"] for a in item["track"]["artists"])

    # pulling full artist objects from the API
    for aid in artist_ids:
        art = _get(f"artists/{aid}", token=token)
        art["snapshot_ts"] = int(time.time())
        artists.append(art)

    return artists