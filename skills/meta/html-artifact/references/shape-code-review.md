# Shape: Code Review

> **Shape**: code-review | **Signal words**: review PR, diff, annotate, code review, explain code, understand module
> CSS layout classes: `templates/shapes/code-review.css` (injected by assemble-template.py)
> Components: `collapsible`, `filter`, `keyboard-nav`, `theme-toggle`

Code-review artifacts annotate diffs, not source files. The reader is scanning for what to look at — severity ordering, jump links, and inline review notes are non-negotiable. Hide nothing in expanding panels that the reader needs to read first.

---

## Layout Description

Two columns on desktop: 220px sticky `.file-nav` (left) + scrollable `.review-main` (right). Below 768px the nav becomes a horizontal scrollable bar above the main content.

Main content order: PR summary header → risk map (severity distribution) → optional module map (SVG) → file diffs in **severity order** (blocking first, safe last) → keyboard-shortcut reference at the bottom.

---

## Canonical Markup Order (load-bearing rule)

| Order | Region | Purpose |
|---|---|---|
| 1 | `<nav class="file-nav">` | Jump links to each file, with severity badges |
| 2 | `<header class="pr-summary">` inside `<main>` | Title, author, branch, +/− stats, description |
| 3 | `.risk-map` section | Severity totals: how many blocking, attention, safe |
| 4 | `.diff-file` blocks, **severity-sorted** | Blocking first, attention second, look third, safe last |
| 5 | Keyboard shortcut footer | `j/k` between files, `x` to expand, `?` for help |

Why severity order: a reviewer with 10 minutes should hit the must-fix items first. Alphabetical or path order buries blockers under safe refactors.

### Skeleton

```html
<body data-shape="code-review" data-theme="birchline">
  <div class="review-layout">
    <nav class="file-nav" aria-label="File navigation">
      <a href="#file-auth-js"><span class="severity-badge blocking">Blocking</span> auth.js</a>
      <a href="#file-cookie-js"><span class="severity-badge attention">Attention</span> cookie.js</a>
      <a href="#file-readme-md"><span class="severity-badge safe">Safe</span> README.md</a>
    </nav>
    <main class="review-main">
      <header class="pr-summary"><!-- title, meta, stats, description --></header>
      <section class="risk-map" aria-label="Severity distribution"><!-- counts --></section>
      <article class="diff-file" id="file-auth-js"><!-- highest severity first --></article>
      <article class="diff-file" id="file-cookie-js"></article>
      <article class="diff-file" id="file-readme-md"></article>
    </main>
  </div>
</body>
```

CSS lives in `templates/shapes/code-review.css` — do not redefine `.review-layout`, `.diff-*`, `.severity-badge`, `.line-num`, `.line-code`, `.annotation` inline.

---

## Severity System

| Level | Class | Meaning | Reviewer Action |
|---|---|---|---|
| Blocking | `.severity-badge.blocking`, `.annotation.blocking` | Bug, security, data loss | Must fix before merge |
| Needs Attention | `.severity-badge.attention`, `.annotation.attention` | Concern worth discussing | Comment, may merge |
| Worth a Look | `.severity-badge.look` | Minor style or naming | Optional |
| Safe | `.severity-badge.safe` | No issue, often praise | None |

Severity is the **organizing axis** of the entire artifact: file nav order, file order in main, annotation styling. A file with one blocking comment ranks above a file with ten attention comments.

---

## Section Types (worked examples)

### PR summary header

```html
<header class="pr-summary">
  <div class="pr-title-row">
    <h1>Refactor auth flow to httpOnly cookies</h1>
    <span class="pr-number">#42</span>
  </div>
  <div class="pr-meta">
    <span class="pr-meta-item"><strong>Author</strong> @alice</span>
    <span class="pr-meta-item"><strong>Branch</strong> feat/auth-cookies → main</span>
    <span class="pr-meta-item"><strong>Files</strong> 12 changed</span>
    <span class="pr-meta-item pr-stats">
      <span class="stat-add">+580</span>
      <span class="stat-del">−220</span>
    </span>
  </div>
  <p class="pr-description">Migrates token storage from localStorage to httpOnly cookies. Adds CSRF middleware and dual-read for backward compat.</p>
</header>
```

Use for: every code-review artifact. PR title is `<h1>`, number is decorative — author, branch, file count and +/− stats are the orienting facts.

### Diff block with annotation

