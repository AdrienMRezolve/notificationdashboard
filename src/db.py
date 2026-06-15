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


def _window(last):
    if last:
        start = datetime.fromisoformat(last.replace("Z", "+00:00"))
        return start - timedelta(seconds=config.OVERLAP_SECONDS)
    return datetime.now(timezone.utc) - timedelta(hours=config.FIRST_RUN_LOOKBACK_HOURS)


def poll_window_start(channel):
    """Window for the shared env-secret connection (user_id is null)."""
    res = sb.table("connections").select("last_polled_at").eq("channel", channel).execute()
    return _window(res.data[0]["last_polled_at"] if res.data else None)


def connection_window_start(channel, user_id):
    """Per-user window when user_id is set, else the shared env-secret window."""
    if user_id is None:
        return poll_window_start(channel)
    res = (sb.table("channel_connections").select("last_polled_at")
           .eq("channel", channel).eq("user_id", user_id).execute())
    return _window(res.data[0]["last_polled_at"] if res.data else None)


def channel_tokens(channel):
    """Per-user connections for a channel: list of (user_id, tokens dict)."""
    res = (sb.table("channel_connections").select("user_id, tokens")
           .eq("channel", channel).execute())
    return [(r["user_id"], r["tokens"]) for r in res.data]


def save_user_tokens(channel, user_id, tokens):
    sb.table("channel_connections").update({
        "tokens": tokens,
    }).eq("channel", channel).eq("user_id", user_id).execute()


def mark_user_health(channel, user_id, status, error=None):
    sb.table("channel_connections").update({
        "status": status,
        "last_polled_at": datetime.now(timezone.utc).isoformat(),
        "last_error": error,
    }).eq("channel", channel).eq("user_id", user_id).execute()


def get_auth(channel):
    res = sb.table("channel_auth").select("auth").eq("channel", channel).execute()
    return res.data[0]["auth"] if res.data else None


def save_auth(channel, auth):
    sb.table("channel_auth").upsert({
        "channel": channel,
        "auth": auth,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def mark_connection(channel, status, error=None):
    sb.table("connections").upsert({
        "channel": channel,
        "status": status,
        "last_polled_at": datetime.now(timezone.utc).isoformat(),
        "last_error": error,
    }).execute()
