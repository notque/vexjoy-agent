# PPTX Export — Phase 7 (html-artifact deck shape)

Phase 7 EXPORT-PPTX renders an html-artifact deck (`.html` with
`<section class="slide">` blocks) into an editable Microsoft PowerPoint
`.pptx` file. Mirrors Phase 6 EXPORT-PDF in shape: opt-in, signal-triggered,
deterministic. HTML stays the source of truth; PPTX is a one-way export for
hand-off.

The bridge re-authors slides natively via `python-pptx` because no general
HTML→PPTX converter preserves CSS-rich layout. The HTML is parsed into a
layout-tagged JSON slide-map, then a typed builder paints native PowerPoint
shapes per layout. Output is a 13.333 × 7.5 in (16:9) deck, dark navy theme,
Aptos body / Cascadia Code mono, fully editable in PowerPoint 2023+ and
Keynote.

---

## Trigger conditions

Phase 7 fires only on explicit user signal:

`pptx`, `.pptx`, `powerpoint`, `editable deck`, `editable`, `as pptx`,
`export pptx`, `hand-off`, `corporate template`, `make a deck` (when paired
with any of the above), `pitch deck` / `slide deck` (when paired with any of
the above).

Without one of these signals, html-artifact stops at Phase 5 DELIVER (HTML
only). Phase 7 never auto-runs.

---

## Pipeline

```
deck.html ──(extract_slides.py)──▶ slides.json ──(_pptx_engine.py)──▶ deck.pptx
                                                            │
                                                            ▼ (optional)
                                                       render_pptx.py
                                                            │
                                                            ▼
                                                     per-slide PNGs (QA)
```

Single command:

```bash
python3 skills/meta/html-artifact/scripts/pptx-bridge/run-unified.py \
    --input deck.html \
    --format pptx \
    --out deck.pptx \
    --no-render
```

`--out` accepts either a directory (sibling `slides.json`, `report.md`,
`render/` written next to the .pptx) or a `.pptx` file path (single-file
mode; no siblings written).

`--no-render` skips the optional LibreOffice QA render. Use it on hosts
without `soffice` or when you only need the editable PPTX.

Exit codes: `0` ok, `2` bad input or missing tool, `3` conversion failure.

---

## Layout types

The extractor classifies each `<section class="slide">` into one of 12
layout types. Each maps 1:1 to a builder in `_pptx_engine.LAYOUT_BUILDERS`.

| Layout | HTML signal | Builder | Notes |
|---|---|---|---|
| `title` | `<section class="slide slide-title active">` | `build_title` | Eyebrow + giant title + subtitle, centered. |
| `closing` | `<section class="slide slide-title">` (no `active`) | `build_closing` | Same shape as title; accent_text split out from h2 if present. |
| `content` | `<ul>` of `<li>`, optional `<strong>` prefix | `build_content` | Eyebrow + title + lead + bulleted list + optional callout box. |
| `metric_grid` | `.metric-grid` with `.metric` cards | `build_metric_grid` | Up to 4 cards horizontally; bigger value, label below, optional desc. |
| `layer_rows` | `.layer-row` blocks | `build_layer_rows` | Stacked horizontal rows with name, count, desc. |
| `pipeline` | `.pipeline` with `.pipeline-step` blocks | `build_pipeline` | Horizontal step boxes; label + name; optional caption. |
| `code_block` | `.code-block` element | `build_code_block` | Mono-font panel; line-by-line color rules ($ = muted, > = accent, ✓ = success). |
| `compare_table_2col` | `.compare-table` with 2 columns | `build_compare_table_2col` | Two-column side-by-side; cell role (`danger`/`success`/`label`) drives color. |
| `compare_table_3col` | `.compare-table` with 3 columns | `build_compare_table_3col` | Three-column variant; smaller text, default role chain (`label`/`danger`/`success`). |
| `outcome_grid` | `.outcome-grid` with `.outcome` cards | `build_outcome_grid` | 3-column card grid with heading + body. |
| `split_narrow` | `.split-narrow` with two child columns | `build_split_narrow` | Left column prose + callout, right column CLI-row card. |
| `section` / `section_divider` | Legacy fallback | `build_section_divider` | Eyebrow + large left-aligned title + subtitle. |

**Type normalization:** the engine lowercases, strips, and replaces `-`/space
with `_` before lookup. So `metric-grid`, `Metric Grid`, and `metric_grid`
all hit the same builder. Unknown types fall back to `build_content`.

**Public registry:** `_pptx_engine.SUPPORTED_LAYOUTS` is the set of accepted
layout keys. Used by `run-unified.py`'s fidelity report to flag fall-throughs.

---

## THEME dict

`_pptx_engine.THEME` is the single source of truth for v2 visual identity.
Builders never inline hex codes — always reference `THEME["..."]`.

| Key | RGB | Role |
|---|---|---|
| `bg` | `#1A1A2E` | Slide background (dark navy). |
| `card_bg` | `#23233D` | Surface / card / metric background. |
| `code_bg` | `#16162A` | Code panel background (slightly darker than bg). |
| `border` | `#3A3A5C` | Default rectangle border. |
| `fg` | `#E8E8F0` | Primary text (off-white). |
| `fg_sec` | `#A0A0B8` | Secondary / lead body text. |
| `muted` | `#6E6E8A` | Eyebrow, muted captions, header rows. |
| `accent` | `#64B5F6` | Sky blue brand accent (eyebrow, bullets, accent text). |
| `success` | `#81C784` | Softer green for dark bg (success roles, ✓ lines). |
| `danger` | `#EF5350` | Red (danger roles). |
| `font_body` | `Aptos` | Body text font; falls back to PowerPoint's substitution table on hosts without Aptos. |
| `font_mono` | `Cascadia Code` | Code / inline-mono font. |

