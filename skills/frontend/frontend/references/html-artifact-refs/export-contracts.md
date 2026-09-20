# HTML artifact export contracts

Export is opt-in. HTML remains the source of truth.

## PDF

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts-html-artifact/to-pdf.py \
  --input artifact.html --output artifact.pdf --json
```

The assembler writes `body[data-shape]`; hand-authored files must provide `--shape`. Deck output is 13.333 × 7.5 inches, full bleed, one `.slide` per page. Other shapes use their print stylesheet under `templates/print/`. The May 9 double-wrapping bug is avoided by injecting those files directly: they already contain `@page` and `@media print`.

Exit codes: 1 malformed input/shape, 2 Playwright unavailable, 3 browser/PDF failure. Playwright needs both the Python package and `playwright install chromium`. External/CDN resources violate the artifact contract and can render blank; inline SVG, fonts, and images.

## PPTX

Deck shape only:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts-html-artifact/pptx-bridge/run-unified.py \
  --input deck.html --format pptx --out deck.pptx --no-render
```

The bridge re-authors editable native slides; it does not reproduce arbitrary CSS. Input must use `<section class="slide">`. Unknown extracted layouts fall back to `content`, so inspect the fidelity report for layout fall-through. HTML→PPTX is one-way; do not treat the PPTX as the next HTML source.

`--no-render` skips optional LibreOffice QA. Without it, `soffice` is required; `pdftoppm` is optional. Exit codes are 0 success, 2 bad input/missing tool, 3 conversion failure. Output under 1 KB indicates a failed engine path even if an earlier wrapper swallowed the exception.

The engine registry `SUPPORTED_LAYOUTS`, builder map, and `THEME` dict are authoritative. When adding an HTML deck layout, update extractor, builder, and registry together. Builders use theme primitives rather than inline colors.
