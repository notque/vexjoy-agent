# Shape: Slide Deck

> **Shape**: deck | **Signal words**: slides, presentation, deck, talk, pitch
> CSS layout classes: `templates/shapes/deck.css` (injected by assemble-template.py)
> JS navigation: `templates/components/keyboard-nav.js` (request `keyboard-nav` component)

Slides are FOCUSED. One idea per slide. Large text, minimal detail, strong visual hierarchy. The deck is a narrative arc, not a document reformatted as slides.

---

## Canonical Markup Order (load-bearing rule)

The deck shape has a fixed structural contract. **Always emit these regions in this order**, top to bottom in source:

| Order | Region | Purpose |
|---|---|---|
| 1 | `<main>` containing `.slide-deck` | The slides themselves |
| 2 | `<footer>` opens with `.slide-nav` | Prev / counter / Next controls |
| 3 | Inside `<footer>`, after `.slide-nav` | `.progress-bar` with `.progress-fill` |

**Why this order:** the slide deck is the content; controls and progress are chrome that frames it from below. Counter-on-top with bar-on-bottom splits chrome across the deck and disorients the user. The historical convention (preserved across the toolkit) is **deck first, controls second, progress bar last**.

Do not invert. Do not place `.slide-nav` in `<header>`. Do not place `.progress-bar` above the deck. The PDF print stylesheet hides chrome via `.no-print`, but on-screen the order matters.

### Skeleton

```html
<body data-shape="deck" data-theme="dark-focus">
  <main>
    <div class="slide-deck" role="region"
         aria-label="Presentation"
         aria-roledescription="carousel">
      <section class="slide active" role="group"
               aria-roledescription="slide"
               aria-label="Slide 1 of N: Title"
               data-notes="Optional presenter notes.">
        <!-- slide content -->
      </section>
      <!-- more slides... -->
    </div>
  </main>
  <footer>
    <nav class="slide-nav no-print" aria-label="Slide navigation">
      <button type="button" class="slide-prev" aria-label="Previous slide">&#8249;</button>
      <span class="slide-counter" aria-live="polite">1/N</span>
      <button type="button" class="slide-next" aria-label="Next slide">&#8250;</button>
    </nav>
    <div class="progress-bar" role="progressbar"
         aria-label="Deck progress"
         aria-valuemin="0" aria-valuemax="100" aria-valuenow="...">
      <div class="progress-fill" style="width: ...%;"></div>
    </div>
  </footer>
</body>
```

The `.no-print` class on `.slide-nav` hides controls in the PDF; `.progress-bar` also hides via the shape's print stylesheet. CSS lives in `templates/shapes/deck.css` and `templates/print/deck-print.css` — do not redefine.

---

## Key CSS Classes (defined in templates/shapes/deck.css)

| Class | Purpose |
|---|---|
| `.slide-deck` | 16:9 container, max-width ~960px, centered |
| `.slide` | Absolutely positioned; hidden by default, `.active` shows |
| `.slide-nav` | Flex row of prev / counter / next |
| `.slide-prev`, `.slide-next` | Navigation buttons (44x44 hit target) |
| `.slide-counter` | Monospace "N/Total" position indicator |
| `.progress-bar` + `.progress-fill` | Thin accent bar, width = `(current/total)*100%` |
| `.no-print` | Marks chrome to hide in PDF export |

---

## Slide Types (worked examples)

Each example is the slide body only. Drop into `<div class="slide-deck">`. Use the CSS classes already defined in the assembled template — do not redefine them inline.

### Title slide

```html
<section class="slide slide-title active" role="group"
         aria-roledescription="slide"
         aria-label="Slide 1 of 8: Title"
         data-notes="Welcome the audience. Set context.">
  <h1>Building Resilient APIs</h1>
  <p class="slide-subtitle">Patterns for graceful degradation at scale</p>
  <p class="slide-meta">Engineering Team &middot; May 2026</p>
</section>
```

Use for: opener, section dividers, closing slide. Centered hero text, optional subtitle and author/date line.

### Content slide (heading + bullets)

```html
<section class="slide" role="group"
         aria-roledescription="slide"
         aria-label="Slide 2 of 8: Key Principles"
         data-notes="These are ordered by priority.">
  <h2>Key Principles</h2>
  <ul>
    <li>Fail fast, recover faster</li>
    <li>Degrade gracefully under load</li>
    <li>Circuit breakers on all external calls</li>
    <li>Retry with exponential backoff</li>
  </ul>
</section>
```

Use for: the workhorse slide. 3-6 bullets max. Each bullet under 12 words. If you need more bullets or longer prose, split across two slides.

