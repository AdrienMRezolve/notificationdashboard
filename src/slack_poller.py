"""Polls Slack DMs and group DMs with a user token (xoxp-...).

MVP scope: direct and group messages addressed to you. Channel @-mentions are
a later upgrade (requires scanning every channel or the paid search API).
"""
from datetime import datetime, timezone

import requests

from . import config, db

SLACK_API = "https://slack.com/api"


def call(method, **params):
    r = requests.get(f"{SLACK_API}/{method}",
                     headers={"Authorization": f"Bearer {config.SLACK_USER_TOKEN}"},
                     params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"slack {method}: {data.get('error')}")
    return data


def poll():
    if not config.SLACK_USER_TOKEN:
        print("slack: SLACK_USER_TOKEN not set, skipping")
        return 0

    me = call("auth.test")["user_id"]
    since = db.poll_window_start("slack")
    oldest = f"{since.timestamp():.6f}"

    convos = call("conversations.list", types="im,mpim", limit=200).get("channels", [])
    patterns = db.vip_patterns()
    user_cache = {}
    rows = []

    for convo in convos:
        history = call("conversations.history",
                       channel=convo["id"], oldest=oldest, limit=20)
        for msg in history.get("messages", []):
            uid = msg.get("user")
            if not uid or uid == me or msg.get("subtype"):
                continue
            if uid not in user_cache:
                info = call("users.info", user=uid)["user"]
                user_cache[uid] = (
                    info.get("real_name") or info.get("name"),
                    info.get("profile", {}).get("email") or info.get("name"),
                )
            sender, handle = user_cache[uid]

            try:
                deep_link = call("chat.getPermalink",
                                 channel=convo["id"],
                                 message_ts=msg["ts"])["permalink"]
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
            })

    n = db.upsert_notifications(rows)
    print(f"slack: {len(convos)} conversations scanned, {n} new messages")
    return n
