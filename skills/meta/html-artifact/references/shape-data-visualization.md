# Shape: Data Visualization

> **Shape**: data-viz | **Signal words**: visualize, chart, dashboard, show data, trends
> CSS layout classes: `templates/shapes/data-viz.css` (injected by assemble-template.py)

---

## Core Principle

Use INLINE SVG -- not canvas, not charting libraries. Self-contained, crisp at any size, accessible via `<title>` elements. Canvas only for >1000 data points updating live.

---

## Chart Types

| Chart | Use When | SVG Approach |
|---|---|---|
| Bar chart | Compare values across categories | `<rect>` elements with computed y/height |
| Grouped bar | Compare two series per category | Two `<rect>` per group, offset by half-width |
| Stacked bar | Show part-of-whole per category | Stacked `<rect>` elements |
| Line chart | Show change over time | `<polyline>` + optional area `<polygon>` + `<circle>` data points |
| Multi-line | Compare trends across series | Multiple `<polyline>` with different colors/dash patterns |
| Donut/pie | Show part-of-whole | `stroke-dasharray` + `stroke-dashoffset` on `<circle>` (r=80, circumference ~503) |
| Comparison table | Ranked data with visual bars | HTML `<table>` with inline bar-fill divs |

---

## Coordinate System

Standard viewBox: `0 0 600 300`. Margins: top=20, right=20, bottom=40, left=50. Plot area: x=[50, 580], y=[20, 260]. Y-axis runs top-down (SVG convention).

---

## Key CSS Classes (from templates/shapes/data-viz.css)

| Class | Purpose |
|---|---|
| `.chart` | Full-width SVG container |
| `.axis`, `.grid` | Axis lines and dashed grid lines |
| `.axis-label`, `.chart-title` | Text labels in SVG |
| `.data-point`, `.bar` | Interactive chart elements with hover states |
| `.chart-tooltip` | Positioned tooltip div for hover details |
| `.metric-row`, `.metric-card` | KPI callout cards above charts |
| `.legend`, `.legend-swatch` | Color key for chart series |
| `.dash-header`, `.dash-charts` | Dashboard layout structure |
| `.chart-card` | Bordered container for individual charts |

---

## Color Scales

| Scale | Use For | Implementation |
|---|---|---|
| Sequential | Ordered data (intensity, frequency) | `color-mix(in srgb, var(--accent) N%, transparent)` at 15/30/50/70/90% |
| Categorical | Unordered categories | `--accent`, `--color-info`, `--color-success`, `--color-warning` |
| Diverging | Data with meaningful midpoint | `--color-danger` (negative), `--text-muted` (neutral), `--color-success` (positive) |

---

## Dashboard Layout

Header (title + time filter) -> Metric cards (4-col grid) -> Charts (2fr + 1fr grid) -> Detail table.

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Canvas for static charts | Use inline SVG |
| Chart.js / D3 CDN import | Build SVG with vanilla JS or static markup |
| Colors without meaning | Use categorical or sequential color scales from tokens |
| Missing `<title>` on data elements | Every bar, point, and segment needs a `<title>` |
| Charts without labels | Always include axis labels, legend, and chart title |
| Fixed-width charts | Use `viewBox` + `width: 100%` for responsiveness |
| Tooltips via `title` attribute only | Use the JS tooltip pattern with positioned div |
| Animation without reduced-motion | Guard behind `prefers-reduced-motion` |
| Color alone to convey meaning | Supplement with labels, patterns, or shapes |
