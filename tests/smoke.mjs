import assert from 'node:assert/strict'
import { test } from 'node:test'

const base = process.env.TEST_BASE_URL || 'http://127.0.0.1:3000'

test('approved page skeletons are available', async () => {
  for (const path of ['/', '/company', '/company/about', '/company/team', '/services', '/services/energy-audit', '/track-record', '/knowledge', '/tools', '/platform', '/contact', '/privacy', '/terms', '/cookies']) {
    const response = await fetch(`${base}${path}`)
    assert.equal(response.status, 200, path)
    const html = await response.text()
    assert.match(html, /lang="fa"/)
    assert.match(html, /dir="rtl"/)
  }
})

test('unknown routes are not found', async () => {
  for (const path of ['/not-a-page', '/services/not-a-service']) {
    const response = await fetch(`${base}${path}`)
    assert.equal(response.status, 404, path)
  }
})

test('CMS collections are not publicly readable', async () => {
  for (const collection of ['staff', 'pages', 'services', 'track-record-items', 'team-members', 'faqs', 'lead-submissions', 'media']) {
    const response = await fetch(`${base}/api/${collection}`)
    assert.equal(response.status, 403, collection)
  }
})
