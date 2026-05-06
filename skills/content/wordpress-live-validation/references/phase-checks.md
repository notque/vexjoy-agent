# WordPress Live Validation — Phase Check Details

## Phase 1: NAVIGATE — Detailed Steps

**Step 1: Verify browser MCP availability**

Before any browser operation, test Playwright tools are accessible. If unavailable, exit with skip report immediately rather than failing later.

**Step 2: Navigate to the post URL**

Use `browser_navigate` with a full HTTPS URL.

**Step 3: Wait for content area**

Use `browser_wait_for` with the content selector. Try selectors in order:
1. `article` (most WordPress themes)
2. `.entry-content` (classic themes)
3. `.post-content` (premium themes)
4. `main` (fallback)

Use custom selector if provided.

**Step 4: Remove cookie/consent banners (if present)**

Use `browser_evaluate` to remove visual overlays (DOM removal only—does not interact with tracking):

```javascript
// Common cookie banner selectors
const banners = document.querySelectorAll(
  '[class*="cookie"], [class*="consent"], [id*="cookie"], [id*="consent"], .gdpr-banner'
);
banners.forEach(b => b.remove());
```

---

## Phase 2: VALIDATE — All 7 Checks

**Check 1: Title Match** (Severity: BLOCKER)

Extract the rendered title:
```javascript
const titleEl = document.querySelector('h1, .entry-title, .post-title');
titleEl ? titleEl.textContent.trim() : null;
```

If expected title provided: compare (case-insensitive, trimmed). PASS if match, BLOCKER if differ or no title found.
If no expected title: report rendered title as INFO.

**Check 2: H2 Structure** (Severity: WARNING)

Extract all H2s:
```javascript
const h2s = Array.from(document.querySelectorAll('h2')).map(h => h.textContent.trim());
JSON.stringify(h2s);
```

If expected count provided: compare. PASS if match, WARNING if differ.
Always report rendered H2 texts for inspection.

**Check 3: Image Loading** (Severity: BLOCKER)

Use `browser_network_requests`. Filter image URLs (common extensions or image MIME types). Check response status:
- 2xx: loaded successfully
- 4xx/5xx: BLOCKER (broken for readers)

Report total, loaded, and failed counts with URLs of failures.

**Check 4: JavaScript Console Errors** (Severity: WARNING)

Use `browser_console_messages`. Filter to `error` level. Exclude patterns:
- Ad networks: doubleclick, googlesyndication, adsbygoogle
- Analytics: gtag, analytics, fbevents
- Consent: cookiebot, onetrust, quantcast
- Browser extensions

Report count of genuine errors and their messages.

**Check 5: OG Tags** (Severity: WARNING)

Extract OG and social meta tags:
```javascript
const getMeta = (sel) => {
  const el = document.querySelector(sel);
  return el ? el.getAttribute('content') : null;
};
JSON.stringify({
  'og:title': getMeta('meta[property="og:title"]'),
  'og:description': getMeta('meta[property="og:description"]'),
  'og:image': getMeta('meta[property="og:image"]'),
  'og:url': getMeta('meta[property="og:url"]'),
  'twitter:card': getMeta('meta[name="twitter:card"]')
});
```

Mark WARNING for missing tags. Report each tag's value and character count.

**Check 6: Meta Description** (Severity: WARNING)

```javascript
const desc = document.querySelector('meta[name="description"]');
desc ? desc.getAttribute('content') : null;
```

PASS if present and non-empty, WARNING if missing or empty. Report value and character count.

**Check 7: Placeholder/Draft Text** (Severity: BLOCKER)

Search visible text for patterns:
```javascript
const body = document.body.innerText;
const patterns = ['[TBD]', '[TODO]', 'PLACEHOLDER', 'Lorem ipsum', '[insert', '[FIXME]'];
const found = patterns.filter(p => body.toLowerCase().includes(p.toLowerCase()));
JSON.stringify(found);
```

Mark BLOCKER if any found, PASS if none.

---

## Phase 3: RESPONSIVE CHECK — Detailed Steps

Test each viewport in sequence:

| Viewport | Width | Height | Represents |
|----------|-------|--------|------------|
| Mobile | 375 | 812 | iPhone-class |
| Tablet | 768 | 1024 | iPad-class |
| Desktop | 1440 | 900 | Standard laptop |

For each viewport:

**Step 1**: Use `browser_resize` to set dimensions.

**Step 2**: Use `browser_take_screenshot` to capture. Save to known path.

**Step 3**: Check for horizontal overflow:

```javascript
document.documentElement.scrollWidth > document.documentElement.clientWidth;
```

Mark WARNING if overflow detected—content extends beyond viewport (usually tables, images, or code blocks not responsive).

**Step 4**: Verify content container visibility:

```javascript
const content = document.querySelector('article, .entry-content, .post-content, main');
if (content) {
  const rect = content.getBoundingClientRect();
  JSON.stringify({ visible: rect.width > 0 && rect.height > 0, width: rect.width, height: rect.height });
} else {
  JSON.stringify({ visible: false });
}
```

Mark WARNING if container not visible or zero dimensions at any breakpoint.
