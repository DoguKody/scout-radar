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

from datetime import date, timedelta
def get_artist_insights(artist_id: str, access_token: str = None) -> list:
    """
    Fetches all albums for the given artist from Chartmetric, then for each album:
      1. Retrieves its tracks via /album/{album_id}/tracks
      2. Extracts each track’s `cm_statistics` (or `statistics`) dict
      3. Sums all numeric metrics across all tracks into a single aggregate
    IMPORTANT: metrics are all time aggregates! so to get weekly changes we will need to subtract from the last week's metrics!

    Args:
        artist_id: Chartmetric artist ID to fetch.
        access_token: (Optional) pre-fetched Bearer token. If None, uses init_credentials().

    Returns:
        A list of dicts, one per album, each with:
          - 'album_id': the Chartmetric album ID
          - 'cm_statistics': a dict of aggregated numeric metrics across all tracks
    """
    # auth header
    token = access_token or init_credentials()
    headers = {'Authorization': f'Bearer {token}'}

    # fetch artist's albums
    resp = requests.get(f"{base_url}/artist/{artist_id}/albums", headers=headers)
    resp.raise_for_status()
    data = resp.json()

    # unwrap album list
    if isinstance(data.get('obj'), list):
        albums = data['obj']
    elif isinstance(data.get('obj'), dict) and 'items' in data['obj']:
        albums = data['obj']['items']
    else:
        albums = data.get('items', []) or []

    albums_stats = []
    for alb in albums:
        cm_album_id = alb.get('cm_album') or alb.get('id')

        # fetch the album's tracks
        tr_resp = requests.get(f"{base_url}/album/{cm_album_id}/tracks", headers=headers)
        tr_resp.raise_for_status()
        raw_tr = tr_resp.json()

        # unwrap track list
        if isinstance(raw_tr, list):
            tracks = raw_tr
        else:
            obj = raw_tr.get('obj')
            if isinstance(obj, list):
                tracks = obj
            elif isinstance(obj, dict) and 'tracks' in obj:
                tracks = obj['tracks']
            else:
                tracks = raw_tr.get('tracks') or []

        # aggregate per-track cm_statistics into album totals
        totals = {}
        for t in tracks:
            stats = t.get('cm_statistics') or t.get('statistics') or {}
            for field, value in stats.items():
                if isinstance(value, (int, float)):
                    totals[field] = totals.get(field, 0) + value

        # result
        albums_stats.append({
            'album_id':      cm_album_id,
            'cm_statistics': totals
        })

    return albums_stats

# ---- TESTING ----
if __name__ == '__main__':
    # 1️⃣ Search and grab the first artist ID
    results = search_artist('DVYN', limit=5, type='artists')
    if not results:
        print("No artists found for 'Erin B'")
        exit(1)
    artist = results[0]
    artist_id = artist.get('id')
    print(f"Using artist_id={artist_id} for {artist.get('name')}")

    # 2️⃣ Call get_artist_insights (no date param needed)
    albums_stats = get_artist_insights(artist_id)
    print(f"Fetched cm_statistics for {len(albums_stats)} albums:\n")

    # 3️⃣ Print the full cm_statistics data for each album
    from pprint import pprint
    for alb in albums_stats:
        print(f"Album ID: {alb['album_id']}")
        print("cm_statistics:")
        pprint(alb['cm_statistics'], indent=2, width=100)
        print("\n" + "-"*80 + "\n")
