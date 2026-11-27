import assert from 'node:assert/strict'
import { test } from 'node:test'
import { describeElement, measureOverflow, pageMeasurementSource } from '../scripts/layout-measure.mjs'

/**
 * A box with a place in it: a tag, some classes, an id and the rectangle it
 * occupies. The measurement only ever asks a box for these, so this is
 * enough of a DOM to test it against — and it is deliberately explicit, so a
 * test says which box it means.
 */
function box({ tag = 'div', id = '', className = '', left = 0, top = 0, width = 100, height = 20, parent = null, overflowX = 'visible' }) {
  const el = {
    tagName: tag,
    id,
    className,
    parentElement: parent,
    overflowX,
    getBoundingClientRect: () => ({ left, top, right: left + width, bottom: top + height, width, height }),
  }
  return el
}

/**
 * A document whose window is `width` wide, holding `body`'s children.
 *
 * The measurement asks each ancestor whether it clips what is past the edge,
 * so the document hands out a style for every box it holds.
 */
function documentOf(width, children) {
  const body = { ...box({ tag: 'body', width, height: 1000 }), querySelectorAll: () => children }
  const root = { ...box({ tag: 'html', width, height: 1000 }), clientWidth: width, scrollWidth: width }
  body.parentElement = root
  const view = {
    getComputedStyle: (el) => ({ overflowX: el.overflowX ?? 'visible' }),
  }
  for (const el of [body, root, ...children]) {
    el.ownerDocument = { defaultView: view }
  }
  return { documentElement: root, body }
}

test('a box that stays inside the window is not reported', () => {
  const inside = box({ className: 'platform__art', left: 16, width: 300 })
  const result = measureOverflow(documentOf(900, [inside]))
  assert.deepEqual(result.offenders, [])
  assert.equal(result.limit, 900)
})

test('a box that reaches past the right edge is named', () => {
  const wide = box({ tag: 'div', className: 'platform__art wide', left: 16, width: 900 })
  const result = measureOverflow(documentOf(900, [wide]))
  assert.equal(result.offenders.length, 1)
  assert.equal(result.offenders[0].selector, 'div.platform__art.wide')
  assert.equal(result.offenders[0].right, 916)
})

test('a box that reaches before the left edge is named', () => {
  const shifted = box({ tag: 'img', left: -40, width: 100 })
  const result = measureOverflow(documentOf(900, [shifted]))
  assert.equal(result.offenders.length, 1)
  assert.equal(result.offenders[0].selector, 'img')
  assert.equal(result.offenders[0].left, -40)
})

test('the outermost box is the one named, not the child inside it', () => {
  // The child sticks out only because the parent does: naming the child
  // would send whoever fixes this to the wrong place.
  const parent = box({ tag: 'section', className: 'platform', left: 16, width: 900 })
  const child = box({ tag: 'img', left: 16, width: 900, parent })
  const result = measureOverflow(documentOf(900, [parent, child]))
  assert.equal(result.offenders.length, 1)
  assert.equal(result.offenders[0].selector, 'section.platform')
})

test('a box the window hides entirely is not asked about', () => {
  // No size, no box: nothing is cut off that was ever shown.
  const hidden = box({ tag: 'div', width: 0, height: 0 })
  const result = measureOverflow(documentOf(900, [hidden]))
  assert.deepEqual(result.offenders, [])
})

test('a box an ancestor clips is not a defect', () => {
  // An SVG draws its shapes in its own coordinate system: a shape can reach
  // far past the window while the SVG that holds it keeps it out of sight.
  // The reader loses nothing, so nothing is reported.
  const shape = box({ tag: 'g', className: 'grid-backdrop__lines', left: -472, width: 1845 })
  const svg = box({ tag: 'svg', className: 'grid-backdrop__svg', left: 0, width: 900, overflowX: 'hidden', parent: null })
  shape.parentElement = svg
  const result = measureOverflow(documentOf(900, [svg, shape]))
  assert.deepEqual(result.offenders, [])
})

test('a box nothing clips is still a defect', () => {
  // The same shape, in a box that lets it show: now it is cut off at the
  // edge, and it is reported.
  const shape = box({ tag: 'g', className: 'art', left: -472, width: 1845 })
  const frame = box({ tag: 'svg', className: 'art__frame', left: 0, width: 900, overflowX: 'visible' })
  shape.parentElement = frame
  const result = measureOverflow(documentOf(900, [frame, shape]))
  assert.equal(result.offenders.length, 1)
  assert.equal(result.offenders[0].selector, 'g.art')
})

test('the page hiding its own overflow does not excuse the overflow', () => {
  // The site hides horizontal overflow on purpose, so the content is cut
  // off at the edge instead of being scrolled to. That hiding is the very
  // defect this measures: it must not also be what excuses it.
  const wide = box({ tag: 'div', className: 'platform__art', left: -16, width: 436 })
  const result = measureOverflow(documentOf(900, [wide]))
  assert.equal(result.offenders.length, 1)
  assert.equal(result.offenders[0].selector, 'div.platform__art')
  assert.equal(result.offenders[0].left, -16)
})

test('an element is named by its tag, its id and up to three classes', () => {
  assert.equal(describeElement(box({ tag: 'img', id: 'hero', className: 'a b c d' })), 'img#hero.a.b.c')
  assert.equal(describeElement(box({ tag: 'div', className: '  one   two  ' })), 'div.one.two')
  assert.equal(describeElement(box({ tag: 'div' })), 'div')
})

test('the measurement the browser receives stands on its own', () => {
  // A browser is given a function's TEXT. A measurement that reaches for a
  // name from the module it was written in arrives with that name missing,
  // and the check then reports a broken measurement instead of a layout.
  // This is what the page runs, evaluated the way the page evaluates it.
  const source = pageMeasurementSource()
  const wide = box({ tag: 'div', className: 'platform__art wide', left: 16, width: 900 })
  const document = documentOf(900, [wide])
  // eslint-disable-next-line no-new-func
  const measure = new Function('document', `return (${source})(document)`)
  const result = measure(document)
  assert.equal(result.offenders.length, 1)
  assert.equal(result.offenders[0].selector, 'div.platform__art.wide')
  assert.equal(result.offenders[0].right, 916)
  assert.equal(result.limit, 900)
})

test('the measurement the browser receives agrees with the one under test', () => {
  // The browser's copy and the tested copy are the same measurement. If they
  // ever drift, the check would be measuring something the tests never saw.
  const source = pageMeasurementSource()
  // eslint-disable-next-line no-new-func
  const measure = new Function('document', `return (${source})(document)`)
  const cases = [
    documentOf(900, [box({ className: 'platform__art', left: 16, width: 300 })]),
    documentOf(900, [box({ tag: 'div', className: 'platform__art wide', left: 16, width: 900 })]),
    documentOf(900, [box({ tag: 'img', left: -40, width: 100 })]),
    documentOf(1280, [box({ tag: 'section', className: 'platform', left: 16, width: 900 })]),
  ]
  for (const document of cases) {
    assert.deepEqual(measure(document), measureOverflow(document))
  }
})
