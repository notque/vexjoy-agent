# Shape: Custom Editor

> **Shape**: editor | **Signal words**: reorder, triage, edit, tune, pick, configure
> CSS layout classes: `templates/shapes/editor.css` (injected by assemble-template.py)

---

## Core Principle

Custom editors solve ONE problem with ONE interface, then export the result. Not a product -- a single-use tool. Every editor MUST end with an export mechanism (Copy as Markdown, Copy as JSON, or both).

---

## Editor Types

| Type | Use When | Key Elements |
|---|---|---|
| Kanban triage board | Categorize items into columns | 4-column drag-drop grid, tag filters, count badges |
| Feature flag editor | Toggle binary settings | Toggle switches, dependency warnings, diff export |
| Split-pane prompt tuner | Edit text with live preview | Contenteditable, variable highlighting, sample rendering |
| Config editor | Pick from constrained options | Selects, radio groups, validation, export |
| List editor | Curate a dataset | Inline edit, add/remove rows, bulk select, CSV export |

---

## Key CSS Classes (from templates/shapes/editor.css)

| Class | Purpose |
|---|---|
| `.export-bar` | Sticky bottom bar with export buttons (MANDATORY) |
| `.btn-primary`, `.btn-secondary` | Action buttons |
| `.pending-badge` | Change count indicator |
| `.kanban` | 4-column grid for triage boards |
| `.kanban-column` | Drop target with `.drag-over` state |
| `.toggle` + `.toggle-slider` | iOS-style toggle switch |

---

## Export Bar (MANDATORY)

Every editor gets a sticky bottom export bar. No exceptions.

Structure: Reset button (secondary) + Copy as Markdown (primary) + Copy as JSON (primary). Pending changes badge on the left (auto-hiding when count is 0).

Use `navigator.clipboard.writeText()` with visual feedback (button text "Copied!", success background for 1.5s).

---

## Composition Guide

| Request | Sections |
|---|---|
| "Triage tickets" | Header + Filter + Kanban Board + Export Bar |
| "Toggle feature flags" | Header + Environment Select + Flag List + Export Bar |
| "Tune this prompt" | Header + Split Pane (editor + preview) + Export Bar |
| "Edit this config" | Header + Form Fields + Validation Feedback + Export Bar |

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Editor without export | Always include the sticky export bar |
| `<input type="text">` for rich editing | Use `contenteditable` with variable slot highlighting |
| Alert-based feedback | Use inline visual feedback (button text change) |
| No reset button | Always include reset in export bar |
| Hardcoded data in HTML | Define data as a JS object, render dynamically |
| `<div>` for tag filters | Use `<button>` elements for keyboard accessibility |
| No pending changes indicator | Show change count badge in export bar |
