---
name: frontend
description: "Frontend: UI design, distinctive visual styles, HTML artifacts, Three.js 3D."
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Agent
  - Skill
routing:
  force_route: false
  not_for: "game UI (use game-dev), backend work (use workflow), brand or logo design without code"
  triggers:
    - "design"
    - "UX copy"
    - "design system"
    - "accessibility"
    - "WCAG"
    - "design handoff"
    - "frontend design"
    - "visual identity"
    - "HTML artifact"
    - "make HTML"
    - "self-contained HTML"
    - "threejs"
    - "three.js"
    - "3D web"
    - "3D scene"
    - "WebGL"
    - "WebGPU"
    - "react three fiber"
    - "r3f"
    - "text animation"
    - "card effects"
    - "pptx"
    - "powerpoint"
    - "slide deck"
    - "design critique"
  category: frontend
  pairs_with:
    - typescript-frontend-engineer
    - ui-frontend-engineer
    - game-dev
---

# Frontend Skill

Four modes: **Design** (UX copy, design systems, critique, accessibility, handoff,
research), **Distinctive** (surface check, then brand-led visual direction for
landing and campaign pages), **HTML-Artifact** (self-contained HTML generation with 8 shapes), and
**Three.js** (3D web apps in imperative, R3F, or WebGPU paradigms).

## Load first for any UI work

Before DESIGN, DISTINCTIVE, HTML-ARTIFACT, or a THREEJS UI overlay (HUD, menu, panel), read `skills/shared-patterns/ui-design-judgment.md`. Take starting values from `ui-design-recipes.md` and before/after fixes from `ui-design-examples.md` in the same folder. The mode references below add depth. Where they conflict with the core doc, the core doc wins. Every default can be overridden; state the reason.

## Mode Selection

Classify the request into one mode before loading references.

| Mode | Signals | What to Load |
|------|---------|-------------|
| **DESIGN** | UX copy, design system, design critique, accessibility, WCAG, design handoff, user research | Design-refs per sub-mode table below |
| **DISTINCTIVE** | Frontend design, typography, visual identity, anti-cliche, text animation, card effects | `references/distinctive-frontend-design-refs/` per step |
| **HTML-ARTIFACT** | HTML artifact, make HTML, as HTML, rich visualization, interactive document, pptx, deck | `references/html-artifact-refs/` per shape |
| **THREEJS** | Three.js, 3D scene, WebGL, WebGPU, react three fiber, R3F, GLTF | `references/threejs-builder-refs/` per paradigm |

---

## DESIGN Mode

Design methodology: UX copy, design systems, critique, accessibility review,
developer handoff, user research synthesis. Always load
`references/design-refs/llm-design-failure-modes.md` alongside mode-specific
reference.

### Sub-mode Detection

| Sub-mode | Signals | Load |
|----------|---------|------|
| UX-COPY | write copy, button text, error message, empty state, tooltip | `references/design-refs/ux-copy.md` |
| DESIGN-SYSTEM | design tokens, component library, audit components, theme | `references/design-refs/design-systems.md` |
| CRITIQUE | review design, critique mockup, design feedback, usability | `references/design-refs/design-critique.md` |
| ACCESSIBILITY | WCAG, accessibility audit, color contrast, keyboard nav, a11y | `references/design-refs/accessibility-review.md` |
| HANDOFF | developer handoff, spec sheet, implementation spec, responsive | `references/design-refs/design-handoff.md` |
| RESEARCH | synthesize research, interview analysis, usability findings | (inline below) |

### UX-COPY

1. Gather context: component type, user emotional state, brand voice, constraints, existing terminology.
2. Generate copy: primary recommendation with rationale, 2-3 alternatives, localization notes.
3. Validate: terminology consistency, action labels match outcomes, error messages follow What/Why/Fix, character limits met.

**Gate**: Copy for all requested components. Each piece has rationale. Alternatives differentiated.

### DESIGN-SYSTEM

