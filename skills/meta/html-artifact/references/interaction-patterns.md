# Interaction Patterns

Shared JavaScript and CSS patterns used across multiple artifact shapes. The html-builder agent loads this reference alongside shape-specific references. All code is vanilla JS/CSS -- no dependencies.

---

## 1. Copy to Clipboard with Visual Feedback

```js
function copyToClipboard(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    const original = btn.textContent;
    btn.textContent = '✓ Copied!';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = original; btn.classList.remove('copied'); }, 1500);
  });
}
```

```css
.copy-btn {
  background: var(--bg-muted);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-xs);
  padding: var(--sp-1) var(--sp-2);
  font: var(--type-caption);
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}
.copy-btn:hover { background: var(--bg-surface); border-color: var(--accent); }
.copy-btn.copied { background: color-mix(in srgb, var(--color-success) 12%, transparent); border-color: var(--color-success); color: var(--color-success); }
```

Usage: `<button class="copy-btn" onclick="copyToClipboard('text here', this)">Copy</button>`

---

## 2. Tab Switching

```html
<div class="tab-bar" role="tablist">
  <button class="tab active" role="tab" aria-selected="true" data-tab="one">Tab One</button>
  <button class="tab" role="tab" aria-selected="false" data-tab="two">Tab Two</button>
</div>
<div class="tab-panel active" id="panel-one" role="tabpanel">Content one</div>
<div class="tab-panel" id="panel-two" role="tabpanel">Content two</div>
```

```js
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => { t.classList.remove('active'); t.setAttribute('aria-selected', 'false'); });
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    tab.setAttribute('aria-selected', 'true');
    document.getElementById('panel-' + tab.dataset.tab).classList.add('active');
  });
});
```

```css
.tab-bar {
  display: flex;
  gap: var(--sp-1);
  border-bottom: 2px solid var(--border-subtle);
  padding: 0 var(--sp-2);
}
.tab {
  background: none;
  border: none;
  padding: var(--sp-2) var(--sp-4);
  font: var(--type-small);
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color 0.15s ease, border-color 0.15s ease;
}
.tab:hover { color: var(--text-primary); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.tab:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; border-radius: var(--radius-xs); }
.tab-panel { display: none; padding: var(--sp-4) 0; }
.tab-panel.active { display: block; }
```

---

## 3. Collapsible Sections

### Approach A: Native `<details>/<summary>` (preferred)

Zero JS. Use when smooth animation is not required.

```html
<details>
  <summary>Section Title</summary>
  <div class="details-content">Content here</div>
</details>
```

```css
details {
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  margin-bottom: var(--sp-3);
}
summary {
  padding: var(--sp-3) var(--sp-4);
  font: var(--type-small);
  font-weight: 500;
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
summary::after { content: '+'; font-size: 18px; color: var(--text-muted); transition: transform 0.2s ease; }
details[open] summary::after { content: '\2212'; }
.details-content { padding: 0 var(--sp-4) var(--sp-4); }
```

### Approach B: Custom Accordion with Smooth Height Animation

Use when you need animated open/close transitions that `<details>` cannot provide.

```html
<div class="accordion">
  <button class="accordion-trigger" aria-expanded="false" aria-controls="acc-1">Section Title</button>
  <div class="accordion-panel" id="acc-1">
    <div class="accordion-inner">Content here</div>
  </div>
</div>
```

```js
document.querySelectorAll('.accordion-trigger').forEach(trigger => {
  trigger.addEventListener('click', () => {
    const expanded = trigger.getAttribute('aria-expanded') === 'true';
    const panel = document.getElementById(trigger.getAttribute('aria-controls'));
    trigger.setAttribute('aria-expanded', String(!expanded));
    if (!expanded) {
      panel.style.maxHeight = panel.scrollHeight + 'px';
    } else {
      panel.style.maxHeight = '0';
    }
  });
});
```

```css
.accordion-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  background: var(--bg-muted);
  border: none;
  padding: var(--sp-3) var(--sp-4);
  font: var(--type-small);
  font-weight: 500;
  cursor: pointer;
  text-align: left;
  border-radius: var(--radius-sm);
}
.accordion-trigger:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.accordion-panel {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.25s cubic-bezier(.16, 1, .3, 1);
}
.accordion-inner { padding: var(--sp-3) var(--sp-4); }
```

