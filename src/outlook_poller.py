"""Polls Outlook inboxes via Microsoft Graph (delegated Mail.Read).

Multi-user aware: it polls every per-user connection in channel_connections
(written by the connect-microsoft Edge Function) AND, for backward compat, the
single shared mailbox configured via the MS_REFRESH_TOKEN env secret
(user_id = None). Each message is written tagged with its owner's user_id.

The mailbox doubles as a universal adapter: LinkedIn / Teams notification
emails are reclassified by classify.py.
"""
from datetime import timezone

import requests

from . import config, db
from .classify import classify

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPE = "https://graph.microsoft.com/Mail.Read offline_access"


def access_token(refresh_token):
    """Exchange a refresh token. Returns (access_token, rotated_refresh_or_None)."""
    r = requests.post(
        f"https://login.microsoftonline.com/{config.MS_TENANT_ID}/oauth2/v2.0/token",
        data={
            "client_id": config.MS_CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": SCOPE,
        }, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data["access_token"], data.get("refresh_token")


def _poll_one(refresh_token, user_id, patterns):
    token, rotated = access_token(refresh_token)
    if rotated:  # Microsoft rotates the refresh token on every use — persist it
        if user_id is None:
            db.save_auth("email", {"refresh_token": rotated})
        else:
            db.save_user_tokens("email", user_id, {"refresh_token": rotated})

    headers = {"Authorization": f"Bearer {token}"}
    since = db.connection_window_start("email", user_id)
    since_iso = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    r = requests.get(
        f"{GRAPH}/me/mailFolders/inbox/messages",
        params={
            "$filter": f"receivedDateTime ge {since_iso}",
            "$orderby": "receivedDateTime desc",
            "$top": 50,
            "$select": "id,subject,from,bodyPreview,receivedDateTime,webLink",
        }, headers=headers, timeout=30)
    r.raise_for_status()
    messages = r.json().get("value", [])

    rows = []
    for msg in messages:
        addr = (msg.get("from") or {}).get("emailAddress") or {}
        from_name = addr.get("name") or addr.get("address") or "Unknown"
        from_email = (addr.get("address") or "").lower()
        subject = msg.get("subject") or ""

        result = classify(from_name, from_email, subject)
        if result is None:
            continue
        channel, sender = result

        snippet = (msg.get("bodyPreview") or "").replace("\r\n", " ").strip()
        if channel == "linkedin":
            preview = snippet[:200]
            deep_link = "https://www.linkedin.com/messaging/"
        else:
            preview = f"{subject} — {snippet}".strip(" —")[:200]
            deep_link = msg.get("webLink")

        rows.append({
            "channel": channel,
            "external_id": msg["id"],
            "sender": sender,
            "sender_handle": from_email,
            "preview": preview,
            "deep_link": deep_link,
            "received_at": msg["receivedDateTime"],
            "is_vip": db.is_vip(sender, from_email, patterns),
            "user_id": user_id,
        })

    return db.upsert_notifications(rows)


def poll():
    if not config.MS_CLIENT_ID:
        print("outlook: MS_CLIENT_ID not set, skipping")
        return None

    patterns = db.vip_patterns()
    connections = list(db.channel_tokens("email"))  # per-user
    saw_any = bool(connections)

    total = 0
    for user_id, tokens in connections:
        refresh = (tokens or {}).get("refresh_token")
        if not refresh:
            continue
        try:
            total += _poll_one(refresh, user_id, patterns)
            db.mark_user_health("email", user_id, "ok")
        except Exception as e:  # noqa: BLE001 — isolate one user's failure
            print(f"outlook[{user_id}]: ERROR {e}")
            db.mark_user_health("email", user_id, "error", str(e)[:300])

    # Shared env-secret mailbox (your own single-user setup)
    env_refresh = (db.get_auth("email") or {}).get("refresh_token") or config.MS_REFRESH_TOKEN
    if env_refresh:
        saw_any = True
        total += _poll_one(env_refresh, None, patterns)

    if not saw_any:
        print("outlook: no connections configured, skipping")
        return None
    print(f"outlook: {total} message(s) kept across {len(connections)} user(s) + env")
    return total
