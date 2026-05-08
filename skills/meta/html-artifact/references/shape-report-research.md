# Shape: Report & Research

Loaded when `detect-shape.py` returns `report`. For artifacts that synthesize information: status reports, incident timelines, feature explainers, concept tutorials, research summaries.

**Theme:** Birchline (status reports, general), Minimal Document (long-form explainers, research). Match to content length and formality.

**Core principle:** Reports are SCANNABLE. Every report opens with a TL;DR. Every section has one job. Information density is high — no filler, no decorative whitespace without purpose.

---

## Layout Patterns

| Layout | Use When | Structure |
|---|---|---|
| Single column + sticky TOC | Long explainers, tutorials | Sticky sidebar nav, main content column (max 680px) |
| Metrics dashboard | Status reports, weekly updates | Metric cards top, sectioned content below |
| Timeline | Incidents, changelogs, postmortems | Vertical timeline with dots, timestamps, content |
| Split: visualization + glossary | Concept explainers | Interactive viz left, reference sidebar right |
| Accordion | Step-by-step guides, how-tos | Numbered collapsible sections |

### Single Column + Sticky TOC

For long-form content. TOC floats on the left (desktop) or collapses to top (mobile).

```html
<div class="report-layout">
  <nav class="toc" aria-label="Table of contents">
    <h3>On this page</h3>
    <a href="#tldr">TL;DR</a>
    <a href="#how-it-works">How it works</a>
    <a href="#gotchas">Gotchas</a>
    <a href="#faq">FAQ</a>
  </nav>
  <main class="report-content">
    <section id="tldr">...</section>
    <section id="how-it-works">...</section>
    <section id="gotchas">...</section>
    <section id="faq">...</section>
  </main>
</div>
```

```css
.report-layout {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: var(--sp-7);
  max-width: 960px;
  margin: 0 auto;
  padding: var(--sp-6) var(--sp-4);
}

@media (max-width: 640px) {
  .report-layout {
    grid-template-columns: 1fr;
    gap: var(--sp-4);
  }
  .toc {
    position: static !important;
    border-bottom: 1px solid var(--border-subtle);
    padding-bottom: var(--sp-4);
    margin-bottom: var(--sp-4);
  }
}

.toc {
  position: sticky;
  top: var(--sp-5);
  align-self: start;
}

.toc h3 {
  font: var(--type-caption);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: var(--sp-3);
}

.toc a {
  display: block;
  padding: var(--sp-1) 0;
  font: var(--type-small);
  color: var(--text-secondary);
  text-decoration: none;
  border-left: 2px solid transparent;
  padding-left: var(--sp-3);
  transition: color 0.15s ease, border-color 0.15s ease;
}

.toc a:hover {
  color: var(--text-primary);
}

.toc a.active {
  color: var(--accent);
  border-left-color: var(--accent);
  font-weight: 500;
}

.toc a:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: var(--radius-xs);
}

.report-content {
  max-width: 680px;
}

.report-content section {
  margin-bottom: var(--sp-7);
}
```

**Scroll-spy for active TOC link** (optional, for long documents):

```js
var tocLinks = document.querySelectorAll('.toc a');
var sections = document.querySelectorAll('.report-content section[id]');

var observer = new IntersectionObserver(function(entries) {
  entries.forEach(function(entry) {
    if (entry.isIntersecting) {
      tocLinks.forEach(function(link) { link.classList.remove('active'); });
      var activeLink = document.querySelector('.toc a[href="#' + entry.target.id + '"]');
      if (activeLink) activeLink.classList.add('active');
    }
  });
}, { rootMargin: '-20% 0px -80% 0px' });

sections.forEach(function(section) { observer.observe(section); });
```

### Metrics Dashboard Layout

Metric cards across the top, content sections below.

```html
<header class="report-header">
  <h1>Weekly Status</h1>
  <p class="report-date">Week of May 5, 2026</p>
</header>
<div class="metrics-row">
  <!-- metric cards -->
</div>
<main class="report-sections">
  <section>...</section>
</main>
```