Three operations: **Audit** (naming consistency, token coverage, hardcoded values, state completeness), **Document** (props/variants/states/a11y/usage spec), **Extend** (new component using existing tokens). Use design token architecture: color, typography, spacing, borders, shadows, motion.

Validate: consistent naming, all values reference tokens, all states defined (default/hover/active/disabled/loading/error), ARIA documented.

### CRITIQUE

Render or open the design first, then run the core doc's section 10 checks (three widths, squint, grayscale, edge content) and rank findings in its fix order: content and job, hierarchy, spacing, type, color, polish. Write each finding as element, problem, effect, fix. Apply Nielsen heuristics only where they explain a real finding. Match depth to stage: exploration (concept direction), refinement (hierarchy, patterns), final (contrast, spacing, a11y).

### ACCESSIBILITY

Audit by WCAG principle: Perceivable (alt text 1.1.1, contrast 4.5:1 text / 3:1 UI), Operable (keyboard 2.1.1, focus order 2.4.3, touch 44x44px), Understandable (predictable 3.2.1, error ID 3.3.1), Robust (name/role/value 4.1.2). Report: severity matrix, each finding with WCAG criterion + remediation, contrast table, keyboard map.

### HANDOFF

Gather: design source, tech stack, tokens, breakpoints. Generate spec covering: layout, tokens, components, states, interactions, content limits, edge cases (empty/loading/error/overflow/i18n), accessibility, animation. Validate: all states documented, token references used, edge cases present.

### RESEARCH

Accept inputs (transcripts, surveys, support tickets). Extract observations and quotes -- behavioral data outweighs stated preferences. Synthesize via affinity mapping and theme development. Priority matrix (impact x frequency). Output: executive summary, themes with evidence, insights-to-opportunities table, user segments, recommendations.

### Output Conventions

Markdown with tables. Severity: Critical (blocks users), Major (degrades), Minor (polish). Every recommendation names element + issue + concrete fix. Include what works alongside what needs improvement.

---

## DISTINCTIVE Mode

Brand-led visual direction for pages people visit once: landing, launch, portfolio, event. Output: tokens, base styles, and a rendered page.

### Step 1: Surface check

Name the surface before any styling (core doc section 1):

| Surface | Examples | Do this |
|---|---|---|
| Tool | dashboard, admin, editor, settings, internal app | Get real content (Step 2 item 1), then use the tool recipe in `ui-design-recipes.md`: one neutral sans (system UI font, Inter, Geist), tinted grays plus one accent, 4/8 spacing scale, borders over shadows, motion only for state changes. Build tokens (Step 6 item 1), then Step 7. |
| Brand page | landing, launch, portfolio, event, campaign | Continue with Step 2. |
| Mixed (marketing site with an app inside) | pricing page plus signed-in app | Brand rules for public pages, tool rules for the app. |

Litmus: on a tool, a user who reads only headings, labels, and numbers understands the screen. On a brand page, a user who sees the first viewport for 3 seconds can name the product and its promise.

### Step 2: Brief

1. Get real content: product name, headline, main action, real section copy. Mark missing items as placeholders (`references/distinctive-frontend-design-refs/honest-placeholders.md`).
2. Pick one page structure from `references/distinctive-frontend-design-refs/macrostructure-catalog.md` by heading anchor. Load only that entry.
3. Write three sentences: visual thesis (mood), content plan (sections in order, one job each), interaction thesis (the few motions that matter).
4. Write two candidate directions from the brand and audience, pick one, and say why. Use `color-inspirations.json` and `font-catalog.json` in `references/distinctive-frontend-design-refs/` when the brand gives no lead. Do not default to serif display, cream background, and grain; that is the overcorrection tell. Direction examples and per-step values: `references/distinctive-frontend-design-refs/phase-details.md`.

### Step 3: Type

