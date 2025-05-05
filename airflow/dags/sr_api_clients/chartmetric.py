import os
import requests
from dotenv import load_dotenv

load_dotenv()

# endpoints 
auth_url = 'https://api.chartmetric.com/api/token'
search_url = 'https://api.chartmetric.com/api/search'
base_url = 'https://api.chartmetric.com/api'
filter_url = f"{base_url}/artist/list/filter"

def init_credentials(refresh_token: str = None) -> str:
    """
    Exchange a Chartmetric refresh token for an access token (returned as 'token').

    Raises:
        ValueError: if no refresh token is available or response is invalid.
        requests.exceptions.RequestException: if the API request fails.
    """
    token = refresh_token or os.getenv('CHARTMETRIC_REFRESH_TOKEN')
    if not token:
        raise ValueError(
            'Missing Chartmetric refresh token. Set it via argument or CHARTMETRIC_REFRESH_TOKEN in .env'
        )
    
    try:
        resp = requests.post(
            auth_url,
            json={'refreshtoken': token},
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Chartmetric auth request failed: {e}")

    try:
        raw = resp.json()
    except ValueError:
        raise ValueError(f"Invalid JSON response from Chartmetric auth endpoint: {resp.text}")

    if 'token' in raw:
        return raw['token']

    raise ValueError(f"Access token not found in response: {raw}")

from airflow.utils.log.logging_mixin import LoggingMixin
logger = LoggingMixin().log

def search_artist(
    query: str,
    limit: int = 10,  # pull more to catch duplicates
    offset: int = 0,
    access_token: str = None,
    type: str = 'artists'
) -> list:
    """
    Chartmetric search limited to *exact name* matches.

    Returns:
        List of exact-match artist dicts. Logs if multiple.
    """
    if type != 'artists':
        raise ValueError(f"Unsupported search type: {type}")

    token = access_token or init_credentials()
    headers = {'Authorization': f'Bearer {token}'}
    params = {'q': query, 'limit': limit, 'offset': offset, 'type': type}

    try:
        resp = requests.get(search_url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except (requests.exceptions.RequestException, ValueError) as e:
        logger.warning(f"[Chartmetric Search] Failed query '{query}': {e}")
        return []

    candidates = (
        data.get('obj', {}).get('artists') or
        data.get('items') or
        data.get('data', {}).get('items') or []
    )

    exact_matches = [a for a in candidates if a.get('name') == query]

    if not exact_matches:
        logger.warning(f"[No Exact Match] No Chartmetric artist found with exact name '{query}'")
    elif len(exact_matches) > 1:
        logger.warning(
            f"[Duplicate Name] {len(exact_matches)} artists found with exact name '{query}'. "
            f"Consider disambiguation upstream (e.g., country, genre, image)."
        )

    return exact_matches


from datetime import date, timedelta
def get_artist_insights(artist_id: str, access_token: str = None) -> list:
    """
    Fetches all albums for the given artist from Chartmetric, then for each album:
      1. Retrieves its tracks via /album/{album_id}/tracks
      2. Extracts each track’s `cm_statistics` (or `statistics`) dict
      3. Sums all numeric metrics across all tracks into a single aggregate

    Args:
        artist_id: Chartmetric artist ID to fetch.
        access_token: (Optional) pre-fetched Bearer token. If None, uses init_credentials().

    Returns:
        A list of dicts, one per album, each with:
          - 'album_id': the Chartmetric album ID
          - 'album_name': name
          - 'album_image_url': image URL
          - 'cm_statistics': aggregated numeric metrics
    """
    token = access_token or init_credentials()
    headers = {'Authorization': f'Bearer {token}'}

    # --- fetch artist's albums ---
    try:
        resp = requests.get(f"{base_url}/artist/{artist_id}/albums",
                            headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"[Album Fetch Failed] Artist={artist_id} → {e}")
        return []

    # unwrap album list
    if isinstance(data.get('obj'), list):
        albums = data['obj']
    elif isinstance(data.get('obj'), dict) and 'items' in data['obj']:
        albums = data['obj']['items']
    else:
        albums = data.get('items') or []

    if not albums:
        logger.warning(f"[No Albums] Artist={artist_id}")
        return []

    albums_stats = []

    for alb in albums:
        cm_album_id     = alb.get('cm_album') or alb.get('id')
        album_name      = alb.get('name')
        album_image_url = alb.get('image_url')

        if not cm_album_id:
            logger.warning(f"[Skipping Album] Missing ID for album: {album_name}")
            continue

        # --- fetch album's tracks ---
        try:
            tr_resp = requests.get(f"{base_url}/album/{cm_album_id}/tracks",
                                   headers=headers, timeout=15)
            tr_resp.raise_for_status()
            raw_tr = tr_resp.json()
        except Exception as e:
            logger.warning(f"[Track Fetch Failed] Album={cm_album_id} ({album_name}) → {e}")
            continue

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

        if not tracks:
            logger.warning(f"[No Tracks] Album={cm_album_id} ({album_name})")
            continue

        # --- aggregate per-track stats ---
        totals = {}
        for t in tracks:
            stats = t.get('cm_statistics') or t.get('statistics') or {}
            if not isinstance(stats, dict):
                logger.warning(f"[Bad Stats] Skipping non-dict stats in track {t.get('id')}")
                continue

            for field, value in stats.items():
                if isinstance(value, (int, float)):
                    totals[field] = totals.get(field, 0) + value

        albums_stats.append({
            'album_id':        cm_album_id,
            'album_name':      album_name,
            'album_image_url': album_image_url,
            'cm_statistics':   totals
        })

    if not albums_stats:
        logger.warning(f"[No Album Stats] Artist={artist_id}")

    return albums_stats

def get_instagram_stats(
    artist_id: str,
    date: str = None,
    geo_only: bool = False,
    access_token: str = None
) -> dict:
    """
    Fetches Instagram audience stats for a given artist on a specific date.

    Args:
        artist_id:    Chartmetric artist ID (e.g. '236')
        date:         ISO date string filter (YYYY-MM-DD). If None, uses most recent.
        geo_only:     If True, limits to geo data only (default False)
        access_token: Optional pre-fetched Bearer token; otherwise uses init_credentials()

    Returns:
        Filtered dict containing only the keys of interest, or empty dict on failure.
    """
    token = access_token or init_credentials()
    headers = {'Authorization': f'Bearer {token}'}

    params = {'geoOnly': str(geo_only).lower()}
    if date:
        params['date'] = date

    # --- fetch instagram stats ---
    try:
        resp = requests.get(
            f"{base_url}/artist/{artist_id}/instagram-audience-stats",
            headers=headers,
            params=params,
            timeout=10
        )
        resp.raise_for_status()
        body = resp.json()
    except requests.exceptions.RequestException as e:
        logger.warning(f"[Instagram Fetch Failed] Artist={artist_id} Date={date} → {e}")
        return None
    except ValueError:
        logger.warning(f"[Instagram Fetch] Invalid JSON response for Artist={artist_id}")
        return None

    raw = body.get('obj', {})
    if not isinstance(raw, dict):
        logger.warning(f"[Instagram Fetch] Unexpected data type: {type(raw)} for Artist={artist_id}")
        return {}

    # keys we want, with defaults
    keys_to_keep = {
        "followers":              None,
        "avg_likes_per_post":     None,
        "avg_commments_per_post": None,
        "engagement_rate":        None,
        "top_countries":          [],  # list of dicts
        "top_cities":             [],
        "likers_top_countries":   [],
        "likers_top_cities":      [],
        "timestp":                None
    }

    filtered = {}
    for key, default in keys_to_keep.items():
        filtered[key] = raw.get(key, default)

    if not filtered:
        logger.warning(f"[Instagram Parse] No stats extracted for Artist={artist_id} Date={date}")

    return filtered


# ---- TESTING ----
if __name__ == '__main__':
    # grab the first artist ID
    query = 'Daiela'
    results = search_artist(query, limit=5, type='artists')
    if not results:
        print(f"No artists found for {query}")
        exit(1)
    print(results)
    artist = results[0]
    artist_id = artist.get('id')
    print(f"Using artist_id={artist_id} for {artist.get('name')}")

    # get_artist_insights (no date param needed)
    albums_stats = get_artist_insights(artist_id)
    print(f"Fetched cm_statistics for {len(albums_stats)} albums:\n")

    # full cm_statistics data for each album
    
    from pprint import pprint
    for alb in albums_stats:
        print(f"Album ID: {alb['album_id']}  Name: {alb.get('album_name')}")
        print("cm_statistics:")
        pprint(alb['cm_statistics'], indent=2, width=100)
        print("\n" + "-"*80 + "\n")

    # instagram data pull for the artist
    test_date = '2025-04-26'  # or any YYYY-MM-DD
    print("Testing get_instagram_stats()...\n")
    ig_stats = get_instagram_stats(artist_id, test_date, geo_only=False)
    print(ig_stats)
    



