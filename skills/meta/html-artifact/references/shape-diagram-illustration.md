# Shape: Diagram & Illustration

Loaded when `detect-shape.py` returns `diagram`. For artifacts that visualize structure: architecture diagrams, flowcharts, sequence diagrams, data-flow diagrams, figure sheets for blog posts.

**Theme:** Dark Focus (default). SVG elements use CSS custom properties so they adapt to both dark and light modes via the standard theme toggle.

**Core principle:** Diagrams are STRUCTURAL. Every diagram communicates relationships between elements through spatial positioning, connection lines, and labeled nodes. Interactive features (click-to-expand, hover-to-highlight) reveal detail without cluttering the primary view.

---

## Layout Patterns

| Layout | Use When | Structure |
|---|---|---|
| Single diagram + legend | One flowchart or architecture diagram | Full-width SVG, legend below |
| Figure sheet (contact grid) | Multiple illustrations for a blog post | 2-3 column grid of labeled SVG panels |
| Sequence diagram | Message passing between actors | Full-width SVG with lifelines, vertical flow |
| Annotated diagram + callout panel | Complex system with numbered callouts | Diagram left (70%), callout list right (30%) |
| Stacked diagrams | Multiple related diagrams (before/after, layers) | Vertical stack with section headings |

### Single Diagram + Legend

For a standalone flowchart or architecture diagram with an interactive legend.

```html
<section class="diagram-section" aria-label="Architecture diagram">
  <h2>System Architecture</h2>
  <div class="diagram-container">
    <svg viewBox="0 0 720 320" xmlns="http://www.w3.org/2000/svg" role="img"
         aria-label="Architecture diagram showing service connections">
      <!-- SVG content (see SVG Patterns below) -->
    </svg>
  </div>
  <div class="diagram-legend" role="region" aria-label="Diagram legend">
    <div class="legend-item">
      <span class="legend-swatch" style="background: var(--color-info)"></span>
      <span class="legend-label">Frontend services</span>
    </div>
    <div class="legend-item">
      <span class="legend-swatch" style="background: var(--color-primary)"></span>
      <span class="legend-label">API layer</span>
    </div>
    <div class="legend-item">
      <span class="legend-swatch" style="background: var(--color-success)"></span>
      <span class="legend-label">Data stores</span>
    </div>
    <div class="legend-item">
      <span class="legend-swatch" style="background: var(--color-warning)"></span>
      <span class="legend-label">External services</span>
    </div>
  </div>
</section>
```

```css
.diagram-section {
  margin-bottom: var(--sp-9);
}

.diagram-section h2 {
  font: var(--type-h2);
  margin-bottom: var(--sp-6);
}

.diagram-container {
  background: var(--color-surface, var(--bg-surface));
  border: 1px solid var(--color-border, var(--border-subtle));
  border-radius: var(--radius-md);
  padding: var(--sp-5);
  overflow-x: auto;
}

.diagram-container svg {
  width: 100%;
  height: auto;
  min-width: 560px;
}

.diagram-legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-4);
  margin-top: var(--sp-4);
  padding: var(--sp-3) var(--sp-4);
  background: var(--color-surface, var(--bg-muted));
  border-radius: var(--radius-sm);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.legend-swatch {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: var(--radius-xs);
  flex-shrink: 0;
}

.legend-label {
  font: var(--type-small);
  color: var(--color-text-secondary, var(--text-secondary));
}
```

### Figure Sheet (Contact Grid)

For blog post illustrations: multiple SVG figures in a responsive grid.

```html
<section class="figure-sheet" aria-label="Figure illustrations">
  <h2>Key Concepts</h2>
  <div class="figure-grid">
    <figure class="figure-panel">
      <div class="figure-svg-wrap">
        <svg viewBox="0 0 320 240" xmlns="http://www.w3.org/2000/svg" role="img"
             aria-label="Figure 1: Request routing">
          <!-- SVG content -->
        </svg>
      </div>
      <figcaption>
        <span class="figure-number">Fig. 1</span>
        <span class="figure-title">Request Routing</span>
        <p class="figure-desc">Incoming requests are dispatched to handlers based on path prefix.</p>
      </figcaption>
      <button class="copy-svg-btn" data-target="fig-1" aria-label="Copy SVG for Figure 1">Copy SVG</button>
    </figure>

    <figure class="figure-panel">
      <div class="figure-svg-wrap">
        <svg viewBox="0 0 320 240" xmlns="http://www.w3.org/2000/svg" role="img"
             aria-label="Figure 2: Connection pooling">
          <!-- SVG content -->
        </svg>
      </div>
      <figcaption>
        <span class="figure-number">Fig. 2</span>
        <span class="figure-title">Connection Pooling</span>
        <p class="figure-desc">Connections are reused from a bounded pool to reduce overhead.</p>
      </figcaption>
      <button class="copy-svg-btn" data-target="fig-2" aria-label="Copy SVG for Figure 2">Copy SVG</button>
    </figure>

    <!-- Additional figures as needed -->
  </div>
</section>
```

