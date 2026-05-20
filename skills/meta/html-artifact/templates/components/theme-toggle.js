/* === Theme Toggle Component ===
 * Initialize <html data-theme> based on body's loaded theme name on first run,
 * then toggle between "light" and "dark" on click. The CSS in
 * theme-toggle.css overrides :root tokens at higher specificity so the
 * toggle works regardless of which named theme is loaded on body.
 */
(function initThemeToggle() {
  var html = document.documentElement;
  var body = document.body;
  if (!html.dataset.theme || html.dataset.theme === '' || html.dataset.theme === 'light' || html.dataset.theme === 'dark') {
    var bodyTheme = body && body.dataset ? body.dataset.theme || '' : '';
    var darkThemes = ['dark-focus'];
    var startsDark = darkThemes.indexOf(bodyTheme) !== -1;
    html.dataset.theme = startsDark ? 'dark' : 'light';
  }
})();
function toggleTheme() {
  var html = document.documentElement;
  html.dataset.theme = html.dataset.theme === 'dark' ? 'light' : 'dark';
}
