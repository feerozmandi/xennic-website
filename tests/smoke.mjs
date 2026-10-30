import assert from 'node:assert/strict'
import { test } from 'node:test'

const base = process.env.TEST_BASE_URL || 'http://127.0.0.1:3000'

test('approved content is served by the public pages', async () => {
  const pages = {
    '/': 'مهندسی انرژی برای تصمیم‌های دقیق‌تر',
    '/company': 'شرکت زر نور نیرو یکتا',
    '/company/about': 'شرکت زر نور نیرو یکتا',
    '/company/team': 'احمد فیروزمندی',
    '/services': 'مشاورهٔ فنی برق صنعتی',
    '/services/industrial-electrical-consulting': 'مشاورهٔ تخصصی در حوزهٔ برق صنعتی',
    '/services/building-electrical-design': 'مبحث ۱۳',
    '/services/distribution-supervision': 'پیمانکاران و شرکت‌های توزیع برق',
    '/services/energy-audit': 'ممیزی انرژی صنایع',
    '/services/grounding-lightning-protection': 'سیستم ارتینگ و صاعقه‌گیر',
    '/services/technical-training': 'به‌زودی',
    '/track-record': 'پیش از تأسیس Xennic',
  }
  for (const [path, text] of Object.entries(pages)) {
    const response = await fetch(`${base}${path}`)
    assert.equal(response.status, 200, path)
    const html = await response.text()
    assert.match(html, /lang="fa"/)
    assert.match(html, /dir="rtl"/)
    assert.ok(html.includes(text), `${path}: expected approved text`)
    assert.ok(!html.includes('ساختار اولیهٔ صفحه؛ محتوا پس از تأیید ساختار افزوده می‌شود.'), `${path}: still placeholder`)
  }
})

test('homepage introductions use the approved copy and platform scope', async () => {
  const response = await fetch(`${base}/`)
  assert.equal(response.status, 200)
  const html = await response.text()
  const trackRecord = html.match(/<section\b[^>]*data-testid="track-record-intro"[^>]*>([\s\S]*?)<\/section>/)?.[1]
  assert.ok(trackRecord, 'track record section is missing')
  assert.ok(trackRecord.includes('تجربهٔ مهندسی که می‌توان به آن اعتماد کرد'))
  assert.ok(trackRecord.includes('با تجربه و پیشینهٔ حرفه‌ای مؤسس Xennic در صنعت برق، پیش از تأسیس این مجموعه، آشنا شوید.'))
  assert.match(trackRecord, /href="\/track-record"/)
  assert.ok(trackRecord.includes('مشاهدهٔ پیشینهٔ مهندسی'))

  const platform = html.match(/<section\b[^>]*data-testid="platform-intro"[^>]*>([\s\S]*?)<\/section>/)?.[1]
  assert.ok(platform, 'platform section is missing')
  assert.equal(platform.replace(/<[^>]*>/g, '').trim(), 'Xennic Platformبه‌زودی')
  assert.doesNotMatch(platform, /<(?:a|p|button)\b/i)
})

test('unknown routes are not found', async () => {
  for (const path of ['/not-a-page', '/services/not-a-service']) {
    const response = await fetch(`${base}${path}`)
    assert.equal(response.status, 404, path)
  }
})

test('only public content is anonymously readable and writes remain restricted', async () => {
  for (const collection of ['pages', 'services', 'track-record-items', 'team-members', 'faqs', 'media']) {
    const response = await fetch(`${base}/api/${collection}`)
    assert.equal(response.status, 200, collection)
    const post = await fetch(`${base}/api/${collection}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
    assert.equal(post.status, 403, `${collection}: create`)
    for (const method of ['PATCH', 'DELETE']) {
      const response = await fetch(`${base}/api/${collection}/999999`, { method, headers: { 'Content-Type': 'application/json' }, body: method === 'PATCH' ? '{}' : undefined })
      assert.equal(response.status, 403, `${collection}: ${method}`)
    }
  }
  for (const collection of ['staff', 'lead-submissions']) {
    const response = await fetch(`${base}/api/${collection}`)
    assert.equal(response.status, 403, collection)
    const post = await fetch(`${base}/api/${collection}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
    assert.equal(post.status, 403, `${collection}: create`)
    for (const method of ['PATCH', 'DELETE']) {
      const response = await fetch(`${base}/api/${collection}/999999`, { method, headers: { 'Content-Type': 'application/json' }, body: method === 'PATCH' ? '{}' : undefined })
      assert.equal(response.status, 403, `${collection}: ${method}`)
    }
  }
})
