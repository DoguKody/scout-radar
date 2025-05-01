"""
YouTube client for ScoutRadar.
@dogu - 2025-04-21
"""

import os
from googleapiclient.discovery import build
from dotenv import load_dotenv
import json
from airflow.utils.log.logging_mixin import LoggingMixin
logger = LoggingMixin().log

def get_youtube_service():
    load_dotenv()  # might drop this in favor of Airflow variables but we will see
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        logger.error("Missing YOUTUBE_API_KEY. Skipping YouTube init.")
        return None

    try:
        client = build("youtube", "v3", developerKey=api_key)
        return client
    except Exception as e:
        logger.error(f"Failed to initialize YouTube client: {e}")
        return None
    
from googleapiclient.errors import HttpError
def search_artist_channel(youtube, artist_name: str, max_results: int = 10) -> dict:
    """
    Searches for YouTube channels matching an artist name using two strategies:
      1. Direct channel search
      2. Video-based search (to catch Topic/secondary channels)

    Returns:
        A dict of channel ID → {
            "title": str,
            "source_count": {
                "channel_search": int,
                "video_search": int
            }
        }
    """
    if youtube is None:
        logger.error(f"[YouTube Client Missing] Cannot search for '{artist_name}'")
        return {}

    results = {}

    # 1) channel name search
    try:
        logger.info(f"[Channel Search] Querying channels for '{artist_name}'")
        resp = (
            youtube.search()
                   .list(q=artist_name, type="channel", part="snippet", maxResults=max_results)
                   .execute()
        )
        for item in resp.get("items", []):
            cid = item["snippet"]["channelId"]
            title = item["snippet"]["title"]
            entry = results.setdefault(
                cid,
                {"title": title, "source_count": {"channel_search": 0, "video_search": 0}}
            )
            entry["source_count"]["channel_search"] += 1

        logger.info(f"[Channel Search] Found {len(results)} unique channel candidates")
    except HttpError as he:
        logger.warning(f"[Channel Search Failed] '{artist_name}': {he}")
    except Exception as e:
        logger.error(f"[Channel Search Error] Unexpected error for '{artist_name}': {e}")

    # 2) video-based search
    try:
        logger.info(f"[Video Search] Querying videos for '{artist_name}'")
        resp = (
            youtube.search()
                   .list(q=artist_name, type="video", part="snippet", maxResults=max_results)
                   .execute()
        )
        for item in resp.get("items", []):
            cid = item["snippet"]["channelId"]
            title = item["snippet"]["channelTitle"]
            entry = results.setdefault(
                cid,
                {"title": title, "source_count": {"channel_search": 0, "video_search": 0}}
            )
            entry["source_count"]["video_search"] += 1

        logger.info(f"[Video Search] Total candidates now {len(results)}")
    except HttpError as he:
        logger.warning(f"[Video Search Failed] '{artist_name}': {he}")
    except Exception as e:
        logger.error(f"[Video Search Error] Unexpected error for '{artist_name}': {e}")

    return results

from typing import Optional
def select_best_channel(results: dict, artist_name: str) -> Optional[str]:
    """
    From a dict of {channel_id: {"title": ..., "source_count": {...}}}, pick the best channel ID.

    Strategy:
      1. Exact title match on `artist_name`
         - If exactly one, return it.
         - If multiple, log a warning and return the one with highest total mentions.
      2. Fallback: pick the channel_id with the highest sum of source_count values.

    Returns:
        Best channel_id, or None if `results` is empty.
    """
    if not results:
        logger.warning(f"[Select Channel] No channel candidates for '{artist_name}'")
        return None

    # 1) exact-title matches
    exact = {
        cid: meta for cid, meta in results.items()
        if meta.get("title") == artist_name
    }
    if exact:
        if len(exact) > 1:
            logger.warning(
                f"[Select Channel] Multiple exact-title matches for '{artist_name}': {list(exact.keys())}"
            )
        # choose the one with highest total source_count
        best = max(
            exact.items(),
            key=lambda kv: sum(kv[1]["source_count"].values())
        )[0]
        logger.info(f"[Select Channel] Exact match selected: {best}")
        return best

    # 2) fallback by total mentions across both searches
    best = max(
        results.items(),
        key=lambda kv: sum(kv[1]["source_count"].values())
    )[0]
    logger.info(
        f"[Select Channel] No exact title match; falling back to highest-mention channel: {best}"
    )
    return best

