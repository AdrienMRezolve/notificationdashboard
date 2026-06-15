-- Align the email connection key with the notifications channel value.
-- The poller tags email notifications channel='email' (provider-agnostic),
-- but the connection/health row was keyed 'outlook'. Make them match so the
-- sidebar count and health dot line up.

insert into connections (channel) values ('email')
on conflict (channel) do nothing;

delete from connections where channel = 'outlook';
