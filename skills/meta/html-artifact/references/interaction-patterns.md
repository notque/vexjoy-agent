# Interaction Patterns

Shared interactive patterns used across artifact shapes. **Implementations** (CSS + JS) live in `templates/components/` and are injected by `assemble-template.py --components <name>`. This file covers when to use each pattern, the markup contract the component expects, accessibility rules, and composition guidance.

> Do not hand-author the CSS or JS for these components in the artifact. Request them from the assembler — that is the only way the bundled accessibility, focus management, and reduced-motion behavior gets included.

---

## Available Components

Request via `--components` flag. Multiple: `--components tabs,collapsible,copy-button`.

| Component | File | Use When |
|---|---|---|
| `tabs` | `tabs.{css,js}` | Multiple views of the same data; mutually exclusive panels |
| `collapsible` | `collapsible.{css,js}` | Progressive disclosure; long sections users scan selectively (when `<details>` won't suffice) |
| `drag-drop` | `drag-drop.{css,js}` | Reordering lists; kanban columns; priority sorting |
| `copy-button` | `copy-button.{css,js}` | Any content the user might paste elsewhere |
| `keyboard-nav` | `keyboard-nav.{css,js}` | Sequential content (slides, cards) navigated by arrow keys |
| `theme-toggle` | `theme-toggle.{css,js}` | Light/dark mode switch; include on every artifact |
| `filter` | `filter.{css,js}` | Text search or tag-based filtering of displayed items |
| `slider` | `slider.css` | Range inputs updating CSS variables in real time (CSS-only; the JS is one-line per slider) |
| `scrollytelling` | `scrollytelling.{css,js}` | IntersectionObserver scroll animations, stagger reveals |

---

## Markup Contracts (what the component expects)

The component JS looks for specific class names and ARIA. If you change the markup, the component breaks silently.

### Tabs

```html
<div class="tab-bar" role="tablist" aria-label="Code examples">
  <button class="tab active" role="tab" aria-selected="true"
          id="tab-yaml" aria-controls="panel-yaml" data-tab="yaml">YAML</button>
  <button class="tab" role="tab" aria-selected="false"
          id="tab-route" aria-controls="panel-route" data-tab="route">Route</button>
</div>
<div class="tab-panel active" id="panel-yaml" role="tabpanel"
     aria-labelledby="tab-yaml"><!-- content --></div>
<div class="tab-panel" id="panel-route" role="tabpanel"
     aria-labelledby="tab-route" hidden><!-- content --></div>
```

Required: `data-tab` on the button matches the `id="panel-<value>"` on the panel. Active tab gets `.active` and `aria-selected="true"`. Hidden panels carry `hidden` attribute. Keyboard: Left/Right move between tabs.

### Collapsible (preferred: native `<details>`)

```html
<details>
  <summary>Section title</summary>
  <div>Content</div>
</details>
```

Use the `collapsible` component **only** when smooth height animation is required. The custom variant uses:

```html
<div class="accordion">
  <button class="accordion-trigger" aria-expanded="false"
          aria-controls="acc-1">Section title</button>
  <div class="accordion-panel" id="acc-1">
    <div class="accordion-inner">Content</div>
  </div>
</div>
```

Default state: collapsed (`aria-expanded="false"`). Open only when the content is primary, not supplementary.

### Drag and Drop

```html
<ul class="drag-list" aria-label="Sortable items" aria-live="polite">
  <li class="drag-item" draggable="true" tabindex="0" data-id="a">Item A</li>
  <li class="drag-item" draggable="true" tabindex="0" data-id="b">Item B</li>
  <li class="drag-item" draggable="true" tabindex="0" data-id="c">Item C</li>
</ul>
```

Required: `draggable="true"` on each item, `tabindex="0"` so keyboard users can focus. Component adds `.dragging` (during drag) and `.drag-over` (on drop target). `aria-live="polite"` on the parent announces reorders.

**Always provide a keyboard alternative** — drag is mouse-only. Pair with up/down buttons or an arrow-key handler.

### Copy Button

```html
<button class="copy-btn" type="button"
        data-copy-target="#config-yaml"
        aria-label="Copy YAML config to clipboard">Copy</button>
<pre id="config-yaml"><code>rate_limit:
  window: 60s
  max_requests: 100</code></pre>
```

Required: `data-copy-target` is a CSS selector for the source content. Component handles `navigator.clipboard.writeText()`, success feedback (text → "Copied!", `.copied` class for 1.5s).

### Keyboard Navigation

```html
<div class="slide-deck" data-keyboard-nav="slides">
  <section class="slide active">...</section>
  <section class="slide">...</section>
</div>
<button class="slide-prev" aria-label="Previous slide">‹</button>
<span class="slide-counter" aria-live="polite">1/N</span>
<button class="slide-next" aria-label="Next slide">›</button>
```

Required: container has `data-keyboard-nav="<scope>"`. Children that get the `.active` class are the navigable units. Counter updates via `aria-live="polite"` so AT announces position.

Keyboard: ArrowLeft / ArrowRight or ArrowUp / ArrowDown move; Home / End jump to first / last. **Skip when focus is in `<input>`, `<textarea>`, or `[contenteditable]`** so typing doesn't trigger navigation.

### Theme Toggle

```html
<button class="theme-toggle" type="button"
        aria-label="Toggle theme" aria-pressed="false">
  <span class="theme-icon-light">☀</span>
  <span class="theme-icon-dark">☾</span>
</button>
```

Component toggles `data-theme` attribute on `<html>` between `"light"` and `"dark"`. Both theme token sets must be in CSS (base + `[data-theme="dark"]` override) — handled automatically by the assembler when you request the `theme-toggle` component.

Position: fixed top-right corner, `z-index: 100`. Include on every artifact unless explicitly suppressed.

### Filter

```html
<div class="filter-bar" role="search">
  <input type="search" class="filter-input"
         placeholder="Filter items..." aria-label="Filter items by text">
  <div class="filter-tags" role="group" aria-label="Filter by category">
    <button class="filter-pill active" type="button"
            aria-pressed="true" data-filter="all">All</button>
    <button class="filter-pill" type="button"
            aria-pressed="false" data-filter="bug">Bug</button>
    <button class="filter-pill" type="button"
            aria-pressed="false" data-filter="feat">Feature</button>
  </div>
</div>
<ul class="filter-target">
  <li data-keywords="login auth" data-tags="bug">Login broken on Safari</li>
  <li data-keywords="export csv" data-tags="feat">CSV export for reports</li>
</ul>
```

Required: items declare searchable text via `data-keywords` and category via `data-tags`. Pills carry `data-filter` matching a tag value (or `all`). Component hides non-matching items via `.hidden` (`display: none !important`).

### Slider (CSS variable update)

```html
<input id="radius" type="range" min="0" max="24" value="6"
       oninput="document.querySelector('.preview').style.setProperty('--demo-radius', this.value + 'px'); this.nextElementSibling.textContent = this.value + 'px';">
<span class="value-display" aria-live="polite">6px</span>
```

CSS-only component. The JS is one inline `oninput` per slider — no separate event listeners needed. Value readout uses `aria-live="polite"`.

---

## Pattern Selection

| Question | Answer |
|---|---|
| Multiple views of the same data, one at a time? | `tabs` |
| Long sections, reader skims and expands selectively? | Native `<details>` first; `collapsible` only if you need animation |
| User reorders or drags between bins? | `drag-drop` + keyboard fallback |
| User wants to take content elsewhere? | `copy-button` |
| Sequential content (slides, cards, stories)? | `keyboard-nav` |
| Light/dark mode? | `theme-toggle` |
| Many items, user wants to narrow them? | `filter` |
| Continuous numeric value driving a preview? | `slider` (CSS-only) |
| Reveal sections as the user scrolls? | `scrollytelling` |

---

## Accessibility Rules (apply across all components)

| Rule | Implementation |
|---|---|
| Keyboard accessible | All interactive elements are `<button>` or `<a>` — never `<div onclick>` |
| ARIA labels | Icon-only buttons require `aria-label="<description>"` |
| Focus indicators | `:focus-visible` with 2px solid outline offset 2px (already in template CSS) |
| Reduced motion | Components disable transitions / animations under `prefers-reduced-motion: reduce` |
| Color is not the sole indicator | Pair color with icon, text, or shape |
| Roles and states | Tabs: `role="tablist"` + `aria-selected`. Accordions: `aria-expanded`. Filters: `aria-pressed` |
| Touch targets | Minimum 44×44px hit area on all interactive elements |
| Screen reader announcements | Use `aria-live="polite"` for dynamic changes (reorder, filter count, copy status, counter) |
| Don't hijack typing | Keyboard shortcuts skip when focus is in `<input>`, `<textarea>`, or `[contenteditable]` |
| Drag has a keyboard alternative | Drag-drop pairs with up/down buttons or arrow-key handler |

---

## Composition Guide (per shape)

| Shape | Typical Components |
|---|---|
| spec | `tabs,copy-button,theme-toggle` |
| code-review | `collapsible,filter,keyboard-nav,theme-toggle` |
| prototype | `slider,copy-button,theme-toggle` |
| report | `collapsible,theme-toggle,copy-button` |
| editor | `drag-drop,filter,copy-button` |
| data-viz | `filter,theme-toggle` |
| diagram | `copy-button,theme-toggle` |
| deck | `keyboard-nav,theme-toggle` |

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Hand-authoring tab switching JS in the artifact | Request the `tabs` component; the assembler injects the keyboard + ARIA logic |
| Custom drag-drop without keyboard fallback | Pair drag with up/down buttons; HTML5 drag is mouse-only |
| Inline `style` redefining `.tab.active` / `.drag-over` / `.copied` | Component CSS lives in `templates/components/<name>.css` — overriding causes drift |
| `<div onclick>` for filter pills | Use `<button>` for keyboard + AT |
| Copy feedback via `alert()` | Use the `copy-button` component's `.copied` state |
| Keyboard shortcuts firing inside text inputs | All bundled handlers guard against this; if you write your own, add the guard |
| Missing `aria-live="polite"` on dynamic readouts (counters, value displays, reorder feedback) | Add it — silent updates fail AT |
| Theme toggle that flickers on load | Set `data-theme` from `localStorage` synchronously before paint (the component handles this) |
| Both `<details>` AND a custom accordion in the same artifact | Pick one pattern; mixing them confuses keyboard users |
