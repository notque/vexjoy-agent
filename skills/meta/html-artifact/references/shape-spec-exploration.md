# Shape: Spec / Exploration

> **Shape**: spec | **Signal words**: plan, explore, compare, brainstorm, approach, option, tradeoff, design directions
> CSS layout classes: `templates/shapes/spec.css` (injected by assemble-template.py)
> Components: `tabs`, `copy-button`, `theme-toggle`

Spec artifacts present N options side-by-side and end with a recommendation. The reader's question is "which one?" — answer it. Comparison without conclusion wastes the reader's time.

---

## Layout Description

A responsive comparison grid that scales from 2 to 5 columns, collapsing to a single stacked column on mobile (`repeat(auto-fit, minmax(320px, 1fr))`). Each `.approach-card` is a self-contained evaluation: numbered header, one-sentence summary, pros/cons split, optional code or metadata badges. The recommended option carries `.approach-tag` which adds an accent border so the eye finds it immediately.

A `.recommendation` block always follows the grid with the chosen option and the reasoning. Optional `.tradeoff-matrix` precedes the recommendation when the comparison has 3+ dimensions worth a table.

---

## Canonical Markup Order (load-bearing rule)

| Order | Region | Purpose |
|---|---|---|
| 1 | `<header>` with title + subtitle | Frames the question |
| 2 | TL;DR (optional) | One-paragraph summary if the spec is also a plan |
| 3 | SVG architecture diagram (optional) | When approaches differ structurally |
| 4 | `.comparison-grid` of `.approach-card`s | The N options, recommended one tagged |
| 5 | `.tradeoff-matrix` (optional) | Cross-cutting dimensions × options |
| 6 | `.recommendation` | **Always last before footer.** Names the choice and why |
| 7 | `<footer>` | Author, date, related links |

Why this order: the reader scans the cards, the recommendation tells them where to look first, and the matrix is the auditable backup. Putting the recommendation before the cards undercuts the comparison; putting the matrix before the cards makes it abstract.

### Skeleton

```html
<body data-shape="spec" data-theme="birchline">
  <header>
    <h1>Rate Limiter — Three Approaches</h1>
    <p class="subtitle">Comparing token bucket, sliding window, and Redis-backed.</p>
  </header>
  <main>
    <section class="comparison-grid">
      <article class="approach-card"><!-- option 1 --></article>
      <article class="approach-card"><!-- option 2, recommended --></article>
      <article class="approach-card"><!-- option 3 --></article>
    </section>
    <section><table class="tradeoff-matrix"><!-- optional --></table></section>
    <section class="recommendation"><!-- always present --></section>
  </main>
  <footer>Authored 2026-05-05 · @platform</footer>
</body>
```

CSS lives in `templates/shapes/spec.css` — do not redefine `.comparison-grid`, `.approach-card`, `.pros-cons`, `.tradeoff-matrix`, `.badge`, `.recommendation` inline.

---

## Section Types (worked examples)

### Approach card

```html
<article class="approach-card">
  <header class="approach-header">
    <span class="approach-number">02</span>
    <h3>Token bucket (in-process)</h3>
    <span class="approach-tag">Recommended</span>
  </header>
  <p>Per-instance bucket refills at a steady rate; bursts allowed up to capacity.</p>
  <div class="pros-cons">
    <div class="pros">
      <h4>Pros</h4>
      <ul>
        <li>No network hop per request</li>
        <li>Survives Redis outage</li>
        <li>~2k LOC, no new infra</li>
      </ul>
    </div>
    <div class="cons">
      <h4>Cons</h4>
      <ul>
        <li>No cross-instance coordination</li>
        <li>Burst is per-instance, not global</li>
      </ul>
    </div>
  </div>
  <div class="badges">
    <span class="badge">Complexity: Low</span>
    <span class="badge">Migration: 1 sprint</span>
    <span class="badge">Testability: High</span>
  </div>
</article>
```

Use for: every option being compared. The recommended option carries `.approach-tag` — that drives the accent border. Numbered headers (01, 02, 03) help reviewers reference "approach 2" in discussion.

### Tradeoff matrix