```css
.report-header {
  margin-bottom: var(--sp-6);
}

.report-header h1 {
  font: var(--type-h1);
  margin-bottom: var(--sp-2);
}

.report-date {
  font: var(--type-small);
  color: var(--text-muted);
}

.report-sections section {
  margin-bottom: var(--sp-7);
}

.report-sections section h2 {
  font: var(--type-h2);
  margin-bottom: var(--sp-4);
  padding-bottom: var(--sp-2);
  border-bottom: 1px solid var(--border-subtle);
}
```

### Split: Visualization + Glossary Sidebar

For concept explainers with interactive diagrams.

```html
<div class="explainer-layout">
  <section class="visualization" aria-label="Interactive diagram">
    <svg id="diagram" width="400" height="400" role="img" aria-label="Concept diagram">
      <!-- Dynamic visualization -->
    </svg>
    <div class="viz-controls">
      <button onclick="addNode()">+ Add Node</button>
      <button onclick="removeNode()">&#8722; Remove</button>
      <button onclick="resetDiagram()">Reset</button>
    </div>
  </section>
  <aside class="glossary-sidebar" aria-label="Glossary">
    <h3>Glossary</h3>
    <dl>
      <dt id="term-hash">Hash function</dt>
      <dd>Maps keys to positions on the ring uniformly.</dd>
      <dt id="term-vnode">Virtual node</dt>
      <dd>Multiple points per server to improve distribution.</dd>
    </dl>
  </aside>
</div>
```

```css
.explainer-layout {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: var(--sp-6);
  align-items: start;
}

@media (max-width: 640px) {
  .explainer-layout {
    grid-template-columns: 1fr;
  }
}

.visualization {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.viz-controls {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
}

.glossary-sidebar {
  position: sticky;
  top: var(--sp-5);
  padding: var(--sp-4);
  background: var(--bg-muted);
  border-radius: var(--radius-sm);
}

.glossary-sidebar h3 {
  font: var(--type-caption);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: var(--sp-3);
}

.glossary-sidebar dt {
  font: var(--type-small);
  font-weight: 600;
  color: var(--text-primary);
  margin-top: var(--sp-3);
}

.glossary-sidebar dd {
  font: var(--type-small);
  color: var(--text-secondary);
  margin-top: var(--sp-1);
  padding-left: 0;
}
```

---

## Content Blocks

### TL;DR Summary Box

**CRITICAL: Every report opens with a TL;DR.** Placed immediately after the title, before any other content.

```html
<div class="tldr-box" role="region" aria-label="Summary">
  <h2 class="tldr-heading">TL;DR</h2>
  <p>Key takeaway in 1-2 sentences. What happened, what it means, what to do.</p>
</div>
```

```css
.tldr-box {
  background: var(--bg-muted);
  border-left: 3px solid var(--accent);
  padding: var(--sp-4) var(--sp-5);
  border-radius: var(--radius-sm);
  margin-bottom: var(--sp-7);
}

.tldr-heading {
  margin: 0 0 var(--sp-2);
  font: var(--type-caption);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.tldr-box p {
  margin: 0;
  font: var(--type-body);
  line-height: 1.6;
}
```

### Metric Callout Cards

Row of key numbers at the top of status reports. Each card: big number, label, optional trend indicator.

```html
<div class="metrics-row" role="region" aria-label="Key metrics">
  <div class="metric-card">
    <span class="metric-value">14</span>
    <span class="metric-label">PRs Merged</span>
    <span class="metric-trend positive" aria-label="Up 3 from last week">&#8593; 3</span>
  </div>
  <div class="metric-card">
    <span class="metric-value">1</span>
    <span class="metric-label">Incidents</span>
    <span class="metric-trend negative" aria-label="Up 1 from last week">&#8593; 1</span>
  </div>
  <div class="metric-card">
    <span class="metric-value">97%</span>
    <span class="metric-label">Uptime</span>
    <span class="metric-trend neutral" aria-label="No change from last week">&#8212; 0</span>
  </div>
  <div class="metric-card">
    <span class="metric-value">3</span>
    <span class="metric-label">Blockers</span>
    <span class="metric-trend positive" aria-label="Down 2 from last week">&#8595; 2</span>
  </div>
</div>
```

