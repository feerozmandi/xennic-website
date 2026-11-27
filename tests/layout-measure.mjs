import assert from 'node:assert/strict'
import { test } from 'node:test'
import { describeElement, measureOverflow } from '../scripts/layout-measure.mjs'

/**
 * A box with a place in it: a tag, some classes, an id and the rectangle it
 * occupies. The measurement only ever asks a box for these, so this is
 * enough of a DOM to test it against — and it is deliberately explicit, so a
 * test says which box it means.
 */
function box({ tag = 'div', id = '', className = '', left = 0, top = 0, width = 100, height = 20, parent = null }) {
  const el = {
    tagName: tag,
    id,
    className,
    parentElement: parent,
    getBoundingClientRect: () => ({ left, top, right: left + width, bottom: top + height, width, height }),
  }
  return el
}

/** A document whose window is `width` wide, holding `body`'s children. */
function documentOf(width, children) {
  const body = { ...box({ tag: 'body', width, height: 1000 }), querySelectorAll: () => children }
  const root = { ...box({ tag: 'html', width, height: 1000 }), clientWidth: width, scrollWidth: width }
  body.parentElement = root
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

test('an element is named by its tag, its id and up to three classes', () => {
  assert.equal(describeElement(box({ tag: 'img', id: 'hero', className: 'a b c d' })), 'img#hero.a.b.c')
  assert.equal(describeElement(box({ tag: 'div', className: '  one   two  ' })), 'div.one.two')
  assert.equal(describeElement(box({ tag: 'div' })), 'div')
})
