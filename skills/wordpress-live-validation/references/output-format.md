# WordPress Live Validation — Output Format

## Phase 4: REPORT

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
