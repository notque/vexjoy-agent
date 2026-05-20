# HTML Artifact Design System

Design principles, theme selection, and quality rules for html-builder. CSS implementations are in `templates/themes/` — injected by `assemble-template.py`.

---

## Theme Selection

**Default themes vary by shape** — see table below.

| Shape | Default Theme | Rationale |
|---|---|---|
| spec | Birchline | Warm professional tone for comparison grids |
| code-review | Dark Focus | Developer-familiar, high-contrast diffs |
| prototype | Interactive Warm | Clean surface, prominent interactive controls |
| report | Birchline | Professional, scannable long-form |
| editor | Interactive Warm | Clear affordances, prominent shadows |
| data-viz | Dark Focus | Charts pop on dark backgrounds |
| diagram | Dark Focus | SVG elements pop, technical aesthetic |
| deck | Dark Focus | Slide contrast, presentation-ready |

**Fallback:** Minimal Document for long-form reading. Override any default with `--theme`.

**Dark mode toggle (ENFORCED):** Every artifact in shapes {deck, spec, code-review, prototype, report, diagram} MUST include a light/dark toggle. The assembler now adds it automatically — `assemble-template.py` injects `theme-toggle` for these shapes by default. Validator rejects HTML missing `[data-theme-toggle]` or `<button class="theme-toggle">`. Override with `--no-theme-toggle` only when genuinely not needed (rare).

**Dark-by-default (ENFORCED):** Every assembled artifact ships with `<html data-theme="dark">` hardcoded on the root element. A pre-paint script in `<head>` reads `localStorage['html-artifact-theme-v2']` and only overrides when a saved value exists. Rationale: artifacts are technical/working documents that read better dark; setting `data-theme` on `<html>` directly (not via end-of-body JS) prevents flash-of-light-content. The storage key suffix is versioned so a future default change can invalidate stale user prefs by bumping `-v2` → `-v3`. Never hardcode `data-theme="light"` in the base template — the assembler enforcement is the source of truth, prose alone is not enough (see retro 2026-05-20).

---

## Theme Files (in templates/themes/)

