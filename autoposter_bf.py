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
    """Minimale log (alleen samenvatting aan eind)"""
    now = datetime.now(timezone.utc).strftime("[%H:%M:%S]")
    print(f"{now} {msg}")

def parse_time(record, post):
    """Zoek timestamp in record"""
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

    try:
        feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100})
        items = feed.feed
    except Exception as e:
        log(f"⚠️ Fout bij ophalen feed: {e}")
        return

    repost_log = "reposted_bf.txt"
    done = set()
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())

    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)
    posts = []

    for item in items:
        post = item.post
        record = post.record
        uri = post.uri
        cid = post.cid
        handle = getattr(post.author, "handle", "unknown")

        if hasattr(item, "reason") and item.reason is not None:
            continue
        if getattr(record, "reply", None):
            continue
        if uri in done:
            continue

        created = parse_time(record, post)
        if not created or created < cutoff:
            continue

        posts.append({"uri": uri, "cid": cid, "handle": handle, "created": created})

    posts.sort(key=lambda x: x["created"])
    total = len(posts)
    log(f"📊 {total} geschikte posts gevonden.")

    reposted = 0
    liked = 0
    per_user = {}

    for post in posts:
        if reposted >= MAX_PER_RUN:
            break
        handle = post["handle"]
        if per_user.get(handle, 0) >= MAX_PER_USER:
            continue

        uri = post["uri"]
        cid = post["cid"]
        try:
            # Repost
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            reposted += 1
            done.add(uri)
            per_user[handle] = per_user.get(handle, 0) + 1

            # Like
            client.app.bsky.feed.like.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            liked += 1
            time.sleep(1)

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar — {reposted} reposts uitgevoerd ({liked} geliked).")
    log(f"🧹 Opschonen voltooid, repost-log behouden.")
    log(f"⏰ Run afgerond op {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()