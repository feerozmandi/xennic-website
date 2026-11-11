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
    '/contact': 'تماس با Xennic',
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

test('homepage introduces the approved pillars, track record and platform scope', async () => {
  const response = await fetch(`${base}/`)
  assert.equal(response.status, 200)
  const html = await response.text()

  for (const text of ['Engineering First', 'Evidence Based', 'Independent Thinking']) {
    assert.ok(html.includes(text), `missing approved principle: ${text}`)
  }
  // No disabled or fake-interactive calls to action may be rendered.
  assert.doesNotMatch(html, /<button[^>]*\bdisabled\b/)
  assert.doesNotMatch(html, /ارسال شد|با موفقیت ثبت/)

  const trackRecord = html.match(/<section\b[^>]*data-testid="track-record-intro"[^>]*>([\s\S]*?)<\/section>/)?.[1]
  assert.ok(trackRecord, 'track record section is missing')
  assert.ok(trackRecord.includes('تجربهٔ مهندسی که می‌توان به آن اعتماد کرد'))
  assert.ok(trackRecord.includes('با تجربه و پیشینهٔ حرفه‌ای مؤسس Xennic در صنعت برق، پیش از تأسیس این مجموعه، آشنا شوید.'))
  assert.ok(trackRecord.includes('احمد فیروزمندی'))
  assert.match(trackRecord, /href="\/track-record"/)

  const platform = html.match(/<section\b[^>]*data-testid="platform-intro"[^>]*>([\s\S]*?)<\/section>/)?.[1]
  assert.ok(platform, 'platform section is missing')
  assert.ok(platform.includes('Xennic Platform'))
  assert.ok(platform.includes('به‌زودی'))
  // The platform is not live: the section must not offer a link or button into it.
  assert.doesNotMatch(platform, /<(?:a|button)\b/i)
})

