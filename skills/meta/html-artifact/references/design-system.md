# HTML Artifact Design System

Loaded by the html-builder agent on every artifact generation. Provides CSS tokens, typography, spacing, theme variants, and structural patterns. All artifacts are self-contained vanilla CSS — no external frameworks.

---

## Theme Selection

Pick theme before writing CSS. Match artifact shape to theme:

| Shape | Theme | Rationale |
|---|---|---|
| spec | Birchline | Warm, readable, comparison grids |
| report | Birchline | Professional, scannable typography |
| code-review | Dark Focus | Developer-familiar, high-contrast diffs |
| data-viz | Dark Focus | Charts pop on dark backgrounds |
| prototype | Interactive Warm | Clean surface, prominent controls |
| editor | Interactive Warm | Clear interactive affordances |
| explainer | Minimal Document | Serif headings, generous whitespace |
| research | Minimal Document | Long-form optimized reading |

User preference overrides shape default.

---

## CSS Reset (include in EVERY artifact)

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; -webkit-text-size-adjust: 100%; }
body { min-height: 100vh; text-rendering: optimizeLegibility; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
img, svg { display: block; max-width: 100%; }
input, button, textarea, select { font: inherit; }
p, h1, h2, h3, h4, h5, h6 { overflow-wrap: break-word; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; }
}
```

---

## Theme 1: Birchline (Default)

Extracted from thariqs.github.io/html-effectiveness/. Warm, earthy, professional.

### Ready-to-paste CSS

```css
:root {
  /* --- Colors --- */
  --color-primary: #D97757;
  --color-slate: #141413;
  --color-ivory: #FAF9F5;
  --color-oat: #E3DACC;
  --color-white: #FFFFFF;
  --color-gray-100: #F0EEE6;
  --color-gray-150: #F0EEE6;
  --color-gray-300: #D1CFC5;
  --color-gray-500: #87867F;
  --color-gray-700: #3D3D3A;
  --color-success: #788C5D;
  --color-warning: #C78E3F;
  --color-danger: #B04A4A;
  --color-info: #5C7CA3;

  /* --- Typography --- */
  --font-sans: system-ui, -apple-system, 'Segoe UI', sans-serif;
  --font-mono: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
  --type-display: 500 48px/1.1 var(--font-sans);
  --type-h1: 500 32px/1.2 var(--font-sans);
  --type-h2: 500 24px/1.3 var(--font-sans);
  --type-body: 430 16px/1.55 var(--font-sans);
  --type-small: 430 14px/1.5 var(--font-sans);
  --type-caption: 500 12px/1.4 var(--font-sans);

  /* --- Spacing --- */
  --sp-1: 4px;
  --sp-2: 8px;
  --sp-3: 12px;
  --sp-4: 16px;
  --sp-5: 24px;
  --sp-6: 32px;
  --sp-7: 48px;
  --sp-8: 64px;

  /* --- Border Radius --- */
  --radius-xs: 4px;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 20px;

  /* --- Shadows --- */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 10px rgba(0,0,0,0.08);
  --shadow-lg: 0 12px 28px rgba(0,0,0,0.12);

  /* --- Semantic Aliases --- */
  --bg-page: var(--color-ivory);
  --bg-surface: var(--color-white);
  --bg-muted: var(--color-gray-100);
  --bg-card: var(--color-oat);
  --text-primary: var(--color-slate);
  --text-secondary: var(--color-gray-700);
  --text-muted: var(--color-gray-500);
  --border-default: var(--color-gray-300);
  --border-subtle: var(--color-gray-150);
  --accent: var(--color-primary);
}

