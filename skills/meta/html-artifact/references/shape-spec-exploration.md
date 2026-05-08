# Shape Reference: Spec / Exploration

> **Shape**: spec | **Signal words**: plan, explore, compare, brainstorm, approach, option, tradeoff, direction
> **Gallery basis**: 01 (Three code approaches), 02 (Visual design directions), 16 (Implementation plan)
> **Generated**: 2026-05-08

---

## Design System Tokens (Birchline)

All patterns below reference these variables. The html-builder agent embeds them in a `<style>` block at the top of every artifact.

```css
:root {
  /* Birchline palette */
  --color-clay: #D97757;
  --color-slate: #141413;
  --color-ivory: #FAF9F5;
  --color-primary: var(--color-clay);
  --color-bg: var(--color-ivory);
  --color-text: var(--color-slate);

  /* Grays */
  --color-gray-100: #F0EFEB;
  --color-gray-200: #E2E0DA;
  --color-gray-300: #C8C5BC;
  --color-gray-400: #A9A69D;
  --color-gray-500: #7A776F;
  --color-gray-600: #52504A;

  /* Semantic */
  --color-danger: #B04A4A;
  --color-warning: #C78E3F;
  --color-success: #788C5D;
  --color-info: #5B7FA5;

  /* Spacing scale (4px base) */
  --sp-1: 4px; --sp-2: 8px; --sp-3: 12px; --sp-4: 16px;
  --sp-5: 20px; --sp-6: 24px; --sp-7: 32px; --sp-8: 40px;
  --sp-9: 48px; --sp-10: 64px;

  /* Typography */
  --font-body: 'Instrument Sans', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  --type-hero: clamp(2rem, 4vw, 3rem);
  --type-h2: clamp(1.25rem, 2.5vw, 1.75rem);
  --type-h3: 1.125rem;
  --type-body: 0.9375rem;
  --type-small: 0.8125rem;
  --type-caption: 0.75rem;

  /* Radius */
  --radius-xs: 4px;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
}
```

---

## Page Shell

Every spec/exploration artifact uses this outer structure:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title><!-- Artifact title --></title>
  <style>
    /* Birchline tokens (above) */
    /* Shape-specific CSS (below) */
  </style>
</head>
<body>
  <header class="page-header">
    <h1><!-- Title --></h1>
    <p class="subtitle"><!-- One-line context --></p>
  </header>
  <main>
    <!-- Shape content sections -->
  </main>
  <footer class="page-footer">
    <p>Generated <time datetime="YYYY-MM-DD">Month DD, YYYY</time></p>
  </footer>
  <script>
    /* Shape-specific JS (below) */
  </script>
</body>
</html>
```

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; }
body {
  font-family: var(--font-body);
  font-size: var(--type-body);
  line-height: 1.6;
  color: var(--color-text);
  background: var(--color-bg);
  padding: var(--sp-7) var(--sp-5);
  max-width: 1200px;
  margin: 0 auto;
}
.page-header { margin-bottom: var(--sp-9); }
.page-header h1 {
  font-size: var(--type-hero);
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: -0.02em;
}
.subtitle {
  margin-top: var(--sp-2);
  color: var(--color-gray-500);
  font-size: var(--type-body);
}
.page-footer {
  margin-top: var(--sp-10);
  padding-top: var(--sp-5);
  border-top: 1px solid var(--color-gray-200);
  color: var(--color-gray-400);
  font-size: var(--type-caption);
}
```

---

## Pattern 1: Comparison Grid

Use when the request says "compare N approaches", "explore options", "pros and cons".

### HTML

```html
<section class="comparison-section">
  <h2>Approaches</h2>
  <div class="comparison-grid">

    <article class="approach-card" data-approach="1">
      <header class="approach-header">
        <span class="approach-number">01</span>
        <h3>Approach Name</h3>
        <span class="approach-tag">Recommended</span>
      </header>
      <p class="approach-summary">One-sentence description of what this approach does.</p>
      <div class="pros-cons">
        <div class="pros">
          <h4>Strengths</h4>
          <ul>
            <li>First advantage</li>
            <li>Second advantage</li>
          </ul>
        </div>
        <div class="cons">
          <h4>Tradeoffs</h4>
          <ul>
            <li>First tradeoff</li>
            <li>Second tradeoff</li>
          </ul>
        </div>
      </div>
      <div class="code-example">
        <pre><code>// Key implementation snippet
const result = await doThing();</code></pre>
      </div>
      <footer class="approach-meta">
        <span class="badge">Complexity: Low</span>
        <span class="badge">Testability: High</span>
        <span class="badge">Migration: Easy</span>
      </footer>
    </article>

    <!-- Repeat for each approach -->
  </div>
</section>
```

