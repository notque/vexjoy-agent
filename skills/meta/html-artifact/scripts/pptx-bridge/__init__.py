"""html-artifact PPTX bridge.

Absorbed from the v2 unified-deck prototype on 2026-05-27 (ADR
`adr/unified-deck-pipeline.md`, Shape A). Provides HTML deck -> editable
.pptx via a deterministic THEME dict and structural slide builders.

Modules:
    extract_slides  HTML <section class="slide"> -> slide-map dict list
    _pptx_engine    slide-map dict list -> .pptx via python-pptx
    render_pptx     optional .pptx -> PNG QA via soffice / pdftoppm
    run-unified     CLI entry point
"""
