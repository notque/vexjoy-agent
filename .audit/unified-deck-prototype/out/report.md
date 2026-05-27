# Unified Deck Prototype — V1 Fidelity Report

- **Source HTML**: vexjoy-agent-management-deck.html
- **Generated PPTX**: `/Users/I810033/pgh/vexjoy-agent/.audit/unified-deck-prototype/out/vexjoy-agent-management-deck.pptx`
- **Size**: 39,725 bytes
- **QA render**: skipped (skipped (soffice not on PATH))

## Slide-level metrics

| Metric | Value | Expected |
|---|---|---|
| Slide count | 12 | 12 |
| Text frames (total) | 15 | >=120 |
| Slide dimensions | 13.33 x 7.50 in | 13.33 x 7.50 in (16:9) |
| Aspect ratio | 1.778 | 1.778 |

## Type distribution (from extractor)

| Type | Count | Engine handling |
|---|---|---|
| `content` | 2 | native |
| `title` | 1 | native |
| `metric_grid` | 1 | FALLBACK -> content_bullets |
| `layer_rows` | 1 | FALLBACK -> content_bullets |
| `pipeline` | 1 | FALLBACK -> content_bullets |
| `code_block` | 1 | FALLBACK -> content_bullets |
| `compare_table_2col` | 1 | FALLBACK -> content_bullets |
| `outcome_grid` | 1 | FALLBACK -> content_bullets |
| `split_narrow` | 1 | FALLBACK -> content_bullets |
| `compare_table_3col` | 1 | FALLBACK -> content_bullets |
| `closing` | 1 | native |

## Fidelity score

| Axis | Points (/2) | Detail |
|---|---|---|
| slide_count_match | 2 | got 12, expected 12 |
| text_frame_density | 0 | got 15, expected >=120 |
| aspect_ratio_widescreen | 2 | 13.33x7.50in (aspect 1.778) |
| layout_coverage | 0 | 8/12 slides fall back to default layout: ['metric_grid', 'layer_rows', 'pipeline', 'code_block', 'compare_table_2col', 'outcome_grid', 'split_narrow', 'compare_table_3col'] |
| build_succeeded | 2 | 39,725 bytes |

**Total: 6 / 10** (worst axis: `text_frame_density` at 0/2)

## Baseline comparison

Baseline PNGs found: 12 files in `.audit/pptx-test/render/`.
Per-slide perceptual diff is not implemented in V1; visual comparison
requires manual side-by-side review or a future image-diff axis.

## Known gaps (Phase 1 scope)

- PDF output (`--format pdf`) NOT wired; would require LibreOffice headless or weasyprint.
- Extended types (`metric_grid`, `layer_rows`, `pipeline`, `code_block`,
  `compare_table_2col/3col`, `outcome_grid`, `split_narrow`) fall back to bullets.
  Phase 2 work: add native builders to `_pptx_engine.py`.
- Perceptual diff vs baseline PNGs not implemented (would require pixelmatch / SSIM).
- LibreOffice render step skipped on hosts without `soffice`.
