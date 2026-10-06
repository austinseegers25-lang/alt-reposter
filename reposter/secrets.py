"""Reads GitHub secrets.

The workflow passes every repo secret in as one JSON blob (SECRETS_JSON), so you
can add a new person's secrets without touching the workflow file. When running
locally, plain environment variables work too.
"""
import json
import os

_cache = None


def get(name: str, default=None):
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(os.environ.get("SECRETS_JSON") or "{}")
        except json.JSONDecodeError:
            _cache = {}
    value = _cache.get(name) or os.environ.get(name)
    return value if value else default


def mask(value: str) -> None:
    """Tell GitHub Actions to hide this value if it ever shows up in a log."""
    if value and os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::add-mask::{value}")
