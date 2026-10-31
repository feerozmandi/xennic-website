#!/usr/bin/env bash
# Independent, loopback-only GitHub OAuth + real Payload lab; not a deployment.
# Uses the prior disposable app IMAGE only; never mounts or starts its DB/volumes.
set -Eeuo pipefail
umask 077

OLD_PROJECT=xennic-gate-lab-9eb37be47536
OLD_ROOT="$HOME/xennic-preview-lab.OcRYuXI8"
BASELINE=418de2b5b3a272e79a824ccde5411dc25f1002cc
BUNDLE_NAME=xennic-preview-gate-delivery-2026-10-31-v1.1.2
ZIP_SHA=63f6f07ae46ed05494d8caff10f84e2b4755fd901bdf30d1c648fcda3e6d760c
CADDY='caddy:2.11.7@sha256:36c24ad91a7ff7bc4c87fe22bfa8df3c4b18da0773d73fc12ee2c52b98c0bb7e'
GATE='quay.io/oauth2-proxy/oauth2-proxy:v7.15.5@sha256:8498b0d0ef0a7b29686414000a08aee467f02d0299c9ed1e006a8f33fc017916'
POSTGRES='postgres:16.14-bookworm@sha256:64154d0babcb1741988719e703419af0382b19953706149f9872fbd0f438efa8'
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
step=preflight
ROOT=''
PROJECT=''
STARTED=0
FIREFOX_PID=''

compose() {
  docker compose --project-directory "$ROOT" --env-file "$ROOT/lab.env" -p "$PROJECT" -f "$ROOT/compose.yml" "$@"
}
cleanup() {
  local status=$?
  trap - EXIT INT TERM
  if [[ -n "$FIREFOX_PID" ]] && kill -0 "$FIREFOX_PID" 2>/dev/null; then
    kill "$FIREFOX_PID" 2>/dev/null || true
    wait "$FIREFOX_PID" 2>/dev/null || true
  fi
  if (( STARTED )); then
    echo 'Stopping only the new local OAuth lab; its new named volumes are retained.'
    if ! compose down >/dev/null 2>&1; then
      echo 'STOP: lab shutdown failed; inspect only the printed project.'
      status=1
    fi
  fi
  if [[ -n "$ROOT" ]]; then
    # Created only in this new private mktemp directory, never in an existing profile.
    rm -f -- "$ROOT/oauth.toml" "$ROOT/effective.json"
    if [[ -d "$ROOT/firefox-profile" && ! -L "$ROOT/firefox-profile" ]]; then
      rm -rf -- "$ROOT/firefox-profile"
    fi
  fi
  if (( status )); then echo "STOP: $step (exit $status). Later steps were not run."
  else echo 'Lab stopped. No OAuth or browser result is implied by this message.'; fi
  [[ -z "$PROJECT" ]] || echo "Lab project: $PROJECT"
  [[ -z "$ROOT" ]] || echo "Private lab directory retained: $ROOT"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for cmd in docker python3 git unzip sha256sum curl firefox; do
  command -v "$cmd" >/dev/null || { echo "STOP: missing $cmd"; exit 1; }
done
[[ $(uname -s) == Linux ]] || { echo 'STOP: Linux required'; exit 1; }
[[ -n ${DISPLAY:-}${WAYLAND_DISPLAY:-} ]] || { echo 'STOP: a desktop session is required'; exit 1; }
if [[ -n ${DOCKER_HOST:-} ]]; then host=$DOCKER_HOST; else host=$(docker context inspect "$(docker context show)" --format '{{(index .Endpoints "docker").Host}}'); fi
[[ $host == unix://* ]] || { echo 'STOP: a local Docker daemon is required'; exit 1; }
docker compose version --short >/dev/null
[[ -f "$SCRIPT_DIR/real-oauth-lab-config.py" ]] || { echo 'STOP: companion configuration helper missing'; exit 1; }
[[ -d "$OLD_ROOT" && ! -L "$OLD_ROOT" ]] || { echo 'STOP: previous isolated lab directory missing'; exit 1; }
ZIP="$OLD_ROOT/$BUNDLE_NAME.zip"
[[ -f "$ZIP" && -f "$OLD_ROOT/website/compose.preview.yml" ]] || { echo 'STOP: prior lab baseline or bundle missing'; exit 1; }
[[ $(sha256sum "$ZIP" | cut -d' ' -f1) == "$ZIP_SHA" ]] || { echo 'STOP: original bundle checksum mismatch'; exit 1; }
[[ $(git -C "$OLD_ROOT/website" rev-parse HEAD) == "$BASELINE" ]] || { echo 'STOP: old lab checkout is not the expected baseline'; exit 1; }
APP_IMAGE=$(docker image inspect "${OLD_PROJECT}-app" --format '{{.Id}}')
[[ $APP_IMAGE =~ ^sha256:[0-9a-f]{64}$ ]] || { echo 'STOP: prior local app image not found'; exit 1; }

ROOT=$(mktemp -d "$HOME/xennic-real-oauth-lab.XXXXXXXX")
PROJECT="xennic-real-oauth-$(python3 -c 'import secrets; print(secrets.token_hex(6))')"
for type in ps volume network; do
  case "$type" in
    ps) existing=$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT");;
    volume) existing=$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT");;
    network) existing=$(docker network ls -q --filter "label=com.docker.compose.project=$PROJECT");;
  esac
  [[ -z "$existing" ]] || { echo 'STOP: lab project name collision'; exit 1; }
