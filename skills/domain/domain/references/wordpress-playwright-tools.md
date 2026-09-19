# WordPress Live Validation -- Playwright MCP Tool Guide

Reference for the 8 Playwright MCP tools used by this skill. Covers tool signatures, usage patterns, common pitfalls, and phase mapping.

---

## Tool Overview

This skill uses 8 of the 18 available Playwright MCP tools. All interactions are **read-only** -- no clicking, typing, or form submission.

| Tool | Phases | Purpose |
|------|--------|---------|
| `browser_navigate` | 1 | Load the post URL |
| `browser_wait_for` | 1 | Wait for the content area selector |
| `browser_snapshot` | 2 | Capture DOM state as structural evidence |
| `browser_evaluate` | 1, 2, 3 | Run JavaScript to extract data from the rendered page |
| `browser_network_requests` | 2 | Inspect image loading status (4xx/5xx detection) |
| `browser_console_messages` | 2 | Detect JavaScript errors |
| `browser_resize` | 3 | Switch viewport between mobile/tablet/desktop |
| `browser_take_screenshot` | 3 | Visual evidence at each breakpoint |

---

## Tool Details

### browser_navigate

**Purpose**: Load a URL in the browser tab.

**When to use**: Phase 1 to load the post URL. Optionally in Phase 2 to verify the og:image URL resolves (if OG image fetch verification is enabled).

**Usage pattern**:
```
Navigate to: {post_url}
```

**Key behaviors**:
- Waits for the page to finish loading (network idle) before returning
- Returns the page title and URL after navigation
- Follows redirects (301/302) automatically
- If the URL returns 4xx/5xx, the navigation still "succeeds" from the tool's perspective -- the browser loaded the error page

**Pitfalls**:
- Do not assume navigation failure means the page does not exist. Check the rendered content.
- If the URL redirects to a login page, the navigation succeeds but the content is wrong. Detect this by checking for the content selector in the next step.
- HTTPS certificate errors may cause navigation to fail. Report the error clearly.

---

### browser_wait_for

**Purpose**: Wait for a CSS selector to appear in the DOM before proceeding.

**When to use**: Phase 1 after navigation, to confirm the content area loaded.

**Usage pattern**:
```
Wait for selector: article
```

Try selectors in order: `article` -> `.entry-content` -> `.post-content` -> `main`

**Key behaviors**:
- Blocks until the selector appears or timeout is reached
- Default timeout is typically 30 seconds
- Returns when the element exists in the DOM (does not guarantee visibility)

**Pitfalls**:
- If none of the default selectors match, the page may have loaded correctly but uses a non-standard theme. Capture a screenshot and DOM snapshot for manual inspection.
- The element being in the DOM does not mean it is visible. A `display: none` element passes `wait_for` but is not rendered. Phase 3 content visibility check catches this.
- Do not wait for selectors that may appear only after user interaction (e.g., modal content, tab panels).

---

### browser_snapshot

**Purpose**: Capture the current DOM state as text, showing the page structure and content.

**When to use**: Phase 2 as evidence capture after running validation checks. Provides a structural record of what the page looked like at validation time.

**Key behaviors**:
- Returns the accessibility tree / DOM structure as text
- Includes element roles, text content, and basic structure
- Does not include CSS styles or computed layout information
- Useful for verifying element existence and text content

**Pitfalls**:
- The snapshot is a text representation, not a visual one. Use `browser_take_screenshot` for visual evidence.
- Large pages produce large snapshots. The snapshot is evidence for the report, not the primary validation mechanism.
- Snapshot content may differ from `browser_evaluate` results because it represents the accessibility tree rather than raw DOM.

---

### browser_evaluate

**Purpose**: Execute JavaScript in the browser context and return the result.

**When to use**: Throughout Phases 1-3 for DOM extraction, data collection, and state checks.

**Usage patterns**:

**Extract a single value:**
```javascript
document.querySelector('h1').textContent.trim()
```

**Extract multiple values as JSON:**
```javascript
JSON.stringify({
  title: document.querySelector('h1')?.textContent?.trim(),
  h2Count: document.querySelectorAll('h2').length
})
```

**Check a boolean condition:**
```javascript
document.documentElement.scrollWidth > document.documentElement.clientWidth
```

**Remove DOM elements (cookie banners):**
```javascript
document.querySelectorAll('[class*="cookie"], [class*="consent"]').forEach(el => el.remove())
```

**Key behaviors**:
- Returns the result of the last expression evaluated
- Can access the full browser DOM API
- Runs synchronously in the page context
- Can modify the DOM (used only for cookie banner removal in this skill)

**Pitfalls**:
- Always use optional chaining (`?.`) when querying elements that may not exist. A null reference error crashes the evaluation.
- `JSON.stringify` is required for returning objects. Without it, the tool may return `[object Object]`.
- Long-running evaluations may timeout. Keep JS execution quick -- no loops over thousands of elements.
- `innerText` vs `textContent`: Use `innerText` when you want visible text only (placeholder check). Use `textContent` when you want all text including hidden elements.
- DOM modifications persist for the session. Removing cookie banners affects all subsequent operations (which is the desired behavior).

---

### browser_network_requests

**Purpose**: List network requests made by the page, including their URLs and status codes.

**When to use**: Phase 2 to check image loading status.