---

## 4. HTML5 Drag and Drop

Complete implementation for reordering list items.

```html
<ul class="drag-list">
  <li class="drag-item" draggable="true">Item A</li>
  <li class="drag-item" draggable="true">Item B</li>
  <li class="drag-item" draggable="true">Item C</li>
</ul>
```

```js
let dragEl = null;

document.querySelectorAll('.drag-item').forEach(item => {
  item.addEventListener('dragstart', e => {
    dragEl = item;
    item.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
  });

  item.addEventListener('dragend', () => {
    item.classList.remove('dragging');
    document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
    dragEl = null;
  });

  item.addEventListener('dragover', e => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    item.classList.add('drag-over');
  });

  item.addEventListener('dragleave', () => {
    item.classList.remove('drag-over');
  });

  item.addEventListener('drop', e => {
    e.preventDefault();
    item.classList.remove('drag-over');
    if (dragEl && dragEl !== item) {
      const list = item.parentNode;
      const items = [...list.children];
      const fromIdx = items.indexOf(dragEl);
      const toIdx = items.indexOf(item);
      if (fromIdx < toIdx) {
        list.insertBefore(dragEl, item.nextSibling);
      } else {
        list.insertBefore(dragEl, item);
      }
    }
  });
});
```

```css
.drag-list { list-style: none; padding: 0; }
.drag-item {
  padding: var(--sp-3) var(--sp-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  margin-bottom: var(--sp-2);
  cursor: grab;
  transition: opacity 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
  user-select: none;
}
.drag-item:active { cursor: grabbing; }
.drag-item.dragging { opacity: 0.35; transform: rotate(2deg); }
.drag-item.drag-over { border-color: var(--accent); box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 25%, transparent); }
```

---

## 5. Slider to Live CSS Variable Update

Pattern for `<input type="range">` that updates a CSS custom property in real-time.

```html
<label class="slider-group">
  <span class="slider-label">Border Radius</span>
  <input type="range" min="0" max="32" value="8"
         oninput="document.documentElement.style.setProperty('--radius-sm', this.value + 'px'); this.nextElementSibling.textContent = this.value + 'px'">
  <span class="slider-value">8px</span>
</label>
```

One line of JS per slider via `oninput`. No separate event listeners needed.

```css
.slider-group {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) 0;
}
.slider-label { font: var(--type-small); color: var(--text-secondary); min-width: 120px; }
.slider-value { font: var(--type-caption); font-family: var(--font-mono); color: var(--text-muted); min-width: 48px; }
input[type="range"] {
  flex: 1;
  height: 6px;
  -webkit-appearance: none;
  appearance: none;
  background: var(--border-default);
  border-radius: 3px;
  outline: none;
}
input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--accent);
  cursor: pointer;
  border: 2px solid var(--bg-surface);
  box-shadow: var(--shadow-sm);
}
input[type="range"]:focus-visible { outline: 2px solid var(--accent); outline-offset: 4px; border-radius: 4px; }
```

---

## 6. Keyboard Navigation

Arrow key listener for sequential content (slides, cards, items).

```js
function setupKeyNav(containerSelector, itemSelector) {
  const container = document.querySelector(containerSelector);
  const items = () => container.querySelectorAll(itemSelector);
  let current = 0;
  const counter = container.querySelector('.key-nav-counter');

  function update() {
    const all = items();
    all.forEach((el, i) => el.classList.toggle('active', i === current));
    if (counter) counter.textContent = (current + 1) + '/' + all.length;
  }

  document.addEventListener('keydown', e => {
    const all = items();
    if (!all.length) return;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      current = (current + 1) % all.length;
      update();
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      current = (current - 1 + all.length) % all.length;
      update();
    }
  });

  update();
}

// Usage: setupKeyNav('.slide-deck', '.slide');
```

```css
.key-nav-counter {
  font: var(--type-caption);
  font-family: var(--font-mono);
  color: var(--text-muted);
  padding: var(--sp-1) var(--sp-2);
  background: var(--bg-muted);
  border-radius: var(--radius-xs);
}
```

