---
name: image-auditor
description: "Non-destructive image validation for accessibility and health."
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
routing:
  triggers:
    - "audit images"
    - "check broken images"
    - "image accessibility"
    - "alt text check"
    - "image optimization"
  category: content-publishing
---

# Image Auditor Skill

Non-destructive 4-phase image validation pipeline: Discover, Validate, Analyze, Report. Read and follow the repository CLAUDE.md before starting any audit.

```
/image-audit                    # Audit entire site
/image-audit content/posts/     # Audit specific directory
/image-audit --post my-post.md  # Audit single post
```

By default, every audit runs all check categories (alt text, existence, size, format, unused images) and calculates per-post page weight. Optional modes: **Deep Scan** includes theme images and `assets/` directory. **Auto-Optimize** generates optimized versions (requires imagemagick and explicit user consent). **Strict Mode** treats all suggestions as blockers.

---

## Instructions

### Phase 1: DISCOVER

**Goal**: Build a complete map of all images and all image references in the codebase.

**Step 1: Find all image files**

Use Glob to locate image files:
- Pattern: `static/**/*.{png,jpg,jpeg,gif,webp,svg}`
- Record each file's absolute path and size (use `ls -la` or `stat`) -- measure actual bytes, never estimate

**Step 2: Find all image references in content**

Use Grep to search content files for these patterns:
- Markdown images: `![alt](path)` -- regex: `!\[.*?\]\(.*?\)`
- Hugo figure shortcode: `{{< figure src="..." >}}` -- regex: `figure.*src=`
- HTML img tags: `<img src="..." alt="...">` -- regex: `<img.*src=`
- Raw path references: `.png)`, `.jpg)`, `.webp)`, `.svg)`

**Step 3: Build reference map**

For each image reference, record:
- Source file path (absolute)
- Line number
- Image path (as written in source)
- Resolved path (in static/)
- Alt text (if present)

**Path Resolution Rules:**
- `/images/foo.png` resolves to `static/images/foo.png`
- `images/foo.png` resolves to `static/images/foo.png`
- `../images/foo.png` resolves relative to the content file's location (always resolve from the content file's directory, never check the literal string against static/)
- Hugo shortcode `src=` values follow the same resolution rules

**Gate**: Reference map is complete with all images and all references catalogued. Proceed only when gate passes.

### Phase 2: VALIDATE

**Goal**: Check every reference and every image against quality criteria. Verify every reported issue by reading the actual file or reference before recording it -- never report an issue based on assumption alone.

**Step 1: Alt text validation**

| Status | Condition |
|--------|-----------|
| PASS | Alt text present, descriptive, 10-125 characters |
| WARN | Alt text too generic (single words: "image", "screenshot", "picture", "photo", "diagram", "figure", "img") -- always check against this generic term list rather than subjectively judging quality |
| FAIL | Alt text missing or empty |

15% of users rely on assistive technology, so validate all alt text regardless of perceived importance.

See `references/alt-text-examples.md` for detailed quality guidelines.

**Step 2: File existence validation**

| Status | Condition |
|--------|-----------|
| PASS | Image file exists at resolved path |
| FAIL | Image file not found at resolved path |

**Step 3: File size validation**

| Status | Threshold |
|--------|-----------|
| PASS | <200KB |
| WARN | 200KB-500KB |
| FAIL | >500KB |

See `references/size-guidelines.md` for type-specific thresholds.

**Step 4: Format appropriateness**

| Image Type | Preferred Format | Detection Heuristic |
|------------|------------------|---------------------|
| Photos | WebP, JPEG | Filename: "photo", "hero", "banner" |
| Screenshots | WebP, PNG | Filename: "screenshot", "screen-", "capture" |
| Diagrams | SVG, WebP | Filename: "diagram", "chart", "graph", "flow" |
| Icons/Logos | SVG | Filename: "icon", "logo", "favicon" |

Report format savings estimates and let the user decide whether to convert -- do not skip format recommendations on the assumption they are unnecessary.

See `references/format-selection.md` for the complete decision flowchart.

**Step 5: Unused image detection**

Compare all files in static/images/ against the reference map. Any file with zero references is reported as unused. Always perform this step -- unused images bloat the repository and deployment size.

**Gate**: All references validated against all criteria. Every issue has a severity level, file path, and line number. Proceed only when gate passes.

### Phase 3: ANALYZE

**Goal**: Compute aggregate metrics and optimization potential.

**Step 1: Page weight per post**

For each post containing images, sum total image bytes and count images.

| Status | Total Images |
|--------|--------------|
| Good | <1 MB |
| Warn | 1-3 MB |
| Critical | >3 MB |

**Step 2: Optimization estimates**

Calculate potential savings for each actionable item:
- WebP conversion: ~30% for photos, ~25% for screenshots
- Resize to max 1200px width: varies by original dimensions
- Compression optimization: ~10-20% additional savings
- Total estimated savings across all recommendations

Present estimates as concrete byte counts (e.g., "save ~340 KB"), never as vague percentages alone.

