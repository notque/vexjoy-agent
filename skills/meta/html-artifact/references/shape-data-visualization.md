# Shape: Data Visualization

Loaded when shape = `data-viz`. For artifacts that visualize data: charts, dashboards, trend graphs, distribution plots, comparison tables with visual elements.

**Theme:** Dark Focus (charts pop on dark backgrounds, inner glows, high contrast). Override to Birchline when the viz is embedded in a report context.

---

## Core Principle

Data viz artifacts use INLINE SVG — not canvas, not charting libraries. Self-contained, crisp at any size, accessible via `<title>` elements and ARIA labels. Canvas is permitted ONLY for complex real-time visualizations (>1000 data points updating live).

---

## SVG Chart Foundations

### Coordinate System

All charts use a consistent viewBox and margin convention:

```
viewBox="0 0 600 300"

Margins: top=20, right=20, bottom=40, left=50
Plot area: x=[50, 580], y=[20, 260]
Y-axis runs top-down (SVG convention): y=20 is max value, y=260 is zero
```

### Axis and Grid Template

```html
<svg class="chart" viewBox="0 0 600 300" role="img" aria-label="[Chart description]"
     style="width: 100%; max-width: 600px;">
  <style>
    .axis { stroke: var(--border-default, #3A3A5C); stroke-width: 1; }
    .grid { stroke: var(--border-subtle, #2E2E4E); stroke-width: 1; stroke-dasharray: 4; }
    .axis-label { font: 11px var(--font-mono, monospace); fill: var(--text-muted, #6E6E8A); }
    .chart-title { font: 500 14px var(--font-sans, system-ui); fill: var(--text-primary, #E0E0E0); }
  </style>

  <!-- Chart title -->
  <text x="50" y="14" class="chart-title">Chart Title</text>

  <!-- Y axis -->
  <line x1="50" y1="20" x2="50" y2="260" class="axis"/>
  <!-- X axis -->
  <line x1="50" y1="260" x2="580" y2="260" class="axis"/>

  <!-- Horizontal grid lines (3-4 lines) -->
  <line x1="50" y1="80"  x2="580" y2="80"  class="grid"/>
  <line x1="50" y1="140" x2="580" y2="140" class="grid"/>
  <line x1="50" y1="200" x2="580" y2="200" class="grid"/>

  <!-- Y axis labels -->
  <text x="45" y="84"  text-anchor="end" class="axis-label">75</text>
  <text x="45" y="144" text-anchor="end" class="axis-label">50</text>
  <text x="45" y="204" text-anchor="end" class="axis-label">25</text>
  <text x="45" y="264" text-anchor="end" class="axis-label">0</text>

  <!-- Plot content goes here -->
</svg>
```

---

## Bar Chart

```html
<!-- Inside the axis template above -->

<!-- Bars -->
<rect x="80"  y="100" width="40" height="160" rx="3" fill="var(--accent)" opacity="0.85" class="bar">
  <title>Mon: 67</title>
</rect>
<rect x="160" y="60"  width="40" height="200" rx="3" fill="var(--accent)" opacity="0.85" class="bar">
  <title>Tue: 83</title>
</rect>
<rect x="240" y="140" width="40" height="120" rx="3" fill="var(--accent)" opacity="0.85" class="bar">
  <title>Wed: 50</title>
</rect>
<rect x="320" y="80"  width="40" height="180" rx="3" fill="var(--accent)" opacity="0.85" class="bar">
  <title>Thu: 75</title>
</rect>
<rect x="400" y="180" width="40" height="80"  rx="3" fill="var(--accent)" opacity="0.85" class="bar">
  <title>Fri: 33</title>
</rect>
<rect x="480" y="40"  width="40" height="220" rx="3" fill="var(--accent)" opacity="0.85" class="bar">
  <title>Sat: 92</title>
</rect>

<!-- X axis labels -->
<text x="100" y="278" text-anchor="middle" class="axis-label">Mon</text>
<text x="180" y="278" text-anchor="middle" class="axis-label">Tue</text>
<text x="260" y="278" text-anchor="middle" class="axis-label">Wed</text>
<text x="340" y="278" text-anchor="middle" class="axis-label">Thu</text>
<text x="420" y="278" text-anchor="middle" class="axis-label">Fri</text>
<text x="500" y="278" text-anchor="middle" class="axis-label">Sat</text>
```

