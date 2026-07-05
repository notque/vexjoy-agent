
# Frontend Slides Skill

Generate browser-based HTML presentations as a single self-contained `.html` file. Three entry paths: new build from topic/notes, PPTX-to-HTML conversion, or enhancement of an existing HTML deck.

**Routing disambiguation**: When the user says only "slides" or "deck" without specifying format, ask exactly one question before proceeding: "Should this be an HTML file (opens in browser) or a PowerPoint file (.pptx)?" This skill only produces HTML — it converts an existing PPTX to HTML but cannot generate a new .pptx file.

## Reference Loading Table

| Signal | Load These Files | Why |
|--------|-----------------|-----|
| Phase 3 (style selection) or Phase 4 (build) | `references/STYLE_PRESETS.md` | CSS base block, 12 named presets, mood mapping, density limits, validation breakpoints |
| SlideController, keyboard nav, touch swipe, wheel scroll, Intersection Observer, reveal animation | `references/slide-controller.md` | Canonical JS implementation, `navigating` guard, wheel debounce, IO reveal pattern, failure modes with detection commands |
| PPTX, `.pptx`, python-pptx, convert slides, extract slides | `references/pptx-conversion.md` | Safe extraction loop, notes guard, GROUP shape recursion, base64 image embedding, error-fix mappings |

## Instructions

### Phase 1: DETECT

Identify which of the three paths applies:

| Path | Signal | Action |
|------|--------|--------|
| **New build** | User provides topic, outline, or notes -- no existing file | Proceed to Phase 2 to gather content |
| **PPTX conversion** | User provides a `.pptx` file path | Extract with `python-pptx`; collect slides, notes, and asset order; then proceed to Phase 3 |
| **HTML enhancement** | User provides an existing `.html` deck | Read the file; identify what needs improving; skip to Phase 4 |

**GATE 1**: Do not proceed without identifying the path. If the input is ambiguous (e.g., "make me a deck" with no file and no topic), ask one question to resolve it.


### Phase 3: DISCOVER STYLE

**Load `skills/frontend/frontend-slides/references/STYLE_PRESETS.md` now.**

Two sub-paths:

**Sub-path A -- User names a preset directly**: Skip previews. Confirm the preset name exists in STYLE_PRESETS.md. Proceed to Phase 4.

**Sub-path B -- User does not know the preset**: Ask for mood using exactly these four options: impressed / energized / focused / inspired. Map the mood to candidate presets using the mood table in STYLE_PRESETS.md -- translate the user's mood description to a preset name rather than asking them to choose from a list. Generate 3 single-slide HTML preview files in `.design/slide-previews/` -- one per candidate preset -- using real slide content (not placeholder lorem ipsum). Present the previews and ask the user to pick.

**GATE 3**: User has either named a preset from STYLE_PRESETS.md or selected one of the three previews. A vague direction like "make it look professional" is not sufficient -- a named preset must be confirmed before Phase 4. If no selection is made, regenerate previews with different presets. Never fall back to a generic purple gradient; presets exist to avoid exactly that.


### Phase 5: VALIDATE

Run the deterministic validation script:

```bash
python3 skills/frontend/frontend-slides/scripts/validate-slides.py path/to/output.html
```

**Exit codes**:
- `0` -- All slides pass at all 9 breakpoints. Proceed to Phase 6.
- `1` -- Overflow detected. The script prints which slides overflow at which breakpoints. Fix by splitting the overflowing slides. Re-run validation. Do not proceed until exit code is 0. Content that fits at 1920x1080 but overflows at 375x667 still fails -- `clamp()` sizing solves most cases; if not, split the slide.
- `2` -- Playwright unavailable. Fall back to the manual checklist gate below. Tell the user validation is running in manual mode and is less reliable.

**Manual checklist gate (fallback, only when exit code is 2)**:

For every slide, verify all of the following. If any item fails, fix it before proceeding.

- [ ] `height: 100vh` and `height: 100dvh` present on `.slide`
- [ ] `overflow: hidden` present on `.slide`
- [ ] All body text uses `clamp()` for font sizing
- [ ] No fixed-height content boxes (no `height: 300px` on inner elements)
- [ ] No `min-height` on `.slide` that could allow growth past 100dvh
- [ ] No `-clamp(...)` patterns anywhere in CSS

**GATE 5**: Exit code 0 from the validation script, or -- only if Playwright is unavailable (exit code 2) -- explicit user confirmation that the manual checklist passed for every slide. User confirmation must enumerate the slide count checked.

