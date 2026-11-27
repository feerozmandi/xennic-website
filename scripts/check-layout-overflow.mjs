/**
 * check-layout-overflow.mjs — does any published page put content outside the
 * window it is shown in?
 *
 *   node scripts/check-layout-overflow.mjs [base-url]
 *
 * WHAT IT LOOKS FOR. The site hides horizontal overflow on purpose (`body {
 * overflow-x: hidden }`), so the page never grows a scrollbar — the content
 * that would have overflowed is simply cut off at the edge. That is why the
 * overflow recorded in the reports was never visible as a scrollbar: it was
 * measured, not seen. This check measures it the same way and names the
 * element that sticks out.
 *
 * A box that reaches past the window's right edge (or before its left edge)
 * is reported, and so is a box wider than the window. The outermost such box
 * is named, because that is the one to fix: a child of a box that already
 * sticks out is only sticking out because its parent does.
 *
 * THE MATRIX. Every published page, at every width in the list, in both
 * themes. The widths are the ones the reports measured by hand, plus the
 * 880–930 px band where `.platform__art` was found to overflow.
 *
 * THE BROWSER. The runner's own Chrome. A browser driver is installed for
 * this check alone (`npm install --no-save puppeteer-core`) and is NOT a
 * dependency of the website: the site never drives a browser, so `npm ci`
 * must not fetch one.
 */
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'
import { pageMeasurementSource } from './layout-measure.mjs'

const BASE = (process.argv[2] ?? process.env.LAYOUT_CHECK_URL ?? 'http://127.0.0.1:3000').replace(/\/+$/, '')
const WIDTHS = [360, 390, 768, 880, 900, 930, 1024, 1280, 1440]
const THEMES = ['dark', 'light']
const HEIGHT = 900

/** Where Chrome is, when nobody says. The GitHub runner has one installed. */
function findChrome() {
  const candidates = [
    process.env.PUPPETEER_EXECUTABLE_PATH,
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
  ].filter(Boolean)
  for (const candidate of candidates) {
    if (existsSync(candidate)) return candidate
  }
  throw new Error('no Chrome found — set PUPPETEER_EXECUTABLE_PATH')
}

/** The published paths, read from the sitemap the site itself serves. */
async function publishedPaths() {
  const fallback = ['/', '/company', '/company/team', '/services', '/track-record', '/platform', '/contact']
  try {
    const response = await fetch(`${BASE}/sitemap.xml`)
    if (!response.ok) return fallback.map((p) => ({ path: p, locale: 'fa' }))
    const xml = await response.text()
    const paths = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => {
      const url = new URL(m[1])
      return { path: url.pathname, locale: url.pathname.startsWith('/en') ? 'en' : 'fa' }
    })
    return paths.length > 0 ? paths : fallback.map((p) => ({ path: p, locale: 'fa' }))
  } catch {
    return fallback.map((p) => ({ path: p, locale: 'fa' }))
  }
}

/**
 * The measurement, run inside the page. It lives in `layout-measure.mjs` so
 * that what counts as "outside the window" can be tested without a browser.
 *
 * It is sent as source, not as a function: a browser receives what a
 * function's text says, and a function that reaches outside its own body
 * arrives with those names missing. `pageMeasurementSource` writes the whole
 * measurement into one expression, so what the page runs is the same
 * measurement the tests cover.
 */
const MEASURE = `(${pageMeasurementSource()})(document)`

// The pages are read before the browser is looked for: a server that is not
// up is the first thing that can be wrong, and it is worth saying so.
const pages = await publishedPaths()
console.log(`layout: ${pages.length} published pages, ${WIDTHS.length} widths, ${THEMES.length} themes.`)

let puppeteer
try {
  puppeteer = (await import('puppeteer-core')).default
} catch {
  console.error(
    'layout: the browser driver is not installed. It is not a dependency of the\n' +
      '  website on purpose — the site never drives a browser — so it is installed\n' +
      '  for this check alone:  npm install --no-save puppeteer-core@24',
  )
  process.exit(2)
}

let executablePath
try {
  executablePath = findChrome()
} catch (error) {
  console.error(`layout: ${error.message}. The runner's own Chrome is used when it is there.`)
  process.exit(2)
}