### Grouped Bar Variant

For comparing two series side-by-side:

```html
<!-- Two bars per group, offset by half-width -->
<g class="bar-group">
  <rect x="75"  y="120" width="20" height="140" rx="2" fill="var(--accent)" opacity="0.85">
    <title>Q1 Revenue: 58</title>
  </rect>
  <rect x="97"  y="160" width="20" height="100" rx="2" fill="var(--color-info)" opacity="0.85">
    <title>Q1 Expenses: 42</title>
  </rect>
</g>
```

### Stacked Bar Variant

```html
<g class="stacked-bar">
  <rect x="80" y="60"  width="40" height="80"  rx="0" fill="var(--accent)" opacity="0.85">
    <title>Desktop: 33</title>
  </rect>
  <rect x="80" y="140" width="40" height="60"  rx="0" fill="var(--color-info)" opacity="0.85">
    <title>Mobile: 25</title>
  </rect>
  <rect x="80" y="200" width="40" height="60"  rx="0" fill="var(--color-warning)" opacity="0.85">
    <title>Tablet: 25</title>
  </rect>
  <!-- Bottom bar gets rounded bottom corners -->
</g>
```

---

## Line Chart

```html
<!-- Inside the axis template -->

<!-- Area fill (optional, draw first so line sits on top) -->
<polygon points="80,200 160,150 240,180 320,90 400,120 480,60 480,260 80,260"
         fill="var(--accent)" opacity="0.08"/>

<!-- Data line -->
<polyline points="80,200 160,150 240,180 320,90 400,120 480,60"
          fill="none" stroke="var(--accent)" stroke-width="2"
          stroke-linejoin="round" stroke-linecap="round"/>

<!-- Data points -->
<circle cx="80"  cy="200" r="4" fill="var(--accent)" class="data-point">
  <title>Week 1: 25</title>
</circle>
<circle cx="160" cy="150" r="4" fill="var(--accent)" class="data-point">
  <title>Week 2: 46</title>
</circle>
<circle cx="240" cy="180" r="4" fill="var(--accent)" class="data-point">
  <title>Week 3: 33</title>
</circle>
<circle cx="320" cy="90"  r="4" fill="var(--accent)" class="data-point">
  <title>Week 4: 71</title>
</circle>
<circle cx="400" cy="120" r="4" fill="var(--accent)" class="data-point">
  <title>Week 5: 58</title>
</circle>
<circle cx="480" cy="60"  r="4" fill="var(--accent)" class="data-point">
  <title>Week 6: 83</title>
</circle>

<!-- X axis labels -->
<text x="80"  y="278" text-anchor="middle" class="axis-label">W1</text>
<text x="160" y="278" text-anchor="middle" class="axis-label">W2</text>
<text x="240" y="278" text-anchor="middle" class="axis-label">W3</text>
<text x="320" y="278" text-anchor="middle" class="axis-label">W4</text>
<text x="400" y="278" text-anchor="middle" class="axis-label">W5</text>
<text x="480" y="278" text-anchor="middle" class="axis-label">W6</text>
```

### Multi-Line Variant

```html
<!-- Series A -->
<polyline points="80,200 160,150 240,180 320,90 400,120 480,60"
          fill="none" stroke="var(--accent)" stroke-width="2"
          stroke-linejoin="round" stroke-linecap="round"/>
<!-- Series B -->
<polyline points="80,180 160,190 240,140 320,160 400,100 480,110"
          fill="none" stroke="var(--color-info)" stroke-width="2"
          stroke-linejoin="round" stroke-linecap="round"
          stroke-dasharray="6 3"/>
```

---

## Donut / Pie Chart

Uses `stroke-dasharray` and `stroke-dashoffset` on circles. Circumference of r=80 is `2 * π * 80 ≈ 503`.

