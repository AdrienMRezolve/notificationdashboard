// OAuth callback for "Connect Slack". The frontend sends the user to Slack's
// authorize URL with state=<supabase user id>; Slack redirects back with ?code;
// we exchange it for the user token (xoxp-...) and store it per user.
//
// Deploy:  supabase functions deploy connect-slack --no-verify-jwt
// Secrets: supabase secrets set SLACK_CLIENT_ID=... SLACK_CLIENT_SECRET=...
// Redirect URL to register on the Slack app:
//   https://<project-ref>.supabase.co/functions/v1/connect-slack
// User scopes on the Slack app: im:history im:read mpim:history mpim:read
//                               users:read users:read.email

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CLIENT_ID = Deno.env.get("SLACK_CLIENT_ID")!;
const CLIENT_SECRET = Deno.env.get("SLACK_CLIENT_SECRET")!;
const APP_REDIRECT = Deno.env.get("APP_REDIRECT_URL") ?? "https://inbox-radar-unified-feed.lovable.app";

Deno.serve(async (req) => {
  const url = new URL(req.url);
  const code = url.searchParams.get("code");
  const userId = url.searchParams.get("state");
  if (!code || !userId) {
    return new Response("missing code or state", { status: 400 });
  }

  const redirectUri = `${url.origin}${url.pathname}`;
  const tokenRes = await fetch("https://slack.com/api/oauth.v2.access", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: CLIENT_ID,
      client_secret: CLIENT_SECRET,
      code,
      redirect_uri: redirectUri,
    }),
  });
  const token = await tokenRes.json();
  // user scopes return the token under authed_user.access_token (xoxp-...)
  const userToken = token?.authed_user?.access_token;
  if (!token.ok || !userToken) {
    return new Response(`token exchange failed: ${JSON.stringify(token)}`, { status: 400 });
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );
  const { error } = await supabase.from("channel_connections").upsert({
    user_id: userId,
    channel: "slack",
    tokens: { access_token: userToken },
    status: "ok",
  });
  if (error) return new Response(`db error: ${error.message}`, { status: 500 });

  return Response.redirect(`${APP_REDIRECT}/?connected=slack`, 302);
});
