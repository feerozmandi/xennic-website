#!/usr/bin/env bash
# Xennic preview gate v1.1.2 — disposable synthetic local lab only.
# This does not touch VPS, DNS, existing projects, OAuth credentials or production data.
set -Eeuo pipefail
umask 077

BASELINE=418de2b5b3a272e79a824ccde5411dc25f1002cc
BUNDLE_COMMIT=ccbaaded6244fb9228fcce6cbe22c67b65f896b4
ZIP_SHA=63f6f07ae46ed05494d8caff10f84e2b4755fd901bdf30d1c648fcda3e6d760c
ZIP_NAME=xennic-preview-gate-delivery-2026-10-31-v1.1.2.zip
BUNDLE_NAME=xennic-preview-gate-delivery-2026-10-31-v1.1.2
CADDY='caddy:2.11.7@sha256:36c24ad91a7ff7bc4c87fe22bfa8df3c4b18da0773d73fc12ee2c52b98c0bb7e'
PYTHON_IMAGE='python:3.12.8-alpine@sha256:ba13ef990f6e5d13014e9e8d04c02a8fdb0fe53d6dccf6e19147f316e6cc3a84'
NODE='node:22.22.3-bookworm-slim@sha256:e21fc383b50d5347dc7a9f1cae45b8f4e2f0d39f7ade28e4eef7d2934522b752'
POSTGRES='postgres:16.14-bookworm@sha256:64154d0babcb1741988719e703419af0382b19953706149f9872fbd0f438efa8'

step='preflight'
PROJECT=''
CONTAINER=''
ROOT=''
STARTED=0
compose() {
  LAB_DIR="$BUNDLE" docker compose --project-directory "$SITE" --env-file "$ENVFILE" \
    -p "$PROJECT" -f "$SITE/compose.preview.yml" \
    -f "$BUNDLE/compose.payload-lab.override.yml" -f "$PINS" "$@"
}
cleanup() {
  local status=$?
  trap - EXIT
  if [[ -n "$CONTAINER" ]]; then docker rm "$CONTAINER" >/dev/null 2>&1 || true; fi
  if [[ -n "$ROOT" ]]; then rm -f "$ROOT/effective-private.json"; fi
  if (( STARTED )); then
    echo 'Stopping only the temporary lab project; its volumes are retained.'
    if ! compose down >/dev/null 2>&1; then
      echo 'STOP: automatic lab shutdown failed; inspect only the printed project.'
      status=1
    fi
  fi
  if (( status != 0 )); then
    echo "STOP: $step failed (exit $status). No subsequent step was run."
  else
    echo 'PASS: isolated synthetic lab completed; no real OAuth, browser, public TLS, VPS or DNS was tested.'
  fi
  [[ -z "$PROJECT" ]] || echo "Lab project: $PROJECT"
  [[ -z "$ROOT" ]] || echo "Private lab directory: $ROOT (synthetic env; do not publish)"
  exit "$status"
}
trap cleanup EXIT

for cmd in docker git curl unzip python3 sha256sum; do command -v "$cmd" >/dev/null || { echo "STOP: missing $cmd"; exit 1; }; done
[[ $(uname -s) == Linux ]] || { echo 'STOP: Linux required.'; exit 1; }
[[ $(docker info --format '{{.Architecture}}') == x86_64 ]] || { echo 'STOP: expected linux/amd64.'; exit 1; }
if [[ -n ${DOCKER_HOST:-} ]]; then host=$DOCKER_HOST; else host=$(docker context inspect "$(docker context show)" --format '{{(index .Endpoints "docker").Host}}'); fi
[[ $host == unix://* ]] || { echo 'STOP: Docker daemon must be local (unix socket).'; exit 1; }
docker compose version --short >/dev/null

ROOT=$(mktemp -d "$HOME/xennic-preview-lab.XXXXXXXX")
SITE="$ROOT/website"
BUNDLE="$ROOT/$BUNDLE_NAME"
ENVFILE="$ROOT/lab.env"
PINS="$ROOT/verified-images.yml"
PROJECT="xennic-gate-lab-$(python3 -c 'import secrets; print(secrets.token_hex(6))')"
for type in ps volume network; do
  case "$type" in
    ps) existing=$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT");;
    volume) existing=$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT");;
    network) existing=$(docker network ls -q --filter "label=com.docker.compose.project=$PROJECT");;
  esac
  [[ -z "$existing" ]] || { echo 'STOP: project name collision; no resource was changed.'; exit 1; }
done
printf 'Temporary lab project: %s\n' "$PROJECT"

step='retrieve pinned bundle and checkout'
curl --fail --silent --show-error --location \
  "https://raw.githubusercontent.com/feerozmandi/ZNNY-Xennic-Vault/$BUNDLE_COMMIT/deliverables/preview-gate-2026-10-31-v1.1.0/$ZIP_NAME" \
  -o "$ROOT/$ZIP_NAME"