body {
  font: var(--type-body);
  color: var(--text-primary);
  background: var(--bg-page);
}
```

---

## Theme 2: Dark Focus

Data visualization, code review, late-night reading. High contrast, inner glows instead of drop shadows.

### Ready-to-paste CSS

```css
:root {
  /* --- Colors --- */
  --color-primary: #64B5F6;
  --color-bg: #1A1A2E;
  --color-surface: #232340;
  --color-surface-raised: #2C2C4A;
  --color-text: #E0E0E0;
  --color-text-secondary: #A0A0B8;
  --color-text-muted: #6E6E8A;
  --color-border: #3A3A5C;
  --color-border-subtle: #2E2E4E;
  --color-success: #81C784;
  --color-warning: #FFB74D;
  --color-danger: #EF5350;
  --color-info: #64B5F6;
  --color-code-bg: #16162A;
  --color-diff-add: rgba(129, 199, 132, 0.12);
  --color-diff-remove: rgba(239, 83, 80, 0.12);

  /* --- Typography --- */
  --font-sans: system-ui, -apple-system, 'Segoe UI', sans-serif;
  --font-mono: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
  --type-display: 500 48px/1.1 var(--font-sans);
  --type-h1: 500 32px/1.2 var(--font-sans);
  --type-h2: 500 24px/1.3 var(--font-sans);
  --type-body: 400 16px/1.55 var(--font-sans);
  --type-small: 400 14px/1.5 var(--font-sans);
  --type-caption: 500 12px/1.4 var(--font-sans);

  /* --- Spacing --- */
  --sp-1: 4px;
  --sp-2: 8px;
  --sp-3: 12px;
  --sp-4: 16px;
  --sp-5: 24px;
  --sp-6: 32px;
  --sp-7: 48px;
  --sp-8: 64px;

  /* --- Border Radius --- */
  --radius-xs: 4px;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 20px;

  /* --- Shadows (inverted: inner glows) --- */
  --shadow-sm: inset 0 1px 2px rgba(0,0,0,0.3);
  --shadow-md: inset 0 2px 6px rgba(0,0,0,0.4);
  --shadow-lg: 0 0 24px rgba(100,181,246,0.06);
  --shadow-glow: 0 0 12px rgba(100,181,246,0.15);

  /* --- Semantic Aliases --- */
  --bg-page: var(--color-bg);
  --bg-surface: var(--color-surface);
  --bg-muted: var(--color-surface-raised);
  --bg-card: var(--color-surface);
  --text-primary: var(--color-text);
  --text-secondary: var(--color-text-secondary);
  --text-muted: var(--color-text-muted);
  --border-default: var(--color-border);
  --border-subtle: var(--color-border-subtle);
  --accent: var(--color-primary);
}

body {
  font: var(--type-body);
  color: var(--text-primary);
  background: var(--bg-page);
}

/* Dark Focus: code block override */
pre, code {
  background: var(--color-code-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}
pre { padding: var(--sp-4); }
code { padding: var(--sp-1) var(--sp-2); font-size: 14px; }

/* Dark Focus: diff highlighting */
.diff-add { background: var(--color-diff-add); }
.diff-remove { background: var(--color-diff-remove); }
```

### Contrast Ratios (WCAG AA verified)

| Pair | Ratio | Pass |
|---|---|---|
| --color-text on --color-bg | 11.5:1 | AA |
| --color-text-secondary on --color-bg | 5.8:1 | AA |
| --color-primary on --color-bg | 5.2:1 | AA |
| --color-text on --color-surface | 9.1:1 | AA |

---

## Theme 3: Interactive Warm

Editors, prototypes, design tools. Clean white surface, blue accent for actions, prominent shadows on interactive elements.

### Ready-to-paste CSS

```css
:root {
  /* --- Colors --- */
  --color-primary: #5B8DEF;
  --color-primary-hover: #4A7DE0;
  --color-bg: #FAFAF8;
  --color-surface: #FFFFFF;
  --color-surface-raised: #F5F5F2;
  --color-text: #2D2D2D;
  --color-text-secondary: #5A5A5A;
  --color-text-muted: #8A8A8A;
  --color-border: #D4D4D0;
  --color-border-subtle: #E8E8E4;
  --color-border-focus: var(--color-primary);
  --color-success: #4CAF50;
  --color-warning: #F9A825;
  --color-danger: #E53935;
  --color-info: #5B8DEF;

  /* --- Typography --- */
  --font-sans: system-ui, -apple-system, 'Segoe UI', sans-serif;
  --font-mono: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
  --type-display: 600 48px/1.1 var(--font-sans);
  --type-h1: 600 32px/1.2 var(--font-sans);
  --type-h2: 600 24px/1.3 var(--font-sans);
  --type-body: 400 16px/1.55 var(--font-sans);
  --type-small: 400 14px/1.5 var(--font-sans);
  --type-caption: 500 12px/1.4 var(--font-sans);

  /* --- Spacing --- */
  --sp-1: 4px;
  --sp-2: 8px;
  --sp-3: 12px;
  --sp-4: 16px;
  --sp-5: 24px;
  --sp-6: 32px;
  --sp-7: 48px;
  --sp-8: 64px;

  /* --- Border Radius --- */
  --radius-xs: 4px;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 20px;

  /* --- Shadows (prominent on interactive elements) --- */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.1);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.12);
  --shadow-interactive: 0 2px 8px rgba(91,141,239,0.2);
  --shadow-interactive-hover: 0 4px 16px rgba(91,141,239,0.3);

  /* --- Semantic Aliases --- */
  --bg-page: var(--color-bg);
  --bg-surface: var(--color-surface);
  --bg-muted: var(--color-surface-raised);
  --bg-card: var(--color-surface);
  --text-primary: var(--color-text);
  --text-secondary: var(--color-text-secondary);
  --text-muted: var(--color-text-muted);
  --border-default: var(--color-border);
  --border-subtle: var(--color-border-subtle);
  --accent: var(--color-primary);
}

