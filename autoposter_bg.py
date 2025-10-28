from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# === CONFIG ===
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaacy5fh4cqc4"
MAX_PER_RUN = 30
MAX_PER_USER = 3
HOURS_BACK = 4
REPOST_LOG = "reposted_bg.txt"

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
    username = os.environ["BSKY_USERNAME_BG"]
    password = os.environ["BSKY_PASSWORD_BG"]
    client = Client()
    client.login(username, password)
    log("✅ Ingelogd.")

    try:
        feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100})
        items = feed.feed
        log(f"📥 {len(items)} posts opgehaald uit feed.")
    except Exception as e:
        log(f"⚠️ Fout bij ophalen feed: {e}")
        return

    done = set()
    if os.path.exists(REPOST_LOG):
        with open(REPOST_LOG, "r") as f:
            done = set(f.read().splitlines())

    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)
    posts = []
    for item in items:
        post = item.post
        record = post.record
        uri = post.uri
        cid = post.cid
        handle = getattr(post.author, "handle", "onbekend")

        if getattr(record, "reply", None) or uri in done:
            continue
        created_dt = parse_time(record, post)
        if not created_dt or created_dt < cutoff:
            continue

        posts.append({"uri": uri, "cid": cid, "handle": handle, "created": created_dt})

    posts.sort(key=lambda x: x["created"])
    posts = posts[:MAX_PER_RUN]
    log(f"🧩 {len(posts)} geschikte posts gevonden.")

    reposted = 0
    liked = 0
    per_user = {}

    for p in posts:
        handle = p["handle"]
        uri = p["uri"]
        cid = p["cid"]

        per_user[handle] = per_user.get(handle, 0)
        if per_user[handle] >= MAX_PER_USER:
            continue

        try:
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            done.add(uri)
            reposted += 1
            per_user[handle] += 1
            time.sleep(1.5)

            try:
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                )
                liked += 1
                time.sleep(1)
            except Exception:
                continue
        except Exception:
            continue

    with open(REPOST_LOG, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar — {reposted} reposts uitgevoerd ({liked} geliked).")
    log(f"🧹 Opschonen voltooid, repost-log behouden.")
    log(f"⏰ Run afgerond op {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()