### CSS

```css
/* --- Comparison Grid --- */
.comparison-section { margin-bottom: var(--sp-10); }
.comparison-section h2 {
  font-size: var(--type-h2);
  font-weight: 600;
  margin-bottom: var(--sp-6);
}
.comparison-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--sp-5);
}

/* --- Approach Card --- */
.approach-card {
  border: 1px solid var(--color-gray-200);
  border-radius: var(--radius-md);
  padding: var(--sp-6);
  background: white;
  transition: border-color 0.15s ease;
}
.approach-card:hover {
  border-color: var(--color-gray-400);
}

/* Recommended highlight */
.approach-card:has(.approach-tag) {
  border-color: var(--color-primary);
  border-width: 2px;
}

.approach-header {
  display: flex;
  align-items: baseline;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
  flex-wrap: wrap;
}
.approach-number {
  font-family: var(--font-mono);
  font-size: var(--type-h2);
  font-weight: 700;
  color: var(--color-gray-300);
  line-height: 1;
}
.approach-header h3 {
  font-size: var(--type-h3);
  font-weight: 600;
  flex: 1;
}
.approach-tag {
  font-size: var(--type-caption);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-primary);
  background: color-mix(in srgb, var(--color-primary) 10%, transparent);
  padding: 2px 8px;
  border-radius: var(--radius-xs);
}
.approach-summary {
  color: var(--color-gray-600);
  margin-bottom: var(--sp-5);
}

/* --- Pros / Cons --- */
.pros-cons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-4);
  margin-bottom: var(--sp-5);
}
.pros-cons h4 {
  font-size: var(--type-small);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: var(--sp-2);
}
.pros h4 { color: var(--color-success); }
.cons h4 { color: var(--color-danger); }
.pros-cons ul {
  list-style: none;
  padding: 0;
}
.pros-cons li {
  font-size: var(--type-small);
  padding: var(--sp-1) 0;
  padding-left: var(--sp-5);
  position: relative;
}
.pros li::before {
  content: '+';
  position: absolute;
  left: 0;
  color: var(--color-success);
  font-weight: 700;
  font-family: var(--font-mono);
}
.cons li::before {
  content: '\2212'; /* minus sign */
  position: absolute;
  left: 0;
  color: var(--color-danger);
  font-weight: 700;
  font-family: var(--font-mono);
}

/* --- Code Example --- */
.code-example {
  margin-bottom: var(--sp-5);
}
.code-example pre {
  background: var(--color-slate);
  color: var(--color-ivory);
  padding: var(--sp-4);
  border-radius: var(--radius-sm);
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: var(--type-small);
  line-height: 1.5;
}

/* --- Metadata Badges --- */
.approach-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  padding-top: var(--sp-4);
  border-top: 1px solid var(--color-gray-100);
}
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  background: var(--color-gray-100);
  font-size: var(--type-caption);
  font-weight: 500;
  color: var(--color-gray-600);
}

/* --- Responsive: 3-col -> 2-col -> 1-col --- */
@media (max-width: 1024px) {
  .comparison-grid { grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
}
@media (max-width: 640px) {
  .comparison-grid { grid-template-columns: 1fr; }
  .pros-cons { grid-template-columns: 1fr; }
}
```

---

## Pattern 2: Recommendation Section

Always include after the comparison grid. Makes the artifact actionable.

### HTML

