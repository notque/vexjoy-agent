# PPTX to self-contained HTML

Use `python-pptx` to extract evidence, then rebuild with this skill's HTML templates. This is semantic conversion, not pixel-perfect import.

## Extraction contract

In one pass, retain slide order/count, text, notes, pictures, and group descendants.

- Check `shape.has_text_frame` before `.text_frame`; pictures, tables, and groups do not expose it.
- Read notes through `slide.notes_slide.notes_text_frame` under `try/except AttributeError`; blank-template slides frequently have no notes placeholder.
- A picture is available only when `shape.shape_type == MSO_SHAPE_TYPE.PICTURE`. Base64-encode `shape.image.blob` as a data URI so the output stays one file.
- Recurse through grouped shapes. Skipping groups silently loses content.
- Preserve table content separately when structure matters; flattening it into text destroys row/column meaning.
- Validate extracted count against `len(prs.slides)` before building. Missing slides are an extraction failure, not permission to continue.

Guard the dependency up front and give the actionable install command: `pip install python-pptx`. `PackageNotFoundError` means the path is wrong, the file is corrupt, or it is not an OOXML PPTX.

## Rebuild decisions

Use speaker notes as author context, not visible slide content. Map hierarchy and content to the repository layouts rather than reproducing absolute PowerPoint coordinates. Embed images; do not leave sibling asset files. Unsupported OLE objects, charts, SmartArt, video, transitions, and animations must be disclosed and represented honestly (for example, a labeled placeholder or extracted static preview when available), never silently omitted or fabricated.

After rebuilding, verify:

1. HTML slide count equals source slide count.
2. Each source slide has corresponding visible content or an explicit unsupported-content note.
3. Notes did not leak into the projected surface.
4. Images resolve without external files.
5. `validate-slides.py` passes and the deck was visually checked when rendering is available.
