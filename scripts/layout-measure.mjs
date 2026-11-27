/**
 * layout-measure.mjs — the measurement, as a function of the page.
 *
 * Kept apart from the browser driver (`check-layout-overflow.mjs`) so that
 * what counts as "outside the window" can be tested without a browser, and so
 * that the driver holds nothing but the driving.
 *
 * The site hides horizontal overflow on purpose (`body { overflow-x: hidden
 * }`), so the page never grows a scrollbar: content that would have
 * overflowed is cut off at the edge instead. That is why the overflow
 * recorded in the reports was never visible as a scrollbar — it was
 * measured, not seen. This measures it the same way, and names the box.
 */

/**
 * A short, readable name for a box: its tag, its id, and up to three of its
 * classes. Enough to find it in the source; not so much that the report
 * becomes a wall of selectors.
 */
export function describeElement(el) {
  const id = el.id ? `#${el.id}` : ''
  const cls =
    el.className && typeof el.className === 'string'
      ? '.' + el.className.trim().split(/\s+/).filter(Boolean).slice(0, 3).join('.')
      : ''
  return `${el.tagName.toLowerCase()}${id}${cls}`
}

/**
 * Measure the page and say what sticks out.
 *
 * `clientWidth` is the window's width without the scrollbar. A box that
 * reaches past either edge — or is simply wider than the window — is a
 * candidate. The OUTERMOST such box is the one reported: a child of a box
 * that already sticks out is only sticking out because its parent does, and
 * fixing the parent fixes both.
 */
export function measureOverflow(document) {
  const root = document.documentElement
  const limit = root.clientWidth
  const sticksOut = (el) => {
    const r = el.getBoundingClientRect()
    if (r.width < 1 || r.height < 1) return false
    return r.right > limit + 1 || r.left < -1 || r.width > limit + 1
  }
  const offenders = []
  for (const el of document.body.querySelectorAll('*')) {
    if (!sticksOut(el)) continue
    const parent = el.parentElement
    if (parent && parent !== document.body && sticksOut(parent)) continue
    const r = el.getBoundingClientRect()
    offenders.push({
      selector: describeElement(el),
      left: Math.round(r.left),
      right: Math.round(r.right),
      width: Math.round(r.width),
    })
  }
  return {
    limit,
    scrollWidth: root.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    offenders,
  }
}