```html
<svg viewBox="0 0 200 200" role="img" aria-label="Language distribution: TypeScript 40%, Go 30%, Python 20%, Other 10%"
     style="width: 200px;">
  <!-- Background ring -->
  <circle cx="100" cy="100" r="80" fill="none" stroke="var(--border-subtle)" stroke-width="20"/>

  <!-- Segment 1: 40% = 201 of 503 -->
  <circle cx="100" cy="100" r="80" fill="none"
          stroke="var(--accent)" stroke-width="20"
          stroke-dasharray="201 503" stroke-dashoffset="0"
          transform="rotate(-90 100 100)">
    <title>TypeScript: 40%</title>
  </circle>

  <!-- Segment 2: 30% = 151 of 503, offset by -201 -->
  <circle cx="100" cy="100" r="80" fill="none"
          stroke="var(--color-info)" stroke-width="20"
          stroke-dasharray="151 503" stroke-dashoffset="-201"
          transform="rotate(-90 100 100)">
    <title>Go: 30%</title>
  </circle>

  <!-- Segment 3: 20% = 101 of 503, offset by -352 -->
  <circle cx="100" cy="100" r="80" fill="none"
          stroke="var(--color-success)" stroke-width="20"
          stroke-dasharray="101 503" stroke-dashoffset="-352"
          transform="rotate(-90 100 100)">
    <title>Python: 20%</title>
  </circle>

  <!-- Segment 4: 10% = 50 of 503, offset by -453 -->
  <circle cx="100" cy="100" r="80" fill="none"
          stroke="var(--color-warning)" stroke-width="20"
          stroke-dasharray="50 503" stroke-dashoffset="-453"
          transform="rotate(-90 100 100)">
    <title>Other: 10%</title>
  </circle>

  <!-- Center label -->
  <text x="100" y="95"  text-anchor="middle" font-size="24" font-weight="600"
        fill="var(--text-primary)">70%</text>
  <text x="100" y="115" text-anchor="middle" font-size="12"
        fill="var(--text-muted)">Coverage</text>
</svg>
```

### Donut Calculation Helper (JS)

```js
function donutSegments(data, radius) {
  const circumference = 2 * Math.PI * radius;
  const total = data.reduce((sum, d) => sum + d.value, 0);
  let offset = 0;
  return data.map(d => {
    const pct = d.value / total;
    const dashLength = pct * circumference;
    const segment = {
      label: d.label,
      value: d.value,
      percent: Math.round(pct * 100),
      dasharray: `${dashLength.toFixed(1)} ${circumference.toFixed(1)}`,
      dashoffset: (-offset).toFixed(1),
      color: d.color,
    };
    offset += dashLength;
    return segment;
  });
}
```

---

## Interactive Ring Visualization

Nodes positioned around a circle with dynamic arc connections.

### HTML

```html
<svg id="ring-viz" viewBox="0 0 400 400" role="img" aria-label="Relationship ring diagram"
     style="width: 100%; max-width: 400px;">
  <!-- Arcs and nodes rendered by JS -->
</svg>
<div class="ring-controls">
  <button class="btn-primary" onclick="addNode()">+ Add Node</button>
  <button class="btn-secondary" onclick="removeNode()">− Remove</button>
  <span class="ring-count" id="ring-count">0 nodes</span>
</div>
```

### Ring JS