```html
<article class="diff-file" id="file-auth-js" aria-label="auth.js review">
  <header class="diff-header">
    <span class="severity-badge blocking">Blocking</span>
    <code class="diff-path">src/auth/login.js</code>
    <span class="stat-add">+42</span>
    <span class="stat-del">−18</span>
  </header>
  <div class="diff-body">
    <div class="diff-line context">
      <span class="line-num">12</span>
      <span class="line-code">async function login(email, password) {</span>
    </div>
    <div class="diff-line deletion">
      <span class="line-num">13</span>
      <span class="line-code">  localStorage.setItem('token', token);</span>
    </div>
    <div class="diff-line addition">
      <span class="line-num">14</span>
      <span class="line-code">  document.cookie = `token=${token}; HttpOnly`;</span>
    </div>
    <aside class="annotation blocking" role="note" aria-label="Blocking comment on line 14">
      <strong>Blocking · @reviewer</strong>
      <p>HttpOnly cookies cannot be set from JavaScript. This must be set
         server-side via <code>Set-Cookie</code> header, otherwise the
         flag is silently ignored and the token is XSS-readable.</p>
    </aside>
  </div>
</article>
```

Use for: every reviewed file. The `.severity-badge` in the header is what drives ordering. Annotations sit **inline between diff lines**, not in a separate section — this preserves the line-of-sight from issue to code.

### Risk map

```html
<section class="risk-map" aria-label="Severity distribution">
  <h2>Risk Map</h2>
  <ul>
    <li><span class="severity-badge blocking">Blocking</span> 1 issue · auth.js</li>
    <li><span class="severity-badge attention">Attention</span> 3 issues · cookie.js, csrf.js, middleware.js</li>
    <li><span class="severity-badge safe">Safe</span> 8 files · no concerns</li>
  </ul>
</section>
```

Use for: any review with 5+ files. A reviewer with limited time reads this first to allocate attention.

---

## Interaction Patterns

| Pattern | Component | Behavior |
|---|---|---|
| Expand / collapse a `.diff-file` | `collapsible` | `aria-expanded` on a button; default open for blocking, collapsed for safe |
| Severity filter | `filter` | Pill buttons with `aria-pressed`; toggling hides matching files AND nav links |
| File jump | Anchor links | `<a href="#file-id">`; sidebar links scroll to and auto-expand the diff |
| Keyboard nav | `keyboard-nav` | `j` / `k` between files, `x` to toggle expand, `?` for shortcut overlay; ignore when focus is in `<input>` or `<textarea>` |
| Module map | Inline SVG | Module nodes are `<a xlink:href="#file-id">`, navigate to corresponding diff |

Do not hand-author keyboard handlers — request the `keyboard-nav` and `filter` components and let the assembler inject them.

---

## ARIA / Accessibility

| Element | Required attributes | Why |
|---|---|---|
| `.file-nav` | `aria-label="File navigation"` | Landmark distinct from main nav |
| `.diff-file` | `aria-label="<filename> review"` or `id` matching the nav link | Discoverable by AT |
| `.annotation` | `role="note"`, `aria-label="<severity> comment on line N"` | Announces what kind of comment and where |
| `.severity-badge` | Text inside ("Blocking") | Color is supplementary; text is the source of truth |
| `.line-num` | `user-select: none` (CSS) | Prevents copying line numbers with the code |
| `.diff-line` `.addition` / `.deletion` | Text marker (`+ ` / `- `) via `::before` | Color alone fails for color-blind reviewers |
| Filter buttons | `<button aria-pressed="true|false">` | Conveys toggle state |
| Keyboard shortcuts | Skip when `e.target.tagName` is `INPUT`, `TEXTAREA`, or `[contenteditable]` | Don't hijack typing in comment fields |
| Reduced motion | Disable smooth-scroll; use `scrollTo({ behavior: 'auto' })` | Respect `prefers-reduced-motion` |

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Files ordered alphabetically or by path | Order by severity descending; blocking first, safe last |
| Annotations grouped in a separate "Comments" section at the bottom | Place inline between diff lines so issue and code are co-visible |
| Line numbers selectable when copying the code | Apply `user-select: none` to `.line-num` (already in template CSS) |
| Diff lines distinguished by color only | Use `+ ` / `− ` glyph via `::before`, not just background color |
| Keyboard shortcuts (`j` / `k`) firing inside textareas | Guard with `e.target.tagName` check; the `keyboard-nav` component does this |
| Sidebar not scrollable independently of main | Sidebar has `position: sticky; top: 0; height: 100vh; overflow-y: auto` (already in template) |
| Severity conveyed by border color only on `.annotation` | Always include `<strong>Blocking · @reviewer</strong>` text label |
| Hand-authored expand/collapse with `display: none` | Use the `collapsible` component for animated, accessible behavior |
| Module map without anchor links | SVG nodes wrap in `<a xlink:href="#file-id">`, otherwise the map is decorative |
| Inline `<style>` redefining `.diff-line` / `.severity-badge` | All shape CSS in `templates/shapes/code-review.css` — touching it creates drift |

---

## Shape Selection

Use **code-review** when the request matches: review PR, annotate diff, code review, explain code change, understand module, PR writeup.

Do **not** use code-review when:

- The user wants to compare design approaches without diffs (use **spec**)
- The user wants to explain how code works without line-level annotation (use **report + diagram**)
- The user wants a tutorial walking through code (use **report**)
- The user wants an interactive editor for code (use **editor**)