```html
<section class="recommendation">
  <h2>Recommendation</h2>
  <p class="verdict"><strong>Approach 2</strong> — because it balances complexity and testability.</p>
  <table class="tradeoff-matrix">
    <thead>
      <tr>
        <th>Criterion</th>
        <th>Approach 1</th>
        <th>Approach 2</th>
        <th>Approach 3</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Complexity</td>
        <td class="cell-success">Low</td>
        <td class="cell-success">Low</td>
        <td class="cell-danger">High</td>
      </tr>
      <tr>
        <td>Testability</td>
        <td class="cell-warning">Medium</td>
        <td class="cell-success">High</td>
        <td class="cell-success">High</td>
      </tr>
      <tr>
        <td>Migration effort</td>
        <td class="cell-success">Easy</td>
        <td class="cell-warning">Moderate</td>
        <td class="cell-danger">Hard</td>
      </tr>
    </tbody>
  </table>
</section>
```

### CSS

```css
/* --- Recommendation --- */
.recommendation {
  border-left: 3px solid var(--color-primary);
  padding-left: var(--sp-6);
  margin-top: var(--sp-9);
}
.recommendation h2 {
  font-size: var(--type-h2);
  font-weight: 600;
  margin-bottom: var(--sp-4);
}
.verdict {
  font-size: var(--type-h3);
  margin-bottom: var(--sp-6);
}

/* --- Tradeoff Matrix --- */
.tradeoff-matrix {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--type-small);
}
.tradeoff-matrix th,
.tradeoff-matrix td {
  padding: var(--sp-3) var(--sp-4);
  text-align: left;
  border-bottom: 1px solid var(--color-gray-200);
}
.tradeoff-matrix th {
  font-weight: 600;
  font-size: var(--type-caption);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-gray-500);
}
.tradeoff-matrix td:first-child {
  font-weight: 500;
}

/* Cell coloring */
.cell-success { color: var(--color-success); font-weight: 600; }
.cell-warning { color: var(--color-warning); font-weight: 600; }
.cell-danger  { color: var(--color-danger);  font-weight: 600; }

@media (max-width: 640px) {
  .tradeoff-matrix { font-size: var(--type-caption); }
  .tradeoff-matrix th, .tradeoff-matrix td { padding: var(--sp-2) var(--sp-3); }
}
```

---

## Pattern 3: Implementation Plan

Use for "implementation plan", "migration plan", "rollout strategy". Combines timeline, data-flow diagram, code snippets, and risk table.

### HTML — Hero + TL;DR

```html
<header class="plan-header">
  <h1>Implementation Plan: Auth Migration</h1>
  <div class="tldr">
    <strong>TL;DR</strong> — Migrate from localStorage tokens to httpOnly cookies in 3 phases
    over 2 sprints. Zero downtime. Backward compatible during transition.
  </div>
</header>
```

```css
.tldr {
  background: var(--color-gray-100);
  border-radius: var(--radius-sm);
  padding: var(--sp-4) var(--sp-5);
  margin-top: var(--sp-5);
  font-size: var(--type-body);
  line-height: 1.5;
}
.tldr strong {
  color: var(--color-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: var(--type-caption);
}
```

### HTML — Timeline

```html
<section class="timeline-section">
  <h2>Milestones</h2>
  <div class="timeline">
    <div class="milestone completed">
      <div class="milestone-marker"></div>
      <div class="milestone-content">
        <span class="milestone-label">Phase 1</span>
        <h3>Cookie infrastructure</h3>
        <p>Set up httpOnly cookie issuance on login, refresh, and logout endpoints.</p>
        <span class="milestone-date">Sprint 14 — Week 1</span>
      </div>
    </div>
    <div class="milestone current">
      <div class="milestone-marker"></div>
      <div class="milestone-content">
        <span class="milestone-label">Phase 2</span>
        <h3>Dual-read middleware</h3>
        <p>Auth middleware reads cookie first, falls back to Authorization header. Both paths valid.</p>
        <span class="milestone-date">Sprint 14 — Week 2</span>
      </div>
    </div>
    <div class="milestone upcoming">
      <div class="milestone-marker"></div>
      <div class="milestone-content">
        <span class="milestone-label">Phase 3</span>
        <h3>Header deprecation</h3>
        <p>Remove localStorage token writes. Log header-only requests for one sprint. Remove fallback.</p>
        <span class="milestone-date">Sprint 15</span>
      </div>
    </div>
  </div>
</section>
```

### CSS — Timeline

