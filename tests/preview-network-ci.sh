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
# This disposable app is explicitly configured for the approved apex origin.
# The installed preview stack and the outer CI app keep their own origin.
export PREVIEW_ORIGIN='https://xennic.ir'
cat > "$scratch/gate.py" <<'PY'
from http.server import BaseHTTPRequestHandler, HTTPServer
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get('Authorization'):
            self.send_response(418)  # A bearer token must never reach the gate.
        else:
            self.send_response(202 if '__Host-preview_gate=ci-valid' in self.headers.get('Cookie', '') else 401)
        self.end_headers()
    def log_message(self, *args): pass
HTTPServer(('0.0.0.0', 4180), Handler).serve_forever()
PY
cat > "$scratch/echo.py" <<'PY'
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(dict(self.headers.items())).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args): pass
HTTPServer(('0.0.0.0', 3000), Handler).serve_forever()
PY
# Exercise the candidate apex Caddyfile with a test-only internal CA. The
# runtime candidate itself has no internal CA and is not installed by this test.
python3 - "$PWD/config/apex-Caddyfile" "$scratch/apex-Caddyfile" <<'PY'
import pathlib, sys
candidate = pathlib.Path(sys.argv[1]).read_text()
site = 'https://xennic.ir {\n'
if candidate.count(site) != 1 or 'tls internal' in candidate:
    raise SystemExit('unexpected apex candidate')
pathlib.Path(sys.argv[2]).write_text(candidate.replace(site, site + '    tls internal\n', 1))
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
  # Disposable header-policy fixture: this does not enable a real apex listener.
  caddy-apex:
    image: caddy:2.11.7@sha256:36c24ad91a7ff7bc4c87fe22bfa8df3c4b18da0773d73fc12ee2c52b98c0bb7e
    environment:
      GATE_ADDR: gate:4180
      APP_ADDR: echo:3000
      PUBLIC_AUTHORITY: xennic.ir
    volumes:
      - $PWD/config/preview-Caddyfile:/etc/caddy/Caddyfile:ro
      - $PWD/config/routes.caddy:/etc/caddy/routes.caddy:ro
      - $PWD/config/oauth-gateway.caddy:/etc/caddy/oauth-gateway.caddy:ro
      - $PWD/config/upstream.caddy:/etc/caddy/upstream.caddy:ro
    networks: [gateway, auth]
  caddy-apex-app:
    image: caddy:2.11.7@sha256:36c24ad91a7ff7bc4c87fe22bfa8df3c4b18da0773d73fc12ee2c52b98c0bb7e
    environment:
      GATE_ADDR: gate:4180
      APP_ADDR: app:3000
      PUBLIC_AUTHORITY: xennic.ir
    volumes:
      - $scratch/apex-Caddyfile:/etc/caddy/Caddyfile:ro
      - $PWD/config/routes.caddy:/etc/caddy/routes.caddy:ro
      - $PWD/config/oauth-gateway.caddy:/etc/caddy/oauth-gateway.caddy:ro
      - $PWD/config/upstream.caddy:/etc/caddy/upstream.caddy:ro
    networks: [gateway, auth]
  echo:
    image: python:3.12.8-alpine@sha256:ba13ef990f6e5d13014e9e8d04c02a8fdb0fe53d6dccf6e19147f316e6cc3a84
    command: ['python', '/fixture/echo.py']
    volumes: ['$scratch/echo.py:/fixture/echo.py:ro']
    networks: [gateway]
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
    (gate, 'caddy-apex', {app + '_gateway', gate + '_auth'}),
    (gate, 'caddy-apex-app', {app + '_gateway', gate + '_auth'}),
    (gate, 'echo', {app + '_gateway'}),
):
    item = inspect(project, service)
    host, net = item['HostConfig'], item['NetworkSettings']
    if host.get('NetworkMode') == 'host' or host.get('PublishAllPorts') or host.get('PortBindings') or any((net.get('Ports') or {}).values()):
        raise RuntimeError('fixture service published a host port')
    if set(net['Networks']) != networks: raise RuntimeError('fixture network is not isolated')
