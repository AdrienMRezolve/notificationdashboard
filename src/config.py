import os


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


SUPABASE_URL = env("SUPABASE_URL", required=True)
SUPABASE_SECRET_KEY = env("SUPABASE_SECRET_KEY", required=True)  # sb_secret_*, NOT the publishable key

GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET")
GOOGLE_REFRESH_TOKEN = env("GOOGLE_REFRESH_TOKEN")

SLACK_USER_TOKEN = env("SLACK_USER_TOKEN")  # xoxp-..., user token (not bot)

# How far back the very first poll looks. Subsequent polls resume from
# connections.last_polled_at with a small overlap.
FIRST_RUN_LOOKBACK_HOURS = int(env("FIRST_RUN_LOOKBACK_HOURS", "24"))
OVERLAP_SECONDS = 120
