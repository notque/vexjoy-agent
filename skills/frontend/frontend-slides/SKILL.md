---
name: frontend-slides
promoted_to: frontend
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
  complexity: Medium
  category: frontend
---

# Frontend Slides Skill

Generate browser-based HTML presentations as a single self-contained `.html` file. Three entry paths: new build from topic/notes, PPTX-to-HTML conversion, or enhancement of an existing HTML deck.

**Routing disambiguation**: When the user says only "slides" or "deck" without specifying format, ask exactly one question before proceeding: "Should this be an HTML file (opens in browser) or a PowerPoint file (.pptx)?" This skill only produces HTML — it converts an existing PPTX to HTML but cannot generate a new .pptx file.

### Style Presets

Assemble CSS: `python3 skills/frontend/frontend-slides/scripts/assemble-styles.py --preset <name>`. Use `--list` for all 12, `--mood <word>` to match.

Templates: `templates/base.css` (mandatory base), `templates/presets/*.css` (preset `:root` variables).

| Preset | Mood | Use Case |
|--------|------|----------|
| obsidian-gold | impressed | executive briefings, boards |
| arctic-minimal | focused | engineering, dev conferences |
| carbon-ember | energized | product launches, pitches |
| sage-paper | inspired | thought leadership, narrative |
| void-neon | futuristic | dev tools, AI, hackathons |
| slate-coral | contemporary | SaaS demos, sales |
| chalk-board | educational | workshops, training |
| glacier-blue | trusted | financial, legal, healthcare |
| rose-noir | artistic | fashion, design portfolios |
| solar-sand | warm | non-profit, community |
| steel-wire | industrial | data science, DevOps |
| lavender-mist | calm | wellness, meditation |

### Slide Layouts (inline -- was references/slide-layout-patterns.md)

Assemble layout CSS: `python3 skills/frontend/frontend-slides/scripts/assemble-layouts.py --layouts title,content,code`. `--all` for everything, `--include-html` for HTML templates.

Each layout in `templates/layouts/` has paired `.html` + `.css`: title, content, grid, code, quote, image, section-break.

### Controller Diagnostics (inline -- was references/js-controller-patterns.md)

Assemble controller: `python3 skills/frontend/frontend-slides/scripts/assemble-controllers.py --core`. Add `--features speaker-notes,countdown-timer`.

| Symptom | Check | Fix |
|---------|-------|-----|
| Skips slides on keypress | `grep -c 'navigating'` | Add `navigating` guard to `go()` |
| Trackpad jumps to end | `rg 'clearTimeout'` | 150ms debounce on wheel |
| Animations never fire | `grep 'display.*none'` | Use `opacity:0` not `display:none` |
| Swipe fires on scroll | `grep 'screenY'` | `abs(dy) > abs(dx)` guard |
| Space scrolls page | `grep -A1 'Space'` | `e.preventDefault()` before `next()` |

## Instructions

### Phase 1: DETECT

Identify which of the three paths applies:

| Path | Signal | Action |
|------|--------|--------|
| **New build** | User provides topic, outline, or notes -- no existing file | Proceed to Phase 2 to gather content |
| **PPTX conversion** | User provides a `.pptx` file path | Extract with `python-pptx`; collect slides, notes, and asset order; then proceed to Phase 3 |
| **HTML enhancement** | User provides an existing `.html` deck | Read the file; identify what needs improving; skip to Phase 4 |

**GATE 1**: Do not proceed without identifying the path. If the input is ambiguous (e.g., "make me a deck" with no file and no topic), ask one question to resolve it.

---

### Phase 2: DISCOVER CONTENT

Ask exactly three questions -- no more:

1. What is the purpose of this presentation? (e.g., pitch, tutorial, conference talk, internal review)
2. How many slides? (approximate is fine)
3. What is the content state? (bullet points, full prose, raw notes, nothing yet)

Collect or generate the content before touching any style decisions.

**GATE 2**: Content exists (or the user has confirmed topic-only intent with an explicit "I'll provide content as we go") before Phase 3 begins. Do not start style work with no content direction.

---

### Phase 3: DISCOVER STYLE

Use the Style Presets table (above) to map mood to preset names.

Two sub-paths:

**Sub-path A -- User names a preset directly**: Skip previews. Confirm the preset name exists in the Style Presets table. Proceed to Phase 4.

**Sub-path B -- User does not know the preset**: Ask for mood using exactly these four options: impressed / energized / focused / inspired. Map the mood to candidate presets using the Style Presets table -- translate the user's mood description to a preset name rather than asking them to choose from a list. Generate 3 single-slide HTML preview files in `.design/slide-previews/` -- one per candidate preset -- using real slide content (not placeholder lorem ipsum). Present the previews and ask the user to pick.

**GATE 3**: User has either named a preset from the Style Presets table or selected one of the three previews. A vague direction like "make it look professional" is not sufficient -- a named preset must be confirmed before Phase 4. If no selection is made, regenerate previews with different presets. Never fall back to a generic purple gradient; presets exist to avoid exactly that.

---

### Phase 4: BUILD

Build the presentation as a single `.html` file with all CSS and JS inline (no external CDN dependencies). Follow these rules:

