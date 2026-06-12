# Inbox radar — unified notification dashboard (backend)

Read-only notification aggregator: Python pollers (GitHub Actions cron, every
10 min) pull new incoming messages from Gmail and Slack into Supabase; LinkedIn
and Teams arrive through their Gmail notification emails, reclassified into
their own channel. The frontend is a separate Lovable app (see
`LOVABLE_PROMPT.md`) reading the same Supabase project.

Everything runs on free tiers: Gmail API (free), Slack app (free),
Supabase (free), GitHub Actions (~600 min/month at this schedule, within the
2,000 free minutes for private repos).

```
Gmail API  ─┐
            ├─ src/run_all.py (cron */10) ──> Supabase `notifications` ──> Lovable UI
Slack API  ─┘        │
                     └──> Supabase `connections` (health) ─────────────────┘
```

## Setup checklist

### 1. Supabase (~2 min)
Run `sql/001_init.sql` in the SQL editor of your Supabase project (a new
project or the existing one — tables don't collide).

### 2. Gmail (~10 min, one time)
1. https://console.cloud.google.com → new project → enable **Gmail API**.
2. *APIs & Services → OAuth consent screen*: External, add yourself as a test
   user (stay in "Testing" — no verification needed for personal use).
3. *Credentials → Create credentials → OAuth client ID → Desktop app*.
   Copy client ID + secret.
4. Locally: `pip install google-auth-oauthlib requests` then
   `python scripts/gmail_auth.py` → browser opens → authorize → it prints your
   `GOOGLE_REFRESH_TOKEN`.

> Heads-up: while the consent screen is in "Testing" mode, Google expires the
> refresh token after **7 days**. Publish the app (no verification required for
> the read-only Gmail scope on a personal project... it will show an "unverified"
> warning once, which is fine) to make the token long-lived.

### 3. Slack (~5 min)
1. https://api.slack.com/apps → *Create New App → From an app manifest* →
   paste `slack-app-manifest.yml` → pick your workspace.
2. *Install to Workspace* (workspace admin approval may be required).
3. Copy the **User OAuth Token** (`xoxp-...`) — not the bot token.

### 4. GitHub repo
1. Create a **private** repo, push this folder.
2. *Settings → Secrets and variables → Actions*: add `SUPABASE_URL`,
   `SUPABASE_SECRET_KEY` (the `sb_secret_...` key), `GOOGLE_CLIENT_ID`,
   `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `SLACK_USER_TOKEN`.
3. *Actions* tab → run **poll-channels** manually once (workflow_dispatch) and
   check the log; afterwards it runs every 10 minutes by itself.

### 5. Frontend
New Lovable project → paste `LOVABLE_PROMPT.md` → connect Lovable's Supabase
integration with the **publishable** key (`sb_publishable_...`).

### Local test run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in
set -a; source .env; set +a
python -m src.run_all
```

## Scope decisions (MVP)

- **Slack**: DMs and group DMs only. Channel @-mentions need either a scan of
  every channel or the search API — planned upgrade, not MVP.
- **LinkedIn**: only what LinkedIn emails you ("X sent you a message" style
  notifications). Make sure LinkedIn message emails are ON: linkedin.com →
  Settings → Notifications → Messaging → Email. Full message sync would require
  Unipile (~€50+/month) — deliberate later upgrade after validation.
- **WhatsApp**: out of scope. No official personal API; bridges risk a number
  ban. Unipile covers it later if needed.
- **Re-polls never reset read state**: inserts use `ignore_duplicates`, so a
  card you marked read stays read.
- **VIPs**: rows in `vip_senders` are case-insensitive substring patterns
  matched against sender name + email/handle at poll time (e.g. `@prospect.com`).

## Later upgrades

- Teams natively via Microsoft Graph (needs Azure AD app + admin consent).
- Slack channel mentions.
- LinkedIn/WhatsApp full sync via Unipile.
- LLM scoring pass ("deal reply / internal / noise") + morning digest.