```html
<table class="tradeoff-matrix">
  <thead>
    <tr><th>Dimension</th><th>Token Bucket</th><th>Sliding Window</th><th>Redis-backed</th></tr>
  </thead>
  <tbody>
    <tr>
      <th scope="row">Cross-instance accuracy</th>
      <td><span class="cell-warning">Approximate</span></td>
      <td><span class="cell-warning">Approximate</span></td>
      <td><span class="cell-success">Exact</span></td>
    </tr>
    <tr>
      <th scope="row">Latency impact</th>
      <td><span class="cell-success">~0ms</span></td>
      <td><span class="cell-success">~0ms</span></td>
      <td><span class="cell-danger">+2-5ms</span></td>
    </tr>
    <tr>
      <th scope="row">Operational cost</th>
      <td><span class="cell-success">None</span></td>
      <td><span class="cell-success">None</span></td>
      <td><span class="cell-warning">Redis cluster</span></td>
    </tr>
  </tbody>
</table>
```

Use for: comparisons with 3+ orthogonal dimensions. Cells use `.cell-success` / `.cell-warning` / `.cell-danger` — text + color, never color alone.

### Recommendation block

```html
<section class="recommendation" aria-label="Recommendation">
  <h2>Recommended: Token bucket</h2>
  <p>Adopts in 1 sprint, adds zero infrastructure, survives Redis outages.
     The cross-instance approximation is acceptable for our 12-instance fleet
     because the global error stays under 8%. Revisit if the fleet grows past 50.</p>
</section>
```

Use for: every spec, every time. Name the choice in the heading. State the reason in one paragraph. Include the condition under which the decision should be revisited.

### Architecture SVG (when approaches differ structurally)

```html
<figure>
  <svg viewBox="0 0 720 200" role="img" aria-label="Token bucket data flow">
    <defs>
      <marker id="arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
        <path d="M0,0 L8,3 L0,6" fill="var(--text-muted)"/>
      </marker>
    </defs>
    <rect x="20" y="70" width="120" height="60" rx="10"
          fill="color-mix(in srgb, var(--color-info) 10%, transparent)"
          stroke="var(--color-info)" stroke-width="1.5"/>
    <text x="80" y="105" text-anchor="middle" font-size="13">Client</text>
    <line x1="140" y1="100" x2="200" y2="100"
          stroke="var(--text-muted)" stroke-width="1.5" marker-end="url(#arrow)"/>
    <!-- continue with rate-limiter, API, DB nodes -->
  </svg>
  <figcaption>Figure 1 · Token bucket request flow</figcaption>
</figure>
```

Use for: when "approach A puts the limiter in-process, approach B puts it in Redis" is structural and prose alone is insufficient. Inline SVG only — no external images. Layer-color convention: Frontend = info, API = primary, DB = success, External = warning.

---

## Composition Guide

| Request | Sections |
|---|---|
| "Compare N approaches" | Header + Comparison Grid + Recommendation |
| "Design directions" | Header + Comparison Grid + Theme Toggle + Recommendation |
| "Implementation plan" | Header + TL;DR + SVG diagram + Comparison Grid + Risk table + Recommendation |
| "Architecture options" | Header + SVG diagram per option + Comparison Grid + Recommendation |
| "Explore tradeoffs" | Header + Comparison Grid (2 cards) + Tradeoff Matrix + Recommendation |

### Layout rules — choose by approach count

The base shape CSS handles density automatically when you set `data-count` on `.comparison-grid`:

| Approach Count | Grid Recipe | Why |
|---|---|---|
| 2 | `<section class="comparison-grid" data-count="2">` | 2 columns, ample width per card |
| 3 | `<section class="comparison-grid" data-count="3">` | 3 columns, default sweet spot |
| 4 | `<section class="comparison-grid" data-count="4">` (2x2) **OR** demote 1-2 to `.alternatives-grid` | 4 columns in one row crams content past readability — see "demote pattern" below |
| 5-6 | Demote weakest 2-3 to `.alternatives-grid`; keep top 3 in main grid | Reader cannot hold more than ~3 full comparisons in working memory |

### Demote pattern (4+ approaches)

When the request is "compare 4 approaches" — keep the top 2-3 as full `.approach-card`s in the main `.comparison-grid` and put the rest in a compact `.alternatives-grid`:

```html
<section class="comparison-grid" data-count="3">
  <article class="approach-card">...</article>  <!-- top 1 (recommended) -->
  <article class="approach-card">...</article>  <!-- top 2 -->
  <article class="approach-card">...</article>  <!-- top 3 -->
</section>

<section class="alternatives">
  <h2>Other approaches considered</h2>
  <div class="alternatives-grid">
    <article class="approach-card">...</article>  <!-- demoted 4 -->
    <article class="approach-card">...</article>  <!-- demoted 5 -->
  </div>
</section>
```

