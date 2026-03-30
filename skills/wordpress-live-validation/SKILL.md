---
name: wordpress-live-validation
description: "Validate published WordPress posts in browser via Playwright."
version: 1.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - mcp__plugin_playwright_playwright__browser_navigate
  - mcp__plugin_playwright_playwright__browser_wait_for
  - mcp__plugin_playwright_playwright__browser_snapshot
  - mcp__plugin_playwright_playwright__browser_evaluate
  - mcp__plugin_playwright_playwright__browser_network_requests
  - mcp__plugin_playwright_playwright__browser_console_messages
  - mcp__plugin_playwright_playwright__browser_resize
  - mcp__plugin_playwright_playwright__browser_take_screenshot
  - mcp__chrome-devtools__navigate_page
  - mcp__chrome-devtools__take_screenshot
  - mcp__chrome-devtools__take_snapshot
  - mcp__chrome-devtools__list_console_messages
  - mcp__chrome-devtools__list_network_requests
  - mcp__chrome-devtools__lighthouse_audit
  - mcp__chrome-devtools__resize_page
routing:
  triggers:
    - validate wordpress post
    - check live post
    - verify published post
    - wordpress post looks right
    - check og tags live
    - responsive check wordpress
    - post rendering check
    - live site validation
  pairs_with:
    - wordpress-uploader
    - pre-publish-checker
    - seo-optimizer
  complexity: Medium
  category: content-publishing
---

# WordPress Live Validation Skill

## Overview

This skill loads a real WordPress post in a Playwright headless browser and verifies that what readers see matches what was uploaded. **The browser is the source of truth** -- REST API success does not guarantee correct rendering.

**Browser backend selection**: Playwright MCP (default) is used for automated validation and CI/CD. Use Chrome DevTools MCP when the user explicitly asks to "check in my browser" or "debug live", or when the task involves Lighthouse audits or performance profiling.

## Instructions

### Constraints (Always Applied)

1. **Read-Only Observation Only**: Never click, type, fill forms, or modify anything on the WordPress site. This is observation-only validation—any write action risks mutating published content.

2. **Evidence-Based Reporting**: Every check result must reference a concrete artifact (DOM value, network response, screenshot path). "Looks fine" is not acceptable. Report what the browser shows, not assumptions.

3. **Non-Blocking Reports**: Failed validation produces a report but does not revert the upload or block the pipeline. The user decides how to act on findings.

4. **Severity Classification** (enforce strictly):
   - **BLOCKER**: Readers see broken content (missing title, broken images, placeholder text, wrong H1)
   - **WARNING**: Degraded quality but functional (missing OG tags, JS errors, responsive overflow)
   - **INFO**: Informational only (rendered values without comparison baseline)
   - Never inflate or deflate—alert fatigue and hidden problems are equal harms.

5. **Browser Availability**: Requires either Playwright MCP or Chrome DevTools MCP. If neither is available, exit in Phase 1 with a skip report. Do not retry.

6. **Default Behaviors** (ON):
   - Run all check categories (content integrity, SEO/social, responsive)
   - Test three breakpoints: mobile (375px), tablet (768px), desktop (1440px)
   - Save screenshots at each breakpoint as evidence
   - Exclude known benign console patterns: ad networks (doubleclick, googlesyndication), analytics (gtag, fbevents), consent managers (cookiebot, onetrust)
   - Try content selectors in order: `article` → `.entry-content` → `.post-content` → `main`

7. **Optional Behaviors** (OFF unless enabled):
   - Draft preview mode (requires authenticated WordPress session)
   - Custom content selector override
   - Strict mode (treat all WARNINGs as BLOCKERs)
   - OG image fetch verification (navigates to og:image URL to check 200 response)

8. **Input Requirements**:
   - WordPress post URL (from wordpress-uploader, direct user input, or `{WORDPRESS_SITE}/?p={post_id}&preview=true`)
   - Optional: expected title (for title match comparison)
   - Optional: expected H2 count (for structure comparison)
   - Optional: custom content selector

---

### Phase 1: NAVIGATE

**Goal**: Load the WordPress post and confirm the content area is present.

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

**GATE**: Page loaded with HTTP 200 (or 30x redirect to 200), content selector found. If 4xx/5xx or no selector found: capture screenshot, report FAIL with HTTP status, STOP. Do not proceed to Phase 2.

---

### Phase 2: VALIDATE

**Goal**: Inspect rendered DOM and network activity for content integrity and SEO completeness. Run all checks without stopping on individual failures.

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

**GATE**: All 7 checks executed, each with severity and evidence. Proceed to Phase 3.

---

### Phase 3: RESPONSIVE CHECK

**Goal**: Verify rendering at three standard breakpoints. Capture visual evidence.

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

**GATE**: Screenshots captured at all three viewports. Overflow and visibility recorded. Proceed to Phase 4.

---

### Phase 4: REPORT

**Goal**: Produce structured pass/fail report with severity counts and evidence artifacts.

**Step 1**: Classify results from Phase 2 and 3. Count BLOCKERs, WARNINGs, INFOs.

**Step 2**: Generate report:

