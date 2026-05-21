# Shape: Spec / Exploration

> **Shape**: spec | **Signal words**: plan, explore, compare, brainstorm, approach, option, tradeoff
> CSS layout classes: `templates/shapes/spec.css` (injected by assemble-template.py)

---

## Layout Description

Spec artifacts present N options side-by-side with structured evaluation. Core element: a responsive comparison grid that scales from 2-5 columns, collapsing to stacked on mobile.

Each approach card contains: numbered header, one-sentence summary, pros/cons split grid, optional code example, metadata badges (complexity, testability, migration effort).

A recommendation section always follows the grid -- makes the artifact actionable.

---

## Composition Guide

| Request Shape | Sections to Include |
|---|---|
| "Compare N approaches" | Header + Comparison Grid + Recommendation |
| "Design directions" | Header + Comparison Grid + Light/Dark Toggle + Recommendation |
| "Implementation plan" | Header + TL;DR + Timeline + Code Snippets + Risk Table + SVG Diagram |
| "Explore tradeoffs" | Header + Comparison Grid (2 approaches) + Recommendation |
| "Architecture options" | Header + Comparison Grid + SVG Diagram + Recommendation |

### Section Ordering

1. Page header with title + subtitle
2. TL;DR block (if implementation plan)
3. SVG diagram (if architecture / data flow)
4. Comparison grid OR timeline
5. Code snippets (if implementation detail needed)
6. Risk table (if plan or migration)
7. Recommendation (always last before footer)
8. Footer with timestamp

---

## Key CSS Classes (from templates/shapes/spec.css)

| Class | Purpose |
|---|---|
| `.comparison-grid` | Auto-fit grid for approach cards |
| `.approach-card` | Outlined card with hover state; `.approach-tag` adds accent border |
| `.approach-number` | Monospace large number (01, 02, 03) |
| `.pros-cons` | 2-column grid for strengths/tradeoffs |
| `.recommendation` | Accent left-border section |
| `.tradeoff-matrix` | Comparison table with colored cells |
| `.badge` | Inline metadata label |

---

## SVG Data-Flow Diagrams

Use within spec artifacts for architecture visualization. Follow the conventions in design-system.md:

- Nodes: `<rect rx="10">` with color-mix tinted fill and semantic-color stroke
- Arrows: solid for sync, dashed for async; use `<marker>` arrowheads
- Legend: always present at bottom mapping line styles to meaning
- Layer colors: Frontend=info, API=primary, Database=success, External=warning

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Grid doesn't collapse on mobile | Use `repeat(auto-fit, minmax(320px, 1fr))` |
| No recommendation section | Always include -- actionable > informational |
| Pros/cons without structure | Use the `.pros-cons` 2-column grid with +/- markers |
| Hardcoded approach count in CSS | Grid auto-fits; works for 2-5 approaches without changes |
| Missing metadata badges | Include at least complexity + one other dimension |
| Color-only cell indicators | Use `.cell-success`, `.cell-warning`, `.cell-danger` (text + color) |

---

## Accessibility Checklist

- [ ] All `<svg>` elements have `role="img"` and `aria-label`
- [ ] Toggle buttons use `aria-pressed` state
- [ ] Focus-visible outlines on all interactive elements
- [ ] Color is never the sole indicator (badges have text labels, risk levels have text + color)
- [ ] `prefers-reduced-motion` disables transitions
- [ ] Table headers use `<th>`
- [ ] Semantic elements: `<article>`, `<section>`, `<header>`, `<footer>`, `<main>`
- [ ] Font sizes use relative units; respect user zoom