**Step 3: Identify highest-impact fixes**

Rank issues by potential impact:
1. Broken references (FAIL) -- content is visibly broken
2. Missing alt text (FAIL) -- accessibility violation
3. Oversized images on heavy pages -- worst page weight first
4. Format mismatches with largest savings potential

**Gate**: Metrics computed for all posts. Optimization estimates are concrete numbers. Priority ranking established. Proceed only when gate passes.

### Phase 4: REPORT

**Goal**: Generate a structured, actionable audit report. This phase is read-only -- never modify, resize, convert, or delete images. Report findings and recommendations only; changes require explicit user request.

Follow the report format in `references/report-templates.md`. The report must include:

1. **Summary**: Total images, total size, posts with images, averages
2. **Alt Text Issues**: Every FAIL and WARN with file path, line number, current alt text
3. **File Size Issues**: Every oversized image with size and recommendation
4. **Missing Files**: Every broken reference with source file and line number
5. **Unused Images**: Every orphaned file with size
6. **Format Suggestions**: Aggregated conversion recommendations with estimated savings
7. **Page Weight**: Per-post breakdown, heaviest posts first
8. **Recommendations**: Numbered, prioritized action items
9. **Status Line**: PASS, WARN, or FAIL with counts

Every issue in the report must include an absolute file path and line number so the user can locate and fix it. Clearly distinguish severity levels: FAIL (broken, must fix), WARN (should fix), INFO (suggestion). Do not conflate severity -- a format suggestion is not a blocker.

**Gate**: Report is complete with all sections populated. Every issue is actionable (file path + line number + recommendation). Report ends with a status line.

---

## Examples

### Example 1: Clean Site
User says: "Run an image audit"
Actions:
1. Glob for all images in static/, Grep for all references in content/ (DISCOVER)
2. Validate alt text, existence, sizes, formats for each reference (VALIDATE)
3. Compute page weights and optimization potential (ANALYZE)
4. Generate report showing no critical issues, minor format suggestions (REPORT)
Result: STATUS: PASS with optional WebP conversion suggestions

### Example 2: Site with Multiple Issues
User says: "Check all images before we publish"
Actions:
1. Build reference map of 24 images across 8 posts (DISCOVER)
2. Find 2 missing alt texts, 1 broken reference, 1 oversized image (VALIDATE)
3. Calculate 4.2 MB total weight, 2.1 MB on heaviest post (ANALYZE)
4. Generate report with 4 critical issues and 5 format suggestions (REPORT)
Result: STATUS: FAIL with prioritized fix list

### Example 3: Single Post Audit
User says: "Audit images in content/posts/2024-12-theme.md"
Actions:
1. Grep that specific file for image references (DISCOVER)
2. Validate the 4 images found: 3 pass, 1 missing alt text (VALIDATE)
3. Sum 890 KB total weight for this post (ANALYZE)
4. Generate focused report for single post (REPORT)
Result: 1 issue to fix (missing alt text on line 45)

---

## Error Handling

### Error: "No Images Found"
Cause: Wrong directory, no content files, or non-standard image paths
Solution:
1. Verify static/images/ directory exists
2. Confirm content files use standard image reference patterns
3. Check for custom Hugo shortcodes that reference images differently

### Error: "Cannot Determine Image Dimensions"
Cause: imagemagick not installed or file permissions issue
Solution:
1. Skip dimension checks and audit only file size
2. Report that dimension analysis was skipped
3. Note that `identify` command requires imagemagick package

### Error: "Path Resolution Ambiguous"
Cause: Relative paths in content that could resolve to multiple locations
Solution:
1. Try resolving relative to the content file's directory first
2. Fall back to resolving relative to static/
3. Report both possible resolutions if ambiguous

### Error: "Permission Denied Reading Files"
Cause: File permissions prevent reading image files or content directories
Solution:
1. Check file permissions with `ls -la` on the failing path
2. Report which files are inaccessible and skip them
3. Note skipped files in the report summary so the user knows the audit is incomplete

---

## References

### Integration Notes

**With pre-publish-checker**: The pre-publish-checker skill performs basic image validation (existence, alt text presence). This skill provides deeper analysis including format optimization, page weight, and unused image detection. Use pre-publish for quick pass/fail; use image-auditor for comprehensive audits.

**With Hugo build**: Run image audit before `hugo --minify` to catch broken references and optimize assets before deployment.

**Recommended cadence**: Run full audit periodically (weekly or before releases). Address FAIL issues immediately. Schedule WARN issues for optimization sprints.

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/alt-text-examples.md`: Good and bad alt text examples by image type
- `${CLAUDE_SKILL_DIR}/references/size-guidelines.md`: Maximum file sizes, dimension limits, page weight budgets
- `${CLAUDE_SKILL_DIR}/references/format-selection.md`: Format decision flowchart and detection heuristics
- `${CLAUDE_SKILL_DIR}/references/report-templates.md`: Full audit and single-post report templates
