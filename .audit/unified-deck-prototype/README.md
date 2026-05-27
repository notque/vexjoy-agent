# Unified Deck Pipeline — Phase 1 Prototype

Sandbox build for `adr/unified-deck-pipeline.md`. Demonstrates that an
html-artifact deck can be converted to editable `.pptx` through a single
CLI without touching either skill's published files.

## Status

**Phase 1: PROTOTYPE.** Local sandbox under `.audit/unified-deck-prototype/`.
Nothing here is wired into the production routing system or installed skills.

## What it does

```
HTML deck (html-artifact deck-shape)
        |
        v
  extract_slides.py  --->  slides.json
        |
        v
  _pptx_engine.py    --->  <name>.pptx
        |
        v
  (LibreOffice, optional)  --->  per-slide PNGs for QA
        |
        v
  python-pptx parse  --->  report.md (fidelity score)
```

## Single command

```bash
python3 .audit/unified-deck-prototype/run-unified.py \
    --input vexjoy-agent-management-deck.html \
    --format pptx \
    --out .audit/unified-deck-prototype/out/
```

Optional flags:

| Flag | Effect |
|---|---|
| `--no-render` | Skip LibreOffice render even if `soffice` is installed |
| `--format pdf` | NOT WIRED in Phase 1 (returns exit 2) |

## Output paths

| File | Purpose |
|---|---|
| `out/slides.json` | Extracted slide map (intermediate, inspectable) |
| `out/<deck-name>.pptx` | Editable PowerPoint output |
| `out/report.md` | V1 fidelity score and gap analysis |
| `out/render/*.pdf` | LibreOffice intermediate (only if `soffice` is on PATH) |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | OK — `.pptx` written, report generated |
| 2 | Bad input (file missing, unsupported format) |
| 3 | Build failure (extractor returned 0 slides, pptx not produced) |

## Known limitations (Phase 1 scope)

- **PDF output not wired.** `--format pdf` returns exit 2.
- **Extended layouts fall back to bullets.** The extractor produces 7 layout
  families (`metric_grid`, `layer_rows`, `pipeline`, `code_block`,
  `compare_table_2col`, `compare_table_3col`, `outcome_grid`, `split_narrow`)
  but the copied `_pptx_engine.py` only natively renders `title`, `content`,
  `closing`, `two_column`, `quote`, `table`, `image_text`. Unsupported types
  use `build_content_bullets` as a graceful fallback.
- **No perceptual diff vs baseline PNGs.** Baseline lives at
  `.audit/pptx-test/render/original-*.png` but the report only notes their
  presence; SSIM/pixelmatch is Phase 3 work.
- **LibreOffice render is optional.** If `soffice` is not on `PATH`, the
  render step is skipped with a message. The `.pptx` itself is unaffected.

## Phase 2 promotion path

If V1 fidelity >= 7/10:

1. Add native builders for the 7 extended layout types to a real engine
   inside `skills/output/html-artifact/scripts/`.
2. Wire `run-unified.py` (renamed to `unified-deck.py`) into the
   `html-artifact` skill SKILL.md as the Phase 7 export step.
3. Move slide-map JSON schema to `skills/output/html-artifact/references/slide-map-schema.md`.
4. Delete this sandbox directory.

## Pointer

ADR: `adr/unified-deck-pipeline.md` (uncommitted, local-only working doc).
