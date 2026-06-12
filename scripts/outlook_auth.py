"""One-time local script: get a Microsoft refresh token via device-code flow.

This IS the "connect with your own login" experience: you sign in on
Microsoft's page with your normal account + MFA; no password ever touches
this code.

Prerequisites (see README step 2): an Entra ID app registration with
"Allow public client flows" enabled and delegated Mail.Read permission.

Run:  python3 scripts/outlook_auth.py
"""
import os
import sys
import time

import requests

CLIENT_ID = os.environ.get("MS_CLIENT_ID") or input("Application (client) ID: ").strip()
TENANT_ID = os.environ.get("MS_TENANT_ID") or input("Directory (tenant) ID [organizations]: ").strip() or "organizations"
SCOPE = "https://graph.microsoft.com/Mail.Read offline_access"
BASE = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0"

dc = requests.post(f"{BASE}/devicecode",
                   data={"client_id": CLIENT_ID, "scope": SCOPE}, timeout=30).json()
if "user_code" not in dc:
    sys.exit(f"Device code request failed: {dc.get('error_description', dc)}")

print(f"\n{dc['message']}\n")  # "go to https://microsoft.com/devicelogin and enter XXX"

while True:
    time.sleep(dc.get("interval", 5))
    tok = requests.post(f"{BASE}/token", data={
        "client_id": CLIENT_ID,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "device_code": dc["device_code"],
    }, timeout=30).json()
    if "refresh_token" in tok:
        break
    if tok.get("error") not in ("authorization_pending", "slow_down"):
        sys.exit(f"Auth failed: {tok.get('error_description', tok)}")

print("Signed in. Add these to your GitHub repo secrets:\n")
print(f"MS_CLIENT_ID={CLIENT_ID}")
print(f"MS_TENANT_ID={TENANT_ID}")
print(f"MS_REFRESH_TOKEN={tok['refresh_token']}")