```css
.timeline-section { margin: var(--sp-9) 0; }
.timeline-section h2 {
  font-size: var(--type-h2);
  font-weight: 600;
  margin-bottom: var(--sp-6);
}
.timeline {
  position: relative;
  padding-left: var(--sp-8);
}
/* Vertical connecting line */
.timeline::before {
  content: '';
  position: absolute;
  left: 11px;
  top: 4px;
  bottom: 4px;
  width: 2px;
  background: var(--color-gray-200);
}
.milestone {
  position: relative;
  padding-bottom: var(--sp-7);
}
.milestone:last-child { padding-bottom: 0; }

/* Dot marker */
.milestone-marker {
  position: absolute;
  left: calc(-1 * var(--sp-8) + 4px);
  top: 4px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid var(--color-gray-300);
  background: white;
  z-index: 1;
}
.milestone.completed .milestone-marker {
  background: var(--color-success);
  border-color: var(--color-success);
}
.milestone.current .milestone-marker {
  background: var(--color-primary);
  border-color: var(--color-primary);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--color-primary) 20%, transparent);
}
.milestone.upcoming .milestone-marker {
  background: white;
  border-color: var(--color-gray-300);
}

.milestone-label {
  font-size: var(--type-caption);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-gray-500);
}
.milestone-content h3 {
  font-size: var(--type-h3);
  font-weight: 600;
  margin: var(--sp-1) 0 var(--sp-2);
}
.milestone-content p {
  color: var(--color-gray-600);
  font-size: var(--type-small);
  margin-bottom: var(--sp-2);
}
.milestone-date {
  font-size: var(--type-caption);
  color: var(--color-gray-400);
}
```

### HTML — Risk Table

```html
<section class="risk-section">
  <h2>Risks</h2>
  <table class="risk-table">
    <thead>
      <tr>
        <th>Risk</th>
        <th>Level</th>
        <th>Mitigation</th>
      </tr>
    </thead>
    <tbody>
      <tr class="risk-high">
        <td>CSRF with cookie auth</td>
        <td><span class="risk-level high">HIGH</span></td>
        <td>SameSite=Strict + CSRF token on state-changing requests</td>
      </tr>
      <tr class="risk-med">
        <td>Dual-read auth confusion</td>
        <td><span class="risk-level med">MED</span></td>
        <td>Structured logging to track which path each request uses</td>
      </tr>
      <tr class="risk-low">
        <td>Client-side cookie size limits</td>
        <td><span class="risk-level low">LOW</span></td>
        <td>Token payload is <300 bytes; 4KB limit is not a concern</td>
      </tr>
    </tbody>
  </table>
</section>
```

### CSS — Risk Table

```css
.risk-section { margin: var(--sp-9) 0; }
.risk-section h2 {
  font-size: var(--type-h2);
  font-weight: 600;
  margin-bottom: var(--sp-6);
}
.risk-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--type-small);
}
.risk-table th,
.risk-table td {
  padding: var(--sp-3) var(--sp-4);
  text-align: left;
  border-bottom: 1px solid var(--color-gray-200);
}
.risk-table th {
  font-weight: 600;
  font-size: var(--type-caption);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-gray-500);
}

/* Row tinting */
.risk-high td:first-child { border-left: 3px solid var(--color-danger); padding-left: calc(var(--sp-4) - 3px); }
.risk-med  td:first-child { border-left: 3px solid var(--color-warning); padding-left: calc(var(--sp-4) - 3px); }
.risk-low  td:first-child { border-left: 3px solid var(--color-success); padding-left: calc(var(--sp-4) - 3px); }

.risk-level {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  font-size: var(--type-caption);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.risk-level.high { background: color-mix(in srgb, var(--color-danger) 12%, transparent); color: var(--color-danger); }
.risk-level.med  { background: color-mix(in srgb, var(--color-warning) 12%, transparent); color: var(--color-warning); }
.risk-level.low  { background: color-mix(in srgb, var(--color-success) 12%, transparent); color: var(--color-success); }

@media (max-width: 640px) {
  .risk-table { font-size: var(--type-caption); }
  .risk-table th:nth-child(3), .risk-table td:nth-child(3) { display: none; }
}
```

---

## Pattern 4: SVG Data-Flow Diagram

Self-contained inline SVG for architecture / data-flow visualization. No external dependencies.

### HTML

