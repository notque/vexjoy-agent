# Shape: Diagram & Illustration

> **Shape**: diagram | **Signal words**: architecture, flowchart, sequence, data-flow, figure sheet
> CSS layout classes: `templates/shapes/diagram.css` (injected by assemble-template.py)

---

## Core Principle

Diagrams are STRUCTURAL. Communicate relationships through spatial positioning, connection lines, and labeled nodes. Interactive features (click-to-expand, hover-to-highlight) reveal detail without cluttering the primary view.

---

## Layout Patterns

| Layout | Use When | Structure |
|---|---|---|
| Single diagram + legend | One flowchart or architecture diagram | Full-width SVG, legend below |
| Figure sheet | Multiple illustrations for a blog post | 2-3 column grid of labeled SVG panels |
| Sequence diagram | Message passing between actors | Full-width SVG with lifelines, vertical flow |
| Annotated diagram + callout panel | Complex system with numbered callouts | Diagram left (70%), callout list right (30%) |
| Stacked diagrams | Before/after or layer views | Vertical stack with section headings |

---

## SVG Construction Rules

| Element | Pattern | Notes |
|---|---|---|
| viewBox | `0 0 720 320` (standard) or `720 480` (tall) | Fixed coordinates; CSS scales to container |
| Rendering | Flat, no gradients | Clean, technical aesthetic |
| Stroke | `1.5` for boxes, `2` for emphasis | Consistent weight |
| Corner radius | `rx="10"` | Matches `--radius-md` |
| Labels | `font-size="11"`, `font-family="var(--font-mono)"` | Monospace for technical |
| Node fill | `color-mix(in srgb, <color> 10%, var(--bg-page))` | Tinted background |
| Node stroke | Full semantic color | `var(--color-info)`, `var(--color-primary)`, etc. |
| Sync arrow | Solid line + `marker-end` | Gray stroke |
| Async arrow | Dashed `stroke-dasharray="6 4"` | Info/blue stroke |
| Grouping box | Dashed stroke `<rect>`, low-opacity fill | Groups related nodes |
| Accessibility | `role="img"` + `aria-label` on every `<svg>` | Required |

**Arrowhead markers:** Define in `<defs>` block. Standard (gray), accent (primary), async (info).

---

## Key CSS Classes (from templates/shapes/diagram.css)

| Class | Purpose |
|---|---|
| `.diagram-container` | Bordered surface with horizontal scroll fallback |
| `.diagram-legend` | Flex-wrap legend below diagram |
| `.figure-grid` | Auto-fit grid for figure sheets |
| `.figure-panel` | Bordered card with SVG + figcaption + copy button |
| `.copy-svg-btn` | Appears on hover, copies SVG markup |
| `.diagram-node` | Clickable SVG group with hover/focus states |
| `.node-detail-panel` | Detail panel for clicked nodes |
| `.callout-dot` | Numbered SVG circles for annotated diagrams |

---

## Interaction Patterns

- **Click-to-expand:** Clicking a node shows detail below the diagram (`aria-live="polite"`)
- **Hover-to-highlight:** Dim unrelated elements, highlight connected paths
- **Copy SVG:** Button copies serialized SVG for reuse in other documents
- **Callout panel:** Click numbered dots to highlight matching callout entry

---

## Diagram Type Templates

| Type | Key Elements |
|---|---|
| Flowchart | Horizontal nodes + arrows, labeled edges |
| Architecture | Layer groups (dashed boxes), nodes within layers, cross-layer arrows |
| Sequence | Actor headers, dashed lifelines, activation bars, solid/dashed messages |
| Data flow | Nodes with port labels, directional arrows, async (dashed) for queues |

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| External image references in SVG | All content inline -- no `<image href>` |
| No legend | Always include legend mapping colors to categories |
| Nodes without text labels | Every node needs a text label, not just color |
| SVG not responsive | Use `viewBox` + CSS `width: 100%` + `min-width` for horizontal scroll |
| Missing keyboard support for clickable nodes | Add `tabindex="0"` + `role="button"` + Enter/Space handler |
| Hover-only interactions | Provide click alternative; hover is not available on touch |

---

## Accessibility

- Every `<svg>` has `role="img"` and descriptive `aria-label`
- Interactive nodes: `tabindex="0"`, `role="button"`, `aria-label`
- Enter/Space activates focused nodes
- Color not sole indicator: all nodes have text labels
- Legend always present
- `prefers-reduced-motion` disables SVG transitions
- Detail panel uses `aria-live="polite"` for dynamic updates
