# Shape: Design Prototype

> **Shape**: prototype | **Signal words**: tune, adjust, animation sandbox, component variants, design system preview
> CSS layout classes: `templates/shapes/prototype.css` (injected by assemble-template.py)

---

## Core Principle

Prototypes are INTERACTIVE. Every parameter updates the preview in real time. Every prototype ends with an export mechanism (Copy Parameters, Copy CSS, Copy Config).

---

## Layout Patterns

| Layout | Use When | Structure |
|---|---|---|
| Split panel | Controls + live preview | Left: controls (300px sticky), Right: preview (flex: 1) |
| Contact sheet | Variant comparison | Grid of cells, each with rendered preview + label |
| Sandbox | Animation tuning | Top: preview with play/reset, Bottom: control panel |
| Swatch grid | Color/token display | Grid of clickable swatches with copy-on-click |

---

## Key CSS Classes (from templates/shapes/prototype.css)

| Class | Purpose |
|---|---|
| `.prototype-layout` | 2-column grid (controls + preview) |
| `.controls-panel` | Sticky sidebar for sliders/selects/toggles |
| `.preview-surface` | Live preview area |
| `.control-row` | Flex row: label + input + value readout |
| `.value-display` | Monospace value readout (user-selectable) |
| `.control-group-label` | Section divider within controls |
| `.export-btn` | Full-width accent button with `.copied` state |
| `.variant-grid` | Auto-fill grid for contact sheet cells |
| `.variant-cell` | Bordered cell with preview + label |

---

## Control Types

| Control | When | HTML Element |
|---|---|---|
| Slider | Continuous numeric values (padding, radius, opacity) | `<input type="range">` with `oninput` |
| Select | Constrained choices (easing curves, font families) | `<select>` with `onchange` |
| Toggle | Boolean on/off (shadow, border, animation) | `<input type="checkbox">` in toggle wrapper |
| Color picker | Color values | `<input type="color">` with hex readout |

All controls update CSS custom properties on the preview element via `style.setProperty()`.

---

## Export (MANDATORY)

Every prototype MUST include at least one export button:
- **Copy Parameters** as JSON: collect all control values
- **Copy as CSS Variables**: emit `:root { --var: value; }` block
- Visual feedback: button text changes to "Copied!", background goes success color for 1.5s

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Prototype without export | Always include Copy Parameters button |
| Controls not updating in real time | Use `oninput` (not `onchange`) for sliders |
| No reduced-motion toggle | Offer explicit toggle for animation testing |
| `<div onclick>` for swatches | Use `<button>` with `aria-label` |
| Preview doesn't reflect all controls | Every control must map to a CSS property or DOM change |
| Missing keyboard support for drag reorder | Provide up/down buttons as alternative |

---

## Accessibility

| Requirement | Implementation |
|---|---|
| Slider labels | Every `<input type="range">` has a `<label>` with matching `for` |
| Live readouts | Value displays use `aria-live="polite"` |
| Keyboard nav | All controls reachable via Tab; sliders adjustable via arrow keys (native) |
| Color swatches | Use `<button>` with `aria-label` including color name and hex |
| Toggle switches | Underlying `<input type="checkbox">` provides semantics; track is `aria-hidden` |
| Touch targets | All controls minimum 44x44px hit area |
