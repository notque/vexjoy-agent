# WordPress Live Validation — Error Handling

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
