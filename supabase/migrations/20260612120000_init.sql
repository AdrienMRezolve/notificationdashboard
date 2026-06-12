-- Unified notification dashboard — initial schema
-- Run this in the Supabase SQL editor (or: supabase db push)

create table if not exists notifications (
  id          uuid primary key default gen_random_uuid(),
  channel     text not null check (channel in ('email','slack','teams','linkedin','whatsapp','other')),
  external_id text not null,
  sender      text not null,
  sender_handle text,
  preview     text,
  deep_link   text,
  received_at timestamptz not null,
  is_read     boolean not null default false,
  is_vip      boolean not null default false,
  created_at  timestamptz not null default now(),
  unique (channel, external_id)
);

create index if not exists notifications_feed_idx
  on notifications (received_at desc);

-- VIP senders: substring patterns matched (case-insensitive) against
-- "sender name + handle/email" by the pollers. e.g. 'kowalska' or '@bigprospect.com'
create table if not exists vip_senders (
  pattern text primary key,
  note    text
);

-- One row per connected channel, maintained by the pollers.
-- The UI reads this to show connection health.
create table if not exists connections (
  channel        text primary key,
  status         text not null default 'pending',  -- pending | ok | error
  last_polled_at timestamptz,
  last_error     text
);

insert into connections (channel) values ('gmail'), ('slack')
on conflict (channel) do nothing;

-- Row level security: the Lovable frontend uses the publishable (anon) key.
-- It may read everything, toggle is_read, and manage the VIP list.
-- Inserts of notifications happen only from the Python poller (secret key, bypasses RLS).

alter table notifications enable row level security;
alter table vip_senders   enable row level security;
alter table connections   enable row level security;

create policy "read notifications"   on notifications for select using (true);
create policy "update notifications" on notifications for update using (true) with check (true);
create policy "read connections"     on connections   for select using (true);
create policy "read vips"            on vip_senders   for select using (true);
create policy "insert vips"          on vip_senders   for insert with check (true);
create policy "delete vips"          on vip_senders   for delete using (true);

-- Column-level lockdown: the anon role may only ever update is_read.
revoke update on notifications from anon, authenticated;
grant  update (is_read) on notifications to anon, authenticated;

-- Live feed in the UI
alter publication supabase_realtime add table notifications;
