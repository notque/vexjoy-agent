# Shape Reference: Code Review

> **Shape**: code-review | **Signal words**: review PR, diff, annotate, code review, explain code, understand module, pr writeup
> **Gallery basis**: 03 (Annotated PR), 04 (Module map), 17 (PR writeup for reviewers)
> **Generated**: 2026-05-08

---

## Design System Tokens (Birchline)

Same token set as all shape references. Embed in `<style>` at top of artifact.

```css
:root {
  /* Birchline palette */
  --color-clay: #D97757;
  --color-slate: #141413;
  --color-ivory: #FAF9F5;
  --color-primary: var(--color-clay);
  --color-bg: var(--color-ivory);
  --color-text: var(--color-slate);

  /* Grays */
  --color-gray-100: #F0EFEB;
  --color-gray-200: #E2E0DA;
  --color-gray-300: #C8C5BC;
  --color-gray-400: #A9A69D;
  --color-gray-500: #7A776F;
  --color-gray-600: #52504A;

  /* Semantic */
  --color-danger: #B04A4A;
  --color-warning: #C78E3F;
  --color-success: #788C5D;
  --color-info: #5B7FA5;

  /* Severity-specific */
  --color-blocking: var(--color-danger);
  --color-attention: var(--color-warning);
  --color-look: #C4A742;
  --color-safe: var(--color-success);

  /* Diff colors */
  --diff-add-bg: #e6ffec;
  --diff-add-border: #abf2bc;
  --diff-del-bg: #ffebe9;
  --diff-del-border: #ffc1ba;
  --diff-ctx-bg: transparent;

  /* Spacing scale (4px base) */
  --sp-1: 4px; --sp-2: 8px; --sp-3: 12px; --sp-4: 16px;
  --sp-5: 20px; --sp-6: 24px; --sp-7: 32px; --sp-8: 40px;
  --sp-9: 48px; --sp-10: 64px;

  /* Typography */
  --font-body: 'Instrument Sans', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  --type-hero: clamp(2rem, 4vw, 3rem);
  --type-h2: clamp(1.25rem, 2.5vw, 1.75rem);
  --type-h3: 1.125rem;
  --type-body: 0.9375rem;
  --type-small: 0.8125rem;
  --type-caption: 0.75rem;

  /* Radius */
  --radius-xs: 4px;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
}
```

---

## Severity System

Central to every code review artifact. Used in badges, annotations, file nav, and risk map.

| Level | Variable | Hex | Badge | Use For |
|---|---|---|---|---|
| Blocking | `--color-blocking` | #B04A4A | `blocking` | Must fix before merge |
| Needs Attention | `--color-attention` | #C78E3F | `attention` | Important, non-blocking |
| Worth a Look | `--color-look` | #C4A742 | `look` | Minor improvement |
| Safe | `--color-safe` | #788C5D | `safe` | No concerns |

### Severity Badge CSS

```css
.severity-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  font-size: var(--type-caption);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.severity-badge.blocking {
  background: color-mix(in srgb, var(--color-blocking) 12%, transparent);
  color: var(--color-blocking);
}
.severity-badge.attention {
  background: color-mix(in srgb, var(--color-attention) 12%, transparent);
  color: var(--color-attention);
}
.severity-badge.look {
  background: color-mix(in srgb, var(--color-look) 12%, transparent);
  color: var(--color-look);
}
.severity-badge.safe {
  background: color-mix(in srgb, var(--color-safe) 12%, transparent);
  color: var(--color-safe);
}
```

---

## Page Shell

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title><!-- PR title --></title>
  <style>/* tokens + all CSS below */</style>
</head>
<body>
  <div class="review-layout">
    <nav class="file-nav" aria-label="File navigation">
      <!-- Jump links -->
    </nav>
    <main class="review-main">
      <header class="pr-summary"><!-- PR header --></header>
      <section class="risk-map"><!-- Severity overview --></section>
      <div class="diff-files"><!-- File diffs + annotations --></div>
    </main>
  </div>
  <script>/* interaction JS */</script>
</body>
</html>
```

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; }
body {
  font-family: var(--font-body);
  font-size: var(--type-body);
  line-height: 1.6;
  color: var(--color-text);
  background: var(--color-bg);
}

/* Two-column layout: side nav + main content */
.review-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  min-height: 100vh;
}

/* On mobile: stack nav above main */
@media (max-width: 768px) {
  .review-layout {
    grid-template-columns: 1fr;
  }
}
```

---

## Pattern 1: PR Summary Header

### HTML

