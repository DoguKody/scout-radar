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
    
def search_artist_channel(youtube, artist_name, max_results=10):
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

channel_id = search_artist_channel(get_youtube_service(), "insyt.")
print(f"📡 Selected channel ID: {channel_id}")



#---------NOTES---------
# Here are some edge cases I am likely to deal with:

# 1. Topic Channel Ranks Higher Than Official Channel
#    - Some artists may not rank in the top 5 results.
#    - Topic channels (e.g., "Superheaven - Topic") may appear first due to distribution metadata.
#    - Heuristic: deprioritize channels with no handle/custom URL and " - Topic" in title.

# 2. Same Artist Name Shared by Multiple Unrelated Channels
#    - E.g., “Herne” could refer to an indie artist, a podcast, or a cultural group.
#    - Heuristic: use keyword search like "Herne official music video" and cross-check video uploaders.

# 3. Official Channel Has Low Engagement or No Custom URL
#    - Emerging or underground artists may have few subscribers or no branding setup.
#    - Heuristic: prioritize channels that upload official content (albums, music videos), not just promo clips.

# 4. Label or Collective Channel Hosts the Artist ('I assume this is unlikely for upcoming artist but we will see.')
#    - Some artists primarily post under their label's or group's YouTube (e.g., Stones Throw, Boiler Room).
#    - Heuristic: check if multiple known artists are posted under one channel, then tag accordingly.

# 5. Multiple Active Channels for One Artist ('Super edge case that might fall out of scope for now, but definitely a consideration.')
#    - Some artists split content: “Artist Official” for music, “Artist Vlogs” for behind-the-scenes.
#    - Heuristic: build logic to flag duplicates and compare activity stats (uploads, recency, views).
