---
name: frontend-slides
description: |
  Browser-based HTML presentation generation with viewport-fit enforcement.
  Produces a single self-contained HTML file with full keyboard/touch/wheel
  navigation, reduced-motion support, and deterministic overflow validation.
  Three paths: new build from topic/notes, PPTX-to-HTML conversion, or
  enhancement of an existing HTML deck.
  Triggers: "HTML slides", "browser presentation", "web deck", "reveal-style",
  "viewport presentation", "convert PPTX to web", "convert PPTX to HTML",
  "slides for a browser", "kiosk presentation", "interactive presentation
  with keyboard navigation", "projector with a browser".
  Do NOT use when the user wants a .pptx output file, a PowerPoint deck,
  a Keynote file, or "slides to upload to Google Drive / email as attachment"
  (use pptx-generator instead). When the user says only "slides" or "deck"
  without a format, ask one disambiguation question before routing.
version: 1.0.0
user-invocable: false
agent: typescript-frontend-engineer
model: sonnet
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

## Operator Context

This skill operates as an operator for browser-based presentation workflows. It configures
Claude's behavior to enforce viewport-fit as a hard constraint, apply a curated preset catalog,
and implement a full JS navigation controller — never improvising visual style or layout.

### Hardcoded Behaviors (Always Apply)

- **Viewport fit is non-negotiable**: Every `.slide` must have `height: 100vh; height: 100dvh; overflow: hidden`. When content overflows, the rule is split the slide, never shrink text.
- **CSS base block verbatim**: The mandatory base CSS block from `skills/frontend-slides/references/STYLE_PRESETS.md` must appear verbatim in every output file. Do not paraphrase or rewrite it.
- **No negated CSS functions**: `clamp()` cannot be negated with a unary minus. Always use `calc(-1 * clamp(...))`. See STYLE_PRESETS.md CSS Gotchas.
- **Density limits enforced**: Apply the density table from STYLE_PRESETS.md without exception. Never add a seventh bullet to a content slide.
- **Full JS controller required**: Keyboard, touch/swipe, wheel navigation, slide index indicator, and Intersection Observer for reveal animations — all required, not optional.
- **Reduced-motion required**: `@media (prefers-reduced-motion: reduce)` block must suppress all animations.
- **Format disambiguation required**: When the user says only "slides" or "deck" without specifying format, ask exactly one question before routing: "Should this be an HTML file (opens in browser) or a PowerPoint file (.pptx)?"
- **Self-contained output**: Output must be a single `.html` file with all CSS and JS inline. No external CDN dependencies.

### Default Behaviors (ON unless disabled)

- **Visual preview approach**: Generate 3 single-slide preview HTML files in `.design/slide-previews/` for style selection when the user has not named a preset.
- **Mood-to-preset mapping**: Use the mood table in STYLE_PRESETS.md to translate the user's mood description to a preset name rather than asking them to choose from a list.
- **PPTX via python-pptx**: On the conversion path, use `python-pptx` as the extractor. Preserve slide notes. Maintain asset order.
- **Cleanup after delivery**: Delete `.design/slide-previews/` at the end unless the user explicitly asks to keep them.
- **OS-appropriate opener**: Deliver the file using the correct OS opener (`open` on macOS, `xdg-open` on Linux, `start` on Windows).
- **Customization summary**: After delivery, print the 3 easiest CSS custom properties the user can change for re-theming.
- **Playwright validation**: Run `skills/frontend-slides/scripts/validate-slides.py` as the viewport-fit gate. Fall back to the manual checklist gate only if Playwright is unavailable (exit code 2).

### Optional Behaviors (OFF unless enabled)

- **Keep preview files**: Retain `.design/slide-previews/` if user requests them for reuse.
- **Speaker notes panel**: Add a visible notes panel toggled by `n` key if user wants speaker view.
- **Print stylesheet**: Add `@media print` CSS for PDF-via-browser export if user needs handouts.
- **Slide timer**: Add a configurable countdown timer overlay if user requests timed presentation mode.

---

## Routing Disambiguation: frontend-slides vs pptx-generator

| Dimension | frontend-slides | pptx-generator |
|-----------|-----------------|----------------|
| Output format | Self-contained `.html` file | `.pptx` file |
| Delivery | Opens in browser | Opens in PowerPoint / Keynote / Google Slides |
| Sharing | URL or file attachment | Email attachment, cloud upload |
| Customization | CSS + JS in-file | PowerPoint themes, slide master |
| Input path | Topic, notes, or existing PPTX → HTML | Topic or notes → PPTX |

**Route to `frontend-slides`**: "HTML slides", "browser presentation", "web deck", "reveal-style", "viewport presentation", "convert PPTX to web/HTML", "slides for a browser/kiosk/projector with a browser", "interactive presentation with keyboard navigation".

**Route to `pptx-generator`**: "PowerPoint", "PPTX", ".pptx", "Keynote-compatible", "Google Slides", "deck I can email", "slides for upload to Drive".

**Ambiguous**: "make me a deck", "create slides" without format → ask one disambiguation question.