```js
const RING_RADIUS = 150;
const CENTER = 200;
let nodes = [];

function addNode() {
  const id = `node-${Date.now()}`;
  const label = `N${nodes.length + 1}`;
  nodes.push({ id, label, active: true });
  renderRing();
}

function removeNode() {
  if (nodes.length > 0) {
    nodes.pop();
    renderRing();
  }
}

function renderRing() {
  const svg = document.getElementById('ring-viz');
  // Clear previous
  svg.innerHTML = '';

  const count = nodes.length;
  document.getElementById('ring-count').textContent = `${count} node${count !== 1 ? 's' : ''}`;

  if (count === 0) return;

  const angleStep = (2 * Math.PI) / count;

  // Position nodes
  nodes.forEach((node, i) => {
    const angle = angleStep * i - Math.PI / 2; // start from top
    node.x = CENTER + RING_RADIUS * Math.cos(angle);
    node.y = CENTER + RING_RADIUS * Math.sin(angle);
  });

  // Draw arcs between adjacent nodes
  for (let i = 0; i < count; i++) {
    const a = nodes[i];
    const b = nodes[(i + 1) % count];
    const arc = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    arc.setAttribute('x1', a.x);
    arc.setAttribute('y1', a.y);
    arc.setAttribute('x2', b.x);
    arc.setAttribute('y2', b.y);
    arc.setAttribute('stroke', 'var(--border-default)');
    arc.setAttribute('stroke-width', '1.5');
    arc.setAttribute('opacity', '0.5');
    svg.appendChild(arc);
  }

  // Draw node circles
  nodes.forEach(node => {
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.style.cursor = 'pointer';

    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', node.x);
    circle.setAttribute('cy', node.y);
    circle.setAttribute('r', '18');
    circle.setAttribute('fill', node.active ? 'var(--accent)' : 'var(--bg-muted)');
    circle.setAttribute('stroke', 'var(--bg-page)');
    circle.setAttribute('stroke-width', '3');

    const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    title.textContent = node.label;
    circle.appendChild(title);

    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', node.x);
    text.setAttribute('y', node.y + 4);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('font-size', '11');
    text.setAttribute('font-weight', '600');
    text.setAttribute('fill', 'white');
    text.textContent = node.label;

    g.appendChild(circle);
    g.appendChild(text);
    g.addEventListener('click', () => {
      node.active = !node.active;
      renderRing();
    });
    svg.appendChild(g);
  });

  // Key indicator dot for active nodes
  const activeCount = nodes.filter(n => n.active).length;
  const indicator = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  indicator.setAttribute('x', CENTER);
  indicator.setAttribute('y', CENTER + 5);
  indicator.setAttribute('text-anchor', 'middle');
  indicator.setAttribute('font-size', '20');
  indicator.setAttribute('font-weight', '600');
  indicator.setAttribute('fill', 'var(--text-primary)');
  indicator.textContent = `${activeCount}/${count}`;
  svg.appendChild(indicator);
}
```

### Ring CSS

```css
.ring-controls {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  justify-content: center;
  padding: var(--sp-4);
}
.ring-count {
  font: var(--type-caption);
  color: var(--text-muted);
}
```

---

## Interactive Tooltip

Shared tooltip pattern for all chart types. Single tooltip element, repositioned on hover.

### HTML

```html
<div id="chart-tooltip" class="chart-tooltip" role="tooltip" aria-hidden="true"></div>
```

### CSS

```css
.chart-tooltip {
  display: none;
  position: fixed;
  background: var(--bg-surface);
  color: var(--text-primary);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-xs);
  font: var(--type-caption);
  font-weight: 500;
  pointer-events: none;
  z-index: 100;
  box-shadow: var(--shadow-md);
  border: 1px solid var(--border-default);
  white-space: nowrap;
}
```

### JS

```js
function initTooltips() {
  const tooltip = document.getElementById('chart-tooltip');

  document.querySelectorAll('.data-point, .bar').forEach(el => {
    el.style.cursor = 'pointer';

    el.addEventListener('mouseenter', (e) => {
      const titleEl = el.querySelector('title');
      if (!titleEl) return;
      tooltip.textContent = titleEl.textContent;
      tooltip.style.display = 'block';
      tooltip.setAttribute('aria-hidden', 'false');
      positionTooltip(e, tooltip);
    });

    el.addEventListener('mousemove', (e) => {
      positionTooltip(e, tooltip);
    });

    el.addEventListener('mouseleave', () => {
      tooltip.style.display = 'none';
      tooltip.setAttribute('aria-hidden', 'true');
    });
  });
}

function positionTooltip(e, tooltip) {
  const pad = 12;
  let x = e.clientX + pad;
  let y = e.clientY - pad - tooltip.offsetHeight;
  // Keep tooltip on screen
  if (x + tooltip.offsetWidth > window.innerWidth) {
    x = e.clientX - pad - tooltip.offsetWidth;
  }
  if (y < 0) {
    y = e.clientY + pad;
  }
  tooltip.style.left = x + 'px';
  tooltip.style.top = y + 'px';
}

// Initialize on load
document.addEventListener('DOMContentLoaded', initTooltips);
```

---

## Comparison Table with Visual Bars

Tabular data with inline bar indicators for at-a-glance comparison.

### HTML

