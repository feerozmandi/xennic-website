import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'

// CI-only synthetic credentials, not written to console or uploaded.
const { email, password, mediaUrl, imageHash } = JSON.parse(await readFile(process.env.RESTORE_FIXTURE_PATH, 'utf8'))
const base = 'http://127.0.0.1:33001'
const r = await fetch(`${base}/api/staff/login`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email, password }) })
assert.equal(r.status, 200, 'restored Staff can log in')
const { token } = await r.json()
assert.ok(token, 'restored login returned token')
const me = await fetch(`${base}/api/staff/me`, { headers: { Authorization: `Bearer ${token}` } })
assert.equal((await me.json()).user.email, email)
const page = await fetch(`${base}/api/pages?where[slug][equals]=track-record-intro`)
assert.equal((await page.json()).docs[0].summary, 'CI edit preserved', 'restored edited CMS record')
const home = await fetch(`${base}/`)
assert.ok((await home.text()).includes('CI edit preserved'), 'restored CMS content is rendered')
const media = await fetch(`${base}${mediaUrl}`)
assert.equal(media.status, 200, 'restored media is served')
assert.equal(createHash('sha256').update(Buffer.from(await media.arrayBuffer())).digest('hex'), imageHash, 'restored media bytes match')
console.log('PASS: restored Staff login, CMS API/rendered edit and exact media bytes')
