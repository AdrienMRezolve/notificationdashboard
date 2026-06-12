from datetime import datetime, timedelta, timezone

from supabase import create_client

from . import config

sb = create_client(config.SUPABASE_URL, config.SUPABASE_SECRET_KEY)


def upsert_notifications(rows):
    """Insert new notifications; re-polled duplicates are ignored so is_read survives."""
    if not rows:
        return 0
    sb.table("notifications").upsert(
        rows, on_conflict="channel,external_id", ignore_duplicates=True
    ).execute()
    return len(rows)


def vip_patterns():
    res = sb.table("vip_senders").select("pattern").execute()
    return [r["pattern"].lower() for r in res.data]


def is_vip(sender, handle, patterns):
    haystack = f"{sender or ''} {handle or ''}".lower()
    return any(p in haystack for p in patterns)


def poll_window_start(channel):
    res = sb.table("connections").select("last_polled_at").eq("channel", channel).execute()
    last = res.data[0]["last_polled_at"] if res.data else None
    if last:
        start = datetime.fromisoformat(last.replace("Z", "+00:00"))
        return start - timedelta(seconds=config.OVERLAP_SECONDS)
    return datetime.now(timezone.utc) - timedelta(hours=config.FIRST_RUN_LOOKBACK_HOURS)


def mark_connection(channel, status, error=None):
    sb.table("connections").upsert({
        "channel": channel,
        "status": status,
        "last_polled_at": datetime.now(timezone.utc).isoformat(),
        "last_error": error,
    }).execute()
