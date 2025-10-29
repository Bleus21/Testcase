from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# === CONFIG ===
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaacy5fh4cqc4"
MAX_PER_RUN = 30
MAX_PER_USER = 3
HOURS_BACK = 4

def log(msg: str):
    """Minimale logging met tijdstempel"""
    now = datetime.now(timezone.utc).strftime("[%H:%M:%S]")
    print(f"{now} {msg}")

def parse_time(record, post):
    """Zoek timestamp"""
    for attr in ["createdAt", "indexedAt", "created_at", "timestamp"]:
        val = getattr(record, attr, None) or getattr(post, attr, None)
        if val:
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except Exception:
                continue
    return None

def main():
    username = os.environ["BSKY_USERNAME_BF"]
    password = os.environ["BSKY_PASSWORD_BF"]

    client = Client()
    client.login(username, password)
    log("✅ Ingelogd.")

    # Ophalen feed
    try:
        feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100}).feed
        log(f"📥 {len(feed)} posts opgehaald uit feed.")
    except Exception as e:
        log(f"⚠️ Fout bij ophalen feed: {e}")
        return

    # Repost-log laden
    repost_log = "reposted_bf.txt"
    done = set()
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())

    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)
    all_posts = []

    for item in feed:
        post = item.post
        record = post.record
        uri = post.uri
        cid = post.cid