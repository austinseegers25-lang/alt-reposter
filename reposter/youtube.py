"""YouTube Shorts upload via the YouTube Data API (resumable upload)."""
import os
import re

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


class YouTubeError(Exception):
    pass


def access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    r = requests.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }, timeout=30)
    data = r.json()
    if "access_token" not in data:
        raise YouTubeError(f"token refresh failed: {data.get('error_description') or data}")
    return data["access_token"]


def make_title(caption: str, add_shorts_tag: bool) -> str:
    first = (caption or "").strip().splitlines()[0] if (caption or "").strip() else ""
    first = re.sub(r"#\w+", "", first)          # hashtags go in the description
    first = re.sub(r"[<>]", "", first).strip()
    suffix = " #Shorts" if add_shorts_tag else ""
    if not first:
        first = "New video"
    return first[: 100 - len(suffix)].rstrip() + suffix


def upload(token: str, path: str, caption: str, privacy: str, add_shorts_tag: bool) -> str:
    size = os.path.getsize(path)
    body = {
        "snippet": {
            "title": make_title(caption, add_shorts_tag),
            "description": re.sub(r"[<>]", "", caption or "")[:4900],
            "categoryId": "22",
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    init = requests.post(
        UPLOAD_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(size),
        },
        json=body,
        timeout=60,
    )
    if init.status_code != 200 or "Location" not in init.headers:
        raise YouTubeError(f"upload start failed ({init.status_code}): {init.text[:300]}")
    with open(path, "rb") as f:
        put = requests.put(
            init.headers["Location"],
            headers={"Content-Type": "video/mp4", "Content-Length": str(size)},
            data=f,
            timeout=600,
        )
    if put.status_code not in (200, 201):
        raise YouTubeError(f"upload failed ({put.status_code}): {put.text[:300]}")
    return put.json()["id"]
