from datetime import datetime, timezone

import requests

from . import config, db
from .classify import classify, parse_from_header

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"


def access_token():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": config.GOOGLE_CLIENT_ID,
        "client_secret": config.GOOGLE_CLIENT_SECRET,
        "refresh_token": config.GOOGLE_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def poll():
    if not (config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET and config.GOOGLE_REFRESH_TOKEN):
        print("gmail: credentials not set, skipping")
        return 0

    token = access_token()
    headers = {"Authorization": f"Bearer {token}"}
    since = db.poll_window_start("gmail")
    # Inbox mail, plus linkedin.com mail wherever Gmail categorised it
    query = f"after:{int(since.timestamp())} (in:inbox OR from:linkedin.com)"

    r = requests.get(f"{GMAIL_API}/messages",
                     params={"q": query, "maxResults": 50},
                     headers=headers, timeout=30)
    r.raise_for_status()
    ids = [m["id"] for m in r.json().get("messages", [])]

    patterns = db.vip_patterns()
    rows = []
    for msg_id in ids:
        m = requests.get(
            f"{GMAIL_API}/messages/{msg_id}",
            params={"format": "metadata",
                    "metadataHeaders": ["From", "Subject"]},
            headers=headers, timeout=30)
        m.raise_for_status()
        msg = m.json()

        hdrs = {h["name"].lower(): h["value"]
                for h in msg.get("payload", {}).get("headers", [])}
        from_name, from_email = parse_from_header(hdrs.get("from", ""))
        subject = hdrs.get("subject", "")

        result = classify(from_name, from_email, subject)
        if result is None:
            continue
        channel, sender = result

        received = datetime.fromtimestamp(
            int(msg["internalDate"]) / 1000, tz=timezone.utc)
        preview = (subject + " — " + msg.get("snippet", "")).strip(" —")[:200]
        if channel == "linkedin":
            preview = msg.get("snippet", "")[:200]
            deep_link = "https://www.linkedin.com/messaging/"
        else:
            deep_link = f"https://mail.google.com/mail/u/0/#all/{msg.get('threadId', msg_id)}"

        rows.append({
            "channel": channel,
            "external_id": msg_id,
            "sender": sender,
            "sender_handle": from_email,
            "preview": preview,
            "deep_link": deep_link,
            "received_at": received.isoformat(),
            "is_vip": db.is_vip(sender, from_email, patterns),
        })

    n = db.upsert_notifications(rows)
    print(f"gmail: {len(ids)} fetched, {n} kept")
    return n
