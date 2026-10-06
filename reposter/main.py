"""One run: for each person, find new Instagram videos and repost them.

Run with:  python -m reposter.main
Set DRY_RUN=1 to see what would happen without uploading anything.
"""
import os
import sys
import tempfile
import time
from datetime import datetime, timezone

import yaml

from . import instagram, notify, secrets, state as state_mod, tiktok, youtube

MAX_ATTEMPTS = 3
KEEP_POSTS = 300


def iso_to_epoch(ts: str) -> float:
    # Instagram format: 2026-10-06T18:22:11+0000
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z").timestamp()


def token_entry(person_state: dict, platform: str, secret_name: str) -> dict:
    """Use the newest token we know about. If someone pasted a fresh token into
    the GitHub secret, that wins over the one saved in state."""
    secret_value = secrets.get(secret_name)
    tokens = person_state.setdefault("tokens", {})
    entry = tokens.get(platform)
    if secret_value and (not entry or entry.get("seed") != state_mod.fingerprint(secret_value)):
        entry = {"value": secret_value, "seed": state_mod.fingerprint(secret_value)}
        tokens[platform] = entry
    if entry:
        secrets.mask(entry.get("value"))
        secrets.mask(entry.get("access_token"))
    return entry


def run() -> int:
    with open(os.environ.get("CONFIG_PATH", "config.yaml")) as f:
        config = yaml.safe_load(f)
    settings = config.get("settings", {})
    dry = os.environ.get("DRY_RUN") == "1"

    key = secrets.get("STATE_KEY")
    if not key:
        # Not set up yet: exit quietly so GitHub doesn't email a failure every 15 minutes.
        print("::warning::Not set up yet: add the STATE_KEY secret (see README step 2).")
        return 0
    state = state_mod.load(key)
    problems = 0

    for person in config.get("people", []):
        name = person["name"]
        ps = state["people"].setdefault(name, {"posts": {}})
        try:
            problems += handle_person(person, ps, settings, dry)
        except Exception as e:  # one person's problem shouldn't stop the others
            problems += 1
            notify.send(f"⚠️ [{name}] run failed: {e}")
        finally:
            state_mod.save(state, key)  # save after each person, in case of a crash

    return 1 if problems and os.environ.get("FAIL_ON_PROBLEMS") == "1" else 0


def handle_person(person: dict, ps: dict, settings: dict, dry: bool) -> int:
    name = person["name"]
    upper = name.upper()
    problems = 0

    ig = token_entry(ps, "instagram", person.get("instagram_secret", f"IG_TOKEN_{upper}"))
    if not ig:
        notify.send(f"⚠️ [{name}] no Instagram token set; skipping")
        return 1
    if not dry:
        instagram.maybe_refresh(ig)
        secrets.mask(ig["value"])

    videos = instagram.recent_videos(ig["value"])

    # First run: don't repost the whole back catalog. Only videos posted from now on.
    if "started_at" not in ps:
        ps["started_at"] = time.time()
        for v in videos:
            ps["posts"].setdefault(v["id"], {"backlog": True})
        print(f"[{name}] first run: marked {len(videos)} existing videos as already handled")
        return 0

    targets = []
    if person.get("youtube", True):
        targets.append("youtube")
    if person.get("tiktok", True):
        targets.append("tiktok")

    max_per_run = int(settings.get("max_videos_per_run", 3))
    handled = 0
    for v in videos:
        if handled >= max_per_run:
            break
        if iso_to_epoch(v["timestamp"]) < ps["started_at"]:
            continue
        rec = ps["posts"].setdefault(v["id"], {})
        if rec.get("backlog"):
            continue
        todo = [t for t in targets if not rec.get(t, {}).get("done")
                and rec.get(t, {}).get("attempts", 0) < MAX_ATTEMPTS]
        if not todo:
            continue
        handled += 1

        if not v.get("media_url"):
            # Instagram hides the file for Reels using licensed music from its library.
            for t in todo:
                rec[t] = {"done": True, "skipped": "no media_url (Instagram library music?)"}
            notify.send(f"⏭️ [{name}] skipped {v.get('permalink')}: Instagram won't share the "
                        "file (usually licensed music). Repost that one by hand.")
            continue

        if dry:
            print(f"[{name}] DRY RUN would post {v.get('permalink')} to {', '.join(todo)}")
            continue

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, f"{v['id']}.mp4")
            instagram.download(v["media_url"], path)
            caption = v.get("caption") or ""
            for t in todo:
                slot = rec.setdefault(t, {})
                try:
                    if t == "youtube":
                        result = post_youtube(person, ps, settings, path, caption)
                    else:
                        result = post_tiktok(person, ps, settings, path, caption)
                    slot.update({"done": True, "id": result, "at": time.time()})
                    notify.send(f"✅ [{name}] {t}: posted {v.get('permalink')} ({result})")
                except Exception as e:
                    slot["attempts"] = slot.get("attempts", 0) + 1
                    slot["last_error"] = str(e)[:300]
                    problems += 1
                    left = MAX_ATTEMPTS - slot["attempts"]
                    notify.send(f"⚠️ [{name}] {t} failed for {v.get('permalink')}: {e}"
                                + (f" (will retry, {left} left)" if left else " (giving up)"))

    # keep the state file small
    if len(ps["posts"]) > KEEP_POSTS:
        for old in list(ps["posts"])[: len(ps["posts"]) - KEEP_POSTS]:
            ps["posts"].pop(old, None)
    return problems


def post_youtube(person, ps, settings, path, caption) -> str:
    upper = person["name"].upper()
    entry = token_entry(ps, "youtube", person.get("youtube_secret", f"YT_REFRESH_TOKEN_{upper}"))
    if not entry:
        raise youtube.YouTubeError(f"missing secret YT_REFRESH_TOKEN_{upper}")
    token = youtube.access_token(secrets.get("YT_CLIENT_ID"), secrets.get("YT_CLIENT_SECRET"),
                                 entry["value"])
    secrets.mask(token)
    return youtube.upload(token, path, caption,
                          privacy=settings.get("youtube_privacy", "public"),
                          add_shorts_tag=settings.get("youtube_add_shorts_tag", True))


def post_tiktok(person, ps, settings, path, caption) -> str:
    upper = person["name"].upper()
    entry = token_entry(ps, "tiktok", person.get("tiktok_secret", f"TIKTOK_REFRESH_TOKEN_{upper}"))
    if not entry:
        raise tiktok.TikTokError(f"missing secret TIKTOK_REFRESH_TOKEN_{upper}")
    tiktok.ensure_access_token(entry, secrets.get("TIKTOK_CLIENT_KEY"),
                               secrets.get("TIKTOK_CLIENT_SECRET"))
    secrets.mask(entry["access_token"])
    secrets.mask(entry["value"])
    return tiktok.upload(entry["access_token"], path, caption,
                         mode=settings.get("tiktok_mode", "draft"),
                         privacy=settings.get("tiktok_privacy", "PUBLIC_TO_EVERYONE"),
                         brand_content=person.get("tiktok_branded_content", False),
                         brand_organic=person.get("tiktok_promotes_own_brand", False))


if __name__ == "__main__":
    sys.exit(run())