```css
.metrics-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--sp-4);
  margin-bottom: var(--sp-6);
}

.metric-card {
  text-align: center;
  padding: var(--sp-5);
  background: var(--bg-surface);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-subtle);
}

.metric-value {
  display: block;
  font-size: 36px;
  font-weight: 600;
  line-height: 1.1;
  color: var(--text-primary);
}

.metric-label {
  display: block;
  font: var(--type-small);
  color: var(--text-muted);
  margin-top: var(--sp-1);
}

.metric-trend {
  display: block;
  font: var(--type-caption);
  margin-top: var(--sp-2);
}

.metric-trend.positive { color: var(--color-success); }
.metric-trend.negative { color: var(--color-danger); }
.metric-trend.neutral  { color: var(--text-muted); }
```

### Collapsible Sections (native `<details>`)

No JS required. Use for step-by-step guides, expandable details, or sections the user may want to skip.

```html
<details class="expandable-section" open>
  <summary>
    <span class="step-number">1</span>
    Configure the rate limiter
  </summary>
  <div class="step-content">
    <p>Detailed explanation here. Can include code, diagrams, or sub-steps.</p>
    <pre><code>rate_limit:
  window: 60s
  max_requests: 100</code></pre>
  </div>
</details>

<details class="expandable-section">
  <summary>
    <span class="step-number">2</span>
    Add middleware to the route
  </summary>
  <div class="step-content">
    <p>Wire the limiter into your HTTP handler chain.</p>
  </div>
</details>
```

```css
details.expandable-section {
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  margin-bottom: var(--sp-3);
}

details.expandable-section summary {
  padding: var(--sp-3) var(--sp-4);
  cursor: pointer;
  font: var(--type-body);
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  list-style: none;
  user-select: none;
}

/* Remove default marker */
details.expandable-section summary::-webkit-details-marker { display: none; }

details.expandable-section summary::after {
  content: '+';
  margin-left: auto;
  font-size: 18px;
  color: var(--text-muted);
  transition: transform 0.15s ease;
}

details.expandable-section[open] summary::after {
  content: '−';
}

details.expandable-section[open] summary {
  border-bottom: 1px solid var(--border-subtle);
}

details.expandable-section summary:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
  border-radius: var(--radius-sm);
}

.step-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--accent);
  color: #FFFFFF;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}

.step-content {
  padding: var(--sp-4) var(--sp-5);
}

.step-content p {
  margin-bottom: var(--sp-3);
  line-height: 1.6;
}

.step-content pre {
  background: var(--bg-muted);
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--radius-xs);
  font-family: var(--font-mono);
  font-size: 14px;
  overflow-x: auto;
  margin: var(--sp-3) 0;
}
```

### Tabbed Code Snippets

Multiple code examples behind tabs. Use when showing the same concept in different languages, configs, or layers.

```html
<div class="code-tabs" role="tablist" aria-label="Code examples">
  <div class="tab-bar">
    <button class="tab active" role="tab" aria-selected="true"
            id="tab-yaml" aria-controls="panel-yaml"
            onclick="showTab(this, 'yaml')">YAML</button>
    <button class="tab" role="tab" aria-selected="false"
            id="tab-route" aria-controls="panel-route"
            onclick="showTab(this, 'route')">Route</button>
    <button class="tab" role="tab" aria-selected="false"
            id="tab-client" aria-controls="panel-client"
            onclick="showTab(this, 'client')">Client</button>
  </div>
  <div class="tab-panel active" id="panel-yaml" role="tabpanel" aria-labelledby="tab-yaml">
    <pre><code>rate_limit:
  window: 60s
  max_requests: 100
  burst: 20</code></pre>
  </div>
  <div class="tab-panel" id="panel-route" role="tabpanel" aria-labelledby="tab-route" hidden>
    <pre><code>app.use('/api', rateLimiter({
  window: '60s',
  max: 100
}))</code></pre>
  </div>
  <div class="tab-panel" id="panel-client" role="tabpanel" aria-labelledby="tab-client" hidden>
    <pre><code>// Client retries on 429
if (res.status === 429) {
  await sleep(res.headers['retry-after'])
  return retry(req)
}</code></pre>
  </div>
</div>
```