```html
<header class="pr-summary">
  <div class="pr-title-row">
    <h1>Refactor auth flow to httpOnly cookies</h1>
    <span class="pr-number">#42</span>
  </div>
  <div class="pr-meta">
    <span class="pr-meta-item">
      <strong>Author</strong> @alice
    </span>
    <span class="pr-meta-item">
      <strong>Branch</strong> feat/auth-cookies &rarr; main
    </span>
    <span class="pr-meta-item">
      <strong>Files</strong> 12 changed
    </span>
    <span class="pr-meta-item pr-stats">
      <span class="stat-add">+580</span>
      <span class="stat-del">&minus;220</span>
    </span>
  </div>
  <p class="pr-description">
    Migrates token storage from localStorage to httpOnly cookies.
    Adds CSRF protection and dual-read middleware for backward compatibility.
  </p>
</header>
```

### CSS

```css
.pr-summary {
  padding: var(--sp-7) var(--sp-7) var(--sp-6);
  border-bottom: 1px solid var(--color-gray-200);
}
.pr-title-row {
  display: flex;
  align-items: baseline;
  gap: var(--sp-3);
  flex-wrap: wrap;
}
.pr-title-row h1 {
  font-size: var(--type-h2);
  font-weight: 700;
  line-height: 1.2;
}
.pr-number {
  font-family: var(--font-mono);
  font-size: var(--type-body);
  color: var(--color-gray-400);
  font-weight: 500;
}
.pr-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-4);
  margin-top: var(--sp-3);
  font-size: var(--type-small);
  color: var(--color-gray-500);
}
.pr-meta-item strong {
  font-weight: 600;
  color: var(--color-gray-600);
  margin-right: var(--sp-1);
}
.pr-stats { font-family: var(--font-mono); }
.stat-add { color: var(--color-success); font-weight: 600; }
.stat-del { color: var(--color-danger); font-weight: 600; }
.pr-description {
  margin-top: var(--sp-4);
  color: var(--color-gray-600);
  font-size: var(--type-small);
  max-width: 680px;
}
```

---

## Pattern 2: Risk Map (Severity Overview)

Shows at-a-glance severity distribution across all files. Appears below PR header, above file diffs.

### HTML

```html
<section class="risk-map" aria-label="File risk summary">
  <h2 class="risk-map-title">Risk Overview</h2>
  <div class="risk-bars">
    <div class="risk-row" data-severity="blocking">
      <span class="risk-indicator blocking"></span>
      <span class="risk-label">Blocking</span>
      <div class="risk-bar-track">
        <div class="risk-bar-fill blocking" style="width: 16.6%"></div>
      </div>
      <span class="risk-count">2</span>
    </div>
    <div class="risk-row" data-severity="attention">
      <span class="risk-indicator attention"></span>
      <span class="risk-label">Needs Attention</span>
      <div class="risk-bar-track">
        <div class="risk-bar-fill attention" style="width: 41.6%"></div>
      </div>
      <span class="risk-count">5</span>
    </div>
    <div class="risk-row" data-severity="look">
      <span class="risk-indicator look"></span>
      <span class="risk-label">Worth a Look</span>
      <div class="risk-bar-track">
        <div class="risk-bar-fill look" style="width: 25%"></div>
      </div>
      <span class="risk-count">3</span>
    </div>
    <div class="risk-row" data-severity="safe">
      <span class="risk-indicator safe"></span>
      <span class="risk-label">Safe</span>
      <div class="risk-bar-track">
        <div class="risk-bar-fill safe" style="width: 66.6%"></div>
      </div>
      <span class="risk-count">8</span>
    </div>
  </div>
</section>
```

### CSS

```css
.risk-map {
  padding: var(--sp-5) var(--sp-7);
  border-bottom: 1px solid var(--color-gray-200);
}
.risk-map-title {
  font-size: var(--type-small);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-gray-500);
  margin-bottom: var(--sp-4);
}
.risk-bars {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.risk-row {
  display: grid;
  grid-template-columns: 12px 130px 1fr 36px;
  align-items: center;
  gap: var(--sp-3);
  cursor: pointer;
}
.risk-row:hover .risk-bar-fill { opacity: 0.8; }

.risk-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.risk-indicator.blocking  { background: var(--color-blocking); }
.risk-indicator.attention { background: var(--color-attention); }
.risk-indicator.look      { background: var(--color-look); }
.risk-indicator.safe      { background: var(--color-safe); }

.risk-label {
  font-size: var(--type-small);
  color: var(--color-gray-600);
}
.risk-bar-track {
  height: 6px;
  background: var(--color-gray-100);
  border-radius: 3px;
  overflow: hidden;
}
.risk-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}
.risk-bar-fill.blocking  { background: var(--color-blocking); }
.risk-bar-fill.attention { background: var(--color-attention); }
.risk-bar-fill.look      { background: var(--color-look); }
.risk-bar-fill.safe      { background: var(--color-safe); }

.risk-count {
  font-family: var(--font-mono);
  font-size: var(--type-small);
  font-weight: 600;
  text-align: right;
  color: var(--color-gray-600);
}

@media (prefers-reduced-motion: reduce) {
  .risk-bar-fill { transition: none; }
}
@media (max-width: 640px) {
  .risk-row { grid-template-columns: 10px 100px 1fr 30px; }
}
```

