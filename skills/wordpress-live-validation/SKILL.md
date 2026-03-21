---
name: wordpress-live-validation
description: |
  Validate a published or draft-preview WordPress post in a real browser using
  Playwright. Checks rendered title, heading structure, image loading, OG/meta
  tags, JavaScript errors, and responsive layout at mobile/tablet/desktop
  breakpoints. When Chrome DevTools MCP is available, can use it for live browser
  inspection as an alternative to Playwright. Use for "validate wordpress post",
  "check live post", "verify published post", "wordpress post looks right",
  "check og tags", or "responsive check wordpress". Do NOT use for source
  markdown validation (use pre-publish-checker), SEO keyword analysis
  (use seo-optimizer), or uploading content (use wordpress-uploader).
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

## Operator Context

This skill operates as an operator for post-publish browser validation, configuring Claude's behavior for read-only inspection of rendered WordPress pages. It uses the Playwright MCP server to load a real browser, extract DOM state, capture screenshots, and verify that what the reader sees matches what was uploaded. **The browser is the source of truth** -- REST API success does not guarantee correct rendering.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before validation
- **Read-Only**: Never click, type, fill forms, or modify anything on the WordPress site. This is observation-only validation. Why: any write action risks mutating published content or triggering unintended side effects.
- **Evidence-Based Reporting**: Every check result must reference a concrete artifact (DOM value, network response, screenshot path). Why: "looks fine" is not a validation result -- the report consumer needs verifiable evidence.
- **Non-Blocking by Default**: Failed validation produces a report but does not revert the upload or block the pipeline. Why: the user decides how to act on findings; automated rollback is a separate, riskier concern.
- **Severity Accuracy**: BLOCKER means readers see broken content. WARNING means degraded quality. INFO means informational. Never inflate or deflate severity. Why: inflated severity causes alert fatigue; deflated severity hides real problems.

### Browser Backend Selection

This skill supports two browser backends:

| Backend | When to Use | How |
|---------|-------------|-----|
| **Playwright MCP** (default) | Automated validation, repeatable checks, CI/CD | Headless browser, deterministic |
| **Chrome DevTools MCP** (alternative) | Live debugging, user watching the browser, performance profiling | User's real Chrome browser |

**Selection logic**: Use Chrome DevTools MCP when:
1. The user explicitly asks to "check in my browser" or "debug live"
2. The task involves Lighthouse audits or performance profiling
3. The user has Chrome DevTools MCP connected AND is actively debugging

Otherwise, default to Playwright MCP for deterministic, repeatable validation.

### Default Behaviors (ON unless disabled)
- **Full Validation**: Run all check categories (content integrity, SEO/social, responsive)
- **Three Breakpoints**: Test mobile (375px), tablet (768px), desktop (1440px)
- **Screenshot Capture**: Save screenshots at each breakpoint as evidence artifacts
- **Console Error Filtering**: Exclude known benign patterns (ad-network noise, analytics warnings) from JS error count
- **Content Selector Fallback**: Try `article`, `.entry-content`, `.post-content`, `main` in order if no selector is specified

### Optional Behaviors (OFF unless enabled)
- **Draft Preview Mode**: Navigate to `?preview=true` URL with authentication (requires WordPress session)
- **Custom Content Selector**: Override the default content area selector chain
- **Strict Mode**: Treat all WARNINGs as BLOCKERs
- **OG Image Fetch Verification**: Navigate to the og:image URL to confirm it returns 200 (adds an extra navigation step)

## What This Skill CAN Do
- Load a published WordPress post in a headless browser and verify it renders
- Extract and compare the rendered title against the uploaded title
- Verify H2 heading structure survived the theme rendering pipeline
- Detect broken images (4xx/5xx responses) via network request inspection
- Extract OG tags (og:title, og:description, og:image, og:url, twitter:card) from rendered `<head>`
- Detect JavaScript console errors that may affect reader experience
- Capture responsive screenshots at mobile, tablet, and desktop breakpoints
- Detect horizontal overflow at each viewport width
- Detect placeholder/draft text that should not be visible to readers
- Produce a structured pass/fail report with evidence artifacts

