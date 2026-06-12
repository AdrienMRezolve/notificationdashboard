#!/usr/bin/env bash
# One-time init for the Matrix spike. Idempotent: safe to re-run.
# Does the deterministic steps; the interactive ones (editing bridge configs,
# logging into WhatsApp/LinkedIn) are described in README.md and printed below.
set -euo pipefail
cd "$(dirname "$0")"

SERVER_NAME="${MATRIX_SERVER_NAME:-localhost}"

echo "==> 1/4  Generating Synapse config (if missing)"
if [ ! -f synapse/homeserver.yaml ]; then
  docker run --rm -v "$PWD/synapse:/data" \
    -e SYNAPSE_SERVER_NAME="$SERVER_NAME" -e SYNAPSE_REPORT_STATS=no \
    docker.io/matrixdotorg/synapse:latest generate
  echo "    homeserver.yaml created."
else
  echo "    already present, skipping."
fi

echo "==> 2/4  Generating bridge configs (if missing)"
for bridge in whatsapp linkedin; do
  if [ ! -f "$bridge/config.yaml" ]; then
    docker compose run --rm "mautrix-$bridge" || true   # first run writes config.yaml then exits
    echo "    $bridge/config.yaml created — EDIT IT (see README step 3)."
  else
    echo "    $bridge/config.yaml present, skipping."
  fi
done

cat <<'EOF'

==> 3/4  MANUAL: edit the two bridge config.yaml files, then generate their
         registrations and wire them into Synapse. Exact lines in README.md
         (homeserver.address: http://synapse:8008, your MXID under permissions,
         then `docker compose run --rm mautrix-<bridge>` to emit registration.yaml,
         copy each into ./synapse/, and add both under app_service_config_files
         in synapse/homeserver.yaml).

==> 4/4  Then:
         docker compose up -d synapse
         docker compose exec synapse register_new_matrix_user -c /data/homeserver.yaml -u radar -a
         # log in to get the ingester's token:
         curl -s -XPOST http://localhost:8008/_matrix/client/v3/login \
           -d '{"type":"m.login.password","identifier":{"type":"m.id.user","user":"radar"},"password":"YOURPASS"}'
         # put access_token -> MATRIX_ACCESS_TOKEN and user_id -> MATRIX_BOT_MXID in .env, then:
         docker compose up -d
EOF