# helper for `get_channel_details`
def fetch_all_video_ids(youtube, channel_id: str, max_results_per_page: int = 50) -> list:
    """
    Fetches all video IDs uploaded by a given YouTube channel using pagination.

    Args:
        youtube: Authenticated YouTube API client (from get_youtube_service()).
        channel_id: The ID of the YouTube channel.
        max_results_per_page: Number of results per API call (max 50).

    Returns:
        List of all video IDs for the channel (possibly empty on error).
    """
    if youtube is None:
        logger.error(f"[Video IDs] YouTube client missing; cannot fetch videos for channel {channel_id}")
        return []

    video_ids = []
    next_page_token = None
    page_num = 0

    try:
        while True:
            page_num += 1
            resp = (
                youtube.search()
                       .list(
                           channelId=channel_id,
                           part="id",
                           type="video",
                           order="date",
                           maxResults=max_results_per_page,
                           pageToken=next_page_token
                       )
                       .execute()
            )

            items = resp.get("items", [])
            for item in items:
                if item.get("id", {}).get("kind") == "youtube#video":
                    video_ids.append(item["id"]["videoId"])

            logger.info(f"[Video IDs] Page {page_num}: fetched {len(items)} items")

            next_page_token = resp.get("nextPageToken")
            if not next_page_token:
                break

    except HttpError as he:
        logger.warning(f"[Video IDs] Google API error on channel {channel_id}, page {page_num}: {he}")
    except Exception as e:
        logger.error(f"[Video IDs] Unexpected error fetching videos for channel {channel_id}: {e}")

    logger.info(f"[Video IDs] Total IDs collected for channel {channel_id}: {len(video_ids)}")
    return video_ids

# helper for `get_channel_details`
def fetch_video_stats_batch(youtube, video_ids: list) -> dict:
    """
    Fetches statistics (viewCount, likeCount, commentCount) for a batch of YouTube video IDs.

    Args:
        youtube: Authenticated YouTube API client.
        video_ids: List of video IDs to query (max 50 per API call).

    Returns:
        Dict mapping video ID to its statistics dict.
    """
    if youtube is None:
        logger.error("[Video Stats] YouTube client missing; aborting stats fetch")
        return {}

    stats = {}
    # API limit is 50 videos per request
    for start in range(0, len(video_ids), 50):
        chunk = video_ids[start:start + 50]
        try:
            response = (
                youtube.videos()
                       .list(part="statistics", id=",".join(chunk))
                       .execute()
            )
            items = response.get("items", [])
            for item in items:
                vid = item.get("id")
                stats[vid] = item.get("statistics", {})
            logger.info(f"[Video Stats] Fetched stats for {len(items)} videos (chunk starting at {start})")
        except HttpError as he:
            logger.warning(f"[Video Stats] API error on IDs {chunk}: {he}")
        except Exception as e:
            logger.error(f"[Video Stats] Unexpected error on IDs {chunk}: {e}")

    logger.info(f"[Video Stats] Total videos with stats fetched: {len(stats)}")
    return stats

# helper for `get_channel_details`
def summarize_video_stats(stats_dict: dict) -> dict:
    """
    Aggregates total views, likes, and comments from a dictionary of per-video statistics.

    Uses Airflow logging to report any data conversion issues and provides a summary
    of the computed totals.

    Args:
        stats_dict (Dict[str, Dict]): Mapping video IDs to their stats dicts (viewCount, likeCount, commentCount).

    Returns:
        Dict[str, int]: Cumulative totals for 'total_views', 'total_likes', and 'total_comments'.
    """
    total_views = 0
    total_likes = 0
    total_comments = 0

    for vid, stats in stats_dict.items():
        try:
            # Convert metric strings to int, defaulting to 0 if missing
            views = int(stats.get("viewCount", 0))
            likes = int(stats.get("likeCount", 0))
            comments = int(stats.get("commentCount", 0))
        except Exception as e:
            logger.warning(
                f"[Summarize Stats] Skipping video {vid} due to data error: {e}"
            )
            continue

        total_views += views
        total_likes += likes
        total_comments += comments

    logger.info(
        f"[Summarize Stats] Computed totals — views: {total_views}, "
        f"likes: {total_likes}, comments: {total_comments}"
    )

    return {
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments
    }