## What This Skill CANNOT Do
- **Modify WordPress content**: Read-only inspection; use wordpress-uploader for edits
- **Validate source markdown**: Use pre-publish-checker for pre-upload validation
- **Visual regression testing**: No pixel-level comparison against golden baselines
- **Performance testing**: Lighthouse audits available via Chrome DevTools MCP; no load time benchmarking or Core Web Vitals tracking
- **Cross-browser testing**: Playwright runs Chromium only; Chrome DevTools MCP runs Chrome only
- **Authenticate to wp-admin**: Draft preview requires the user to provide an authenticated session or use published posts
- **Work without a browser MCP**: Requires either Playwright MCP or Chrome DevTools MCP. If neither is available, the skill exits with a skip report

---

## Instructions

### Input

The skill requires a WordPress post URL. This comes from one of:

1. **wordpress-uploader output**: The `post_url` from a successful upload (primary integration path)
2. **User-provided URL**: Any WordPress post URL provided directly
3. **Constructed preview URL**: `{WORDPRESS_SITE}/?p={post_id}&preview=true` for draft validation

Optional inputs:
- **Expected title**: The title passed to `wordpress-upload.py` -- used for title match comparison. If not provided, the title check reports the rendered title without comparison.
- **Expected H2 count**: Number of H2 headings in the source markdown. If not provided, the H2 check reports the rendered count without comparison.
- **Content selector**: CSS selector for the main content area (default: tries `article`, `.entry-content`, `.post-content`, `main` in order).

---

### Phase 1: NAVIGATE

**Goal**: Load the WordPress post in a browser and confirm the content area is present.

**Step 1: Check Playwright availability**

Before any browser operation, verify the Playwright MCP tools are accessible by attempting a simple navigation. If the tools are unavailable, exit immediately with a skip report rather than failing cryptically in later phases.

**Step 2: Navigate to the post URL**

Use `browser_navigate` to load the target URL. The URL must be a full HTTPS URL.

**Step 3: Wait for content area**

Use `browser_wait_for` with the content selector. Try selectors in order until one matches:
1. `article` (most WordPress themes)
2. `.entry-content` (classic themes)
3. `.post-content` (some premium themes)
4. `main` (fallback)

If a custom selector was provided, use that instead of the default chain.

**Step 4: Dismiss cookie/consent banners (if present)**

Some WordPress sites show cookie consent overlays that obscure content. Use `browser_evaluate` to check for common consent banner selectors and dismiss them:

```javascript
// Common cookie banner selectors
const banners = document.querySelectorAll(
  '[class*="cookie"], [class*="consent"], [id*="cookie"], [id*="consent"], .gdpr-banner'
);
banners.forEach(b => b.remove());
```

This is DOM removal, not clicking -- it does not interact with the site's consent tracking, it just clears the visual overlay for screenshot accuracy.

**GATE**: Page loaded with HTTP 200 (or 30x redirect to 200), content selector found. If the page returns 4xx/5xx or the content selector is not found after waiting, capture a screenshot of the current state, report FAIL with the HTTP status and screenshot path, and STOP. Do not proceed to Phase 2.

---

### Phase 2: VALIDATE

**Goal**: Inspect the rendered DOM and network activity for content integrity and SEO completeness.

Run all checks and collect results. Do not stop on individual failures -- collect everything and report in Phase 4.

**Check 1: Title Match** (Severity: BLOCKER)

```javascript
// Extract rendered title
const titleEl = document.querySelector('h1, .entry-title, .post-title');
titleEl ? titleEl.textContent.trim() : null;
```

If an expected title was provided, compare (case-insensitive, trimmed). Mark PASS if they match, BLOCKER if they differ or no title element is found.

If no expected title was provided, report the rendered title as INFO.

**Check 2: H2 Structure** (Severity: WARNING)

```javascript
// Extract all H2 headings
const h2s = Array.from(document.querySelectorAll('h2')).map(h => h.textContent.trim());
JSON.stringify(h2s);
```

If an expected H2 count was provided, compare. Mark PASS if counts match, WARNING if they differ. Always report the rendered H2 texts for manual inspection.