```css
.code-tabs {
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  overflow: hidden;
  margin: var(--sp-4) 0;
}

.tab-bar {
  display: flex;
  background: var(--bg-muted);
  border-bottom: 1px solid var(--border-subtle);
}

.tab {
  all: unset;
  padding: var(--sp-2) var(--sp-4);
  font: var(--type-caption);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--text-muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.15s ease, border-color 0.15s ease;
}

.tab:hover {
  color: var(--text-primary);
}

.tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
  font-weight: 600;
}

.tab:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}

.tab-panel {
  display: none;
}

.tab-panel.active {
  display: block;
}

.tab-panel pre {
  margin: 0;
  padding: var(--sp-4);
  background: var(--bg-surface);
  font-family: var(--font-mono);
  font-size: 14px;
  line-height: 1.5;
  overflow-x: auto;
}
```

```js
function showTab(btn, panelId) {
  var container = btn.closest('.code-tabs');

  // Deactivate all tabs
  container.querySelectorAll('.tab').forEach(function(t) {
    t.classList.remove('active');
    t.setAttribute('aria-selected', 'false');
  });

  // Hide all panels
  container.querySelectorAll('.tab-panel').forEach(function(p) {
    p.classList.remove('active');
    p.setAttribute('hidden', '');
  });

  // Activate selected tab and panel
  btn.classList.add('active');
  btn.setAttribute('aria-selected', 'true');
  var panel = document.getElementById('panel-' + panelId);
  panel.classList.add('active');
  panel.removeAttribute('hidden');
}

// Keyboard navigation for tabs (arrow keys)
document.querySelectorAll('.tab-bar').forEach(function(bar) {
  bar.addEventListener('keydown', function(e) {
    var tabs = Array.from(bar.querySelectorAll('.tab'));
    var current = tabs.indexOf(document.activeElement);
    if (current < 0) return;

    var next = -1;
    if (e.key === 'ArrowRight') next = (current + 1) % tabs.length;
    if (e.key === 'ArrowLeft') next = (current - 1 + tabs.length) % tabs.length;

    if (next >= 0) {
      e.preventDefault();
      tabs[next].focus();
      tabs[next].click();
    }
  });
});
```

### Incident Timeline

Vertical timeline with timestamp, severity dot, and content. For incident reports, changelogs, and postmortems.

```html
<section aria-label="Incident timeline">
  <h2>Timeline</h2>
  <div class="timeline">
    <div class="timeline-event">
      <div class="timeline-time">14:32 UTC</div>
      <div class="timeline-dot critical" aria-label="Critical severity"></div>
      <div class="timeline-body">
        <h4>Alert fired: API latency > 2s</h4>
        <p>PagerDuty triggered. On-call engineer acknowledged within 3 minutes.</p>
        <pre class="log-excerpt">ERROR: connection pool exhausted (max=50, active=50, waiting=312)</pre>
      </div>
    </div>

    <div class="timeline-event">
      <div class="timeline-time">14:38 UTC</div>
      <div class="timeline-dot warning" aria-label="Warning severity"></div>
      <div class="timeline-body">
        <h4>Investigation started</h4>
        <p>Identified spike in database connections correlating with deploy at 14:28.</p>
      </div>
    </div>

    <div class="timeline-event">
      <div class="timeline-time">14:52 UTC</div>
      <div class="timeline-dot resolved" aria-label="Resolved"></div>
      <div class="timeline-body">
        <h4>Rollback deployed</h4>
        <p>Reverted to previous release. Connection pool returned to normal within 2 minutes.</p>
      </div>
    </div>

    <div class="timeline-event">
      <div class="timeline-time">15:10 UTC</div>
      <div class="timeline-dot resolved" aria-label="Resolved"></div>
      <div class="timeline-body">
        <h4>All clear</h4>
        <p>Latency back to baseline. Monitoring confirmed stable for 15 minutes.</p>
      </div>
    </div>
  </div>
</section>
```

