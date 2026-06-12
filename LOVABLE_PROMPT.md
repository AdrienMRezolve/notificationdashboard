# Lovable prompt — paste this into a NEW Lovable project

(Keep this frontend repo separate from the backend repo, as usual. After Lovable
generates the app, connect it to Supabase via the Lovable Supabase integration
using the PUBLISHABLE key — `sb_publishable_...`.)

---

Build a read-only "unified notification dashboard" called **Inbox radar**. It is a
personal heads-up display showing incoming messages from several channels in one
chronological feed. There is NO reply functionality anywhere — clicking a message
opens the original app in a new tab via its deep link.

## Data (already exists in Supabase — do not create tables, just read them)

Table `notifications`:
- id (uuid), channel (text: 'email' | 'slack' | 'teams' | 'linkedin' | 'whatsapp' | 'other')
- external_id, sender (display name), sender_handle (email or username)
- preview (one-line text snippet), deep_link (url, may be null)
- received_at (timestamptz), is_read (bool), is_vip (bool), created_at

Table `connections`: channel (text pk), status ('pending' | 'ok' | 'error'),
last_polled_at (timestamptz), last_error (text).

Table `vip_senders`: pattern (text pk), note (text).

The app may UPDATE only `notifications.is_read`, and INSERT/DELETE rows in
`vip_senders`. Everything else is read-only. Subscribe to Supabase Realtime on
`notifications` inserts so new cards appear live without refresh.

## Layout

Single page, light, clean, generous whitespace, no clutter:

1. **Header bar**: app name left; right side has three filter pills — "All",
   "Unread (n)", "VIP" — plus a subtle relative "last sync" time computed from
   the most recent connections.last_polled_at. "Unread" is the default filter.
2. **Left sidebar (~180px)**: channel list — All channels, Email, Slack, Teams,
   LinkedIn — each with an icon and unread count badge. Clicking filters the
   feed. Channels whose `connections.status = 'error'` show a small amber
   warning dot with the error text in a tooltip. Bottom of sidebar: "VIP senders"
   link opening a small modal to view/add/remove vip_senders patterns.
3. **Main feed**: one card per notification, newest first, max ~50 with a
   "load more" button. Each card: circular avatar with sender initials (background
   color derived from channel), sender name (+ a small pink "VIP" pill when
   is_vip), channel icon + relative timestamp on the right, one-line truncated
   preview below, and an external-link icon. Unread cards have a slightly
   stronger background; read cards are muted.

## Behavior

- Clicking a card: set is_read = true AND open deep_link in a new tab (if present).
- A small check button on each card marks read without opening the link.
- "Mark all as read" text button at the top of the feed (applies to current filter).
- Browser tab title shows the unread count, e.g. "(7) Inbox radar".
- New realtime inserts slide in at the top with a subtle highlight that fades.
- Empty state: friendly "All clear" message with a checkmark illustration.
- No auth screens needed — this is a single-user personal tool.

## Style

Minimal flat design, white background, 0.5px hairline borders, rounded-xl cards,
one accent color (indigo/violet), sans-serif. Channel colors: email = blue,
slack = teal, linkedin = purple, teams = coral. No gradients, no shadows beyond
a subtle card hover. Desktop-first but usable on mobile (sidebar collapses to a
horizontal chip row).
