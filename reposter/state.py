"""Encrypted state file.

The bot has to remember two things between runs:
  1. which Instagram videos it already reposted (so nothing posts twice)
  2. refreshed login tokens (Instagram and TikTok hand out new ones over time)

Tokens are secrets, so the whole file is encrypted with STATE_KEY (a GitHub
secret) before it is committed back to the repo. Without the key the file is
unreadable noise, so it is safe even in a public repo.
"""
import hashlib
import json
import os

from cryptography.fernet import Fernet, InvalidToken

STATE_PATH = os.environ.get("STATE_PATH", "state.enc")


def _fernet(key: str) -> Fernet:
    return Fernet(key.encode() if isinstance(key, str) else key)


def load(key: str) -> dict:
    if not os.path.exists(STATE_PATH):
        return {"version": 1, "people": {}}
    with open(STATE_PATH, "rb") as f:
        blob = f.read()
    try:
        return json.loads(_fernet(key).decrypt(blob))
    except InvalidToken:
        raise SystemExit(
            "Could not decrypt state.enc. STATE_KEY changed? Delete state.enc to start "
            "fresh (the bot will then treat existing Instagram posts as already handled)."
        )


def save(state: dict, key: str) -> None:
    blob = _fernet(key).encrypt(json.dumps(state, sort_keys=True).encode())
    with open(STATE_PATH, "wb") as f:
        f.write(blob)


def fingerprint(value: str) -> str:
    """Short hash used to notice when a GitHub secret was replaced by hand."""
    return hashlib.sha256((value or "").encode()).hexdigest()[:16]