**Check 3: Image Loading** (Severity: BLOCKER)

Use `browser_network_requests` and filter for image requests (URLs ending in common image extensions or with image MIME types). Check each response status:
- 2xx: loaded successfully
- 4xx/5xx: BLOCKER -- image is broken for readers

Report total images, loaded count, and failed count with URLs of any failures.

**Check 4: JavaScript Console Errors** (Severity: WARNING)

Use `browser_console_messages` and filter to `error` level. Exclude known benign patterns:
- Ad network errors (doubleclick, googlesyndication, adsbygoogle)
- Analytics warnings (gtag, analytics, fbevents)
- Consent manager noise (cookiebot, onetrust, quantcast)
- Browser extension artifacts

Report count of genuine errors and their messages.

**Check 5: OG Tags** (Severity: WARNING)

```javascript
// Extract OG and social meta tags
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

Mark WARNING for any missing OG tag. Report each tag's value and character count.

**Check 6: Meta Description** (Severity: WARNING)

```javascript
const desc = document.querySelector('meta[name="description"]');
desc ? desc.getAttribute('content') : null;
```

Mark PASS if present and non-empty, WARNING if missing or empty. Report value and character count.

**Check 7: Placeholder/Draft Text** (Severity: BLOCKER)

```javascript
// Search visible text for placeholder patterns
const body = document.body.innerText;
const patterns = ['[TBD]', '[TODO]', 'PLACEHOLDER', 'Lorem ipsum', '[insert', '[FIXME]'];
const found = patterns.filter(p => body.toLowerCase().includes(p.toLowerCase()));
JSON.stringify(found);
```

Mark BLOCKER if any placeholder patterns are found in the visible page text. Mark PASS if none found.

**GATE**: All 7 checks executed. Each has a severity classification and evidence value. Proceed to Phase 3.

---

### Phase 3: RESPONSIVE CHECK

**Goal**: Verify the post renders correctly at three standard breakpoints. Capture visual evidence.

Test each viewport in sequence:

| Viewport | Width | Height | Represents |
|----------|-------|--------|------------|
| Mobile | 375 | 812 | iPhone-class |
| Tablet | 768 | 1024 | iPad-class |
| Desktop | 1440 | 900 | Standard laptop |

For each viewport:

**Step 1**: Use `browser_resize` to set the viewport dimensions.

**Step 2**: Use `browser_take_screenshot` to capture the rendered page. Save to a known path for the report.

**Step 3**: Check for horizontal overflow:

```javascript
document.documentElement.scrollWidth > document.documentElement.clientWidth;
```

Mark WARNING if overflow detected -- content extends beyond the viewport, which usually means a table, image, or code block is not responsive.

**Step 4**: Verify content container is visible and has dimensions:

```javascript
const content = document.querySelector('article, .entry-content, .post-content, main');
if (content) {
  const rect = content.getBoundingClientRect();
  JSON.stringify({ visible: rect.width > 0 && rect.height > 0, width: rect.width, height: rect.height });
} else {
  JSON.stringify({ visible: false });
}
```

Mark WARNING if the content container is not visible or has zero dimensions at any breakpoint.

**GATE**: Screenshots captured at all three viewports. Overflow status and visibility recorded for each. Proceed to Phase 4.

---

### Phase 4: REPORT

**Goal**: Produce a structured pass/fail report with severity counts and evidence artifacts.

**Step 1: Classify results**

Count BLOCKERs, WARNINGs, and INFO items from Phase 2 and Phase 3.

**Step 2: Generate report**

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
- `[PASS]` -- check passed
- `[FAIL]` -- BLOCKER severity, readers see broken content
- `[WARN]` -- WARNING severity, degraded but not broken
- `[INFO]` -- informational, no action needed
- `[SKIP]` -- check could not be performed (explain why)

**Result classification**:
- **PASS**: Zero BLOCKERs. WARNINGs may be present but do not constitute failure.
- **FAIL**: One or more BLOCKERs. List all BLOCKERs after the result line.

**GATE**: Report generated with accurate severity counts. Screenshots saved. Result matches the blocker tally.

---

## Integration with wordpress-uploader

When invoked after `wordpress-uploader`, this skill acts as an optional **Phase 5: POST-PUBLISH VALIDATION**. The wordpress-uploader output provides:

- `post_url` -- the navigation target
- `post_id` -- for constructing draft preview URLs (`{WORDPRESS_SITE}/?p={post_id}&preview=true`)
- The `--title` value or extracted H1 -- the expected title for comparison

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
Actions:
1. wordpress-uploader creates the post, returns post_url
2. NAVIGATE: Load post_url, wait for content area
3. VALIDATE: Run all 7 checks against rendered page
4. RESPONSIVE: Screenshots at 375/768/1440px
5. REPORT: Structured output with pass/fail and screenshots

### Example 2: Standalone Live Check
User says: "Check if https://your-blog.com/posts/my-latest/ looks right"
Actions:
1. NAVIGATE: Load the URL directly
2. VALIDATE: All checks run without expected title/H2 comparison (reports rendered values as INFO)
3. RESPONSIVE: Screenshots at all breakpoints
4. REPORT: Structured output

### Example 3: OG Tag Verification
User says: "Check the OG tags on my latest post"
Actions:
1. NAVIGATE: Load the URL
2. VALIDATE: Full check suite, but user is primarily interested in OG results
3. RESPONSIVE: Still run for completeness
4. REPORT: Full report, user focuses on SEO/SOCIAL section

---

## Error Handling

### Error: Playwright MCP Not Available
**Cause**: Playwright MCP server is not running or not configured in the Claude Code session
**Solution**:
1. The skill detects this in Phase 1 when the first browser tool call fails
2. Exit immediately with a skip report: "Playwright MCP not available. Skipping live validation."
3. Do not retry or attempt workarounds -- browser validation requires Playwright

### Error: Page Returns 4xx/5xx
**Cause**: Post URL is wrong, post was deleted, or WordPress is down
**Solution**:
1. Capture a screenshot of whatever the browser shows
2. Report the HTTP status code
3. STOP at Phase 1 gate -- do not proceed to validation
4. If this was a draft preview URL, suggest the user check that the post exists and is accessible

### Error: Content Selector Not Found
**Cause**: Theme uses a non-standard content container, or page loaded but content area is empty
**Solution**:
1. The selector chain (article -> .entry-content -> .post-content -> main) covers most themes
2. If none match, capture a screenshot and DOM snapshot for manual inspection
3. Report as FAIL with suggestion: "Content area not found. Try specifying a custom selector."
4. Still attempt Phase 2 checks against the full page (some checks like OG tags work without a content selector)

### Error: Network Timeout on Image Checks
**Cause**: CDN slow, image URLs resolve but download slowly, or intermittent network issues
**Solution**:
1. browser_network_requests reports what the browser observed -- timeout images appear as failed
2. If all images fail, this likely indicates a network issue rather than broken images
3. Report the failure but note the pattern: "All {N} images failed -- possible network/CDN issue rather than broken content"

### Error: Cookie Banner Blocks Content
**Cause**: GDPR/consent overlay covers the content area, affecting screenshots
**Solution**:
1. Phase 1 Step 4 attempts to remove common cookie banners via DOM manipulation
2. If the banner persists (non-standard selector), screenshots may show the overlay
3. The DOM-level checks (title, H2s, OG tags) still work because they query elements directly
4. Note in the report if a consent overlay was detected but could not be dismissed

---

## Anti-Patterns

### Anti-Pattern 1: Clicking Consent Banners Instead of Removing
**What it looks like**: Using browser_click to accept cookie consent
**Why wrong**: Clicking "Accept" activates cookie tracking, modifies the site's consent state for this session, and may trigger additional scripts that affect validation results. This skill is read-only.
**Do instead**: Remove the banner DOM element with browser_evaluate. This clears the visual overlay without interacting with the consent system.

### Anti-Pattern 2: Treating All Warnings as Blockers
**What it looks like**: Reporting FAIL because OG tags are missing or H2 count differs
**Why wrong**: Missing OG tags degrade social sharing but do not break the reader experience. Severity inflation causes the user to ignore the report.
**Do instead**: Classify accurately. BLOCKERs = readers see broken content (missing images, wrong title, placeholder text). WARNINGs = degraded quality (missing OG, JS errors, overflow).

### Anti-Pattern 3: Skipping Responsive Checks
**What it looks like**: "Content looks fine at desktop, skipping mobile/tablet"
**Why wrong**: Mobile is often 50%+ of traffic. A table that overflows at 375px is invisible at 1440px.
**Do instead**: Always run all three breakpoints. The screenshots are cheap and the overflow check catches layout bugs that only manifest at narrow widths.

### Anti-Pattern 4: Validating Draft Preview Without Authentication
**What it looks like**: Navigating to `?preview=true` URL expecting it to render the draft
**Why wrong**: WordPress draft previews require an authenticated session. Without auth cookies, the URL either redirects to login or shows a 404.
**Do instead**: For draft validation, either authenticate first (if the user provides credentials) or wait until the post is published. Report clearly if the preview URL is inaccessible.

### Anti-Pattern 5: Retrying Indefinitely on Playwright Failure
**What it looks like**: Attempting browser operations 5+ times when the Playwright server is down
**Why wrong**: If Playwright MCP is not available, no number of retries will fix it. This wastes time and context.
**Do instead**: Try once in Phase 1. If it fails, emit a skip report and exit. The user needs to fix their Playwright MCP configuration, not wait for retries.

---

## Anti-Rationalization

### Domain-Specific Rationalizations

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "The upload succeeded, so the page is fine" | REST API 201 says nothing about rendered HTML, theme CSS, or CDN delivery | Run the browser validation |
| "OG tags are a nice-to-have" | Missing og:image means social shares show a generic placeholder or broken thumbnail | Report as WARNING with the actual rendered values |
| "Mobile overflow is minor" | Mobile may be the majority of the audience; overflow breaks reading experience | Always test at 375px and flag overflow |
| "Console errors are just ad noise" | Some console errors indicate broken rendering, blocked resources, or failed lazy-loading | Filter known benign patterns but report genuine errors |
| "Screenshots are enough evidence" | Screenshots show what it looks like, not what the DOM contains; both are needed | Capture screenshots AND extract DOM values |
| "One breakpoint is representative" | Desktop, tablet, and mobile have fundamentally different CSS layouts | Test all three breakpoints |
| "Playwright is probably available" | Tool availability should be verified, not assumed | Check in Phase 1 before doing any work |

---

## Blocker Criteria

STOP and ask the user (do NOT proceed autonomously) when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| URL requires authentication | Cannot validate without credentials | "This URL requires login. Can you provide an authenticated session, or should I validate after publish?" |
| All images fail simultaneously | Likely network issue, not content issue | "All {N} images returned errors. This may be a CDN/network issue rather than broken content. Proceed with report or retry?" |
| Playwright MCP unavailable | Cannot perform any browser checks | "Playwright MCP is not available. Live validation requires browser access. Skip validation?" |

### Never Guess On
- Whether a page is publicly accessible vs requiring authentication
- Whether console errors are benign (use the filter list, report the rest)
- Whether overflow at a breakpoint is "acceptable" (always report it, let the user decide)

---

## References

For detailed check specifications and Playwright tool usage:
- **Validation Checks**: [references/validation-checks.md](references/validation-checks.md) -- severity rationale, edge cases, and extended check specifications
- **Playwright Tools**: [references/playwright-tools.md](references/playwright-tools.md) -- MCP tool signatures, usage patterns, and common pitfalls

### Complementary Skills
- [pre-publish-checker](../pre-publish-checker/SKILL.md) -- validates source markdown before upload (complementary, not overlapping)
- [wordpress-uploader](../wordpress-uploader/SKILL.md) -- uploads content to WordPress (upstream integration)
- [seo-optimizer](../seo-optimizer/SKILL.md) -- validates SEO properties against source (data consumer of this skill's output)
- [endpoint-validator](../endpoint-validator/SKILL.md) -- similar validation pattern for API endpoints

### Shared Patterns
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) -- prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) -- pre-completion checks