---

## Pattern 3: File Navigation (Side Nav)

Sticky side nav with severity-colored links. Scrolls independently from main content.

### HTML

```html
<nav class="file-nav" aria-label="File navigation">
  <h2 class="file-nav-title">Files</h2>

  <div class="filter-controls" role="group" aria-label="Filter files by severity">
    <button class="filter-btn active" data-filter="all" aria-pressed="true">All <span class="filter-count">18</span></button>
    <button class="filter-btn" data-filter="blocking" aria-pressed="false">Blocking <span class="filter-count">2</span></button>
    <button class="filter-btn" data-filter="attention" aria-pressed="false">Attention <span class="filter-count">5</span></button>
  </div>

  <ul class="file-list">
    <li>
      <a href="#file-auth-ts" class="file-link blocking" data-severity="blocking">
        <span class="file-severity-dot blocking"></span>
        <span class="file-name">src/auth.ts</span>
        <span class="file-stats">+142 &minus;38</span>
      </a>
    </li>
    <li>
      <a href="#file-middleware-ts" class="file-link blocking" data-severity="blocking">
        <span class="file-severity-dot blocking"></span>
        <span class="file-name">src/middleware.ts</span>
        <span class="file-stats">+89 &minus;12</span>
      </a>
    </li>
    <li>
      <a href="#file-config-ts" class="file-link safe" data-severity="safe">
        <span class="file-severity-dot safe"></span>
        <span class="file-name">src/config.ts</span>
        <span class="file-stats">+5 &minus;2</span>
      </a>
    </li>
    <!-- Repeat for all files -->
  </ul>
</nav>
```

### CSS

```css
.file-nav {
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  padding: var(--sp-5) var(--sp-4);
  border-right: 1px solid var(--color-gray-200);
  background: white;
}
.file-nav-title {
  font-size: var(--type-small);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-gray-500);
  margin-bottom: var(--sp-4);
}

/* --- Filter buttons --- */
.filter-controls {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1);
  margin-bottom: var(--sp-4);
}
.filter-btn {
  font-family: var(--font-body);
  font-size: var(--type-caption);
  padding: 2px 8px;
  border: 1px solid var(--color-gray-200);
  border-radius: var(--radius-xs);
  background: white;
  color: var(--color-gray-600);
  cursor: pointer;
  transition: background 0.1s;
}
.filter-btn:hover { background: var(--color-gray-100); }
.filter-btn.active {
  background: var(--color-slate);
  color: white;
  border-color: var(--color-slate);
}
.filter-btn:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
.filter-count {
  font-family: var(--font-mono);
  margin-left: 2px;
}

/* --- File list --- */
.file-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.file-link {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-xs);
  text-decoration: none;
  color: var(--color-text);
  font-size: var(--type-small);
  transition: background 0.1s;
}
.file-link:hover { background: var(--color-gray-100); }
.file-link:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}
.file-link.active { background: var(--color-gray-100); font-weight: 600; }

.file-severity-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.file-severity-dot.blocking  { background: var(--color-blocking); }
.file-severity-dot.attention { background: var(--color-attention); }
.file-severity-dot.look      { background: var(--color-look); }
.file-severity-dot.safe      { background: var(--color-safe); }

.file-name {
  flex: 1;
  font-family: var(--font-mono);
  font-size: var(--type-caption);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-stats {
  font-family: var(--font-mono);
  font-size: var(--type-caption);
  color: var(--color-gray-400);
  white-space: nowrap;
}

/* Mobile: horizontal scrollable nav bar */
@media (max-width: 768px) {
  .file-nav {
    position: static;
    height: auto;
    overflow-y: visible;
    overflow-x: auto;
    border-right: none;
    border-bottom: 1px solid var(--color-gray-200);
    padding: var(--sp-3) var(--sp-4);
  }
  .file-list {
    display: flex;
    gap: var(--sp-1);
    overflow-x: auto;
    padding-bottom: var(--sp-2);
  }
  .file-link { white-space: nowrap; }
}
```

