# Shape: Diagram & Illustration

> **Shape**: diagram | **Signal words**: diagram, flowchart, architecture, sequence, SVG, illustrate, figure
> CSS layout classes: `templates/shapes/diagram.css` (injected by assemble-template.py)
> Components: `copy-button`, `theme-toggle`

Diagrams are STRUCTURAL. They communicate relationships through spatial layout, connection lines, and labeled nodes. The reader's eye traces edges; the writer's job is to make those edges legible. Interactive features (click-to-expand, hover-to-highlight) reveal detail without crowding the primary view.

---

## Layout Description

Diagram artifacts come in two flavors:

1. **Single diagram** — one full-width SVG inside a `.diagram-container`, optional `.diagram-legend` below. For one architecture, one flowchart, one sequence.
2. **Figure sheet** — a `.figure-grid` (auto-fit, 280px min) of `.figure-panel`s. Each panel is a labeled SVG with a figure number, title, and copy-SVG button. Use for blog companions, multi-figure explainers.

Annotated variants overlay numbered `.callout-dot`s on a base diagram with a paired list of callouts beside or beneath. Sequence diagrams use a vertical layout: actor headers across the top, dashed lifelines descending, message arrows between.

---

## Canonical Markup Order (load-bearing rule)

| Order | Region | Purpose |
|---|---|---|
| 1 | `<header>` (optional) | Title + brief context |
| 2 | `.diagram-section` per diagram | Holds the SVG |
| 3 | `.diagram-container` wrapping the `<svg>` | Provides border, padding, and horizontal-scroll fallback |
| 4 | `.diagram-legend` BELOW the diagram | Maps colors / line styles to meaning |
| 5 | `.node-detail-panel` (optional) | Detail of a clicked node, `aria-live="polite"` |

For figure sheets: replace step 2 with `.figure-grid` containing `.figure-panel` items in source order matching figure numbers.

Why legend below: readers look at the diagram first, hit confusion, then look down for the legend. Legend above forces them to memorize the key before they know what they're looking for.

### Skeleton (single diagram)

```html
<body data-shape="diagram" data-theme="birchline">
  <header>
    <h1>Auth flow — token cookie migration</h1>
  </header>
  <main>
    <section class="diagram-section">
      <h2>Request lifecycle</h2>
      <div class="diagram-container">
        <svg viewBox="0 0 720 320" role="img"
             aria-label="Auth request lifecycle: client to API gateway to auth service to database">
          <!-- nodes, arrows, labels -->
        </svg>
      </div>
      <ul class="diagram-legend">
        <li><span class="legend-swatch" style="background: var(--color-info)"></span> Frontend</li>
        <li><span class="legend-swatch" style="background: var(--accent)"></span> API</li>
        <li><span class="legend-swatch" style="background: var(--color-success)"></span> Database</li>
      </ul>
      <div class="node-detail-panel" hidden aria-live="polite"></div>
    </section>
  </main>
</body>
```

CSS lives in `templates/shapes/diagram.css` — do not redefine `.diagram-container`, `.diagram-legend`, `.figure-*`, `.diagram-node`, `.callout-dot`, `.node-detail-panel` inline.

---

## SVG Construction Rules

| Element | Pattern | Notes |
|---|---|---|
| `viewBox` | `0 0 720 320` (wide), `0 0 720 480` (tall), `0 0 600 600` (square) | Fixed coords; CSS scales |
| Stroke weight | `1.5` for boxes, `2` for emphasized arrows | Consistent visual rhythm |
| Corner radius | `rx="10"` on rectangles | Matches `--radius-md` |
| Node fill | `color-mix(in srgb, <semantic-color> 10%, var(--bg-page))` | Tinted background |
| Node stroke | Full semantic color | `var(--color-info)`, `var(--accent)`, `var(--color-success)` |
| Label font | `font-size="11" font-family="var(--font-mono, monospace)"` | Mono for technical |
| Sync arrow | Solid line + `marker-end="url(#arrow)"` | Gray stroke `var(--text-muted)` |
| Async arrow | `stroke-dasharray="6 4"` | Info / blue stroke |
| Grouping box | Dashed stroke, low-opacity fill | Wraps related nodes |
| External actor | Different stroke style (dashed border) | Marks "outside the system" |
| Labels in mono | `font-family="var(--font-mono)"` | Improves alignment of code-shaped labels |
| Accessibility | `role="img"` + `aria-label` | Required on every `<svg>` |

