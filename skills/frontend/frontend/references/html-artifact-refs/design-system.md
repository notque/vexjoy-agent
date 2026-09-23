# HTML Artifact Design System

Theme selection and artifact-specific rules for html-builder. General judgment (hierarchy, spacing, type, color, states, look-then-fix) lives in `skills/shared-patterns/ui-design-judgment.md`; read it first. CSS implementations are in `templates/themes/`, injected by `assemble-template.py`.

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

**Fallback:** Minimal Document for long-form reading. These are defaults: override with `--theme` when the reader or content calls for it (for example, a report read on a projector or printed suits a light theme).

**Dark mode toggle:** Add the `theme-toggle` component (`assemble-template.py --components theme-toggle`) when the artifact will be read in both settings. Dark values come from their own tokens, not inverted light values: slightly lighter surfaces for elevation, less saturated accents, no pure black under pure white text.

---

## Theme Files (in templates/themes/)

| Theme | File | Character |
|---|---|---|
| Birchline | `birchline.css` | Warm, earthy, professional. Clay accent (#D97757) |
| Dark Focus | `dark-focus.css` | Dark bg, inset shadows, blue accent (#64B5F6) |
| Interactive Warm | `interactive-warm.css` | Clean white, blue accent (#3D6FD9), shadowed controls |
| Minimal Document | `minimal-document.css` | Serif headings, 680px max-width, generous whitespace |

### Contrast Ratios (computed from the theme files)

| Theme | Text on Bg | Secondary on Bg | Muted on Bg | Accent note |
|---|---|---|---|---|
| Dark Focus | 12.9:1 | 6.7:1 | 5.2:1 | Accent on bg 7.7:1 |
| Interactive Warm | 13.2:1 | 6.6:1 | 4.9:1 | White on accent 4.7:1 |
| Minimal Document | 12.4:1 | 7.5:1 | 3.5:1 (large text only) | Gray accent |
| Birchline | 17.5:1 | 10.3:1 | 5.2:1 | Clay accent 3.0:1 on ivory: use for fills and large text, not small text |

Recheck any pair you add or change: 4.5:1 body text, 3:1 large text and UI boundaries.

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

Six structural treatments. Pick one container style per artifact and group with spacing inside it; do not nest cards in cards. Use semantic aliases so cards adapt to any theme.

| Variant | Class | Use For |
|---|---|---|
| Flat | `.card-flat` | Dense lists, inline content |
| Outlined | `.card-outlined` | Comparison items, content cards |
| Elevated | `.card-elevated` | Draggable items, interactive cards |
| Accent stripe | `.card-accent` | One priority item or callout; a stripe on every card is a generated-UI tell |
| Inset | `.card-inset` | Nested content, code blocks |
| Horizontal | `.card-horizontal` | Scannable rows, search results |

---

## Responsive Breakpoints

| Breakpoint | Width | Behavior |
|---|---|---|
| Mobile | < 640px | Single column, stacked |
| Tablet | 640-1024px | 2 columns where applicable |
| Desktop | > 1024px | Full layout, side-by-side panels |

Use `min-width` media queries (mobile-first). Container max-width: 1200px; prose 60-75 characters per line. Check the render at 375, 768, and 1280 px.

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
8. States: every data view has empty, loading, and error content; every control has hover, focus-visible, active, and disabled

---

## Patterns to Replace

| Common Mistake | Preferred Approach |
|---|---|
| CSS frameworks (Bootstrap, Tailwind CDN) | Use the token system via templates |
| Random colors per artifact | Use theme tokens |
| Hardcoded px values | Use `--sp-N` tokens and `--type-*` scale |
| Dark theme = invert colors | Use Dark Focus preset, or build dark tokens from their own values |
| Every button styled as primary | One primary action per region; secondary actions as outline or text buttons |
| `outline: none` without replacement | Add `:focus-visible` with ring |
| `<div onclick>` | Use `<button>` or `<a>` elements |
| Heading level skipping (h1 to h3) | Sequential heading levels |
| Text as images | Real text with CSS styling |
| `color-mix()` without fallback | Provide fallback hex for critical paths |
