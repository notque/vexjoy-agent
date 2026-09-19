# WordPress Live Validation -- Check Specifications

Detailed specifications for each validation check, including severity rationale, edge cases, and JavaScript extraction patterns.

---

## Severity Levels

| Level | Meaning | User Impact | Examples |
|-------|---------|-------------|---------|
| BLOCKER | Readers see broken or incorrect content | Direct negative impact on reader experience | Broken images, wrong title, placeholder text visible |
| WARNING | Quality is degraded but content is readable | Indirect impact on discoverability or experience | Missing OG tags, JS errors, horizontal overflow |
| INFO | Informational, no action needed | None | Rendered title reported without comparison target |

**Severity assignment is not arbitrary.** The distinction is: does the reader see something broken (BLOCKER) or something suboptimal (WARNING)? If neither, it is INFO.

---

## Check 1: Title Match

**Severity**: BLOCKER (when comparison available), INFO (when no expected title)

**Why BLOCKER**: The title is the single most visible element on the page. If the theme renders a different title than what was uploaded, readers see the wrong content. This can happen when:
- A WordPress plugin rewrites titles (SEO plugins, auto-titling)
- The theme pulls the title from a different field than `post_title`
- HTML entities in the title are double-encoded (`&amp;amp;` instead of `&`)

**Extraction**:
```javascript
const titleEl = document.querySelector('h1, .entry-title, .post-title');
titleEl ? titleEl.textContent.trim() : null;
```

**Selector priority**: `h1` covers most themes. `.entry-title` is WordPress default class. `.post-title` is used by some premium themes. The first match wins.

**Comparison logic**:
- Trim whitespace from both strings
- Case-insensitive comparison
- Normalize HTML entities (`&amp;` -> `&`, `&#8217;` -> `'`)
- If comparison fails, report both values for manual inspection

**Edge cases**:
- Post has no H1 (some themes use the title in `<header>` outside the content area): try `.entry-title` and `.post-title` selectors
- Multiple H1 elements: use the first one, report a WARNING about multiple H1s
- Title contains special characters that render differently in HTML: compare after entity normalization

---

## Check 2: H2 Structure

**Severity**: WARNING

**Why WARNING (not BLOCKER)**: A missing or reordered H2 means the article's structure changed during rendering, but the content is still readable. Common causes:
- Theme CSS hides certain headings
- A plugin modifies heading hierarchy (e.g., table-of-contents generators that restructure headings)
- WordPress block editor wraps headings differently than raw markdown

**Extraction**:
```javascript
const h2s = Array.from(document.querySelectorAll('h2')).map(h => h.textContent.trim());
JSON.stringify(h2s);
```

**Comparison logic** (when expected count is provided):
- Compare count only, not text content (themes may add prefixes, numbers, or anchors)
- If count differs, report both the rendered H2 texts and the expected count
- If rendered count is higher, the theme or a plugin may be injecting headings (e.g., "Related Posts" section)
- If rendered count is lower, a heading may be hidden by CSS or stripped by a filter

**Edge cases**:
- Table of contents plugins inject H2s at the top: the rendered count will be higher than source
- Some themes render H2s as styled `<div>` or `<span>` elements: these will not be captured by the H2 query
- WordPress "separator" blocks between sections: not H2s, should not affect count

---

## Check 3: Image Loading

**Severity**: BLOCKER

**Why BLOCKER**: A broken image (404, 403, 500) shows a broken image icon or empty space where visual content should be. This is immediately visible to readers and damages credibility.

**Method**: Use `browser_network_requests` and filter results.

**Filtering criteria**:
- URL ends with common image extensions: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.svg`, `.avif`
- OR response Content-Type starts with `image/`
- Exclude data URIs (inline base64 images) -- these are not network requests
- Exclude known tracking pixels (1x1 images from analytics/ad platforms)

**Status classification**:
- 200-299: Loaded successfully
- 301/302 -> 200: Redirect to successful load (OK)
- 403: Access denied (BLOCKER -- CDN permission issue)
- 404: Not found (BLOCKER -- image missing)
- 500+: Server error (BLOCKER -- upstream failure)

**Edge cases**:
- Lazy-loaded images: May not appear in network requests until scrolled into view. Use `browser_evaluate` to scroll to the bottom of the page before checking network requests, or accept that lazy images may show as "not loaded" rather than "failed"
- Responsive images (`srcset`): The browser picks one source from the set. Only the selected source appears in network requests.
- External images (Unsplash, Cloudinary, etc.): These are not under WordPress control but still affect reader experience. Report failures regardless of origin.
- SVG inline: SVGs inlined as `<svg>` elements are not network requests and will not appear in the image check

---

## Check 4: JavaScript Console Errors

**Severity**: WARNING

**Why WARNING (not BLOCKER)**: Most JS errors on content sites are from third-party scripts (ads, analytics, consent managers) and do not affect content rendering. However, some JS errors do block lazy loading, break interactive elements, or prevent consent banners from functioning.

**Method**: Use `browser_console_messages` and filter to `error` level.

**Benign pattern filter** (exclude these from the error count):

```
// Ad networks
doubleclick, googlesyndication, adsbygoogle, amazon-adsystem, criteo