Layer color convention (used across the toolkit so diagrams compose visually):

| Layer | Color token | Examples |
|---|---|---|
| Frontend / client | `var(--color-info)` | Browser, mobile app |
| API / service | `var(--accent)` | Gateway, auth service |
| Database / state | `var(--color-success)` | Postgres, Redis |
| External / 3rd party | `var(--color-warning)` | Stripe, Auth0, S3 |

---

## Section Types (worked examples)

### Single horizontal flow

```html
<svg viewBox="0 0 720 200" role="img"
     aria-label="Request flow: client to rate limiter to API to database">
  <defs>
    <marker id="arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
      <path d="M0,0 L8,3 L0,6" fill="var(--text-muted)"/>
    </marker>
  </defs>
  <rect x="20"  y="80" width="120" height="60" rx="10"
        fill="color-mix(in srgb, var(--color-info) 10%, var(--bg-page))"
        stroke="var(--color-info)" stroke-width="1.5"/>
  <text x="80" y="115" text-anchor="middle" font-size="13">Client</text>
  <line x1="140" y1="110" x2="200" y2="110"
        stroke="var(--text-muted)" stroke-width="1.5" marker-end="url(#arrow)"/>
  <rect x="200" y="80" width="140" height="60" rx="10"
        fill="color-mix(in srgb, var(--accent) 10%, var(--bg-page))"
        stroke="var(--accent)" stroke-width="1.5"/>
  <text x="270" y="115" text-anchor="middle" font-size="13">Rate Limiter</text>
  <!-- continue chain -->
</svg>
```

Use for: data flows, request lifecycles, pipelines. Node spacing ~60-80px between blocks.

### Annotated diagram with callouts

```html
<div class="diagram-container">
  <svg viewBox="0 0 720 320" role="img" aria-label="System overview with numbered callouts">
    <!-- base diagram nodes and arrows -->
    <circle class="callout-dot" cx="180" cy="120" r="10" tabindex="0"
            role="button" aria-label="Callout 1: Connection pool"/>
    <text x="180" y="124" text-anchor="middle" font-size="11" fill="white" pointer-events="none">1</text>
    <circle class="callout-dot" cx="420" cy="200" r="10" tabindex="0"
            role="button" aria-label="Callout 2: Read replica fallback"/>
    <text x="420" y="204" text-anchor="middle" font-size="11" fill="white" pointer-events="none">2</text>
  </svg>
</div>
<ol class="callout-list">
  <li id="callout-1"><strong>Connection pool</strong> — sized for peak burst, not average load.</li>
  <li id="callout-2"><strong>Read replica fallback</strong> — primary failure trips read traffic to replica within 200ms.</li>
</ol>
```

Use for: complex diagrams where labels would clutter the visual. Each `.callout-dot` is keyboard-focusable; clicking highlights its matching list entry.

### Figure sheet panel

```html
<figure class="figure-panel">
  <button class="copy-svg-btn" type="button" aria-label="Copy SVG markup">Copy SVG</button>
  <div class="figure-svg-wrap">
    <svg viewBox="0 0 280 180" role="img" aria-label="Token bucket — refill rate">
      <!-- single concept SVG -->
    </svg>
  </div>
  <figcaption>
    <span class="figure-number">Fig 1</span>
    <span class="figure-title">Token bucket refill</span>
    <span class="figure-desc">Capacity of 20 refills at 5 tokens/second; bursts allowed up to capacity.</span>
  </figcaption>
</figure>
```

Use for: blog companions and multi-figure explainers. Each figure is independently copyable via the `copy-svg-btn`.

### Sequence diagram skeleton

