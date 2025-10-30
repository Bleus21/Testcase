from atproto import Client
import os
from datetime import datetime, timedelta, timezone

# === CONFIG ===
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaacy5fh4cqc4"
MAX_PER_RUN = 30
MAX_PER_USER = 3
HOURS_BACK = 4
REPOST_LOG = "reposted_nb.txt"

def log(msg: str):
    """Print logregel met tijdstempel (stille versie, zonder namen)."""
    now = datetime.now(timezone.utc).strftime("[%H:%M:%S]")
    print(f"{now} {msg}")

def parse_time(record, post):
    """Probeer timestamp te vinden."""
    for attr in ["createdAt", "indexedAt", "created_at", "timestamp"]:
        val = getattr(record, attr, None) or getattr(post, attr, None)
        if val:
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except Exception:
                continue
    return None

def main():
    username = os.environ["BSKY_USERNAME_NB"]
    password = os.environ["BSKY_PASSWORD_NB"]

    client = Client()
    client.login(username, password)
    log("✅ Ingelogd.")
    log("📥 Ophalen feed...")

    try:
        feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100})
        items = feed.feed
        log(f"📊 {len(items)} posts gevonden in feed.")
    except Exception as e:
        log(f"⚠️ Fout bij ophalen feed: {e}")
        return

    done = set()
    if os.path.exists(REPOST_LOG):
        with open(REPOST_LOG, "r", encoding="utf-8") as f:
            done = set(f.read().splitlines())

    all_posts = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)

    for item in items:
        post = item.post
        record = post.record
        uri = post.uri
        cid = post.cid
        handle = getattr(post.author, "handle", "unknown")

        # Skip replies, reposts, en reeds verwerkte posts
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

    total = len(all_posts)
    log(f"🧩 {total} geschikte posts gevonden.")
    all_posts.sort(key=lambda x: x["created"])  # Oudste eerst

    reposted = 0
    liked = 0
    per_user = {}

    for post in all_posts:
        if reposted >= MAX_PER_RUN:
            break

        handle = post["handle"]
        uri = post["uri"]
        cid = post["cid"]

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
            reposted += 1
            per_user[handle] += 1
            done.add(uri)
            log(f"🔁 Gerepost ({reposted}/{MAX_PER_RUN})")

            try:
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                )
                liked += 1
                log(f"❤️ Geliked ({liked}/{MAX_PER_RUN})")
            except Exception:
                continue

        except Exception:
            continue

    with open(REPOST_LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar — {reposted} reposts uitgevoerd ({liked} geliked).")
    log(f"🧹 Opschonen voltooid, repost-log behouden.")
    log(f"⏰ Run afgerond om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()