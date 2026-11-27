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
 *
 * A box that is CLIPPED by an ancestor is not a defect either. An SVG
 * draws its shapes in its own coordinate system, and a shape may well reach
 * past the window while the SVG that holds it — whose viewport clips by
 * default — keeps it from ever being seen there. The reader loses nothing.
 * So a box is only reported when nothing above it clips it: the overflow is
 * real because it is visible.
 *
 * `body` and `html` do not count as clipping. Their overflow is the site's
 * own way of hiding the overflow — it propagates to the viewport and the
 * content is cut off at the edge instead of being scrolled to. That is the
 * defect being looked for, so it cannot also be the thing that excuses it.
 */
export function measureOverflow(document) {
  const root = document.documentElement
  const limit = root.clientWidth
  const sticksOut = (el) => {
    const r = el.getBoundingClientRect()
    if (r.width < 1 || r.height < 1) return false
    return r.right > limit + 1 || r.left < -1 || r.width > limit + 1
  }
  // Does anything above this box hide what is past the edge? The style is
  // read from the box's own owner, so the measurement does not need a
  // browser to answer it.
  const isClipped = (el) => {
    for (let parent = el.parentElement; parent; parent = parent.parentElement) {
      if (parent === document.body || parent === root) continue
      const style = parent.ownerDocument?.defaultView?.getComputedStyle?.(parent)
      const overflow = style?.overflowX
      if (overflow && overflow !== 'visible') return true
    }
    return false
  }
  const offenders = []
  for (const el of document.body.querySelectorAll('*')) {
    if (!sticksOut(el)) continue
    const parent = el.parentElement
    if (parent && parent !== document.body && sticksOut(parent)) continue
    if (isClipped(el)) continue
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

/**
 * The measurement, as the browser will receive it.
 *
 * A function handed to a browser crosses as its SOURCE, not as a closure:
 * anything it names from outside its own body is simply not there when it
 * arrives. Measuring through the module's own functions therefore finds
 * `measureOverflow is not defined` in the page, and the check reports a
 * broken measurement rather than a layout.
 *
 * So the page-side measurement is written out as ONE expression with its
 * helpers inside it, and that text — not the module's functions — is what
 * the driver sends. The helpers are still the ones above: their source is
 * what is carried over, so there is one measurement and not two.
 *
 * What comes back is a function of the page's document: the caller says
 * which document to measure, so that the text and the call are two things a
 * reader can check separately.
 */
export function pageMeasurementSource() {
  return `(function (document) {
${describeElement.toString()}
${measureOverflow.toString()}
return measureOverflow(document)
})`
}