---

## Pattern 4: Diff File Block

Core rendering unit. One per changed file. Contains diff lines and inline annotations.

### HTML

```html
<article class="diff-file" id="file-auth-ts" data-severity="blocking">
  <header class="diff-header">
    <button class="diff-toggle" aria-expanded="true" aria-controls="diff-body-auth-ts">
      <svg class="chevron" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
        <path d="M6 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
    </button>
    <span class="diff-filename">src/auth.ts</span>
    <span class="severity-badge blocking">Blocking</span>
    <span class="diff-stats">
      <span class="stat-add">+142</span>
      <span class="stat-del">&minus;38</span>
    </span>
  </header>

  <div class="diff-body" id="diff-body-auth-ts">
    <!-- Context lines -->
    <div class="diff-line context">
      <span class="line-num line-num-old">14</span>
      <span class="line-num line-num-new">14</span>
      <span class="line-code">  import { validate } from './validate';</span>
    </div>

    <!-- Deletion -->
    <div class="diff-line deletion">
      <span class="line-num line-num-old">15</span>
      <span class="line-num line-num-new"></span>
      <span class="line-code">  const token = localStorage.get('token');</span>
    </div>

    <!-- Addition -->
    <div class="diff-line addition">
      <span class="line-num line-num-old"></span>
      <span class="line-num line-num-new">15</span>
      <span class="line-code">  const token = await getToken();</span>
    </div>

    <!-- Context -->
    <div class="diff-line context">
      <span class="line-num line-num-old">16</span>
      <span class="line-num line-num-new">16</span>
      <span class="line-code">  return validate(token);</span>
    </div>

    <!-- Inline annotation (appears between diff lines) -->
    <div class="annotation blocking" id="note-1" role="note" aria-label="Blocking annotation on line 15">
      <div class="annotation-header">
        <span class="severity-badge blocking">Blocking</span>
        <span class="annotation-line">Line 15</span>
      </div>
      <div class="annotation-body">
        <p><code>getToken()</code> is async but the error path is unhandled.
           If the token fetch fails, the function silently returns <code>undefined</code>,
           which <code>validate()</code> will accept as a guest session.</p>
        <div class="annotation-suggestion">
          <strong>Suggestion:</strong>
          <pre><code>const token = await getToken().catch(() => {
  throw new AuthError('Token fetch failed');
});</code></pre>
        </div>
      </div>
    </div>

    <!-- More diff lines... -->
  </div>
</article>
```

### CSS

