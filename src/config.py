import os


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


SUPABASE_URL = env("SUPABASE_URL", required=True)
SUPABASE_SECRET_KEY = env("SUPABASE_SECRET_KEY", required=True)  # sb_secret_*, NOT the publishable key

# Microsoft (Outlook now, Teams later) — device-code flow.
# Defaults to Microsoft's first-party "Graph CLI" public client, so no Azure
# app registration is required. Override MS_CLIENT_ID only if you registered
# your own app.
MS_CLIENT_ID = env("MS_CLIENT_ID", "14d82eec-204b-4c2f-b7e8-296a70dab67e")
MS_TENANT_ID = env("MS_TENANT_ID", "organizations")
MS_REFRESH_TOKEN = env("MS_REFRESH_TOKEN")

# Gmail (dormant — swap back in run_all.py for Gmail users)
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET")
GOOGLE_REFRESH_TOKEN = env("GOOGLE_REFRESH_TOKEN")

SLACK_USER_TOKEN = env("SLACK_USER_TOKEN")  # xoxp-..., user token (not bot)

# How far back the very first poll looks. Subsequent polls resume from
# connections.last_polled_at with a small overlap.
FIRST_RUN_LOOKBACK_HOURS = int(env("FIRST_RUN_LOOKBACK_HOURS", "24"))
OVERLAP_SECONDS = 120
