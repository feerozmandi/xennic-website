#!/usr/bin/env bash
# Disposable CI only: test the candidate boundary against the real application.
set -euo pipefail
container="xennic-public-http-${GITHUB_RUN_ID:-local}"
cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --rm --name "$container" --network host \
  -e XENNIC_PUBLIC_HOST=127.0.0.1 -e XENNIC_PUBLIC_PORT=18081 \
  -v "$PWD/config/public-readonly.Caddyfile:/etc/caddy/Caddyfile:ro" \
  caddy:2.10.2-alpine >/dev/null
TEST_BASE_URL=http://127.0.0.1:18081 node scripts/wait-for-server.mjs
base=http://127.0.0.1:18081

expect() {
  local expected=$1 method=$2 path=$3 actual
  actual=$(curl --path-as-is --silent --show-error --max-time 10 -o /dev/null -w '%{http_code}' -X "$method" "$base$path")
  if [[ $actual != "$expected" ]]; then
    echo "Unexpected HTTP status $actual: $method $path (expected $expected)" >&2
    exit 1
  fi
}

for path in / /company /company/team /services /services/energy-audit /track-record /contact; do
  expect 200 GET "$path"
done
page=$(mktemp)
trap 'rm -f "$page"; cleanup' EXIT
curl --silent --show-error --fail -o "$page" "$base/"
grep -q 'مهندسی انرژی' "$page"
asset=$(node -e "const f=require('fs').readFileSync(process.argv[1],'utf8'); const m=f.match(/\\/_next\\/static\\/[^\\\"' ?]+\\.css/); if (!m) process.exit(1); console.log(m[0])" "$page")
expect 200 GET "$asset"

# Explicitly deny login, API, uploads, unknown routes, traversal and mutations.
for path in /admin /admin/login /api/staff/login /api/graphql /api/pages /media/test \
  /oauth2/start /health /_next/image '/%61dmin' '/services/../api/staff' \
  '/_next/static/../../api/staff' /_next/staticx/test /unknown; do
  expect 404 GET "$path"
done
for method in POST PUT PATCH DELETE OPTIONS; do
  expect 404 "$method" /
  expect 404 "$method" /api/staff/login
done

headers=$(mktemp)
trap 'rm -f "$page" "$headers"; cleanup' EXIT
curl --silent --show-error --fail -o /dev/null -D "$headers" \
  -H 'Cookie: payload-token=synthetic-test-only' \
  -H 'Authorization: Bearer synthetic-test-only' "$base/"
if grep -qi '^set-cookie:' "$headers"; then
  echo 'Public HTTP boundary returned a cookie' >&2
  exit 1
fi
echo 'Public read-only HTTP boundary CI checks passed.'