```css
/* --- Diff File Block --- */
.diff-file {
  border: 1px solid var(--color-gray-200);
  border-radius: var(--radius-md);
  margin: var(--sp-5) var(--sp-7);
  overflow: hidden;
  background: white;
}

.diff-header {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--sp-4);
  background: var(--color-gray-100);
  border-bottom: 1px solid var(--color-gray-200);
}
.diff-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  background: none;
  border: none;
  cursor: pointer;
  border-radius: var(--radius-xs);
  color: var(--color-gray-500);
  transition: transform 0.15s ease;
}
.diff-toggle:hover { background: var(--color-gray-200); }
.diff-toggle:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
.diff-toggle[aria-expanded="true"] .chevron {
  transform: rotate(90deg);
}
.diff-filename {
  font-family: var(--font-mono);
  font-size: var(--type-small);
  font-weight: 600;
  flex: 1;
}
.diff-stats {
  font-family: var(--font-mono);
  font-size: var(--type-small);
}

/* --- Diff Body (collapsible) --- */
.diff-body {
  overflow: hidden;
  transition: max-height 0.2s ease;
}
.diff-body.collapsed {
  max-height: 0 !important;
}

/* --- Diff Lines --- */
.diff-line {
  display: flex;
  align-items: stretch;
  font-family: var(--font-mono);
  font-size: var(--type-small);
  line-height: 1.5;
  min-height: 24px;
}
.diff-line.addition { background: var(--diff-add-bg); }
.diff-line.deletion { background: var(--diff-del-bg); }
.diff-line.context  { background: var(--diff-ctx-bg); }

/* Line numbers */
.line-num {
  display: inline-block;
  width: 48px;
  min-width: 48px;
  text-align: right;
  padding: 0 8px 0 0;
  color: var(--color-gray-400);
  font-size: var(--type-caption);
  border-right: 1px solid var(--color-gray-200);
  user-select: none;
  line-height: 24px;
}
.line-num-old {
  border-right: none;
  padding-right: 4px;
}
.line-num-new {
  padding-left: 4px;
}

/* Line code content */
.line-code {
  flex: 1;
  padding: 0 var(--sp-4);
  white-space: pre;
  overflow-x: auto;
  tab-size: 4;
  line-height: 24px;
}

/* +/- prefix indicators */
.diff-line.addition .line-code::before {
  content: '+';
  color: var(--color-success);
  font-weight: 700;
  margin-right: var(--sp-2);
}
.diff-line.deletion .line-code::before {
  content: '\2212';
  color: var(--color-danger);
  font-weight: 700;
  margin-right: var(--sp-2);
}
.diff-line.context .line-code::before {
  content: '\00a0';
  margin-right: var(--sp-2);
}

/* --- Annotations --- */
.annotation {
  margin: 0 var(--sp-4) var(--sp-3);
  padding: var(--sp-4);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--color-gray-300);
  background: var(--color-gray-100);
}
.annotation.blocking  { border-left-color: var(--color-blocking); background: color-mix(in srgb, var(--color-blocking) 4%, white); }
.annotation.attention { border-left-color: var(--color-attention); background: color-mix(in srgb, var(--color-attention) 4%, white); }
.annotation.look      { border-left-color: var(--color-look); background: color-mix(in srgb, var(--color-look) 4%, white); }
.annotation.safe      { border-left-color: var(--color-safe); background: color-mix(in srgb, var(--color-safe) 4%, white); }

.annotation-header {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-bottom: var(--sp-3);
}
.annotation-line {
  font-family: var(--font-mono);
  font-size: var(--type-caption);
  color: var(--color-gray-500);
}
.annotation-body {
  font-size: var(--type-small);
  line-height: 1.5;
  color: var(--color-gray-600);
}
.annotation-body code {
  font-family: var(--font-mono);
  background: color-mix(in srgb, var(--color-gray-200) 50%, transparent);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 0.875em;
}
.annotation-suggestion {
  margin-top: var(--sp-3);
}
.annotation-suggestion strong {
  font-size: var(--type-caption);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-gray-500);
  display: block;
  margin-bottom: var(--sp-2);
}
.annotation-suggestion pre {
  background: var(--color-slate);
  color: var(--color-ivory);
  padding: var(--sp-3);
  border-radius: var(--radius-xs);
  font-family: var(--font-mono);
  font-size: var(--type-caption);
  line-height: 1.5;
  overflow-x: auto;
}

/* --- Responsive --- */
@media (max-width: 640px) {
  .diff-file { margin: var(--sp-3) var(--sp-3); }
  .line-num { width: 32px; min-width: 32px; font-size: 10px; }
  .line-code { font-size: var(--type-caption); padding: 0 var(--sp-2); }
  .annotation { margin: 0 var(--sp-2) var(--sp-2); padding: var(--sp-3); }
}

@media (prefers-reduced-motion: reduce) {
  .diff-body, .diff-toggle .chevron { transition: none; }
}
```

### Syntax Highlight Tokens

Minimal token classes for inline syntax coloring within diffs:

```css
/* Apply these to <span> elements wrapping tokens inside .line-code */
.tok-kw  { color: #C792EA; } /* keyword: const, let, async, await, return, if, else */
.tok-fn  { color: #82AAFF; } /* function name / method call */
.tok-str { color: #C3E88D; } /* string literal */
.tok-cm  { color: #6A737D; } /* comment */
.tok-num { color: #F78C6C; } /* number literal */
.tok-op  { color: #89DDFF; } /* operator: =, =>, ===, !== */
.tok-typ { color: #FFCB6B; } /* type / interface name */

/* Inside diff additions/deletions, boost token visibility */
.diff-line.addition .tok-kw,
.diff-line.deletion .tok-kw { font-weight: 600; }
```

---

## Pattern 5: Module Map (SVG)

Box-and-arrow diagram for visualizing module architecture. Hot path highlighted.

### HTML

