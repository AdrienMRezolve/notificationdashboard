-- Apply THIS one only once you enable Supabase Auth in the Lovable frontend
-- (login screen). It scopes the feed so each person sees only their own
-- notifications. Until then, leave the permissive policies from 001 in place
-- so the no-auth POC view keeps showing rows.

drop policy if exists "read notifications"   on notifications;
drop policy if exists "update notifications" on notifications;

create policy "read own notifications" on notifications
  for select using (auth.uid() = user_id);

create policy "update own notifications" on notifications
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Re-grant the column-level update (dropping the policy doesn't touch grants).
revoke update on notifications from anon, authenticated;
grant  update (is_read) on notifications to anon, authenticated;
