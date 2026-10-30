#!/usr/bin/env bash
# Disposable synthetic CI only. Never a production backup procedure.
set -euo pipefail
if [[ "${CI:-}" != true || "${COMPOSE_PROJECT_NAME:-}" != xennic-preview-ci || -z "${RESTORE_FIXTURE_PATH:-}" ]]; then
  echo 'Refusing: CI-only restore test requires the exact disposable source project.' >&2; exit 1
fi
umask 077
scratch=$(mktemp -d "${RUNNER_TEMP:-/tmp}/xennic-restore.XXXXXX")
project="xennic-restore-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
source=(docker compose -p "$COMPOSE_PROJECT_NAME" -f compose.preview.yml)
restore=(env PREVIEW_POSTGRES_DB=restore_ci PREVIEW_POSTGRES_USER=restore_ci PREVIEW_POSTGRES_PASSWORD=restore-ci-only-password PREVIEW_DATABASE_URL=postgresql://restore_ci:restore-ci-only-password@postgres:5432/restore_ci PREVIEW_PORT=33001 docker compose -p "$project" -f compose.preview.yml)
cleanup_restore() { "${restore[@]}" down --volumes --remove-orphans >/dev/null || true; docker image rm "$project-app" >/dev/null 2>&1 || true; rm -rf "$scratch"; }
trap cleanup_restore EXIT
# Synthetic row verifies shared-domain data as well as Payload tables.
"${source[@]}" exec -T postgres psql -U "$PREVIEW_POSTGRES_USER" -d "$PREVIEW_POSTGRES_DB" -v ON_ERROR_STOP=1 -c "INSERT INTO shared.customers (name, source) VALUES ('CI restore fixture', 'ci-only')" >/dev/null
# No writes are in progress: database dump and media archive are made together.
"${source[@]}" exec -T postgres pg_dump -U "$PREVIEW_POSTGRES_USER" -d "$PREVIEW_POSTGRES_DB" --format=custom --no-owner --no-privileges > "$scratch/db.dump"
"${source[@]}" exec -T app tar -C /app/media -czf - . > "$scratch/media.tar.gz"
test -s "$scratch/db.dump" && test -s "$scratch/media.tar.gz"
docker tag "${COMPOSE_PROJECT_NAME}-app" "$project-app"
"${restore[@]}" up -d --wait postgres
"${restore[@]}" exec -T postgres pg_restore -U restore_ci -d restore_ci --exit-on-error --no-owner --no-privileges < "$scratch/db.dump"
"${restore[@]}" run --rm --no-deps -T --entrypoint tar app -C /app/media -xzf - < "$scratch/media.tar.gz"
"${restore[@]}" run --rm --no-deps app npm run preview:migrate
"${restore[@]}" up -d --wait app
TEST_BASE_URL=http://127.0.0.1:33001 node scripts/wait-for-server.mjs
node tests/restore-verification.mjs
"${restore[@]}" exec -T postgres psql -U restore_ci -d restore_ci -v ON_ERROR_STOP=1 -tAc "SELECT count(*) FROM shared.customers WHERE name='CI restore fixture' AND source='ci-only'" | grep -qx 1
printf 'PASS: shared customer fixture and separate DB/media restoration verified\n'
