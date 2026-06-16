# Lovable prompt — Auth + Connections page

Paste this into Lovable's chat after the initial LOVABLE_PROMPT.md build.

---

## Step 0 — Supabase Auth setup (you do this before prompting Lovable)

In the **Supabase dashboard** → Authentication → Providers → Azure (Microsoft):

| Field | Value |
|-------|-------|
| Client ID | `bd9ded6c-52f2-426f-bb90-7a630bc1decd` |
| Client Secret | *(the value IT gave you)* |
| Azure Tenant | `49e55eb4-ecc2-4f12-8494-9c8c5c38be7f` |

Supabase will show a **Callback URL** like:
`https://rqxwdrjpkgtfooutbcgh.supabase.co/auth/v1/callback`

**Ask IT to add that URL as a second Redirect URI** on the same Azure app they registered.
The app currently has one redirect URI (the Edge Function). They just need to add this second one.
No other change needed from IT.

---

## Step 1 — Apply per-user RLS (run once, after Auth is live)

```bash
# Apply sql/006 via Supabase management API (same IPv6 workaround as before)
TOKEN=$(security find-generic-password -s "Supabase CLI" -w | sed 's/^go-keyring-base64://' | base64 -d)
curl -s -X POST "https://api.supabase.com/v1/projects/rqxwdrjpkgtfooutbcgh/database/query" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$(sed 's/"/\\"/g' sql/006_user_scoped_rls.sql | tr '\n' ' ')\"}"
```

---

## Step 2 — Lovable prompt (paste this)

```
The app uses Supabase. Project URL and publishable key are already set.
Supabase Auth is enabled with the Azure (Microsoft) provider — users sign in with their work Microsoft account.

Please make the following changes:

### 1. Authentication wrapper
- If the user is not signed in, show a centered login screen with a "Sign in with Microsoft" button.
- Call `supabase.auth.signInWithOAuth({ provider: 'azure' })` when clicked.
- If the user IS signed in, show the existing notification feed as normal.
- Add a small "Sign out" link in the top-right corner of the header (calls `supabase.auth.signOut()`).
- Show the signed-in user's email next to the sign-out link.

### 2. Connections page
Add a "Connections" item to the sidebar/navigation. The page:

**Outlook (Email)**
- Query `channel_connections` where `channel = 'email'` (own row via RLS).
- If a row exists with `status = 'ok'`: show a green "Connected" badge + a "Disconnect" button.
- "Disconnect" deletes the row: `supabase.from('channel_connections').delete().eq('channel', 'email')`
- If no row (or status ≠ ok): show a "Connect Outlook" button.

"Connect Outlook" opens this URL in the same tab (replace USER_ID at runtime with `session.user.id`):
```
https://login.microsoftonline.com/49e55eb4-ecc2-4f12-8494-9c8c5c38be7f/oauth2/v2.0/authorize?client_id=bd9ded6c-52f2-426f-bb90-7a630bc1decd&response_type=code&redirect_uri=https://rqxwdrjpkgtfooutbcgh.supabase.co/functions/v1/connect-microsoft&response_mode=query&scope=https%3A%2F%2Fgraph.microsoft.com%2FMail.Read%20offline_access&state=USER_ID
```

**Slack**
- Same pattern, query `channel_connections` where `channel = 'slack'`.
- "Connect Slack" button opens (USER_ID = session.user.id, SLACK_CLIENT_ID = env var or hardcoded below):

```
https://slack.com/oauth/v2/authorize?client_id=SLACK_CLIENT_ID&user_scope=im:history,im:read,mpim:history,mpim:read,users:read,users:read.email&redirect_uri=https://rqxwdrjpkgtfooutbcgh.supabase.co/functions/v1/connect-slack&state=USER_ID
```
(Leave SLACK_CLIENT_ID as a placeholder for now — we'll fill it in once the Slack app is set up.)

**Other channels** (WhatsApp, LinkedIn, Teams):
- Show them as "Coming soon" cards, greyed out, no button.

### 3. Success banner
When the page loads with `?connected=email` or `?connected=slack` in the URL, show a brief green toast ("Outlook connected!" / "Slack connected!") then clear the query param.

### 4. Notification feed — filter by current user
Each notification row has a `user_id` column. Filter the feed query to only show rows where `user_id = session.user.id` OR `user_id IS NULL` (the shared env-secret mailbox, visible to all until full per-user mode).
```

---

## After Lovable builds this

1. Test the login flow: open the app, click "Sign in with Microsoft", confirm you land back on the dashboard.
2. Test "Connect Outlook": you should be redirected to Microsoft login, then back to the app with `?connected=email`.
3. Confirm a row appears in `channel_connections` (Supabase → Table Editor → channel_connections).
4. The next cron run (within 10 min) will poll your mailbox and tag messages with your user_id.
5. Delete sample data: `delete from notifications where external_id like 'sample-%'`
