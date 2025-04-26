import os
import requests
from dotenv import load_dotenv

load_dotenv()

# endpoints 
auth_url = 'https://api.chartmetric.com/api/token'
search_url = 'https://api.chartmetric.com/api/search'
base_url = 'https://api.chartmetric.com/api'
filter_url = f"{base_url}/artist/list/filter"
# Artist-specific Spotify daily chart endpoint template
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


def get_artist_insights(
    artist_id: int,
    start_date: str,
    end_date: str
) -> dict:
    """
    Pull Instagram stats, album cm_statistics, and artist-specific Spotify daily chart data.

    Args:
        artist_id: Chartmetric artist ID.
        start_date: YYYY-MM-DD (since parameter for daily charts).
        end_date: YYYY-MM-DD (until parameter for daily charts).

    Returns:
        dict with keys 'instagram', 'albums', 'spotify_charts'.
    """
    token = init_credentials()
    headers = {'Authorization': f'Bearer {token}'}

    # 1. Instagram audience stats
    ig_resp = requests.get(
        f"{base_url}/artist/{artist_id}/instagram-audience-stats",
        headers=headers
    )
    ig_resp.raise_for_status()
    instagram = ig_resp.json()

    # 2. Album-level cm_statistics
    alb_resp = requests.get(
        f"{base_url}/artist/{artist_id}/albums",
        headers=headers
    )
    alb_resp.raise_for_status()
    raw_alb = alb_resp.json()
    if isinstance(raw_alb.get('obj'), list):
        albums = raw_alb['obj']
    elif isinstance(raw_alb.get('obj'), dict) and 'items' in raw_alb['obj']:
        albums = raw_alb['obj']['items']
    elif 'items' in raw_alb:
        albums = raw_alb['items']
    else:
        albums = raw_alb.get('data', {}).get('items', []) or []

    albums_stats = []
    for alb in albums:
        album_id = alb.get('cm_album') or alb.get('id')
        tr_resp = requests.get(
            f"{base_url}/album/{album_id}/tracks",
            headers=headers
        )
        tr_resp.raise_for_status()
        tr_data = tr_resp.json()
        albums_stats.append({
            'album_id': album_id,
            'cm_statistics': tr_data.get('cm_statistics', {})
        })

    # 3. Artist-specific Spotify daily chart data
    charts_url = artist_charts_url_template.format(artist_id=artist_id)
    charts_params = {'since': start_date, 'until': end_date}
    ch_resp = requests.get(
        charts_url,
        headers=headers,
        params=charts_params
    )
    ch_resp.raise_for_status()
    spotify_charts = ch_resp.json()

    return {
        'instagram': instagram,
        'albums': albums_stats,
        'spotify_charts': spotify_charts
    }


if __name__ == '__main__':
    try:
        # Test search
        print('Testing search_artist()...')
        artists = search_artist('anderson .paak', limit=10, type='artists')
        if not artists:
            print('No artists found.')
        else:
            for art in artists:
                print(f"{art.get('id')} - {art.get('name')} (score: {art.get('cm_artist_score') or art.get('score')})")

            # Test get_artist_insights
            artist_id = artists[0].get('id')
            print(f"\nTesting get_artist_insights() for artist ID {artist_id}...\n")
            insights = get_artist_insights(artist_id, '2025-01-01', '2025-04-25')
            print('Instagram stats:', insights['instagram'])
            print('Albums stats count:', insights['albums'])
            print('Spotify daily chart data:', insights['spotify_charts'])
    except Exception as e:
        print('Error during test:', e)

