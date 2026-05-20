# PDF Export

How `to-pdf.py` turns an HTML artifact into a paper-ready PDF, what page sizes each shape gets, and how to debug when output looks wrong.

---

## When To Export

Export PDF when the user signals paper or share intent. Skip otherwise — most artifacts live as HTML.

| Signal in user request | Export? |
|---|---|
| "PDF", "print", "printout", "paper" | Yes |
| "share", "send to colleague", "Slack this", "email" | Yes |
| "review on phone", "show in browser" | No |
| "save", "drop in repo" | No (HTML is the deliverable) |
| (nothing) | No |

---

## One Command

```bash
python3 scripts/to-pdf.py --input file.html --json
```

| Flag | Purpose |
|---|---|
| `--input` | Path to assembled HTML artifact (required) |
| `--output` | Output PDF path (defaults to `<input>.pdf`) |
| `--json` | Emit JSON report — for pipeline consumption. Humans omit this. |
| `--chrome-path` | Force a specific Chrome binary (rare; use when auto-detect picks the wrong one) |
| `--shape` | Override shape detection (rare; the artifact's `data-shape` attribute is the source of truth) |

Pipeline phase 6 EXPORT calls this. Manual users run it without `--json` for human-readable output.

---

## Shape -> Page Size

| Shape | Page size | Orientation | Driver |
|---|---|---|---|
| deck | 13.333in x 7.5in | landscape | `templates/print/deck-print.css` |
| report | 8.5in x 11in | portrait | `templates/print/report-print.css` |
| spec | 11in x 8.5in | landscape | `templates/print/spec-print.css` |
| data-viz | 8.5in x 11in | portrait | `templates/print/data-viz-print.css` |
| code-review, prototype, diagram, editor, (other) | 8.5in x 11in | portrait | `templates/print/default-print.css` |

The shape comes from the artifact's `<html data-shape="deck">` attribute. `to-pdf.py` reads it and lets the print CSS drive Chrome.

---

## How Sizing Works

| Layer | Behavior |
|---|---|
| Print CSS | `templates/print/{shape}-print.css` declares `@page { size: <dim> <orientation>; }` |
| Assembler | Injects the matching print CSS into the artifact's `<style>` block at generation time |
| Chrome headless | Reads `@page` and renders at that size. No `--print-to-pdf-paper-width` flag passed. |
| `to-pdf.py` | Invokes Chrome with `--print-to-pdf=<output>` and lets CSS drive |

**Rule:** Do not pass `--print-to-pdf-paper-width` / `-paper-height` to Chrome from `to-pdf.py`. CSS `@page` is authoritative. Forcing dimensions on the command line overrides the shape-specific CSS and reintroduces the clipping bug.

---

## Why Decks Don't Clip Anymore

The previous bug:

| Before | After |
|---|---|
| Print CSS used `height: 7.5in; overflow: hidden;` on a slide box | Print CSS uses `width: 13.333in; height: 7.5in;` — 1:1 with live viewport |
| Live viewport was 1280px x 720px (16:9) | Live viewport is 1280px x 720px (16:9) — same |
| 1280px @ 96dpi = 13.333in, but the print box was 8.5in x 11in scaled wrong | 1280px @ 96dpi = 13.333in. Print box matches exactly. |
| Content authored against `100vh` overflowed the smaller print box -> clipped | Content authored against `100vh` fits — no scale, no clip. |

If a deck PDF clips again, suspect: print CSS got overridden, or someone added `overflow: hidden` on a parent. Check `templates/print/deck-print.css` first. The 1:1 mapping is the design — don't compromise it.

---

## Dark Theme In PDF

```css
* {
  -webkit-print-color-adjust: exact !important;
  print-color-adjust: exact !important;
  color-adjust: exact !important;
}
```

| Vendor variant | Why all three |
|---|---|
| `-webkit-print-color-adjust` | Chrome <97 |
| `print-color-adjust` | Standard |
| `color-adjust` | Legacy spec name; some embedded browsers |

This block is in every `templates/print/*-print.css`. If a dark-themed PDF prints white-on-white:

| Diagnosis | Fix |
|---|---|
| Theme CSS overrides the rule with later specificity | Add the rule to `<style>` last, or raise specificity with `html *` |
| User passed `--no-print-backgrounds` to Chrome | Don't. `to-pdf.py` should never pass that flag. |
| Print CSS got stripped from the artifact (assembler bug) | Confirm `@page` block is in the rendered HTML; if absent, the assembler skipped print injection. Re-run with verbose. |

---

## Chrome Detection

`to-pdf.py` resolves Chrome in this order:

| Priority | Source |
|---|---|
| 1 | `--chrome-path` CLI flag |
| 2 | `CHROME_PATH` environment variable |
| 3 | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` (macOS) |
| 4 | `chromium` on `$PATH` |
| 5 | `google-chrome` on `$PATH` |
| 6 | `chrome` on `$PATH` |

First match wins. If none resolve, the script fails with `Chrome not found` and lists what it tried.

---

## Validation After Generation

`to-pdf.py` checks every output before declaring success.

| Check | What it confirms |
|---|---|
| File exists | Chrome wrote something |
| Size > 10KB | Not a blank page (sub-10KB usually means Chrome rendered nothing) |
| Magic bytes `%PDF-` | File is a real PDF, not an error page |
| Page count = expected | For decks: matches slide count. For reports: > 0. |

JSON output reports each check. Pipeline phase 6 EXPORT halts if any fail.

```json
{
  "ok": true,
  "input": "siem-deck.html",
  "output": "siem-deck.pdf",
  "shape": "deck",
  "pages": 9,
  "expected_pages": 9,
  "size_bytes": 487231
}
```

---

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| `Chrome not found` | None of the resolution paths matched | Install Chrome or set `CHROME_PATH=/path/to/chrome` |
| `PDF too small (4231 bytes)` | Chrome rendered blank — usually a JS error or missing CSS | Open the HTML in a real browser, check console for errors |
| `Wrong page count: expected 9 got 1` | Print CSS missing or shape attr wrong | Confirm `data-shape` set; confirm print CSS block in HTML; re-assemble if absent |
| `PDF magic bytes missing` | Chrome wrote an HTML error page instead of a PDF | Run `to-pdf.py` without `--json` to see Chrome's stderr |
| `Decks clip in PDF` | `overflow: hidden` ancestor or scale transform | Search `templates/print/deck-print.css` and the artifact for stray `overflow: hidden` / `transform: scale()` |
| `Dark theme prints white` | `print-color-adjust: exact` got overridden | See "Dark Theme In PDF" above |

---

## Visual Validation

Eyeball every page after generation when debugging. Pipeline tests use this for snapshot diffs.

```python
import pypdfium2 as pdfium

pdf = pdfium.PdfDocument("siem-deck.pdf")
for i, page in enumerate(pdf):
    bitmap = page.render(scale=2.0)
    bitmap.to_pil().save(f"siem-deck-page-{i+1}.png")
print(f"Rendered {len(pdf)} pages")
```

| Use case | Action |
|---|---|
| Confirm no clipping | Check each PNG fills the expected aspect ratio with no cut content |
| Confirm dark theme survived | First pixel of background should match theme bg color, not white |
| Confirm fonts embedded | Text should be sharp at 2x; if blurry, fonts didn't subset |

`pypdfium2` is the dependency (`pip install pypdfium2`). It does not require Chrome — pure Python rendering.
