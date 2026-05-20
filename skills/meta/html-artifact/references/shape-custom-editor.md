# Shape: Custom Editor

> **Shape**: editor | **Signal words**: reorder, triage, edit, tune prompt, pick values, configure, kanban
> CSS layout classes: `templates/shapes/editor.css` (injected by assemble-template.py)
> Components: `drag-drop`, `filter`, `copy-button`

Custom editors solve ONE problem with ONE interface, then export the result. Not a product — a single-use tool. The user came here to make a thing and leave with it. Every editor MUST end with an export bar; an editor without export is an unfinished sentence.

---

## Layout Description

A `.kanban` triage board is a 4-column grid with drag targets per column. A flag editor is a vertical list of `.toggle` rows. A prompt tuner is a split pane: editable text on one side, rendered preview on the other. Whatever the layout, the **export bar is the bottom horizon** of the page — sticky, always visible, always reachable.

Header sits above the work area with title and any global filters. Pending-changes indicator sits in the export bar so the user can see what they're about to commit.

---

## Canonical Markup Order (load-bearing rule)

| Order | Region | Purpose |
|---|---|---|
| 1 | `<header>` | Title + global filters / environment selector |
| 2 | Editing surface (`.kanban`, flag list, split pane, etc.) | The interactive work area |
| 3 | `.export-bar` (sticky to bottom of viewport) | **Mandatory.** Reset, Copy as Markdown, Copy as JSON |
| 4 | `.pending-badge` inside export bar | Auto-shows when there are unsaved changes |

Why export-bar last: the user works top-to-bottom; export is the conclusion. Sticky-to-bottom keeps it reachable without forcing it to compete with content. Hiding it behind a menu adds friction at the moment of completion.

### Skeleton (kanban triage)

```html
<body data-shape="editor" data-theme="birchline">
  <header>
    <h1>Triage backlog · 32 items</h1>
    <div class="filters"><!-- filter component --></div>
  </header>
  <main class="kanban" aria-label="Triage board">
    <section class="kanban-column" data-status="todo" aria-label="To do">
      <h2>To do <span class="count">12</span></h2>
      <article class="card" draggable="true"><!-- ticket --></article>
    </section>
    <section class="kanban-column" data-status="in-progress"><!-- ... --></section>
    <section class="kanban-column" data-status="review"><!-- ... --></section>
    <section class="kanban-column" data-status="done"><!-- ... --></section>
  </main>
  <footer class="export-bar" role="region" aria-label="Export">
    <span class="pending-badge" hidden>3 pending changes</span>
    <button class="btn-secondary" type="button">Reset</button>
    <button class="btn-primary" type="button">Copy as Markdown</button>
    <button class="btn-primary" type="button">Copy as JSON</button>
  </footer>
</body>
```

CSS lives in `templates/shapes/editor.css` — do not redefine `.export-bar`, `.btn-primary`, `.btn-secondary`, `.pending-badge`, `.kanban`, `.kanban-column`, `.toggle`, `.toggle-slider` inline.

---

## Editor Types

| Type | Use When | Key Elements |
|---|---|---|
| Kanban triage board | Categorize items into columns | 4-column `.kanban` grid, drag-drop, count badges, tag filters |
| Feature flag editor | Toggle binary settings per env | `.toggle` rows, dependency warnings, environment selector |
| Split-pane prompt tuner | Edit text with live preview | `contenteditable` editor, variable highlighting, sample render |
| Config editor | Pick from constrained options | Selects, radio groups, inline validation |
| List editor | Curate a dataset | Inline edit, add/remove rows, bulk select, CSV export |

---

## Section Types (worked examples)

### Kanban column with drag target

```html
<section class="kanban-column" data-status="review"
         aria-label="In review — 4 items">
  <header>
    <h2>In review</h2>
    <span class="count">4</span>
  </header>
  <article class="card" draggable="true" tabindex="0"
           data-id="t-142" aria-label="Ticket 142: Add CSRF middleware">
    <header class="card-header">
      <span class="card-id">#142</span>
      <span class="severity-badge attention">Attention</span>
    </header>
    <p class="card-title">Add CSRF middleware</p>
    <footer class="card-meta">
      <span>@alice</span><span>3 comments</span>
    </footer>
  </article>
</section>
```

Use for: triage boards. Each `.card` is `draggable="true"` AND `tabindex="0"` so keyboard users can move it via up/down buttons (drag is not keyboard-accessible). The column gets `.drag-over` while a card is hovering above it.

### Toggle row (feature flag)

```html
<div class="flag-row" role="group" aria-labelledby="flag-newcheckout-label">
  <div class="flag-info">
    <h3 id="flag-newcheckout-label">checkout.v2_enabled</h3>
    <p>Routes traffic to the new checkout pipeline.</p>
  </div>
  <span class="toggle">
    <input type="checkbox" id="flag-newcheckout"
           aria-describedby="flag-newcheckout-label">
    <span class="toggle-slider" aria-hidden="true"></span>
  </span>
</div>
```