---

## 7. Anchor Navigation with Active Tracking

Scroll-based active section detection using IntersectionObserver.

```html
<nav class="toc" aria-label="Table of contents">
  <a href="#section-1" class="toc-link active">Introduction</a>
  <a href="#section-2" class="toc-link">Method</a>
  <a href="#section-3" class="toc-link">Results</a>
</nav>
```

```js
function setupScrollNav(tocSelector, sectionSelector) {
  const links = document.querySelectorAll(tocSelector + ' a');
  const sections = document.querySelectorAll(sectionSelector);

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        links.forEach(link => link.classList.remove('active'));
        const active = document.querySelector(tocSelector + ' a[href="#' + entry.target.id + '"]');
        if (active) active.classList.add('active');
      }
    });
  }, { rootMargin: '-20% 0px -60% 0px' });

  sections.forEach(section => observer.observe(section));
}

// Usage: setupScrollNav('.toc', 'section[id]');
```

```css
.toc {
  position: sticky;
  top: var(--sp-5);
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  padding: var(--sp-3);
  max-height: calc(100vh - var(--sp-8));
  overflow-y: auto;
}
.toc-link {
  font: var(--type-small);
  color: var(--text-muted);
  text-decoration: none;
  padding: var(--sp-1) var(--sp-3);
  border-left: 2px solid transparent;
  border-radius: 0;
  transition: color 0.15s ease, border-color 0.15s ease;
}
.toc-link:hover { color: var(--text-primary); }
.toc-link.active { color: var(--accent); border-left-color: var(--accent); font-weight: 500; }
.toc-link:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--radius-xs); }
```

Layout: use a two-column grid with `grid-template-columns: 200px 1fr` at desktop breakpoint, single column on mobile with `.toc` position static.

---

## 8. Live Template Re-rendering

Pattern for textarea that parses `{{var}}` template variables and renders filled versions live.

```html
<div class="template-editor">
  <textarea class="template-input" placeholder="Hello {{name}}, welcome to {{place}}!"></textarea>
  <div class="template-vars"></div>
  <div class="template-preview"></div>
  <span class="char-count">0 chars</span>
</div>
```

```js
function setupTemplateEditor(containerSelector) {
  const container = document.querySelector(containerSelector);
  const input = container.querySelector('.template-input');
  const varsContainer = container.querySelector('.template-vars');
  const preview = container.querySelector('.template-preview');
  const charCount = container.querySelector('.char-count');
  const varValues = {};

  function extractVars(text) {
    const matches = text.match(/\{\{(\w+)\}\}/g) || [];
    return [...new Set(matches.map(m => m.slice(2, -2)))];
  }

  function render() {
    const text = input.value;
    charCount.textContent = text.length + ' chars';
    const vars = extractVars(text);

    // Build var inputs if new vars appear
    vars.forEach(v => {
      if (!container.querySelector('[data-var="' + v + '"]')) {
        const label = document.createElement('label');
        label.className = 'template-var-field';
        label.innerHTML = '<span>' + v + '</span>';
        const inp = document.createElement('input');
        inp.type = 'text';
        inp.dataset.var = v;
        inp.placeholder = v;
        inp.value = varValues[v] || '';
        inp.addEventListener('input', () => { varValues[v] = inp.value; render(); });
        label.appendChild(inp);
        varsContainer.appendChild(label);
      }
    });

    // Render preview
    let filled = text;
    vars.forEach(v => {
      filled = filled.replaceAll('{{' + v + '}}', varValues[v] || '<em class="unfilled">' + v + '</em>');
    });
    preview.innerHTML = filled;
  }

  input.addEventListener('input', render);
  render();
}
```

