/* === Theme Toggle Component ===
 * Pre-paint init in <head> already set <html data-theme> from localStorage
 * (or to the "dark" default). This file only handles click-to-flip and
 * persistence. Storage key 'html-artifact-theme-v2' is versioned: bumping
 * the suffix invalidates stale prefs when the default theme changes.
 */
var THEME_STORAGE_KEY = 'html-artifact-theme-v2';
function toggleTheme() {
  var html = document.documentElement;
  var next = html.dataset.theme === 'dark' ? 'light' : 'dark';
  html.dataset.theme = next;
  try { localStorage.setItem(THEME_STORAGE_KEY, next); } catch (e) { /* storage blocked: in-memory only */ }
}