```css
.figure-sheet {
  margin-bottom: var(--sp-9);
}

.figure-sheet h2 {
  font: var(--type-h2);
  margin-bottom: var(--sp-6);
}

.figure-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--sp-5);
}

.figure-panel {
  border: 1px solid var(--color-border, var(--border-subtle));
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--color-surface, var(--bg-surface));
  position: relative;
}

.figure-svg-wrap {
  padding: var(--sp-4);
  display: flex;
  align-items: center;
  justify-content: center;
}

.figure-svg-wrap svg {
  width: 100%;
  height: auto;
}

.figure-panel figcaption {
  padding: var(--sp-3) var(--sp-4);
  border-top: 1px solid var(--color-border, var(--border-subtle));
}

.figure-number {
  font: var(--type-caption);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-primary);
  margin-right: var(--sp-2);
}

.figure-title {
  font: var(--type-small);
  font-weight: 600;
  color: var(--color-text, var(--text-primary));
}

.figure-desc {
  font: var(--type-small);
  color: var(--color-text-secondary, var(--text-secondary));
  margin-top: var(--sp-1);
}

.copy-svg-btn {
  position: absolute;
  top: var(--sp-2);
  right: var(--sp-2);
  padding: var(--sp-1) var(--sp-3);
  font: var(--type-caption);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  background: var(--color-surface, var(--bg-muted));
  color: var(--color-text-secondary, var(--text-muted));
  border: 1px solid var(--color-border, var(--border-subtle));
  border-radius: var(--radius-sm);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.figure-panel:hover .copy-svg-btn,
.copy-svg-btn:focus-visible {
  opacity: 1;
}

.copy-svg-btn:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.copy-svg-btn.copied {
  color: var(--color-success);
  border-color: var(--color-success);
}

@media (max-width: 640px) {
  .figure-grid {
    grid-template-columns: 1fr;
  }
  .copy-svg-btn {
    opacity: 1;
  }
}
```

### Annotated Diagram + Callout Panel

Diagram with numbered callouts linked to a sidebar explanation panel.

```html
<section class="annotated-layout" aria-label="Annotated architecture diagram">
  <h2>Annotated Architecture</h2>
  <div class="annotated-grid">
    <div class="annotated-diagram">
      <div class="diagram-container">
        <svg viewBox="0 0 720 400" xmlns="http://www.w3.org/2000/svg" role="img"
             aria-label="Architecture with numbered callouts">
          <!-- Nodes, arrows, plus callout circles -->
          <circle class="callout-dot" cx="150" cy="100" r="10" data-callout="1"/>
          <text x="150" y="104" text-anchor="middle" font-size="11" font-weight="700"
                fill="var(--color-bg, #1a1a19)" style="pointer-events:none">1</text>
          <circle class="callout-dot" cx="400" cy="200" r="10" data-callout="2"/>
          <text x="400" y="204" text-anchor="middle" font-size="11" font-weight="700"
                fill="var(--color-bg, #1a1a19)" style="pointer-events:none">2</text>
          <!-- More callouts... -->
        </svg>
      </div>
    </div>
    <aside class="callout-panel" aria-label="Diagram callouts">
      <h3>Callouts</h3>
      <div class="callout-entry" data-callout="1">
        <span class="callout-number">1</span>
        <div>
          <h4>Load Balancer</h4>
          <p>Distributes requests across API instances using round-robin with health checks.</p>
        </div>
      </div>
      <div class="callout-entry" data-callout="2">
        <span class="callout-number">2</span>
        <div>
          <h4>Cache Layer</h4>
          <p>Redis cache with 60s TTL reduces database load for read-heavy endpoints.</p>
        </div>
      </div>
      <!-- More entries... -->
    </aside>
  </div>
</section>
```