```css
.template-editor { display: grid; gap: var(--sp-3); }
.template-input {
  width: 100%;
  min-height: 120px;
  padding: var(--sp-3);
  font-family: var(--font-mono);
  font-size: 14px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  resize: vertical;
}
.template-vars { display: flex; flex-wrap: wrap; gap: var(--sp-2); }
.template-var-field { display: flex; align-items: center; gap: var(--sp-2); font: var(--type-caption); }
.template-var-field input { width: 120px; padding: var(--sp-1) var(--sp-2); font: var(--type-small); border: 1px solid var(--border-subtle); border-radius: var(--radius-xs); }
.template-preview {
  padding: var(--sp-4);
  background: var(--bg-muted);
  border-radius: var(--radius-sm);
  font: var(--type-body);
  white-space: pre-wrap;
}
.template-preview .unfilled { color: var(--text-muted); font-style: italic; }
.char-count { font: var(--type-caption); color: var(--text-muted); text-align: right; }
```

---

## 9. Filter / Search

Client-side filtering of displayed items.

### Text Search

```html
<input type="search" class="filter-input" placeholder="Filter items..." aria-label="Filter items">
<div class="filter-list">
  <div class="filter-item" data-keywords="apple fruit red">Apple</div>
  <div class="filter-item" data-keywords="banana fruit yellow">Banana</div>
</div>
```

```js
function setupFilter(inputSelector, itemSelector) {
  const input = document.querySelector(inputSelector);
  input.addEventListener('input', () => {
    const query = input.value.toLowerCase();
    document.querySelectorAll(itemSelector).forEach(item => {
      const text = (item.textContent + ' ' + (item.dataset.keywords || '')).toLowerCase();
      item.classList.toggle('hidden', query && !text.includes(query));
    });
  });
}

// Usage: setupFilter('.filter-input', '.filter-item');
```

### Tag-Based Filter

```html
<div class="tag-filters">
  <button class="tag-btn active" data-tag="all">All</button>
  <button class="tag-btn" data-tag="frontend">Frontend</button>
  <button class="tag-btn" data-tag="backend">Backend</button>
</div>
```

```js
function setupTagFilter(barSelector, itemSelector) {
  document.querySelectorAll(barSelector + ' .tag-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll(barSelector + ' .tag-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tag = btn.dataset.tag;
      document.querySelectorAll(itemSelector).forEach(item => {
        item.classList.toggle('hidden', tag !== 'all' && !item.dataset.tags.includes(tag));
      });
    });
  });
}
```

```css
.filter-input {
  width: 100%;
  padding: var(--sp-2) var(--sp-3);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  font: var(--type-body);
  margin-bottom: var(--sp-3);
}
.filter-input:focus { border-color: var(--accent); outline: none; box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 15%, transparent); }
.tag-filters { display: flex; gap: var(--sp-2); flex-wrap: wrap; margin-bottom: var(--sp-3); }
.tag-btn {
  background: var(--bg-muted);
  border: 1px solid var(--border-subtle);
  border-radius: 999px;
  padding: var(--sp-1) var(--sp-3);
  font: var(--type-caption);
  cursor: pointer;
  transition: all 0.15s ease;
}
.tag-btn:hover { border-color: var(--accent); }
.tag-btn.active { background: var(--accent); color: var(--bg-surface); border-color: var(--accent); }
.tag-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.hidden { display: none !important; }
```

---

## 10. Theme Toggle (Light/Dark)

```html
<button class="theme-toggle no-print" aria-label="Toggle dark mode" onclick="toggleTheme()">
  <span class="theme-icon-light">&#9788;</span>
  <span class="theme-icon-dark">&#9790;</span>
</button>
```

```js
function toggleTheme() {
  const html = document.documentElement;
  html.dataset.theme = html.dataset.theme === 'dark' ? 'light' : 'dark';
}
```

Requires two `:root` blocks -- light tokens as default, dark overrides under `[data-theme="dark"]`:

```css
/* Default light tokens already in :root */

[data-theme="dark"] {
  --color-primary: #64B5F6;
  --bg-page: #1A1A2E;
  --bg-surface: #232340;
  --bg-muted: #2C2C4A;
  --bg-card: #232340;
  --text-primary: #E0E0E0;
  --text-secondary: #A0A0B8;
  --text-muted: #6E6E8A;
  --border-default: #3A3A5C;
  --border-subtle: #2E2E4E;
  --accent: #64B5F6;
  --shadow-sm: inset 0 1px 2px rgba(0,0,0,0.3);
  --shadow-md: inset 0 2px 6px rgba(0,0,0,0.4);
}

.theme-toggle {
  position: fixed;
  top: var(--sp-3);
  right: var(--sp-3);
  background: var(--bg-muted);
  border: 1px solid var(--border-default);
  border-radius: 50%;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 18px;
  z-index: 100;
}
.theme-toggle:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.theme-icon-dark { display: none; }
[data-theme="dark"] .theme-icon-light { display: none; }
[data-theme="dark"] .theme-icon-dark { display: inline; }
```

