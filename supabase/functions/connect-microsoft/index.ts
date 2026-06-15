// OAuth callback for "Connect Outlook". The frontend sends the user to
// Microsoft's authorize URL with state=<supabase user id>; Microsoft redirects
// back here with ?code; we exchange it for a refresh token and store it per
// user in channel_connections (service role).
//
// Deploy:  supabase functions deploy connect-microsoft --no-verify-jwt
// Secrets: supabase secrets set MS_CLIENT_ID=... MS_CLIENT_SECRET=... MS_TENANT_ID=...
//          (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are injected automatically)
// Redirect URI to register on the Azure app:
//   https://<project-ref>.supabase.co/functions/v1/connect-microsoft

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const TENANT = Deno.env.get("MS_TENANT_ID") ?? "organizations";
const CLIENT_ID = Deno.env.get("MS_CLIENT_ID")!;
const CLIENT_SECRET = Deno.env.get("MS_CLIENT_SECRET")!;
const SCOPE = "https://graph.microsoft.com/Mail.Read offline_access";

const APP_REDIRECT = Deno.env.get("APP_REDIRECT_URL") ?? "https://inbox-radar-unified-feed.lovable.app";

Deno.serve(async (req) => {
  const url = new URL(req.url);
  const code = url.searchParams.get("code");
  const userId = url.searchParams.get("state");
  if (!code || !userId) {
    return new Response("missing code or state", { status: 400 });
  }

  const redirectUri = `${url.origin}${url.pathname}`;
  const tokenRes = await fetch(
    `https://login.microsoftonline.com/${TENANT}/oauth2/v2.0/token`,
    {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: CLIENT_ID,
        client_secret: CLIENT_SECRET,
        grant_type: "authorization_code",
        code,
        redirect_uri: redirectUri,
        scope: SCOPE,
      }),
    },
  );
  const token = await tokenRes.json();
  if (!token.refresh_token) {
    return new Response(`token exchange failed: ${JSON.stringify(token)}`, { status: 400 });
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );
  const { error } = await supabase.from("channel_connections").upsert({
    user_id: userId,
    channel: "email",
    tokens: { refresh_token: token.refresh_token },
    status: "ok",
  });
  if (error) return new Response(`db error: ${error.message}`, { status: 500 });

  // Back to the dashboard with a success flag
  return Response.redirect(`${APP_REDIRECT}/?connected=email`, 302);
});