```html
<table class="data-table" role="table">
  <thead>
    <tr>
      <th scope="col">Feature</th>
      <th scope="col">Score</th>
      <th scope="col" class="hide-mobile">Distribution</th>
      <th scope="col">Status</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Performance</td>
      <td class="mono">85</td>
      <td class="hide-mobile">
        <div class="bar-cell" role="meter" aria-valuenow="85" aria-valuemin="0" aria-valuemax="100" aria-label="Performance: 85%">
          <div class="bar-fill" style="width: 85%; background: var(--color-success);"></div>
        </div>
      </td>
      <td><span class="badge badge-success">Good</span></td>
    </tr>
    <tr>
      <td>Reliability</td>
      <td class="mono">72</td>
      <td class="hide-mobile">
        <div class="bar-cell" role="meter" aria-valuenow="72" aria-valuemin="0" aria-valuemax="100" aria-label="Reliability: 72%">
          <div class="bar-fill" style="width: 72%; background: var(--color-warning);"></div>
        </div>
      </td>
      <td><span class="badge badge-warning">Fair</span></td>
    </tr>
    <tr>
      <td>Security</td>
      <td class="mono">94</td>
      <td class="hide-mobile">
        <div class="bar-cell" role="meter" aria-valuenow="94" aria-valuemin="0" aria-valuemax="100" aria-label="Security: 94%">
          <div class="bar-fill" style="width: 94%; background: var(--color-success);"></div>
        </div>
      </td>
      <td><span class="badge badge-success">Good</span></td>
    </tr>
  </tbody>
</table>
```

### Table CSS

```css
.data-table {
  width: 100%;
  border-collapse: collapse;
  font: var(--type-small);
}
.data-table th {
  text-align: left;
  font: var(--type-caption);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 2px solid var(--border-default);
}
.data-table td {
  padding: var(--sp-3);
  border-bottom: 1px solid var(--border-subtle);
  vertical-align: middle;
}
.data-table tr:hover td {
  background: var(--bg-muted);
}
.data-table .mono {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
}

.bar-cell {
  width: 180px;
  height: 14px;
  background: var(--bg-muted);
  border-radius: 7px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  border-radius: 7px;
  transition: width 0.4s ease;
}
```

---

## Metric Callout Cards

Top-level KPIs rendered as a row of metric cards above charts.

### HTML

```html
<div class="metric-row">
  <div class="metric-card">
    <span class="metric-label">Total Users</span>
    <span class="metric-value">12,847</span>
    <span class="metric-delta positive">↑ 12.3%</span>
  </div>
  <div class="metric-card">
    <span class="metric-label">Avg Response</span>
    <span class="metric-value">142ms</span>
    <span class="metric-delta negative">↑ 8ms</span>
  </div>
  <div class="metric-card">
    <span class="metric-label">Error Rate</span>
    <span class="metric-value">0.3%</span>
    <span class="metric-delta positive">↓ 0.1%</span>
  </div>
  <div class="metric-card">
    <span class="metric-label">Uptime</span>
    <span class="metric-value">99.97%</span>
    <span class="metric-delta neutral">—</span>
  </div>
</div>
```

### Metric CSS

```css
.metric-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--sp-4);
  margin-bottom: var(--sp-5);
}
@media (max-width: 768px) {
  .metric-row { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 480px) {
  .metric-row { grid-template-columns: 1fr; }
}

.metric-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.metric-label {
  font: var(--type-caption);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.metric-value {
  font-family: var(--font-mono);
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.1;
}
.metric-delta {
  font: var(--type-caption);
  font-weight: 600;
}
.metric-delta.positive { color: var(--color-success); }
.metric-delta.negative { color: var(--color-danger); }
.metric-delta.neutral  { color: var(--text-muted); }
```

---

## Dashboard Layout

Assembles metrics, charts, and tables into a single-page dashboard.

### HTML

```html
<header class="dash-header">
  <div>
    <h1>Dashboard Title</h1>
    <p class="dash-subtitle">Last updated: <time id="last-updated"></time></p>
  </div>
  <div class="dash-filters">
    <select id="time-range" onchange="filterData(this.value)" aria-label="Time range">
      <option value="7d">Last 7 days</option>
      <option value="30d">Last 30 days</option>
      <option value="90d">Last 90 days</option>
    </select>
    <button class="btn-secondary" onclick="refreshData()">↻ Refresh</button>
  </div>
</header>

<main class="dashboard">
  <!-- Metric row -->
  <section class="dash-section" aria-label="Key metrics">
    <div class="metric-row">
      <!-- metric cards -->
    </div>
  </section>

  <!-- Charts -->
  <section class="dash-section" aria-label="Charts">
    <div class="dash-charts">
      <div class="chart-card">
        <h2>Trend Over Time</h2>
        <!-- Line chart SVG -->
      </div>
      <div class="chart-card">
        <h2>Distribution</h2>
        <!-- Donut chart SVG -->
      </div>
    </div>
  </section>

  <!-- Detail table -->
  <section class="dash-section" aria-label="Detailed data">
    <h2>Details</h2>
    <!-- Comparison table -->
  </section>
</main>
```

