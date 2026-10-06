"""Optional Discord ping when something posts or breaks (set DISCORD_WEBHOOK)."""
import requests

from . import secrets


def send(text: str) -> None:
    print(text)
    url = secrets.get("DISCORD_WEBHOOK")
    if not url:
        return
    try:
        requests.post(url, json={"content": text[:1900]}, timeout=15)
    except requests.RequestException:
        pass
