from atproto import Client
from datetime import datetime, timedelta, timezone
import os

# === CONFIG ===
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaacy5fh4cqc4"
MAX_PER_RUN = 30
MAX_PER_USER = 3
HOURS_BACK = 4

# Accounts en secrets
ACCOUNTS = [
    ("BG", os.getenv("BSKY_USERNAME_BG"), os.getenv("BSKY_PASSWORD_BG")),
    ("BF", os.getenv("BSKY_USERNAME_BF"), os.getenv("BSKY_PASSWORD_BF")),
    ("BP", os.getenv("BSKY_USERNAME_BP"), os.getenv("BSKY_PASSWORD_BP")),
    ("NB", os.getenv("BSKY_USERNAME_NB"), os.getenv("BSKY_PASSWORD_NB")),
    ("HB", os.getenv("BSKY_USERNAME_HB"), os.getenv("BSKY_PASSWORD_HB")),
]

def log(msg):
    now = datetime.now().strftime("[%H:%M:%S]")
    print(f"{now} {msg}")

def parse_time(record, post):
    for attr in ["createdAt", "indexedAt", "timestamp"]:
        val = getattr(record, attr, None) or getattr(post, attr, None)
        if val:
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except Exception:
                continue
    return None

def run_for_account(tag, username, password):
    if not username or not password:
        log(f"⚠️ {tag}: ontbrekende inloggegevens, overslaan.")
        return

    client = Client()
    try:
        client.login(username, password)
        log(f"✅ {tag}: ingelogd.")
    except Exception as e:
        log(f"❌ {tag}: fout bij inloggen: {e}")
        return

    try:
        feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100}).feed
    except Exception as e:
        log(f"⚠️ {tag}: feed ophalen mislukt: {e}")
        return

    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)
    repost_file = f"reposted_{tag}.txt"
    done = set()
    if os.path.exists(repost_file):
        with open(repost_file, "r") as f:
            done = set(f.read().splitlines())

    posts = []
    for item in feed:
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

        created = parse_time(record, post)
        if not created or created < cutoff:
            continue

        posts.append({"uri": uri, "cid": cid, "handle": handle, "created": created})

    posts.sort(key=lambda x: x["created"])  # Oudste eerst
    posts = posts[:MAX_PER_RUN]

    reposted = 0
    per_user = {}

    for p in posts:
        if reposted >= MAX_PER_RUN:
            break
        user = p["handle"]
        if per_user.get(user, 0) >= MAX_PER_USER:
            continue

        try:
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": p["uri"], "cid": p["cid"]},
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            client.app.bsky.feed.like.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": p["uri"], "cid": p["cid"]},
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            done.add(p["uri"])
            reposted += 1
            per_user[user] = per_user.get(user, 0) + 1
        except Exception:
            continue

    with open(repost_file, "w") as f:
        f.write("\n".join(done))

    log(f"🏁 {tag}: {reposted} reposts uitgevoerd ({len(posts)} bekeken).")

def main():
    log("🚀 Start multi-account run...")
    for tag, user, pwd in ACCOUNTS:
        run_for_account(tag, user, pwd)
    log("✅ Alle accounts voltooid.")

if __name__ == "__main__":
    main()