**Key behaviors**:
- Returns all network requests made since the page started loading
- Each entry includes the URL, status code, and resource type
- Includes requests for CSS, JS, images, fonts, and other resources

**Image filtering strategy**:
Filter requests where:
1. URL path ends with `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.svg`, `.avif`
2. OR resource type is `image`

Then classify by status code:
- 200-299: loaded
- 301-302: followed redirect (check final status)
- 4xx: broken (BLOCKER)
- 5xx: server error (BLOCKER)

**Pitfalls**:
- Lazy-loaded images may not appear in network requests if they are below the fold. Consider scrolling to the bottom of the page before checking, or accept incomplete coverage.
- Ad/tracking pixels (1x1 transparent GIFs) are technically images but not content images. Filter by size or domain if noise is excessive.
- Some CDNs return 200 with a placeholder image instead of 404. These are harder to detect -- the status code looks fine but the content is wrong. Visual inspection (screenshots) catches these.
- Cached resources may not appear as new network requests on revisit.

---

### browser_console_messages

**Purpose**: Retrieve JavaScript console messages (log, warn, error).

**When to use**: Phase 2 to detect JavaScript errors on the page.

**Key behaviors**:
- Returns all console messages since page load
- Each message has a level (log, warn, error, info) and text content
- Captures messages from all scripts (first-party and third-party)

**Error filtering strategy**:
1. Filter to `error` level only
2. Exclude messages matching benign patterns (see validation-checks.md Check 4)
3. Count remaining errors
4. Report message text for any genuine errors

**Pitfalls**:
- Third-party scripts (ads, analytics) generate the majority of console errors on most WordPress sites. Without filtering, the error count is meaningless.
- Some errors are transient (race conditions during page load). A single run captures whatever happened during this particular load.
- Console messages accumulate during the session. If multiple navigations happen (e.g., OG image verification), messages from all navigations are included. Filter by relevance if needed.
- The benign pattern filter is intentionally conservative (exclude known noise). Unknown errors are reported rather than silently filtered.

---

### browser_resize

**Purpose**: Change the browser viewport dimensions.

**When to use**: Phase 3 to test responsive layout at mobile (375x812), tablet (768x1024), and desktop (1440x900).

**Usage pattern**:
```
Resize to: 375x812
```

**Key behaviors**:
- Changes viewport width and height immediately
- Page content reflows according to CSS media queries
- Does not trigger a page reload -- the same DOM is reflowed
- Returns confirmation of the new viewport size

**Pitfalls**:
- After resizing, allow a brief moment for CSS transitions and reflow before taking screenshots or checking overflow. The browser_evaluate call acts as an implicit wait since it runs after reflow.
- Some themes use JavaScript-based responsive logic (not just CSS media queries). These may not trigger on resize without a page reload. Most WordPress themes use CSS media queries, so this is rare.
- The order of resizing matters for screenshots. Go from smallest to largest (mobile -> tablet -> desktop) to capture the most common user experience first.

---

### browser_take_screenshot

**Purpose**: Capture a visual screenshot of the current browser viewport.

**When to use**: Phase 3 at each breakpoint for visual evidence. Also in Phase 1 if the page fails to load (error evidence).

**Key behaviors**:
- Captures the visible viewport area
- Returns the screenshot as an image (viewable in Claude's response)
- Screenshots capture the current visual state including any overlays, modals, or CSS effects

**Pitfalls**:
- Screenshots capture only the above-the-fold content at the current scroll position. Long articles require scrolling for full coverage. For this skill, above-the-fold is sufficient -- the purpose is layout validation, not full-page capture.
- Cookie banners or consent overlays appear in screenshots unless removed first (Phase 1 Step 4).
- Dark mode themes may make screenshots harder to interpret visually. The DOM-level checks are not affected by visual themes.
- Screenshot file paths should be noted in the report for reference.

---

## Tools NOT Used

These Playwright MCP tools are available but intentionally excluded:

| Tool | Reason for Exclusion |
|------|---------------------|
| `browser_click` | Read-only validation -- no clicking |
| `browser_fill_form` | No form interaction needed |
| `browser_type` | No typing needed |
| `browser_select_option` | No dropdown interaction needed |
| `browser_drag` | No drag interaction needed |
| `browser_hover` | No hover interaction needed |
| `browser_press_key` | No keyboard interaction needed |
| `browser_handle_dialog` | No expected dialogs on published posts |
| `browser_navigate_back` | Single-page validation, no navigation history |
| `browser_tabs` | Single-tab workflow |
| `browser_file_upload` | No file uploads needed |
| `browser_install` | Playwright assumed pre-installed |
| `browser_close` | Handled by MCP server lifecycle |
| `browser_run_code` | `browser_evaluate` covers all JS execution needs |

If any of these tools are invoked during validation, it is a signal that the skill is doing something outside its read-only scope. Review the workflow.

---

## Availability Detection

The Playwright MCP server may not be available in all Claude Code sessions. Detection strategy:

1. Attempt `browser_navigate` in Phase 1 as the first operation
2. If the tool call fails with a "tool not found" or connection error, Playwright is not available
3. Emit a skip report and exit -- do not retry
4. The skip report should state: "Playwright MCP not available. Live validation skipped. Configure the Playwright MCP server to enable browser-based validation."

Do not attempt to install or configure Playwright from within the skill. That is the user's responsibility.