```css
.annotated-layout {
  margin-bottom: var(--sp-9);
}

.annotated-layout h2 {
  font: var(--type-h2);
  margin-bottom: var(--sp-6);
}

.annotated-grid {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: var(--sp-6);
  align-items: start;
}

@media (max-width: 768px) {
  .annotated-grid {
    grid-template-columns: 1fr;
  }
}

.callout-panel {
  position: sticky;
  top: var(--sp-5);
  padding: var(--sp-4);
  background: var(--color-surface, var(--bg-muted));
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border, var(--border-subtle));
}

.callout-panel h3 {
  font: var(--type-caption);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-secondary, var(--text-muted));
  margin-bottom: var(--sp-4);
}

.callout-entry {
  display: flex;
  gap: var(--sp-3);
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--color-border, var(--border-subtle));
  cursor: pointer;
  transition: background 0.15s ease;
  border-radius: var(--radius-xs);
}

.callout-entry:last-child {
  border-bottom: none;
}

.callout-entry:hover,
.callout-entry.active {
  background: color-mix(in srgb, var(--color-primary) 8%, transparent);
}

.callout-entry:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.callout-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-primary);
  color: var(--color-bg, #1a1a19);
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.callout-entry h4 {
  font: var(--type-small);
  font-weight: 600;
  color: var(--color-text, var(--text-primary));
}

.callout-entry p {
  font: var(--type-small);
  color: var(--color-text-secondary, var(--text-secondary));
  margin-top: var(--sp-1);
}

/* SVG callout dots */
.callout-dot {
  fill: var(--color-primary);
  cursor: pointer;
  transition: r 0.15s ease;
}

.callout-dot:hover,
.callout-dot.active {
  r: 13;
}
```

---

## SVG Patterns

### SVG Construction Rules

All SVGs are inline (no external files). Use CSS custom properties for colors so diagrams adapt to dark/light themes.

| Element | Pattern | Notes |
|---|---|---|
| viewBox | `0 0 720 320` (standard) or `0 0 720 480` (tall) | Fixed coordinate space; CSS scales to container |
| Rendering | Flat, no gradients | Clean, technical aesthetic |
| Stroke width | `1.5` for boxes, `2` for emphasis | Consistent line weight |
| Corner radius | `rx="10"` | Matches `--radius-md` |
| Label font | `font-size="11"`, `font-family="var(--font-mono)"` | Monospace for technical labels |
| Annotation font | `font-size="12"`, `font-family="var(--font-sans)"` | Sans-serif for descriptions |
| Node fill | `color-mix(in srgb, <color> 10%, var(--color-bg, #1a1a19))` | Tinted background matching layer color |
| Node stroke | Layer semantic color at full strength | `var(--color-info)`, `var(--color-primary)`, etc. |
| Sync arrow | Solid line + `marker-end` | `var(--color-text-secondary)` stroke |
| Async arrow | Dashed `stroke-dasharray="6 4"` | `var(--color-info)` stroke |
| Grouping box | `<rect>` with dashed stroke, low-opacity fill | Groups related nodes |
| Accessibility | `role="img"` + `aria-label` on every `<svg>` | Descriptive label for screen readers |

### Arrowhead Marker Definition

Include in every diagram's `<defs>` block.

```html
<defs>
  <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3"
          orient="auto-start-auto">
    <path d="M0,0 L8,3 L0,6 z" fill="var(--color-text-secondary, #87867F)"/>
  </marker>
  <marker id="arrowhead-accent" markerWidth="8" markerHeight="6" refX="8" refY="3"
          orient="auto-start-auto">
    <path d="M0,0 L8,3 L0,6 z" fill="var(--color-primary, #D97757)"/>
  </marker>
  <marker id="arrowhead-async" markerWidth="8" markerHeight="6" refX="8" refY="3"
          orient="auto-start-auto">
    <path d="M0,0 L8,3 L0,6 z" fill="var(--color-info, #5C7CA3)"/>
  </marker>
</defs>
```

### Flowchart Pattern

Horizontal process flow with labeled nodes and arrows.

