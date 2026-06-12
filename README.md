# Inbox radar — unified notification dashboard (backend)

Read-only notification aggregator: Python pollers (GitHub Actions cron, every
10 min) pull new incoming messages from Outlook and Slack into Supabase;
LinkedIn and Teams arrive through their notification emails in the Outlook
inbox, reclassified into their own channel. The frontend is a separate Lovable
app (see `LOVABLE_PROMPT.md`) reading the same Supabase project.

Everything runs on free tiers: Microsoft Graph (free), Slack app (free),
Supabase (free), GitHub Actions (~600 min/month at this schedule, within the
2,000 free minutes for private repos).

```
MS Graph   ─┐
            ├─ src/run_all.py (cron */10) ──> Supabase `notifications` ──> Lovable UI
Slack API  ─┘        │
                     └──> Supabase `connections` (health) ─────────────────┘
```

(A Gmail poller also exists in `src/gmail_poller.py`, dormant — register it in
`run_all.py` for Gmail users.)

## Setup checklist

### 1. Supabase (~2 min)
Run `sql/001_init.sql` in the SQL editor of your Supabase project (a new
project or the existing one — tables don't collide).

### 2. Outlook / Microsoft (~5 min, one time) — no Azure access needed
The script defaults to Microsoft's own first-party "Graph CLI" public client
(client ID `14d82eec-...`), which exists in every tenant, so **you do not need
to register an app in the Azure portal.**

1. Locally: `python3 scripts/outlook_auth.py` → it prints a code → open
   https://microsoft.com/devicelogin, enter the code, sign in with your normal
   Microsoft account (your own username/password + MFA — the password never
   touches this code).
2. It prints `MS_REFRESH_TOKEN` (and `MS_CLIENT_ID`/`MS_TENANT_ID`). You only
   need to set **`MS_REFRESH_TOKEN`** as a secret; the client ID and tenant
   default correctly.

> If sign-in says **"needs admin approval"**, your tenant requires admin
> consent for delegated Mail.Read. Two fallbacks: (a) ask IT to consent to
> Mail.Read for the Graph CLI app — it's read-only on your own mailbox, a
> small ask; or (b) register your own app and set `MS_CLIENT_ID`/`MS_TENANT_ID`
> (the old portal steps, kept in git history).

> Token rotation: Microsoft issues a NEW refresh token on every use. The
> poller persists the current one in the `channel_auth` table (hidden from the
> frontend key); the `MS_REFRESH_TOKEN` secret only seeds the very first run.

### 3. Slack (~5 min)
1. https://api.slack.com/apps → *Create New App → From an app manifest* →
   paste `slack-app-manifest.yml` → pick your workspace.
2. *Install to Workspace* (workspace admin approval may be required).
3. Copy the **User OAuth Token** (`xoxp-...`) — not the bot token.

### 4. GitHub repo
1. Create a **private** repo, push this folder.
2. *Settings → Secrets and variables → Actions*: add `SUPABASE_URL`,
   `SUPABASE_SECRET_KEY` (the secret/service key, not the publishable one),
   `MS_REFRESH_TOKEN`, `SLACK_USER_TOKEN`. (`MS_CLIENT_ID`/`MS_TENANT_ID` only
   needed if you registered your own app instead of using the default.)
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
  notifications) into your Outlook inbox. Make sure LinkedIn message emails are
  ON: linkedin.com → Settings → Notifications → Messaging → Email. Full message
  sync would require Unipile (~€50+/month) — deliberate later upgrade after
  validation.
- **WhatsApp**: out of scope. No official personal API; bridges risk a number
  ban. Unipile covers it later if needed.
- **Re-polls never reset read state**: inserts use `ignore_duplicates`, so a
  card you marked read stays read.
- **VIPs**: rows in `vip_senders` are case-insensitive substring patterns
  matched against sender name + email/handle at poll time (e.g. `@prospect.com`).

## Can other people connect their own accounts?

Yes — that's the v2 multi-user upgrade, and it does NOT mean collecting
anyone's password (providers block password login from third-party apps, and
storing passwords would be a liability). The standard pattern, which gives
exactly the "log in with your own account" experience:

1. The app registrations created above are one-time, shared infrastructure —
   set audience to multi-tenant for Microsoft, add a redirect URL.
2. The dashboard's Connections page gets "Connect Outlook" / "Connect Slack"
   buttons → the provider's own login page opens → the user signs in normally
   (password + MFA stay with the provider) → a Supabase Edge Function receives
   the OAuth callback and stores a revocable token in `channel_auth`, keyed by
   user.
3. Pollers loop over all stored tokens instead of one set of env secrets.
   Add a `user_id` column to `notifications` + Supabase Auth in the frontend.

The only literal username/password option that exists anywhere is for LinkedIn
and WhatsApp via aggregators like Unipile (~€50+/user/month hosted credential
login) — because those have no official API at all.

## Later upgrades

- Multi-user OAuth connect flow (above).
- Teams natively via Microsoft Graph (same app registration, add Chat.Read).
- Slack channel mentions.
- LinkedIn/WhatsApp full sync via Unipile.
- LLM scoring pass ("deal reply / internal / noise") + morning digest.