done
printf 'New private lab project: %s\n' "$PROJECT"
printf 'New private lab directory: %s\n' "$ROOT"
echo 'The previous app image is reused by local image ID; previous databases and media are NOT mounted.'

step='prepare reviewed Caddy files and isolated settings'
for file in Caddyfile.payload.lab routes.caddy oauth-gateway.caddy upstream.caddy; do
  unzip -p "$ZIP" "$BUNDLE_NAME/$file" > "$ROOT/$file"
done
python3 - "$ROOT/lab.env" "$APP_IMAGE" "$(id -u)" "$(id -g)" <<'PY'
import os, secrets, sys
password = secrets.token_hex(32)
values = {
    'APP_IMAGE': sys.argv[2], 'LAB_UID': sys.argv[3], 'LAB_GID': sys.argv[4],
    'DB_PASSWORD': password,
    'DATABASE_URL': 'postgresql://xennic_lab:' + password + '@postgres:5432/xennic_lab',
    'PAYLOAD_SECRET': secrets.token_urlsafe(48),
}
fd = os.open(sys.argv[1], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as f:
    for k, v in values.items(): f.write(k + '=' + v + '\n')
PY
cat > "$ROOT/compose.yml" <<EOF
services:
  postgres:
    image: $POSTGRES
    environment:
      POSTGRES_DB: xennic_lab
      POSTGRES_USER: xennic_lab
      POSTGRES_PASSWORD: \${DB_PASSWORD:?required}
    volumes: ["db:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U xennic_lab -d xennic_lab"]
      interval: 5s
      timeout: 5s
      retries: 12
    networks: [backend]
    mem_limit: 256m
  app:
    image: \${APP_IMAGE:?required}
    environment:
      DATABASE_URL: \${DATABASE_URL:?required}
      PAYLOAD_SECRET: \${PAYLOAD_SECRET:?required}
      PREVIEW_ORIGIN: https://preview.xennic.ir
    volumes: ["media:/app/media"]
    depends_on:
      postgres: {condition: service_healthy}
    networks: [backend]
    mem_limit: 512m
  caddy:
    image: $CADDY
    ports: ["127.0.0.1:443:443/tcp"]
    environment:
      GATE_ADDR: gate:4180
      APP_ADDR: app:3000
      PUBLIC_AUTHORITY: preview.xennic.ir
    volumes:
      - ./Caddyfile.payload.lab:/etc/caddy/Caddyfile:ro
      - ./routes.caddy:/etc/caddy/routes.caddy:ro
      - ./oauth-gateway.caddy:/etc/caddy/oauth-gateway.caddy:ro
      - ./upstream.caddy:/etc/caddy/upstream.caddy:ro
      - caddy_data:/data
    networks: [frontend, backend, auth]
    # Callback URLs can contain OAuth codes. Do not persist proxy request/error logs.
    logging: {driver: none}
    mem_limit: 96m
  gate:
    image: $GATE
    user: "\${LAB_UID:?required}:\${LAB_GID:?required}"
    command: ["--config=/run/private/oauth.toml"]
    volumes: ["./oauth.toml:/run/private/oauth.toml:ro"]
    networks: [auth, egress]
    logging: {driver: none}
    mem_limit: 128m
networks:
  frontend: {}
  backend: {internal: true}
  auth: {internal: true}
  egress: {}
volumes:
  db: {}
  media: {}
  caddy_data: {}
EOF
# Placeholder exists before Caddy starts, but contains no credentials; it is removed
# before the exclusive creation of the actual config. Gate is not started yet.
: > "$ROOT/oauth.toml"
compose config --quiet
compose config --format json > "$ROOT/effective.json"
python3 - "$ROOT/effective.json" <<'PY'
import json, sys
c = json.load(open(sys.argv[1]))
s = c['services']
for name in ('app', 'postgres', 'gate'):
    assert not s[name].get('ports'), 'unexpected published port on ' + name
for name, expected in {'postgres': {'backend'}, 'app': {'backend'},
                       'caddy': {'frontend', 'backend', 'auth'}, 'gate': {'auth', 'egress'}}.items():
    assert set(s[name].get('networks', {})) == expected, 'unexpected network on ' + name
for name in ('backend', 'auth'):
    assert c['networks'][name].get('internal'), 'network is not internal: ' + name
ports = s['caddy'].get('ports', [])
assert len(ports) == 1 and ports[0]['host_ip'] == '127.0.0.1' and str(ports[0]['published']) == '443' and ports[0]['target'] == 443
assert s['gate']['logging']['driver'] == 'none' and s['caddy']['logging']['driver'] == 'none'
print('PASS: new Compose isolation and loopback-only Caddy port')
PY
rm -f "$ROOT/effective.json"

step='start new empty database and migrate'
STARTED=1
compose up -d --no-build --wait postgres
compose run --rm --no-deps app npm run preview:migrate
STATE=$(compose exec -T postgres sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT (to_regclass('\''website.payload_migrations'\'') IS NOT NULL AND to_regclass('\''shared.customers'\'') IS NOT NULL AND EXISTS (SELECT 1 FROM website.payload_migrations WHERE name = '\''20261030_163225_baseline'\'' AND batch >= 0) AND NOT EXISTS (SELECT 1 FROM website.payload_migrations WHERE batch = -1) AND NOT EXISTS (SELECT 1 FROM website.staff) AND NOT EXISTS (SELECT 1 FROM website.pages));"')
[[ $STATE == t ]] || { echo 'STOP: new database migration/empty-state precondition failed'; exit 1; }
echo 'PASS: new database migrated; Staff and pages are empty'
step='seed only new empty lab database'
compose run --rm --no-deps app npm run preview:seed
step='start app and Caddy on loopback'
compose up -d --no-build --wait app caddy
caddy_id=$(compose ps -q caddy)
[[ -n $caddy_id ]] || { echo 'STOP: Caddy missing'; exit 1; }
for service in app postgres caddy; do
  id=$(compose ps -q "$service")
  docker inspect --format '{{json .HostConfig.PortBindings}} {{json .NetworkSettings.Ports}}' "$id" | python3 -c '
import json,sys
service=sys.argv[1]; text=sys.stdin.read(); decoder=json.JSONDecoder()
configured,end=decoder.raw_decode(text); actual=json.loads(text[end:].strip())
for name,ports in (("configured",configured or {}),("actual",actual or {})):
    bound=[(port,b) for port,bindings in ports.items() for b in (bindings or [])]
    if service=="caddy":
        if len(bound)!=1 or bound[0][0]!="443/tcp" or bound[0][1].get("HostIp")!="127.0.0.1" or bound[0][1].get("HostPort")!="443":
            raise SystemExit("STOP: unexpected " + name + " Caddy binding")
    elif bound: raise SystemExit("STOP: unexpected " + name + " binding on " + service)
print("PASS: actual and configured port bindings", service)
' "$service"
done
AUTH_NETWORK="${PROJECT}_auth"
CADDY_IP=$(docker inspect --format "{{(index .NetworkSettings.Networks \"$AUTH_NETWORK\").IPAddress}}" "$caddy_id")
python3 - "$CADDY_IP" <<'PY'
import ipaddress, sys
ip=ipaddress.ip_address(sys.argv[1]); assert ip.version == 4 and ip.is_private
PY
step='create local OAuth config via hidden terminal prompts'
rm "$ROOT/oauth.toml"
python3 "$SCRIPT_DIR/real-oauth-lab-config.py" "$ROOT/oauth.toml" "$CADDY_IP"
step='start real OAuth2 Proxy'
compose up -d --no-build gate
id=$(compose ps -q gate)
docker inspect --format '{{json .HostConfig.PortBindings}} {{json .NetworkSettings.Ports}}' "$id" | python3 -c '
import json,sys
text=sys.stdin.read(); decoder=json.JSONDecoder(); configured,end=decoder.raw_decode(text); actual=json.loads(text[end:].strip())
assert not any((configured or {}).values()) and not any((actual or {}).values()), "unexpected gate port"
print("PASS: gate has no published ports")
'
step='validate local TLS and unauthenticated gate'
# Caddy generates its lab CA during startup. Wait only for this new container.
for _ in {1..30}; do
  if docker cp "$caddy_id:/data/caddy/pki/authorities/local/root.crt" "$ROOT/lab-root.crt" 2>/dev/null; then break; fi
  sleep 1
done
[[ -s "$ROOT/lab-root.crt" ]] || { echo 'STOP: local Caddy CA missing'; exit 1; }
python3 - "$ROOT/lab-root.crt" <<'PY'
import subprocess, sys, time
ca=sys.argv[1]
checks=[('/',302),('/admin',302),('/api/staff/me',401),('/api/graphql',401),('/api/media/file/missing',401)]
for path, expected in checks:
    result = None
    for _ in range(30):
        p=subprocess.run(['curl','--silent','--show-error','--max-time','3','--noproxy','*',
                          '--resolve','preview.xennic.ir:443:127.0.0.1','--cacert',ca,
                          '--output','/dev/null','--write-out','%{http_code}',
                          'https://preview.xennic.ir'+path], capture_output=True, text=True)
        if p.returncode == 0 and p.stdout == str(expected): result=expected; break
        time.sleep(1)
    if result != expected:
        raise SystemExit('STOP: local TLS or unauthenticated route check failed: '+path)
    print('PASS: unauthenticated '+path+' HTTP '+str(expected))
PY

step='open dedicated Firefox profile'
mkdir "$ROOT/firefox-profile"
cat > "$ROOT/firefox-profile/user.js" <<'EOF'
user_pref("network.dns.localDomains", "preview.xennic.ir");
user_pref("network.trr.mode", 5);
user_pref("network.proxy.type", 0);
user_pref("security.enterprise_roots.enabled", false);
user_pref("signon.rememberSignons", false);
user_pref("browser.startup.homepage", "about:blank");
EOF
printf '\nCA file to import ONLY into this new Firefox profile: %s/lab-root.crt\n' "$ROOT"
echo 'In the new Firefox window: Settings > Privacy & Security > Certificates > View Certificates > Authorities > Import.'
echo 'Select the CA above and check ONLY “Trust this CA to identify websites”. Do not import into the system or your normal profile.'
echo 'Then open https://preview.xennic.ir in that same window. Before signing in, inspect the site certificate:'
echo 'the issuer must contain “Caddy Local Authority”. If not, STOP; do not sign in.'
echo 'Use only the approved GitHub account. If GitHub asks for org access, STOP without granting it.'
echo 'Do not bypass any certificate warning. Keep this terminal and the lab Firefox window open while reporting only the outcome.'
echo 'Closing the lab Firefox window or pressing Ctrl-C stops the lab and deletes this disposable Firefox profile and private OAuth config.'
firefox --no-remote --profile "$ROOT/firefox-profile" 'about:preferences#privacy' >/dev/null 2>&1 &
FIREFOX_PID=$!
wait "$FIREFOX_PID"
FIREFOX_PID=''
step='finished browser session'