```html
<svg viewBox="0 0 720 480" role="img" aria-label="Login sequence: client, gateway, auth, database">
  <!-- Actor headers across the top -->
  <rect x="40"  y="20" width="120" height="40" rx="6"
        fill="color-mix(in srgb, var(--color-info) 10%, var(--bg-page))"
        stroke="var(--color-info)"/>
  <text x="100" y="46" text-anchor="middle" font-size="12">Client</text>

  <!-- Dashed lifelines descending from each actor -->
  <line x1="100" y1="60" x2="100" y2="460" stroke="var(--border-subtle)"
        stroke-width="1" stroke-dasharray="4 3"/>

  <!-- Message arrow between lifelines -->
  <line x1="100" y1="120" x2="320" y2="120"
        stroke="var(--text-muted)" stroke-width="1.5" marker-end="url(#arrow)"/>
  <text x="210" y="115" text-anchor="middle" font-size="11"
        font-family="var(--font-mono, monospace)">POST /login</text>
</svg>
```

Use for: protocol exchanges, message-passing, async workflows. Lifelines dashed; sync messages solid; async messages dashed.

---

## Interaction Patterns

| Pattern | Behavior |
|---|---|
| Click-to-expand node | `.diagram-node` is a `<g tabindex="0" role="button">`; click reveals `.node-detail-panel` (`aria-live="polite"`) |
| Hover-to-highlight | Dim unrelated nodes via `opacity: 0.35`; highlight connected paths via `stroke-width` increase |
| Copy SVG | `.copy-svg-btn` copies `outerHTML` of the sibling `<svg>` to clipboard |
| Callout link | Numbered `.callout-dot`s are `<a xlink:href="#callout-N">` OR keyboard buttons that scroll to the matching list item |

---

## ARIA / Accessibility

| Element | Required attributes | Why |
|---|---|---|
| `<svg>` root | `role="img"`, `aria-label="<description>"` | Otherwise SVG is invisible to AT |
| Interactive `<g class="diagram-node">` | `tabindex="0"`, `role="button"`, `aria-label` | Keyboard + AT activation |
| Click-handlers on nodes | Listen for Enter and Space, not just `click` | Keyboard equivalent |
| `.callout-dot` | `tabindex="0"`, `role="button"`, `aria-label="Callout N: <topic>"` | Each is a real action target |
| `.node-detail-panel` | `aria-live="polite"` | Detail change announced when a node is clicked |
| Color encoding | Always paired with text label | Color-blind users need redundancy |
| Legend | Always present; below the diagram | Decodes the color system |
| Reduced motion | Disable `transition` on `.diagram-node`, `.callout-dot` under `prefers-reduced-motion` | Already in template |
| External images | None — no `<image href=...>`, only inline SVG | Self-contained constraint |

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| `<image href="...">` inside the SVG | Inline only — the artifact must work offline |
| Diagram without a legend | Always include a legend mapping colors / line styles to meaning |
| Color is the only category indicator | Pair with text labels, patterns, or shapes |
| Node has color but no text label | Every node needs a `<text>` label |
| SVG with fixed `width="600"` and no viewBox | Use `viewBox` + `width: 100%` + `min-width` for horizontal scroll |
| Async vs sync arrows visually identical | Async = `stroke-dasharray="6 4"`, sync = solid |
| Hover-only interactions | Touch / keyboard users cannot hover; provide click + focus alternative |
| Clickable node without keyboard support | Add `tabindex="0"` + `role="button"` + Enter/Space handler |
| Ad-hoc layer colors that don't match other diagrams | Use the convention: Frontend=info, API=accent, DB=success, External=warning |
| Inline `<style>` redefining `.diagram-container` / `.figure-panel` | Lives in `templates/shapes/diagram.css` — touching it creates drift |

---

## Shape Selection

Use **diagram** when the request matches: diagram, flowchart, architecture, sequence, data-flow, figure sheet, illustrate, SVG.

Do **not** use diagram when:

- The diagram is part of a larger written explanation (use **report + diagram** hybrid)
- The user wants to compare design approaches (use **spec + diagram** hybrid)
- The user wants charts of numerical data (use **data-viz**)
- The user wants annotated source code (use **code-review**)
