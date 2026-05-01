# PageSpeed Insights Workflow

Machine-measured site performance, SEO, accessibility, and best-practices analysis using the Google PageSpeed Insights API. Complements the manual SEO analysis in `seo.md` with quantitative data from Lighthouse.

**Integration:** Run PageSpeed analysis as the data-gathering step before or after manual SEO optimization. The scores and failing audits provide measurable baselines that the SEO workflow's ASSESS phase cannot capture on its own.

---

## Instructions

### Phase 1: SCAN — Capture Baseline Scores

**Goal**: Get current PageSpeed Insights data for both mobile and desktop.

**Step 1: Run the pagespeed script**

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/pagespeed.py --url <target-url>
```

This runs both mobile and desktop by default. For a single strategy:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/pagespeed.py --url <target-url> --strategy mobile
```

**Step 2: Save the baseline for comparison**

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/pagespeed.py --url <target-url> --format markdown --output /tmp/psi-baseline.md
```

**Step 3: Record scores**

Document the current state:
```
Mobile:  Performance XX | SEO XX | Accessibility XX | Best Practices XX
Desktop: Performance XX | SEO XX | Accessibility XX | Best Practices XX
```

**Gate**: Both mobile and desktop results captured. Failing audits listed. Do not proceed to Phase 2 without complete data.

### Phase 2: DIAGNOSE — Categorize Issues by Impact

**Goal**: Separate fixable content-level issues from infrastructure-level issues.

**Step 1: Review failing audits from the scan**

For each failing audit, classify it:

| Classification | Description | Action |
|---------------|-------------|--------|
| Content-level | Fixable by editing Hugo content or front matter | Fix in Phase 3 |
| Theme-level | Requires Hugo theme or layout changes | Fix if theme is under your control |
| Infrastructure | Hosting, CDN, server config | Report to user, cannot fix in content |
| Informational | Low-impact or cosmetic | Note but deprioritize |

**Step 2: Cross-reference with SEO workflow**

If the SEO workflow (`seo.md`) has already been run on this content, merge findings. PageSpeed Insights catches what manual analysis misses:
- Missing meta descriptions flagged by PSI confirm the SEO workflow gap
- Image optimization issues provide specific byte savings
- Core Web Vitals data quantifies the user experience impact

**Step 3: Prioritize by impact**

1. Core Web Vitals failures (LCP, FID/INP, CLS) — direct ranking factor
2. SEO audit failures — directly affect search visibility
3. Accessibility failures — affect usability and legal compliance
4. Best practices failures — general quality signal

**Gate**: Issues classified and prioritized. Content-level fixes identified with specific remediation steps.

### Phase 3: FIX — Apply Content-Level Improvements

**Goal**: Fix issues that can be resolved through Hugo content and front matter changes.

Apply fixes from the mapping table below. Only modify content that the user has confirmed.

**Constraint**: Do not modify theme files, hosting configuration, or external dependencies without explicit user approval. These changes have broader impact than content edits.

#### PSI Audit to Hugo Fix Mapping

| PSI Audit | Category | Fixable in Hugo? | How to Fix |
|-----------|----------|------------------|------------|
| `meta-description` | SEO | Yes | Add `description` to front matter |
| `document-title` | SEO | Yes | Ensure `title` in front matter is descriptive |
| `hreflang` | SEO | Maybe | Add hreflang links in Hugo template or config |
| `canonical` | SEO | Yes | Set `canonical` in front matter or Hugo config |
| `robots-txt` | SEO | Yes | Create or fix `static/robots.txt` |
| `image-alt` | Accessibility | Yes | Add `alt` text to all images in content |
| `html-has-lang` | Accessibility | Maybe | Set `lang` attribute in theme `baseof.html` |
| `color-contrast` | Accessibility | Maybe | Theme CSS change |
| `heading-order` | Accessibility | Yes | Fix heading hierarchy in content (no H1-to-H3 skips) |
| `link-name` | Accessibility | Yes | Add descriptive text to links (no bare URLs) |
| `render-blocking-resources` | Performance | Maybe | Defer scripts, inline critical CSS in theme |
| `unused-css-rules` | Performance | Maybe | PurgeCSS in Hugo build pipeline |
| `uses-responsive-images` | Performance | Yes | Use Hugo image processing (`{{ $image.Resize }}`) |
| `offscreen-images` | Performance | Yes | Add `loading="lazy"` to below-fold images |
| `uses-optimized-images` | Performance | Yes | Use Hugo image processing with quality settings |
| `modern-image-formats` | Performance | Yes | Use Hugo image processing to convert to WebP |
| `unminified-css` | Performance | Maybe | Hugo's `minify` option in config |
| `unminified-javascript` | Performance | Maybe | Hugo's `minify` option in config |
| `uses-text-compression` | Performance | No | Server/CDN configuration |
| `uses-long-cache-ttl` | Performance | No | Server/CDN configuration |
| `server-response-time` | Performance | No | Hosting provider issue |

**Gate**: All content-level fixes applied. No theme or infrastructure changes made without user approval.

### Phase 4: VERIFY — Confirm Improvements

**Goal**: Re-run the analysis and compare before/after scores.

**Step 1: Re-run the pagespeed script**

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/pagespeed.py --url <target-url> --format markdown --output /tmp/psi-after.md
```

**Step 2: Compare scores**

Present a before/after comparison:
```
                     BEFORE    AFTER    DELTA
Mobile Performance:    72        85      +13
Mobile SEO:            88        95       +7
Mobile Accessibility:  76        91      +15
Mobile Best Practices: 90        95       +5
```

**Step 3: Check threshold**

Run with explicit threshold to get a pass/fail exit code:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/pagespeed.py --url <target-url> --threshold 80
echo "Exit code: $?"
```

Exit code 0 means all categories pass. Exit code 1 means at least one category is below threshold.

**Step 4: Document remaining issues**

List any failing audits that cannot be fixed at the content level. These are infrastructure items the user needs to address separately (CDN caching, server response time, render-blocking third-party scripts).

**Gate**: Before/after scores documented. Remaining issues classified as content-level (missed) or infrastructure (out of scope).

---

## Error Handling

### Error: "API error: HTTP 429"
Cause: Rate limited by Google's shared API quota (no API key set)
Solution:
1. Set `PAGESPEED_API_KEY` environment variable
2. Get a free key at https://developers.google.com/speed/docs/insights/v5/get-started
3. The script retries once after 2 seconds automatically

### Error: "Network error"
Cause: Cannot reach Google's API endpoint
Solution:
1. Check internet connectivity
2. Verify the target URL is publicly accessible
3. Try again — transient network issues resolve on retry

### Error: "Exit code 1 after fixes"
Cause: Some categories still below threshold after content-level fixes
Solution:
1. Review the remaining failing audits
2. Determine if they are infrastructure-level (server response time, CDN)
3. Lower the threshold if infrastructure changes are out of scope
4. Report infrastructure issues to the user for separate resolution

---

## References

### Script
- `${CLAUDE_SKILL_DIR}/scripts/pagespeed.py`: Deterministic CLI for PSI API calls

### Related Workflows
- `${CLAUDE_SKILL_DIR}/references/seo.md`: Manual SEO optimization (4-phase ASSESS-DECIDE-APPLY-VERIFY)
- `${CLAUDE_SKILL_DIR}/references/image-audit.md`: Image optimization and accessibility
- `${CLAUDE_SKILL_DIR}/references/pre-publish.md`: Pre-publication checklist