Default: one display face plus one text face, both from `font-catalog.json` and matched to the direction. A neutral sans is a valid text face. Use the core doc's scale and line heights (section 4); body 16 px, headings 1.1-1.25 line height. Avoid reflexive picks: a face chosen because it is popular (Inter, Space Grotesk) or because it looks "not generic" (editorial serif) needs a brand reason on a brand page.

### Step 4: Color

Start neutral: background, surface, border, and text grays tinted toward the brand hue. Add one brand accent for the main action, links, and selection; status colors are separate. A rough 60/30/10 split (neutral, secondary, accent) is a starting point, not a target. Build scales with `references/distinctive-frontend-design-refs/oklch-color-harmony.md`. Check contrast on real pairs: 4.5:1 body text, 3:1 large text and UI boundaries. Build dark mode from its own values (core doc section 5).

### Step 5: Motion and background

- Motion: 2-3 intentional motions per page is a good budget (entrance, scroll, interaction). Use 150-250 ms ease-out for UI, up to 600 ms for a one-time hero entrance. Respect `prefers-reduced-motion`. Patterns: `references/distinctive-frontend-design-refs/animation-patterns.md`.
- Background: a solid surface is a valid default. Add at most one effect (gradient, pattern, texture) from `references/distinctive-frontend-design-refs/background-techniques.md` when it supports the brand and keeps text contrast.
- Hero: one composition, the product name at hero scale, one primary action. Full-bleed by default.

### Step 6: Build and check

1. Emit the design stamp comment, CSS custom properties, and base styles (`references/distinctive-frontend-design-refs/implementation-examples.md`).
2. Run the advisory check: `python3 ${CLAUDE_SKILL_DIR}/scripts-distinctive-frontend-design/validate_design.py --fonts "Display,Body" --palette palette.json --project NAME --macrostructure macro:ID --emitted-css generated.html`. Fix warnings that apply; for the rest, state why the default does not fit. Add `--strict` to exit 1 below a score of 80.

### Step 7: Look, then fix

Run the core doc's section 10 loop on the rendered page. This is the final step for every surface, including tools.

---

## HTML-ARTIFACT Mode

Generate single self-contained `.html` files. All CSS in `<style>`, all JS in
`<script>`. No CDN links, no frameworks, no external deps. Max 500KB.

### Phase 0: Check Saved Template

Run: `python3 ${CLAUDE_SKILL_DIR}/scripts-html-artifact/fill-template.py --list`

If a saved template matches, clone it and fill slots only. Skip to Phase 4 VALIDATE. Do not restyle the template.

### Phase 1: Detect Shape

Run: `python3 ${CLAUDE_SKILL_DIR}/scripts-html-artifact/detect-shape.py --request "{request}"`

| Shape | Signals | Output |
|-------|---------|--------|
| spec | plan, compare, brainstorm | Side-by-side grids, pro/con, SVG diagrams |
| code-review | review PR, explain diff | Diff rendering, severity colors, annotations |
| prototype | prototype, tune, try options | Sliders, CSS var live update, sandbox |
| report | report, summarize, status | TL;DR box, collapsibles, timeline, metrics |
| editor | reorder, triage, edit config | Drag-drop, kanban, toggles, export |
| data-viz | visualize, chart, dashboard | SVG charts, canvas, tooltips, filters |
| diagram | diagram, flowchart, architecture | Inline SVG, annotated flowcharts |
| deck | slides, presentation, pitch | Arrow-key nav, 16:9, progress bar |

Low confidence falls back to report. Hybrid shapes: primary controls layout, secondary provides embedded components.

### Phase 2: Assemble + Load Context

Run: `python3 ${CLAUDE_SKILL_DIR}/scripts-html-artifact/assemble-template.py --shape {shape} --title "{title}" --components {components}`

Load `references/html-artifact-refs/design-system.md`. For diagram shapes, also load `references/html-artifact-refs/shape-diagram-illustration.md` and `references/html-artifact-refs/diagram-layering.md`. Per-shape must-include rules live in `agents/html-builder.md`.

### Phase 3: Generate

