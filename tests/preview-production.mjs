import assert from 'node:assert/strict'
import { createHash, randomBytes } from 'node:crypto'
import { writeFile } from 'node:fs/promises'
import http from 'node:http'
import { test } from 'node:test'

const upstream = new URL(process.env.TEST_BASE_URL || 'http://127.0.0.1:3000')
const gate = randomBytes(20).toString('hex')
// Test harness only: separate proxy credential from Payload Authorization.
// This is NOT an internet-ready proxy or a selected deployment design.
const proxy = http.createServer((req, res) => {
  if (req.headers['x-test-preview-key'] !== gate) { res.writeHead(401); res.end(); return }
  const headers = { ...req.headers, host: upstream.host }
  delete headers['x-test-preview-key']
  const toApp = http.request({ hostname: upstream.hostname, port: upstream.port, path: req.url, method: req.method, headers }, fromApp => {
    res.writeHead(fromApp.statusCode, fromApp.headers); fromApp.pipe(res)
  })
  toApp.on('error', () => { res.writeHead(502); res.end() })
  req.pipe(toApp)
})
await new Promise(resolve => proxy.listen(0, '127.0.0.1', resolve))
const base = `http://127.0.0.1:${proxy.address().port}`
const request = (path, opts = {}) => fetch(`${base}${path}`, { ...opts, headers: { 'x-test-preview-key': gate, ...opts.headers }, redirect: 'manual' })
const password = randomBytes(24).toString('hex')
const email = 'ci-staff@example.invalid'
const json = { 'Content-Type': 'application/json' }

test('isolated proxy, Payload auth, media and protected paths', async () => {
  try {
    assert.equal((await fetch(`${base}/`)).status, 401)
    for (const path of ['/api/pages', '/admin', '/api/media']) assert.equal((await fetch(`${base}${path}`)).status, 401)
    let r = await request('/api/staff/first-register', { method: 'POST', headers: json, body: JSON.stringify({ name: 'CI Staff', email, password }) })
    assert.equal(r.status, 200, 'first staff registration')
    r = await request('/api/staff/first-register', { method: 'POST', headers: json, body: JSON.stringify({ name: 'Another', email: 'other@example.invalid', password }) })
    assert.notEqual(r.status, 200, 'second first-register denied')
    r = await request('/api/staff/login', { method: 'POST', headers: json, body: JSON.stringify({ email, password }) })
    assert.equal(r.status, 200, 'staff login')
    const cookieHeader = r.headers.get('set-cookie') || ''
    assert.match(cookieHeader, /HttpOnly/i)
    assert.match(cookieHeader, /SameSite=Lax/i)
    // Characterize current preview config: HTTPS Secure is not enabled yet.
    assert.doesNotMatch(cookieHeader, /(?:^|;)\s*Secure(?:;|$)/i)
    const cookie = cookieHeader.split(';')[0]
    const { token } = await r.json()
    assert.ok(cookie && token, 'session cookie and token')
    r = await request('/admin', { headers: { Cookie: cookie } })
    assert.equal(r.status, 200, 'admin with cookie')
    // Characterization, not an endorsement: empty Payload CSRF list accepts
    // cookie requests even when the Origin is not the approved preview origin.
    r = await request('/api/staff/me', { headers: { Cookie: cookie, Origin: 'https://untrusted.example.invalid' } })
    assert.equal((await r.json()).user.email, email, 'empty CSRF allowlist currently accepts foreign Origin')
    r = await request('/api/staff/me', { headers: { Cookie: cookie, Origin: 'https://preview.xennic.ir' } })
    assert.equal((await r.json()).user.email, email, 'preview Origin cookie behavior')
    r = await request('/api/staff/me', { headers: { Authorization: `Bearer ${token}` } })
    assert.equal(r.status, 200, 'Payload Bearer header survives proxy')
    assert.equal((await r.json()).user.email, email)
    r = await request('/api/staff/me', { headers: { Authorization: 'Basic dGVzdDp0ZXN0' } })
    assert.equal((await r.json()).user, null, 'Basic credentials cannot also carry a Payload Bearer token')
    // Explicitly exercise the conflict at a Basic-auth gate, not merely at Payload.
    const basic = `Basic ${Buffer.from('preview:test-only').toString('base64')}`
    const basicProxy = http.createServer((req, res) => {
      if (req.headers.authorization !== basic) { res.writeHead(401); res.end(); return }
      const forward = http.request({ hostname: upstream.hostname, port: upstream.port, path: req.url, method: req.method, headers: { ...req.headers, host: upstream.host } }, fromApp => {
        res.writeHead(fromApp.statusCode, fromApp.headers); fromApp.pipe(res)
      })
      forward.on('error', () => { res.writeHead(502); res.end() })
      req.pipe(forward)
    })
    await new Promise(resolve => basicProxy.listen(0, '127.0.0.1', resolve))
    try {
      const basicBase = `http://127.0.0.1:${basicProxy.address().port}`
      let basicResponse = await fetch(`${basicBase}/api/staff/me`, { headers: { Authorization: `Bearer ${token}` } })
      assert.equal(basicResponse.status, 401, 'Basic gate rejects Payload Bearer header')
      basicResponse = await fetch(`${basicBase}/api/staff/me`, { headers: { Authorization: basic, Cookie: cookie } })
      assert.equal(basicResponse.status, 200, 'Basic gate plus Payload cookie')
      assert.equal((await basicResponse.json()).user.email, email)
    } finally { await new Promise(resolve => basicProxy.close(resolve)) }
    r = await request('/api/pages?where[slug][equals]=track-record-intro', { headers: { Authorization: `Bearer ${token}` } })
    const page = (await r.json()).docs[0]
    assert.ok(page?.id)
    r = await request(`/api/pages/${page.id}`, { method: 'PATCH', headers: { ...json, Authorization: `Bearer ${token}` }, body: JSON.stringify({ summary: 'CI edit preserved' }) })
    assert.equal(r.status, 200, 'staff CMS edit')
    const form = new FormData()
    form.set('_payload', JSON.stringify({ alt: 'CI image' }))
    form.set('file', new Blob([Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lX8AAAAASUVORK5CYII=', 'base64')], { type: 'image/png' }), 'ci.png')
    r = await request('/api/media', { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form })
    assert.equal(r.status, 201, 'media upload')
    const media = await r.json()
    assert.ok(media.doc?.url)
    r = await request(media.doc.url)
    assert.equal(r.status, 200, 'media retrieval behind proxy')
    const imageHash = createHash('sha256').update(Buffer.from(await r.arrayBuffer())).digest('hex')
    if (process.env.RESTORE_FIXTURE_PATH) {
      // CI-only synthetic values; never printed or uploaded as artifacts.
      await writeFile(process.env.RESTORE_FIXTURE_PATH, JSON.stringify({ email, password, token, cookie, mediaUrl: media.doc.url, imageHash }), { mode: 0o600 })
    }
    r = await request('/health')
    assert.equal(r.status, 200)
    assert.equal(r.headers.get('x-robots-tag'), 'noindex, nofollow')
  } finally { await new Promise(resolve => proxy.close(resolve)) }
})
