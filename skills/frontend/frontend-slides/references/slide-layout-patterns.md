# Slide Layout Patterns -- Frontend Slides Reference

> **Load this file during Phase 4 (BUILD) when building slide HTML structure.**

## Assembly

Assemble CSS for selected layouts:

```bash
python3 skills/frontend/frontend-slides/scripts/assemble-layouts.py --layouts title,content,code
python3 scripts/assemble-layouts.py --all --output layouts.css
```

Use `--list` to see all layouts, density limits, overflow checks, and validation breakpoints.
Use `--include-html` to include HTML templates in output.

## Template Files

Each layout type has paired `.html` and `.css` files in `templates/layouts/`:

| Layout | HTML | CSS | Density Limit |
|--------|------|-----|---------------|
| title | title.html | title.css | 1 heading + 1 subtitle |
| content | content.html | content.css | 4-6 bullets |
| grid | grid.html | grid.css | 6 cards max |
| code | code.html | code.css | 8-10 lines |
| quote | quote.html | quote.css | 1 quote + attribution |
| image | image.html | image.css | 1 image + caption |
| section-break | section-break.html | section-break.css | 1 word/phrase |

## Overflow Checks

| Pattern | Detection | Fix |
|---------|-----------|-----|
| Fixed inner height | `grep 'height: [0-9]*px'` | `max-height: min(Xvh, Ypx)` |
| min-height on slide | `grep 'min-height.*slide'` | Exact `height: 100vh; 100dvh` |
| Nested bullets | `grep '<li>.*<ul>'` | Flatten to single level |
| Pre without overflow | `grep -A5 '<pre>' \| grep overflow` | `max-height: min(55vh,500px); overflow:hidden` |
| Hard-coded colors | `grep 'color: #' \| grep -v :root` | Use `var(--text-primary)` etc. |

## Validation Breakpoints

9 breakpoints required: 1920x1080, 1440x900, 1280x720, 1024x768, 768x1024,
375x667, 414x896, 667x375, 896x414. Zero overflows required to pass Gate 5.