```html
<section class="module-map-section">
  <h2>Module Map</h2>
  <div class="diagram-container">
    <svg viewBox="0 0 800 500" xmlns="http://www.w3.org/2000/svg" role="img"
         aria-label="Module dependency diagram showing auth flow through middleware, service, and database layers">

      <defs>
        <marker id="dep-arrow" viewBox="0 0 10 7" refX="10" refY="3.5"
                markerWidth="8" markerHeight="6" orient="auto-start-auto">
          <path d="M 0 0 L 10 3.5 L 0 7 z" fill="var(--color-gray-400)" />
        </marker>
        <marker id="dep-arrow-hot" viewBox="0 0 10 7" refX="10" refY="3.5"
                markerWidth="8" markerHeight="6" orient="auto-start-auto">
          <path d="M 0 0 L 10 3.5 L 0 7 z" fill="var(--color-primary)" />
        </marker>
      </defs>

      <!-- Entry point indicator -->
      <g class="entry-point" transform="translate(20, 85)">
        <polygon points="0,8 12,0 12,16" fill="var(--color-primary)" />
      </g>

      <!-- Module: auth.ts (blocking — highlighted border) -->
      <g class="module" data-file="auth-ts">
        <rect x="50" y="60" width="160" height="56" rx="8" ry="8"
              fill="white" stroke="var(--color-blocking)" stroke-width="2" />
        <text x="130" y="83" text-anchor="middle"
              font-family="var(--font-mono)" font-size="12" font-weight="600"
              fill="var(--color-text)">auth.ts</text>
        <text x="130" y="103" text-anchor="middle"
              font-family="var(--font-mono)" font-size="10"
              fill="var(--color-gray-500)">+142 &minus;38</text>
      </g>

      <!-- Module: middleware.ts -->
      <g class="module" data-file="middleware-ts">
        <rect x="320" y="60" width="160" height="56" rx="8" ry="8"
              fill="white" stroke="var(--color-gray-300)" stroke-width="1.5" />
        <text x="400" y="83" text-anchor="middle"
              font-family="var(--font-mono)" font-size="12" font-weight="600"
              fill="var(--color-text)">middleware.ts</text>
        <text x="400" y="103" text-anchor="middle"
              font-family="var(--font-mono)" font-size="10"
              fill="var(--color-gray-500)">+89 &minus;12</text>
      </g>

      <!-- Module: db.ts (safe — muted border) -->
      <g class="module" data-file="db-ts">
        <rect x="590" y="60" width="160" height="56" rx="8" ry="8"
              fill="white" stroke="var(--color-gray-200)" stroke-width="1.5" />
        <text x="670" y="83" text-anchor="middle"
              font-family="var(--font-mono)" font-size="12" font-weight="600"
              fill="var(--color-text)">db.ts</text>
        <text x="670" y="103" text-anchor="middle"
              font-family="var(--font-mono)" font-size="10"
              fill="var(--color-gray-500)">+5 &minus;2</text>
      </g>

      <!-- Hot path: auth -> middleware (thick, primary color) -->
      <line x1="210" y1="88" x2="318" y2="88"
            stroke="var(--color-primary)" stroke-width="2.5"
            marker-end="url(#dep-arrow-hot)" />
      <text x="264" y="78" text-anchor="middle"
            font-family="var(--font-mono)" font-size="9"
            fill="var(--color-primary)">authenticateRequest()</text>

      <!-- Normal path: middleware -> db -->
      <line x1="480" y1="88" x2="588" y2="88"
            stroke="var(--color-gray-400)" stroke-width="1.5"
            marker-end="url(#dep-arrow)" />
      <text x="534" y="78" text-anchor="middle"
            font-family="var(--font-mono)" font-size="9"
            fill="var(--color-gray-500)">findUser()</text>

      <!-- Legend -->
      <g transform="translate(50, 460)">
        <polygon points="0,6 10,0 10,12" fill="var(--color-primary)" />
        <text x="18" y="10" font-family="var(--font-mono)" font-size="10" fill="var(--color-gray-500)">Entry point</text>

        <line x1="130" y1="6" x2="160" y2="6" stroke="var(--color-primary)" stroke-width="2.5" />
        <text x="168" y="10" font-family="var(--font-mono)" font-size="10" fill="var(--color-gray-500)">Hot path (changed)</text>

        <line x1="320" y1="6" x2="350" y2="6" stroke="var(--color-gray-400)" stroke-width="1.5" />
        <text x="358" y="10" font-family="var(--font-mono)" font-size="10" fill="var(--color-gray-500)">Dependency</text>

        <rect x="470" y="-2" width="16" height="16" rx="3" stroke="var(--color-blocking)" stroke-width="2" fill="white" />
        <text x="494" y="10" font-family="var(--font-mono)" font-size="10" fill="var(--color-gray-500)">Blocking issue</text>
      </g>

    </svg>
  </div>
</section>
```

### CSS