```html
<svg viewBox="0 0 720 160" xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="Flowchart: request lifecycle from ingress to response">
  <defs>
    <marker id="arrow-flow" markerWidth="8" markerHeight="6" refX="8" refY="3"
            orient="auto-start-auto">
      <path d="M0,0 L8,3 L0,6 z" fill="var(--color-text-secondary, #87867F)"/>
    </marker>
  </defs>

  <!-- Node 1 -->
  <rect x="20" y="50" width="130" height="60" rx="10"
        fill="color-mix(in srgb, var(--color-info) 10%, var(--color-bg, #1a1a19))"
        stroke="var(--color-info)" stroke-width="1.5"/>
  <text x="85" y="76" text-anchor="middle"
        font-family="var(--font-mono)" font-size="11" font-weight="600"
        fill="var(--color-info)">INGRESS</text>
  <text x="85" y="94" text-anchor="middle"
        font-family="var(--font-mono)" font-size="11"
        fill="var(--color-text-secondary, #87867F)">nginx proxy</text>

  <!-- Arrow 1->2 -->
  <line x1="150" y1="80" x2="200" y2="80"
        stroke="var(--color-text-secondary, #87867F)" stroke-width="1.5"
        marker-end="url(#arrow-flow)"/>

  <!-- Node 2 -->
  <rect x="200" y="50" width="130" height="60" rx="10"
        fill="color-mix(in srgb, var(--color-primary) 10%, var(--color-bg, #1a1a19))"
        stroke="var(--color-primary)" stroke-width="1.5"/>
  <text x="265" y="76" text-anchor="middle"
        font-family="var(--font-mono)" font-size="11" font-weight="600"
        fill="var(--color-primary)">AUTH</text>
  <text x="265" y="94" text-anchor="middle"
        font-family="var(--font-mono)" font-size="11"
        fill="var(--color-text-secondary, #87867F)">JWT validate</text>

  <!-- Arrow 2->3 -->
  <line x1="330" y1="80" x2="380" y2="80"
        stroke="var(--color-text-secondary, #87867F)" stroke-width="1.5"
        marker-end="url(#arrow-flow)"/>

  <!-- Node 3 -->
  <rect x="380" y="50" width="130" height="60" rx="10"
        fill="color-mix(in srgb, var(--color-warning) 10%, var(--color-bg, #1a1a19))"
        stroke="var(--color-warning)" stroke-width="1.5"/>
  <text x="445" y="76" text-anchor="middle"
        font-family="var(--font-mono)" font-size="11" font-weight="600"
        fill="var(--color-warning)">HANDLER</text>
  <text x="445" y="94" text-anchor="middle"
        font-family="var(--font-mono)" font-size="11"
        fill="var(--color-text-secondary, #87867F)">business logic</text>

  <!-- Arrow 3->4 -->
  <line x1="510" y1="80" x2="560" y2="80"
        stroke="var(--color-text-secondary, #87867F)" stroke-width="1.5"
        marker-end="url(#arrow-flow)"/>

  <!-- Node 4 -->
  <rect x="560" y="50" width="140" height="60" rx="10"
        fill="color-mix(in srgb, var(--color-success) 10%, var(--color-bg, #1a1a19))"
        stroke="var(--color-success)" stroke-width="1.5"/>
  <text x="630" y="76" text-anchor="middle"
        font-family="var(--font-mono)" font-size="11" font-weight="600"
        fill="var(--color-success)">RESPONSE</text>
  <text x="630" y="94" text-anchor="middle"
        font-family="var(--font-mono)" font-size="11"
        fill="var(--color-text-secondary, #87867F)">JSON serialize</text>
</svg>
```

### Architecture Diagram Pattern

Multi-layer architecture with grouping boxes and labeled connections.

