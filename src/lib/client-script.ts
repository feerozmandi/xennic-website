/**
 * Pre-paint capability marker.
 *
 * The scroll-reveal animation needs to hide its elements before they enter the
 * viewport, but hiding content in plain CSS would leave a visitor without
 * JavaScript looking at an empty page. The `has-js` class is therefore added
 * here, in `<head>`, before the first frame: the animation only exists when the
 * browser can actually run it.
 */
export const clientScript = `
(function () {
  document.documentElement.classList.add('has-js');
})();
`
