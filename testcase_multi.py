from atproto import Client
import os
from datetime import datetime, timedelta, timezone

# === CONFIG ===
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaacy5fh4cqc4"
MAX_PER_RUN = 30
MAX_PER_USER = 3
HOURS_BACK = 4

def log(msg: str):
    """Eenvoudige log met tijdstempel"""
    now = datetime.now(timezone.utc).strftime("[%H:%M:%S]")
    print(f"{now}] {msg}")

def run_for_account(username, password):
    client = Client()
    try:
        client.login(username, password)
        log(f"🔑 Ingelogd als {username}")

        # Feed ophalen
        feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100})
        items = feed.feed
        log(f"📥 {len(items)} posts opgehaald")

        cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)
        reposted = 0
        liked = 0
        per_user = {}

        for item in sorted(items, key=lambda x: getattr(x.post.record, "createdAt", "")):
            if reposted >= MAX_PER_RUN:
                break

            post = item.post
            record = post.record
            uri = post.uri
            cid = post.cid
            author = getattr(post.author, "handle", "onbekend")

            # Skip reposts of replies
            if hasattr(item, "reason") and item.reason:
                continue
            if getattr(record, "reply", None):
                continue

            created_at = getattr(record, "createdAt", None)
            if not created_at:
                continue

            try:
                created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except:
                continue

            if created_dt < cutoff:
                continue

            if per_user.get(author, 0) >= MAX_PER_USER:
                continue

            # Repost
            try:
                client.app.bsky.feed.repost.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                )
                reposted += 1
                per_user[author] = per_user.get(author, 0) + 1

                # Like direct daarna
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                )
                liked += 1

            except Exception:
                continue

        log(f"🔁 {reposted} reposts uitgevoerd ({liked} likes)")

    except Exception as e:
        log(f"⚠️ Fout bij account {username}: {e}")
    finally:
        try:
            client.close()
        except:
            pass

def main():
    accounts = [
        ("BSKY_USERNAME_BG", "BSKY_PASSWORD_BG"),
        ("BSKY_USERNAME_BF", "BSKY_PASSWORD_BF"),
        ("BSKY_USERNAME_BP", "BSKY_PASSWORD_BP"),
        ("BSKY_USERNAME_NB", "BSKY_PASSWORD_NB"),
        ("BSKY_USERNAME_HB", "BSKY_PASSWORD_HB"),
    ]

    for user_env, pass_env in accounts:
        username = os.getenv(user_env)
        password = os.getenv(pass_env)
        if username and password:
            run_for_account(username, password)
        else:
            log(f"⚠️ Geheim ontbreekt voor {user_env}")

    log(f"✅ Alle accounts voltooid om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()