```html
<svg viewBox="0 0 720 480" xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="Architecture diagram with frontend, API, and data layers">
  <defs>
    <marker id="arrow-arch" markerWidth="8" markerHeight="6" refX="8" refY="3"
            orient="auto-start-auto">
      <path d="M0,0 L8,3 L0,6 z" fill="var(--color-text-secondary, #87867F)"/>
    </marker>
  </defs>

  <!-- Layer group: Frontend -->
  <rect x="20" y="20" width="680" height="100" rx="10"
        fill="none" stroke="var(--color-info)" stroke-width="1" stroke-dasharray="6 4"
        opacity="0.4"/>
  <text x="36" y="42" font-family="var(--font-mono)" font-size="10" font-weight="600"
        fill="var(--color-info)" text-transform="uppercase" letter-spacing="1">FRONTEND</text>

  <!-- Nodes inside Frontend group -->
  <rect x="60" y="55" width="120" height="50" rx="10"
        fill="color-mix(in srgb, var(--color-info) 10%, var(--color-bg, #1a1a19))"
        stroke="var(--color-info)" stroke-width="1.5"/>
  <text x="120" y="84" text-anchor="middle"
        font-family="var(--font-mono)" font-size="11" fill="var(--color-info)">Web App</text>

  <rect x="220" y="55" width="120" height="50" rx="10"
        fill="color-mix(in srgb, var(--color-info) 10%, var(--color-bg, #1a1a19))"
        stroke="var(--color-info)" stroke-width="1.5"/>
  <text x="280" y="84" text-anchor="middle"
        font-family="var(--font-mono)" font-size="11" fill="var(--color-info)">Mobile App</text>

  <!-- Layer group: API -->
  <rect x="20" y="160" width="680" height="100" rx="10"
        fill="none" stroke="var(--color-primary)" stroke-width="1" stroke-dasharray="6 4"
        opacity="0.4"/>
  <text x="36" y="182" font-family="var(--font-mono)" font-size="10" font-weight="600"
        fill="var(--color-primary)">API LAYER</text>

  <rect x="140" y="195" width="140" height="50" rx="10"
        fill="color-mix(in srgb, var(--color-primary) 10%, var(--color-bg, #1a1a19))"
        stroke="var(--color-primary)" stroke-width="1.5"/>
  <text x="210" y="224" text-anchor="middle"
        font-family="var(--font-mono)" font-size="11" fill="var(--color-primary)">API Gateway</text>

  <!-- Arrows: Frontend -> API -->
  <line x1="120" y1="105" x2="190" y2="195"
        stroke="var(--color-text-secondary, #87867F)" stroke-width="1.5"
        marker-end="url(#arrow-arch)"/>
  <line x1="280" y1="105" x2="230" y2="195"
        stroke="var(--color-text-secondary, #87867F)" stroke-width="1.5"
        marker-end="url(#arrow-arch)"/>

  <!-- Layer group: Data -->
  <rect x="20" y="300" width="680" height="100" rx="10"
        fill="none" stroke="var(--color-success)" stroke-width="1" stroke-dasharray="6 4"
        opacity="0.4"/>
  <text x="36" y="322" font-family="var(--font-mono)" font-size="10" font-weight="600"
        fill="var(--color-success)">DATA LAYER</text>

  <rect x="80" y="335" width="120" height="50" rx="10"
        fill="color-mix(in srgb, var(--color-success) 10%, var(--color-bg, #1a1a19))"
        stroke="var(--color-success)" stroke-width="1.5"/>
  <text x="140" y="364" text-anchor="middle"
        font-family="var(--font-mono)" font-size="11" fill="var(--color-success)">PostgreSQL</text>

  <rect x="260" y="335" width="120" height="50" rx="10"
        fill="color-mix(in srgb, var(--color-success) 10%, var(--color-bg, #1a1a19))"
        stroke="var(--color-success)" stroke-width="1.5"/>
  <text x="320" y="364" text-anchor="middle"
        font-family="var(--font-mono)" font-size="11" fill="var(--color-success)">Redis</text>

  <!-- Arrows: API -> Data -->
  <line x1="190" y1="245" x2="150" y2="335"
        stroke="var(--color-text-secondary, #87867F)" stroke-width="1.5"
        marker-end="url(#arrow-arch)"/>
  <line x1="230" y1="245" x2="310" y2="335"
        stroke="var(--color-text-secondary, #87867F)" stroke-width="1.5"
        marker-end="url(#arrow-arch)"/>
</svg>
```

### Sequence Diagram Pattern

Vertical sequence diagram with lifelines, messages, and activation bars.