test('the contact page publishes only owner-confirmed channels and a real form', async () => {
  const response = await fetch(`${base}/contact`)
  assert.equal(response.status, 200)
  const html = await response.text()

  // Every value below was supplied by the owner; none may be inferred.
  for (const value of [
    '۰۹۱۲۴۵۳۳۸۷۸',
    'tel:+989124533878',
    'info@xennic.ir',
    'feerozmandiha@gmail.com',
    'https://ble.ir/xennic',
    'https://t.me/xennicco',
    'https://instagram.com/xennic.ir',
  ]) {
    assert.ok(html.includes(value), `missing contact channel: ${value}`)
  }

  // The founder portrait is the real supplied photo, not a placeholder box.
  assert.match(html, /founder\.jpg/)
  assert.doesNotMatch(html, /عکس رسمی مؤسس|جای رزرو/)

  // A real form with labelled fields, and no success message before submission.
  assert.match(html, /<form[^>]*class="contact-form"/)
  for (const field of ['name', 'phone', 'email', 'subject', 'message']) {
    assert.ok(html.includes(`name="${field}"`), `missing field: ${field}`)
    assert.ok(html.includes(`for="contact-${field}"`), `missing label: ${field}`)
  }
  assert.ok(html.includes('ارسال پیام'))
  assert.doesNotMatch(html, /با موفقیت ثبت|ارسال شد/)
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

test('the theme resolves before paint and the switches are real controls', async () => {
  const response = await fetch(`${base}/`)
  const html = await response.text()
  // The pre-paint script must be inside <head> so no frame renders in the wrong theme.
  const head = html.slice(0, html.indexOf('</head>'))
  assert.match(head, /xennic-theme/, 'theme script is not in <head>')
  assert.match(head, /root\.dataset\.theme/, 'theme script does not set the attribute')
  // Exactly one theme switch, exposed as a switch, with a Persian label.
  const switches = html.match(/role="switch"/g) ?? []
  assert.equal(switches.length, 1, 'expected a single theme switch in the header')
  assert.match(html, /class="liquid-switch"/)
  assert.match(html, /aria-label="حالت (شب|روز)[^"]*"/)
  // Locale control: both editions are live, so each is a link to the twin page.
  assert.match(html, /aria-current="true"[^>]*>فا/)
  assert.match(html, /href="\/en"[^>]*>EN/)
  assert.match(html, /rel="alternate" hrefLang="en" href="https:\/\/xennic\.ir\/en"/)
  // Official artwork replaces the retyped wordmark.
  assert.match(html, /\/brand\/xennic-logo-on-dark\.webp/)
})

test('content pages carry one H1, approved framing and no placeholder text', async () => {
  const pages = ['/company', '/company/team', '/services', '/services/energy-audit', '/track-record', '/knowledge']
  for (const path of pages) {
    const html = await (await fetch(`${base}${path}`)).text()
    assert.equal((html.match(/<h1\b/g) ?? []).length, 1, `${path}: exactly one H1`)
    assert.ok(!html.includes('ساختار اولیهٔ صفحه'), `${path}: placeholder copy is gone`)
    assert.ok(!/<button[^>]*\bdisabled\b/.test(html), `${path}: no disabled buttons`)
  }

  // The service detail page offers a real route to the contact page.
  const detail = await (await fetch(`${base}/services/energy-audit`)).text()
  assert.match(detail, /href="\/contact"/)
  assert.match(detail, /class="btn btn--primary"/)

  // The unpublished service keeps its "soon" badge and offers no request button.
  const soon = await (await fetch(`${base}/services/technical-training`)).text()
  assert.ok(soon.includes('به‌زودی'))
  assert.doesNotMatch(soon, /href="\/contact"[^>]*class="btn btn--primary"/)

  // Track record stays framed as the founder's prior experience, entry by entry.
  const record = await (await fetch(`${base}/track-record`)).text()
  const badges = (record.match(/پیش از تأسیس Xennic/g) ?? []).length
  assert.ok(badges >= 5, 'every track-record entry keeps the prior-experience badge')
  assert.ok(record.includes('به‌معنای سابقهٔ پروژه‌های شرکت نیست'))
})

test('SEO policy: published pages are indexable, unpublished and private ones are not', async () => {
  const indexable = ['/', '/company', '/company/team', '/services', '/services/energy-audit', '/track-record', '/contact']
  for (const path of indexable) {
    const html = await (await fetch(`${base}${path}`)).text()
    assert.ok(!/<meta name="robots"[^>]*noindex/.test(html), `${path}: must stay indexable`)
    assert.match(html, /<link rel="canonical" href="https:\/\/xennic\.ir/, `${path}: canonical host`)
    assert.match(html, /<meta property="og:image" content="https:\/\/xennic\.ir\/brand\/og-cover\.png"/, `${path}: share image`)
    const description = html.match(/<meta name="description" content="([^"]+)"/)?.[1] ?? ''
    assert.ok(description.length > 40, `${path}: own description`)
  }

  // Pages that are linked but not approved yet are served with noindex.
  for (const path of ['/knowledge', '/platform', '/privacy', '/tools']) {
    const html = await (await fetch(`${base}${path}`)).text()
    assert.match(html, /<meta name="robots" content="noindex, nofollow"/, `${path}: noindex`)
  }

  // A service that is still "soon" is not indexed, an open one is.
  const soon = await (await fetch(`${base}/services/technical-training`)).text()
  assert.match(soon, /noindex/)
  const open = await (await fetch(`${base}/services/energy-audit`)).text()
  assert.ok(!/<meta name="robots"[^>]*noindex/.test(open))

  // Crawl directives follow the deployment mode. The preview image is built with
  // XENNIC_PREVIEW=1, so there the whole site is closed; production keeps the
  // public pages open and the private surfaces out. The global noindex may only
  // be lifted by the owner, so the test accepts both and never assumes which.
  const robots = await (await fetch(`${base}/robots.txt`)).text()
  const previewMode = /^Disallow: \/$/m.test(robots)
  if (previewMode) {
    assert.match(robots, /^Disallow: \/$/m, 'preview must keep the whole site closed')
    assert.ok(!/^Allow: \//m.test(robots), 'preview must not allow crawling')
  } else {
    assert.match(robots, /Disallow: \/admin/)
    assert.match(robots, /Sitemap: https:\/\/xennic\.ir\/sitemap\.xml/)
  }
  const sitemap = await (await fetch(`${base}/sitemap.xml`)).text()
  assert.ok(sitemap.includes('https://xennic.ir/contact'))
  assert.ok(!sitemap.includes('/knowledge'))
  assert.ok(!sitemap.includes('technical-training'))
  assert.ok(!sitemap.includes('/admin'))
})

test('the English edition is a separate, correctly declared language tree', async () => {
  const pages = {
    '/en': 'Energy engineering for sharper decisions',
    '/en/company': 'Zar-e Noor-e Niroo-e Yekta (trade name: Xennic)',
    '/en/company/team': 'Ahmad Firouzmandi',
    '/en/services': 'Industrial electrical consulting',
    '/en/services/energy-audit': 'Data-driven analysis of energy consumption',
    '/en/track-record': 'Before Xennic was founded',
    '/en/contact': 'Contact Xennic',
  }
  for (const [path, text] of Object.entries(pages)) {
    const response = await fetch(`${base}${path}`)
    assert.equal(response.status, 200, path)
    const html = await response.text()
    assert.match(html, /<html lang="en" dir="ltr"/, `${path}: language declaration`)
    assert.ok(html.includes(text), `${path}: expected translated copy`)
    // The English tree must not leak a Persian interface string into the chrome.
    assert.ok(!html.includes('در حال آماده‌سازی'), `${path}: Persian badge in the English chrome`)
    assert.ok(!html.includes('ساختار اولیهٔ صفحه'), `${path}: placeholder copy`)
    assert.equal((html.match(/<h1\b/g) ?? []).length, 1, `${path}: exactly one H1`)
    // Canonical points at English, and the pair is declared both ways.
    assert.match(html, /<link rel="canonical" href="https:\/\/xennic\.ir\/en/, `${path}: english canonical`)
    assert.match(html, /rel="alternate" hrefLang="fa" href="https:\/\/xennic\.ir(\/[^"]*)?"/, `${path}: persian twin`)
    const description = html.match(/<meta name="description" content="([^"]+)"/)?.[1] ?? ''
    assert.ok(description.length > 40, `${path}: own description`)
  }

  // The language switch on an English page points back at the same Persian page.
  const contact = await (await fetch(`${base}/en/contact`)).text()
  assert.match(contact, /class="locale-switch__option"[^>]*href="\/contact"/)
  assert.match(contact, /aria-current="true"[^>]*>EN/)

  // The Persian page offers the same page in English, not the English home page.
  const persianContact = await (await fetch(`${base}/contact`)).text()
  assert.match(persianContact, /href="\/en\/contact"/)

  // Unpublished English pages stay out of the index, and unknown ones are 404.
  for (const path of ['/en/knowledge', '/en/platform', '/en/privacy']) {
    const html = await (await fetch(`${base}${path}`)).text()
    assert.match(html, /<meta name="robots" content="noindex, nofollow"/, `${path}: noindex`)
  }
  for (const path of ['/en/not-a-page', '/en/services/not-a-service']) {
    const response = await fetch(`${base}${path}`)
    assert.equal(response.status, 404, path)
  }

  // The sitemap lists both editions with mutual alternates.
  const sitemap = await (await fetch(`${base}/sitemap.xml`)).text()
  assert.ok(sitemap.includes('https://xennic.ir/en/contact'))
  assert.ok(sitemap.includes('hreflang="en" href="https://xennic.ir/en/contact"'))
  assert.ok(!sitemap.includes('/en/knowledge'))
})
