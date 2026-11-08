#!/usr/bin/env bash
# Disposable Actions runner only: real Caddy and app, synthetic auth (not OAuth).
set -euo pipefail
[[ ${CI:-} == true && ${GITHUB_ACTIONS:-} == true && -n ${RUNNER_TEMP:-} && ${COMPOSE_PROJECT_NAME:-} == xennic-preview-ci ]] || exit 1
app_project=xennic-network-ci
gate_project=xennic-network-gate-ci
for project in "$app_project" "$gate_project"; do
  for kind in container network volume; do
    if [[ -n $(docker "$kind" ls -q --filter "label=com.docker.compose.project=$project") ]]; then
      echo 'Refusing pre-existing disposable network fixture' >&2; exit 1
    fi
  done
done
scratch=$(mktemp -d "$RUNNER_TEMP/xennic-network.XXXXXX")
app=(docker compose -p "$app_project" -f config/preview-compose.yml)
gate=(docker compose -p "$gate_project" -f "$scratch/gateway.yml")
cleanup() {
  "${gate[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  "${app[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$scratch"
}
trap cleanup EXIT
export PREVIEW_IMAGE="${COMPOSE_PROJECT_NAME}-app"
cat > "$scratch/gate.py" <<'PY'
from http.server import BaseHTTPRequestHandler, HTTPServer
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(202 if '__Host-preview_gate=ci-valid' in self.headers.get('Cookie', '') else 401)
        self.end_headers()
    def log_message(self, *args): pass
HTTPServer(('0.0.0.0', 4180), Handler).serve_forever()
PY
cat > "$scratch/gateway.yml" <<EOF
services:
  caddy:
    image: caddy:2.11.7@sha256:36c24ad91a7ff7bc4c87fe22bfa8df3c4b18da0773d73fc12ee2c52b98c0bb7e
    environment:
      CADDY_SITE: ':8080'
      GATE_ADDR: gate:4180
      APP_ADDR: app:3000
      PUBLIC_AUTHORITY: preview.xennic.ir
    volumes:
      - $PWD/config/preview-Caddyfile:/etc/caddy/Caddyfile:ro
      - $PWD/config/routes.caddy:/etc/caddy/routes.caddy:ro
      - $PWD/config/oauth-gateway.caddy:/etc/caddy/oauth-gateway.caddy:ro
      - $PWD/config/upstream.caddy:/etc/caddy/upstream.caddy:ro
    networks: [gateway, auth]
  gate:
    image: python:3.12.8-alpine@sha256:ba13ef990f6e5d13014e9e8d04c02a8fdb0fe53d6dccf6e19147f316e6cc3a84
    command: ['python', '/fixture/gate.py']
    volumes: ['$scratch/gate.py:/fixture/gate.py:ro']
    networks: [auth]
networks:
  gateway:
    external: true
    name: ${app_project}_gateway
  auth:
    internal: true
EOF
"${app[@]}" up -d --wait postgres
"${app[@]}" run --rm --no-deps -T app npm run preview:migrate
"${app[@]}" run --rm --no-deps -T app npm run preview:seed
"${app[@]}" up -d --wait --no-build app
"${gate[@]}" up -d --wait
python3 - "$app_project" "$gate_project" <<'PY'
import json, subprocess, sys
app, gate = sys.argv[1:]
def inspect(project, service):
    cid = subprocess.check_output(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=' + project,
                                   '--filter', 'label=com.docker.compose.service=' + service], text=True).strip()
    if not cid: raise RuntimeError('missing fixture service')
    return json.loads(subprocess.check_output(['docker', 'inspect', cid]))[0]
for project, service, networks in (
    (app, 'postgres', {app + '_default'}),
    (app, 'app', {app + '_default', app + '_gateway'}),
    (gate, 'caddy', {app + '_gateway', gate + '_auth'}),
    (gate, 'gate', {gate + '_auth'}),
):
    item = inspect(project, service)
    host, net = item['HostConfig'], item['NetworkSettings']
    if host.get('NetworkMode') == 'host' or host.get('PublishAllPorts') or host.get('PortBindings') or any((net.get('Ports') or {}).values()):
        raise RuntimeError('fixture service published a host port')
    if set(net['Networks']) != networks: raise RuntimeError('fixture network is not isolated')
print('PASS: app, database, Caddy and synthetic gate have no host ports and use only exact fixture networks')
PY
"${app[@]}" exec -T app node - <<'JS'
(async () => {
  const base = 'http://caddy:8080';
  const call = (path, cookie) => fetch(base + path, {redirect: 'manual', headers: {
    Host: 'preview.xennic.ir', ...(cookie ? {Cookie: cookie} : {})}});
  const page = await call('/');
  if (page.status !== 302) throw Error('missing session did not block page');
  const api = await call('/api/pages');
  if (api.status !== 401) throw Error('missing session did not block API');
  const authorized = await call('/', '__Host-preview_gate=ci-valid');
  if (authorized.status !== 200) throw Error('authorized request did not reach app');
  const html = await authorized.text();
  if (!html.includes('<html')) throw Error('app HTML missing');
  console.log('PASS: real Caddy and real app route correctly; gate is synthetic, not OAuth');
})().catch(e => { console.error(e.message); process.exit(1); });
JS
# Run the real installed health logic over Docker's internal exec path.
python3 - "$PWD/config/preview-compose.yml" "$app_project" <<'PY'
import importlib.util, os, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('health', 'scripts/preview-internal-health.py')
h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
h.COMPOSE = ['/usr/bin/docker', 'compose', '-p', sys.argv[2], '-f', sys.argv[1]]
h.ENV = dict(os.environ)
h.check_once()
print('PASS: real internal health checks without host app port')
PY