PowerPoint 2023+ ships both Aptos and Cascadia Code. On older hosts, the
viewer falls back to Calibri / Consolas via PowerPoint's font substitution.
This is a deliberate portability trade-off — embedding fonts in `.pptx`
roughly doubles file size and is not python-pptx-supported.

The legacy `PALETTES["vexjoy-dark"]` dict is kept as a passthrough for old
callers that pass a `design.palette` argument; all current builders read
`THEME` directly.

---

## CLI reference

### `run-unified.py` — full pipeline

```bash
python3 skills/meta/html-artifact/scripts/pptx-bridge/run-unified.py \
    --input <html_path> \
    --format pptx \
    --out <pptx_path_or_dir> \
    [--no-render]
```

- `--input` — HTML deck file (must contain `<section class="slide">` blocks).
- `--format` — `pptx` (default). `pdf` is rejected here; use
  `scripts/to-pdf.py` for HTML→PDF.
- `--out` — `.pptx` file path (single-file mode) OR directory (writes the
  .pptx plus `slides.json`, `report.md`, and optional `render/` siblings).
- `--no-render` — skip the optional LibreOffice QA step. Required on hosts
  without `soffice`.

### `extract_slides.py` — HTML → slide-map JSON

```bash
python3 .../extract_slides.py --input deck.html --output slides.json
```

Standalone extractor. Useful for inspecting the slide-map intermediate or
hand-editing it before re-running the engine.

### `_pptx_engine.py` — slide-map JSON → .pptx

```bash
python3 .../_pptx_engine.py --slide-map slides.json --design design.json --output deck.pptx
```

`design.json` is `{"palette": "vexjoy-dark"}`; the THEME dict drives all
visuals regardless. Useful for power users who hand-author slide-maps.

### `render_pptx.py` — .pptx → per-slide PNGs (QA only)

```bash
python3 .../render_pptx.py --input deck.pptx --output-dir ./qa/ [--dpi 150] [--keep-pdf]
```

Soft-dependency on `soffice` (LibreOffice) and optionally `pdftoppm`
(poppler-utils). Used by the QA loop only; not required for the editable
.pptx itself.

---

## Validation

After Phase 7, `run-unified.py` writes `report.md` (in directory mode) with:

| Axis | Pass criterion |
|---|---|
| `slide_count_match` | Got 12 slides for the vexjoy fixture; tolerance ±2. |
| `text_frame_density` | ≥120 editable text frames (no rasterized text). |
| `aspect_ratio_widescreen` | 13.33 × 7.50 in, aspect ≈ 1.778. |
| `layout_coverage` | All extracted types map to native builders (no fall-throughs to default). |
| `build_succeeded` | Output ≥10 KB and parses cleanly via python-pptx. |

Each axis scores 0–2; total normalized to a 0–10 fidelity number. The
vexjoy-agent-management fixture currently scores 10/10 deterministically.

---

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `extractor produced 0 slides` | HTML has no `<section class="slide">` blocks. | Confirm the deck was generated by html-artifact's deck shape; hand-written HTML must use the `slide` class. |
| `python-pptx not installed` | Missing dep. | `pip install python-pptx`. |
| `pptx not produced` / size <1 KB | Engine raised an exception silently caught earlier. | Re-run with `python3 -X dev` or read the printed `FAIL: ...` line. |
| Fonts wrong in PowerPoint | Host lacks Aptos / Cascadia Code. | Update to PowerPoint 2023+, or accept the substitution (Segoe UI / Consolas). |
| QA render skipped | No `soffice` on PATH. | `brew install --cask libreoffice` (macOS) or `sudo apt install libreoffice-impress` (Debian). The PPTX itself is unaffected. |
| Layout falls back to `content` | New layout type added in HTML but not registered in `LAYOUT_BUILDERS`. | Add a builder + extractor branch; update `SUPPORTED_LAYOUTS`. |

---

## Engine architecture

`_pptx_engine.py` is organized in three layers:

1. **THEME dict + `hex_to_rgb` / `get_palette`** — visual constants.
2. **Low-level primitives** — `fill_bg`, `add_text`, `add_rect`,
   `add_eyebrow_and_title`. All theme-aware. Builders never call
   python-pptx directly for fill/line color.
3. **Layout builders** — one function per layout type. Each takes
   `(prs, slide_data, _palette)` and returns the slide. Builders are pure
   functions over the THEME dict + slide data; no global state.

`build_presentation(slide_map, design, output_path)` is the entry point:
sets 16:9 dimensions, normalizes each slide's `type`, dispatches via
`LAYOUT_BUILDERS`, saves.

---

## When NOT to use this

- For a viewable deck on screen → keep the HTML; it has the best visuals
  and zero export step.
- For a PDF → use `scripts/to-pdf.py` (Phase 6); it's faster than going
  through PPTX.
- For a deck whose source is markdown / a slide-map JSON written by hand →
  call `_pptx_engine.py` directly with `--slide-map`. The HTML pipeline is
  for html-artifact-generated decks.