Dispatch html-builder agent (see `agents/html-builder.md`) with pre-assembled template. Vanilla JS only. Semantic HTML. SVG inline.

### Phase 4: Validate, then look

1. Run: `python3 ${CLAUDE_SKILL_DIR}/scripts-html-artifact/validate-artifact.py {html_file}`. Errors (structure, `<title>`, external deps, empty body) must be fixed; re-run up to 3 times. CSS slop findings are warnings: fix them or state why they fit this artifact.
2. Run the core doc's section 10 loop on the rendered file. This is the final check before delivery.

### Phase 5: Deliver

Print absolute file path, 1-line summary, offer browser open. Check `$DISPLAY`/`$SSH_TTY` before offering open on Linux.

### Phase 6-7: Export (optional)

PDF: `python3 ${CLAUDE_SKILL_DIR}/scripts-html-artifact/to-pdf.py --input <html> --output <pdf> --json`. PPTX (deck shape only): `python3 ${CLAUDE_SKILL_DIR}/scripts-html-artifact/pptx-bridge/run-unified.py --input <html> --format pptx --out <pptx> --no-render`.

---

## THREEJS Mode

Build Three.js web applications in four phases: Design, Build, Animate, Polish.
Three paradigms detected from context.

### Phase 1: Design

Detect paradigm first:

| Signal | Paradigm | Load |
|--------|----------|------|
| `@react-three/fiber`, r3f, drei, `useFrame` | React Three Fiber | `references/threejs-builder-refs/react-three-fiber.md` |
| `WebGPURenderer`, TSL, compute shader | WebGPU | `references/threejs-builder-refs/webgpu.md` |
| Standalone HTML, `new THREE.Scene()`, vanilla | Imperative | `references/threejs-builder-refs/advanced-topics.md` |
| EventBus, GameState, player controller | Game (alongside paradigm) | `references/threejs-builder-refs/game-architecture.md` + `game-patterns.md` |
| GLTF/GLB, `.glb`, skeletal rigs | GLTF (alongside paradigm) | `references/threejs-builder-refs/gltf-loading.md` |

If ambiguous, ask -- imperative and R3F patterns conflict. Identify core visual element, select components per `references/threejs-builder-refs/build-recipes.md`, document visual style.

### Phase 2: Build

Follow paradigm-specific patterns from loaded reference. Imperative defaults: single HTML, CONFIG object, three-point lighting, `renderer.setAnimationLoop()`. See `references/threejs-builder-refs/build-recipes.md` for boilerplate, scene infrastructure, constraints.

### Phase 3: Animate

R3F uses `useFrame` (never `requestAnimationFrame`). Imperative uses `setAnimationLoop`. No geometry/material allocation in animation loop. Wire interaction handlers per scene plan.

### Phase 4: Polish

Remove debug helpers. Handle window resize. Verify visible lighting. Run the verification steps in `references/threejs-builder-refs/build-recipes.md`, then finish with the core doc's section 10 loop on the rendered scene and any UI overlay.

---

## Deep References

Load on demand when the task needs detailed patterns, examples, or specifications:

### Design Refs

| File | Content |
|------|---------|
| `references/design-refs/ux-copy.md` | Component-specific UX copy patterns |
| `references/design-refs/design-systems.md` | Design token architecture, component specs |
| `references/design-refs/design-critique.md` | Structured critique method, heuristics |
| `references/design-refs/accessibility-review.md` | WCAG criteria, component a11y patterns |
| `references/design-refs/design-handoff.md` | Spec categories, artifact templates |
| `references/design-refs/llm-design-failure-modes.md` | LLM design failure modes with defenses |

### Distinctive Frontend Design Refs