printf '%s  %s\n' "$ZIP_SHA" "$ROOT/$ZIP_NAME" | sha256sum -c -
python3 - "$ROOT/$ZIP_NAME" "$BUNDLE_NAME" <<'PY'
import stat, sys, zipfile
from pathlib import PurePosixPath
with zipfile.ZipFile(sys.argv[1]) as z:
    assert z.testzip() is None
    for i in z.infolist():
        p = PurePosixPath(i.filename)
        if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] != sys.argv[2] or stat.S_ISLNK(i.external_attr >> 16):
            raise SystemExit('STOP: unexpected ZIP path or symlink')
PY
unzip -q "$ROOT/$ZIP_NAME" -d "$ROOT"
(cd "$BUNDLE" && sha256sum -c SHA256SUMS >/dev/null)
git init -q "$SITE"
git -C "$SITE" remote add origin https://github.com/feerozmandi/xennic-website.git
git -C "$SITE" fetch -q --depth 1 origin "$BASELINE"
git -C "$SITE" checkout -q --detach FETCH_HEAD
[[ $(git -C "$SITE" rev-parse HEAD) == "$BASELINE" ]] || { echo 'STOP: incorrect application commit.'; exit 1; }
[[ $(sha256sum "$SITE/compose.preview.yml" | cut -d' ' -f1) == e00963aed6cd1b6d87a27af55b71f662304097a338e519d7f286dcbc3c40918c ]] || { echo 'STOP: base Compose differs from reviewed baseline.'; exit 1; }

step='pin previously verified Node and PostgreSQL index digests'
python3 - "$SITE/Dockerfile.preview" "$NODE" "$PINS" "$POSTGRES" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1]); content = p.read_text()
old = 'FROM node:22.22.3-bookworm-slim AS '
assert content.count(old) == 2, 'Unexpected Dockerfile; stop'
p.write_text(content.replace(old, 'FROM ' + sys.argv[2] + ' AS '))
Path(sys.argv[3]).write_text('services:\n  postgres:\n    image: ' + sys.argv[4] + '\n  caddy:\n    ports: !reset []\n')
PY
printf 'Pinned index references in this disposable copy only:\n  %s\n  %s\n' "$NODE" "$POSTGRES"

step='create synthetic lab environment'
python3 - "$ENVFILE" <<'PY'
from pathlib import Path
import os, secrets, sys
password = secrets.token_hex(32)
content = '\n'.join(['PREVIEW_POSTGRES_DB=xennic_preview_lab', 'PREVIEW_POSTGRES_USER=xennic_preview_lab',
  'PREVIEW_POSTGRES_PASSWORD=' + password,
  'PREVIEW_DATABASE_URL=postgresql://xennic_preview_lab:' + password + '@postgres:5432/xennic_preview_lab',
  'PREVIEW_PAYLOAD_SECRET=' + secrets.token_urlsafe(48), 'PREVIEW_ORIGIN=https://preview.xennic.ir', 'PREVIEW_PORT=3000', ''])
