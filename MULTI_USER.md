# Multi-user mode — each colleague connects their own channels

Internal Rezolve audience (same Microsoft tenant + Slack workspace). The big
win of staying internal: provider consent is granted **once for the whole org**
— no Google security audit, no public app verification.

```
Dashboard (Lovable + Supabase Auth)
  └─ "Connect Outlook" / "Connect Slack" button
       └─ provider login page (colleague's own account + MFA)
            └─ Edge Function callback  → stores token in channel_connections (per user)
                 └─ poller loops all users → notifications(user_id) → feed filtered by RLS
```

## What's already built
- `sql/005_multi_user.sql` (applied): `channel_connections` table + `user_id`
  on `notifications`, both RLS-scoped per user.
- `sql/006_user_scoped_rls.sql` (NOT yet applied): flips the feed to per-user
  reads. Apply it the moment Auth is live in the frontend.
- Pollers (`src/outlook_poller.py`, `src/slack_poller.py`) now loop over every
  per-user connection **and** the shared env-secret mailbox, tagging each
  message with its `user_id`.
- Edge Functions `supabase/functions/connect-microsoft` and `connect-slack`
  handle the OAuth callback and store per-user tokens with the service role.

## One-time setup (IT / you, the owner)

### A. Microsoft app registration (the thing you couldn't self-serve)
Ask IT to register **one** internal app in Entra ID:
- Single tenant (Rezolve only).
- Redirect URI (Web): `https://rqxwdrjpkgtfooutbcgh.supabase.co/functions/v1/connect-microsoft`
- Delegated permission **Mail.Read**, then **Grant admin consent** — this one
  click covers every colleague, so nobody hits a consent wall.
- Create a client secret.
Then: `supabase secrets set MS_CLIENT_ID=... MS_CLIENT_SECRET=... MS_TENANT_ID=<rezolve-tenant-id>`

### B. Slack app
- Reuse the app from `slack-app-manifest.yml`, add OAuth redirect URL
  `https://rqxwdrjpkgtfooutbcgh.supabase.co/functions/v1/connect-slack`.
- Workspace admin approves it once.
- `supabase secrets set SLACK_CLIENT_ID=... SLACK_CLIENT_SECRET=...`

### C. Deploy the functions
```bash
supabase functions deploy connect-microsoft --no-verify-jwt
supabase functions deploy connect-slack --no-verify-jwt
```

### D. Turn on Auth + per-user reads
- Enable an auth provider in Supabase (e.g. Azure/Microsoft SSO so colleagues
  sign in with their work account).
- Add a login screen in Lovable (Supabase Auth UI).
- Apply `sql/006_user_scoped_rls.sql`.

## Frontend: the Connect buttons (Lovable prompt)
Add a "Connections" page. Each button opens the provider authorize URL with
`state` set to the logged-in user's id, redirecting to the Edge Function:

- Outlook:
  `https://login.microsoftonline.com/<tenant>/oauth2/v2.0/authorize?client_id=<MS_CLIENT_ID>&response_type=code&redirect_uri=https://rqxwdrjpkgtfooutbcgh.supabase.co/functions/v1/connect-microsoft&response_mode=query&scope=https://graph.microsoft.com/Mail.Read%20offline_access&state=<USER_ID>`
- Slack:
  `https://slack.com/oauth/v2/authorize?client_id=<SLACK_CLIENT_ID>&user_scope=im:history,im:read,mpim:history,mpim:read,users:read,users:read.email&redirect_uri=https://rqxwdrjpkgtfooutbcgh.supabase.co/functions/v1/connect-slack&state=<USER_ID>`

The page also reads `channel_connections` (own rows, via RLS) to show which
channels are connected and offer a "Disconnect" (delete) button.

> Hardening note (POC uses the simple version): `state` currently carries the
> raw user id. For production, pass the Supabase JWT in `state` and verify it in
> the Edge Function so a connection can't be attached to someone else's id.

## Channels that DON'T fit multi-user OAuth
- **WhatsApp / LinkedIn**: no per-user OAuth. Self-hosting Matrix bridges per
  colleague doesn't scale — this is where **Unipile** (~€50/user/mo, hosted
  per-user login) is the realistic answer. Keep them out of the internal MVP.
- **Teams**: same Microsoft app can add `Chat.Read` later (admin consent again),
  but start with email-notification parsing.

## Scale note
The GitHub Actions cron looping over all users is fine for a team. Past a few
dozen users (token refresh volume, Slack rate limits, 10-min granularity), move
the pollers to an always-on worker or scheduled Edge Functions.
