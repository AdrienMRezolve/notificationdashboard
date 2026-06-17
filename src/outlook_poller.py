"""Polls Outlook inboxes via Microsoft Graph.

Two auth modes (auto-detected):
  1. App-only (client_credentials): requires Mail.Read *application* permission
     with admin consent. No user tokens needed — just MS_CLIENT_ID + MS_CLIENT_SECRET.
     Set MS_MAILBOX_EMAIL to the mailbox to poll (e.g. AdrienMauriac@rezolve.com).
     This is the preferred mode for the env-secret personal mailbox.

  2. Delegated (refresh_token): per-user tokens from channel_connections (multi-user
     OAuth flow via the connect-microsoft Edge Function).

The mailbox doubles as a universal adapter: LinkedIn / Teams notification
emails are reclassified by classify.py.
"""
from datetime import timezone

import requests

from . import config, db
from .classify import classify

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPE = "https://graph.microsoft.com/Mail.Read offline_access"


def app_only_token():
    """Get an app-only access token via client_credentials. No rotation needed."""
    r = requests.post(
        f"https://login.microsoftonline.com/{config.MS_TENANT_ID}/oauth2/v2.0/token",
        data={
            "client_id": config.MS_CLIENT_ID,
            "client_secret": config.MS_CLIENT_SECRET,
            "grant_type": "client_credentials",
            "scope": "https://graph.microsoft.com/.default",
        }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def delegated_token(refresh_token, client_id=None):
    """Exchange a refresh token. Returns (access_token, rotated_refresh_or_None)."""
    payload = {
        "client_id": client_id or config.MS_CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": SCOPE,
    }
    if config.MS_CLIENT_SECRET:
        payload["client_secret"] = config.MS_CLIENT_SECRET
    r = requests.post(
        f"https://login.microsoftonline.com/{config.MS_TENANT_ID}/oauth2/v2.0/token",
        data=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data["access_token"], data.get("refresh_token")


def _poll_one(token, user_id, patterns, refresh_token=None, client_id=None):
    if refresh_token:
        token, rotated = delegated_token(refresh_token, client_id=client_id)
        if rotated:
            if user_id is None:
                db.save_auth("email", {"refresh_token": rotated})
            else:
                db.save_user_tokens("email", user_id, {"refresh_token": rotated})

    headers = {"Authorization": f"Bearer {token}"}
    since = db.connection_window_start("email", user_id)
    since_iso = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # App-only uses /users/{email}/..., delegated uses /me/...
    mailbox = config.MS_MAILBOX_EMAIL if not refresh_token else "me"
    base_url = f"{GRAPH}/users/{mailbox}" if not refresh_token else f"{GRAPH}/me"

    r = requests.get(
        f"{base_url}/mailFolders/inbox/messages",
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
    connections = list(db.channel_tokens("email"))  # per-user (delegated tokens)
    saw_any = bool(connections)

    total = 0
    for user_id, tokens in connections:
        refresh = (tokens or {}).get("refresh_token")
        if not refresh:
            continue
        try:
            total += _poll_one(None, user_id, patterns, refresh_token=refresh)
            db.mark_user_health("email", user_id, "ok")
        except Exception as e:  # noqa: BLE001 — isolate one user's failure
            print(f"outlook[{user_id}]: ERROR {e}")
            db.mark_user_health("email", user_id, "error", str(e)[:300])

    # App-only mode: client_credentials + Mail.Read application permission.
    # Requires MS_CLIENT_SECRET + MS_MAILBOX_EMAIL. No refresh token needed.
    if config.MS_CLIENT_SECRET and config.MS_MAILBOX_EMAIL:
        saw_any = True
        try:
            token = app_only_token()
            total += _poll_one(token, None, patterns)
        except Exception as e:  # noqa: BLE001
            raise  # surface to run_all so connections table shows error

    # Delegated fallback: env-secret refresh token (legacy / if app-only not configured)
    elif not saw_any:
        env_refresh = (db.get_auth("email") or {}).get("refresh_token") or config.MS_REFRESH_TOKEN
        if env_refresh:
            saw_any = True
            total += _poll_one(None, None, patterns, refresh_token=env_refresh)

    if not saw_any:
        print("outlook: no connections configured, skipping")
        return None
    print(f"outlook: {total} message(s) kept across {len(connections)} user(s) + env")
    return total
