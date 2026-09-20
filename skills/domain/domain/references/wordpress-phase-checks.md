# WordPress browser procedure

1. Navigate and require HTTP 200. Wait for `article`, then `.entry-content`, `.post-content`, or `main`. If none exists, save screenshot plus DOM snapshot and stop content checks; metadata checks may continue.
2. Snapshot the rendered DOM. Extract title/H1, H2 text, image `src/currentSrc/naturalWidth`, console errors, OG/Twitter tags, meta description, and visible text.
3. Check visible text case-insensitively for `TODO`, `TBD`, `lorem ipsum`, `[insert`, `draft`, and `placeholder`; report the matched excerpt rather than the token alone.
4. At 375×812, 768×1024, and 1440×900, resize, screenshot, and compare `document.documentElement.scrollWidth` to `clientWidth`. Confirm the content root has nonzero dimensions and is not hidden.

Cookie banners may be removed from the DOM solely to expose the page for read-only validation; do not click consent controls.