// Analytics
gtag, analytics, google-analytics, fbevents, facebook.net/tr, hotjar, clarity.ms

// Consent managers
cookiebot, onetrust, quantcast, cookieconsent, gdpr

// Browser/extension noise
extensions::, chrome-extension://, moz-extension://

// Common benign warnings
Failed to load resource: net::ERR_BLOCKED_BY_CLIENT  (ad blocker)
```

**Genuine error indicators** (always report these):
- Errors from the site's own domain
- `Uncaught TypeError` or `Uncaught ReferenceError` from non-filtered scripts
- Errors mentioning `wp-content`, `wp-includes`, or theme paths
- `Content Security Policy` violations from the site's own resources

**Edge cases**:
- Ad blocker in the browser blocks ad scripts, generating console errors: these are benign, filter them
- Third-party script errors can cascade into site functionality issues: report the count, let the user judge

---

## Check 5: OG Tags

**Severity**: WARNING

**Why WARNING (not BLOCKER)**: Missing OG tags do not affect on-page reader experience. They affect how the post appears when shared on social media -- broken thumbnails, generic titles, missing descriptions. Important for content distribution but not a reader-facing defect.

**Extraction**:
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

**Expected values**:

| Tag | Expected | Notes |
|-----|----------|-------|
| og:title | Non-empty, matches post title | May differ from H1 if SEO plugin overrides |
| og:description | Non-empty, 50-160 chars | Generated by SEO plugin, may differ from meta description |
| og:image | Valid URL, resolves to 200 | Should be the featured image, not the site logo |
| og:url | Matches the canonical post URL | Should not be the homepage URL |
| twitter:card | `summary` or `summary_large_image` | Missing means Twitter uses og:* fallbacks |

**OG Image verification** (optional behavior):
When enabled, navigate to the og:image URL and verify it returns 200. This catches cases where the OG image URL is set but points to a deleted or moved image.

**Edge cases**:
- SEO plugin generates different og:title than the post title: report both, this is expected behavior
- og:image points to site default image instead of featured image: report the URL for manual check
- Multiple og:image tags: report the first one (Facebook/Twitter use the first)

---

## Check 6: Meta Description

**Severity**: WARNING

**Why WARNING**: Missing meta description means search engines auto-generate one from page content, which is usually worse than a crafted description. Not visible to readers on the page itself.

**Extraction**:
```javascript
const desc = document.querySelector('meta[name="description"]');
desc ? desc.getAttribute('content') : null;
```

**Validation**:
- Present and non-empty: PASS (report value and length)
- Present but empty string: WARNING ("meta description is empty")
- Not present: WARNING ("meta description tag missing")
- Length > 160 chars: INFO ("meta description may be truncated in SERPs -- {N} chars")

**Edge cases**:
- Some themes use `og:description` but not `meta[name="description"]`: report the og:description as a note
- Description generated dynamically by JS: may not appear in the initial DOM snapshot if the SEO plugin renders client-side

---

## Check 7: Placeholder/Draft Text

**Severity**: BLOCKER

**Why BLOCKER**: Placeholder text visible to readers is an immediate credibility issue. `[TBD]`, `Lorem ipsum`, or `[TODO]` in a published post signals unfinished content.

**Extraction**:
```javascript
const body = document.body.innerText;
const patterns = ['[TBD]', '[TODO]', 'PLACEHOLDER', 'Lorem ipsum', '[insert', '[FIXME]', 'XXX'];
const found = patterns.filter(p => body.toLowerCase().includes(p.toLowerCase()));
JSON.stringify(found);
```

**Why `innerText` not `textContent`**: `innerText` returns only visible text (respects `display: none`, `visibility: hidden`). Hidden placeholder text in comments or hidden elements is not reader-facing and should not be flagged.

**Edge cases**:
- Article content legitimately discusses placeholder text (e.g., "avoid using [TBD] in production"): this is a false positive. The skill flags it; the user judges context. This is acceptable because false positives are preferable to false negatives for reader-facing text.
- WordPress admin bar or theme elements contain "placeholder" in class names: `innerText` filters these out because class names are not visible text
- Code blocks containing placeholder patterns: these are visible to readers and should be flagged (a code example with `[TODO]` may be intentional, but the user should verify)

---

## Responsive Checks

### Horizontal Overflow

**Severity**: WARNING

**Detection**:
```javascript
document.documentElement.scrollWidth > document.documentElement.clientWidth;
```

**Common causes of overflow at narrow viewports**:
- Tables without `overflow-x: auto` wrapper
- Images without `max-width: 100%`
- Code blocks with long lines and no horizontal scroll
- Fixed-width elements (iframes, embeds)
- Flexbox or grid layouts that do not wrap at small sizes

### Content Visibility

**Severity**: WARNING

**Detection**:
```javascript
const content = document.querySelector('article, .entry-content, .post-content, main');
if (content) {
  const rect = content.getBoundingClientRect();
  JSON.stringify({ visible: rect.width > 0 && rect.height > 0, width: rect.width, height: rect.height });
} else {
  JSON.stringify({ visible: false });
}
```

A content container with zero width or zero height at any breakpoint means the content is hidden -- possibly by a CSS media query that collapses the content area on mobile (a theme bug).
