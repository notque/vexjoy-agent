# Shape: Design Prototype

> **Shape**: prototype | **Signal words**: tune, adjust, animation sandbox, component variants, design system preview, try options
> CSS layout classes: `templates/shapes/prototype.css` (injected by assemble-template.py)
> Components: `slider`, `copy-button`, `theme-toggle`

Prototypes are INTERACTIVE. Every parameter the user can adjust must update the preview live, and every prototype ends with an export mechanism. A prototype that the user can't take with them is half-built.

---

## Layout Description

Two-pane on desktop: 300px sticky `.controls-panel` (left) + flex `.preview-panel` (right). On mobile both stack (controls above preview). The preview surface (`.preview-surface`) is a card-shaped target the user's eye returns to as they tweak — never let the controls overflow into the preview area.

For variant comparison (contact sheet pattern), the layout flips: full-width `.variant-grid` of `.variant-cell`s, each with its own preview + label + copy button.

---

## Canonical Markup Order (load-bearing rule)

| Order | Region | Purpose |
|---|---|---|
| 1 | `<header>` | Title + brief explanation of what's being prototyped |
| 2 | `.prototype-layout` (split) OR `.variant-grid` (contact sheet) | The interactive surface |
| 3 | Within controls: `.control-group-label` divides sections | Grouped knobs (Spacing, Color, Motion) |
| 4 | Within controls: `.export-btn` at the bottom of the panel | **Mandatory** |
| 5 | `<footer>` (optional) | Notes, related tokens, links |

Why this order: controls before preview reads naturally left-to-right; export at the bottom of the controls panel matches the "tune, then take" workflow. Burying export at the page bottom invites users to scroll past it.

### Skeleton (split panel)

```html
<body data-shape="prototype" data-theme="birchline">
  <header>
    <h1>Card Padding Tuner</h1>
    <p>Adjust spacing tokens; copy CSS variables when ready.</p>
  </header>
  <main class="prototype-layout">
    <aside class="controls-panel" aria-label="Controls">
      <h2>Spacing</h2>
      <div class="control-row">
        <label for="pad-x">Horizontal</label>
        <input id="pad-x" type="range" min="8" max="48" value="16">
        <span class="value-display" aria-live="polite">16px</span>
      </div>
      <!-- more control-rows -->
      <button class="export-btn" type="button">Copy CSS Variables</button>
    </aside>
    <section class="preview-panel">
      <div class="preview-surface" aria-label="Live preview">
        <!-- live preview content -->
      </div>
    </section>
  </main>
</body>
```

CSS lives in `templates/shapes/prototype.css` — do not redefine `.prototype-layout`, `.controls-panel`, `.preview-surface`, `.control-row`, `.value-display`, `.export-btn`, `.variant-*` inline.

---

## Layout Patterns

| Pattern | Use When | Structure |
|---|---|---|
| Split panel | One thing being tuned | `.prototype-layout` (controls + preview) |
| Contact sheet | Variant comparison (8 button styles, 6 type scales) | `.variant-grid` of `.variant-cell`s |
| Sandbox | Animation tuning | Preview top with play / pause / reset, controls below |
| Swatch grid | Color tokens, spacing tokens | Grid of clickable swatches; each is a `<button>` that copies on click |

---

## Section Types (worked examples)

### Slider control row

```html
<div class="control-row">
  <label for="radius">Radius</label>
  <input id="radius" type="range" min="0" max="24" value="6"
         oninput="document.querySelector('.preview-surface').style.setProperty('--demo-radius', this.value + 'px'); this.nextElementSibling.textContent = this.value + 'px';">
  <span class="value-display" aria-live="polite">6px</span>
</div>
```

Use for: continuous numeric values (padding, radius, opacity, duration). **Always `oninput`, never `onchange`** — the user expects the preview to track the slider, not lag until release. The `aria-live="polite"` on the readout announces the new value to AT.

### Toggle control row

```html
<div class="control-row">
  <label for="shadow-on">Shadow</label>
  <span class="toggle">
    <input id="shadow-on" type="checkbox" checked
           onchange="document.querySelector('.preview-surface').classList.toggle('with-shadow', this.checked);">
    <span class="toggle-slider" aria-hidden="true"></span>
  </span>
</div>
```

Use for: boolean state (shadow on/off, animation on/off). Underlying `<input type="checkbox">` provides the semantics; the styled slider is `aria-hidden`.

### Variant cell (contact sheet)

```html
<article class="variant-cell">
  <div class="variant-preview">
    <button class="btn-variant" style="--btn-radius:4px; --btn-pad:8px 16px;">Subtle</button>
  </div>
  <footer class="variant-label">
    <code>--btn-radius: 4px; --btn-pad: 8px 16px;</code>
    <button class="copy-btn" type="button" aria-label="Copy values">Copy</button>
  </footer>
</article>
```

Use for: side-by-side variant comparison. Each cell is independent and copyable.

### Export button

```html
<button class="export-btn" type="button"
        aria-label="Copy CSS variables to clipboard">
  Copy CSS Variables
</button>
```

Use for: every prototype, every time. The handler reads each control's value and emits `:root { --var: value; }` to the clipboard. Use the `copy-button` component's success-state pattern (text → "Copied!", `.copied` class for 1.5s).

---

## Export (MANDATORY)

Every prototype includes at least one export action. Choose what matches the prototype:

| Prototype Kind | Export Format |
|---|---|
| Single design (split panel) | "Copy CSS Variables" — emits `:root { ... }` block |
| Component variants (contact sheet) | Per-cell "Copy" — copies that cell's parameters |
| Animation sandbox | "Copy keyframes" — emits `@keyframes` block |
| Color picker | "Copy hex" / "Copy HSL" — both formats |
| Configuration tuner | "Copy JSON" — emits config object |

