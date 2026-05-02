---
name: wordpress-live-validation
description: "Validate published WordPress posts in browser via Playwright."
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
    - publish
    - e2e-testing
  complexity: Medium
  category: content-publishing
---

# WordPress Live Validation Skill

## Overview

Loads a real WordPress post in a Playwright headless browser and verifies rendered output matches what was uploaded. **The browser is the source of truth** — REST API success does not guarantee correct rendering.

**Browser backend**: Playwright MCP (default) for automated validation/CI. Chrome DevTools MCP when user asks to "check in my browser", "debug live", or needs Lighthouse audits.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `validation-checks.md` | Loads detailed guidance from `validation-checks.md`. |
| tasks related to this reference | `playwright-tools.md` | Loads detailed guidance from `playwright-tools.md`. |
| tasks related to this reference | `phase-checks.md` | Loads detailed guidance from `phase-checks.md`. |
| tasks related to this reference | `output-format.md` | Loads detailed guidance from `output-format.md`. |
| example-driven tasks | `examples.md` | Loads detailed guidance from `examples.md`. |
| errors, error handling | `error-handling.md` | Loads detailed guidance from `error-handling.md`. |

## Instructions

### Constraints (Always Applied)

1. **Read-Only Only**: Never click, type, fill forms, or modify anything. Observation-only — write actions risk mutating published content.

2. **Evidence-Based Reporting**: Every result must reference a concrete artifact (DOM value, network response, screenshot path). "Looks fine" is not acceptable.

3. **Non-Blocking Reports**: Failed validation produces a report but does not revert uploads or block the pipeline. User decides.

4. **Severity Classification** (enforce strictly):
   - **BLOCKER**: Broken content visible to readers (missing title, broken images, placeholder text, wrong H1)
   - **WARNING**: Degraded quality but functional (missing OG tags, JS errors, responsive overflow)
   - **INFO**: Informational only (rendered values without comparison baseline)
   - Never inflate or deflate.

5. **Browser Availability**: Requires Playwright MCP or Chrome DevTools MCP. If neither available, exit in Phase 1 with skip report.

6. **Default Behaviors** (ON):
   - Run all check categories (content integrity, SEO/social, responsive)
   - Three breakpoints: mobile (375px), tablet (768px), desktop (1440px)
   - Save screenshots at each breakpoint
   - Exclude known benign console patterns: ad networks, analytics, consent managers
   - Content selectors in order: `article` -> `.entry-content` -> `.post-content` -> `main`

7. **Optional Behaviors** (OFF unless enabled):
   - Draft preview mode (requires authenticated session)
   - Custom content selector override
   - Strict mode (WARNINGs become BLOCKERs)
   - OG image fetch verification

8. **Input Requirements**:
   - WordPress post URL (from uploader, user input, or `{WORDPRESS_SITE}/?p={post_id}&preview=true`)
   - Optional: expected title, expected H2 count, custom content selector

---

### Phase 1: NAVIGATE

**Goal**: Load the post and confirm content area present.

See `references/phase-checks.md` "Phase 1: NAVIGATE" for the 4-step procedure (verify browser MCP, navigate, wait for content selector chain, remove cookie/consent banners).

**GATE**: HTTP 200 (or 30x -> 200), content selector found. If 4xx/5xx or no selector: screenshot, report FAIL, STOP.

---

### Phase 2: VALIDATE

> **Opus 4.7 override:** Run the command. Do not reason about whether it would pass. Execute the check, paste the exit code and output. A verdict without an observed tool result is a guess.

**Goal**: Inspect rendered DOM and network activity for content integrity and SEO completeness. Run all checks without stopping on individual failures.

7 checks documented in `references/phase-checks.md` "Phase 2: VALIDATE":

1. **Title Match** (BLOCKER)
2. **H2 Structure** (WARNING)
3. **Image Loading** (BLOCKER)
4. **JavaScript Console Errors** (WARNING)
5. **OG Tags** (WARNING)
6. **Meta Description** (WARNING)
7. **Placeholder/Draft Text** (BLOCKER)

**GATE**: All 7 checks executed with severity and evidence.

---

### Phase 3: RESPONSIVE CHECK

**Goal**: Verify rendering at three breakpoints with visual evidence.

| Viewport | Width | Height | Represents |
|----------|-------|--------|------------|
| Mobile | 375 | 812 | iPhone-class |
| Tablet | 768 | 1024 | iPad-class |
| Desktop | 1440 | 900 | Standard laptop |

See `references/phase-checks.md` "Phase 3: RESPONSIVE CHECK" for per-viewport procedure (resize, screenshot, overflow check, container visibility).

**GATE**: Screenshots at all three viewports. Overflow and visibility recorded.

---

### Phase 4: REPORT

**Goal**: Structured pass/fail report with severity counts and evidence.

See `references/output-format.md` for report template, status markers, and classification rules.

**GATE**: Report generated with accurate severity counts. Screenshots saved.

---

## Integration with wordpress-uploader

After `wordpress-uploader`, this skill acts as optional **Phase 5: POST-PUBLISH VALIDATION**. See `references/examples.md` for integration flow. Non-blocking by default.

## Examples

See `references/examples.md` for worked examples and wordpress-uploader integration flow.

## Error Handling

See `references/error-handling.md` for the full error matrix.

---

## References

- **Validation Checks**: [references/validation-checks.md](references/validation-checks.md) — severity rationale, edge cases, extended specs
- **Playwright Tools**: [references/playwright-tools.md](references/playwright-tools.md) — MCP tool signatures, usage patterns, pitfalls
- **Phase Check Details**: [references/phase-checks.md](references/phase-checks.md) — Phase 1/2/3 step-by-step with JS snippets
- **Output Format**: [references/output-format.md](references/output-format.md) — report template, status markers, classification
- **Examples**: [references/examples.md](references/examples.md) — worked examples and uploader integration
- **Error Handling**: [references/error-handling.md](references/error-handling.md) — browser availability, HTTP failures, selector misses, timeouts, cookie banners

### Complementary Skills
- [pre-publish-checker](../pre-publish-checker/SKILL.md) — validates source markdown before upload
- [wordpress-uploader](../wordpress-uploader/SKILL.md) — uploads content to WordPress (upstream)
- [seo-optimizer](../seo-optimizer/SKILL.md) — validates SEO properties (data consumer)
- [endpoint-validator](../endpoint-validator/SKILL.md) — similar validation pattern for APIs
