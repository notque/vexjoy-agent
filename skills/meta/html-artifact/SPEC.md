# html-artifact Specification

## Purpose

Generate rich self-contained HTML artifacts instead of markdown when output benefits from visual structure, interactivity, or information density.

## Scope

**IN:**
- Single self-contained `.html` files for 6 shapes: spec, code-review, prototype, report, editor, data-viz
- Auto-detection of artifact shape from user request
- Birchline design system with 4 theme presets
- Interactive elements: tabs, collapsibles, drag-drop, sliders, copy buttons
- SVG diagrams and charts (inline, no external deps)

**OUT:**
- Multi-page sites, framework apps, deployment artifacts
- Anything requiring npm, build steps, or external dependencies
- Presentation decks (use `distinctive-frontend-design` skill)
- Application UIs with backend integration

## Non-Goals

- Not a web app builder — no npm, no build steps, no server-side logic
- For scroll-triggered animations, use the `scrollytelling-patterns.md` reference instead of full Vite+React projects
- Not a replacement for `distinctive-frontend-design` (presentation decks)
- Not forced — user opts out with "as markdown" or "in markdown"
- Not a charting library — SVG generation is inline, not a reusable API

## Invariants

1. Every artifact is a SINGLE `.html` file with no external dependencies
2. All CSS inline in `<style>`, all JS inline in `<script>`
3. `detect-shape.py` classification is deterministic (same input produces same shape)
4. `validate-artifact.py` checks run before delivery
5. Editor and prototype shapes MUST include export/copy buttons
6. All artifacts use Birchline design tokens (not hardcoded values)
7. File size under 500KB
8. Semantic HTML structure with accessibility support

## Pipeline

```
Phase 1: DETECT SHAPE    → scripts/detect-shape.py (deterministic)
Phase 2: LOAD CONTEXT    → design-system.md + interaction-patterns.md + shape-*.md
Phase 3: GENERATE        → agents/html-builder.md subagent
Phase 4: VALIDATE        → scripts/validate-artifact.py (deterministic)
Phase 5: DELIVER         → file path + browser open offer
```

## Dependencies

| Dependency | Required | Purpose |
|---|---|---|
| Python 3.10+ | Yes | Shape detection, artifact validation |
| External Python packages | No | Scripts use stdlib only |
| Node.js / npm | No | Not used |
| `xdg-open` / `open` | Optional | Browser preview |

## Success Criteria

| Criterion | Measurement |
|---|---|
| Renders correctly | Chrome, Firefox, Safari — no console errors |
| Self-contained | No network requests on load (validate-artifact.py check) |
| Interactive | All controls respond to user input without external deps |
| File size | < 500KB (validate-artifact.py check) |
| Validation | `validate-artifact.py` exits 0 |
| Shareable | User can email/share the `.html` file directly — no build required |
| Accessible | Keyboard navigation works; ARIA labels present; reduced-motion respected |
| Responsive | Works at 375px (mobile) and 1440px (desktop) |

## Router Integration

| Mechanism | Details |
|---|---|
| Auto-detect | `/do` Phase 3 ENHANCE injects when output benefits from HTML |
| Explicit | User types `/html [description]` |
| Opt-out | User says "as markdown" or "in markdown" |
| Shape override | `/html --shape=<name> <description>` |

## File Layout

```
skills/meta/html-artifact/
├── SKILL.md                              # Orchestrator (5-phase pipeline)
├── SPEC.md                               # This file
├── EVAL.md                               # Evaluation cases
├── agents/
│   └── html-builder.md                   # Subagent: generates the HTML
├── references/
│   ├── design-system.md                  # Birchline CSS tokens, themes
│   ├── interaction-patterns.md           # Shared JS patterns
│   ├── shape-spec-exploration.md         # Spec shape patterns
│   ├── shape-code-review.md              # Code review shape patterns
│   ├── shape-design-prototype.md         # Prototype shape patterns
│   ├── shape-report-research.md          # Report shape patterns
│   ├── shape-custom-editor.md            # Editor shape patterns
│   └── shape-data-visualization.md       # Data viz shape patterns
├── scripts/
│   ├── detect-shape.py                   # Deterministic shape classifier
│   └── validate-artifact.py              # Post-generation validator
└── assets/                               # (reserved for templates)
```
