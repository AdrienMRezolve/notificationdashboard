# Matrix → Supabase spike (WhatsApp + LinkedIn adapter)

Goal: get WhatsApp and LinkedIn — the two channels with **no official personal
API** — into the dashboard without paying for Unipile (~€50+/mo). Matrix bridges
log into those networks and drop messages into "portal" rooms; the `ingester`
bot reads those rooms over the Matrix `/sync` API and writes each new message
into the same Supabase `notifications` table the rest of the dashboard uses.

```
WhatsApp ─ mautrix-whatsapp ─┐
                             ├─ Synapse (rooms) ─ ingester ─> Supabase notifications ─> Lovable UI
LinkedIn ─ mautrix-linkedin ─┘
```

It is **read-only by construction**: the ingester only ever calls `/sync` and
`/join`; it never sends a message back to WhatsApp or LinkedIn.

> This is a proof-of-life spike, not production. SQLite everywhere, single
> host. It also means running real infrastructure (4 containers) and re-auth
> when a session drops — that's the trade vs. a paid API. Don't bridge
> *corporate* accounts through it; this is for personal WhatsApp/LinkedIn.

## Prerequisites
- Docker + Docker Compose
- The `notifications` / `connections` tables already exist (main repo SQL +
  `sql/003_matrix_channels.sql`, already applied).

## Setup

```bash
cd matrix
cp .env.example .env          # fill SUPABASE_SECRET_KEY
./setup.sh                    # generates Synapse + bridge configs, prints next steps
```

### 3. Edit each bridge `config.yaml` (whatsapp/ and linkedin/)
Set, in both files:
- `homeserver.address: http://synapse:8008`
- `homeserver.domain: localhost` (or your `MATRIX_SERVER_NAME`)
- `appservice.address: http://mautrix-<bridge>:29318`
- under `bridge.permissions:` add `"@radar:localhost": admin` (your bot MXID)
- `database` → leave as the default SQLite path

Then emit each registration and wire it into Synapse:
```bash
docker compose run --rm mautrix-whatsapp     # writes whatsapp/registration.yaml
docker compose run --rm mautrix-linkedin     # writes linkedin/registration.yaml
cp whatsapp/registration.yaml synapse/whatsapp-registration.yaml
cp linkedin/registration.yaml synapse/linkedin-registration.yaml
```
Add to `synapse/homeserver.yaml`:
```yaml
app_service_config_files:
  - /data/whatsapp-registration.yaml
  - /data/linkedin-registration.yaml
```

### 4. Create the bot user + token
```bash
docker compose up -d synapse
docker compose exec synapse register_new_matrix_user -c /data/homeserver.yaml -u radar -a
curl -s -XPOST http://localhost:8008/_matrix/client/v3/login \
  -d '{"type":"m.login.password","identifier":{"type":"m.id.user","user":"radar"},"password":"YOURPASS"}'
```
Put `access_token` → `MATRIX_ACCESS_TOKEN` and `user_id` → `MATRIX_BOT_MXID` in `.env`.

### 5. Start everything and log into the networks
```bash
docker compose up -d
```
From any Matrix client (Element, logged in as `@radar`) — or via the bridges'
admin commands — start a DM with each bridge bot and authenticate:
- **WhatsApp**: message `@whatsappbot:localhost` → `login` → scan the QR with
  your phone (Linked Devices). Session persists until you unlink.
- **LinkedIn**: message `@linkedinbot:localhost` → `login` → provide the
  `li_at` cookie from a logged-in LinkedIn web session.

Once linked, the bridges backfill recent chats into portal rooms, the ingester
auto-joins them and starts pushing messages into Supabase. Watch it:
```bash
docker compose logs -f ingester
```

## How messages are mapped
- Sender MXID prefix → channel: `@whatsapp_*` → `whatsapp`, `@linkedin_*` → `linkedin`.
- Bridge control bots (`whatsappbot`, `linkedinbot`) and the bot's own messages are skipped.
- `external_id` = Matrix event id (globally unique) → re-syncs never duplicate
  or un-read a card.
- `deep_link` = a `matrix.to` link to the event (opens in Element).
- VIP flag reuses the `vip_senders` patterns from the main dashboard.

## Known limitations
- **WhatsApp** uses a linked-device web session; it drops if your phone is
  offline ~14 days or you unlink. Re-run `login`.
- **LinkedIn** is an unofficial bridge driven by web cookies — it breaks when
  LinkedIn changes their site and needs the cookie refreshed periodically.
- No outbound: replying is intentionally not implemented.
- For production: move Synapse + bridges to Postgres, put Synapse behind TLS,
  and run on an always-on host (small VPS).
