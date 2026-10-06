"""Runs the whole bot against fake Instagram/YouTube/TikTok servers.

    python -m pytest tests -q
"""
import json
import os
import time
from datetime import datetime, timezone

import pytest
from cryptography.fernet import Fernet

from reposter import main, state as state_mod, tiktok, youtube


class Resp:
    def __init__(self, status=200, data=None, headers=None, text=""):
        self.status_code = status
        self._data = data
        self.headers = headers or {}
        self.text = text or json.dumps(data)

    def json(self):
        return self._data

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield b"x" * (12 * 1024 * 1024)  # 12 MB fake video

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    key = Fernet.generate_key().decode()
    secrets = {
        "STATE_KEY": key,
        "IG_TOKEN_LUCAS": "ig-lucas",
        "YT_REFRESH_TOKEN_LUCAS": "yt-lucas",
        "TIKTOK_REFRESH_TOKEN_LUCAS": "tt-lucas",
        "YT_CLIENT_ID": "id", "YT_CLIENT_SECRET": "sec",
        "TIKTOK_CLIENT_KEY": "ck", "TIKTOK_CLIENT_SECRET": "cs",
    }
    monkeypatch.setenv("SECRETS_JSON", json.dumps(secrets))
    import reposter.secrets as s
    s._cache = None
    (tmp_path / "config.yaml").write_text(
        "people:\n  - name: lucas\nsettings:\n  tiktok_mode: draft\n")
    return key


def make_fake(media, calls):
    def fake_get(url, params=None, stream=False, timeout=None):
        calls.append(("GET", url))
        if url.endswith("/me/media"):
            return Resp(data={"data": media})
        if "refresh_access_token" in url:
            return Resp(data={"access_token": "ig-lucas-2", "expires_in": 5184000})
        if url.startswith("https://cdn"):
            return Resp()
        raise AssertionError(url)

    def fake_post(url, data=None, json=None, headers=None, params=None, timeout=None):
        calls.append(("POST", url, json))
        if url == youtube.TOKEN_URL:
            return Resp(data={"access_token": "yt-access"})
        if url == youtube.UPLOAD_URL:
            return Resp(headers={"Location": "https://upload/session"})
        if url.endswith("/v2/oauth/token/"):
            return Resp(data={"access_token": "tt-access", "expires_in": 86400,
                              "refresh_token": "tt-lucas-rotated"})
        if url.endswith("/inbox/video/init/"):
            return Resp(data={"data": {"publish_id": "pub1", "upload_url": "https://tt/upload"},
                              "error": {"code": "ok"}})
        raise AssertionError(url)

    def fake_put(url, data=None, headers=None, timeout=None):
        body = data.read() if hasattr(data, "read") else data
        calls.append(("PUT", url, headers.get("Content-Range"), len(body)))
        if url == "https://upload/session":
            return Resp(data={"id": "ytvid1"})
        return Resp(status=201, data={})

    return fake_get, fake_post, fake_put


def ig_ts(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")


def patch(monkeypatch, media, calls):
    g, p, u = make_fake(media, calls)
    for mod in ("reposter.instagram", "reposter.youtube", "reposter.tiktok"):
        monkeypatch.setattr(f"{mod}.requests.get", g, raising=False)
        monkeypatch.setattr(f"{mod}.requests.post", p, raising=False)
        monkeypatch.setattr(f"{mod}.requests.put", u, raising=False)


def test_full_flow(env, monkeypatch):
    calls = []
    old = {"id": "old1", "media_type": "VIDEO", "media_product_type": "REELS",
           "media_url": "https://cdn/old1.mp4", "caption": "old", "permalink": "p/old1",
           "timestamp": ig_ts(time.time() - 86400)}
    patch(monkeypatch, [old], calls)

    # run 1: only marks existing videos, posts nothing
    assert main.run() == 0
    assert not any(c[0] == "PUT" for c in calls)

    # run 2: a new reel appears -> goes to YouTube and TikTok once
    new = {"id": "new1", "media_type": "VIDEO", "media_product_type": "REELS",
           "media_url": "https://cdn/new1.mp4", "caption": "Turned $50 into $900 #memecoin",
           "permalink": "p/new1", "timestamp": ig_ts(time.time() + 5)}
    photo = {"id": "img1", "media_type": "IMAGE", "media_product_type": "FEED",
             "timestamp": ig_ts(time.time() + 6)}
    calls.clear()
    patch(monkeypatch, [old, new, photo], calls)
    assert main.run() == 0
    puts = [c for c in calls if c[0] == "PUT"]
    assert ("PUT", "https://upload/session") == puts[0][:2]
    tt = [c for c in puts if c[1] == "https://tt/upload"]
    # 12 MB -> one 12 MB chunk (10 MB chunk + remainder folded in)
    assert tt == [("PUT", "https://tt/upload", "bytes 0-12582911/12582912", 12582912)]
    yt_body = [c for c in calls if c[0] == "POST" and c[1] == youtube.UPLOAD_URL][0][2]
    assert yt_body["snippet"]["title"] == "Turned $50 into $900 #Shorts"

    # state is encrypted and remembers the rotated TikTok token
    raw = open("state.enc", "rb").read()
    assert b"tt-lucas" not in raw
    st = state_mod.load(env)
    assert st["people"]["lucas"]["posts"]["new1"]["youtube"]["id"] == "ytvid1"
    assert st["people"]["lucas"]["tokens"]["tiktok"]["value"] == "tt-lucas-rotated"

    # run 3: nothing new -> nothing uploaded again
    calls.clear()
    patch(monkeypatch, [old, new, photo], calls)
    assert main.run() == 0
    assert not any(c[0] == "PUT" for c in calls)


def test_chunk_plan():
    assert tiktok.chunk_plan(3_000_000) == (3_000_000, 1)
    assert tiktok.chunk_plan(7 * 1024 * 1024) == (7 * 1024 * 1024, 1)
    assert tiktok.chunk_plan(35 * 1024 * 1024) == (10 * 1024 * 1024, 3)


def test_title():
    assert youtube.make_title("", True) == "New video #Shorts"
    assert len(youtube.make_title("a" * 300, True)) == 100
