"""
YouTube client for ScoutRadar.
@dogu - 2025-04-21
"""

import os
from googleapiclient.discovery import build
from dotenv import load_dotenv

def get_youtube_service():
    try:
        load_dotenv()
        YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
        if not YOUTUBE_API_KEY:
            raise ValueError("❌ Missing YOUTUBE_API_KEY environment variable.")
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        return youtube
    except Exception as e:
        print(f"❌ Failed to initialize YouTube API client: {e}")
        return None
    
def search_artist_channel(youtube, artist_name, max_results=5):
    try:
        print(f"🔎 Searching for channel: {artist_name}")
        response = youtube.search().list(
            q=artist_name,
            type="channel",
            part="snippet",
            maxResults=max_results
        ).execute()

        items = response.get("items", [])
        if not items:
            print("⚠️ No channels found for this artist.")
            return None

        # candidate results
        for idx, item in enumerate(items):
            channel_title = item['snippet']['title']
            channel_id = item['snippet']['channelId']
            print(f"{idx + 1}. {channel_title} → {channel_id}")

        # defaulting to the first result, might have to change this later to store all links
        return items[0]['snippet']['channelId']
    except Exception as e:
        print(f"❌ Error while searching for channel: {e}")
        return None

channel_id = search_artist_channel(get_youtube_service(), "quickly, quickly")
print(f"📡 Selected channel ID: {channel_id}")