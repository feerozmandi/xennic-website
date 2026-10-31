#!/usr/bin/env bash
set -euo pipefail
# This script removes its disposable Compose volumes on exit. Never run it elsewhere.
if [[ "${CI:-}" != true || "${COMPOSE_PROJECT_NAME:-}" != xennic-preview-ci ]]; then
  echo 'Refusing: production preview tests require the exact disposable CI project.' >&2
  exit 1
fi
if [[ -n "${PREVIEW_TEST_IMAGE:-}" && ! "$PREVIEW_TEST_IMAGE" =~ ^ghcr\.io/feerozmandi/xennic-website@sha256:[0-9a-f]{64}$ ]]; then
  echo 'Refusing: invalid immutable website image reference.' >&2
  exit 1
fi
compose=(docker compose -f compose.preview.yml)
metrics="${RUNNER_TEMP:-/tmp}/preview-resource-measurements.txt"
export RESTORE_FIXTURE_PATH="$(mktemp "${RUNNER_TEMP:-/tmp}/preview-fixture.XXXXXX")"
chmod 600 "$RESTORE_FIXTURE_PATH"
: > "$metrics"
cleanup() { "${compose[@]}" down --volumes --remove-orphans; rm -f "$RESTORE_FIXTURE_PATH"; }
trap cleanup EXIT
if [[ -n "${PREVIEW_TEST_IMAGE:-}" ]]; then
  printf '\n--- Test the published image by digest (no rebuild) ---\n'
  docker pull --platform linux/amd64 "$PREVIEW_TEST_IMAGE"
  expected_image_id=$(docker image inspect "$PREVIEW_TEST_IMAGE" --format '{{.Id}}')
  docker tag "$PREVIEW_TEST_IMAGE" "${COMPOSE_PROJECT_NAME}-app"
  test "$(docker image inspect "${COMPOSE_PROJECT_NAME}-app" --format '{{.Id}}')" = "$expected_image_id"
  image="${COMPOSE_PROJECT_NAME}-app"
else
  printf '\n--- Build (off VPS) ---\n'
  python3 scripts/measure-preview-build.py | tee -a "$metrics"
  image=$("${compose[@]}" images -q app | head -1)
  # A build-only service may not yet exist; Compose labels the image by project/service.
  if [ -z "$image" ]; then image="${COMPOSE_PROJECT_NAME}-app"; fi
fi
docker image inspect "$image" --format 'Image size bytes: {{.Size}}' | tee -a "$metrics"
"${compose[@]}" up -d --wait postgres
printf '\n--- Migration peak sampling (docker stats, 0.2s) ---\n'
"${compose[@]}" run --name xennic-preview-ci-migrate --no-deps app npm run preview:migrate &
migration_pid=$!
while kill -0 "$migration_pid" 2>/dev/null; do docker stats --no-stream --format 'migration {{.MemUsage}}' xennic-preview-ci-migrate 2>/dev/null | tee -a "$metrics" || true; sleep 0.2; done
wait "$migration_pid"
docker rm xennic-preview-ci-migrate >/dev/null
"${compose[@]}" run --rm --no-deps app npm run preview:migrate
# An untracked existing database must not be baselined automatically.
"${compose[@]}" exec -T postgres psql -U "$PREVIEW_POSTGRES_USER" -d "$PREVIEW_POSTGRES_DB" -c 'CREATE DATABASE legacy_ci'
"${compose[@]}" exec -T postgres psql -U "$PREVIEW_POSTGRES_USER" -d legacy_ci -c 'CREATE SCHEMA shared; CREATE TABLE shared.customers (id integer); INSERT INTO shared.customers VALUES (1)'
if "${compose[@]}" run --rm --no-deps -e DATABASE_URL="postgresql://${PREVIEW_POSTGRES_USER}:${PREVIEW_POSTGRES_PASSWORD}@postgres:5432/legacy_ci" app npm run preview:migrate; then
  echo 'ERROR: untracked database was not rejected'; exit 1
fi
"${compose[@]}" exec -T postgres psql -U "$PREVIEW_POSTGRES_USER" -d legacy_ci -c 'SELECT id FROM shared.customers' | grep -q 1
"${compose[@]}" run --rm --no-deps app npm run preview:seed
"${compose[@]}" up -d --wait --no-build app
if [[ -n "${PREVIEW_TEST_IMAGE:-}" ]]; then
  actual_image_id=$(docker inspect "$("${compose[@]}" ps -q app)" --format '{{.Image}}')
  if [[ "$actual_image_id" != "$expected_image_id" ]]; then
    echo 'ERROR: running app image does not match the digest-pulled image.' >&2
    exit 1
  fi
  printf 'PASS: running app uses the image pulled by the recorded digest\n'
fi
python3 tests/preview-internal-health-ci.py
printf '\n--- Idle app and database memory ---\n'
docker stats --no-stream --format 'idle {{.Name}} {{.MemUsage}}' "$("${compose[@]}" ps -q app)" "$("${compose[@]}" ps -q postgres)" | tee -a "$metrics"
node scripts/wait-for-server.mjs
npm run test:smoke
node --test tests/preview-production.mjs &
test_pid=$!
while kill -0 "$test_pid" 2>/dev/null; do docker stats --no-stream --format 'representative {{.Name}} {{.MemUsage}}' "$("${compose[@]}" ps -q app)" "$("${compose[@]}" ps -q postgres)" | tee -a "$metrics"; sleep 0.2; done
wait "$test_pid"
"${compose[@]}" run --rm --no-deps app npm run preview:seed
node - <<'NODE'
(async()=>{const r=await fetch('http://127.0.0.1:3000/api/pages?where[slug][equals]=track-record-intro');const j=await r.json();if(j.docs[0]?.summary!=='CI edit preserved')throw Error('seed overwrote CMS edit');console.log('PASS: seed preserved CMS edit')})().catch(e=>{console.error(e.message);process.exit(1)})
NODE
"${compose[@]}" restart app
node scripts/wait-for-server.mjs
node - <<'NODE'
(async()=>{const r=await fetch('http://127.0.0.1:3000/api/media');const j=await r.json();if(!j.docs?.[0]?.url)throw Error('media missing after restart');const u=new URL(j.docs[0].url,'https://preview.xennic.ir');if(u.origin!=='https://preview.xennic.ir')throw Error('unexpected media origin');const f=await fetch('http://127.0.0.1:3000'+u.pathname+u.search);if(!f.ok)throw Error('file missing after restart');console.log('PASS: media persists after app restart')})().catch(e=>{console.error(e.message);process.exit(1)})
NODE

node tests/log-security.mjs
bash scripts/ci-restore.sh
python3 scripts/summarize-preview-metrics.py "$metrics"
