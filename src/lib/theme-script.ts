/**
 * Pre-paint theme resolution.
 *
 * Runs inline in `<head>` before the first frame so the page never flashes the
 * wrong theme: stored choice first, then the operating-system preference, then
 * the dark brand default. Kept as a string because it must execute before any
 * React code is parsed.
 */
export const themeScript = `
(function () {
  var root = document.documentElement;
  var theme = 'dark';
  try {
    var stored = window.localStorage.getItem('xennic-theme');
    if (stored === 'light' || stored === 'dark') {
      theme = stored;
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      theme = 'light';
    }
  } catch (error) {
    theme = 'dark';
  }
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
  root.dataset.themeReady = 'true';
})();
`
