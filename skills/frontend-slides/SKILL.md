---
name: frontend-slides
description: "Browser-based HTML presentation generation."
user-invocable: false
agent: typescript-frontend-engineer
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
routing:
  triggers:
    - HTML slides
    - browser presentation
    - web deck
    - reveal-style
    - viewport presentation
    - convert PPTX to web
    - convert PPTX to HTML
    - slides for a browser
    - kiosk presentation
    - interactive presentation keyboard
    - projector browser
  pairs_with:
    - typescript-frontend-engineer
    - pptx-generator
  complexity: Medium
  category: frontend
---

# Frontend Slides Skill

Generate browser-based HTML presentations as a single self-contained `.html` file. Three entry paths: new build from topic/notes, PPTX-to-HTML conversion, or enhancement of existing HTML deck.

**Routing disambiguation**: When user says only "slides" or "deck" without format, ask: "Should this be an HTML file (opens in browser) or a PowerPoint file (.pptx)?" Route to `pptx-generator` for PowerPoint/Keynote/Google Slides requests.

## Reference Loading Table

| Signal | Load These Files | Why |
|--------|-----------------|-----|
| Phase 3 (style selection) or Phase 4 (build) | `references/STYLE_PRESETS.md` | CSS base block, 12 named presets, mood mapping, density limits, validation breakpoints |
| SlideController, keyboard nav, touch swipe, wheel scroll, Intersection Observer, reveal animation | `references/slide-controller.md` | Canonical JS implementation, `navigating` guard, wheel debounce, IO reveal pattern, anti-patterns with detection commands |
| PPTX, `.pptx`, python-pptx, convert slides, extract slides | `references/pptx-conversion.md` | Safe extraction loop, notes guard, GROUP shape recursion, base64 image embedding, error-fix mappings |

## Instructions

### Phase 1: DETECT

Identify which path applies:

| Path | Signal | Action |
|------|--------|--------|
| **New build** | Topic, outline, or notes -- no existing file | Proceed to Phase 2 |
| **PPTX conversion** | `.pptx` file path provided | Extract with `python-pptx`; collect slides, notes, asset order; proceed to Phase 3 |
| **HTML enhancement** | Existing `.html` deck provided | Read file; identify improvements; skip to Phase 4 |

**GATE 1**: Path identified. If ambiguous, ask one question to resolve.

---

### Phase 2: DISCOVER CONTENT

Ask exactly three questions:
1. Purpose of presentation? (pitch, tutorial, conference talk, internal review)
2. How many slides? (approximate)
3. Content state? (bullets, full prose, raw notes, nothing yet)

Collect or generate content before style decisions.

**GATE 2**: Content exists (or user confirmed topic-only intent) before Phase 3.

---

### Phase 3: DISCOVER STYLE

**Load `skills/frontend-slides/references/STYLE_PRESETS.md` now.**

**Sub-path A -- User names a preset**: Confirm it exists in STYLE_PRESETS.md. Proceed to Phase 4.

**Sub-path B -- User does not know**: Ask for mood using four options: impressed / energized / focused / inspired. Map mood to candidate presets via mood table. Generate 3 single-slide HTML previews in `.design/slide-previews/` using real content. Present previews, ask user to pick.

**GATE 3**: Named preset confirmed. "Make it look professional" is insufficient -- a preset name must be selected. If none selected, regenerate with different presets. Never fall back to a generic purple gradient.

---

### Phase 4: BUILD

**Load `skills/frontend-slides/references/STYLE_PRESETS.md` if not already loaded.**

Build as single `.html` with all CSS and JS inline (no external CDN dependencies):

1. **CSS base block verbatim**: Copy mandatory CSS base block from STYLE_PRESETS.md exactly. Apply chosen preset's theme variables on top. Validation script checks for it character-for-character.

2. **Viewport fit**: Every `.slide` must have `height: 100vh; height: 100dvh; overflow: hidden`. On overflow, split the slide -- never shrink text, add scrollbars, or use `min-height`.

3. **Density limits**: Maximum 6 bullets per content slide. 7th bullet = split into two slides.

4. **Responsive sizing**: All body text uses `clamp()`. No fixed-height content boxes. For images/code blocks needing height constraints, use `max-height: min(Xvh, Ypx)` with `overflow: hidden`.

5. **CSS negation rule**: Never write `-clamp(...)` -- browsers compute it to `0`. Always write `calc(-1 * clamp(...))`.