const failures = []
let checked = 0

/**
 * The report, written whether the check passed, failed or stopped: a clean
 * run says which pages and widths were measured, and a failing one says
 * which box stuck out. Either way it travels with the run — a measurement
 * that is not written down is not a measurement.
 */
function writeReport() {
  const target = process.env.LAYOUT_CHECK_REPORT
  if (!target) return
  const summary = {
    baseUrl: BASE,
    widths: WIDTHS,
    themes: THEMES,
    checked,
    failures: failures.map((f) => ({
      path: f.path,
      locale: f.locale,
      width: f.width,
      theme: f.theme,
      reason: f.reason ?? null,
      offenders: f.offenders ?? [],
    })),
  }
  mkdirSync(dirname(target), { recursive: true })
  writeFileSync(target, `${JSON.stringify(summary, null, 1)}\n`, 'utf8')
}

let browser
try {
  browser = await puppeteer.launch({
    executablePath,
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--hide-scrollbars'],
  })
} catch (error) {
  failures.push({ path: '-', locale: '-', width: 0, theme: '-', reason: `the browser did not start: ${error?.message ?? error}` })
  writeReport()
  console.error(`layout: the browser did not start: ${error?.message ?? error}`)
  process.exit(1)
}

try {
  const page = await browser.newPage()
  for (const { path, locale } of pages) {
    for (const width of WIDTHS) {
      await page.setViewport({ width, height: HEIGHT, deviceScaleFactor: 1 })
      // A page that will not load, or a browser that will not answer, is a
      // finding of its own: the measurement did not happen, and saying so is
      // better than letting the run end without a word.
      let response
      try {
        response = await page.goto(`${BASE}${path}`, { waitUntil: 'load', timeout: 45000 })
      } catch (error) {
        failures.push({ path, locale, width, theme: '-', reason: `the page did not load: ${error?.message ?? error}` })
        continue
      }
      if (!response || !response.ok()) {
        // 304 is the browser's own cache answering: the page is there, and
        // it is the same page. Only a status that is not a success and not
        // a revalidation means the page did not arrive.
        const status = response ? response.status() : 0
        if (status !== 304) {
          failures.push({ path, locale, width, theme: '-', reason: `the page answered ${response ? status : 'nothing'}` })
          continue
        }
      }
      // The text's width decides where it breaks, and a webfont that has not
      // arrived yet is measured with a fallback: the boxes read here would
      // not be the boxes the reader gets. So the fonts are waited for.
      await page.evaluate(() => document.fonts.ready)
      for (const theme of THEMES) {
        await page.evaluate((t) => {
          document.documentElement.setAttribute('data-theme', t)
        }, theme)
        // The theme changes colours only, but the page settles a frame after
        // the change; measuring in the same frame would read the old boxes.
        await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))))
        const result = await page.evaluate(MEASURE)
        checked++
        if (result.offenders.length > 0) {
          failures.push({ path, locale, width, theme, offenders: result.offenders, scrollWidth: result.scrollWidth })
        }
      }
    }
  }
} catch (error) {
  // The run ends with the report written: what was measured, and what was
  // not, is the whole of what is known.
  failures.push({ path: '-', locale: '-', width: 0, theme: '-', reason: `the measurement stopped: ${error?.message ?? error}` })
} finally {
  await browser.close()
  writeReport()
}

if (failures.length === 0) {
  console.log(`layout: ${checked} page/theme/width combinations, no content outside the window.`)
  process.exit(0)
}

console.error(`layout: ${failures.length} of ${checked} combinations put content outside the window.`)
for (const failure of failures) {
  const where = `${failure.path} (${failure.locale}) at ${failure.width}px, theme ${failure.theme}`
  if (failure.reason) {
    console.error(`  ${where}: ${failure.reason}`)
    continue
  }
  console.error(`  ${where}:`)
  for (const offender of failure.offenders) {
    console.error(`    ${offender.selector} — left ${offender.left}, right ${offender.right}, width ${offender.width} (window ${failure.scrollWidth})`)
  }
}

process.exit(1)
