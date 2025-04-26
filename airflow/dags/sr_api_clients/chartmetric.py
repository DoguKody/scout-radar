import os
import requests
from dotenv import load_dotenv

load_dotenv()

# endpoints 
auth_url = 'https://api.chartmetric.com/api/token'
search_url = 'https://api.chartmetric.com/api/search'
filter_url = 'https://api.chartmetric.com/api/artist/list/filter'

def init_credentials(refresh_token: str = None) -> str:
    """
    Exchange a Chartmetric refresh token for an access token (returned as 'token').

    Args:
        refresh_token: Chartmetric refresh token string. If None, reads from
                       environment variable CHARTMETRIC_REFRESH_TOKEN (loaded via .env).

    Returns:
        access_token: Short-lived access token for API calls.

    Raises:
        ValueError: If no refresh token is provided or 'token' not found in response.
        HTTPError: If the HTTP request to the auth endpoint fails.
    """
    # fallback to .env var
    token = refresh_token or os.getenv('CHARTMETRIC_REFRESH_TOKEN')
    if not token:
        raise ValueError(
            'A Chartmetric refresh token must be provided either as an argument '
            'or via CHARTMETRIC_REFRESH_TOKEN in your .env file'
        )

    response = requests.post(
        auth_url,
        json={'refreshtoken': token},
        headers={'Content-Type': 'application/json'}
    )
    response.raise_for_status()

    raw = response.json()
    if 'token' in raw:
        return raw['token']
    else:
        raise ValueError(
            f"Access token not found in auth response. Response content: {raw}"
        )

def search_artist(
    query: str,
    limit: int = 5,
    offset: int = 0,
    access_token: str = None,
    type: str = 'artists'
) -> list:
    """
    Search for artists on Chartmetric by name.

    Args:
        query: Free-form search string (e.g. 'Ariana Grande').
        limit: Max number of results to return.
        offset: Pagination offset.
        access_token: Bearer token. If None, retrieves a new one via init_credentials().
        type: Resource type to search ('all', 'artists', 'tracks', etc.).

    Returns:
        List of artist dicts parsed from the response.
    """
    token = access_token or init_credentials()
    headers = {
        'Authorization': f'Bearer {token}'
    }
    params = {
        'q': query,
        'limit': limit,
        'offset': offset,
        'type': type
    }

    # Perform a simple GET with query params
    response = requests.get(
        search_url,
        headers=headers,
        params=params
    )
    response.raise_for_status()
    data = response.json()

    # Chartmetric search wraps results under 'obj':{'artists':[...]}
    if isinstance(data.get('obj'), dict) and 'artists' in data['obj']:
        return data['obj']['artists']

    # Fallback to top-level 'items'
    if 'items' in data:
        return data['items'] or []

    # Fallback to nested data wrapper
    nested = data.get('data', {})
    return nested.get('items', []) or []


if __name__ == '__main__':
    try:
        # Test search
        print('Testing search_artist()...')
        artists = search_artist('Erin B', limit=10, type='artists')
        if not artists:
            print('No artists found.')
        for art in artists:
            print(f"{art.get('id')} - {art.get('name')} (score: {art.get('cm_artist_score') or art.get('score')})")

    except Exception as e:
        print('Error during test:', e)