```html
<section class="diagram-section">
  <h2>Data Flow</h2>
  <div class="diagram-container">
    <svg viewBox="0 0 800 400" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Data flow diagram showing request path from browser through API to database">

      <!-- Definitions -->
      <defs>
        <marker id="arrow" viewBox="0 0 10 7" refX="10" refY="3.5"
                markerWidth="8" markerHeight="6" orient="auto-start-auto">
          <path d="M 0 0 L 10 3.5 L 0 7 z" fill="var(--color-gray-500)" />
        </marker>
        <marker id="arrow-async" viewBox="0 0 10 7" refX="10" refY="3.5"
                markerWidth="8" markerHeight="6" orient="auto-start-auto">
          <path d="M 0 0 L 10 3.5 L 0 7 z" fill="var(--color-info)" />
        </marker>
      </defs>

      <!-- Layer: Frontend (blue-tinted) -->
      <rect x="40" y="60" width="160" height="60" rx="10" ry="10"
            fill="color-mix(in srgb, var(--color-info) 8%, white)"
            stroke="var(--color-info)" stroke-width="1.5" />
      <text x="120" y="85" text-anchor="middle"
            font-family="var(--font-mono)" font-size="11" fill="var(--color-info)"
            font-weight="600">FRONTEND</text>
      <text x="120" y="105" text-anchor="middle"
            font-family="var(--font-mono)" font-size="11" fill="var(--color-gray-600)">Browser / SPA</text>

      <!-- Layer: API (clay-tinted) -->
      <rect x="320" y="60" width="160" height="60" rx="10" ry="10"
            fill="color-mix(in srgb, var(--color-primary) 8%, white)"
            stroke="var(--color-primary)" stroke-width="1.5" />
      <text x="400" y="85" text-anchor="middle"
            font-family="var(--font-mono)" font-size="11" fill="var(--color-primary)"
            font-weight="600">API</text>
      <text x="400" y="105" text-anchor="middle"
            font-family="var(--font-mono)" font-size="11" fill="var(--color-gray-600)">Auth Middleware</text>

      <!-- Layer: Database (success-tinted) -->
      <rect x="600" y="60" width="160" height="60" rx="10" ry="10"
            fill="color-mix(in srgb, var(--color-success) 8%, white)"
            stroke="var(--color-success)" stroke-width="1.5" />
      <text x="680" y="85" text-anchor="middle"
            font-family="var(--font-mono)" font-size="11" fill="var(--color-success)"
            font-weight="600">DATABASE</text>
      <text x="680" y="105" text-anchor="middle"
            font-family="var(--font-mono)" font-size="11" fill="var(--color-gray-600)">PostgreSQL</text>

      <!-- Arrow: Frontend -> API (solid = request) -->
      <line x1="200" y1="90" x2="318" y2="90"
            stroke="var(--color-gray-500)" stroke-width="1.5"
            marker-end="url(#arrow)" />
      <text x="260" y="80" text-anchor="middle"
            font-family="var(--font-mono)" font-size="10" fill="var(--color-gray-500)">POST /login</text>

      <!-- Arrow: API -> Database (solid = request) -->
      <line x1="480" y1="90" x2="598" y2="90"
            stroke="var(--color-gray-500)" stroke-width="1.5"
            marker-end="url(#arrow)" />
      <text x="540" y="80" text-anchor="middle"
            font-family="var(--font-mono)" font-size="10" fill="var(--color-gray-500)">SELECT user</text>

      <!-- Arrow: API -> Frontend (dashed = async/real-time) -->
      <line x1="318" y1="130" x2="200" y2="130"
            stroke="var(--color-info)" stroke-width="1.5"
            stroke-dasharray="6 4"
            marker-end="url(#arrow-async)" />
      <text x="260" y="150" text-anchor="middle"
            font-family="var(--font-mono)" font-size="10" fill="var(--color-info)">Set-Cookie (httpOnly)</text>

      <!-- Legend -->
      <g transform="translate(40, 340)">
        <line x1="0" y1="0" x2="30" y2="0" stroke="var(--color-gray-500)" stroke-width="1.5" />
        <text x="38" y="4" font-family="var(--font-mono)" font-size="10" fill="var(--color-gray-500)">Synchronous request</text>
        <line x1="200" y1="0" x2="230" y2="0" stroke="var(--color-info)" stroke-width="1.5" stroke-dasharray="6 4" />
        <text x="238" y="4" font-family="var(--font-mono)" font-size="10" fill="var(--color-info)">Async / real-time</text>
      </g>

    </svg>
  </div>
</section>
```

