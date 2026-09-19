# PDF Export Reference

Phase 6 EXPORT renders an html-artifact to PDF via Playwright. Optional, opt-in, additive — HTML stays the default deliverable.

---

## When Phase 6 fires

Trigger conditions (any of these in the current turn's user message):

- "PDF"
- "export PDF"
- "make a PDF"
- "as PDF"
- "send as PDF"
- "save as PDF"
- "PDF version"
- "PDF export"

If none of these signals are present, Phase 6 stays dormant. The HTML artifact is the deliverable; no follow-up nag.

---

## Invocation

```bash
python3 skills/meta/html-artifact/scripts/to-pdf.py \
    --input <generated.html> \
    --output <generated.pdf> \
    --json
```

Flags:

| Flag | Purpose |
|---|---|
| `--input` | Path to the source `.html` file (required) |
| `--output` | Path for the generated `.pdf` file (required) |
| `--shape` | Override shape detection (one of the 8 shapes). Optional; `data-shape` attribute drives detection otherwise. |
| `--json` | Emit machine-readable JSON: `{"output", "page_count", "shape", "bytes"}`. Without it, prints a friendly one-line summary. |

---

## Page-size map

| Shape | Page size | Orientation | Margin |
|---|---|---|---|
| deck | 13.333in × 7.5in | landscape | 0 |
| spec | Letter | landscape | 0.5in |
| code-review | Letter | landscape | 0.5in |
| prototype | Letter | landscape | 0.5in |
| data-viz | Letter | landscape | 0.5in |
| diagram | Letter | landscape | 0.5in |
| report | Letter | portrait | 0.75in |
| editor | Letter | portrait | 0.5in |
| (fallback) | Letter | portrait | 0.5in |

Deck dimensions match Google Slides / PowerPoint widescreen (16:9). One slide per page, no margin, full-bleed.

---

## Shape detection

The script reads `<body data-shape="...">` to pick page settings.

`assemble-template.py` adds the attribute automatically. For artifacts hand-crafted outside the assembler, pass `--shape <name>` explicitly. If neither is present, exit code 1 with a hint to re-assemble or supply the flag.

`--shape` overrides the attribute when both are present. Useful for re-rendering a draft as a different shape.

---

## Page-count contract

For deck shape, `page_count` in the JSON output equals the count of `class="slide"` occurrences in the HTML. Example:

```json
{"output": "/abs/path.pdf", "page_count": 12, "shape": "deck", "bytes": 482104}
```

For non-deck shapes, `page_count` is 0 (the PDF renderer doesn't expose page count without re-parsing the PDF; deck is the documented case where slide count drives expectations).

---

## Print stylesheets

Each shape pairs with a print stylesheet under `templates/print/`:

| File | Page setup |
|---|---|
| `default-print.css` | Letter portrait fallback |
| `deck-print.css` | One slide per page, no margin, un-stick controls |
| `spec-print.css` | Tabs collapse to stacked panels, code-block break-inside avoid |
| `report-print.css` | Heading break-after avoid, table thead repeats |
| `editor-print.css` | Kanban stacks, export bar un-sticks |
| `code-review-print.css` | Diff lines no break, line numbers un-stick |
| `prototype-print.css` | Controls hidden, preview full-width |
| `data-viz-print.css` | Charts full-width, dashboard grid relaxes |
| `diagram-print.css` | SVGs centered, captions stay with figures |

Print CSS files self-declare `@page` and `@media print`. The assembler injects them as full stylesheets — no double-wrapping. (This was the May 9 bug fixed in commit `6b3e830d`.)

---

## Failure paths

### Playwright not installed

Exit code 2. Stderr surfaces:

```
Error: Playwright is not installed.
Install with: pip install -e ".[pdf]" && playwright install chromium
```

Two-step install is required: the Python package (`playwright`) and the browser binary (`chromium`). Skipping `playwright install chromium` produces a different runtime error from a launching browser missing executable.

### Missing `data-shape` attribute, no `--shape` flag

Exit code 1. Stderr:

```
Error: HTML artifact missing data-shape attribute. Re-assemble with assemble-template.py or pass --shape explicitly.
```

### Malformed HTML

Exit code 1 if input lacks `<html>` or `<body>` tags, or is empty.

### Browser launch / page-load / page.pdf failure

Exit code 3 with the exception type and message. Most common causes:

- File URL escaping issue (paths with spaces — Playwright handles it, but a relative path without `file://` prefix won't load).
- `networkidle` never fires (rare — happens if page has long-polling JS; HTML artifacts are static so this is unusual).
- Disk full / output directory not writable.

---

## Troubleshooting

### Fonts render as system default instead of design tokens

Birchline tokens use a system font stack (`-apple-system`, `Inter`, `Segoe UI`, …). Whatever's available locally renders. Embedded `@font-face` with a `data:` URL works in Playwright PDF; CDN font URLs do not (and would violate the self-contained constraint anyway).

### Images timing — blank rectangles in the PDF

The script waits for `networkidle` (no in-flight requests for 500ms). If an artifact pulls a resource that races the load event, it won't appear. Fix: inline the resource as a data URL or `<svg>` rather than an external `<img src>`.

### Large file size

Default PDFs are ~50–500KB. If a generated PDF exceeds 5MB, suspect inlined raster images that should be SVG or CSS, or runaway keyframe animations rendered as discrete frames.

### Color rendering — backgrounds missing

Print CSS sets `print-color-adjust: exact` and `-webkit-print-color-adjust: exact`. If a generated artifact omits these, the browser strips background colors per print convention. Use `templates/print/{shape}-print.css` as the canonical pattern.

---

## What this feature does NOT do

- Email the PDF.
- Auto-trigger on every artifact (HTML stays default).
- Open the PDF in a viewer.
- Embed the PDF in another document.

These are deliberately out of scope. Phase 6 produces a `.pdf` next to the `.html` and reports the path. Whatever ships it onward is the user's call.
