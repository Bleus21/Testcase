from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# === CONFIG ===
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaacy5fh4cqc4"
MAX_PER_RUN = 30
MAX_PER_USER = 3
HOURS_BACK = 4

# Accounts
ACCOUNTS = [
    ("BSKY_USERNAME_BG", "BSKY_PASSWORD_BG"),
    ("BSKY_USERNAME_BF", "BSKY_PASSWORD_BF"),
    ("BSKY_USERNAME_BP", "BSKY_PASSWORD_BP"),
    ("BSKY_USERNAME_NB", "BSKY_PASSWORD_NB"),
    ("BSKY_USERNAME_HB", "BSKY_PASSWORD_HB"),
]

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

def process_account(username, password):
    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als {username}")

    try:
        feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100})
        items = feed.feed
        log(f"📥 {len(items)} posts opgehaald uit feed.")
    except Exception as e:
        log(f"⚠️ Fout bij ophalen feed: {e}")
        return

    repost_log = "reposted.txt"
    done = set()
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
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
            per_user_count[handle] += 1
            done.add(uri)
            log(f"🔁 Gerepost @{handle}")

            try:
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                )
                liked += 1
            except Exception as e_like:
                log(f"⚠️ Fout bij liken @{handle}: {e_like}")

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar — {reposted} reposts uitgevoerd ({liked} geliked).")

def main():
    for user_key, pass_key in ACCOUNTS:
        username = os.getenv(user_key)
        password = os.getenv(pass_key)
        if not username or not password:
            log(f"⚠️ Secret ontbreekt voor {user_key}.")
            continue
        process_account(username, password)

    # Opruimen (behoud repost-log)
    for file in os.listdir():
        if file not in ["reposted.txt", "testcase_multi.py"]:
            try:
                os.remove(file)
            except Exception:
                pass
    log("🧹 Opschonen voltooid, repost-log behouden.")
    log(f"⏰ Run afgerond op {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()