```
===============================================================
 LIVE VALIDATION: {post_url}
===============================================================

 CONTENT INTEGRITY:
   [{status}] Title match: "{rendered_title}" vs "{uploaded_title}"
   [{status}] H2 structure: {rendered_count} rendered / {source_count} expected
   [{status}] Images: {loaded}/{total} loaded, {failed} failed
   [{status}] JS errors: {count} errors detected
   [{status}] Placeholder text: {found_patterns or "none"}

 SEO / SOCIAL:
   [{status}] og:title: "{value}" ({chars} chars)
   [{status}] og:description: "{value}" ({chars} chars)
   [{status}] og:image: {url}
   [{status}] og:url: {url}
   [{status}] twitter:card: {value}
   [{status}] meta description: "{value}" ({chars} chars)

 RESPONSIVE:
   [{status}] Mobile (375px): overflow: {yes/no} — screenshot: {path}
   [{status}] Tablet (768px): overflow: {yes/no} — screenshot: {path}
   [{status}] Desktop (1440px): overflow: {yes/no} — screenshot: {path}

===============================================================
 RESULT: {PASS | FAIL - N blockers, M warnings}
===============================================================

 Screenshots:
   - {mobile_screenshot_path}
   - {tablet_screenshot_path}
   - {desktop_screenshot_path}
```

**Status markers**:
- `[PASS]` = check passed
- `[FAIL]` = BLOCKER severity
- `[WARN]` = WARNING severity
- `[INFO]` = informational
- `[SKIP]` = check could not be performed

**Result classification**:
- **PASS**: Zero BLOCKERs. WARNINGs may be present but do not constitute failure.
- **FAIL**: One or more BLOCKERs. List all blockers after result line.

**GATE**: Report generated with accurate severity counts. Screenshots saved. Result matches blocker tally.

---

## Integration with wordpress-uploader

When invoked after `wordpress-uploader`, this skill acts as an optional **Phase 5: POST-PUBLISH VALIDATION**. The wordpress-uploader output provides:

- `post_url` – the navigation target
- `post_id` – for constructing draft preview URLs (`{WORDPRESS_SITE}/?p={post_id}&preview=true`)
- The `--title` value or extracted H1 – the expected title for comparison

The validation is **non-blocking by default**: a FAIL result produces a report for the user but does not revert the upload. The user decides whether to act on findings.

**Example integration flow**:
```
wordpress-uploader Phase 4 completes
  -> post_url = "https://example.com/my-post/"
  -> post_title = "My Post Title"
  -> invoke wordpress-live-validation with post_url and expected title
  -> report generated
  -> user reviews and decides next action
```

---

## Examples

### Example 1: Post-Upload Validation
User says: "Upload this article and check if it looks right"
1. wordpress-uploader creates the post, returns post_url
2. NAVIGATE: Load post_url, wait for content area
3. VALIDATE: Run all 7 checks
4. RESPONSIVE: Screenshots at 375/768/1440px
5. REPORT: Structured output with pass/fail and screenshots

### Example 2: Standalone Live Check
User says: "Check if https://your-blog.com/posts/my-latest/ looks right"
1. NAVIGATE: Load the URL
2. VALIDATE: All checks run without expected title/H2 (reports rendered values as INFO)
3. RESPONSIVE: Screenshots at all breakpoints
4. REPORT: Structured output

### Example 3: OG Tag Verification
User says: "Check the OG tags on my latest post"
1. NAVIGATE: Load the URL
2. VALIDATE: Full check suite (user focuses on SEO/SOCIAL section)
3. RESPONSIVE: Run for completeness
4. REPORT: Full report

---

## Error Handling

### Error: Playwright MCP Not Available
**Cause**: Playwright MCP server not running or not configured
**Solution**:
1. Detect in Phase 1 when first browser tool call fails
2. Exit with skip report: "Playwright MCP not available. Skipping live validation."
3. Do not retry—browser validation requires Playwright

### Error: Page Returns 4xx/5xx
**Cause**: Wrong URL, post deleted, or WordPress down
**Solution**:
1. Capture screenshot of what browser shows
2. Report HTTP status code
3. STOP at Phase 1 gate—do not proceed to validation
4. If draft preview URL, suggest checking that post exists and is accessible

### Error: Content Selector Not Found
**Cause**: Theme uses non-standard content container, or page loaded but content empty
**Solution**:
1. Selector chain (article → .entry-content → .post-content → main) covers most themes
2. If none match: capture screenshot and DOM snapshot
3. Report FAIL with suggestion: "Content area not found. Try specifying a custom selector."
4. Still attempt Phase 2 checks against full page (OG tags work without content selector)

### Error: Network Timeout on Image Checks
**Cause**: CDN slow, images resolve but download slowly, intermittent network issues
**Solution**:
1. browser_network_requests reports what browser observed—timeout images appear as failed
2. If all images fail: likely network issue rather than broken content
3. Report failure with pattern note: "All {N} images failed—possible network/CDN issue rather than broken content"

### Error: Cookie Banner Blocks Content
**Cause**: GDPR/consent overlay covers content
**Solution**:
1. Phase 1 Step 4 attempts DOM removal of common banners
2. If banner persists (non-standard selector): screenshots may show overlay
3. DOM-level checks (title, H2s, OG tags) still work—they query elements directly
4. Note in report if consent overlay detected but not dismissed

---

## References

For detailed check specifications and Playwright tool usage:
- **Validation Checks**: [references/validation-checks.md](references/validation-checks.md) – severity rationale, edge cases, and extended check specifications
- **Playwright Tools**: [references/playwright-tools.md](references/playwright-tools.md) – MCP tool signatures, usage patterns, and common pitfalls

### Complementary Skills
- [pre-publish-checker](../pre-publish-checker/SKILL.md) – validates source markdown before upload (complementary, not overlapping)
- [wordpress-uploader](../wordpress-uploader/SKILL.md) – uploads content to WordPress (upstream integration)
- [seo-optimizer](../seo-optimizer/SKILL.md) – validates SEO properties against source (data consumer of this skill's output)
- [endpoint-validator](../endpoint-validator/SKILL.md) – similar validation pattern for API endpoints