from typing import Dict, Any
def get_channel_details(youtube, channel_id: str) -> Dict[str, Any]:
    """
    Fetches metadata and aggregate video statistics for a given YouTube channel.

    Args:
        youtube: Authenticated YouTube API client (from get_youtube_service()).
        channel_id: The ID of the YouTube channel.

    Returns:
        A dict containing channel metadata and cumulative video stats, or an "error" key on failure.
    """
    if youtube is None:
        logger.error(f"[Channel Details] YouTube client not initialized for channel {channel_id}")
        return {"error": "YouTube client not initialized"}

    # --- fetch channel metadata ---
    try:
        response = (
            youtube.channels()
                   .list(part="snippet,statistics", id=channel_id)
                   .execute()
        )
    except HttpError as he:
        logger.error(f"[Channel Details] API error fetching channel info for {channel_id}: {he}")
        return {"error": str(he)}
    except Exception as e:
        logger.error(f"[Channel Details] Unexpected error fetching metadata for {channel_id}: {e}")
        return {"error": str(e)}

    items = response.get("items") or []
    if not items:
        logger.warning(f"[Channel Details] No channel found with ID {channel_id}")
        return {"error": "Channel not found"}

    info = items[0]
    snippet = info.get("snippet", {})
    statistics = info.get("statistics", {})

    base_data = {
        "id": snippet.get("channelId", info.get("id")),
        "title": snippet.get("title"),
        "description": snippet.get("description", ""),
        "customUrl": snippet.get("customUrl", ""),
        "publishedAt": snippet.get("publishedAt"),
        "subscriberCount": statistics.get("subscriberCount", "0"),
        "hiddenSubscriberCount": statistics.get("hiddenSubscriberCount", False),
        "contentCount": statistics.get("videoCount", "0")
    }
    logger.info(f"[Channel Details] Fetched metadata for channel {base_data['id']} — {base_data['title']}")

    # --- fetch and summarize video metrics ---
    video_ids = fetch_all_video_ids(youtube, channel_id)
    stats = fetch_video_stats_batch(youtube, video_ids)
    totals = summarize_video_stats(stats)

    # return
    result = {**base_data, **totals}
    logger.info(f"[Channel Details] Compiled metadata and stats for channel {channel_id}")
    return result


# -----------TESTING-----------
if __name__ == "__main__":
    artist_name = "insyt."  
    youtube_key = get_youtube_service()
    results_dict = search_artist_channel(youtube_key, artist_name)
    best_channel = select_best_channel(results_dict, artist_name)
    channel_data = get_channel_details(youtube_key, best_channel)

    print(channel_data)

    '''
    if best_channel:
        meta = results_dict[best_channel]
        print(f"\nFinal channel ID: {best_channel}")
        print(f"Channel title: {meta['title']}")
        print(f"Counts — Channel search: {meta['source_count']['channel_search']}, Video search: {meta['source_count']['video_search']}")
    else:
        print("No suitable channel found.")
    '''
    
#---------NOTES---------
# Here are some edge cases I am likely to deal with:

# 1. Topic Channel Ranks Higher Than Official Channel
#    - Issue: Artist's auto-generated "Topic" channel may rank above their actual page.
#    - Example: “Superheaven - Topic” shows before “Superheaven”.
#    - Heuristic: Deprioritize channels with no custom URL and title ending in " - Topic".

# 2. Duplicate or Ambiguous Artist Names
#    - Issue: Multiple channels may exist for a generic name like “Herne”.
#    - Heuristic: Use video search fallback (e.g., "Herne official music video") and match uploader channels.

# 3. Legitimate Artist Channels With Low Visibility
#    - Issue: Underground artists might lack subscribers, branding, or even a handle.
#    - Heuristic: Favor channels uploading full music videos or albums over unrelated promo/media snippets.

# 4. Artist Releases Through Labels or Collectives
#    - Issue: Artist content is hosted under label/group accounts (e.g., Stones Throw, Lyrical Lemonade).
#    - Heuristic: Detect label patterns (shared uploads across artists) and tag as collective-hosted.

# 5. Artists Maintain Multiple Active Channels
#    - Issue: Some split content across "Official", "Vlogs", "Live", etc.
#    - Heuristic: Flag duplicate titles and compare engagement (upload count, recent activity, view stats).
