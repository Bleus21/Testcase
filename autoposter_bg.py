from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# === CONFIG ===
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaabnak6nvizm"
MAX_PER_RUN = 30
MAX_PER_USER = 3
HOURS_BACK = 4

def log(msg: str):
    """Minimale logging"""
    now = datetime.now(timezone.utc).strftime("[%H:%M:%S]")
    print(f"{now} {msg}")

def parse_time(record, post):
    """Vind correcte tijd van post"""
    for attr in ["createdAt", "indexedAt", "created_at", "timestamp"]:
        val = getattr(record, attr, None) or getattr(post, attr, None)
        if val:
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except Exception:
                continue
    return None

def main():
    username = os.environ["BSKY_USERNAME_BG"]
    password = os.environ["BSKY_PASSWORD_BG"]

    client = Client()
    client.login(username, password)
    log("✅ Ingelogd.")

    # Feed ophalen
    try:
        feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100})
        items = feed.feed
        log(f"📥 {len(items)} posts opgehaald uit feed.")
    except Exception as e:
        log(f"⚠️ Fout bij ophalen feed: {e}")
        return

    # Log inlezen
    log_file = "reposted_bg.txt"
    done = set()
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            done = set(f.read().splitlines())

    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)
    all_posts = []

    for item in items:
        post = item.post
        record = post.record
        uri = post.uri
        cid = post.cid
        handle = getattr(post.author, "handle", "onbekend")

        if hasattr(item, "reason") and item.reason is not None:
            continue
        if getattr(record, "reply", None):
            continue
        if uri in done:
            continue

        created_dt = parse_time(record, post)
        if not created_dt or created_dt < cutoff:
            continue

        all_posts.append({
            "handle": handle,
            "uri": uri,
            "cid": cid,
            "created": created_dt,
        })

    log(f"🧩 {len(all_posts)} geschikte posts gevonden.")
    all_posts.sort(key=lambda x: x["created"])

    reposted = 0
    liked = 0
    per_user = {}

    for post in all_posts:
        if reposted >= MAX_PER_RUN:
            break
        handle = post["handle"]
        if per_user.get(handle, 0) >= MAX_PER_USER:
            continue

        try:
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": post["uri"], "cid": post["cid"]},
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            client.app.bsky.feed.like.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": post["uri"], "cid": post["cid"]},
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            done.add(post["uri"])
            reposted += 1
            liked += 1
            per_user[handle] = per_user.get(handle, 0) + 1
            time.sleep(2)

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    # Log opslaan
    with open(log_file, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar — {reposted} reposts uitgevoerd ({liked} geliked).")
    log(f"⏰ Run afgerond op {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()