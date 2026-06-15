-- Multi-user: each person connects their own accounts.
-- ADDITIVE and non-breaking: existing anon reads keep working until you turn on
-- Supabase Auth in the frontend and apply 006 to scope reads per user.

-- Tag every notification with its owner (nullable so the current single-user
-- env-secret path and the sample rows still load).
alter table notifications add column if not exists user_id uuid;
create index if not exists notifications_user_idx on notifications (user_id, received_at desc);

-- Per-user OAuth tokens, written by the connect Edge Functions (service role),
-- read by the pollers (service role). Users never see each other's tokens.
create table if not exists channel_connections (
  user_id        uuid not null,
  channel        text not null check (channel in ('email','slack','teams','linkedin','whatsapp')),
  tokens         jsonb not null,
  status         text not null default 'ok',
  last_polled_at timestamptz,
  last_error     text,
  created_at     timestamptz not null default now(),
  primary key (user_id, channel)
);

alter table channel_connections enable row level security;

-- The frontend (anon key + a logged-in user) may see and disconnect only its
-- own connections. Inserts happen server-side from the Edge Function.
create policy "own connections read"   on channel_connections
  for select using (auth.uid() = user_id);
create policy "own connections delete" on channel_connections
  for delete using (auth.uid() = user_id);