### Code slide

```html
<section class="slide slide-code" role="group"
         aria-roledescription="slide"
         aria-label="Slide 4 of 8: Circuit Breaker"
         data-notes="Walk through state machine: closed, open, half-open.">
  <h2>Circuit Breaker</h2>
  <pre><code>class CircuitBreaker {
  constructor(threshold = 5, resetMs = 30000) {
    this.failures = 0;
    this.state = 'closed';
  }
  async call(fn) {
    if (this.state === 'open') throw new Error('Circuit open');
    try { const r = await fn(); this.onSuccess(); return r; }
    catch (e) { this.onFailure(); throw e; }
  }
}</code></pre>
</section>
```

Use for: technical talks, tutorials. Keep code under 20 lines per slide — if longer, split or simplify. Monospace and contrast are inherited from the theme.

### Split slide (text left, visual right)

```html
<section class="slide slide-split" role="group"
         aria-roledescription="slide"
         aria-label="Slide 6 of 8: Before and After">
  <div class="split-text">
    <h2>Before &amp; After</h2>
    <ul>
      <li>p99 latency: 2.4s &rarr; 180ms</li>
      <li>Error rate: 4.2% &rarr; 0.1%</li>
      <li>Uptime: 99.2% &rarr; 99.97%</li>
    </ul>
  </div>
  <div class="split-visual">
    <svg viewBox="0 0 280 200" role="img"
         aria-label="Latency improvement chart">
      <!-- inline SVG -->
    </svg>
  </div>
</section>
```

Use for: text alongside diagram, results next to chart, problem/solution. Two children: `.split-text` and `.split-visual`. Reflows to single column on narrow viewports via the shape stylesheet.

### Quote slide

```html
<section class="slide slide-quote" role="group"
         aria-roledescription="slide"
         aria-label="Slide 7 of 8: Quote">
  <blockquote>
    <p>&ldquo;Everything fails all the time.&rdquo;</p>
    <cite>Werner Vogels, CTO Amazon</cite>
  </blockquote>
</section>
```

Use for: emphasis, principle restated, transition between sections. One quote per slide. Keep under ~20 words so it reads at a glance.

---

## Accessibility Pattern Table

The deck must declare its semantics correctly so screen readers can navigate it as a carousel. These attributes are **required**, not optional.

| Element | Required attributes | Why |
|---|---|---|
| `.slide-deck` container | `role="region"`, `aria-label="..."`, `aria-roledescription="carousel"` | Identifies the deck as a slideshow region |
| Each `.slide` | `role="group"`, `aria-roledescription="slide"`, `aria-label="Slide N of M: <title>"` | Announces position + title on focus |
| `.slide-counter` | `aria-live="polite"` | Counter updates announce on navigation without interrupting |
| `.progress-bar` | `role="progressbar"`, `aria-valuemin`, `aria-valuemax`, `aria-valuenow` | Programmatic progress for AT |
| `.slide-prev`, `.slide-next` | `aria-label="Previous slide"` / `"Next slide"` | Buttons with icon-only content need accessible names |
| Active state | Toggle `.active` class on the visible slide; non-active slides should not steal focus | Hidden slides remain in the DOM but are inert |
| Keyboard nav | Arrow keys ignore form inputs (`INPUT`, `TEXTAREA`); Home/End jump to first/last | Don't hijack typing in interactive demos |
| Reduced motion | Slide opacity transitions disabled under `prefers-reduced-motion: reduce` | Handled in `templates/shapes/deck.css` |
| Print | All slides rendered sequentially with page breaks | Handled in `templates/print/deck-print.css` |

---

## Navigation

Request the `keyboard-nav` component when assembling. It provides:

- Arrow Left/Up = previous slide; Arrow Right/Down = next.
- Home/End jump to first/last slide.
- Touch swipe (horizontal threshold ~50px) on the deck container.
- Counter and progress-bar update on every transition.
- Optional `data-notes` attribute on each `.slide` surfaces presenter notes when toggled.

Do not hand-author keyboard handlers — the component already exists.

---

## Composition Guide

### Slide variants — pick one per slide

Every slide MUST carry one of these variant classes (or no variant for plain heading + bullets). The base CSS in `templates/shapes/deck.css` styles each variant; the artifact never authors layout for these.

