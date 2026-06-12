"""Matrix -> Supabase ingester.

A long-running bot that /syncs a Matrix homeserver and pushes every new
bridged message into the same `notifications` table the rest of the dashboard
uses. Matrix is used purely as a read adapter for channels that have no
official personal API (WhatsApp, LinkedIn): the mautrix bridges drop messages
into portal rooms, this bot relays them onward. It never sends a message back,
so the read-only guarantee holds.

Run as a service (docker compose), not a cron — it holds a long-poll /sync.
"""
import os
import sys
import time

import requests

HOMESERVER = os.environ["MATRIX_HOMESERVER"].rstrip("/")
ACCESS_TOKEN = os.environ["MATRIX_ACCESS_TOKEN"]
BOT_MXID = os.environ["MATRIX_BOT_MXID"]  # e.g. @radar:localhost — to skip our own echoes

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]

TOKEN_FILE = os.environ.get("SYNC_TOKEN_FILE", "/data/sync_token")

# Map the localpart prefix the bridge gives its puppet users to our channel.
# mautrix-whatsapp -> @whatsapp_<jid>:server ; mautrix-linkedin -> @linkedin_<id>:server
CHANNEL_PREFIXES = {
    "whatsapp_": "whatsapp",
    "linkedin_": "linkedin",
}
# Bridge control bots emit notices we never want in the feed.
SKIP_LOCALPARTS = {"whatsappbot", "linkedinbot"}

mx = requests.Session()
mx.headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"

_display_cache = {}
_vip_cache = {"patterns": [], "fetched_at": 0.0}


def channel_for(sender):
    localpart = sender.split(":", 1)[0].lstrip("@")
    if localpart in SKIP_LOCALPARTS:
        return None
    for prefix, channel in CHANNEL_PREFIXES.items():
        if localpart.startswith(prefix):
            return channel
    return None  # not a bridged sender — ignore (e.g. our own messages, system)


def display_name(sender):
    if sender not in _display_cache:
        try:
            r = mx.get(f"{HOMESERVER}/_matrix/client/v3/profile/{sender}/displayname", timeout=15)
            name = r.json().get("displayname") if r.ok else None
        except requests.RequestException:
            name = None
        # mautrix appends " (WA)" / " (LinkedIn)" suffixes — trim for a clean feed
        if name:
            name = name.split(" (")[0].strip()
        _display_cache[sender] = name or sender.split(":", 1)[0].lstrip("@")
    return _display_cache[sender]


def vip_patterns():
    if time.time() - _vip_cache["fetched_at"] > 300:
        try:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/vip_senders",
                params={"select": "pattern"},
                headers=_sb_headers(), timeout=15)
            if r.ok:
                _vip_cache["patterns"] = [row["pattern"].lower() for row in r.json()]
                _vip_cache["fetched_at"] = time.time()
        except requests.RequestException:
            pass
    return _vip_cache["patterns"]


def _sb_headers(extra=None):
    h = {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def insert_notifications(rows):
    if not rows:
        return
    # ignore-duplicates so a re-sync of the same event never resurfaces a read card
    requests.post(
        f"{SUPABASE_URL}/rest/v1/notifications",
        json=rows,
        headers=_sb_headers({"Prefer": "resolution=ignore-duplicates,return=minimal"}),
        timeout=30,
    ).raise_for_status()


def mark_healthy():
    for channel in set(CHANNEL_PREFIXES.values()):
        requests.post(
            f"{SUPABASE_URL}/rest/v1/connections",
            json={"channel": channel, "status": "ok", "last_polled_at": _now_iso()},
            headers=_sb_headers({"Prefer": "resolution=merge-duplicates,return=minimal"}),
            timeout=15,
        )


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_since():
    try:
        with open(TOKEN_FILE) as f:
            return f.read().strip() or None
    except FileNotFoundError:
        return None


def save_since(token):
    with open(TOKEN_FILE, "w") as f:
        f.write(token)


def auto_join(invited_rooms):
    for room_id in invited_rooms:
        try:
            mx.post(f"{HOMESERVER}/_matrix/client/v3/join/{room_id}", json={}, timeout=20)
            print(f"joined portal room {room_id}", flush=True)
        except requests.RequestException as e:
            print(f"join failed {room_id}: {e}", flush=True)


def handle_sync(data):
    rooms = data.get("rooms", {})
    auto_join(list(rooms.get("invite", {}).keys()))

    patterns = vip_patterns()
    batch = []
    for room_id, room in rooms.get("join", {}).items():
        for ev in room.get("timeline", {}).get("events", []):
            if ev.get("type") != "m.room.message":
                continue
            sender = ev.get("sender", "")
            if sender == BOT_MXID:
                continue
            channel = channel_for(sender)
            if channel is None:
                continue

            content = ev.get("content", {})
            msgtype = content.get("msgtype", "m.text")
            if msgtype == "m.text":
                body = content.get("body", "")
            else:
                body = content.get("body") or f"[{msgtype.replace('m.', '')}]"

            name = display_name(sender)
            event_id = ev["event_id"]
            haystack = f"{name} {sender}".lower()
            batch.append({
                "channel": channel,
                "external_id": event_id,
                "sender": name,
                "sender_handle": sender,
                "preview": body[:200],
                "deep_link": f"https://matrix.to/#/{room_id}/{event_id}",
                "received_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime(ev.get("origin_server_ts", 0) / 1000)),
                "is_vip": any(p in haystack for p in patterns),
            })

    if batch:
        insert_notifications(batch)
        print(f"ingested {len(batch)} message(s)", flush=True)


def main():
    since = load_since()
    print(f"ingester starting (since={'resume' if since else 'fresh'})", flush=True)
    backoff = 1
    while True:
        params = {"timeout": 30000, "set_presence": "offline"}
        if since:
            params["since"] = since
        try:
            r = mx.get(f"{HOMESERVER}/_matrix/client/v3/sync", params=params, timeout=60)
            r.raise_for_status()
            data = r.json()
            handle_sync(data)
            since = data["next_batch"]
            save_since(since)
            mark_healthy()
            backoff = 1
        except requests.RequestException as e:
            print(f"sync error: {e} (retry in {backoff}s)", flush=True)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    sys.exit(main())