### Dashboard CSS

```css
.dash-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: var(--sp-5);
  border-bottom: 1px solid var(--border-subtle);
  flex-wrap: wrap;
  gap: var(--sp-3);
}
.dash-header h1 {
  font: var(--type-h2);
  color: var(--text-primary);
}
.dash-subtitle {
  font: var(--type-small);
  color: var(--text-muted);
  margin-top: var(--sp-1);
}
.dash-filters {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.dashboard {
  padding: var(--sp-5);
}
.dash-section {
  margin-bottom: var(--sp-6);
}
.dash-section h2 {
  font: var(--type-small);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: var(--sp-3);
}

.dash-charts {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: var(--sp-5);
}
@media (max-width: 768px) {
  .dash-charts { grid-template-columns: 1fr; }
}

.chart-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: var(--sp-4);
}
.chart-card h2 {
  margin-bottom: var(--sp-3);
}
```

---

## Legend Patterns

### Horizontal Legend (below chart)

```html
<div class="legend legend-horizontal">
  <div class="legend-item">
    <span class="legend-swatch" style="background: var(--accent);"></span>
    <span class="legend-label">TypeScript</span>
  </div>
  <div class="legend-item">
    <span class="legend-swatch" style="background: var(--color-info);"></span>
    <span class="legend-label">Go</span>
  </div>
  <div class="legend-item">
    <span class="legend-swatch" style="background: var(--color-success);"></span>
    <span class="legend-label">Python</span>
  </div>
</div>
```

### Vertical Legend (beside donut)

```html
<div class="legend legend-vertical">
  <div class="legend-item">
    <span class="legend-swatch" style="background: var(--accent);"></span>
    <span class="legend-label">TypeScript</span>
    <span class="legend-value">40%</span>
  </div>
  <!-- ... -->
</div>
```

### Legend CSS

```css
.legend {
  display: flex;
  gap: var(--sp-4);
}
.legend-horizontal {
  flex-direction: row;
  flex-wrap: wrap;
  justify-content: center;
  padding: var(--sp-3) 0;
}
.legend-vertical {
  flex-direction: column;
  gap: var(--sp-2);
}
.legend-item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.legend-swatch {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  flex-shrink: 0;
}
.legend-label {
  font: var(--type-caption);
  color: var(--text-secondary);
}
.legend-value {
  font: var(--type-caption);
  font-family: var(--font-mono);
  color: var(--text-muted);
  margin-left: auto;
}
```

---

## Color Scales

### Sequential (single-hue, light-to-dark)

For ordered data (intensity, frequency, temperature).

```css
/* Based on accent color with opacity steps */
.seq-1 { fill: color-mix(in srgb, var(--accent) 15%, transparent); }
.seq-2 { fill: color-mix(in srgb, var(--accent) 30%, transparent); }
.seq-3 { fill: color-mix(in srgb, var(--accent) 50%, transparent); }
.seq-4 { fill: color-mix(in srgb, var(--accent) 70%, transparent); }
.seq-5 { fill: color-mix(in srgb, var(--accent) 90%, transparent); }
```

### Categorical (distinct hues)

For unordered categories. Use the four semantic colors.

```css
.cat-a { fill: var(--accent); }       /* Primary series */
.cat-b { fill: var(--color-info); }    /* Secondary series */
.cat-c { fill: var(--color-success); } /* Tertiary series */
.cat-d { fill: var(--color-warning); } /* Quaternary series */
/* Avoid color-danger for data; reserve for error states */
```

### Diverging (positive/negative)

For data with a meaningful midpoint (profit/loss, above/below average).

```css
.div-negative { fill: var(--color-danger); }
.div-neutral  { fill: var(--text-muted); }
.div-positive { fill: var(--color-success); }
```

---

## Chart Entry Animation