```html
<svg viewBox="0 0 720 480" xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="Sequence diagram: login flow between Client, API, and Database">
  <defs>
    <marker id="arrow-seq" markerWidth="8" markerHeight="6" refX="8" refY="3"
            orient="auto-start-auto">
      <path d="M0,0 L8,3 L0,6 z" fill="var(--color-text-secondary, #87867F)"/>
    </marker>
    <marker id="arrow-seq-return" markerWidth="8" markerHeight="6" refX="8" refY="3"
            orient="auto-start-auto">
      <path d="M0,0 L8,3 L0,6 z" fill="var(--color-info, #5C7CA3)"/>
    </marker>
  </defs>

  <!-- Actor headers -->
  <rect x="80" y="20" width="100" height="36" rx="6"
        fill="color-mix(in srgb, var(--color-info) 10%, var(--color-bg, #1a1a19))"
        stroke="var(--color-info)" stroke-width="1.5"/>
  <text x="130" y="43" text-anchor="middle"
        font-family="var(--font-mono)" font-size="12" font-weight="600"
        fill="var(--color-info)">Client</text>

  <rect x="310" y="20" width="100" height="36" rx="6"
        fill="color-mix(in srgb, var(--color-primary) 10%, var(--color-bg, #1a1a19))"
        stroke="var(--color-primary)" stroke-width="1.5"/>
  <text x="360" y="43" text-anchor="middle"
        font-family="var(--font-mono)" font-size="12" font-weight="600"
        fill="var(--color-primary)">API</text>

  <rect x="540" y="20" width="100" height="36" rx="6"
        fill="color-mix(in srgb, var(--color-success) 10%, var(--color-bg, #1a1a19))"
        stroke="var(--color-success)" stroke-width="1.5"/>
  <text x="590" y="43" text-anchor="middle"
        font-family="var(--font-mono)" font-size="12" font-weight="600"
        fill="var(--color-success)">Database</text>

  <!-- Lifelines -->
  <line x1="130" y1="56" x2="130" y2="440"
        stroke="var(--color-border, var(--border-subtle, #3D3D3A))" stroke-width="1"
        stroke-dasharray="4 4"/>
  <line x1="360" y1="56" x2="360" y2="440"
        stroke="var(--color-border, var(--border-subtle, #3D3D3A))" stroke-width="1"
        stroke-dasharray="4 4"/>
  <line x1="590" y1="56" x2="590" y2="440"
        stroke="var(--color-border, var(--border-subtle, #3D3D3A))" stroke-width="1"
        stroke-dasharray="4 4"/>

  <!-- Activation bar on API (during processing) -->
  <rect x="354" y="100" width="12" height="160" rx="2"
        fill="color-mix(in srgb, var(--color-primary) 20%, var(--color-bg, #1a1a19))"
        stroke="var(--color-primary)" stroke-width="1"/>

  <!-- Message 1: Client -> API (request) -->
  <line x1="130" y1="110" x2="352" y2="110"
        stroke="var(--color-text-secondary, #87867F)" stroke-width="1.5"
        marker-end="url(#arrow-seq)"/>
  <text x="240" y="102" text-anchor="middle"
        font-family="var(--font-mono)" font-size="10"
        fill="var(--color-text-secondary, #87867F)">POST /login</text>

  <!-- Message 2: API -> Database (query) -->
  <line x1="366" y1="160" x2="588" y2="160"
        stroke="var(--color-text-secondary, #87867F)" stroke-width="1.5"
        marker-end="url(#arrow-seq)"/>
  <text x="477" y="152" text-anchor="middle"
        font-family="var(--font-mono)" font-size="10"
        fill="var(--color-text-secondary, #87867F)">SELECT user</text>

  <!-- Message 3: Database -> API (return, dashed) -->
  <line x1="588" y1="200" x2="366" y2="200"
        stroke="var(--color-info)" stroke-width="1.5" stroke-dasharray="6 4"
        marker-end="url(#arrow-seq-return)"/>
  <text x="477" y="192" text-anchor="middle"
        font-family="var(--font-mono)" font-size="10"
        fill="var(--color-info)">user record</text>

  <!-- Message 4: API -> Client (response, dashed) -->
  <line x1="352" y1="250" x2="130" y2="250"
        stroke="var(--color-info)" stroke-width="1.5" stroke-dasharray="6 4"
        marker-end="url(#arrow-seq-return)"/>
  <text x="240" y="242" text-anchor="middle"
        font-family="var(--font-mono)" font-size="10"
        fill="var(--color-info)">200 + JWT token</text>
</svg>
```

---

## Interactive Features

### Click-to-Expand Node Details

Clicking an SVG node highlights it and displays detail information below the diagram.

