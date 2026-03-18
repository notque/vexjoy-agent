# Report Templates

Reference for image audit report formats and output structures.

---

## Full Site Audit Report

```
===============================================================
 IMAGE AUDIT: [Site Name]
===============================================================

 SUMMARY:
   Total images: [N]
   Total size: [X.X MB]
   Posts with images: [N]
   Average per post: [N] images ([X KB])

 ALT TEXT ISSUES:

   [FAIL] static/images/screenshot1.png
     Used in: content/posts/2024-12-theme.md line 45
     Alt text: Missing
     Suggest: Add descriptive alt text

   [WARN] static/images/diagram.png
     Used in: content/posts/2025-01-debugging.md line 23
     Alt text: "image" (too generic)
     Suggest: Describe what the diagram shows

 FILE SIZE ISSUES:

   [WARN] static/images/hero-large.jpg (1.8 MB)
     Used in: content/posts/2024-11-intro.md line 12
     Dimensions: 4000x3000
     Suggest: Resize to max 1200px wide, compress to <500KB

 MISSING FILES:

   [FAIL] content/posts/2024-10-old.md line 34
     References: /images/missing-screenshot.png
     Status: File not found in static/

 UNUSED IMAGES:

   [INFO] static/images/unused-draft.png (no references found)
   [INFO] static/images/old-logo.svg (no references found)

 FORMAT SUGGESTIONS:

   [SUGGESTION] 5 screenshots could be WebP (save ~40%)
   [SUGGESTION] 2 photos could be WebP (save ~30%)

 PAGE WEIGHT BY POST:

   content/posts/heavy-post.md: 2.4 MB (4 images)
   content/posts/normal-post.md: 340 KB (2 images)

===============================================================
 RECOMMENDATIONS:
   1. Add alt text to [N] images
   2. Resize [N] oversized images
   3. Fix [N] broken image references
   4. Consider removing [N] unused images
   5. Convert [N] images to WebP (est. [X MB] savings)
===============================================================
```

---

## Single Post Audit Report

```
===============================================================
 IMAGE AUDIT: content/posts/[post-name].md
===============================================================

 IMAGES IN POST: [N]
   Line 23: ![Terminal output](/images/terminal.png) [PASS]
   Line 45: ![](/images/screenshot1.png) [FAIL: no alt text]
   Line 67: ![Theme colors](/images/colors.webp) [PASS]
   Line 89: ![Chart](/images/chart.svg) [PASS]

 TOTAL SIZE: [X KB]

 ISSUES:

   [FAIL] Line 45: /images/screenshot1.png
     Alt text: Missing
     Size: 234 KB
     Suggest: Add descriptive alt text

===============================================================
 STATUS: [N] issue(s) to fix
===============================================================
```

---

## Severity Levels

| Level | Prefix | Meaning | Action Required |
|-------|--------|---------|-----------------|
| FAIL | `[FAIL]` | Broken or inaccessible content | Must fix before publish |
| WARN | `[WARN]` | Quality or performance concern | Should fix soon |
| INFO | `[INFO]` | Optimization opportunity | Optional improvement |
| SUGGESTION | `[SUGGESTION]` | Format or compression advice | Consider when convenient |

---

## Page Weight Analysis Format

For each post with images, report:
- Total image bytes
- Image-to-content ratio
- Largest single image
- Number of images

**Thresholds:**
- Total images <1MB: Good
- Total images 1-3MB: Warn
- Total images >3MB: Needs optimization

---

## Optimization Potential Estimates

Standard savings from common optimizations:
- WebP conversion: ~30% for photos, ~25% for screenshots
- Resize to max 1200px width: varies by original
- Compression optimization: ~10-20%

---

## Status Summary Line

End every report with a status line:

| Condition | Status |
|-----------|--------|
| No FAIL or WARN issues | `STATUS: PASS - No critical issues` |
| Only WARN issues | `STATUS: WARN - [N] issues to address` |
| Any FAIL issues | `STATUS: FAIL - [N] critical issues ([brief list])` |
