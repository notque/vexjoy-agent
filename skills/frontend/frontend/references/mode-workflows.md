# Frontend Mode Workflows: DESIGN, DISTINCTIVE, HTML-ARTIFACT, and THREEJS

Detailed phase steps for the four visual modes of `frontend`. Read `skills/shared-patterns/ui-design-judgment.md` first before running any UI mode.

## DESIGN Mode

Always load `references/design-refs/llm-design-failure-modes.md` alongside the sub-mode reference.

| Sub-mode | Signals | Load |
|---|---|---|
| UX-COPY | write copy, button text, error message, empty state, tooltip | `references/design-refs/ux-copy.md` |
| DESIGN-SYSTEM | design tokens, component library, audit components, theme | `references/design-refs/design-systems.md` |
| CRITIQUE | review design, critique mockup, design feedback, usability | `references/design-refs/design-critique.md` |
| ACCESSIBILITY | WCAG, accessibility audit, color contrast, keyboard nav, a11y | `references/design-refs/accessibility-review.md` |
| HANDOFF | developer handoff, spec sheet, implementation spec, responsive | `references/design-refs/design-handoff.md` |
| RESEARCH | synthesize research, interview analysis, usability findings | (inline below) |

- **UX-COPY:** Gather context (component type, user state, voice, constraints), draft primary copy with rationale plus 2-3 alternatives and localization notes, and validate What/Why/Fix error structure and length limits. **Gate:** copy + rationale + differentiated alternatives for every component.
- **DESIGN-SYSTEM:** Audit (naming, token coverage, hardcoded values, states), Document (props/variants/states/a11y/usage), or Extend using color, typography, spacing, border, shadow, and motion tokens across default/hover/active/disabled/loading/error states.
- **CRITIQUE:** Open the rendered design, run core doc section 10 checks (three widths, squint, grayscale, edge content), and rank findings by content/job, hierarchy, spacing, type, color, polish as element + problem + effect + fix.
- **ACCESSIBILITY:** Audit WCAG Perceivable (1.1.1 alt, 4.5:1 text / 3:1 UI contrast), Operable (2.1.1 keyboard, 2.4.3 focus order, 44x44px touch), Understandable (3.2.1 predictable, 3.3.1 errors), Robust (4.1.2 name/role/value); emit severity matrix, contrast table, and keyboard map.
- **HANDOFF:** Document layout, tokens, components, states, interactions, content limits, edge cases (empty/loading/error/overflow/i18n), accessibility, and animation.
- **RESEARCH:** Extract behavioral observations and quotes from transcripts/surveys/tickets, synthesize themes via affinity mapping, rank by impact x frequency, and output summary, evidence themes, insights-to-opportunities, segments, and recommendations.

**Output conventions:** Markdown tables; Critical (blocks users), Major (degrades), Minor (polish); element + issue + concrete fix; include strengths alongside issues.

---

## DISTINCTIVE Mode

Brand-led visual direction for landing, launch, portfolio, and event pages. Output: tokens, base styles, and a rendered page.

1. **Surface check (core doc section 1):** Classify as **Tool** (use `ui-design-recipes.md` neutral sans, tinted grays + one accent, 4/8 spacing, borders over shadows, motion for state changes only), **Brand page** (continue below), or **Mixed** (brand rules for public pages, tool rules for app).
2. **Brief:** Gather real content (`references/distinctive-frontend-design-refs/honest-placeholders.md` for gaps); choose one structure from `macrostructure-catalog.md`; write visual, content, and interaction theses; compare two candidate directions (`color-inspirations.json`, `font-catalog.json`, `phase-details.md`) and commit to one with rationale.
3. **Type:** Choose one display face and one text face from `font-catalog.json` matched to the direction; body 16 px, headings 1.1-1.25 line height.
4. **Color:** Start with brand-tinted neutral grays plus one brand accent (~60/30/10 starting point), build scales via `oklch-color-harmony.md`, verify 4.5:1 body / 3:1 large+UI contrast, and define dark mode with its own values.
5. **Motion and background:** Budget 2-3 intentional motions (150-250 ms ease-out UI, <=600 ms hero entrance, honor `prefers-reduced-motion`; `animation-patterns.md`). Default to a solid surface; add at most one atmospheric effect (`background-techniques.md`) while preserving contrast. Full-bleed hero with one composition and one primary action.
6. **Build and check:** Emit design stamp comment, CSS custom properties, and base styles (`implementation-examples.md`). Run `python3 ${CLAUDE_SKILL_DIR}/scripts-distinctive-frontend-design/validate_design.py --fonts "Display,Body" --palette palette.json --project NAME --macrostructure macro:ID --emitted-css generated.html` (`--strict` exits 1 below 80).
7. **Look, then fix:** Run core doc section 10 loop on the rendered page.

