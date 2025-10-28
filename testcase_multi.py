# filename: testcase_multi.py
from atproto import Client
from datetime import datetime, timedelta, timezone
import os
import time

# --- Instellingen ---
WINDOW_HOURS = 4
MAX_PER_RUN = 30
MAX_PER_USER = 3
SLEEP_BETWEEN_ACTIONS = 0  # geen interval (direct achter elkaar)

# Secrets verwacht:
# - feed  (FEED URI, bv: at://did:.../app.bsky.feed.generator/xxxxx)
# - BSKY_USERNAME_BG / BSKY_PASSWORD_BG
# - BSKY_USERNAME_BF / BSKY_PASSWORD_BF
# - BSKY_USERNAME_BP / BSKY_PASSWORD_BP
# - BSKY_USERNAME_NB / BSKY_PASSWORD_NB
# - BSKY_USERNAME_HB / BSKY_PASSWORD_HB

ACCOUNTS = [
    ("BG", "BSKY_USERNAME_BG", "BSKY_PASSWORD_BG"),
    ("BF", "BSKY_USERNAME_BF", "BSKY_PASSWORD_BF"),
    ("BP", "BSKY_USERNAME_BP", "BSKY_PASSWORD_BP"),
    ("NB", "BSKY_USERNAME_NB", "BSKY_PASSWORD_NB"),
    ("HB", "BSKY_USERNAME_HB", "BSKY_PASSWORD_HB"),
]

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def log(msg: str):
    # Minimale logging, geen namen/URIs
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def parse_time(record, post):
    # Zoek een bruikbare timestamp
    for attr in ("createdAt", "indexedAt", "created_at", "timestamp"):
        val = getattr(record, attr, None) or getattr(post, attr, None)
        if val:
            try:
                return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
            except Exception:
                continue
    return None

def load_done(logfile: str):
    if os.path.exists(logfile):
        with open(logfile, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_done(logfile: str, done: set):
    # Schrijf deterministisch
    with open(logfile, "w", encoding="utf-8") as f:
        for uri in sorted(done):
            f.write(uri + "\n")

def process_account(tag: str, user_env: str, pass_env: str, feed_uri: str):
    username = os.getenv(user_env)
    password = os.getenv(pass_env)

    if not username or not password:
        log(f"❌ Secrets missen voor account {tag} ({user_env}/{pass_env}). Sla over.")
        return

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als {tag}")

    # Feed ophalen
    try:
        feed = client.app.bsky.feed.get_feed({"feed": feed_uri, "limit": 100}).feed
    except Exception as e:
        log(f"⚠️ Feed ophalen mislukt ({tag}): {e}")
        return

    cutoff = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)
    logfile = f"reposted_{tag}.txt"
    done = load_done(logfile)

    # Verzamel kandidaten
    candidates = []
    for item in feed:
        post = item.post
        record = post.record

        # Sla reposts/replies over
        if getattr(item, "reason", None) is not None:
            continue
        if getattr(record, "reply", None):
            continue

        created = parse_time(record, post)
        if not created or created < cutoff:
            continue

        uri = post.uri
        if uri in done:
            continue

        author_id = getattr(post.author, "did", None) or getattr(post.author, "handle", "unknown")
        candidates.append({
            "uri": uri,
            "cid": post.cid,
            "author_id": author_id,
            "created": created,
        })

    # Oudste eerst
    candidates.sort(key=lambda x: x["created"])

    # Per-user limiet + totaal limiet
    per_author = {}
    selected = []
    for c in candidates:
        if len(selected) >= MAX_PER_RUN:
            break
        count = per_author.get(c["author_id"], 0)
        if count >= MAX_PER_USER:
            continue
        per_author[c["author_id"]] = count + 1
        selected.append(c)

    log(f"🧩 {len(selected)} geschikte posts voor {tag} (venster {WINDOW_HOURS}u, max {MAX_PER_RUN}, {MAX_PER_USER}/user).")

    # Repost + like
    reposted = 0
    liked = 0
    for idx, p in enumerate(selected, start=1):
        try:
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": p["uri"], "cid": p["cid"]},
                    "createdAt": now_iso(),
                },
            )
            reposted += 1
            # Like
            try:
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": p["uri"], "cid": p["cid"]},
                        "createdAt": now_iso(),
                    },
                )
                liked += 1
            except Exception:
                # like mislukking overslaan zonder extra ruis
                pass

            # Markeer als gedaan
            done.add(p["uri"])

            if SLEEP_BETWEEN_ACTIONS > 0 and idx < len(selected):
                time.sleep(SLEEP_BETWEEN_ACTIONS)

        except Exception:
            # fout bij specifieke post — stil verder
            continue

    save_done(logfile, done)
    log(f"🎯 {tag}: {reposted} reposts uitgevoerd ({liked} geliked). Log: {logfile}")

def main():
    feed_uri = os.getenv("feed")
    if not feed_uri:
        log("❌ Secret 'feed' ontbreekt. Stop.")
        return

    for tag, user_env, pass_env in ACCOUNTS:
        process_account(tag, user_env, pass_env, feed_uri)

    log(f"⏰ Run afgerond op {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()