Use for: flag editors, settings panels. Underlying `<input type="checkbox">` provides keyboard + AT semantics; the styled slider is decorative.

### Export bar

```html
<footer class="export-bar" role="region" aria-label="Export">
  <span class="pending-badge" hidden aria-live="polite">3 pending changes</span>
  <button class="btn-secondary" type="button"
          onclick="resetEdits()">Reset</button>
  <button class="btn-primary" type="button"
          onclick="copyAsMarkdown(this)">Copy as Markdown</button>
  <button class="btn-primary" type="button"
          onclick="copyAsJson(this)">Copy as JSON</button>
</footer>
```

Use for: every editor, every time. Reset is `.btn-secondary`; export actions are `.btn-primary`. The `.pending-badge` toggles visible when the user has unsaved changes (use `removeAttribute('hidden')`).

### Inline-edit list row

```html
<li class="list-row">
  <input type="checkbox" aria-label="Select row">
  <span class="cell" contenteditable="true">Migrate user auth</span>
  <span class="cell" contenteditable="true">@bob</span>
  <button class="btn-remove" type="button" aria-label="Remove row">×</button>
</li>
```

Use for: simple curated datasets. `contenteditable` cells stay editable; remove via `.btn-remove`. Keep the schema flat — once you need types beyond strings, switch to a config editor with selects.

---

## Export (MANDATORY)

Every editor includes export. Choose the formats that match the use case:

| Editor Kind | Export Formats |
|---|---|
| Kanban triage | "Copy as Markdown" (grouped lists by column) + "Copy as JSON" (structured) |
| Flag editor | "Copy diff" (only changed flags) + "Copy full state" |
| Prompt tuner | "Copy prompt" (raw text) + "Copy template + values" |
| Config editor | "Copy YAML" / "Copy JSON" — match the source format |
| List editor | "Copy as CSV" + "Copy as Markdown table" |

Visual feedback: button text → "Copied!", `.copied` class for 1.5s. Never `alert()`.

---

## ARIA / Accessibility

| Element | Required attributes | Why |
|---|---|---|
| `.kanban` | `aria-label="Triage board"` | Distinguishes the board region |
| `.kanban-column` | `aria-label="<column name> — <count> items"` | Column purpose announced |
| `.card` | `tabindex="0"`, `aria-label="<id>: <title>"`, `role="article"` (implicit) | Keyboard-focusable, AT-readable |
| Drag operations | Provide keyboard alternative (up/down buttons or arrow-key handler) | HTML5 drag is not keyboard-accessible |
| `.drag-over` state | Real `aria-live` announcement when reorder happens | Otherwise the change is silent for AT |
| `.toggle` | Real `<input type="checkbox">` inside; `.toggle-slider` is `aria-hidden` | Native semantics |
| Tag-filter buttons | `<button aria-pressed="true|false">` | Toggle state announced |
| `contenteditable` cell | `role="textbox"` (implicit), provide a visible `<label>` or `aria-labelledby` | Otherwise the field has no name |
| `.export-bar` | `role="region"`, `aria-label="Export"` | Landmark — keyboard users jump here |
| `.pending-badge` | `aria-live="polite"` | Count change announced when edits accumulate |
| Touch targets | All buttons / toggles ≥ 44×44px | The template enforces this |

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Editor without an export bar | Always include `.export-bar`; non-negotiable |
| Drag-drop with no keyboard alternative | Add up/down buttons OR arrow-key handler; HTML5 drag is mouse-only |
| `<div onclick>` for tag filters | Use `<button>` for keyboard + AT |
| `<input type="text">` for rich editing | Use `contenteditable` with variable-slot highlighting |
| Alert-based copy feedback | Inline visual feedback via `.copied` class |
| No reset button | Include reset in the export bar; users will edit destructively |
| Hardcoded data in HTML | Define data as a JS object, render dynamically — exporting is then a serialize step |
| Pending-changes badge always visible | Default `hidden`; show only when count > 0 |
| Export bar scrolls away | Sticky-positioned in the template; do not override `position` |
| Toggle slider with click handler on the `.toggle-slider` div | Click the underlying `<input>`; the slider is decorative |
| Inline `<style>` redefining `.export-bar` / `.kanban` / `.toggle` | Lives in `templates/shapes/editor.css` — touching it creates drift |

---

## Shape Selection

Use **editor** when the request matches: reorder, triage, kanban, edit config, tune prompt, pick values, toggle flags, curate list.

Do **not** use editor when:

- The user wants to tune visual parameters with live preview (use **prototype**)
- The user wants to compare predefined options (use **spec**)
- The user wants to view existing data (use **report** or **data-viz**)
- The user wants to annotate code, not edit it (use **code-review**)
