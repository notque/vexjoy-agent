# Shape: Data Visualization

> **Shape**: data-viz | **Signal words**: visualize, chart, dashboard, show data, trends, distribution
> CSS layout classes: `templates/shapes/data-viz.css` (injected by assemble-template.py)
> Components: `filter`, `theme-toggle`

Data-viz artifacts make patterns visible. Self-contained inline SVG, not canvas, not charting libraries — every chart must work offline, scale crisply, and announce itself to assistive tech.

---

## Core Principle

**Inline SVG by default.** Canvas only when justified by scale (>1000 data points updating live). Charting libraries (Chart.js, D3, Recharts) are forbidden — they require CDN imports and break the self-contained contract. Build charts with `<rect>`, `<polyline>`, `<circle>`, `<path>` and a small loop in vanilla JS.

---

## Layout Description

A dashboard reads top to bottom: header (title + filters) → KPI metric row → primary chart(s) → detail / drill-down section. The eye lands on metrics first (the answer), then the chart (the why), then the table (the proof).

Single-chart artifacts skip the dashboard chrome: just a chart card with title, the SVG, and a legend.

---

## Canonical Markup Order (load-bearing rule)

| Order | Region | Purpose |
|---|---|---|
| 1 | `<header class="dash-header">` | Title + time/category filter controls |
| 2 | `.metric-row` | KPI cards (4-up); the headline numbers |
| 3 | `.dash-charts` (2fr / 1fr grid) | Primary chart left, secondary chart or legend right |
| 4 | Detail table or breakdown | Sortable HTML table beneath the charts |
| 5 | `<footer>` | Source, methodology, last-updated timestamp |

Why this order: filters must be reachable before the data they affect. Metrics summarize; charts explain; tables prove. Inverting (chart-first) makes filtering feel laggy because the user adjusts a control then has to scan past the chart to confirm a number changed.

### Skeleton

```html
<body data-shape="data-viz" data-theme="dark-focus">
  <header class="dash-header">
    <h1>API Latency · Last 24h</h1>
    <div class="filters"><!-- range buttons --></div>
  </header>
  <main>
    <section class="metric-row" aria-label="Key metrics">
      <!-- .metric-card * 4 -->
    </section>
    <section class="dash-charts">
      <article class="chart-card"><!-- primary --></article>
      <article class="chart-card"><!-- secondary or legend --></article>
    </section>
    <section><!-- detail table --></section>
  </main>
</body>
```

CSS lives in `templates/shapes/data-viz.css` — do not redefine `.chart`, `.bar`, `.data-point`, `.legend-*`, `.dash-*` inline.

---

## SVG Coordinate System (canonical)

Every chart uses the same viewBox and margins so charts compose visually:

| Property | Value | Rationale |
|---|---|---|
| `viewBox` | `0 0 600 300` (wide), `0 0 400 400` (square donut) | Predictable aspect, scales via CSS `width: 100%` |
| Top margin | 20 | Room for chart title text |
| Right margin | 20 | Breathing room |
| Bottom margin | 40 | Room for x-axis labels |
| Left margin | 50 | Room for y-axis labels |
| Plot area | x ∈ [50, 580], y ∈ [20, 260] | Stable working region |
| Y direction | Top-down (SVG native): y=20 is max, y=260 is zero | Avoid manual flips |

Always: `width="100%"` + `viewBox` for responsiveness. Never: fixed `width="600"` without viewBox.

---

## Chart Types (worked examples)

### Bar chart

```html
<svg class="chart" viewBox="0 0 600 300" role="img" aria-label="Daily request volume, bar chart">
  <text x="50" y="14" class="chart-title">Requests per day</text>
  <line class="axis" x1="50" y1="20"  x2="50"  y2="260"/>
  <line class="axis" x1="50" y1="260" x2="580" y2="260"/>
  <line class="grid" x1="50" y1="140" x2="580" y2="140"/>
  <text class="axis-label" x="45" y="144" text-anchor="end">50</text>

  <rect class="bar" x="80"  y="100" width="40" height="160" rx="3" fill="var(--accent)">
    <title>Mon: 67</title>
  </rect>
  <rect class="bar" x="160" y="60"  width="40" height="200" rx="3" fill="var(--accent)">
    <title>Tue: 83</title>
  </rect>
  <!-- repeat per category -->
  <text class="axis-label" x="100" y="278" text-anchor="middle">Mon</text>
  <text class="axis-label" x="180" y="278" text-anchor="middle">Tue</text>
</svg>
```

Use for: comparing values across discrete categories. Each `<rect>` needs a `<title>` child — that becomes the hover/touch tooltip and is announced to AT.

### Line chart

```html
<svg class="chart" viewBox="0 0 600 300" role="img" aria-label="p99 latency over time">
  <text x="50" y="14" class="chart-title">p99 latency · 24h</text>
  <line class="axis" x1="50" y1="20"  x2="50"  y2="260"/>
  <line class="axis" x1="50" y1="260" x2="580" y2="260"/>

  <polyline fill="none" stroke="var(--accent)" stroke-width="2"
            points="60,180 130,160 200,140 270,90 340,110 410,80 480,60 550,50"/>
  <circle class="data-point" cx="60"  cy="180" r="4" fill="var(--accent)"><title>00:00 — 240ms</title></circle>
  <circle class="data-point" cx="550" cy="50"  r="4" fill="var(--accent)"><title>23:00 — 430ms</title></circle>
</svg>
```