Bars grow up from the x-axis; lines draw in from left. Disabled when `prefers-reduced-motion` is set (handled by the global CSS reset).

### Bar Growth Animation

```css
.bar {
  transform-origin: bottom;
  animation: bar-grow 0.5s ease-out both;
}
@keyframes bar-grow {
  from { transform: scaleY(0); }
  to   { transform: scaleY(1); }
}

/* Stagger each bar */
.bar:nth-child(1)  { animation-delay: 0.0s; }
.bar:nth-child(2)  { animation-delay: 0.05s; }
.bar:nth-child(3)  { animation-delay: 0.1s; }
.bar:nth-child(4)  { animation-delay: 0.15s; }
.bar:nth-child(5)  { animation-delay: 0.2s; }
.bar:nth-child(6)  { animation-delay: 0.25s; }
.bar:nth-child(7)  { animation-delay: 0.3s; }
.bar:nth-child(8)  { animation-delay: 0.35s; }
```

Note: `transform-origin: bottom` requires the bars to be positioned using `y` and `height` attributes (not `transform`). For SVG `<rect>` elements, apply the animation to a `<g>` wrapper or use JS-based animation.

### JS-Based Bar Animation (more reliable for SVG)

```js
function animateBars() {
  const bars = document.querySelectorAll('.bar');
  bars.forEach((bar, i) => {
    const targetHeight = parseFloat(bar.getAttribute('height'));
    const targetY = parseFloat(bar.getAttribute('y'));
    const baseY = 260; // x-axis position
    bar.setAttribute('height', '0');
    bar.setAttribute('y', baseY);

    setTimeout(() => {
      bar.style.transition = 'height 0.4s ease-out, y 0.4s ease-out';
      bar.setAttribute('height', targetHeight);
      bar.setAttribute('y', targetY);
    }, i * 60);
  });
}

// Respect reduced motion
if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  document.addEventListener('DOMContentLoaded', animateBars);
}
```

### Line Draw-In Animation

```css
.chart polyline {
  stroke-dasharray: 1000;
  stroke-dashoffset: 1000;
  animation: line-draw 1s ease-out forwards;
}
@keyframes line-draw {
  to { stroke-dashoffset: 0; }
}
```

### JS-Based Line Draw (accurate dasharray)

```js
function animateLines() {
  document.querySelectorAll('polyline').forEach(line => {
    const length = line.getTotalLength();
    line.style.strokeDasharray = length;
    line.style.strokeDashoffset = length;
    line.style.transition = 'stroke-dashoffset 0.8s ease-out';
    // Trigger after a frame so the transition fires
    requestAnimationFrame(() => {
      line.style.strokeDashoffset = '0';
    });
  });
}

if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  document.addEventListener('DOMContentLoaded', animateLines);
}
```

---

## Hover States for Data Points

```css
.data-point {
  transition: r 0.15s ease, opacity 0.15s ease;
  cursor: pointer;
}
.data-point:hover {
  r: 7;
  opacity: 1;
}

.bar {
  transition: opacity 0.15s ease;
  cursor: pointer;
}
.bar:hover {
  opacity: 1;
  filter: brightness(1.1);
}
```

---

## Responsive Chart Behavior

```css
/* Charts fill container width */
.chart {
  width: 100%;
  height: auto;
}

/* On mobile, force charts to minimum readable width with horizontal scroll */
@media (max-width: 640px) {
  .chart-card {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  .chart {
    min-width: 480px;
  }
  .dash-charts {
    grid-template-columns: 1fr;
  }
  .metric-row {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 480px) {
  .metric-row {
    grid-template-columns: 1fr;
  }
}
```

---

## Print Styles

```css
@media print {
  body {
    background: white !important;
    color: black !important;
  }
  .dash-header,
  .dash-filters,
  .chart-tooltip,
  .btn-primary,
  .btn-secondary {
    display: none !important;
  }
  .chart-card,
  .metric-card {
    border: 1px solid #ccc !important;
    box-shadow: none !important;
    break-inside: avoid;
  }
  .bar { fill: #333 !important; }
  polyline { stroke: #333 !important; }
  .data-point { fill: #333 !important; }
  .legend-swatch { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
}
```

---

## Data Generation Helper

Generate chart data from JS objects. Keeps data separate from rendering.