```css
.timeline {
  position: relative;
  padding-left: 130px;
}

.timeline::before {
  content: '';
  position: absolute;
  left: 118px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--border-default);
}

.timeline-event {
  position: relative;
  margin-bottom: var(--sp-6);
}

.timeline-time {
  position: absolute;
  left: -130px;
  width: 108px;
  text-align: right;
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-muted);
  padding-top: 2px;
}

.timeline-dot {
  position: absolute;
  left: -18px;
  top: 4px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid var(--bg-page, var(--color-ivory, #FAF9F5));
}

.timeline-dot.critical { background: var(--color-danger); }
.timeline-dot.warning  { background: var(--color-warning); }
.timeline-dot.resolved { background: var(--color-success); }
.timeline-dot.info     { background: var(--color-info); }

.timeline-body h4 {
  font: var(--type-body);
  font-weight: 600;
  margin-bottom: var(--sp-1);
}

.timeline-body p {
  font: var(--type-small);
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: var(--sp-2);
}

.log-excerpt {
  background: var(--bg-muted);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-xs);
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--color-danger);
  overflow-x: auto;
  white-space: pre;
  margin-top: var(--sp-2);
}

/* Mobile: stack timestamp above content */
@media (max-width: 640px) {
  .timeline { padding-left: 24px; }
  .timeline::before { left: 5px; }
  .timeline-time {
    position: static;
    width: auto;
    text-align: left;
    margin-bottom: var(--sp-1);
  }
  .timeline-dot {
    left: -24px;
  }
}
```

---

## Interactive Elements for Reports

### Hover-Linked Glossary Terms

Inline terms that highlight on hover and link to a glossary sidebar or footnote.

```html
<p>The <a href="#term-hash" class="glossary-link">hash function</a> maps each key to a position on the
<a href="#term-ring" class="glossary-link">ring</a>, ensuring even distribution.</p>
```

```css
.glossary-link {
  color: var(--text-primary);
  text-decoration: none;
  border-bottom: 1px dashed var(--color-info);
  cursor: help;
  transition: background 0.15s ease;
}

.glossary-link:hover {
  background: color-mix(in srgb, var(--color-info) 10%, transparent);
}

.glossary-link:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: var(--radius-xs);
}
```

### FAQ Accordion

Uses native `<details>` elements. No JS required. Renders as a list of expandable questions.

```html
<section class="faq" aria-label="Frequently asked questions">
  <h2>FAQ</h2>
  <details>
    <summary>Why not just use Redis rate limiting?</summary>
    <div class="faq-answer">
      <p>Redis works for single-region deployments, but introduces a network hop
      for every request and a single point of failure. The local token bucket
      eliminates both issues at the cost of cross-node coordination.</p>
    </div>
  </details>
  <details>
    <summary>What happens when the limit is exceeded?</summary>
    <div class="faq-answer">
      <p>The client receives a <code>429 Too Many Requests</code> response with a
      <code>Retry-After</code> header indicating when to retry.</p>
    </div>
  </details>
</section>
```

```css
.faq details {
  border-bottom: 1px solid var(--border-subtle);
}

.faq details:last-child {
  border-bottom: none;
}

.faq summary {
  padding: var(--sp-3) 0;
  cursor: pointer;
  font: var(--type-body);
  font-weight: 500;
  color: var(--text-primary);
  list-style: none;
}

.faq summary::-webkit-details-marker { display: none; }

.faq summary::before {
  content: '▸ ';
  color: var(--text-muted);
  transition: transform 0.15s ease;
  display: inline-block;
}

.faq details[open] summary::before {
  content: '▾ ';
}

.faq summary:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: var(--radius-xs);
}

.faq-answer {
  padding: 0 0 var(--sp-4) var(--sp-4);
  color: var(--text-secondary);
  line-height: 1.6;
}

.faq-answer code {
  background: var(--bg-muted);
  padding: 2px 6px;
  border-radius: var(--radius-xs);
  font-family: var(--font-mono);
  font-size: 14px;
}
```

### Callout / Admonition Boxes

For warnings, notes, tips, and important information.

```html
<div class="callout callout-warning" role="note">
  <strong>Warning:</strong> This will drop all existing connections.
</div>

<div class="callout callout-info" role="note">
  <strong>Note:</strong> Rate limits reset at the start of each window.
</div>

<div class="callout callout-danger" role="alert">
  <strong>Breaking change:</strong> The <code>v1</code> endpoint is removed in this release.
</div>
```

