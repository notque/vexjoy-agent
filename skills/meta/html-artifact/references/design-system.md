# HTML Artifact Design System

Design principles, theme selection, and quality rules for html-builder. CSS implementations are in `templates/themes/` — injected by `assemble-template.py`.

---

## Theme Selection

**Default: Dark Focus** for all shapes unless user requests light.

| Shape | Default Theme | Rationale |
|---|---|---|
| spec | Dark Focus | High contrast grids, premium feel |
| report | Dark Focus | Professional, scannable |
| code-review | Dark Focus | Developer-familiar, high-contrast diffs |
| data-viz | Dark Focus | Charts pop on dark backgrounds |
| prototype | Dark Focus | Clean dark surface, prominent controls |
| editor | Dark Focus | Clear affordances on dark canvas |
| diagram | Dark Focus | SVG elements pop, technical aesthetic |
| deck | Dark Focus | Slide contrast, presentation-ready |

**Light fallbacks:** Birchline for reports/specs, Interactive Warm for prototypes/editors, Minimal Document for long-form.

**Dark mode toggle:** Every artifact includes light/dark toggle (top-right). Request `theme-toggle` component via `assemble-template.py --components theme-toggle`.

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

## Anti-Patterns

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