```js
function generateBarChart(containerId, data, options = {}) {
  const { width = 600, height = 300, color = 'var(--accent)' } = options;
  const margin = { top: 20, right: 20, bottom: 40, left: 50 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;

  const maxVal = Math.max(...data.map(d => d.value));
  const barWidth = Math.min(40, (plotW / data.length) * 0.6);
  const gap = plotW / data.length;

  let svg = `<svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${options.label || 'Bar chart'}" style="width:100%;max-width:${width}px;">`;

  // Axes and grid
  svg += `<line x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${margin.top + plotH}" class="axis"/>`;
  svg += `<line x1="${margin.left}" y1="${margin.top + plotH}" x2="${margin.left + plotW}" y2="${margin.top + plotH}" class="axis"/>`;

  // Grid lines and Y labels
  for (let i = 0; i <= 3; i++) {
    const y = margin.top + (plotH / 3) * i;
    const val = Math.round(maxVal * (1 - i / 3));
    svg += `<line x1="${margin.left}" y1="${y}" x2="${margin.left + plotW}" y2="${y}" class="grid"/>`;
    svg += `<text x="${margin.left - 5}" y="${y + 4}" text-anchor="end" class="axis-label">${val}</text>`;
  }

  // Bars
  data.forEach((d, i) => {
    const x = margin.left + gap * i + (gap - barWidth) / 2;
    const barH = (d.value / maxVal) * plotH;
    const y = margin.top + plotH - barH;
    svg += `<rect x="${x}" y="${y}" width="${barWidth}" height="${barH}" rx="3" fill="${color}" opacity="0.85" class="bar"><title>${d.label}: ${d.value}</title></rect>`;
    svg += `<text x="${x + barWidth / 2}" y="${margin.top + plotH + 18}" text-anchor="middle" class="axis-label">${d.label}</text>`;
  });

  svg += '</svg>';
  document.getElementById(containerId).innerHTML = svg;
}
```

---

## Filter Controls

Wire time-range or category filters to chart re-rendering.

```js
function filterData(range) {
  // Determine data subset based on range
  const now = Date.now();
  const rangeMs = { '7d': 7, '30d': 30, '90d': 90 }[range] * 86400000;
  const filtered = ALL_DATA.filter(d => (now - d.timestamp) <= rangeMs);

  // Re-render charts with filtered data
  generateBarChart('bar-container', filtered.map(d => ({ label: d.date, value: d.value })));
  updateMetrics(filtered);
  updateTable(filtered);

  // Update the last-updated timestamp
  const el = document.getElementById('last-updated');
  if (el) el.textContent = new Date().toLocaleString();
}
```

---

## Pattern Selection Guide

| Need | Pattern | Key Elements |
|---|---|---|
| Compare values across categories | Bar chart | Bars, labels, grid, optional grouping |
| Show change over time | Line chart | Polyline, area fill, data points |
| Show part-of-whole | Donut chart | Stroke-dasharray circles, center label, legend |
| Top-level KPIs | Metric cards | Value, label, delta with color coding |
| Detailed ranked data | Comparison table | Table rows with inline bar fills |
| Relationships / network | Ring visualization | Positioned nodes, connecting lines |
| Full overview | Dashboard layout | Header + metrics + charts + table |

---

## Anti-Patterns

| Pattern | Why Wrong | Do Instead |
|---|---|---|
| Canvas for static charts | Not accessible, blurry on zoom, can't style with CSS | Use inline SVG |
| Chart.js / D3 CDN import | Breaks self-contained constraint | Build SVG with vanilla JS or static markup |
| Colors without meaning | Decorative gradients obscure data | Use categorical or sequential color scales from tokens |
| Missing `<title>` on data elements | Screen readers can't access data values | Every bar, point, and segment needs a `<title>` |
| Charts without labels | Data is unreadable without context | Always include axis labels, a legend, and a chart title |
| Fixed-width charts | Break on mobile, ignore container | Use `viewBox` + `width: 100%` for responsiveness |
| Tooltips via `title` attribute only | Inconsistent across browsers, can't style | Use the JS tooltip pattern with positioned div |
| Animation without reduced-motion check | Triggers vestibular disorders | Guard all animation behind `prefers-reduced-motion` |
| Using color alone to convey meaning | Fails for color-blind users | Supplement with labels, patterns, or shapes |