```css
.callout {
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--radius-sm);
  font: var(--type-small);
  line-height: 1.6;
  margin: var(--sp-4) 0;
  border-left: 3px solid;
}

.callout strong {
  font-weight: 600;
}

.callout-info {
  background: color-mix(in srgb, var(--color-info) 8%, transparent);
  border-color: var(--color-info);
  color: var(--text-primary);
}

.callout-warning {
  background: color-mix(in srgb, var(--color-warning) 8%, transparent);
  border-color: var(--color-warning);
  color: var(--text-primary);
}

.callout-danger {
  background: color-mix(in srgb, var(--color-danger) 8%, transparent);
  border-color: var(--color-danger);
  color: var(--text-primary);
}

.callout-success {
  background: color-mix(in srgb, var(--color-success) 8%, transparent);
  border-color: var(--color-success);
  color: var(--text-primary);
}
```

### Inline Code and Code Blocks

```css
/* Inline code */
code {
  background: var(--bg-muted);
  padding: 2px 6px;
  border-radius: var(--radius-xs);
  font-family: var(--font-mono);
  font-size: 0.875em;
}

/* Code blocks */
pre {
  background: var(--bg-muted);
  padding: var(--sp-4);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 14px;
  line-height: 1.5;
  overflow-x: auto;
  margin: var(--sp-4) 0;
}

pre code {
  background: none;
  padding: 0;
  border-radius: 0;
  font-size: inherit;
}
```

---

## SVG Diagrams in Reports

### Flow Diagram (horizontal process)

```html
<svg viewBox="0 0 720 120" xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="Request flow: Client to Rate Limiter to API to Database">
  <style>
    .box { fill: var(--bg-surface, #FFF); stroke: var(--border-default, #D1CFC5); stroke-width: 1.5; rx: 10; }
    .box-accent { fill: color-mix(in srgb, var(--accent, #D97757) 10%, var(--bg-surface, #FFF)); stroke: var(--accent, #D97757); stroke-width: 1.5; rx: 10; }
    .arrow { stroke: var(--border-default, #D1CFC5); stroke-width: 1.5; fill: none; marker-end: url(#arrowhead); }
    .label { font: 12px var(--font-sans, system-ui, sans-serif); fill: var(--text-primary, #333); text-anchor: middle; }
    .sublabel { font: 11px var(--font-mono, monospace); fill: var(--text-muted, #888); text-anchor: middle; }
  </style>
  <defs>
    <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
      <path d="M0,0 L8,3 L0,6" fill="var(--border-default, #D1CFC5)"/>
    </marker>
  </defs>
  <rect class="box" x="10" y="30" width="120" height="60"/>
  <text class="label" x="70" y="58">Client</text>
  <text class="sublabel" x="70" y="74">HTTP</text>
  <line class="arrow" x1="130" y1="60" x2="190" y2="60"/>
  <rect class="box-accent" x="190" y="30" width="140" height="60"/>
  <text class="label" x="260" y="58">Rate Limiter</text>
  <text class="sublabel" x="260" y="74">token bucket</text>
  <line class="arrow" x1="330" y1="60" x2="390" y2="60"/>
  <rect class="box" x="390" y="30" width="120" height="60"/>
  <text class="label" x="450" y="58">API</text>
  <text class="sublabel" x="450" y="74">handler</text>
  <line class="arrow" x1="510" y1="60" x2="570" y2="60"/>
  <rect class="box" x="570" y="30" width="130" height="60"/>
  <text class="label" x="635" y="58">Database</text>
  <text class="sublabel" x="635" y="74">PostgreSQL</text>
</svg>
```

### Before/After Comparison

Side-by-side status indicators for reports showing improvement.

