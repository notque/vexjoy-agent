# WordPress browser-tool notes

Use `browser_navigate`, `browser_wait_for`, `browser_snapshot`, `browser_evaluate`, `browser_network_requests`, `browser_console_messages`, `browser_resize`, and `browser_take_screenshot`.

Repository-specific invocation cautions:

- `browser_evaluate` must return serialized objects with `JSON.stringify`; otherwise some backends expose `[object Object]`.
- Use `innerText` for visible placeholder checks and `textContent` only when hidden text is intentionally included.
- An image failure requires an image request with 4xx/5xx or a rendered image whose `complete` is false or `naturalWidth` is zero. Ignore unrelated failed requests.
- Filter console noise from browser extensions and known third-party scripts, but preserve first-party uncaught errors and CSP failures.
- Validation is single-page/read-only: do not use click, fill, type, upload, drag, select, or dialog actions.

If the Playwright backend is unavailable, try the configured Chrome DevTools backend; otherwise report SKIPPED once without retry loops.