---

## Shared CSS Utilities

Include as needed in any artifact.

```css
/* Screen reader only */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* Flex centering */
.flex-center {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Text overflow ellipsis */
.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Hide scrollbar, keep scrollable */
.no-scrollbar { overflow: auto; scrollbar-width: none; -ms-overflow-style: none; }
.no-scrollbar::-webkit-scrollbar { display: none; }

/* Focus visible styles (apply globally) */
:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
:focus:not(:focus-visible) { outline: none; }

/* Print: hide interactive elements */
@media print {
  .no-print,
  button,
  input[type="range"],
  .tab-bar,
  .theme-toggle,
  .drag-item[draggable] { display: none !important; }

  body { background: white; color: black; }
  a { color: black; text-decoration: underline; }
  a::after { content: ' (' attr(href) ')'; font-size: 0.8em; }
}
```

---

## Animation Utilities

```css
/* Keyframes */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { transform: translateY(10px); opacity: 0; }
  to { transform: none; opacity: 1; }
}

@keyframes scaleIn {
  from { transform: scale(0.92); opacity: 0; }
  to { transform: none; opacity: 1; }
}

/* Easing presets */
/* Spring: overshoot for interactive feedback */
/* cubic-bezier(.34, 1.56, .64, 1) */

/* Smooth out: decelerate for exits and settling */
/* cubic-bezier(.16, 1, .3, 1) */

/* Stagger delay classes */
.delay-1 { animation-delay: 80ms; }
.delay-2 { animation-delay: 160ms; }
.delay-3 { animation-delay: 240ms; }
.delay-4 { animation-delay: 320ms; }
.delay-5 { animation-delay: 400ms; }
.delay-6 { animation-delay: 480ms; }
.delay-7 { animation-delay: 560ms; }
.delay-8 { animation-delay: 640ms; }

/* Apply animation to elements */
.animate-fade { animation: fadeIn 0.3s cubic-bezier(.16, 1, .3, 1) both; }
.animate-slide { animation: slideUp 0.35s cubic-bezier(.16, 1, .3, 1) both; }
.animate-scale { animation: scaleIn 0.3s cubic-bezier(.34, 1.56, .64, 1) both; }

/* Reduced motion: disable all animations */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Accessibility Patterns

Rules that apply to every pattern above.

| Rule | Implementation |
|---|---|
| Keyboard accessible | All interactive elements are `<button>` or `<a>`, never `<div onclick>` |
| ARIA labels | Icon-only buttons use `aria-label="Description"` |
| Focus indicators | `:focus-visible` with 2px solid outline offset 2px, never `outline: none` alone |
| Reduced motion | `@media (prefers-reduced-motion: reduce)` disables all animation/transition |
| Color not sole indicator | Pair color with icon, text, or shape. `.copied` has text change + color. Tab active has underline + color. Drag-over has border + shadow |
| Roles and states | Tab bars use `role="tablist"`, `role="tab"`, `aria-selected`. Accordions use `aria-expanded`, `aria-controls`. Filters use `aria-label` |
| Touch targets | Minimum 44x44px hit area for buttons, tab items, toggle controls |

### Focus Style Template

```css
/* Apply to any interactive element that needs custom focus */
.interactive-element:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
```

### Screen Reader Announcement (for dynamic changes)

```js
function announce(message) {
  let region = document.getElementById('sr-announce');
  if (!region) {
    region = document.createElement('div');
    region.id = 'sr-announce';
    region.setAttribute('role', 'status');
    region.setAttribute('aria-live', 'polite');
    region.className = 'sr-only';
    document.body.appendChild(region);
  }
  region.textContent = message;
}
```

Use after drag-drop reorder, filter results change, or copy completion.