```css
.module-map-section {
  padding: var(--sp-6) var(--sp-7);
}
.module-map-section h2 {
  font-size: var(--type-h2);
  font-weight: 600;
  margin-bottom: var(--sp-5);
}
.diagram-container {
  background: white;
  border: 1px solid var(--color-gray-200);
  border-radius: var(--radius-md);
  padding: var(--sp-4);
  overflow-x: auto;
}
.diagram-container svg {
  width: 100%;
  height: auto;
  min-width: 700px;
}

/* Clickable modules (link to file diff) */
.module { cursor: pointer; }
.module:hover rect {
  filter: brightness(0.97);
}

/* SVG construction rules:
   - Modules: <rect rx="8"> with 1.5px gray stroke (normal) or 2px severity stroke (flagged)
   - Hot path: 2.5px stroke in --color-primary with arrow marker
   - Normal deps: 1.5px stroke in --color-gray-400 with arrow marker
   - Labels: font-family var(--font-mono), 12px bold for names, 10px for stats
   - Entry point: triangle polygon pointing right, filled with --color-primary
   - Legend: always present at bottom of SVG
*/
```

---

## Pattern 6: JavaScript Interactions

### Expand/Collapse File Diffs

```js
(function () {
  document.querySelectorAll('.diff-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const expanded = btn.getAttribute('aria-expanded') === 'true';
      const targetId = btn.getAttribute('aria-controls');
      const target = document.getElementById(targetId);

      btn.setAttribute('aria-expanded', String(!expanded));

      if (expanded) {
        target.style.maxHeight = target.scrollHeight + 'px';
        // Force reflow, then collapse
        requestAnimationFrame(() => {
          target.style.maxHeight = '0';
          target.classList.add('collapsed');
        });
      } else {
        target.classList.remove('collapsed');
        target.style.maxHeight = target.scrollHeight + 'px';
        // Clean up after transition
        target.addEventListener('transitionend', function handler() {
          target.style.maxHeight = '';
          target.removeEventListener('transitionend', handler);
        });
      }
    });
  });
})();
```

### Filter Files by Severity

```js
(function () {
  const filterBtns = document.querySelectorAll('.filter-btn');
  const fileLinks = document.querySelectorAll('.file-link');
  const diffFiles = document.querySelectorAll('.diff-file');

  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      // Update active state
      filterBtns.forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-pressed', 'false');
      });
      btn.classList.add('active');
      btn.setAttribute('aria-pressed', 'true');

      const severity = btn.dataset.filter;

      // Filter side nav links
      fileLinks.forEach(link => {
        const li = link.closest('li');
        if (severity === 'all' || link.dataset.severity === severity) {
          li.style.display = '';
        } else {
          li.style.display = 'none';
        }
      });

      // Filter diff file blocks
      diffFiles.forEach(file => {
        if (severity === 'all' || file.dataset.severity === severity) {
          file.style.display = '';
        } else {
          file.style.display = 'none';
        }
      });
    });
  });
})();
```

### Keyboard Navigation (j/k between files)

```js
(function () {
  let currentFileIndex = -1;
  const files = Array.from(document.querySelectorAll('.diff-file'));

  function scrollToFile(index) {
    if (index < 0 || index >= files.length) return;
    currentFileIndex = index;
    files[index].scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Update active state in file nav
    const fileId = files[index].id;
    document.querySelectorAll('.file-link').forEach(link => {
      link.classList.toggle('active', link.getAttribute('href') === '#' + fileId);
    });
  }

  document.addEventListener('keydown', (e) => {
    // Don't intercept when user is typing in an input/textarea
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    // Only respond to visible (non-filtered) files
    const visibleFiles = files.filter(f => f.style.display !== 'none');

    switch (e.key) {
      case 'j': // Next file
        e.preventDefault();
        currentFileIndex = Math.min(currentFileIndex + 1, visibleFiles.length - 1);
        scrollToFile(files.indexOf(visibleFiles[currentFileIndex]));
        break;
      case 'k': // Previous file
        e.preventDefault();
        currentFileIndex = Math.max(currentFileIndex - 1, 0);
        scrollToFile(files.indexOf(visibleFiles[currentFileIndex]));
        break;
      case 'x': // Toggle expand/collapse current file
        e.preventDefault();
        if (currentFileIndex >= 0 && currentFileIndex < files.length) {
          const toggle = files[currentFileIndex].querySelector('.diff-toggle');
          if (toggle) toggle.click();
        }
        break;
    }
  });

  // Sync current file index on scroll
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const index = files.indexOf(entry.target);
        if (index !== -1) currentFileIndex = index;

        // Update side nav active state
        document.querySelectorAll('.file-link').forEach(link => {
          link.classList.toggle('active', link.getAttribute('href') === '#' + entry.target.id);
        });
      }
    });
  }, { threshold: 0.3 });

  files.forEach(file => observer.observe(file));
})();
```

