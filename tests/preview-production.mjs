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
const origin = 'https://preview.xennic.ir'
const untrusted = 'https://untrusted.example.invalid'

test('isolated proxy, Payload auth, media and protected paths', async () => {
  try {
    assert.equal((await fetch(`${base}/`)).status, 401)
    for (const path of ['/api/pages', '/admin', '/api/media']) assert.equal((await fetch(`${base}${path}`)).status, 401)
    let r = await request('/api/staff/first-register', { method: 'POST', headers: json, body: JSON.stringify({ name: 'CI Staff', email, password }) })
    assert.equal(r.status, 200, 'first staff registration')
    r = await request('/api/staff/first-register', { method: 'POST', headers: json, body: JSON.stringify({ name: 'Another', email: 'other@example.invalid', password }) })
    assert.notEqual(r.status, 200, 'second first-register denied')
    // Login is unauthenticated, so the Staff hook separately checks browser origins.
    r = await request('/api/staff/login', { method: 'POST', headers: { ...json, Origin: untrusted }, body: JSON.stringify({ email, password }) })
    assert.equal(r.status, 403, 'untrusted origin login rejected')
    assert.ok(!(r.headers.get('set-cookie') || '').includes('payload-token='), 'rejected login does not issue session')
    assert.equal(r.headers.get('access-control-allow-origin'), null, 'untrusted login response is not CORS-readable')
    r = await request('/api/staff/login', { method: 'POST', headers: { ...json, 'Sec-Fetch-Site': 'cross-site' }, body: JSON.stringify({ email, password }) })
    assert.equal(r.status, 403, 'cross-site login without Origin rejected')
    const loginMutation = 'mutation ($email: String!, $password: String!) { loginStaff(email: $email, password: $password) { token } }'
    r = await request('/api/graphql', { method: 'POST', headers: { ...json, Origin: untrusted }, body: JSON.stringify({ query: loginMutation, variables: { email, password } }) })
    const badGraphqlLogin = await r.json()
    assert.ok(!badGraphqlLogin.data?.loginStaff?.token && badGraphqlLogin.errors?.length, 'untrusted GraphQL login rejected')
    r = await request('/api/graphql', { method: 'POST', headers: { ...json, Origin: origin }, body: JSON.stringify({ query: loginMutation, variables: { email, password } }) })
    assert.ok((await r.json()).data?.loginStaff?.token, 'trusted GraphQL login')
    r = await request('/api/staff/login', { method: 'POST', headers: json, body: JSON.stringify({ email, password }) })
    assert.equal(r.status, 200, 'headerless non-browser staff login')
    const cookieHeader = r.headers.get('set-cookie') || ''
    assert.ok(/(?:^|;)\s*HttpOnly(?:=true)?(?:;|$)/i.test(cookieHeader), 'cookie HttpOnly')
    assert.ok(/(?:^|;)\s*SameSite=Lax(?:;|$)/i.test(cookieHeader), 'cookie SameSite=Lax')
    assert.ok(/(?:^|;)\s*Secure(?:=true)?(?:;|$)/i.test(cookieHeader), 'cookie Secure')
    assert.ok(/(?:^|;)\s*Path=\/(?:;|$)/i.test(cookieHeader), 'cookie Path=/')
    assert.ok(!/(?:^|;)\s*Domain=/i.test(cookieHeader), 'cookie is host-only')
    const cookie = cookieHeader.split(';')[0]
    const { token } = await r.json()
    assert.ok(cookie && token, 'session cookie and token')
    r = await request('/admin', { headers: { Cookie: cookie, 'Sec-Fetch-Site': 'same-origin' } })
    assert.equal(r.status, 200, 'admin with cookie')
    const adminHtml = await r.text()
    assert.ok(adminHtml.includes('/admin/logout') && adminHtml.includes('Dashboard'), 'authenticated admin dashboard rendered')
    for (const headers of [{ Cookie: cookie, Origin: untrusted }, { Cookie: cookie }]) {
      r = await request('/admin', { headers })
      const html = await r.text()
      assert.ok(!html.includes('/admin/logout'), 'untrusted/ambiguous admin request has no authenticated dashboard')
    }
    // Payload accepts cookie auth only for the configured Origin, or for
    // origin-less navigation carrying an allowed browser Sec-Fetch-Site value.
    for (const headers of [
      { Cookie: cookie, Origin: origin },
      { Cookie: cookie, 'Sec-Fetch-Site': 'same-origin' },
      { Cookie: cookie, 'Sec-Fetch-Site': 'same-site' },
      { Cookie: cookie, 'Sec-Fetch-Site': 'none' },
    ]) {
      r = await request('/api/staff/me', { headers })
      assert.equal((await r.json()).user?.email, email, 'legitimate cookie request')
    }
    for (const headers of [
      { Cookie: cookie, Origin: untrusted },
      { Cookie: cookie, Origin: 'null' },
      { Cookie: cookie, 'Sec-Fetch-Site': 'cross-site' },
      { Cookie: cookie },
    ]) {
      r = await request('/api/staff/me', { headers })
      assert.equal((await r.json()).user, null, 'untrusted/ambiguous cookie request')
    }
    r = await request('/api/pages', { headers: { Origin: origin } })
    assert.equal(r.headers.get('access-control-allow-origin'), origin)
    r = await request('/api/pages', { headers: { Origin: untrusted } })
    assert.equal(r.headers.get('access-control-allow-origin'), null)
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
      basicResponse = await fetch(`${basicBase}/api/staff/me`, { headers: { Authorization: basic, Cookie: cookie, Origin: origin } })
      assert.equal(basicResponse.status, 200, 'Basic gate plus Payload cookie')
      assert.equal((await basicResponse.json()).user.email, email)
    } finally { await new Promise(resolve => basicProxy.close(resolve)) }
    r = await request('/api/pages?where[slug][equals]=track-record-intro', { headers: { Authorization: `Bearer ${token}` } })
    const page = (await r.json()).docs[0]
    assert.ok(page?.id)
    for (const headers of [
      { ...json, Cookie: cookie, Origin: untrusted },
      { ...json, Cookie: cookie, 'Sec-Fetch-Site': 'cross-site' },
      { ...json, Cookie: cookie },
    ]) {
      r = await request(`/api/pages/${page.id}`, { method: 'PATCH', headers, body: JSON.stringify({ summary: 'untrusted edit' }) })
      assert.equal(r.status, 403, 'untrusted/ambiguous cookie write rejected')
    }
    r = await request(`/api/pages/${page.id}`, { method: 'PATCH', headers: { ...json, Cookie: cookie, Origin: origin }, body: JSON.stringify({ summary: 'CI edit with origin' }) })
    assert.equal(r.status, 200, 'trusted origin cookie write')
    r = await request(`/api/pages/${page.id}`, { method: 'PATCH', headers: { ...json, Cookie: cookie, 'Sec-Fetch-Site': 'same-origin' }, body: JSON.stringify({ summary: 'CI edit preserved' }) })
    assert.equal(r.status, 200, 'origin-less same-origin cookie write')
    const makeForm = () => {
      const form = new FormData()
      form.set('_payload', JSON.stringify({ alt: 'CI image' }))
      form.set('file', new Blob([Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lX8AAAAASUVORK5CYII=', 'base64')], { type: 'image/png' }), 'ci.png')
      return form
    }
    for (const headers of [{ Cookie: cookie, Origin: untrusted }, { Cookie: cookie }]) {
      r = await request('/api/media', { method: 'POST', headers, body: makeForm() })
      assert.equal(r.status, 403, 'untrusted/ambiguous cookie upload rejected')
    }
    r = await request('/api/media', { method: 'POST', headers: { Cookie: cookie, Origin: origin }, body: makeForm() })
    assert.equal(r.status, 201, 'media upload')
    const media = await r.json()
    assert.ok(media.doc?.url)
    const mediaUrl = new URL(media.doc.url, origin)
    assert.equal(mediaUrl.origin, origin, 'media URL uses approved origin')
    r = await request(mediaUrl.pathname + mediaUrl.search)
    assert.equal(r.status, 200, 'media retrieval behind proxy')
    const imageHash = createHash('sha256').update(Buffer.from(await r.arrayBuffer())).digest('hex')
    if (process.env.RESTORE_FIXTURE_PATH) {
      // CI-only synthetic values; never printed or uploaded as artifacts.
      await writeFile(process.env.RESTORE_FIXTURE_PATH, JSON.stringify({ email, password, token, cookie, mediaUrl: mediaUrl.pathname + mediaUrl.search, imageHash }), { mode: 0o600 })
    }
    for (const headers of [{ Cookie: cookie, Origin: untrusted }, { Cookie: cookie }]) {
      await request('/api/staff/logout', { method: 'POST', headers })
      r = await request('/api/staff/me', { headers: { Cookie: cookie, Origin: origin } })
      assert.equal((await r.json()).user?.email, email, 'untrusted/ambiguous logout did not revoke session')
    }
    r = await request('/api/staff/logout', { method: 'POST', headers: { Cookie: cookie, Origin: origin } })
    assert.equal(r.status, 200, 'cookie logout')
    assert.ok(/(?:^|;)\s*Secure(?:=true)?(?:;|$)/i.test(r.headers.get('set-cookie') || ''), 'logout expires Secure cookie')
    r = await request('/api/staff/me', { headers: { Cookie: cookie, Origin: origin } })
    assert.equal((await r.json()).user, null, 'old session no longer valid')
    r = await request('/api/staff/login', { method: 'POST', headers: { ...json, Origin: origin }, body: JSON.stringify({ email, password }) })
    assert.equal(r.status, 200, 'login after logout')
    r = await request('/health')
    assert.equal(r.status, 200)
    assert.equal(r.headers.get('x-robots-tag'), 'noindex, nofollow')
  } finally { await new Promise(resolve => proxy.close(resolve)) }
})