```html
<div class="diagram-container">
  <svg viewBox="0 0 720 320" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="Interactive architecture diagram">
    <!-- Nodes with data-node attribute -->
    <g class="diagram-node" data-node="api" tabindex="0" role="button"
       aria-label="API Gateway - click for details">
      <rect x="280" y="100" width="160" height="60" rx="10"
            fill="color-mix(in srgb, var(--color-primary) 10%, var(--color-bg, #1a1a19))"
            stroke="var(--color-primary)" stroke-width="1.5"/>
      <text x="360" y="126" text-anchor="middle"
            font-family="var(--font-mono)" font-size="11" font-weight="600"
            fill="var(--color-primary)">API GATEWAY</text>
      <text x="360" y="144" text-anchor="middle"
            font-family="var(--font-mono)" font-size="11"
            fill="var(--color-text-secondary, #87867F)">rate limit + auth</text>
    </g>
    <!-- More nodes... -->
  </svg>
</div>

<div class="node-detail-panel" id="node-detail" role="region" aria-live="polite" hidden>
  <h4 id="node-detail-title"></h4>
  <p id="node-detail-desc"></p>
</div>
```

```css
.diagram-node {
  cursor: pointer;
  outline: none;
}

.diagram-node rect {
  transition: stroke-width 0.15s ease;
}

.diagram-node:hover rect,
.diagram-node:focus-visible rect,
.diagram-node.active rect {
  stroke-width: 2.5;
}

.diagram-node:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.node-detail-panel {
  margin-top: var(--sp-4);
  padding: var(--sp-4) var(--sp-5);
  background: var(--color-surface, var(--bg-muted));
  border-left: 3px solid var(--color-primary);
  border-radius: var(--radius-sm);
}

.node-detail-panel[hidden] {
  display: none;
}

.node-detail-panel h4 {
  font: var(--type-body);
  font-weight: 600;
  margin-bottom: var(--sp-2);
}

.node-detail-panel p {
  font: var(--type-small);
  color: var(--color-text-secondary, var(--text-secondary));
  line-height: 1.6;
}
```

```js
(function() {
  var nodeData = {
    "api": {
      title: "API Gateway",
      desc: "Handles rate limiting (token bucket, 100 req/min), JWT validation, and request routing. Deployed as a Go service behind nginx."
    },
    "db": {
      title: "PostgreSQL",
      desc: "Primary data store. Connection pool max 50. Read replicas for reporting queries."
    }
    // Add entries for each data-node value
  };

  var detailPanel = document.getElementById('node-detail');
  var detailTitle = document.getElementById('node-detail-title');
  var detailDesc = document.getElementById('node-detail-desc');
  var nodes = document.querySelectorAll('.diagram-node');

  nodes.forEach(function(node) {
    node.addEventListener('click', function() {
      var key = node.getAttribute('data-node');
      var info = nodeData[key];
      if (!info) return;

      // Deactivate all nodes
      nodes.forEach(function(n) { n.classList.remove('active'); });
      node.classList.add('active');

      // Show detail
      detailTitle.textContent = info.title;
      detailDesc.textContent = info.desc;
      detailPanel.removeAttribute('hidden');
    });

    // Keyboard: Enter/Space activates
    node.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        node.click();
      }
    });
  });
})();
```

### Hover-to-Highlight Connected Paths

Hovering a node dims unrelated elements and highlights connected arrows.

```css
.diagram-container svg.has-hover .diagram-node:not(.highlighted),
.diagram-container svg.has-hover line:not(.highlighted) {
  opacity: 0.25;
  transition: opacity 0.2s ease;
}

.diagram-container svg .diagram-node,
.diagram-container svg line {
  transition: opacity 0.2s ease;
}
```

```js
(function() {
  var svg = document.querySelector('.diagram-container svg');
  if (!svg) return;

  // Define connections: node -> list of arrow IDs connected to it
  var connections = {
    "api": ["arrow-1-2", "arrow-2-3"],
    "db": ["arrow-2-3"]
  };

  var nodes = svg.querySelectorAll('.diagram-node');

  nodes.forEach(function(node) {
    node.addEventListener('mouseenter', function() {
      var key = node.getAttribute('data-node');
      var linked = connections[key] || [];

      svg.classList.add('has-hover');
      node.classList.add('highlighted');

      linked.forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.classList.add('highlighted');
      });
    });

    node.addEventListener('mouseleave', function() {
      svg.classList.remove('has-hover');
      svg.querySelectorAll('.highlighted').forEach(function(el) {
        el.classList.remove('highlighted');
      });
    });
  });
})();
```

### Copy SVG Button

Copies the SVG markup of a specific diagram for reuse in other documents.