| File | Content |
|------|---------|
| `references/distinctive-frontend-design-refs/font-catalog.json` | Curated fonts by aesthetic category |
| `references/distinctive-frontend-design-refs/color-inspirations.json` | Cultural/contextual palette sources |
| `references/distinctive-frontend-design-refs/animation-patterns.md` | Animation choreography with CSS/React |
| `references/distinctive-frontend-design-refs/background-techniques.md` | Atmospheric background methods |
| `references/distinctive-frontend-design-refs/implementation-examples.md` | CSS tokens, framework templates |
| `references/distinctive-frontend-design-refs/macrostructure-catalog.md` | Named macro:* page structures |
| `references/distinctive-frontend-design-refs/phase-details.md` | Direction examples, motion timing, hero, backgrounds, design stamp |
| `references/distinctive-frontend-design-refs/css-audit-patterns.md` | Grep commands to audit existing CSS |
| `references/distinctive-frontend-design-refs/performance-budgets.md` | Render costs, layout thrashing |
| `references/distinctive-frontend-design-refs/game-ui-polish.md` | Game-native UI polish rules |
| `references/distinctive-frontend-design-refs/card-shader-patterns.md` | Fragment shader GLSL |
| `references/distinctive-frontend-design-refs/shader-integration-react.md` | React 19 WebGL hook + context pool |
| `references/distinctive-frontend-design-refs/balatro-shader-breakdown.md` | Holographic foil shader |
| `references/distinctive-frontend-design-refs/roll-text.md` | Roll/slot text patterns |
| `references/distinctive-frontend-design-refs/text-animation-patterns.md` | Reveal, typewriter, crossfade |
| `references/distinctive-frontend-design-refs/oklch-color-harmony.md` | OKLCH color harmony |
| `references/distinctive-frontend-design-refs/honest-placeholders.md` | Placeholder content rules |

### HTML Artifact Refs

| File | Content |
|------|---------|
| `references/html-artifact-refs/design-system.md` | Theme tokens, a11y checklist, SVG rules |
| `references/html-artifact-refs/diagram-layering.md` | SVG layer order, dark-theme colors |
| `references/html-artifact-refs/infographic-layouts.md` | 21 layout types, 22 visual styles |
| `references/html-artifact-refs/pdf-export.md` | Page-size table, troubleshooting |
| `references/html-artifact-refs/pptx-export.md` | Layout types, THEME dict, CLI ref |
| `references/html-artifact-refs/shape-diagram-illustration.md` | SVG construction, diagram types |

### Three.js Refs

| File | Content |
|------|---------|
| `references/threejs-builder-refs/build-recipes.md` | Boilerplate, scene setup, error handling |
| `references/threejs-builder-refs/react-three-fiber.md` | R3F patterns, Drei, Zustand |
| `references/threejs-builder-refs/webgpu.md` | WebGPURenderer, TSL, compute shaders |
| `references/threejs-builder-refs/advanced-topics.md` | GLTF, post-processing, shaders, physics |
| `references/threejs-builder-refs/visual-polish.md` | Materials, lighting, HDR, shadows |
| `references/threejs-builder-refs/gltf-loading.md` | Coordinate contract, caching, auto-center |
| `references/threejs-builder-refs/game-patterns.md` | Animation FSM, camera movement, input |
| `references/threejs-builder-refs/game-architecture.md` | EventBus, GameState, pre-ship checklist |
| `references/threejs-builder-refs/shader-patterns.md` | ShaderMaterial, vertex displacement, effects |
| `references/threejs-builder-refs/performance-patterns.md` | InstancedMesh, batching, LOD, dispose |
| `references/threejs-builder-refs/advanced-animation.md` | AnimationMixer, IK, spring physics, GSAP |

## Scripts

- Distinctive design: `scripts-distinctive-frontend-design/validate_design.py`, `scripts-distinctive-frontend-design/css_slop_rules.py`
- HTML artifact: `scripts-html-artifact/detect-shape.py`, `scripts-html-artifact/assemble-template.py`, `scripts-html-artifact/validate-artifact.py`, `scripts-html-artifact/fill-template.py`, `scripts-html-artifact/to-pdf.py`, `scripts-html-artifact/pptx-bridge/`
- HTML artifact templates: `templates/`, agents: `agents/html-builder.md`