Why: the main grid carries the cards the reader actually weighs against the recommendation. The alternatives grid signals "we considered these and ruled them out" without burning equal visual real estate.

### Architecture diagram slot

For "architecture options" requests where each approach has a different structure, use the `.architecture-diagram` slot — a centered figure that wraps an inline SVG:

```html
<figure class="architecture-diagram">
  <svg viewBox="0 0 720 280" role="img" aria-label="Token bucket data flow">
    <!-- inline SVG, layer-color convention from references/design-system.md -->
  </svg>
  <figcaption>Figure 1 · Token bucket request flow</figcaption>
</figure>
```

Place ONE diagram per approach (between the comparison grid and the recommendation), or a single shared diagram above the grid if approaches differ on a single dimension. Inline SVG only — no `<image href>` or external references.

### When NOT to author shape CSS in the artifact

The base `templates/shapes/spec.css` already provides every layout primitive listed above. The artifact `<style>` block should be reserved for **content-specific** tweaks (e.g., a per-artifact accent color), never for layout primitives. In particular:

- **Never override `display` with `!important`** in artifact `<style>`. The validator rejects it. Base CSS uses cascade defenses (e.g., `:not(.active)`) that artifact `!important` rules silently defeat — past failure: a deck artifact's `.slide-split { display: grid !important }` made every split slide visible at once.
- Never redefine `.comparison-grid`, `.approach-card`, `.pros-cons`, `.tradeoff-matrix`, `.alternatives-grid`, `.architecture-diagram` — they live in the template.
- If you find yourself needing a layout primitive the template doesn't ship, that's a template bug; file an issue rather than papering over with inline CSS.

---

## ARIA / Accessibility

| Element | Required attributes | Why |
|---|---|---|
| `.approach-card` | Use `<article>` | Self-contained chunk; AT can list articles on the page |
| `.approach-tag` | Text content "Recommended" | Don't rely on the accent border alone |
| `.tradeoff-matrix` | `<th scope="col">` for column headers, `<th scope="row">` for row labels | AT announces the matrix correctly |
| `.cell-success` / `.cell-warning` / `.cell-danger` | Real text inside ("Exact", "Approximate") | Color alone fails WCAG |
| `<svg>` diagrams | `role="img"`, `aria-label="<description>"` | Otherwise the SVG is invisible to AT |
| `.recommendation` | `<section aria-label="Recommendation">` | Landmark — readers can jump straight to it |
| `.badge` | Text content; not color-coded | Treat as neutral metadata, not a status indicator |
| Theme toggle | Provided by `theme-toggle` component | Don't hand-author — use the assembler |

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Comparison grid without a recommendation section | Always end with a recommendation; spec without a choice is just a list |
| Recommended option not visually distinct | Add `.approach-tag` so the accent border applies |
| Pros/cons as flat bullets, mixed | Use `.pros-cons` 2-column grid; `.pros` and `.cons` get their own +/− markers via CSS |
| Hardcoded grid columns (`grid-template-columns: 1fr 1fr 1fr`) | Use `repeat(auto-fit, minmax(320px, 1fr))` from the template — works for 2-5 cards |
| Missing badges (no complexity / migration / testability indicator) | Include 2-3 badges per card; otherwise the cards feel like marketing |
| Color-only matrix cells | Use `.cell-success/.cell-warning/.cell-danger` — text + color |
| `<table>` without `<th scope>` | Screen readers cannot navigate the matrix |
| SVG diagram with `<image href=...>` | All inline — no external image refs in a self-contained artifact |
| Recommendation buried mid-document | Always last before footer |
| Inline `<style>` redefining `.approach-card` / `.tradeoff-matrix` | Lives in `templates/shapes/spec.css` — touching it creates drift |

---

## Shape Selection

Use **spec** when the request matches: plan, explore options, compare N approaches, brainstorm, design directions, tradeoffs, architecture options, RFC.

Do **not** use spec when:

- The user wants a single recommended approach without comparison (use **report**)
- The user wants to tune one design interactively (use **prototype**)
- The user wants charts comparing performance numerically (use **data-viz**)
- The user wants a slide deck pitching one option (use **deck**)

Hybrid OK: `spec + diagram` (architecture options with per-option SVG); `spec + data-viz` (comparison with per-option charts).
