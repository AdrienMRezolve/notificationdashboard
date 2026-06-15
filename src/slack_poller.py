"""Polls Slack DMs and group DMs with user tokens (xoxp-...).

Multi-user aware: polls every per-user token in channel_connections (written by
the connect-slack Edge Function) plus the shared SLACK_USER_TOKEN env secret
(user_id = None). MVP scope: direct and group messages; channel @-mentions are
a later upgrade.
"""
from datetime import datetime, timezone

import requests

from . import config, db

SLACK_API = "https://slack.com/api"


def call(token, method, **params):
    r = requests.get(f"{SLACK_API}/{method}",
                     headers={"Authorization": f"Bearer {token}"},
                     params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"slack {method}: {data.get('error')}")
    return data


def _poll_one(token, user_id, patterns):
    me = call(token, "auth.test")["user_id"]
    since = db.connection_window_start("slack", user_id)
    oldest = f"{since.timestamp():.6f}"

    convos = call(token, "conversations.list", types="im,mpim", limit=200).get("channels", [])
    user_cache = {}
    rows = []

    for convo in convos:
        history = call(token, "conversations.history",
                       channel=convo["id"], oldest=oldest, limit=20)
        for msg in history.get("messages", []):
            uid = msg.get("user")
            if not uid or uid == me or msg.get("subtype"):
                continue
            if uid not in user_cache:
                info = call(token, "users.info", user=uid)["user"]
                user_cache[uid] = (
                    info.get("real_name") or info.get("name"),
                    info.get("profile", {}).get("email") or info.get("name"),
                )
            sender, handle = user_cache[uid]

            try:
                deep_link = call(token, "chat.getPermalink",
                                 channel=convo["id"], message_ts=msg["ts"])["permalink"]
            except RuntimeError:
                deep_link = None

            received = datetime.fromtimestamp(float(msg["ts"]), tz=timezone.utc)
            rows.append({
                "channel": "slack",
                "external_id": f"{convo['id']}:{msg['ts']}",
                "sender": sender,
                "sender_handle": handle,
                "preview": (msg.get("text") or "")[:200],
                "deep_link": deep_link,
                "received_at": received.isoformat(),
                "is_vip": db.is_vip(sender, handle, patterns),
                "user_id": user_id,
            })

    return db.upsert_notifications(rows)


def poll():
    patterns = db.vip_patterns()
    connections = list(db.channel_tokens("slack"))  # per-user
    saw_any = bool(connections)

    total = 0
    for user_id, tokens in connections:
        token = (tokens or {}).get("access_token")
        if not token:
            continue
        try:
            total += _poll_one(token, user_id, patterns)
            db.mark_user_health("slack", user_id, "ok")
        except Exception as e:  # noqa: BLE001 — isolate one user's failure
            print(f"slack[{user_id}]: ERROR {e}")
            db.mark_user_health("slack", user_id, "error", str(e)[:300])

    if config.SLACK_USER_TOKEN:
        saw_any = True
        total += _poll_one(config.SLACK_USER_TOKEN, None, patterns)

    if not saw_any:
        print("slack: no connections configured, skipping")
        return None
    print(f"slack: {total} message(s) across {len(connections)} user(s) + env")
    return total
