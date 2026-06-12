"""One-time local script: get a Gmail refresh token.

Prerequisites (see README step 2):
  1. Google Cloud project with the Gmail API enabled
  2. OAuth client of type "Desktop app" — download is not needed,
     just copy the client ID and secret below or set them as env vars.

Run:  pip install google-auth-oauthlib && python scripts/gmail_auth.py
A browser opens; authorize with your Gmail account; the refresh token prints.
Store it as the GOOGLE_REFRESH_TOKEN secret.
"""
import os

from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID") or input("Google client ID: ").strip()
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET") or input("Google client secret: ").strip()

flow = InstalledAppFlow.from_client_config(
    {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    },
    scopes=["https://www.googleapis.com/auth/gmail.readonly"],
)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

print("\nAdd these to your GitHub repo secrets / .env:\n")
print(f"GOOGLE_CLIENT_ID={CLIENT_ID}")
print(f"GOOGLE_CLIENT_SECRET={CLIENT_SECRET}")
print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