fd = os.open(sys.argv[1], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as f: f.write(content)
PY

step='verify effective Compose isolation'
compose config --quiet
compose config --format json > "$ROOT/effective-private.json"
python3 - "$ROOT/effective-private.json" <<'PY'
import json, sys
with open(sys.argv[1]) as f: c = json.load(f)
s = c['services']
for name in ('app', 'postgres', 'gate', 'caddy'):
    if s[name].get('ports'): raise SystemExit('STOP: unexpected host port on ' + name)
if not c['networks']['preview_gate_lab'].get('internal'): raise SystemExit('STOP: lab network not internal')
for name in ('app', 'postgres', 'gate', 'caddy'):
    if set(s[name].get('networks', {})) != {'preview_gate_lab'}: raise SystemExit('STOP: unexpected network on ' + name)
print('PASS: merged Compose has no published ports and one internal network')
PY
rm -f "$ROOT/effective-private.json"

step='validate Caddy and synthetic cookie/routing mock'
docker pull --platform linux/amd64 "$CADDY" >/dev/null
CONTAINER=$(docker create --entrypoint caddy "$CADDY" version)
docker cp "$CONTAINER:/usr/bin/caddy" "$ROOT/caddy"
docker rm "$CONTAINER" >/dev/null
CONTAINER=''
chmod u+x "$ROOT/caddy"
mkdir -p "$ROOT/caddy-home"
HOME="$ROOT/caddy-home" XDG_DATA_HOME="$ROOT/caddy-home/data" XDG_CONFIG_HOME="$ROOT/caddy-home/config" CADDY_BIN="$ROOT/caddy" python3 "$BUNDLE/check_caddy_config.py"
HOME="$ROOT/caddy-home" XDG_DATA_HOME="$ROOT/caddy-home/data" XDG_CONFIG_HOME="$ROOT/caddy-home/config" CADDY_BIN="$ROOT/caddy" python3 "$BUNDLE/test_caddy_mock.py"

step='build exact application code with verified image pins'
compose build app
step='start isolated PostgreSQL'
STARTED=1
compose up -d --wait postgres
step='migrate disposable database'
compose run --rm --no-deps app npm run preview:migrate
step='verify migration ledger'
MIGRATION_OK=$(compose exec -T postgres sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT (to_regclass('\''website.payload_migrations'\'') IS NOT NULL AND to_regclass('\''shared.customers'\'') IS NOT NULL AND EXISTS (SELECT 1 FROM website.payload_migrations WHERE name = '\''20261030_163225_baseline'\'' AND batch >= 0) AND NOT EXISTS (SELECT 1 FROM website.payload_migrations WHERE batch = -1));"')
[[ $MIGRATION_OK == t ]] || { echo 'STOP: migration verification did not return t.'; exit 1; }
echo 'PASS: migration ledger and shared schema'

step='start disposable app, Caddy and synthetic gate'
compose up -d --wait app caddy gate
step='verify no actual or configured published ports'
for service in app postgres gate caddy; do
  id=$(compose ps -q "$service")
  [[ -n $id ]] || { echo "STOP: missing lab service $service"; exit 1; }
  docker inspect --format '{{json .HostConfig.PortBindings}} {{json .NetworkSettings.Ports}}' "$id" | python3 -c '
import json,sys
service=sys.argv[1]; line=sys.stdin.read(); decoder=json.JSONDecoder()
config,end=decoder.raw_decode(line); actual=json.loads(line[end:].strip())
for ports in (config or {}, actual or {}):
    if any(ports.values()): raise SystemExit("STOP: unexpected host port on " + service)
print("PASS: no published ports",service)
' "$service"
done
NETWORK_ID=$(docker network ls -q --filter "label=com.docker.compose.project=$PROJECT" --filter 'label=com.docker.compose.network=preview_gate_lab')
[[ $(printf '%s\n' "$NETWORK_ID" | grep -c .) == 1 ]] || { echo 'STOP: expected exactly one lab network.'; exit 1; }
step='test Payload Staff, Origin, sessions, GraphQL and media'
caddy_id=$(compose ps -q caddy)
docker cp "$caddy_id:/data/caddy/pki/authorities/local/root.crt" "$ROOT/lab-root.crt"
# Extend only a disposable test copy with both origin-less cookie cases.
python3 - "$BUNDLE/test_payload_caddy.mjs" "$ROOT/test-payload-local.mjs" <<'PY'
from pathlib import Path
import sys
source = Path(sys.argv[1]).read_text()
source = source.replace("import https from 'node:https'", "import https from 'node:https'\nimport dns from 'node:dns'")
old_lookup = '''      lookup(_host, options, cb) {
        if (options?.all) cb(null, [{address:'127.0.0.1', family:4}])
        else cb(null, '127.0.0.1', 4)
      },'''
new_lookup = "      lookup(_host, options, cb) { dns.lookup('caddy', options, cb) },"
assert source.count(old_lookup) == 1, 'Unexpected resolver source; stop'
source = source.replace(old_lookup, new_lookup)
needle = "  check(r.status === 200 && Boolean(cookieMe.user?.email), 'Payload Cookie session works through Caddy')\n"
assert source.count(needle) == 1, 'Unexpected test source; stop'
extra = '''\n  r = await request('/api/staff/me', {headers:{Cookie:payloadCookie, 'Sec-Fetch-Site':'same-origin'}})
  check(r.status === 200 && Boolean(jsonBody(r).user?.email), 'origin-less same-origin cookie request authenticates')
  r = await request('/api/staff/me', {headers:{Cookie:payloadCookie}})
  check(r.status === 200 && jsonBody(r).user === null, 'origin-less request without Fetch Metadata is not authenticated')
'''
Path(sys.argv[2]).write_text(source.replace(needle, needle + extra))
PY
printf 'Test-copy diff: resolve Caddy only inside lab network and add Origin-absent checks; source bundle unchanged.\n'
docker run --rm --network "$NETWORK_ID" --user "$(id -u):$(id -g)" \
  -e LAB_CA_FILE=/lab-root.crt -v "$ROOT/lab-root.crt:/lab-root.crt:ro" \
  -v "$ROOT/test-payload-local.mjs:/test-payload-local.mjs:ro" --entrypoint node "$NODE" /test-payload-local.mjs
step='seed approved content once in disposable database'
compose run --rm --no-deps app npm run preview:seed
step='complete'