### Jump-to-File via Anchor Links

```js
(function () {
  // Smooth scroll for file nav links
  document.querySelectorAll('.file-link').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = link.getAttribute('href').slice(1);
      const target = document.getElementById(targetId);
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });

        // Expand if collapsed
        const body = target.querySelector('.diff-body');
        const toggle = target.querySelector('.diff-toggle');
        if (body && body.classList.contains('collapsed') && toggle) {
          toggle.click();
        }
      }
    });
  });
})();
```

### Clickable Module Map

```js
(function () {
  // Click module box in SVG to jump to that file's diff
  document.querySelectorAll('.module').forEach(mod => {
    mod.addEventListener('click', () => {
      const fileSlug = mod.dataset.file;
      const target = document.getElementById('file-' + fileSlug);
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
})();
```

---

## Pattern 7: Risk Map Click-to-Filter

Connect the risk map rows to the severity filter.

### JS

```js
(function () {
  document.querySelectorAll('.risk-row').forEach(row => {
    row.addEventListener('click', () => {
      const severity = row.dataset.severity;
      const filterBtn = document.querySelector(`.filter-btn[data-filter="${severity}"]`);
      if (filterBtn) filterBtn.click();
    });
  });
})();
```

---

## Composition Guide

| Request Shape | Patterns to Combine |
|---|---|
| "Review this PR" | Shell + PR Summary + Risk Map + File Nav + Diff Blocks + Annotations + Keyboard Nav |
| "Annotate this diff" | Shell (no side nav) + Diff Blocks + Annotations |
| "Explain module architecture" | Shell + Module Map + Brief annotations per module |
| "PR writeup for reviewers" | Shell + PR Summary + Risk Map + File Nav + Diff Blocks + Annotations + Keyboard Nav |
| "What changed in this commit" | Shell (no side nav) + Diff Blocks (context-heavy, fewer annotations) |

### Section Ordering

1. PR summary header (title, author, branch, stats)
2. Risk map (severity distribution)
3. Module map (if architecture/dependency visualization needed)
4. File diffs in severity order: blocking first, safe last
5. Each diff block contains its annotations inline

### Keyboard Shortcut Reference

Include as a tooltip or small `<details>` block at bottom:

```html
<details class="keyboard-help">
  <summary>Keyboard shortcuts</summary>
  <dl class="shortcut-list">
    <dt><kbd>j</kbd></dt><dd>Next file</dd>
    <dt><kbd>k</kbd></dt><dd>Previous file</dd>
    <dt><kbd>x</kbd></dt><dd>Toggle expand/collapse</dd>
  </dl>
</details>
```

```css
.keyboard-help {
  margin: var(--sp-7) var(--sp-7) var(--sp-5);
  font-size: var(--type-small);
  color: var(--color-gray-500);
}
.keyboard-help summary {
  cursor: pointer;
  font-weight: 500;
}
.keyboard-help summary:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
.shortcut-list {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--sp-2) var(--sp-4);
  margin-top: var(--sp-3);
}
.shortcut-list dt { text-align: right; }
kbd {
  display: inline-block;
  padding: 2px 6px;
  border: 1px solid var(--color-gray-300);
  border-radius: 3px;
  background: var(--color-gray-100);
  font-family: var(--font-mono);
  font-size: var(--type-caption);
  line-height: 1;
}
```

---

## Accessibility Checklist

- [ ] All `<svg>` elements have `role="img"` and `aria-label`
- [ ] Expand/collapse buttons have `aria-expanded` and `aria-controls`
- [ ] Filter buttons use `aria-pressed` state
- [ ] File nav has `aria-label="File navigation"`
- [ ] Annotations have `role="note"` and descriptive `aria-label`
- [ ] Focus-visible outlines on all buttons and links
- [ ] Color is never the sole indicator (severity uses text labels + color)
- [ ] Keyboard shortcuts don't fire inside text inputs
- [ ] `prefers-reduced-motion` disables transitions and smooth scrolling
- [ ] Side nav scrolls independently with visible scroll region
- [ ] Semantic elements: `<article>` per file, `<nav>` for file list, `<main>` for content
- [ ] Diff line numbers use `user-select: none` to prevent copy noise