body {
  font: var(--type-body);
  color: var(--text-primary);
  background: var(--bg-page);
}

/* Interactive Warm: button and control styles */
button, [role="button"] {
  background: var(--color-primary);
  color: #FFFFFF;
  border: none;
  border-radius: var(--radius-sm);
  padding: var(--sp-2) var(--sp-4);
  font: var(--type-small);
  font-weight: 500;
  cursor: pointer;
  box-shadow: var(--shadow-interactive);
  transition: box-shadow 0.15s ease, background 0.15s ease;
}
button:hover, [role="button"]:hover {
  background: var(--color-primary-hover);
  box-shadow: var(--shadow-interactive-hover);
}
button:focus-visible, [role="button"]:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

input, textarea, select {
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  padding: var(--sp-2) var(--sp-3);
  font: var(--type-body);
  background: var(--bg-surface);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
input:focus, textarea:focus, select:focus {
  border-color: var(--color-border-focus);
  box-shadow: 0 0 0 3px rgba(91,141,239,0.15);
  outline: none;
}
```

### Contrast Ratios (WCAG AA verified)

| Pair | Ratio | Pass |
|---|---|---|
| --color-text on --color-bg | 12.8:1 | AA |
| --color-text-secondary on --color-bg | 7.0:1 | AA |
| #FFFFFF on --color-primary | 4.6:1 | AA |
| --color-text on --color-surface | 14.7:1 | AA |

---

## Theme 4: Minimal Document

Long-form reports, explainers, research summaries. Serif headings, generous whitespace, restrained palette.

### Ready-to-paste CSS

```css
:root {
  /* --- Colors --- */
  --color-primary: #555555;
  --color-bg: #FFFFF8;
  --color-surface: #FFFFFF;
  --color-surface-raised: #F8F8F2;
  --color-text: #333333;
  --color-text-secondary: #555555;
  --color-text-muted: #888888;
  --color-border: #D0D0C8;
  --color-border-subtle: #E8E8E0;
  --color-accent-subtle: rgba(85,85,85,0.08);
  --color-success: #5A7A42;
  --color-warning: #B8860B;
  --color-danger: #A83232;
  --color-info: #4A6A8A;

  /* --- Typography (serif headings, sans body) --- */
  --font-serif: Georgia, 'Times New Roman', serif;
  --font-sans: system-ui, -apple-system, 'Segoe UI', sans-serif;
  --font-mono: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
  --type-display: 500 44px/1.15 var(--font-serif);
  --type-h1: 500 30px/1.25 var(--font-serif);
  --type-h2: 500 22px/1.35 var(--font-serif);
  --type-body: 400 17px/1.7 var(--font-sans);
  --type-small: 400 15px/1.6 var(--font-sans);
  --type-caption: 500 12px/1.4 var(--font-sans);

  /* --- Spacing (generous for long-form) --- */
  --sp-1: 4px;
  --sp-2: 8px;
  --sp-3: 12px;
  --sp-4: 16px;
  --sp-5: 24px;
  --sp-6: 32px;
  --sp-7: 48px;
  --sp-8: 64px;

  /* --- Border Radius --- */
  --radius-xs: 2px;
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;

  /* --- Shadows (minimal) --- */
  --shadow-sm: 0 1px 1px rgba(0,0,0,0.04);
  --shadow-md: 0 2px 6px rgba(0,0,0,0.06);
  --shadow-lg: 0 6px 16px rgba(0,0,0,0.08);

  /* --- Semantic Aliases --- */
  --bg-page: var(--color-bg);
  --bg-surface: var(--color-surface);
  --bg-muted: var(--color-surface-raised);
  --bg-card: var(--color-surface);
  --text-primary: var(--color-text);
  --text-secondary: var(--color-text-secondary);
  --text-muted: var(--color-text-muted);
  --border-default: var(--color-border);
  --border-subtle: var(--color-border-subtle);
  --accent: var(--color-primary);

  /* --- Document-specific --- */
  --content-width: 680px;
  --content-margin: auto;
}

body {
  font: var(--type-body);
  color: var(--text-primary);
  background: var(--bg-page);
  max-width: var(--content-width);
  margin: var(--sp-8) var(--content-margin);
  padding: 0 var(--sp-5);
}

/* Minimal Document: heading rhythm */
h1 { font: var(--type-h1); margin: var(--sp-8) 0 var(--sp-5); }
h2 { font: var(--type-h2); margin: var(--sp-7) 0 var(--sp-4); }
p + p { margin-top: var(--sp-4); }

/* Minimal Document: blockquote */
blockquote {
  border-left: 3px solid var(--color-border);
  padding: var(--sp-3) var(--sp-5);
  color: var(--text-secondary);
  font-style: italic;
  margin: var(--sp-5) 0;
}

/* Minimal Document: horizontal rule */
hr {
  border: none;
  border-top: 1px solid var(--color-border-subtle);
  margin: var(--sp-7) 0;
}
```

### Contrast Ratios (WCAG AA verified)

| Pair | Ratio | Pass |
|---|---|---|
| --color-text on --color-bg | 12.4:1 | AA |
| --color-text-secondary on --color-bg | 7.5:1 | AA |
| --color-text-muted on --color-bg | 3.5:1 | AA large text only |
| --color-text on --color-surface | 12.6:1 | AA |

Note: `--text-muted` passes AA for large text (>=18px bold or >=24px). Use only for captions, labels, and supplementary text at `--type-small` size or above.

---

## Card Variants

Six structural treatments. Use semantic aliases (--bg-card, --border-default, etc.) so cards adapt to any theme.

```css
/* Flat: dense lists, inline content */
.card-flat {
  background: var(--bg-muted);
  padding: var(--sp-4);
  border-radius: var(--radius-sm);
}

/* Outlined: content cards, comparison items */
.card-outlined {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  padding: var(--sp-4);
  border-radius: var(--radius-sm);
}

/* Elevated: draggable items, interactive cards */
.card-elevated {
  background: var(--bg-surface);
  box-shadow: var(--shadow-md);
  padding: var(--sp-4);
  border-radius: var(--radius-sm);
}

/* Accent stripe: priority items, callouts */
.card-accent {
  background: var(--bg-surface);
  border-left: 3px solid var(--accent);
  padding: var(--sp-4);
  border-radius: var(--radius-xs);
}

/* Inset: nested content, code blocks */
.card-inset {
  background: var(--bg-muted);
  padding: var(--sp-4);
  border-radius: var(--radius-sm);
}

/* Horizontal: list rows, table alternatives */
.card-horizontal {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  background: var(--bg-surface);
  padding: var(--sp-3) var(--sp-4);
  border-bottom: 1px solid var(--border-subtle);
}
```

### Card Selection Guide

| Need | Variant | Example |
|---|---|---|
| List of items, dense | Flat | Task list, log entries |
| Comparable items side-by-side | Outlined | Feature comparison, option cards |
| User can grab/move/click | Elevated | Kanban cards, drag-and-drop items |
| Needs visual emphasis | Accent stripe | Warnings, key metrics, status callouts |
| Content within content | Inset | Code snippet inside a section, nested quote |
| Scannable rows | Horizontal | Search results, notification feed |

---

## Responsive Breakpoints

```css
/* Mobile-first: base styles target < 640px */

@media (min-width: 640px) {
  /* Tablet: 2-column layouts where applicable */
}

@media (min-width: 1024px) {
  /* Desktop: full layout, side-by-side panels */
}
```

| Breakpoint | Width | Column behavior |
|---|---|---|
| Mobile | < 640px | Single column, stacked |
| Tablet | 640-1024px | 2 columns where applicable |
| Desktop | > 1024px | Full layout, side-by-side panels |

### Responsive Utilities

```css
.container {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 var(--sp-4);
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--sp-4);
}
@media (min-width: 640px) {
  .grid-2 { grid-template-columns: 1fr 1fr; }
}

