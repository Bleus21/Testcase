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
    now = datetime.now(timezone.utc).strftime("[%H:%M:%S]")
    print(f"{now} {msg}")

def parse_time(record, post):
    for attr in ["createdAt", "indexedAt", "created_at", "timestamp"]:
        val = getattr(record, attr, None) or getattr(post, attr, None)
        if val:
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except Exception:
                continue
    return None

def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]
    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als {username}")

    try:
        log("📥 Ophalen feed...")
        feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100})
        items = feed.feed
        log(f"🕒 {len(items)} posts opgehaald.")
    except Exception as e:
        log(f"⚠️ Fout bij ophalen feed: {e}")
        return

    repost_log = "reposted_bf.txt"
    done = set()
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())

    all_posts = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)

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
    all_posts.sort(key=lambda x: x["created"])  # Oudste eerst

    reposted = 0
    liked = 0
    per_user_count = {}

    for post in all_posts:
        if reposted >= MAX_PER_RUN:
            break

        handle = post["handle"]
        uri = post["uri"]
        cid = post["cid"]

        per_user_count[handle] = per_user_count.get(handle, 0)
        if per_user_count[handle] >= MAX_PER_USER:
            continue

        try:
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            reposted += 1
            done.add(uri)
            per_user_count[handle] += 1

            client.app.bsky.feed.like.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            liked += 1

        except Exception as e:
            log(f"⚠️ Fout bij @{handle}: {e}")

    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar — {reposted} reposts uitgevoerd ({liked} geliked).")
    log(f"⏰ Run afgerond om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()