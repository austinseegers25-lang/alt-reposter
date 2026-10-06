"""TikTok upload via the Content Posting API.

Two modes:
  draft  - video lands in the TikTok app's inbox; the person taps it, adds a
           sound if they want, and posts. Works before TikTok's audit.
  direct - posts straight to the profile. Only works publicly after TikTok
           approves ("audits") the app; before that TikTok forces it private.
"""
import math
import os
import time

import requests

API = "https://open.tiktokapis.com"
MIN_CHUNK = 5 * 1024 * 1024
CHUNK = 10 * 1024 * 1024


class TikTokError(Exception):
    pass


def _check(r: requests.Response) -> dict:
    try:
        data = r.json()
    except ValueError:
        raise TikTokError(f"HTTP {r.status_code}: {r.text[:300]}")
    err = data.get("error") or {}
    if r.status_code != 200 or err.get("code") not in (None, "ok"):
        raise TikTokError(f"{err.get('code')}: {err.get('message') or r.text[:300]}")
    return data.get("data") or {}


def ensure_access_token(entry: dict, client_key: str, client_secret: str) -> bool:
    """Refresh the 24h access token when needed. Returns True if anything changed."""
    if entry.get("access_token") and entry.get("expires_at", 0) > time.time() + 300:
        return False
    r = requests.post(f"{API}/v2/oauth/token/", data={
        "client_key": client_key,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": entry["value"],
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    data = r.json()
    if "access_token" not in data:
        raise TikTokError(f"token refresh failed: {data.get('error_description') or data}")
    entry["access_token"] = data["access_token"]
    entry["expires_at"] = time.time() + int(data.get("expires_in", 86400))
    if data.get("refresh_token"):
        entry["value"] = data["refresh_token"]  # TikTok may rotate it
    return True


def chunk_plan(size: int):
    """TikTok rules: files under 5 MB go whole; otherwise fixed-size chunks with
    the leftover folded into the last chunk."""
    if size <= MIN_CHUNK:
        return size, 1
    chunk = min(CHUNK, size)
    return chunk, max(1, math.floor(size / chunk))


def _upload_chunks(upload_url: str, path: str, size: int, chunk: int, count: int):
    with open(path, "rb") as f:
        for i in range(count):
            start = i * chunk
            end = size - 1 if i == count - 1 else start + chunk - 1
            f.seek(start)
            body = f.read(end - start + 1)
            r = requests.put(upload_url, data=body, headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(len(body)),
                "Content-Range": f"bytes {start}-{end}/{size}",
            }, timeout=300)
            if r.status_code not in (200, 201, 206):
                raise TikTokError(f"chunk {i + 1}/{count} failed ({r.status_code}): {r.text[:200]}")


def _source_info(size: int) -> dict:
    chunk, count = chunk_plan(size)
    return {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk,
            "total_chunk_count": count}


def upload(token: str, path: str, caption: str, mode: str, privacy: str,
           brand_content: bool = False, brand_organic: bool = False) -> str:
    size = os.path.getsize(path)
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json; charset=UTF-8"}
    source = _source_info(size)

    if mode == "draft":
        data = _check(requests.post(f"{API}/v2/post/publish/inbox/video/init/",
                                    headers=headers, json={"source_info": source}, timeout=60))
    else:
        creator = _check(requests.post(f"{API}/v2/post/publish/creator_info/query/",
                                       headers=headers, timeout=30))
        allowed = creator.get("privacy_level_options") or ["SELF_ONLY"]
        level = privacy if privacy in allowed else "SELF_ONLY"
        post_info = {
            "title": (caption or "")[:2200],
            "privacy_level": level,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "brand_content_toggle": bool(brand_content),
            "brand_organic_toggle": bool(brand_organic),
        }
        data = _check(requests.post(f"{API}/v2/post/publish/video/init/", headers=headers,
                                    json={"post_info": post_info, "source_info": source},
                                    timeout=60))

    _upload_chunks(data["upload_url"], path, size, source["chunk_size"], source["total_chunk_count"])
    return data["publish_id"]