### CSS

```css
.diagram-section { margin: var(--sp-9) 0; }
.diagram-section h2 {
  font-size: var(--type-h2);
  font-weight: 600;
  margin-bottom: var(--sp-6);
}
.diagram-container {
  background: white;
  border: 1px solid var(--color-gray-200);
  border-radius: var(--radius-md);
  padding: var(--sp-5);
  overflow-x: auto;
}
.diagram-container svg {
  width: 100%;
  height: auto;
  min-width: 600px; /* prevent squishing on mobile — scrolls horizontally */
}
```

### SVG Construction Rules

| Element | Pattern | Notes |
|---|---|---|
| Box | `<rect rx="10" ry="10">` | Rounded corners, 1.5px stroke |
| Label | `<text font-family="var(--font-mono)" font-size="11">` | Monospace, 11px |
| Sync arrow | Solid line + `marker-end="url(#arrow)"` | Gray stroke |
| Async arrow | Dashed line `stroke-dasharray="6 4"` + blue arrow marker | Info color |
| Layer color | `color-mix(in srgb, <layer-color> 8%, white)` fill, full color stroke | Frontend=info, API=primary, DB=success |
| Legend | Group at bottom with line samples + labels | Always include |

---

## Pattern 5: Light/Dark Preview Toggle

Use for design direction artifacts (gallery example 02). Lets the reader see how a design holds up in both modes.

### HTML

```html
<div class="preview-controls">
  <button id="theme-toggle" class="toggle-btn" aria-pressed="false" aria-label="Toggle dark preview mode">
    <span class="toggle-label-light">Light</span>
    <span class="toggle-track">
      <span class="toggle-thumb"></span>
    </span>
    <span class="toggle-label-dark">Dark</span>
  </button>
</div>

<div class="preview-frame" id="preview-frame">
  <!-- Design preview content rendered here -->
  <div class="preview-sample">
    <h3>Heading Sample</h3>
    <p>Body text sample for contrast verification.</p>
    <button class="preview-cta">Primary Action</button>
  </div>
</div>
```

### CSS

```css
/* --- Toggle Button --- */
.preview-controls {
  display: flex;
  justify-content: flex-end;
  margin-bottom: var(--sp-4);
}
.toggle-btn {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  background: none;
  border: none;
  cursor: pointer;
  font-family: var(--font-body);
  font-size: var(--type-small);
  color: var(--color-gray-500);
  padding: var(--sp-2);
  border-radius: var(--radius-sm);
}
.toggle-btn:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
.toggle-track {
  display: inline-block;
  width: 36px;
  height: 20px;
  background: var(--color-gray-200);
  border-radius: 10px;
  position: relative;
  transition: background 0.2s ease;
}
.toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  background: white;
  border-radius: 50%;
  transition: transform 0.2s ease;
  box-shadow: 0 1px 2px rgba(0,0,0,0.15);
}

/* Active state */
.toggle-btn[aria-pressed="true"] .toggle-track { background: var(--color-slate); }
.toggle-btn[aria-pressed="true"] .toggle-thumb { transform: translateX(16px); }

/* --- Preview Frame --- */
.preview-frame {
  border: 1px solid var(--color-gray-200);
  border-radius: var(--radius-md);
  padding: var(--sp-7);
  transition: background 0.3s ease, color 0.3s ease;
}
.preview-frame.preview-dark {
  background: #1a1a19;
  color: var(--color-ivory);
  border-color: #333;
}
.preview-frame.preview-dark .preview-cta {
  background: var(--color-primary);
  color: white;
}

@media (prefers-reduced-motion: reduce) {
  .toggle-thumb, .preview-frame { transition: none; }
}
```

### JS

```js
(function () {
  const toggle = document.getElementById('theme-toggle');
  const frame = document.getElementById('preview-frame');

  if (!toggle || !frame) return;

  toggle.addEventListener('click', () => {
    const isDark = toggle.getAttribute('aria-pressed') === 'true';
    toggle.setAttribute('aria-pressed', String(!isDark));
    frame.classList.toggle('preview-dark', !isDark);
  });

  // Keyboard: Enter and Space activate the toggle
  toggle.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggle.click();
    }
  });
})();
```