```js
(function() {
  document.querySelectorAll('.copy-svg-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var panel = btn.closest('.figure-panel') || btn.closest('.diagram-section');
      var svg = panel ? panel.querySelector('svg') : null;
      if (!svg) return;

      var svgString = new XMLSerializer().serializeToString(svg);

      navigator.clipboard.writeText(svgString).then(function() {
        btn.textContent = 'Copied';
        btn.classList.add('copied');
        setTimeout(function() {
          btn.textContent = 'Copy SVG';
          btn.classList.remove('copied');
        }, 2000);
      }).catch(function() {
        // Fallback: select text area
        var ta = document.createElement('textarea');
        ta.value = svgString;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        btn.textContent = 'Copied';
        btn.classList.add('copied');
        setTimeout(function() {
          btn.textContent = 'Copy SVG';
          btn.classList.remove('copied');
        }, 2000);
      });
    });
  });
})();
```

### Callout Panel Interaction

Clicking a callout entry highlights the corresponding numbered dot in the SVG.

```js
(function() {
  var entries = document.querySelectorAll('.callout-entry');
  var dots = document.querySelectorAll('.callout-dot');

  function activateCallout(num) {
    entries.forEach(function(e) { e.classList.remove('active'); });
    dots.forEach(function(d) { d.classList.remove('active'); });

    var entry = document.querySelector('.callout-entry[data-callout="' + num + '"]');
    var dot = document.querySelector('.callout-dot[data-callout="' + num + '"]');
    if (entry) entry.classList.add('active');
    if (dot) dot.classList.add('active');
  }

  entries.forEach(function(entry) {
    entry.setAttribute('tabindex', '0');
    entry.addEventListener('click', function() {
      activateCallout(entry.getAttribute('data-callout'));
    });
    entry.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        activateCallout(entry.getAttribute('data-callout'));
      }
    });
  });

  dots.forEach(function(dot) {
    dot.addEventListener('click', function() {
      activateCallout(dot.getAttribute('data-callout'));
    });
  });
})();
```

---

## Print Styles

Diagrams may be printed or saved as PDF. SVGs print well natively; hide interactive controls.

```css
@media print {
  body {
    background: white;
    color: black;
    font-size: 12pt;
  }

  .copy-svg-btn,
  .node-detail-panel,
  .diagram-legend button {
    display: none;
  }

  .diagram-container {
    border: 1px solid #ccc;
    break-inside: avoid;
  }

  .figure-panel {
    break-inside: avoid;
  }

  .callout-panel {
    position: static;
  }

  .annotated-grid {
    grid-template-columns: 1fr 240px;
  }
}
```

---

## Accessibility Requirements

| Requirement | Implementation |
|---|---|
| SVG labels | Every `<svg>` has `role="img"` and descriptive `aria-label` |
| Interactive nodes | Use `tabindex="0"`, `role="button"`, `aria-label` on clickable `<g>` groups |
| Keyboard activation | Enter/Space on focused nodes triggers click action |
| Focus indicators | `:focus-visible` outlines on all interactive SVG elements |
| Color not sole indicator | All nodes have text labels in addition to color coding |
| Legend | Always include a legend mapping colors to categories |
| Callout text | Numbered callouts have matching text descriptions in the callout panel |
| Reduced motion | `prefers-reduced-motion` disables SVG transitions |
| Copy button feedback | "Copied" text change announces state to screen readers |
| Detail panel | `aria-live="polite"` on node detail panel for dynamic content updates |

---

## Shape Selection Guidance

Use **diagram** shape when the user's request matches any of:

| Signal | Example Request |
|---|---|
| Architecture diagram | "Show the system architecture" |
| Flowchart | "Draw a flowchart for the deploy process" |
| Sequence diagram | "Sequence diagram for the login flow" |
| Data-flow diagram | "Show how data flows through the pipeline" |
| Figure sheet | "Create illustrations for the blog post" |
| Dependency map | "Map the dependency graph for this module" |
| Annotated diagram | "Annotate the infrastructure diagram with callouts" |
| Node graph | "Visualize the service mesh topology" |

Do NOT use diagram when:
- The user wants charts from numerical data (use **data-viz**)
- The user wants to compare N options side by side (use **spec**)
- The user wants a written report with inline diagrams (use **report** -- it includes basic SVG support)
- The user wants to interactively adjust visual parameters (use **prototype**)