print('PASS: app, database, Caddy and synthetic gate have no host ports and use only exact fixture networks')
PY
if ! "${app[@]}" exec -T app node - <<'JS'
(async () => {
  // Node fetch normalizes Host to the URL authority, so use http.request to
  // test Caddy's actual host matcher rather than an ignored Host override.
  const http = require('node:http');
  const call = (path, cookie, host = 'preview.xennic.ir', method = 'GET') => new Promise((resolve, reject) => {
    const req = http.request({hostname:'caddy', port:8080, path, method, headers:{
      Host:host, ...(cookie ? {Cookie:cookie} : {})}}, response => {
      const chunks=[]; response.on('data', chunk => chunks.push(chunk));
      response.on('end', () => resolve({status:response.statusCode, headers:new Headers(response.headers),
        text:async () => Buffer.concat(chunks).toString('utf8')}));
      response.on('error', reject);
    });
    req.setTimeout(10000, () => req.destroy(new Error('fixture request timeout')));
    req.on('error', reject); req.end();
  });
  const page = await call('/');
  if (page.status !== 302) throw Error('missing session did not block page');
  const api = await call('/api/pages');
  if (api.status !== 401) throw Error('missing session did not block API');
  const authorized = await call('/', '__Host-preview_gate=ci-valid');
  if (authorized.status !== 200) throw Error('authorized request did not reach app');
  const html = await authorized.text();
  if (!html.includes('<html')) throw Error('app HTML missing');
  // Both editions are public, and so are the files the rendered pages load.
  // A page that reaches the visitor while its picture does not is a defect, so
  // the optimizer, the public brand and image folders and the crawl files are
  // asserted beside the pages themselves.
  const publicPages = ['/', '/company', '/company/about', '/company/team', '/services',
    '/services/industrial-electrical-consulting', '/services/building-electrical-design',
    '/services/distribution-supervision', '/services/energy-audit',
    '/services/grounding-lightning-protection', '/services/technical-training',
    '/track-record', '/knowledge', '/tools', '/platform', '/contact', '/privacy', '/terms', '/cookies',
    '/en', '/en/company', '/en/company/team', '/en/services',
    '/en/services/industrial-electrical-consulting', '/en/services/energy-audit',
    '/en/track-record', '/en/knowledge', '/en/tools', '/en/platform', '/en/contact',
    '/en/privacy', '/en/terms', '/en/cookies',
    '/robots.txt', '/sitemap.xml', '/images/hero-grid-solar.webp', '/brand/og-cover.png',
    '/icon.png', '/apple-icon.png', '/_next/image?url=%2Fimages%2Fhero-grid-solar.webp&w=640&q=75'];
  let publicHtml = '';
  for (const path of publicPages) {
    const result = await call(path, null, 'xennic.ir');
    if (result.status !== 200) throw Error('public page not reachable: ' + path + ' ' + result.status + ' location=' + result.headers.get('location'));
    if (path === '/') publicHtml = await result.text();
    // The image optimizer answers GET only; every other public path must
    // serve HEAD as well, because that is what crawlers and proxies send.
    if (!path.startsWith('/_next/image') &&
        (await call(path, null, 'xennic.ir', 'HEAD')).status !== 200) throw Error('public HEAD blocked: ' + path);
  }
  const assetPath = publicHtml.match(/\/_next\/static\/[^"'?\s<>]+/)?.[0];
  if (!assetPath || (await call(assetPath, null, 'xennic.ir')).status !== 200) throw Error('rendered static asset not reachable');
  const staticAsset = await call('/_next/static/nonexistent.js', null, 'xennic.ir');
  if (![200, 404].includes(staticAsset.status)) throw Error('static route blocked unexpectedly');
  for (const path of ['/admin', '/en/admin', '/media/missing.png', '/health', '/unknown', '/services/unknown']) {
    const result = await call(path, null, 'xennic.ir');
    if (result.status !== 302) throw Error('private path was not gated: ' + path);
  }
  if ((await call('/api/pages', null, 'xennic.ir')).status !== 401) throw Error('API was not gated');
  if ((await call('/api/graphql', null, 'xennic.ir', 'POST')).status !== 401) throw Error('GraphQL was not gated');
  if ((await call('/', null, 'xennic.ir', 'POST')).status !== 302) throw Error('public POST was not gated');
  if ((await call('/', null, 'www.xennic.ir')).status !== 302) throw Error('unapproved host was not gated');
  for (const path of ['/services/%2e%2e/admin', '/_next/static/%2e%2e/%2e%2e/admin', '/services%2f..%2fadmin']) {
    const status = await new Promise((resolve, reject) => {
      const req = http.request({hostname:'caddy', port:8080, path, method:'GET', headers:{Host:'xennic.ir'}},
        response => { response.resume(); resolve(response.statusCode); });
      req.on('error', reject); req.end();
    });
    if (![302, 400, 404].includes(status)) throw Error('encoded path escaped gate');
  }
  // A separate Caddy points at a synthetic header-echo app and an explicit apex
  // authority. This checks header handling, not the installed preview settings.
  const echo = (path, headers) => new Promise((resolve, reject) => {
    const req = http.request({hostname:'caddy-apex', port:8080, path, headers:{Host:'xennic.ir', ...headers}}, response => {
      const chunks=[]; response.on('data', chunk => chunks.push(chunk));
      response.on('end', () => resolve({status:response.statusCode, body:Buffer.concat(chunks).toString()}));
      response.on('error', reject);
    });
    req.setTimeout(10000, () => req.destroy(new Error('header fixture timeout')));
    req.on('error', reject); req.end();
  });
  const forwarded = await echo('/api/staff/me', {
    Cookie:'payload-token=ci-payload; __Host-preview_gate=ci-valid; other=keep',
    Authorization:'Bearer ci-payload-token', Origin:'https://xennic.ir',
    'X-Forwarded-User':'forged', 'X-Auth-Request-User':'forged', 'X-Forwarded-Host':'evil.example'
  });
  if (forwarded.status !== 200) throw Error('authorized API or bearer separation failed: ' + forwarded.status);
  const received = Object.fromEntries(Object.entries(JSON.parse(forwarded.body)).map(([k,v]) => [k.toLowerCase(), v]));
  if (received.host !== 'xennic.ir' || received['x-forwarded-host'] !== 'xennic.ir' ||
      received['x-forwarded-proto'] !== 'https' || received.origin !== 'https://xennic.ir' ||
      received.authorization !== 'Bearer ci-payload-token') throw Error('upstream authority, origin or bearer incorrect');
  if (received['x-forwarded-user'] || received['x-auth-request-user']) throw Error('forged identity forwarded');
  if (!received.cookie?.includes('payload-token=ci-payload') || !received.cookie?.includes('other=keep') ||
      received.cookie?.includes('__Host-preview_gate')) throw Error('gate cookie separation failed');
  if ((await echo('/api/staff/me', {Authorization:'Bearer ci-payload-token'})).status !== 401)
    throw Error('bearer token bypassed gate');
  console.log('PASS: apex fixture header and cookie separation; OAuth and real deployment not tested');
  console.log('PASS: exact apex public routes and protected management routes; internal CI only, gate synthetic');
})().catch(e => { console.error(e.message); process.exit(1); });
JS
then
  # Disposable synthetic fixture only: show adapted matchers, not secrets or requests.
  "${gate[@]}" exec -T caddy caddy adapt --config /etc/caddy/Caddyfile --adapter caddyfile 2>/dev/null | python3 -c '
import json, sys
x=json.load(sys.stdin); found=[]
def walk(v):
    if isinstance(v,dict):
        if "match" in v: found.append(v["match"])
        for child in v.values(): walk(child)
    elif isinstance(v,list):
        for child in v: walk(child)
walk(x); print("CI_GATE_MATCHERS="+json.dumps(found,separators=(",",":"))[:4000])' || true
  exit 1
fi
# Only the disposable CA certificate is copied; its private key never leaves Caddy.
# This validates a private TLS fixture, not public ACME, DNS or VPS reachability.
fixture_ca=$("${gate[@]}" exec -T caddy-apex-app sh -c '
  for i in 1 2 3 4 5 6 7 8 9 10; do
    test -s /data/caddy/pki/authorities/local/root.crt && exec cat /data/caddy/pki/authorities/local/root.crt
    sleep 1
  done
  exit 1
')
"${app[@]}" exec -T -e "FIXTURE_CA=$fixture_ca" app node - <<'JS'
const https = require('node:https');
const http = require('node:http');
const assert = require('node:assert/strict');
const ca = process.env.FIXTURE_CA;
if (!ca?.includes('BEGIN CERTIFICATE')) throw Error('fixture CA missing');
const secure = (path, {host='xennic.ir', servername='xennic.ir', method='GET', headers={}} = {}) => new Promise((resolve, reject) => {
  const req = https.request({hostname:'caddy-apex-app', port:443, servername, ca, path, method,
    headers:{Host:host, ...headers}}, res => {
    const chunks=[]; res.on('data', x => chunks.push(x));
    res.on('end', () => resolve({status:res.statusCode, headers:res.headers, body:Buffer.concat(chunks).toString()}));
    res.on('error', reject);
  });
  req.setTimeout(10000, () => req.destroy(new Error('TLS fixture timeout')));
  req.on('error', reject); req.end();
});
const cleartext = () => new Promise((resolve, reject) => {
  const req = http.request({hostname:'caddy-apex-app', port:80, path:'/company', headers:{Host:'xennic.ir'}}, res => {
    res.resume(); resolve({status:res.statusCode, location:res.headers.location});
  });
  req.setTimeout(10000, () => req.destroy(new Error('redirect fixture timeout')));
  req.on('error', reject); req.end();
});
(async () => {
  const root = await secure('/');
  assert.equal(root.status, 200, 'public TLS page');
  assert.ok(root.body.includes('<html'), 'TLS page is not application HTML');
  assert.equal((await secure('/', {method:'HEAD'})).status, 200, 'public TLS HEAD');
  assert.equal((await secure('/admin')).status, 302, 'admin gate on TLS');
  assert.equal((await secure('/api/pages')).status, 401, 'API gate on TLS');
  assert.equal((await secure('/api/pages', {headers:{Cookie:'__Host-preview_gate=ci-valid'}})).status, 200, 'synthetic gate session on TLS');
  assert.equal((await secure('/media/missing.png')).status, 302, 'media gate on TLS');
  const foreignHost = await secure('/', {host:'unapproved.example.invalid'});
  assert.equal(foreignHost.status, 421, 'mismatched Host/SNI was not rejected: ' + foreignHost.status);
  await assert.rejects(secure('/', {servername:'unapproved.example.invalid'}), 'foreign SNI was accepted');
  const redirect = await cleartext();
  assert.equal(redirect.status, 308, 'HTTP must only redirect');
  assert.equal(redirect.location, 'https://xennic.ir/company', 'incorrect HTTPS redirect');
  console.log('PASS: isolated apex HTTPS and HTTP redirect with test CA; no public TLS or OAuth tested');
})().catch(error => { console.error(error.message); process.exit(1); });
JS
# Exercise Payload through real Caddy and the synthetic gate at apex authority.
# Credentials, data, network and database are disposable CI-only fixtures.
"${app[@]}" exec -T app node - <<'JS'
const http = require('node:http');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const origin = 'https://xennic.ir';
const gate = '__Host-preview_gate=ci-valid';
const request = (path, {method='GET', headers={}, body} = {}) => new Promise((resolve, reject) => {
  const data = body === undefined ? undefined : JSON.stringify(body);
  const req = http.request({hostname:'caddy-apex-app', port:8080, path, method,
    headers:{Host:'xennic.ir', ...(data ? {'Content-Type':'application/json','Content-Length':Buffer.byteLength(data)} : {}), ...headers}}, res => {
    const chunks=[]; res.on('data', x => chunks.push(x));
    res.on('end', () => resolve({status:res.statusCode, headers:res.headers, body:Buffer.concat(chunks).toString()}));
    res.on('error', reject);
  });
  req.setTimeout(15000, () => req.destroy(new Error('Payload fixture timeout')));
  req.on('error', reject); req.end(data);
});
(async () => {
  const email = 'apex-ci@example.invalid', password = crypto.randomBytes(24).toString('hex');
  let r = await request('/api/staff/first-register', {method:'POST', headers:{Cookie:gate, Origin:origin},
    body:{name:'Apex CI', email, password}});
  assert.equal(r.status, 200, 'synthetic Staff registration');
  r = await request('/api/staff/login', {method:'POST', headers:{Cookie:gate, Origin:'https://untrusted.example.invalid'}, body:{email,password}});
  assert.equal(r.status, 403, 'untrusted login origin');
  r = await request('/api/staff/login', {method:'POST', headers:{Cookie:gate, Origin:origin}, body:{email,password}});
  assert.equal(r.status, 200, 'trusted login origin');
  const token = JSON.parse(r.body).token;
  const payloadCookie = (r.headers['set-cookie'] || []).find(c => c.startsWith('payload-token='))?.split(';')[0];
  assert.ok(token && payloadCookie, 'Payload credentials missing');
  r = await request('/api/staff/me', {headers:{Cookie:gate, Authorization:'Bearer ' + token}});
  assert.equal(JSON.parse(r.body).user?.email, email, 'bearer passes Caddy and gate');
  r = await request('/api/staff/me', {headers:{Authorization:'Bearer ' + token}});
  assert.equal(r.status, 401, 'Payload bearer cannot bypass gate');
  r = await request('/api/staff/me', {headers:{Cookie:gate + '; ' + payloadCookie, Origin:origin}});
  assert.equal(JSON.parse(r.body).user?.email, email, 'trusted cookie survives Caddy');
  r = await request('/api/staff/me', {headers:{Cookie:gate + '; ' + payloadCookie, Origin:'https://untrusted.example.invalid'}});
  assert.equal(JSON.parse(r.body).user, null, 'untrusted cookie rejected');
  r = await request('/api/staff/me', {headers:{Cookie:gate + '; ' + payloadCookie}});
  assert.equal(JSON.parse(r.body).user, null, 'ambiguous cookie rejected');
  r = await request('/api/graphql', {method:'POST', headers:{Cookie:gate, Authorization:'Bearer ' + token, Origin:origin}, body:{query:'query { meStaff { user { email } } }'}});
  const graphql = JSON.parse(r.body);
  assert.equal(graphql.data?.meStaff?.user?.email, email, 'GraphQL bearer passes Caddy');
  console.log('PASS: apex Caddy, synthetic gate and real Payload auth; OAuth not tested');
})().catch(error => { console.error(error.message); process.exit(1); });
JS
# Exercise the exact candidate host-side probe against this disposable gateway.
# CI has not performed the real installed gateway identity checks.
python3 - "$gate_project" "$app_project" online <<'PY'
import importlib.util, json, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode = True
project, app, mode = sys.argv[1:]
cid = subprocess.check_output(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=' + project,
                               '--filter', 'label=com.docker.compose.service=caddy-apex-app'], text=True).strip()
if not cid or '\n' in cid: raise RuntimeError('missing apex fixture gateway')
item = json.loads(subprocess.check_output(['docker', 'inspect', cid]))[0]
ip = item['NetworkSettings']['Networks'][app + '_gateway']['IPAddress']
spec = importlib.util.spec_from_file_location('apex_fixed_fixture', Path('scripts/preview-fixed-operations.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
# Test-only: bind the fixture edge to the approved apex mode. The reviewed hash
# mapping itself is covered by tests/preview-installer-apex.py.
m._probe_cases = lambda authority: m.APEX_INGRESS_CASES if authority == 'xennic.ir' else ()
m.edge_authority = lambda: 'xennic.ir'
m.check_ingress_protection(ip)
print('PASS: fixed apex probe accepted expected public/private routes; fixture identity not operational acceptance')
PY
# Valid synthetic gate session must not bypass protection when the gate stops.
"${gate[@]}" stop gate
python3 - "$gate_project" "$app_project" <<'PY'
import importlib.util, json, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode = True
project, app = sys.argv[1:]
cid = subprocess.check_output(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=' + project,
                               '--filter', 'label=com.docker.compose.service=caddy-apex-app'], text=True).strip()
if not cid or '\n' in cid: raise RuntimeError('missing apex fixture gateway')
item = json.loads(subprocess.check_output(['docker', 'inspect', cid]))[0]
ip = item['NetworkSettings']['Networks'][app + '_gateway']['IPAddress']
spec = importlib.util.spec_from_file_location('apex_fixed_outage', Path('scripts/preview-fixed-operations.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.time.sleep = lambda _: None  # Faster retries only in this disposable fixture.
m._probe_cases = lambda authority: m.APEX_INGRESS_CASES
m.edge_authority = lambda: 'xennic.ir'
try:
    m.check_ingress_protection(ip)
except m.Rejected:
    print('PASS: fixed apex probe rejected synthetic gate outage')
else:
    raise RuntimeError('fixed apex probe accepted gate outage')
PY
"${app[@]}" exec -T -e "FIXTURE_CA=$fixture_ca" app node - <<'JS'
const https = require('node:https');
const assert = require('node:assert/strict');
const request = (path, cookie) => new Promise((resolve, reject) => {
  const req = https.request({hostname:'caddy-apex-app', port:443, servername:'xennic.ir', ca:process.env.FIXTURE_CA,
    path, headers:{Host:'xennic.ir', ...(cookie ? {Cookie:cookie} : {})}}, res => {res.resume(); resolve(res.statusCode)});
  req.setTimeout(10000, () => req.destroy(new Error('outage fixture timeout')));
  req.on('error', reject); req.end();
});
(async () => {
  for (const cookie of [undefined, '__Host-preview_gate=ci-valid']) {
    for (const path of ['/admin', '/api/pages', '/media/missing.png'])
      assert.ok((await request(path, cookie)) >= 500, 'gate outage did not close ' + path);
  }
  assert.equal(await request('/'), 200, 'public page unavailable during synthetic gate outage');
  console.log('PASS: gate outage closed protected TLS routes even with synthetic session');
})().catch(error => { console.error(error.message); process.exit(1); });
JS
unset fixture_ca
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