| Theme | File | Character |
|---|---|---|
| Birchline | `birchline.css` | Warm, earthy, professional. Clay accent (#D97757) |
| Dark Focus | `dark-focus.css` | Dark bg, inner glows, blue accent (#64B5F6) |
| Interactive Warm | `interactive-warm.css` | Clean white, blue accent (#5B8DEF), prominent shadows |
| Minimal Document | `minimal-document.css` | Serif headings, 680px max-width, generous whitespace |

### Contrast Ratios (WCAG AA verified)

| Theme | Text on Bg | Secondary on Bg | Accent on Bg |
|---|---|---|---|
| Dark Focus | 11.5:1 | 5.8:1 | 5.2:1 |
| Interactive Warm | 12.8:1 | 7.0:1 | 4.6:1 (white on accent) |
| Minimal Document | 12.4:1 | 7.5:1 | Muted 3.5:1 (large text only) |
| Birchline | 14.0:1 | 7.2:1 | 5.1:1 |

---

## Token Architecture

All themes share the same semantic alias layer. Components reference aliases, not raw values.

| Layer | Examples | Purpose |
|---|---|---|
| Raw colors | `--color-primary`, `--color-danger` | Theme-specific palette |
| Typography | `--type-body`, `--type-caption` | Font stacks with weight/size/line-height |
| Spacing | `--sp-1` through `--sp-8` | 4px base scale |
| Semantic | `--bg-page`, `--text-primary`, `--accent` | Component-facing aliases |

**Rule:** Components use semantic aliases (`--bg-surface`, `--text-muted`, `--accent`). Never reference raw color values directly.

---

## Card Variants

Six structural treatments. Use semantic aliases so cards adapt to any theme.

| Variant | Class | Use For |
|---|---|---|
| Flat | `.card-flat` | Dense lists, inline content |
| Outlined | `.card-outlined` | Comparison items, content cards |
| Elevated | `.card-elevated` | Draggable items, interactive cards |
| Accent stripe | `.card-accent` | Priority items, callouts |
| Inset | `.card-inset` | Nested content, code blocks |
| Horizontal | `.card-horizontal` | Scannable rows, search results |

---

## Responsive Breakpoints

| Breakpoint | Width | Behavior |
|---|---|---|
| Mobile | < 640px | Single column, stacked |
| Tablet | 640-1024px | 2 columns where applicable |
| Desktop | > 1024px | Full layout, side-by-side panels |

Use `min-width` media queries (mobile-first). Container max-width: 1200px.

---

## SVG Illustration Conventions

| Property | Value |
|---|---|
| Dimensions | 720 x 320px viewBox (standard) |
| Rendering | Flat -- no gradients, no drop shadows |
| Stroke width | 1.5-2px |
| Corner radius | rx="10" |
| Label font | 11px monospace |
| Annotation font | 12px sans-serif |
| Color source | CSS custom properties via embedded `<style>` |
| Self-contained | Embed `<style>` block inside the SVG |
| Accessibility | `role="img"` + `aria-label` on every `<svg>` |

---

## Accessibility Checklist

1. Color contrast: text on background >= 4.5:1 (normal), >= 3:1 (large text)
2. Focus indicators: all interactive elements have `:focus-visible` styles
3. Semantic HTML: headings in order, lists for lists, tables for tabular data
4. Alt text: every `<img>` has `alt`, every `<svg>` has `role="img"` + `aria-label`
5. Reduced motion: global reset handles via `prefers-reduced-motion`
6. Touch targets: interactive elements minimum 44x44px hit area
7. Language: `<html lang="en">` on root element

---

## Common Failure Modes

| Pattern | Do Instead |
|---|---|
| CSS frameworks (Bootstrap, Tailwind CDN) | Use the token system via templates |
| Random colors per artifact | Use theme tokens |
| Hardcoded px values | Use `--sp-N` tokens and `--type-*` scale |
| Dark theme = invert colors | Use Dark Focus preset with tuned contrast |
| `outline: none` without replacement | Add `:focus-visible` with ring |
| `<div onclick>` | Use `<button>` or `<a>` elements |
| Heading level skipping (h1 to h3) | Sequential heading levels |
| Text as images | Real text with CSS styling |
| `color-mix()` without fallback | Provide fallback hex for critical paths |

---

## Print / PDF Export

Every artifact ships print-ready. The assembler injects `templates/print/{shape}-print.css` into the artifact's `<style>` block. PDF generation is `python3 scripts/to-pdf.py --input <file>`.

| Shape | Page size | Strategy |
|---|---|---|
| deck | 13.333in × 7.5in landscape | 1:1 with live viewport (1280×720), no scale |
| report | 8.5in × 11in portrait | Content flows; cards page-break-inside: avoid |
| spec | 11in × 8.5in landscape | Side-by-side grids preserved |
| data-viz | 8.5in × 11in portrait | SVGs vector; controls hidden |
| editor | 8.5in × 11in portrait | Kanban columns stack vertically; sticky export bar un-sticks; banner |
| (other: code-review, prototype, diagram) | 8.5in × 11in portrait | default-print.css with banner |

Dark themes preserved via `print-color-adjust: exact` (all vendor variants). Full details in `references/pdf-export.md`.

### Print CSS rules (lessons learned)

These are graduated from real regressions. Read before editing any `templates/print/*.css`.

| Rule | Why |
|---|---|
| **Never replace `display: flex` with `display: block` in `@media print`.** Override only what print actually needs: page size, page-break, color-adjust, sticky→static. | Replacing flex with block kills `justify-content: center` and flushes title slides to the top-left at ~45% offset. Keep `display: flex; flex-direction: column; justify-content: center`; add `align-items: center` and `max-width: 720px` on children for readable column width. |
| **Don't print three CSS-grid columns + `page-break-inside: avoid` on letter-portrait.** | The constraints fight: Chrome resolves by orphaning column headers from cards. For kanban-style print, `display: block` the grid container so columns stack vertically (this is shape-specific, not a general flex rule — see above). |
| **Sticky elements un-stick in print.** | `.export-bar { position: static; box-shadow: none; }` so a Reset/Copy bar renders as a normal block at document end, not floating over content. |

### Theme tokens + runtime toggle

| Rule | Why |
|---|---|
| **Never declare runtime-switchable theme tokens on `:root`.** | `:root` rules block lower-specificity `[data-theme]` overrides. The toggle becomes visually dead. Declare tokens on `html[data-theme="dark"]` and `html[data-theme="light"]` at matching specificity to the toggle target. |
| **Seed `<html data-theme>` from `<body>` on init.** | The toggle flips `<html>`'s attribute, but pages typically declare initial theme on `<body>`. Without the seed, the first toggle click reads `undefined` → no flip. The toggle JS in `templates/components/theme-toggle.js` does this on `DOMContentLoaded`. |

### Reference-file taxonomy (graduated from a refactor regression)

When splitting or condensing references, sort each chunk into one of three buckets:

| Category | Lives in | Example |
|---|---|---|
| Deterministic code | `templates/` | CSS, JS components, print stylesheets |
| Design principles | `references/` (full prose) | Token architecture, contrast ratios, accessibility |
| Judgment scaffolds | `references/` (full prose) **AND** mirrored as one-liners in `SKILL.md` | Worked examples, markup-ordering rules, ARIA tables |

The mirror to SKILL.md is non-negotiable for load-bearing rules. A prior 86%-cut refactor dropped scaffolds from references and shipped — the next deck regressed (chrome moved from below to above the deck) because the rule lived nowhere SKILL.md could see it. Mirror the rule, then refactors can't silently lose it.
