"""Instagram side: find new Reels and download the original file (no watermark)."""
import time

import requests

GRAPH = "https://graph.instagram.com"
FIELDS = "id,caption,media_type,media_product_type,media_url,permalink,timestamp"
REFRESH_EVERY = 7 * 24 * 3600  # long-lived tokens last 60 days; refresh weekly


class InstagramError(Exception):
    pass


def maybe_refresh(token_entry: dict) -> bool:
    """Refresh the long-lived token about once a week. Returns True if it changed."""
    now = time.time()
    if now - token_entry.get("refreshed_at", 0) < REFRESH_EVERY:
        return False
    r = requests.get(
        f"{GRAPH}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token_entry["value"]},
        timeout=30,
    )
    data = r.json()
    if r.status_code != 200 or "access_token" not in data:
        # A token under 24h old can't be refreshed yet; that's fine, try next run.
        token_entry["refreshed_at"] = now - REFRESH_EVERY + 6 * 3600
        return False
    token_entry["value"] = data["access_token"]
    token_entry["refreshed_at"] = now
    return True


def recent_videos(access_token: str, limit: int = 25) -> list:
    r = requests.get(
        f"{GRAPH}/me/media",
        params={"fields": FIELDS, "limit": limit, "access_token": access_token},
        timeout=30,
    )
    data = r.json()
    if r.status_code != 200:
        raise InstagramError(data.get("error", {}).get("message", r.text[:300]))
    videos = [
        m for m in data.get("data", [])
        if m.get("media_type") == "VIDEO" and m.get("media_product_type") in ("REELS", "FEED")
    ]
    videos.sort(key=lambda m: m.get("timestamp", ""))  # oldest first
    return videos


def download(url: str, dest: str) -> int:
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        size = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
                size += len(chunk)
    return size
