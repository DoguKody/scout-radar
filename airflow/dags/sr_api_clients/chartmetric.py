import os
import requests
from dotenv import load_dotenv

load_dotenv()

# endpoints 
auth_url = 'https://api.chartmetric.com/api/token'
search_url = 'https://api.chartmetric.com/api/search'
base_url = 'https://api.chartmetric.com/api'
filter_url = f"{base_url}/artist/list/filter"
# artist-specific Spotify daily chart endpoint template
artist_charts_url_template = f"{base_url}/artist/{{artist_id}}/spotify_top_daily/charts"


def init_credentials(refresh_token: str = None) -> str:
    """
    Exchange a Chartmetric refresh token for an access token (returned as 'token').
    """
    token = refresh_token or os.getenv('CHARTMETRIC_REFRESH_TOKEN')
    if not token:
        raise ValueError(
            'A Chartmetric refresh token must be provided either as an argument '
            'or via CHARTMETRIC_REFRESH_TOKEN in your .env file'
        )
    resp = requests.post(
        auth_url,
        json={'refreshtoken': token},
        headers={'Content-Type': 'application/json'}
    )
    resp.raise_for_status()
    raw = resp.json()
    if 'token' in raw:
        return raw['token']
    raise ValueError(f"Access token not found in auth response. Response content: {raw}")

from datetime import date, timedelta

def search_artist(
    query: str,
    limit: int = 5,
    offset: int = 0,
    access_token: str = None,
    type: str = 'artists'
) -> list:
    """
    Search for artists on Chartmetric by name.
    """
    token = access_token or init_credentials()
    headers = {'Authorization': f'Bearer {token}'}
    params = {'q': query, 'limit': limit, 'offset': offset, 'type': type}
    resp = requests.get(search_url, headers=headers, params=params)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data.get('obj'), dict) and 'artists' in data['obj']:
        return data['obj']['artists']
    if 'items' in data:
        return data['items'] or []
    nested = data.get('data', {})
    return nested.get('items', []) or []


def get_artist_insights(artist_id: str, date: str, country_code: str = 'US',
                        interval: str = 'daily', chart_type: str = 'regional') -> dict:
    token = init_credentials()
    headers = {'Authorization': f'Bearer {token}'}

    # ------ hitting the ALBUMS endpoint ------
    url = f"{base_url}/artist/{artist_id}/albums"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    # the album list from whichever wrapper Chartmetric used
    if isinstance(data.get('obj'), list):
        albums = data['obj']
    elif isinstance(data.get('obj'), dict) and 'items' in data['obj']:
        albums = data['obj']['items']
    elif 'items' in data:
        albums = data['items']
    else:
        albums = []

    # ------ getting the `cm_statistics` ------
    albums_stats = []
    for alb in albums:
        # Chartmetric album ID
        cm_album_id = alb.get('cm_album') or alb.get('id')

        # fetching the tracks for that album
        tr_url = f"{base_url}/album/{cm_album_id}/tracks"
        tr_resp = requests.get(tr_url, headers=headers)
        tr_resp.raise_for_status()
        raw_tr = tr_resp.json()

        # unwrapping the tracks array (it may live under `obj.tracks`, `tracks`, or even be the top‐level list)
        if isinstance(raw_tr, list):
            tracks_list = raw_tr
        else:
            obj = raw_tr.get('obj')

            if isinstance(obj, list):
                # obj _is_ already the list of tracks
                tracks_list = obj
            elif isinstance(obj, dict):
                # obj is a dict: look for its "tracks" key first
                tracks_list = obj.get('tracks') or raw_tr.get('tracks') or []
            else:
                # nothing under obj, fall back to top-level "tracks"
                tracks_list = raw_tr.get('tracks') or []

        # extracing each track’s cm_statistics (or `statistics`) field
        cm_stats = [
            t.get('cm_statistics') or t.get('statistics') or {}
            for t in tracks_list
        ]

        # output list
        albums_stats.append({
            'album_id':      cm_album_id,
            'cm_statistics': cm_stats
        })

    return albums_stats

# ---- TESTING ----
if __name__ == '__main__':
    # 1️⃣ Search and grab the first artist ID
    results = search_artist('anderson .paak', limit=5, type='artists')
    if not results:
        print("No artists found for 'Erin B'")
        exit(1)
    artist = results[0]
    artist_id = artist.get('id')
    print(f"Using artist_id={artist_id} for {artist.get('name')}")

    # 2️⃣ Call get_artist_insights with today’s date
    from datetime import date as _d
    today = _d.today().isoformat()  # e.g. '2025-04-26'

    albums_stats = get_artist_insights(artist_id, today)
    print(f"Fetched cm_statistics for {len(albums_stats)} albums:\n")

    # 3️⃣ Print the full cm_statistics data for each album
    from pprint import pprint
    for alb in albums_stats:
        print(f"Album ID: {alb['album_id']}")
        print("cm_statistics:")
        pprint(alb['cm_statistics'], indent=2, width=100)
        print("\n" + "-"*80 + "\n")