Visual feedback: button text → "Copied!", `.copied` class adds `.export-btn` success color for 1.5s. Never use `alert()` for copy feedback.

---

## ARIA / Accessibility

| Element | Required attributes | Why |
|---|---|---|
| Every `<input type="range">` | `<label for="...">` matching `id` | Label is required for AT |
| `.value-display` | `aria-live="polite"` | New value announced when slider moves |
| `.preview-surface` | `aria-label="Live preview"` (or descriptive) | Otherwise it's an unlabeled region |
| `.toggle` wrapper | Real `<input type="checkbox">` inside | Provides keyboard + AT semantics |
| `.toggle-slider` | `aria-hidden="true"` | Decorative; the input is the source of truth |
| Color swatches | `<button aria-label="Copy <color name> <hex>">` | Never `<div onclick>` |
| `.export-btn` | Visible focus indicator (`:focus-visible` already in template) | Keyboard users land on it |
| Touch targets | All controls ≥ 44×44px | The template enforces this; do not override |
| Reduced motion | Provide an explicit "Reduced motion" toggle when the prototype is animation-heavy | Lets the user test that path |

---

## Composition Guide

### Layout rules — keep the controls panel disciplined

The base `templates/shapes/prototype.css` styles the controls panel as a flex column with natural overflow. **Do not** layer artifact CSS that re-introduces these long-disabled patterns:

| Pattern (NEVER do) | Why it breaks |
|---|---|
| `overflow-y: auto; max-height: 100vh` on `.controls-panel` | Reserves a viewport-height empty rectangle when the control list is short — the empty-rectangle bug |
| `position: sticky; top: 0` on `.controls-panel` | Pins controls during page scroll but interacts poorly with the empty-rectangle reservation; not needed because the layout is already a two-pane split |
| `min-width: 120px` (or any min-width) on `.control-row label` | Starves the slider track on narrow panels — labels should size to content |
| Hard-coded slider widths or label widths | Use the template's grid (`max-content | 1fr | auto`) which flexes correctly |

If your prototype has more than ~6 control rows, **group with `.control-group-label` headings** rather than reaching for `overflow-y` to hide them. Trust normal page scroll.

If a label is unusually long and needs more breathing room, add `.control-row.wide` and override only the row that needs it — never the global rule.

### Sizing

- Default panel width: 340px (see `.prototype-layout`'s `grid-template-columns: 340px 1fr`). Don't override.
- Slider tracks: minimum effective track width is ~180px on the narrowest viewport; the template guarantees this when label min-widths aren't pinned.
- `<select>` and `<input type="text">` controls fill the available column (template provides `width: 100%`).

### Composition by prototype kind

| Prototype Kind | Layout | Components |
|---|---|---|
| Single-design tuner | `.prototype-layout` (split) | `slider`, `copy-button` |
| Component variants | `.variant-grid` of `.variant-cell`s | `copy-button` per cell |
| Animation sandbox | `.prototype-layout` + reduced-motion toggle | `slider`, `copy-button` |
| Color picker | `.prototype-layout` + swatch grid | `copy-button` |

### When NOT to author shape CSS in the artifact

The artifact `<style>` block is for content-specific tweaks (the demo's own styled element under `.preview-surface`, e.g., a `.demo-card` with custom colors). It is NOT for layout primitives. In particular:

- **Never override `display` with `!important`** in artifact `<style>`. The validator rejects it. Base CSS uses cascade defenses that artifact `!important` rules silently defeat.
- Never redefine `.controls-panel`, `.preview-surface`, `.control-row`, `.export-btn`, `.variant-grid`, `.variant-cell` — they live in the template.
- Demo content classes (`.demo-card`, `.btn-variant`, etc.) are fine to author inline because they're the artifact's specific subject.

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Prototype without an export action | Always include at least one `.export-btn` |
| Slider uses `onchange` not `oninput` | Switch to `oninput` so the preview tracks the drag |
| Value readout is static text not live | Use `aria-live="polite"` on the readout |
| Controls don't all map to a preview change | Every control must drive a CSS custom property or DOM mutation |
| `<div onclick>` for swatches and toggle slider | Use `<button>` and `<input type="checkbox">` |
| Drag-reorder without keyboard alternative | Provide up/down buttons; keyboard users cannot drag |
| Animation prototype with no reduced-motion path | Offer an explicit toggle |
| Preview surface not a single, fixed card target | Keep `.preview-surface` shape stable; controls change content, not the frame |
| Copy feedback via `alert()` | Use the `copy-button` component's `.copied` state |
| `overflow-y` / `max-height: 100vh` on `.controls-panel` | The empty-rectangle bug — remove it; trust normal page scroll |
| `min-width: 120px` on `.control-row label` | Starves the slider track — let labels size to content |
| Inline `<style>` redefining `.controls-panel` / `.preview-surface` | Lives in `templates/shapes/prototype.css` — touching it creates drift |
| `display: <x> !important` in artifact `<style>` | Validator-rejected; base CSS owns layout primitives |

---

## Shape Selection

Use **prototype** when the request matches: tune, adjust, animation sandbox, component variants, design system preview, try options interactively, parameter tuner.

Do **not** use prototype when:

- The user wants to compare N predefined approaches (use **spec**)
- The user wants to triage / reorder / curate items (use **editor**)
- The user wants charts that filter by category (use **data-viz**)
- The user wants a static design reference document (use **report**)