---

## HTML-ARTIFACT Mode

Single self-contained `.html` files (inline `<style>` and `<script>`, zero CDN/external deps, max 500 KB). Write local files to disk and open in Google Chrome; reserve Claude Artifact publishing for explicit requests, and use Perses for metrics dashboards.

0. **Check Saved Template:** Run `python3 ${CLAUDE_SKILL_DIR}/scripts-html-artifact/fill-template.py --list`. If a template matches, clone and fill slots only, then jump to Phase 4.
1. **Detect Shape:** Run `python3 ${CLAUDE_SKILL_DIR}/scripts-html-artifact/detect-shape.py --request "{request}"` across `spec`, `code-review`, `prototype`, `report`, `editor`, `data-viz`, `diagram`, `deck` (default `report`).
2. **Assemble + Load Context:** Run `python3 ${CLAUDE_SKILL_DIR}/scripts-html-artifact/assemble-template.py --shape {shape} --title "{title}" --components {components}`. Load `references/html-artifact-refs/design-system.md` (embed `templates/fonts/archivo-black.css`, weight 400, `font-synthesis: none`). For diagrams, also load `shape-diagram-illustration.md` and `diagram-layering.md`.
3. **Generate:** Dispatch a subagent with prompt `agents/html-builder.md` and the pre-assembled template (vanilla JS, semantic HTML, inline SVG).
4. **Validate, then look:** Run `python3 ${CLAUDE_SKILL_DIR}/scripts-html-artifact/validate-artifact.py {html_file}` (fix all errors up to 3 retries), then run core doc section 10 loop on the rendered file.
5. **Deliver:** Open locally in Google Chrome (`open -a "Google Chrome" <file>` on macOS, `google-chrome <file>` on Linux when `$DISPLAY` is set and `$SSH_TTY` is unset) and print absolute path + 1-line summary.
6. **Export (optional):** PDF via `to-pdf.py --input <html> --output <pdf> --json`; PPTX (deck shape only) via `pptx-bridge/run-unified.py --input <html> --format pptx --out <pptx> --no-render`.

---

## THREEJS Mode

Four phases: Design, Build, Animate, Polish.

1. **Design:** Detect paradigm first (ask if ambiguous, since imperative and R3F conflict):
   - R3F (`@react-three/fiber`, drei, `useFrame`) -> `references/threejs-builder-refs/react-three-fiber.md`
   - WebGPU (`WebGPURenderer`, TSL, compute shader) -> `references/threejs-builder-refs/webgpu.md`
   - Imperative (vanilla `new THREE.Scene()`) -> `references/threejs-builder-refs/advanced-topics.md`
   - Add `game-architecture.md` + `game-patterns.md` for game controllers, and `gltf-loading.md` for `.glb`/skeletal rigs. Select boilerplate from `build-recipes.md`.
2. **Build:** Follow loaded paradigm reference (imperative default: single HTML, `CONFIG`, three-point lighting, `renderer.setAnimationLoop()`).
3. **Animate:** Use `useFrame` in R3F and `setAnimationLoop` in imperative mode; pre-allocate geometry and materials outside the animation loop.
4. **Polish:** Remove debug helpers, handle window resize, verify visible lighting, run `build-recipes.md` checks, and finish with core doc section 10 loop.