---

## Reference Files

Load these files at the phase that requires them. Do not load them all upfront.

| File | Load At | Contains |
|------|---------|----------|
| `skills/frontend-slides/references/STYLE_PRESETS.md` | Phase 3 (DISCOVER STYLE) and Phase 4 (BUILD) | Mandatory CSS base block, 12 named presets, mood mapping, animation feel mapping, CSS gotchas, density limits, validation breakpoints |

---

## Pipeline

### Phase 1: DETECT

Identify which of the three paths applies:

| Path | Signal | Action |
|------|--------|--------|
| **New build** | User provides topic, outline, or notes — no existing file | Proceed to Phase 2 to gather content |
| **PPTX conversion** | User provides a `.pptx` file path | Extract with `python-pptx`; collect slides, notes, and asset order; then proceed to Phase 3 |
| **HTML enhancement** | User provides an existing `.html` deck | Read the file; identify what needs improving; skip to Phase 4 |

**GATE 1**: Do not proceed without identifying the path. If the input is ambiguous (e.g., "make me a deck" with no file and no topic), ask one question to resolve it.

---

### Phase 2: DISCOVER CONTENT

Ask exactly three questions — no more:

1. What is the purpose of this presentation? (e.g., pitch, tutorial, conference talk, internal review)
2. How many slides? (approximate is fine)
3. What is the content state? (bullet points, full prose, raw notes, nothing yet)

Collect or generate the content before touching any style decisions.

**GATE 2**: Content exists (or the user has confirmed topic-only intent with an explicit "I'll provide content as we go") before Phase 3 begins. Do not start style work with no content direction.

---

### Phase 3: DISCOVER STYLE

**Load `skills/frontend-slides/references/STYLE_PRESETS.md` now.**

Two sub-paths:

**Sub-path A — User names a preset directly**: Skip previews. Confirm the preset name exists in STYLE_PRESETS.md. Proceed to Phase 4.

**Sub-path B — User does not know the preset**: Ask for mood using exactly these four options: impressed / energized / focused / inspired. Map the mood to candidate presets using the mood table in STYLE_PRESETS.md. Generate 3 single-slide HTML preview files in `.design/slide-previews/` — one per candidate preset — using real slide content (not placeholder lorem ipsum). Present the previews and ask the user to pick.

**GATE 3**: User has either named a preset from STYLE_PRESETS.md or selected one of the three previews. A vague direction like "make it look professional" is not sufficient — a named preset must be confirmed before Phase 4. If no selection is made, regenerate previews with different presets.

---

### Phase 4: BUILD

**Load `skills/frontend-slides/references/STYLE_PRESETS.md` if not already loaded.**

Build rules (all mandatory):

1. **Single file**: Output is one `.html` file with all CSS and JS inline.
2. **CSS base block verbatim**: Copy the mandatory CSS base block from STYLE_PRESETS.md exactly as written. Apply the chosen preset's theme variables on top.
3. **Density limits**: Apply the density table from STYLE_PRESETS.md without exception.
4. **JS controller class**: Implement `SlideController` with:
   - Keyboard: `ArrowRight`/`ArrowLeft`/`Space` forward; `ArrowLeft`/`Backspace` backward; `Home`/`End` for first/last
   - Touch/swipe: `touchstart`/`touchend` with 50px threshold
   - Wheel: debounced `wheel` event (150ms)
   - Slide index indicator: `currentSlide / totalSlides` visible in corner
   - Intersection Observer: add `.visible` class when slide enters viewport for reveal animations
5. **Reduced-motion**: `@media (prefers-reduced-motion: reduce)` suppresses all transitions and animations.
6. **CSS negation rule**: Never write `-clamp(...)`. Write `calc(-1 * clamp(...))` instead.
7. **Font loading**: Use `@font-face` with `font-display: swap` or system font stacks. Never reference external CDN fonts without a local fallback.
8. **PPTX path**: If converting from PPTX, use `python-pptx` to extract text, notes, and asset paths. If `python-pptx` is unavailable, print a clear error and ask the user to install it (`pip install python-pptx`) or provide content manually — do not silently skip content.

**GATE 4**: The output HTML file exists on disk and contains the verbatim mandatory CSS base block from STYLE_PRESETS.md. Verify with a string search before proceeding. A file that "looks right" is not sufficient — the exact block must be present.

---

### Phase 5: VALIDATE

Run the deterministic validation script:

```bash
python3 skills/frontend-slides/scripts/validate-slides.py path/to/output.html
```

**Exit codes**:
- `0` — All slides pass at all 9 breakpoints. Proceed to Phase 6.
- `1` — Overflow detected. The script prints which slides overflow at which breakpoints. Fix by splitting the overflowing slides. Re-run validation. Do not proceed until exit code is 0.
- `2` — Playwright unavailable. Fall back to the manual checklist gate below.

**Manual checklist gate (fallback, only when exit code is 2)**:

For every slide, verify all of the following. If any item fails, fix it before proceeding. Do not mark this gate passed speculatively.