1. **CSS base block verbatim**: Copy the mandatory CSS base block from `templates/base.css` exactly as written -- do not paraphrase or rewrite it. Apply the chosen preset's theme variables on top. The base block must be present character-for-character because the validation script checks for it.

2. **Viewport fit on every slide**: Every `.slide` element must have `height: 100vh; height: 100dvh; overflow: hidden`. When content overflows, split the slide into multiple slides -- never shrink text, add scrollbars, or set `min-height` that could allow growth past 100dvh. A slide with scrollable content is a web page, not a slide.

3. **Density limits**: Apply the Density Limits table (above) without exception. Maximum 6 bullets per content slide. If content needs a 7th bullet, split into two slides -- dense text is unreadable in presentation context.

4. **Responsive sizing**: All body text must use `clamp()` for font sizing. No fixed-height content boxes (`height: 300px` on inner elements). For images or code blocks that need height constraints, use `max-height: min(Xvh, Ypx)` with `overflow: hidden`.

5. **CSS negation rule**: Never write `-clamp(...)` -- browsers silently compute it to `0`, causing text to disappear. Always write `calc(-1 * clamp(...))` when a negative value is needed.

6. **JS controller class**: Implement `SlideController` with all of the following (not optional):
   - Keyboard: `ArrowRight`/`ArrowLeft`/`Space` forward; `ArrowLeft`/`Backspace` backward; `Home`/`End` for first/last
   - Touch/swipe: `touchstart`/`touchend` with 50px threshold
   - Wheel: debounced `wheel` event (150ms) -- without debounce, wheel events cause multi-slide jumps. Add a `navigating` flag that blocks re-entry during transition.
   - Slide index indicator: `currentSlide / totalSlides` visible in corner
   - Intersection Observer: add `.visible` class when slide enters viewport for reveal animations. Use `opacity: 0` + `transform: translateY(20px)` to hide slides before reveal -- never `display: none`, which prevents Intersection Observer callbacks.

7. **Reduced-motion**: Include a `@media (prefers-reduced-motion: reduce)` block that suppresses all transitions and animations.

8. **Font loading**: Use `@font-face` with `font-display: swap` and a system font stack fallback. Never reference external CDN fonts without a local fallback. Missing `font-display: swap` causes invisible text during load (FOIT).

9. **PPTX path**: If converting from PPTX, use `python-pptx` to extract text, notes, and asset paths. Preserve slide notes and maintain asset order. If `python-pptx` is unavailable, print a clear error and ask the user to install it (`pip install python-pptx`) or provide content manually -- do not silently skip content.

**Optional features** (off by default, add only when user requests):
- Speaker notes panel toggled by `n` key
- `@media print` CSS for PDF-via-browser export
- Configurable countdown timer overlay

**GATE 4**: The output HTML file exists on disk and contains the verbatim mandatory CSS base block from `templates/base.css`. Verify with a string search before proceeding -- a file that "looks right" is not sufficient.

---

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

---

### Phase 6: DELIVER

1. Delete `.design/slide-previews/` unless the user explicitly asked to keep them:
   ```bash
   rm -rf .design/slide-previews/
   ```

2. Open the file with the OS-appropriate command:
   - macOS: `open path/to/output.html`
   - Linux: `xdg-open path/to/output.html`
   - Windows: `start path/to/output.html`

3. Print a delivery summary:
   ```
   File:    path/to/output.html
   Preset:  [preset-name]
   Slides:  [N]
   Theme:   [3 CSS custom properties easiest to change for re-theming]
   ```

**GATE 6**: Delivery summary printed. File exists at the stated path. Previews deleted (or user confirmed to keep). Task is complete only when all three conditions are met.

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| `-clamp(...)` in CSS | CSS negation of `clamp()` is silently ignored by browsers -- it computes to `0` | Replace every instance with `calc(-1 * clamp(...))`. Run a grep search for `-clamp` before delivery. |
| Font load failure / FOUT | External font CDN unreachable, or `@font-face` src missing `format()` hint | Use `font-display: swap` on every `@font-face`. Include a system font stack fallback. Test offline. |
| PPTX extraction error | `python-pptx` unavailable, or PPTX uses embedded OLE objects | Print a clear error message naming the missing dependency. Ask the user to `pip install python-pptx` or provide content manually. Do not silently skip slides. |
| Playwright unavailable (exit 2) | `playwright` not installed or Chromium browser not available | Fall back to the manual checklist gate in Phase 5. Explicitly tell the user validation is running in manual mode and is less reliable. |
| Overflow at one breakpoint only | Content fits at 1920x1080 but overflows at 375x667 | `clamp()` sizing solves most cases. If not, split the slide. Never set a smaller viewport as "not important." |
| Reveal animations not triggering | Intersection Observer threshold too high, or slides hidden with `display:none` | Use `display: flex` with `opacity: 0` + `transform` for hidden slides. Never use `display: none` on slides that need IO callbacks. |
| JS controller not advancing | `wheel` event not debounced, causing multi-slide jumps | Enforce 150ms debounce on wheel. Add a `navigating` flag that blocks re-entry during transition. |

## Deep References

| Signal | Reference |
|--------|-----------|
| Phase 4 BUILD: JS controller implementation | `references/slide-controller.md` |
| Phase 1 DETECT: PPTX extraction and conversion | `references/pptx-conversion.md` |
