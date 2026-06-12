-- Switch email channel from Gmail to Outlook + token storage for rotating
-- Microsoft refresh tokens.

insert into connections (channel) values ('outlook')
on conflict (channel) do nothing;

delete from connections where channel = 'gmail';

-- OAuth tokens per channel. RLS enabled with NO policies: invisible to the
-- publishable key — only the pollers (secret key, bypasses RLS) can touch it.
create table if not exists channel_auth (
  channel    text primary key references connections(channel) on delete cascade,
  auth       jsonb not null,
  updated_at timestamptz not null default now()
);

alter table channel_auth enable row level security;
