import assert from 'node:assert/strict'
import { test } from 'node:test'
import { execFileSync } from 'node:child_process'
import { APPROVED_APEX_ORIGIN, APPROVED_PREVIEW_ORIGIN, previewLoginAllowed, previewOrigin } from '../src/lib/preview-security.ts'

test('preview only accepts an exact approved HTTPS origin', () => {
  for (const allowed of [APPROVED_PREVIEW_ORIGIN, APPROVED_APEX_ORIGIN]) {
    assert.equal(previewOrigin({ XENNIC_PREVIEW: '1', PREVIEW_ORIGIN: allowed }), allowed)
  }
  for (const origin of [undefined, '', '*', 'http://preview.xennic.ir', 'http://xennic.ir', 'https://www.xennic.ir', 'https://xennic.ir/', 'https://user@xennic.ir', 'https://xennic.ir:444', 'https://xennic.ir/path', 'https://evil.example', 'https://preview.xennic.ir.evil.example', 'https://preview.xennic.ir/', 'https://user@preview.xennic.ir', 'https://preview.xennic.ir:444', 'https://preview.xennic.ir/path']) {
    assert.throws(() => previewOrigin({ XENNIC_PREVIEW: '1', PREVIEW_ORIGIN: origin }))
  }
})

test('local development is separate and does not require preview origin', () => {
  assert.equal(previewOrigin({}), undefined)
  assert.equal(previewOrigin({ XENNIC_PREVIEW: '0', PREVIEW_ORIGIN: 'http://localhost:3000' }), undefined)
})

function inspectConfig(preview, origin = APPROVED_PREVIEW_ORIGIN) {
  const script = `const { default: config } = await import('./src/payload.config.ts');
    const c = await config; const staff = c.collections.find(x => x.slug === 'staff');
    console.log(JSON.stringify({ serverURL: c.serverURL, csrf: c.csrf, cors: c.cors, cookies: staff.auth.cookies }));`
  const output = execFileSync(process.execPath, ['--import=tsx', '--input-type=module', '-e', script], {
    env: { ...process.env, XENNIC_PREVIEW: preview ? '1' : '0', PREVIEW_ORIGIN: preview ? origin : 'http://localhost:3000', PAYLOAD_SECRET: 'test-only' },
    encoding: 'utf8',
  })
  return JSON.parse(output.trim())
}

test('sanitized Payload settings use only the selected approved origin', () => {
  for (const origin of [APPROVED_PREVIEW_ORIGIN, APPROVED_APEX_ORIGIN]) {
    const config = inspectConfig(true, origin)
    assert.equal(config.serverURL, origin)
    assert.deepEqual([...new Set(config.csrf)], [origin])
    assert.deepEqual(config.cors, [origin])
    assert.equal(config.cookies.secure, true)
    assert.equal(config.cookies.sameSite, 'Lax')
    assert.equal(config.cookies.domain, undefined)
  }
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
  assert.equal(previewLoginAllowed(new Headers({ Origin: APPROVED_APEX_ORIGIN }), APPROVED_PREVIEW_ORIGIN), false)
  assert.equal(previewLoginAllowed(new Headers({ Origin: APPROVED_PREVIEW_ORIGIN }), APPROVED_APEX_ORIGIN), false)
  assert.equal(previewLoginAllowed(new Headers({ Origin: APPROVED_APEX_ORIGIN }), APPROVED_APEX_ORIGIN), true)
  assert.equal(previewLoginAllowed(new Headers(), 'http://xennic.ir'), false)
  assert.equal(previewLoginAllowed(new Headers({ 'Sec-Fetch-Site': 'cross-site' })), false)
  assert.equal(previewLoginAllowed(new Headers({ 'Sec-Fetch-Site': 'same-origin' })), true)
  assert.equal(previewLoginAllowed(new Headers()), true)
})
