import os


def env(name, default=None, required=False):
    value = os.environ.get(name) or default  # treat "" same as missing
    if required and not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


SUPABASE_URL = env("SUPABASE_URL", required=True)
SUPABASE_SECRET_KEY = env("SUPABASE_SECRET_KEY", required=True)  # sb_secret_*, NOT the publishable key

# Microsoft (Outlook + multi-user OAuth). Client registered by Rezolve IT.
# The Graph CLI public client is kept as the MS_CLIENT_ID default only for
# local device-code flows (scripts/outlook_auth.py). The real app values come
# from Supabase/GitHub secrets.
MS_CLIENT_ID = env("MS_CLIENT_ID", "bd9ded6c-52f2-426f-bb90-7a630bc1decd")
MS_TENANT_ID = env("MS_TENANT_ID", "49e55eb4-ecc2-4f12-8494-9c8c5c38be7f")
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