6. **JS controller class (`SlideController`)** -- all required:
   - Keyboard: `ArrowRight`/`Space` forward; `ArrowLeft`/`Backspace` backward; `Home`/`End` first/last
   - Touch/swipe: `touchstart`/`touchend` with 50px threshold
   - Wheel: debounced `wheel` event (150ms) with `navigating` flag blocking re-entry
   - Slide index indicator: `currentSlide / totalSlides` visible in corner
   - Intersection Observer: `.visible` class on viewport entry for reveal animations. Use `opacity: 0` + `transform: translateY(20px)` -- never `display: none` (prevents IO callbacks)

7. **Reduced-motion**: `@media (prefers-reduced-motion: reduce)` block suppressing all transitions/animations.

8. **Font loading**: `@font-face` with `font-display: swap` and system font fallback. Never reference CDN fonts without local fallback.

9. **PPTX path**: Use `python-pptx` to extract text, notes, asset paths. Preserve notes and asset order. If unavailable, print error and ask user to install (`pip install python-pptx`).

**Optional features** (off by default, add only on request):
- Speaker notes panel toggled by `n` key
- `@media print` CSS for PDF export
- Countdown timer overlay

**GATE 4**: Output HTML exists and contains verbatim mandatory CSS base block. Verify with string search.

---

### Phase 5: VALIDATE

```bash
python3 skills/frontend-slides/scripts/validate-slides.py path/to/output.html
```

**Exit codes**:
- `0` -- All slides pass at all 9 breakpoints. Proceed.
- `1` -- Overflow detected. Script prints which slides overflow at which breakpoints. Fix by splitting. Re-run until exit 0.
- `2` -- Playwright unavailable. Fall back to manual checklist. Tell user validation is less reliable.

**Manual checklist (only when exit code 2)**:

Per slide verify:
- [ ] `height: 100vh` and `height: 100dvh` on `.slide`
- [ ] `overflow: hidden` on `.slide`
- [ ] All body text uses `clamp()`
- [ ] No fixed-height content boxes
- [ ] No `min-height` on `.slide` exceeding 100dvh
- [ ] No `-clamp(...)` in CSS

**GATE 5**: Exit code 0, or (Playwright unavailable only) user confirms manual checklist passed with slide count.

---

### Phase 6: DELIVER

1. Delete `.design/slide-previews/` unless user asked to keep: `rm -rf .design/slide-previews/`
2. Open file: macOS `open`, Linux `xdg-open`, Windows `start`
3. Print delivery summary:
   ```
   File:    path/to/output.html
   Preset:  [preset-name]
   Slides:  [N]
   Theme:   [3 CSS custom properties for re-theming]
   ```

**GATE 6**: Summary printed. File exists. Previews deleted (or user confirmed keep).

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| `-clamp(...)` in CSS | Browsers compute to `0` | Replace with `calc(-1 * clamp(...))`. Grep for `-clamp` before delivery. |
| Font load failure / FOUT | CDN unreachable or missing `format()` hint | Use `font-display: swap`. Include system font fallback. Test offline. |
| PPTX extraction error | `python-pptx` unavailable or embedded OLE objects | Print error naming missing dependency. Ask user to `pip install python-pptx`. |
| Playwright unavailable (exit 2) | Not installed or Chromium unavailable | Fall back to manual checklist. Tell user. |
| Overflow at one breakpoint | Fits 1920x1080 but overflows 375x667 | `clamp()` sizing fixes most cases. Otherwise split the slide. |
| Reveal animations not triggering | IO threshold too high or `display:none` on slides | Use `display: flex` with `opacity: 0` + `transform`. Never `display: none` on IO-observed slides. |
| JS controller not advancing | Wheel event not debounced | 150ms debounce + `navigating` flag. |

## References

| File | Load At | Contains |
|------|---------|----------|
| `skills/frontend-slides/references/STYLE_PRESETS.md` | Phase 3 and Phase 4 | Mandatory CSS base block, 12 presets, mood mapping, density limits, validation breakpoints |
| `skills/frontend-slides/references/slide-controller.md` | Phase 4 (JS controller) | Canonical SlideController, `navigating` guard, wheel debounce, IO reveal, anti-patterns |
| `skills/frontend-slides/references/pptx-conversion.md` | Phase 1 (PPTX path) | Safe python-pptx extraction, notes guard, GROUP shape recursion, base64 embedding, error-fix table |
