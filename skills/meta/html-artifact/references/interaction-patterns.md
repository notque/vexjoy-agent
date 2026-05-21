# Interaction Patterns

Shared interactive patterns used across artifact shapes. CSS/JS implementations are in `templates/components/` -- injected by `assemble-template.py --components <name>`. This file covers when to use each pattern, accessibility rules, and composition guidance.

---

## Available Components

Request via `--components` flag. Multiple: `--components tabs,collapsible,copy-button`.

| Component | File | Use When |
|---|---|---|
| `tabs` | `tabs.{css,js}` | Multiple views of same data; mutually exclusive panels |
| `collapsible` | `collapsible.{css,js}` | Progressive disclosure; long sections users scan selectively |
| `drag-drop` | `drag-drop.{css,js}` | Reordering lists; kanban columns; priority sorting |
| `copy-button` | `copy-button.{css,js}` | Any content the user might paste elsewhere |
| `keyboard-nav` | `keyboard-nav.{css,js}` | Sequential content (slides, cards) navigated by arrow keys |
| `theme-toggle` | `theme-toggle.{css,js}` | Light/dark mode switch; include on every artifact |
| `filter` | `filter.{css,js}` | Text search or tag-based filtering of displayed items |
| `slider` | `slider.css` | Range inputs updating CSS variables in real-time |

---

## Pattern Descriptions

### Tabs
- HTML: `role="tablist"` container with `role="tab"` buttons + `role="tabpanel"` divs
- Active tab gets `aria-selected="true"` and `.active` class
- Panels are `display: none` by default, `.active` shows them
- Keyboard: Tab focuses the tab bar, Left/Right moves between tabs

### Collapsible
- **Preferred:** Native `<details>/<summary>` (zero JS, browser-native behavior)
- **Alternative:** Custom accordion with `aria-expanded`, `aria-controls`, animated `max-height`
- Default state: collapsed. Open only when content is primary, not supplementary
- Keyboard: Enter/Space toggles open/closed

### Drag and Drop
- HTML5 `draggable="true"` with `dragstart`, `dragover`, `drop`, `dragend` events
- Visual feedback: `.dragging` (opacity 0.35, rotate 2deg), `.drag-over` (accent border + shadow)
- Always provide keyboard alternative (up/down buttons) for accessibility
- Announce reorder to screen readers via `aria-live` region

### Copy to Clipboard
- Uses `navigator.clipboard.writeText()` with visual feedback
- Button text changes to "Copied!" for 1.5s, `.copied` class adds success color
- Never use `alert()` for copy feedback

### Keyboard Navigation
- Arrow keys navigate sequential content (slides, cards, items)
- Track current index, wrap around at boundaries
- Skip arrow-key handling when the user is typing in input/textarea
- Update counter display (`1/N`) on navigation

### Theme Toggle
- Toggles `data-theme` attribute on `<html>` between `"light"` and `"dark"`
- Light icons/dark icons swap via CSS `display` rules
- Position: fixed top-right corner, `z-index: 100`
- Both theme token sets must be in CSS (base + `[data-theme="dark"]` override)

### Filter
- **Text search:** `input[type="search"]` filters items by `textContent` + `data-keywords`
- **Tag filter:** `<button>` pills toggle categories; `.active` gets accent background
- Hidden items get `.hidden` class (`display: none !important`)
- Include clear/reset mechanism

### Slider (CSS Variable Update)
- `<input type="range">` with `oninput` updating a CSS custom property
- Value readout as `<span>` next to the slider
- One line of JS per slider -- no separate event listeners needed

---

## Accessibility Rules

| Rule | Implementation |
|---|---|
| Keyboard accessible | All interactive elements are `<button>` or `<a>`, never `<div onclick>` |
| ARIA labels | Icon-only buttons use `aria-label="Description"` |
| Focus indicators | `:focus-visible` with 2px solid outline offset 2px |
| Reduced motion | Global reset disables all animation/transition |
| Color not sole indicator | Pair color with icon, text, or shape |
| Roles and states | Tab bars: `role="tablist"` + `aria-selected`. Accordions: `aria-expanded`. Filters: `aria-label` |
| Touch targets | Minimum 44x44px hit area |
| Screen reader announcements | Use `aria-live="polite"` region for dynamic changes (drag reorder, filter count, copy status) |

---

## Composition Guide

| Artifact Need | Components to Request |
|---|---|
| Report with sections | `collapsible,theme-toggle,copy-button` |
| Spec with code comparison | `tabs,copy-button,theme-toggle` |
| Interactive editor | `drag-drop,filter,copy-button` |
| Data dashboard | `filter,theme-toggle` |
| Slide deck | `keyboard-nav,theme-toggle` |
| Prototype with controls | `slider,theme-toggle,copy-button` |
