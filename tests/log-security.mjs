import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { spawnSync } from 'node:child_process'

if (process.env.CI !== 'true' || process.env.COMPOSE_PROJECT_NAME !== 'xennic-preview-ci') throw new Error('CI-only log audit')
const fixture = JSON.parse(await readFile(process.env.RESTORE_FIXTURE_PATH, 'utf8'))
const randomCanary = `CANARY_${randomBytes(18).toString('hex')}`
const badURL = `postgresql://invalid:${randomCanary}@postgres:5432/absent`
// Exercise failures and Authorization/body handling using synthetic secrets only.
await fetch('http://127.0.0.1:3000/api/staff/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'invalid@example.invalid', password: randomCanary }) })
await fetch('http://127.0.0.1:3000/api/staff/me', { headers: { Authorization: `Bearer ${randomCanary}` } })
const command = (...args) => spawnSync('docker', ['compose', '-f', 'compose.preview.yml', ...args], { encoding: 'utf8', env: process.env, maxBuffer: 8 * 1024 * 1024 })
const migration = command('run', '--rm', '--no-deps', 'app', 'npm', 'run', 'preview:migrate')
const seed = command('run', '--rm', '--no-deps', 'app', 'npm', 'run', 'preview:seed')
const failure = command('run', '--rm', '--no-deps', '-e', `DATABASE_URL=${badURL}`, 'app', 'npm', 'run', 'preview:migrate')
const logs = command('logs', '--no-color', '--no-log-prefix', 'app')
assert.equal(migration.status, 0, 'migration succeeds')
assert.equal(seed.status, 0, 'seed succeeds')
assert.notEqual(failure.status, 0, 'synthetic invalid DB URL fails')
assert.equal(logs.status, 0, 'application log captured')
const observed = [migration.stdout, migration.stderr, seed.stdout, seed.stderr, failure.stdout, failure.stderr, logs.stdout, logs.stderr].join('\n')
const canaries = [randomCanary, badURL, fixture.password, fixture.token, fixture.cookie, process.env.PREVIEW_POSTGRES_PASSWORD, process.env.PREVIEW_DATABASE_URL, process.env.PREVIEW_PAYLOAD_SECRET].filter(Boolean)
for (const value of canaries) {
  // Report index only, never a secret or raw log on failure.
  assert.ok(!observed.includes(value), `secret canary ${canaries.indexOf(value)} not present in captured logs`)
  assert.ok(!observed.includes(encodeURIComponent(value)), `encoded secret canary ${canaries.indexOf(value)} not present in captured logs`)
}
console.log('PASS: synthetic application, migration, seed and failed DB connection canaries absent from captured logs')