Use for: change over time. Add an area fill (`<polygon>` mirroring the polyline) when emphasizing magnitude rather than trend. Each data point needs a `<title>`.

### Donut / pie

```html
<svg viewBox="0 0 200 200" role="img" aria-label="Traffic by region">
  <circle cx="100" cy="100" r="80" fill="none" stroke="var(--bg-muted)" stroke-width="36"/>
  <!-- Each segment: stroke-dasharray = "<segment-len> <remainder>", rotate to start position -->
  <circle cx="100" cy="100" r="80" fill="none"
          stroke="var(--accent)" stroke-width="36"
          stroke-dasharray="251 503" transform="rotate(-90 100 100)">
    <title>US-East — 50%</title>
  </circle>
  <circle cx="100" cy="100" r="80" fill="none"
          stroke="var(--color-info)" stroke-width="36"
          stroke-dasharray="151 503" stroke-dashoffset="-251" transform="rotate(-90 100 100)">
    <title>EU-West — 30%</title>
  </circle>
</svg>
```

Use for: part-of-whole, max 5 segments. Circumference at r=80 is ~503; segment length = `(percent/100) * 503`.

### KPI metric card row

```html
<section class="metric-row">
  <div class="metric-card">
    <span class="metric-label">p99 latency</span>
    <span class="metric-value">180ms</span>
    <span class="metric-delta positive">↓ 92% vs yesterday</span>
  </div>
  <div class="metric-card">
    <span class="metric-label">Requests / sec</span>
    <span class="metric-value">12.4k</span>
    <span class="metric-delta neutral">— flat</span>
  </div>
</section>
```

Use for: dashboard headline. The metric row IS the answer; charts below are evidence.

---

## Color Scales

| Scale | Use For | Token Pattern |
|---|---|---|
| Sequential | Ordered data (intensity, frequency, time) | `color-mix(in srgb, var(--accent) N%, transparent)` at 15 / 30 / 50 / 70 / 90% |
| Categorical | Unordered categories (regions, products) | `var(--accent)`, `var(--color-info)`, `var(--color-success)`, `var(--color-warning)` — max 5 |
| Diverging | Data with a meaningful midpoint (positive/negative) | `var(--color-danger)` (negative) → `var(--text-muted)` (zero) → `var(--color-success)` (positive) |

Color is supplementary. Always pair with text label, pattern, or position.

---

## ARIA / Accessibility

| Element | Required attributes | Why |
|---|---|---|
| `<svg>` chart root | `role="img"`, `aria-label="<concise description>"` | Whole chart announces as a single image |
| `<rect>` / `<circle>` data marks | `<title>` child element with "<label>: <value>" | Hover tooltip + AT announcement |
| Axis | `<text class="axis-label">` with real numbers, not images | Readable, scalable, AT-accessible |
| Legend | `.legend` row of `.legend-item`; each item has swatch + text label | Color decoded by text, not just hue |
| Tooltips | Real `<div class="chart-tooltip">` positioned absolutely | Native `title` attribute is too slow; positioned tooltip is part of `data-viz.css` |
| Filter buttons | `<button aria-pressed="true|false">` | Toggle state announced |
| Reduced motion | Disable `transition` on `.bar`, `.data-point` under `prefers-reduced-motion: reduce` | Already in template; respect it |
| Color-only encoding | Pair every color with text or pattern | Color-blind users need redundancy |

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Using `<canvas>` for static / small charts | Use inline SVG; canvas only when >1000 live data points |
| Importing Chart.js / D3 / Recharts via CDN | Vanilla JS + SVG primitives; the build constraint is non-negotiable |
| Bars/points without `<title>` | Every data mark needs `<title>` for hover and AT |
| Fixed-width SVG (`width="600"` no viewBox) | Use `viewBox` + CSS `width: 100%` |
| Tooltip via `title=` attribute on outer SVG only | Use the `.chart-tooltip` div positioned by JS, OR per-mark `<title>` |
| Color is the only category indicator | Pair color with legend text, pattern, or label-on-mark |
| Donut with 8+ slices | Bin into "Other"; max 5 distinct segments |
| Y-axis without a zero baseline on a bar chart | Bar charts must include zero; truncated baselines lie about magnitude |
| Animation without `prefers-reduced-motion` guard | Disable transitions when reduced-motion is set |
| Inline `<style>` redefining `.chart` / `.bar` | Lives in `templates/shapes/data-viz.css` — touching it creates drift |

---

## Shape Selection

Use **data-viz** when the request matches: visualize, chart, dashboard, show data, trends, distribution, KPIs, metrics over time.

Do **not** use data-viz when:

- The user wants explanation around the data (use **report + data-viz** hybrid)
- The user wants to compare design approaches (use **spec**)
- The user wants tunable parameters that drive a chart (use **prototype**)
- The user wants to triage rows of data (use **editor**)