| Variant Class | Use for | Required children |
|---|---|---|
| `slide-title` | Opener, section dividers, closing slide | `<h1>`, optional `.slide-subtitle`, `.slide-meta` |
| `slide-section` | Mid-deck section break | `.eyebrow` + `<h1>` or `<h2>` |
| `slide-split` | Text-left, visual-right | `.split-text`, `.split-visual` (each direct child of the slide) |
| `slide-quote` | Pull quote, principle | `<blockquote>` with `<p>` and `<cite>` |
| `slide-code` | Code walkthrough | `<h2>` + `<pre><code>` |
| `slide-table` | Data comparison | `<h2>` + `<table>` |
| (no variant) | Plain heading + bullets | `<h2>` + `<ul>` or `<ol>` |

### Layout rules — load-bearing

1. **Show/hide is owned by base CSS.** `.slide-deck > .slide:not(.active) { display: none !important; }` is pinned in `templates/shapes/deck.css`. The artifact never authors `display` rules on `.slide` or any `.slide-*` variant.
2. **NEVER add `display: <x> !important` in the artifact `<style>` block.** Past failure (2026-05-20): a deck inlined `.slide-split { display: grid !important; }` to style its split layout. That declaration silently defeated `.slide { display: none }` for every `.slide-split` element, rendering all split slides simultaneously and producing a stacked-pages broken deck. The base CSS now uses `:not(.active)` to defend against this, AND `validate-artifact.py` rejects the pattern. If you find yourself wanting to write `display: grid !important` on a slide variant, that's the bug — use the variant class (`slide-split`) and let base CSS handle it.
3. **Variant CSS is already shipped.** `slide-split` already grids text + visual. `slide-quote` already centers the blockquote. `slide-code` already pads the `<pre>`. The artifact authors content; the template owns layout.
4. **Slide count matches duration.** Lightning (5 min) = 4-6 slides. Standard (15 min) = 8-12. Deep dive (30+ min) = 15-30. Don't pad with filler.

### Slide sequence patterns (keep)

| Deck Type | Slide Sequence |
|---|---|
| Technical talk (15 min) | Title, Content (overview), Code x2-3, Split (results), Content (takeaways), Title (closing) |
| Pitch deck | Title, Content (problem), Split (solution), Content (metrics), Visual (architecture), Content (next steps) |
| Lightning talk (5 min) | Title, Content (one idea), Code or Visual, Content (takeaway) |
| Training deck | Title, Content (goals), alternating Code + Content, Content (exercises), Title (Q&A) |

| Duration | Slide Count | Pace |
|---|---|---|
| 5 min lightning | 4-6 | ~1 min/slide |
| 15 min | 8-12 | ~90s/slide |
| 30 min | 15-20 | ~90s/slide |
| 45 min | 20-30 | ~90s/slide |

### When NOT to author shape CSS in the artifact

The base `templates/shapes/deck.css` ships every layout primitive listed above. Do not redefine `.slide`, `.slide-deck`, `.slide-nav`, `.progress-bar`, or any `slide-<variant>` class in the artifact `<style>`. If a slide needs a custom layout the variants don't cover, add a content-class (e.g., `.metrics-row` inside the slide body) and style THAT — never the slide itself.

`!important` on `display` is validator-rejected. `!important` on color/background/font properties is fine in moderation but rarely needed (the theme tokens cascade correctly).

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Chrome above the deck | Place `.slide-nav` and `.progress-bar` in `<footer>`, after `<main>` |
| Counter on top, progress bar at bottom (split chrome) | Both belong in the same `<footer>`, in order: nav, then bar |
| Slides not 16:9 | The shape stylesheet sets `aspect-ratio: 16/9` on `.slide-deck` — don't override |
| Missing `aria-roledescription` | Required on both deck container ("carousel") and each slide ("slide") |
| Hand-authored keyboard handlers | Request `keyboard-nav` component; the assembler injects it |
| Inline `<style>` redefining `.slide-*` classes | All slide CSS lives in `templates/shapes/deck.css`; touching it in the artifact creates drift |
| `display: <x> !important` on `.slide-*` (especially `.slide-split`) | Validator rejects it. Use the variant class; base CSS handles `display` via `:not(.active)` |
| Content overflows slide | Cut bullets; split across two slides; use shorter prose |
| Counter not updating | The component listens for navigation events; ensure `.slide-counter` exists in the markup |

---

## Shape Selection

Use **deck** when the request matches: slides, presentation, slide deck, talk, pitch, keynote, slideshow.

Do **not** use deck when:

- The user wants a written document (use **report**)
- The user wants to compare options side by side (use **spec**)
- The user wants interactive parameter tuning (use **prototype**)
- The user wants diagrams without a presentation wrapper (use **diagram**)
- The user wants a dashboard with charts (use **data-viz**)