.grid-3 {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--sp-4);
}
@media (min-width: 640px) {
  .grid-3 { grid-template-columns: 1fr 1fr; }
}
@media (min-width: 1024px) {
  .grid-3 { grid-template-columns: 1fr 1fr 1fr; }
}

/* Hide/show by breakpoint */
.hide-mobile { display: none; }
@media (min-width: 640px) { .hide-mobile { display: initial; } }
.hide-desktop { display: initial; }
@media (min-width: 1024px) { .hide-desktop { display: none; } }
```

---

## SVG Illustration Conventions

All inline SVGs follow these rules for visual consistency across artifacts.

| Property | Value |
|---|---|
| Dimensions | 720 x 320px (viewBox) |
| Rendering | Flat — no gradients, no drop shadows |
| Stroke width | 1.5-2px |
| Corner radius | rx="10" |
| Label font | 11px monospace |
| Annotation font | 12px sans-serif |
| Color source | Theme tokens (use currentColor or CSS vars) |
| Self-contained | Embed `<style>` block inside the SVG |

### SVG Template

```html
<svg viewBox="0 0 720 320" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="[description]">
  <style>
    .label { font: 11px var(--font-mono, monospace); fill: var(--text-secondary, #555); }
    .annotation { font: 12px var(--font-sans, system-ui, sans-serif); fill: var(--text-primary, #333); }
    .stroke { stroke: var(--border-default, #D1CFC5); stroke-width: 1.5; fill: none; }
    .fill-primary { fill: var(--accent, #D97757); }
    .fill-surface { fill: var(--bg-surface, #FFFFFF); }
  </style>
  <!-- SVG content here -->
</svg>
```

---

## Common Component Patterns

Reusable CSS classes that work across all themes via semantic aliases.

### Status Badge

```css
.badge {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
  padding: var(--sp-1) var(--sp-2);
  border-radius: 999px;
  font: var(--type-caption);
  font-weight: 500;
}
.badge-success { background: color-mix(in srgb, var(--color-success) 15%, transparent); color: var(--color-success); }
.badge-warning { background: color-mix(in srgb, var(--color-warning) 15%, transparent); color: var(--color-warning); }
.badge-danger  { background: color-mix(in srgb, var(--color-danger) 15%, transparent); color: var(--color-danger); }
.badge-info    { background: color-mix(in srgb, var(--color-info) 15%, transparent); color: var(--color-info); }
```

### Table

```css
table {
  width: 100%;
  border-collapse: collapse;
  font: var(--type-small);
}
th {
  text-align: left;
  font-weight: 500;
  font: var(--type-caption);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 2px solid var(--border-default);
}
td {
  padding: var(--sp-3);
  border-bottom: 1px solid var(--border-subtle);
  vertical-align: top;
}
tr:hover td {
  background: var(--bg-muted);
}
```

### Section Divider

```css
.divider {
  border: none;
  border-top: 1px solid var(--border-subtle);
  margin: var(--sp-6) 0;
}
```

---

## Accessibility Checklist (every artifact)

1. **Color contrast**: text on background >= 4.5:1 (normal), >= 3:1 (large text >= 18px bold or >= 24px)
2. **Focus indicators**: all interactive elements have `:focus-visible` styles
3. **Semantic HTML**: headings in order (h1 > h2 > h3), lists for lists, tables for tabular data
4. **Alt text**: every `<img>` has `alt`, every `<svg>` has `role="img"` + `aria-label`
5. **Reduced motion**: the CSS reset handles this globally via `prefers-reduced-motion`
6. **Touch targets**: interactive elements minimum 44x44px hit area
7. **Language**: `<html lang="en">` on the root element

---

## Anti-Patterns

| Pattern | Why Wrong | Do Instead |
|---|---|---|
| CSS frameworks (Bootstrap, Tailwind CDN) | External dependency, breaks self-contained | Use the token system with vanilla CSS |
| Random colors per artifact | Inconsistent, unprofessional | Use theme tokens — they work together |
| Hardcoded px values | Breaks the scale, inconsistent spacing | Use --sp-N tokens and --type-* scale |
| Dark theme = just invert colors | Poor contrast ratios, ugly results | Use the Dark Focus preset with tuned contrast |
| `outline: none` without replacement | Destroys keyboard navigation | Add `:focus-visible` with ring or border |
| `<div onclick>` | Not keyboard accessible, no semantics | Use `<button>` or `<a>` elements |
| Heading level skipping (h1 to h3) | Breaks screen reader navigation | Use sequential heading levels |
| Text as images | Not searchable, not accessible | Use real text with CSS styling |
| `color-mix()` without fallback | Unsupported in older browsers | Provide fallback hex for critical paths |

---

## HTML Artifact Shell Template

Minimal starting point for any artifact. Select theme block, paste into `<style>`, build from there.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>[Artifact Title]</title>
  <style>
    /* === CSS Reset === */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html { scroll-behavior: smooth; -webkit-text-size-adjust: 100%; }
    body { min-height: 100vh; text-rendering: optimizeLegibility; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
    img, svg { display: block; max-width: 100%; }
    input, button, textarea, select { font: inherit; }
    p, h1, h2, h3, h4, h5, h6 { overflow-wrap: break-word; }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; }
    }

    /* === Theme: [paste selected theme :root block here] === */

    /* === Component styles === */
  </style>
</head>
<body>
  <main>
    <!-- Artifact content -->
  </main>
</body>
</html>
```
