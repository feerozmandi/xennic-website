import assert from 'node:assert/strict'
import { test } from 'node:test'
import { execFileSync } from 'node:child_process'
import { APPROVED_PREVIEW_ORIGIN, previewLoginAllowed, previewOrigin } from '../src/lib/preview-security.ts'

test('preview only accepts the exact approved origin', () => {
  assert.equal(previewOrigin({ XENNIC_PREVIEW: '1', PREVIEW_ORIGIN: APPROVED_PREVIEW_ORIGIN }), APPROVED_PREVIEW_ORIGIN)
  for (const origin of [undefined, '', '*', 'http://preview.xennic.ir', 'https://evil.example', 'https://preview.xennic.ir.evil.example', 'https://preview.xennic.ir/', 'https://user@preview.xennic.ir', 'https://preview.xennic.ir:444', 'https://preview.xennic.ir/path']) {
    assert.throws(() => previewOrigin({ XENNIC_PREVIEW: '1', PREVIEW_ORIGIN: origin }))
  }
})

test('local development is separate and does not require preview origin', () => {
  assert.equal(previewOrigin({}), undefined)
  assert.equal(previewOrigin({ XENNIC_PREVIEW: '0', PREVIEW_ORIGIN: 'http://localhost:3000' }), undefined)
})

function inspectConfig(preview) {
  const script = `const { default: config } = await import('./src/payload.config.ts');
    const c = await config; const staff = c.collections.find(x => x.slug === 'staff');
    console.log(JSON.stringify({ serverURL: c.serverURL, csrf: c.csrf, cors: c.cors, cookies: staff.auth.cookies }));`
  const output = execFileSync(process.execPath, ['--import=tsx', '--input-type=module', '-e', script], {
    env: { ...process.env, XENNIC_PREVIEW: preview ? '1' : '0', PREVIEW_ORIGIN: preview ? APPROVED_PREVIEW_ORIGIN : 'http://localhost:3000', PAYLOAD_SECRET: 'test-only' },
    encoding: 'utf8',
  })
  return JSON.parse(output.trim())
}

test('sanitized Payload settings are scoped to preview and exclude other origins', () => {
  const config = inspectConfig(true)
  assert.equal(config.serverURL, APPROVED_PREVIEW_ORIGIN)
  assert.deepEqual([...new Set(config.csrf)], [APPROVED_PREVIEW_ORIGIN])
  assert.deepEqual(config.cors, [APPROVED_PREVIEW_ORIGIN])
  assert.equal(config.cookies.secure, true)
  assert.equal(config.cookies.sameSite, 'Lax')
  assert.equal(config.cookies.domain, undefined)
})

test('sanitized local development settings remain unchanged', () => {
  const config = inspectConfig(false)
  assert.equal(config.serverURL, '')
  assert.deepEqual(config.csrf, [])
  assert.deepEqual(config.cors, [])
  assert.equal(config.cookies.secure, false)
})

test('preview login checks Origin and cross-site fetch metadata without blocking headerless clients', () => {
  assert.equal(previewLoginAllowed(new Headers({ Origin: APPROVED_PREVIEW_ORIGIN })), true)
  assert.equal(previewLoginAllowed(new Headers({ Origin: 'https://untrusted.example.invalid' })), false)
  assert.equal(previewLoginAllowed(new Headers({ Origin: 'null' })), false)
  assert.equal(previewLoginAllowed(new Headers({ 'Sec-Fetch-Site': 'cross-site' })), false)
  assert.equal(previewLoginAllowed(new Headers({ 'Sec-Fetch-Site': 'same-origin' })), true)
  assert.equal(previewLoginAllowed(new Headers()), true)
})
