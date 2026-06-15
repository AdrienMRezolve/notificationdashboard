"""Polls the Outlook inbox via Microsoft Graph (delegated Mail.Read).

Auth: device-code flow done once with scripts/outlook_auth.py. Microsoft
rotates refresh tokens on use, so the current one is persisted in the
channel_auth table (service-role only); the MS_REFRESH_TOKEN secret is just
the seed for the first run.

Like the Gmail variant, the mailbox doubles as a universal adapter:
LinkedIn / Teams notification emails are reclassified by classify.py.
"""
from datetime import datetime, timezone

import requests

from . import config, db
from .classify import classify

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPE = "https://graph.microsoft.com/Mail.Read offline_access"


def access_token():
    stored = db.get_auth("email") or {}
    refresh = stored.get("refresh_token") or config.MS_REFRESH_TOKEN
    r = requests.post(
        f"https://login.microsoftonline.com/{config.MS_TENANT_ID}/oauth2/v2.0/token",
        data={
            "client_id": config.MS_CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "scope": SCOPE,
        }, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("refresh_token"):
        db.save_auth("email", {"refresh_token": data["refresh_token"]})
    return data["access_token"]


def poll():
    if not (config.MS_CLIENT_ID and config.MS_REFRESH_TOKEN):
        print("outlook: credentials not set, skipping")
        return None

    headers = {"Authorization": f"Bearer {access_token()}"}
    since = db.poll_window_start("email")
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

    patterns = db.vip_patterns()
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
        })

    n = db.upsert_notifications(rows)
    print(f"outlook: {len(messages)} fetched, {n} kept")
    return n