- [ ] `height: 100vh` and `height: 100dvh` present on `.slide`
- [ ] `overflow: hidden` present on `.slide`
- [ ] All body text uses `clamp()` for font sizing
- [ ] No fixed-height content boxes (no `height: 300px` on inner elements)
- [ ] No `min-height` on `.slide` that could allow growth past 100dvh
- [ ] No `-clamp(...)` patterns anywhere in CSS

**GATE 5**: Exit code 0 from the validation script, or — only if Playwright is unavailable (exit code 2) — explicit user confirmation that the manual checklist passed for every slide. "Looks fine on my screen" is not a gate pass. User confirmation must enumerate the slide count checked.

---

### Phase 6: DELIVER

Delivery sequence:

1. Delete `.design/slide-previews/` (unless user asked to keep them):
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

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| `-clamp(...)` in CSS | CSS negation of `clamp()` is silently ignored by browsers — it computes to `0` | Replace every instance with `calc(-1 * clamp(...))`. Run a grep search for `-clamp` before delivery. |
| Font load failure / FOUT | External font CDN unreachable, or `@font-face` src missing `format()` hint | Use `font-display: swap` on every `@font-face`. Include a system font stack fallback. Test offline. |
| PPTX extraction error | `python-pptx` unavailable, or PPTX uses embedded OLE objects | Print a clear error message naming the missing dependency. Ask the user to `pip install python-pptx` or provide content manually. Do not silently skip slides. |
| Playwright unavailable (exit 2) | `playwright` not installed or Chromium browser not available | Fall back to the manual checklist gate in Phase 5. Explicitly tell the user validation is running in manual mode and is less reliable. |
| Overflow at one breakpoint only | Content fits at 1920x1080 but overflows at 375x667 | `clamp()` sizing solves most cases. If not, split the slide. Never set a smaller viewport as "not important." |
| Reveal animations not triggering | Intersection Observer threshold too high, or slides hidden with `display:none` | Use `display: flex` with `opacity: 0` + `transform` for hidden slides. Never use `display: none` on slides that need IO callbacks. |
| JS controller not advancing | `wheel` event not debounced, causing multi-slide jumps | Enforce 150ms debounce on wheel. Add a `navigating` flag that blocks re-entry during transition. |

---

## Anti-Patterns

Never do these. They are failure modes, not style choices.

| Anti-Pattern | Why It Fails | Correct Approach |
|--------------|-------------|------------------|
| Generic purple gradient background | Signals AI-generated content, visually dated, no alignment with user's brand or message | Use a named preset from STYLE_PRESETS.md. Generic gradients are not a style — they are the absence of style. |
| Negated `clamp()`: `-clamp(2rem, 3vw, 4rem)` | Silently computes to `0` in all browsers — text disappears or collapses | Always use `calc(-1 * clamp(2rem, 3vw, 4rem))` when a negative value is needed |
| Scrollable content inside a slide | Breaks the "each slide = one viewport" contract; audiences cannot scroll during a live presentation | Split the slide into multiple slides. If content genuinely needs scrolling, that is a web page, not a slide. |
| Fixed-height inner boxes | `height: 300px` on an image or code block causes overflow at smaller viewports | Use `max-height: min(Xvh, Ypx)` with `overflow: hidden`. Resize the asset, not the slide. |
| Font loading failure silent fallback | Missing `font-display: swap` causes invisible text during load (FOIT) | Always declare `font-display: swap` and a system font stack fallback. Test with network throttling. |
| Bullet walls (7+ bullets per slide) | Dense text is unreadable in a presentation context; audiences read or listen, not both | Enforce the density table: max 6 bullets per content slide. Split into multiple slides if needed. |
| Missing keyboard navigation | Mouse-only or click-only decks are inaccessible and break projector workflows | Implement `SlideController` with the full keyboard + touch + wheel interface. |
| `display: none` on slides for animation | Intersection Observer never fires on `display: none` elements | Use `opacity: 0` + `transform: translateY(20px)` to hide, not `display: none`. |

---

## Anti-Rationalization

| Rationalization | Reality | Required Action |
|-----------------|---------|-----------------|
| "Slide looks fine on my screen" | Your screen is one of 9 required breakpoints | Run `validate-slides.py`. Do not ship until exit code 0. |
| "User won't resize the browser during a presentation" | Projectors, kiosks, and conference room displays vary; the skill requirement is 9 breakpoints | Validate all 9 breakpoints. The user's assumption is not a gate pass. |
| "Splitting adds too many slides" | A presentation with 18 tight slides is better than one with 12 overflowing ones | Split. Density limits exist because cognitive load is real. |
| "The CSS base block is already implied by my styles" | The base block must be present verbatim for validation and portability | Copy the block exactly from STYLE_PRESETS.md. Do not paraphrase. |
| "Playwright check is optional if it looks right" | Visual inspection misses mobile breakpoints and zoom interactions | Exit code 2 triggers the manual checklist. Exit code 0 is required to pass Gate 5. |
