import os
import requests
from dotenv import load_dotenv

load_dotenv()

# endpoint to exchange a refresh token for an access token
auth_url = 'https://api.chartmetric.com/api/token'

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


if __name__ == '__main__':
    try:
        print('Testing init_credentials()...')
        access_token = init_credentials()
        print('Access token successfully obtained:', access_token)
    except Exception as e:
        print('Error during test:', str(e))