---

## Pattern 6: Section Code Snippet with Context

For implementation plans that include inline code examples with explanatory context.

### HTML

```html
<section class="code-section">
  <div class="code-context">
    <h3>Cookie issuance on login</h3>
    <p>The <code>/login</code> endpoint sets an httpOnly cookie alongside the existing JSON response.
       This maintains backward compatibility during the dual-read phase.</p>
  </div>
  <div class="code-block">
    <header class="code-block-header">
      <span class="code-filename">src/auth/login.ts</span>
      <span class="code-lang">TypeScript</span>
    </header>
    <pre><code><span class="kw">export async function</span> <span class="fn">handleLogin</span>(req: Request, res: Response) {
  <span class="kw">const</span> { email, password } = req.body;
  <span class="kw">const</span> user = <span class="kw">await</span> authenticate(email, password);

  <span class="kw">const</span> token = signJWT({ sub: user.id, role: user.role });

  <span class="cm">// Phase 1: Set httpOnly cookie</span>
  res.cookie(<span class="st">'session'</span>, token, {
    httpOnly: <span class="kw">true</span>,
    secure: <span class="kw">true</span>,
    sameSite: <span class="st">'strict'</span>,
    maxAge: 7 * 24 * 60 * 60 * 1000,
  });

  <span class="cm">// Backward compat: still return token in body</span>
  res.json({ token, user: sanitize(user) });
}</code></pre>
  </div>
</section>
```

### CSS

```css
.code-section {
  margin: var(--sp-7) 0;
}
.code-context {
  margin-bottom: var(--sp-4);
}
.code-context h3 {
  font-size: var(--type-h3);
  font-weight: 600;
  margin-bottom: var(--sp-2);
}
.code-context p {
  color: var(--color-gray-600);
  font-size: var(--type-small);
}
.code-context code {
  font-family: var(--font-mono);
  background: var(--color-gray-100);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 0.875em;
}
.code-block {
  border: 1px solid var(--color-gray-200);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.code-block-header {
  display: flex;
  justify-content: space-between;
  padding: var(--sp-2) var(--sp-4);
  background: var(--color-gray-100);
  border-bottom: 1px solid var(--color-gray-200);
  font-size: var(--type-caption);
}
.code-filename {
  font-family: var(--font-mono);
  font-weight: 500;
  color: var(--color-gray-600);
}
.code-lang {
  color: var(--color-gray-400);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}
.code-block pre {
  background: var(--color-slate);
  color: var(--color-ivory);
  padding: var(--sp-5);
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: var(--type-small);
  line-height: 1.6;
  margin: 0;
}

/* Syntax highlight tokens */
.kw { color: #C792EA; } /* keyword — purple */
.fn { color: #82AAFF; } /* function — blue */
.st { color: #C3E88D; } /* string — green */
.cm { color: #6A737D; } /* comment — gray */
.nr { color: #F78C6C; } /* number — orange */
```

---

## Composition Guide

Assemble spec/exploration artifacts by selecting patterns above:

| Request Shape | Patterns to Combine |
|---|---|
| "Compare N approaches" | Shell + Comparison Grid + Recommendation |
| "Design directions" | Shell + Comparison Grid + Light/Dark Toggle + Recommendation |
| "Implementation plan" | Shell + TL;DR + Timeline + Code Snippets + Risk Table + SVG Diagram |
| "Explore tradeoffs" | Shell + Comparison Grid (2 approaches) + Recommendation |
| "Architecture options" | Shell + Comparison Grid + SVG Diagram + Recommendation |

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

## Accessibility Checklist

- [ ] All `<svg>` elements have `role="img"` and `aria-label`
- [ ] Toggle buttons use `aria-pressed` state
- [ ] Focus-visible outlines on all interactive elements
- [ ] Color is never the sole indicator (badges have text labels, risk levels have text + color)
- [ ] `prefers-reduced-motion` disables transitions
- [ ] Table headers use `<th>` with scope implied by position
- [ ] Semantic elements: `<article>`, `<section>`, `<header>`, `<footer>`, `<nav>`, `<main>`
- [ ] Font sizes in rem/clamp — respect user zoom