```html
<div class="comparison-row">
  <div class="comparison-before">
    <h4>Before</h4>
    <div class="stat-line">
      <span class="stat-label">p99 latency</span>
      <span class="stat-value danger">2.4s</span>
    </div>
    <div class="stat-line">
      <span class="stat-label">Error rate</span>
      <span class="stat-value danger">4.2%</span>
    </div>
  </div>
  <div class="comparison-arrow" aria-hidden="true">&#8594;</div>
  <div class="comparison-after">
    <h4>After</h4>
    <div class="stat-line">
      <span class="stat-label">p99 latency</span>
      <span class="stat-value success">180ms</span>
    </div>
    <div class="stat-line">
      <span class="stat-label">Error rate</span>
      <span class="stat-value success">0.1%</span>
    </div>
  </div>
</div>
```

```css
.comparison-row {
  display: flex;
  align-items: center;
  gap: var(--sp-5);
  margin: var(--sp-5) 0;
}

@media (max-width: 640px) {
  .comparison-row {
    flex-direction: column;
    gap: var(--sp-3);
  }
  .comparison-arrow {
    transform: rotate(90deg);
  }
}

.comparison-before,
.comparison-after {
  flex: 1;
  padding: var(--sp-4);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-subtle);
}

.comparison-before {
  background: color-mix(in srgb, var(--color-danger) 4%, var(--bg-surface));
}

.comparison-after {
  background: color-mix(in srgb, var(--color-success) 4%, var(--bg-surface));
}

.comparison-before h4,
.comparison-after h4 {
  font: var(--type-caption);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: var(--sp-3);
}

.comparison-arrow {
  font-size: 24px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.stat-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--sp-2) 0;
  border-bottom: 1px solid var(--border-subtle);
}

.stat-line:last-child {
  border-bottom: none;
}

.stat-label {
  font: var(--type-small);
  color: var(--text-secondary);
}

.stat-value {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 600;
}

.stat-value.success { color: var(--color-success); }
.stat-value.danger  { color: var(--color-danger); }
```

---

## Print Styles

Reports may be printed or saved as PDF. Include basic print overrides.

```css
@media print {
  body {
    background: white;
    color: black;
    font-size: 12pt;
  }

  .toc,
  .viz-controls,
  button {
    display: none;
  }

  details {
    display: block;
  }

  details[open] summary ~ * {
    display: block;
  }

  .timeline::before {
    background: #ccc;
  }

  .metric-card {
    border: 1px solid #ccc;
    break-inside: avoid;
  }

  a {
    color: inherit;
    text-decoration: none;
  }

  pre {
    white-space: pre-wrap;
    border: 1px solid #ccc;
  }
}
```

---

## Accessibility Requirements

| Requirement | Implementation |
|---|---|
| Heading hierarchy | h1 (title) > h2 (sections) > h3 (subsections), never skip levels |
| Section landmarks | Use `<section>`, `<nav>`, `<main>`, `<aside>` with `aria-label` |
| TOC navigation | TOC links are `<a href="#id">` pointing to sections with matching `id` |
| Tab panels | Proper `role="tablist"`, `role="tab"`, `role="tabpanel"`, `aria-selected`, `aria-controls` |
| Timeline | Severity dots include `aria-label`; timestamps are real text, not images |
| Metric trends | Trend indicators use `aria-label` to convey direction and magnitude |
| Code blocks | Use `<pre><code>` for code; `overflow-x: auto` for horizontal scroll |
| Callouts | Use `role="note"` or `role="alert"` (for breaking/danger only) |
| Focus visible | All interactive elements (links, tabs, summaries) have `:focus-visible` styles |
| Print | Reports remain readable when printed (no dark backgrounds, hidden nav) |

---

## Shape Selection Guidance

Use **report** shape when the user's request matches any of:

| Signal | Example Request |
|---|---|
| Status update | "Write a weekly status report" |
| Incident report | "Create a postmortem for the outage" |
| Feature explainer | "Explain how rate limiting works" |
| Concept tutorial | "Teach consistent hashing visually" |
| Research summary | "Summarize the findings from the research" |
| Changelog | "Show what changed in this release" |
| Meeting notes | "Format these meeting notes" |
| How-to guide | "Step-by-step guide for setting up X" |

Do NOT use report when:
- The user wants to tune/adjust parameters interactively (use **prototype**)
- The user wants to edit, reorder, or triage content (use **editor**)
- The user wants charts from raw data (use **data-viz**)
- The user wants to compare N approaches with grids (use **spec**)
