# Shape: Custom Editor

Loaded when shape = `editor`. For throwaway purpose-built editing interfaces: ticket triage boards, feature flag editors, prompt tuners, config editors, dataset curators.

**Theme:** Interactive Warm (clean surface, prominent controls, blue accent for actions).

---

## Core Principle

Custom editors solve ONE problem with ONE interface, then export the result. Not a product — a single-use tool. Every editor MUST end with an export mechanism (copy as markdown, copy as JSON, or both).

---

## Export Button Pattern (MANDATORY for every editor)

Every editor artifact gets a sticky bottom export bar. No exceptions.

### HTML

```html
<div class="export-bar">
  <span class="pending-badge" id="pending-count" style="display: none;">0 changes</span>
  <button class="btn-secondary" onclick="resetState()">↺ Reset</button>
  <button class="btn-primary" onclick="copyAsMarkdown()">📋 Copy as Markdown</button>
  <button class="btn-primary" onclick="copyAsJSON()">📋 Copy as JSON</button>
</div>
```

### CSS

```css
.export-bar {
  position: sticky;
  bottom: 0;
  background: var(--bg-page);
  border-top: 1px solid var(--border-default);
  padding: var(--sp-3) var(--sp-5);
  display: flex;
  gap: var(--sp-3);
  align-items: center;
  justify-content: flex-end;
  z-index: 50;
}

.btn-primary {
  background: var(--accent);
  color: white;
  border: none;
  padding: var(--sp-2) var(--sp-4);
  border-radius: var(--radius-sm);
  font: var(--type-small);
  font-weight: 500;
  cursor: pointer;
  box-shadow: var(--shadow-interactive);
  transition: box-shadow 0.15s ease, background 0.15s ease;
}
.btn-primary:hover {
  filter: brightness(0.9);
  box-shadow: var(--shadow-interactive-hover);
}
.btn-primary:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.btn-secondary {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-default);
  padding: var(--sp-2) var(--sp-4);
  border-radius: var(--radius-sm);
  font: var(--type-small);
  cursor: pointer;
  transition: background 0.15s ease;
}
.btn-secondary:hover {
  background: var(--bg-muted);
}
.btn-secondary:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.pending-badge {
  background: var(--color-warning);
  color: white;
  padding: var(--sp-1) var(--sp-3);
  border-radius: 999px;
  font: var(--type-caption);
  font-weight: 600;
  margin-right: auto;
}
```

### JS: Copy with Visual Feedback

```js
function copyWithFeedback(btn, text) {
  navigator.clipboard.writeText(text);
  const original = btn.textContent;
  btn.textContent = '✓ Copied!';
  const originalBg = btn.style.background;
  btn.style.background = 'var(--color-success)';
  setTimeout(() => {
    btn.textContent = original;
    btn.style.background = originalBg;
  }, 1500);
}
```

### JS: Pending Changes Counter

```js
let changeCount = 0;

function trackChange() {
  changeCount++;
  const badge = document.getElementById('pending-count');
  badge.textContent = `${changeCount} change${changeCount !== 1 ? 's' : ''}`;
  badge.style.display = 'inline-block';
}

function resetPendingCount() {
  changeCount = 0;
  document.getElementById('pending-count').style.display = 'none';
}
```

---

## Editor Type 1: Kanban Triage Board

Drag tickets between columns (Now / Next / Later / Cut), then export the triage result.

### HTML Structure

```html
<header class="editor-header">
  <h1>Ticket Triage</h1>
  <div class="header-controls">
    <input type="text" id="filter-input" placeholder="Filter tickets…"
           oninput="filterCards(this.value)" aria-label="Filter tickets">
    <div class="active-filters" id="active-filters"></div>
  </div>
</header>

<div class="kanban" role="region" aria-label="Triage board">
  <div class="kanban-column" id="col-now" ondragover="allowDrop(event)" ondrop="dropCard(event)">
    <h2 class="column-header">Now <span class="count" aria-live="polite">0</span></h2>
    <div class="card-container" role="list">
      <!-- cards inserted here -->
    </div>
  </div>
  <div class="kanban-column" id="col-next" ondragover="allowDrop(event)" ondrop="dropCard(event)">
    <h2 class="column-header">Next <span class="count" aria-live="polite">0</span></h2>
    <div class="card-container" role="list"></div>
  </div>
  <div class="kanban-column" id="col-later" ondragover="allowDrop(event)" ondrop="dropCard(event)">
    <h2 class="column-header">Later <span class="count" aria-live="polite">0</span></h2>
    <div class="card-container" role="list"></div>
  </div>
  <div class="kanban-column" id="col-cut" ondragover="allowDrop(event)" ondrop="dropCard(event)">
    <h2 class="column-header">Cut <span class="count" aria-live="polite">0</span></h2>
    <div class="card-container" role="list"></div>
  </div>
</div>
```

### Card Element

```html
<div class="ticket-card card-elevated" draggable="true" data-id="TICK-001"
     data-tags="auth,backend" ondragstart="dragStart(event)" role="listitem">
  <div class="card-id">TICK-001</div>
  <div class="card-title">Implement auth flow</div>
  <div class="card-meta">
    <span class="card-priority badge-danger">P1</span>
    <span class="card-estimate">3pt</span>
  </div>
  <div class="card-tags">
    <button class="tag" onclick="filterByTag('auth')">auth</button>
    <button class="tag" onclick="filterByTag('backend')">backend</button>
  </div>
</div>
```

### Kanban CSS

```css
.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--sp-4) var(--sp-5);
  border-bottom: 1px solid var(--border-subtle);
  flex-wrap: wrap;
  gap: var(--sp-3);
}
.editor-header h1 {
  font: var(--type-h2);
  color: var(--text-primary);
}
.header-controls {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}
.header-controls input {
  width: 220px;
}

.kanban {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--sp-4);
  padding: var(--sp-5);
  min-height: 400px;
}
@media (max-width: 1024px) {
  .kanban { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
  .kanban { grid-template-columns: 1fr; }
}

.kanban-column {
  background: var(--bg-muted);
  border-radius: var(--radius-md);
  padding: var(--sp-3);
  min-height: 300px;
  transition: background 0.15s ease;
}
.kanban-column.drag-over {
  background: color-mix(in srgb, var(--accent) 8%, var(--bg-muted));
  outline: 2px dashed var(--accent);
  outline-offset: -2px;
}

.column-header {
  font: var(--type-small);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  padding: var(--sp-2) var(--sp-2) var(--sp-3);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.column-header .count {
  background: var(--bg-surface);
  padding: var(--sp-1) var(--sp-2);
  border-radius: 999px;
  font: var(--type-caption);
  min-width: 24px;
  text-align: center;
}

.card-container {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.ticket-card {
  background: var(--bg-surface);
  border-radius: var(--radius-sm);
  padding: var(--sp-3);
  box-shadow: var(--shadow-sm);
  cursor: grab;
  transition: box-shadow 0.15s ease, opacity 0.15s ease, transform 0.15s ease;
  user-select: none;
}
.ticket-card:hover {
  box-shadow: var(--shadow-md);
}
.ticket-card:active {
  cursor: grabbing;
}

.card-id {
  font: var(--type-caption);
  color: var(--text-muted);
  margin-bottom: var(--sp-1);
}
.card-title {
  font: var(--type-small);
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: var(--sp-2);
}
.card-meta {
  display: flex;
  gap: var(--sp-2);
  align-items: center;
  margin-bottom: var(--sp-2);
}
.card-priority {
  font: var(--type-caption);
  padding: var(--sp-1) var(--sp-2);
  border-radius: 999px;
}
.card-estimate {
  font: var(--type-caption);
  color: var(--text-muted);
}

.card-tags {
  display: flex;
  gap: var(--sp-1);
  flex-wrap: wrap;
}
.tag {
  background: var(--bg-muted);
  color: var(--text-secondary);
  border: none;
  padding: 2px var(--sp-2);
  border-radius: var(--radius-xs);
  font: var(--type-caption);
  cursor: pointer;
  transition: background 0.1s ease;
}
.tag:hover {
  background: color-mix(in srgb, var(--accent) 15%, transparent);
  color: var(--accent);
}
.tag.active {
  background: color-mix(in srgb, var(--accent) 20%, transparent);
  color: var(--accent);
  font-weight: 600;
}
.tag:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}

.active-filters {
  display: flex;
  gap: var(--sp-1);
}
.filter-pill {
  background: color-mix(in srgb, var(--accent) 15%, transparent);
  color: var(--accent);
  padding: var(--sp-1) var(--sp-2);
  border-radius: 999px;
  font: var(--type-caption);
  display: flex;
  align-items: center;
  gap: var(--sp-1);
}
.filter-pill button {
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  padding: 0;
  font-size: 14px;
  line-height: 1;
  box-shadow: none;
}
```

### Drag-and-Drop JS

```js
let draggedCard = null;

function dragStart(e) {
  draggedCard = e.target.closest('.ticket-card');
  draggedCard.style.opacity = '0.35';
  draggedCard.style.transform = 'rotate(2deg)';
  e.dataTransfer.effectAllowed = 'move';
}

function allowDrop(e) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  const column = e.target.closest('.kanban-column');
  if (column) column.classList.add('drag-over');
}

function dropCard(e) {
  e.preventDefault();
  const column = e.target.closest('.kanban-column');
  if (!column || !draggedCard) return;
  column.querySelector('.card-container').appendChild(draggedCard);
  draggedCard.style.opacity = '1';
  draggedCard.style.transform = 'none';
  column.classList.remove('drag-over');
  draggedCard = null;
  updateCounts();
  trackChange();
}

document.addEventListener('dragend', () => {
  document.querySelectorAll('.kanban-column').forEach(c =>
    c.classList.remove('drag-over')
  );
  if (draggedCard) {
    draggedCard.style.opacity = '1';
    draggedCard.style.transform = 'none';
  }
});

function updateCounts() {
  document.querySelectorAll('.kanban-column').forEach(col => {
    const count = col.querySelectorAll('.ticket-card').length;
    col.querySelector('.count').textContent = count;
  });
}
```

### Tag Filtering JS

```js
const activeFilters = new Set();

function filterByTag(tag) {
  if (activeFilters.has(tag)) {
    activeFilters.delete(tag);
  } else {
    activeFilters.add(tag);
  }
  applyFilters();
  renderFilterPills();
}

function filterCards(query) {
  const q = query.toLowerCase();
  document.querySelectorAll('.ticket-card').forEach(card => {
    const text = card.textContent.toLowerCase();
    const matchesQuery = !q || text.includes(q);
    const matchesTags = activeFilters.size === 0 ||
      Array.from(activeFilters).some(t =>
        (card.dataset.tags || '').split(',').includes(t)
      );
    card.style.display = (matchesQuery && matchesTags) ? '' : 'none';
  });
}

function applyFilters() {
  filterCards(document.getElementById('filter-input').value);
  // Update tag active states
  document.querySelectorAll('.tag').forEach(el => {
    el.classList.toggle('active', activeFilters.has(el.textContent));
  });
}

function renderFilterPills() {
  const container = document.getElementById('active-filters');
  container.innerHTML = '';
  activeFilters.forEach(tag => {
    const pill = document.createElement('span');
    pill.className = 'filter-pill';
    pill.innerHTML = `${tag} <button onclick="filterByTag('${tag}')" aria-label="Remove ${tag} filter">×</button>`;
    container.appendChild(pill);
  });
}
```

### Kanban Export JS

```js
function copyAsMarkdown() {
  const columns = ['now', 'next', 'later', 'cut'];
  let md = '# Triage Results\n\n';
  columns.forEach(col => {
    const cards = document.querySelectorAll(`#col-${col} .ticket-card`);
    md += `## ${col.charAt(0).toUpperCase() + col.slice(1)} (${cards.length})\n\n`;
    cards.forEach(card => {
      const id = card.querySelector('.card-id').textContent;
      const title = card.querySelector('.card-title').textContent;
      const tags = Array.from(card.querySelectorAll('.tag')).map(t => t.textContent).join(', ');
      md += `- **${id}**: ${title}`;
      if (tags) md += ` [${tags}]`;
      md += '\n';
    });
    md += '\n';
  });
  copyWithFeedback(event.target, md);
}

function copyAsJSON() {
  const columns = ['now', 'next', 'later', 'cut'];
  const result = {};
  columns.forEach(col => {
    result[col] = [];
    document.querySelectorAll(`#col-${col} .ticket-card`).forEach(card => {
      result[col].push({
        id: card.querySelector('.card-id').textContent,
        title: card.querySelector('.card-title').textContent,
        tags: Array.from(card.querySelectorAll('.tag')).map(t => t.textContent),
      });
    });
  });
  copyWithFeedback(event.target, JSON.stringify(result, null, 2));
}
```

---

## Editor Type 2: Feature Flag Editor

Toggle flags on/off, see dependency warnings, export the diff or full state.

### HTML Structure

```html
<header class="editor-header">
  <h1>Feature Flags</h1>
  <div class="header-controls">
    <select id="env-select" onchange="loadEnvironment(this.value)" aria-label="Environment">
      <option value="dev">Development</option>
      <option value="staging">Staging</option>
      <option value="prod">Production</option>
    </select>
    <span class="pending-badge" id="flag-changes" style="display: none;"></span>
  </div>
</header>

<div class="flag-list" role="list">
  <!-- flag rows inserted by JS from FLAGS data -->
</div>
```

### Flag Row HTML

```html
<div class="flag-row" role="listitem">
  <label class="toggle" aria-label="Toggle dark_mode flag">
    <input type="checkbox" data-flag="dark_mode" onchange="toggleFlag(this)">
    <span class="toggle-slider"></span>
  </label>
  <div class="flag-info">
    <span class="flag-name">dark_mode</span>
    <span class="flag-area badge-info">ui</span>
    <span class="flag-desc">Enable dark mode across the application</span>
    <span class="flag-deps" id="deps-dark_mode" role="alert"></span>
  </div>
</div>
```

### Flag Editor CSS

```css
.flag-list {
  padding: var(--sp-4) var(--sp-5);
  max-width: 720px;
  margin: 0 auto;
}

.flag-row {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-4);
  padding: var(--sp-4) 0;
  border-bottom: 1px solid var(--border-subtle);
}
.flag-row:last-child {
  border-bottom: none;
}

.flag-info {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--sp-2);
}
.flag-name {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.flag-area {
  font: var(--type-caption);
  padding: var(--sp-1) var(--sp-2);
  border-radius: 999px;
}
.flag-desc {
  width: 100%;
  font: var(--type-small);
  color: var(--text-muted);
  margin-top: var(--sp-1);
}
.flag-deps {
  width: 100%;
  font: var(--type-small);
  margin-top: var(--sp-1);
}

/* Toggle Switch */
.toggle {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
  flex-shrink: 0;
  margin-top: 2px;
}
.toggle input {
  opacity: 0;
  width: 0;
  height: 0;
  position: absolute;
}
.toggle-slider {
  position: absolute;
  inset: 0;
  background: var(--border-default);
  border-radius: 24px;
  cursor: pointer;
  transition: background 0.2s ease;
}
.toggle-slider::before {
  content: '';
  position: absolute;
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background: white;
  border-radius: 50%;
  transition: transform 0.2s ease;
  box-shadow: var(--shadow-sm);
}
.toggle input:checked + .toggle-slider {
  background: var(--accent);
}
.toggle input:checked + .toggle-slider::before {
  transform: translateX(20px);
}
.toggle input:focus-visible + .toggle-slider {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* Changed-state indicator */
.flag-row.changed {
  background: color-mix(in srgb, var(--color-warning) 6%, transparent);
  margin: 0 calc(-1 * var(--sp-3));
  padding-left: var(--sp-3);
  padding-right: var(--sp-3);
  border-radius: var(--radius-sm);
}
```

### Flag Editor JS

```js
// Define flags as data. Populate from user's request.
const FLAGS = {
  dark_mode:    { area: 'ui',       desc: 'Enable dark mode across the application', requires: [] },
  new_nav:      { area: 'ui',       desc: 'Redesigned navigation sidebar',            requires: [] },
  ai_search:    { area: 'search',   desc: 'AI-powered search results',                requires: ['embeddings_v2'] },
  embeddings_v2:{ area: 'infra',    desc: 'Use v2 embedding model',                   requires: [] },
  beta_api:     { area: 'api',      desc: 'Enable beta API endpoints',                requires: [] },
  rate_limit_v2:{ area: 'api',      desc: 'New rate limiting algorithm',               requires: ['beta_api'] },
};

let initialState = {};
let currentState = {};

function initFlags() {
  const list = document.querySelector('.flag-list');
  Object.entries(FLAGS).forEach(([key, flag]) => {
    initialState[key] = false;
    currentState[key] = false;

    const row = document.createElement('div');
    row.className = 'flag-row';
    row.setAttribute('role', 'listitem');
    row.id = `row-${key}`;
    row.innerHTML = `
      <label class="toggle" aria-label="Toggle ${key} flag">
        <input type="checkbox" data-flag="${key}" onchange="toggleFlag(this)">
        <span class="toggle-slider"></span>
      </label>
      <div class="flag-info">
        <span class="flag-name">${key}</span>
        <span class="flag-area badge-info">${flag.area}</span>
        <span class="flag-desc">${flag.desc}</span>
        <span class="flag-deps" id="deps-${key}" role="alert"></span>
      </div>
    `;
    list.appendChild(row);
  });
}

function toggleFlag(input) {
  const flag = input.dataset.flag;
  currentState[flag] = input.checked;

  // Check dependency warnings
  const deps = FLAGS[flag].requires || [];
  const unmet = deps.filter(d => !currentState[d]);
  const depsEl = document.getElementById(`deps-${flag}`);
  if (unmet.length && input.checked) {
    depsEl.textContent = `⚠ Requires: ${unmet.join(', ')}`;
    depsEl.style.color = 'var(--color-warning)';
  } else {
    depsEl.textContent = '';
  }

  // Warn dependents when disabling
  if (!input.checked) {
    Object.entries(FLAGS).forEach(([k, f]) => {
      if (f.requires.includes(flag) && currentState[k]) {
        const el = document.getElementById(`deps-${k}`);
        el.textContent = `⚠ Dependency disabled: ${flag}`;
        el.style.color = 'var(--color-danger)';
      }
    });
  }

  // Mark changed rows
  const row = document.getElementById(`row-${flag}`);
  row.classList.toggle('changed', currentState[flag] !== initialState[flag]);

  updatePendingCount();
}

function updatePendingCount() {
  const changed = Object.keys(currentState).filter(k => currentState[k] !== initialState[k]);
  const badge = document.getElementById('flag-changes');
  if (changed.length) {
    badge.textContent = `${changed.length} pending`;
    badge.style.display = 'inline-block';
  } else {
    badge.style.display = 'none';
  }
}
```

### Flag Export JS

```js
function copyAsMarkdown() {
  const changed = Object.entries(currentState)
    .filter(([k, v]) => v !== initialState[k]);
  if (!changed.length) {
    copyWithFeedback(event.target, '(no changes)');
    return;
  }
  let md = '# Flag Changes\n\n';
  changed.forEach(([k, v]) => {
    md += `- ${v ? '✅ Enable' : '❌ Disable'} \`${k}\`\n`;
    const deps = FLAGS[k].requires || [];
    if (deps.length) md += `  - Requires: ${deps.join(', ')}\n`;
  });
  copyWithFeedback(event.target, md);
}

function copyAsJSON() {
  const diff = {};
  Object.entries(currentState).forEach(([k, v]) => {
    if (v !== initialState[k]) {
      diff[k] = { from: initialState[k], to: v };
    }
  });
  const output = {
    environment: document.getElementById('env-select')?.value || 'dev',
    timestamp: new Date().toISOString(),
    changes: diff,
    full_state: { ...currentState },
  };
  copyWithFeedback(event.target, JSON.stringify(output, null, 2));
}

function resetState() {
  Object.keys(currentState).forEach(k => {
    currentState[k] = initialState[k];
    const input = document.querySelector(`[data-flag="${k}"]`);
    if (input) input.checked = initialState[k];
    const row = document.getElementById(`row-${k}`);
    if (row) row.classList.remove('changed');
    const deps = document.getElementById(`deps-${k}`);
    if (deps) deps.textContent = '';
  });
  updatePendingCount();
  resetPendingCount();
}
```

---

## Editor Type 3: Split-Pane Prompt Tuner

Edit a template on the left, see live-rendered previews on the right with sample inputs.

### HTML Structure

```html
<header class="editor-header">
  <h1>Prompt Tuner</h1>
  <div class="header-controls">
    <span class="token-counter">
      <span id="char-count">0</span> chars ·
      <span id="token-estimate">0</span> tokens (est.)
    </span>
  </div>
</header>

<div class="tuner-layout">
  <div class="editor-pane">
    <h2>Template</h2>
    <div contenteditable="true" id="template-editor"
         oninput="renderPreviews()"
         class="editable-area"
         role="textbox"
         aria-label="Prompt template editor"
         aria-multiline="true"
         spellcheck="false">You are a {{role}} assistant. Help the user {{task}}. Respond in {{tone}} tone.</div>
    <div class="variable-legend" id="variable-legend"></div>
  </div>
  <div class="preview-pane">
    <h2>Previews</h2>
    <div class="sample-cards">
      <div class="sample-card card-outlined">
        <div class="sample-label">Sample 1</div>
        <div class="sample-preview" id="preview-0"></div>
      </div>
      <div class="sample-card card-outlined">
        <div class="sample-label">Sample 2</div>
        <div class="sample-preview" id="preview-1"></div>
      </div>
      <div class="sample-card card-outlined">
        <div class="sample-label">Sample 3</div>
        <div class="sample-preview" id="preview-2"></div>
      </div>
    </div>
  </div>
</div>
```

### Tuner CSS

```css
.tuner-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-5);
  padding: var(--sp-5);
  min-height: calc(100vh - 200px);
}
@media (max-width: 768px) {
  .tuner-layout {
    grid-template-columns: 1fr;
    min-height: auto;
  }
}

.editor-pane h2,
.preview-pane h2 {
  font: var(--type-small);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: var(--sp-3);
}

.editable-area {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  padding: var(--sp-4);
  min-height: 200px;
  font-family: var(--font-mono);
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
  white-space: pre-wrap;
  word-break: break-word;
}
.editable-area:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 15%, transparent);
}

.token-counter {
  font: var(--type-caption);
  color: var(--text-muted);
  background: var(--bg-muted);
  padding: var(--sp-1) var(--sp-3);
  border-radius: 999px;
}

.variable-legend {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
  margin-top: var(--sp-3);
}
.variable-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
  padding: var(--sp-1) var(--sp-2);
  border-radius: var(--radius-xs);
  font: var(--type-caption);
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  color: var(--accent);
}
.variable-chip.unmatched {
  background: color-mix(in srgb, var(--color-danger) 10%, transparent);
  color: var(--color-danger);
}

.sample-cards {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.sample-card {
  padding: var(--sp-3);
}
.sample-label {
  font: var(--type-caption);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: var(--sp-2);
}
.sample-preview {
  font: var(--type-small);
  line-height: 1.6;
  color: var(--text-primary);
}

/* Variable slot highlight (inside rendered previews) */
.var-filled {
  background: color-mix(in srgb, var(--color-success) 15%, transparent);
  padding: 1px 3px;
  border-radius: 2px;
}
.var-missing {
  border-bottom: 2px dashed var(--color-danger);
  color: var(--color-danger);
}
.var-slot {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  padding: 1px 4px;
  border-radius: 3px;
  border-bottom: 2px dashed var(--accent);
}
```

### Tuner JS

```js
const SAMPLES = [
  { role: 'coding', task: 'debug a React component', tone: 'concise' },
  { role: 'writing', task: 'draft a blog post',      tone: 'friendly' },
  { role: 'data',   task: 'analyze sales trends',    tone: 'formal' },
];

function renderPreviews() {
  const template = document.getElementById('template-editor').textContent;

  // Render each sample
  SAMPLES.forEach((sample, i) => {
    let filled = escapeHtml(template);
    // Fill known variables
    Object.entries(sample).forEach(([k, v]) => {
      const re = new RegExp(`\\{\\{${k}\\}\\}`, 'g');
      filled = filled.replace(re, `<span class="var-filled">${escapeHtml(v)}</span>`);
    });
    // Highlight unrecognized variables
    filled = filled.replace(/\{\{(\w+)\}\}/g,
      '<span class="var-missing">{{$1}}</span>');
    document.getElementById(`preview-${i}`).innerHTML = filled;
  });

  updateTokenCount(template);
  updateVariableLegend(template);
  trackChange();
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function updateTokenCount(text) {
  const chars = text.length;
  // Rough estimate: ~4 chars per token for English
  const tokens = Math.ceil(chars / 4);
  document.getElementById('char-count').textContent = chars;
  document.getElementById('token-estimate').textContent = tokens;
}

function updateVariableLegend(text) {
  const vars = [...text.matchAll(/\{\{(\w+)\}\}/g)].map(m => m[1]);
  const unique = [...new Set(vars)];
  const sampleKeys = Object.keys(SAMPLES[0]);
  const legend = document.getElementById('variable-legend');
  legend.innerHTML = unique.map(v => {
    const matched = sampleKeys.includes(v);
    return `<span class="variable-chip ${matched ? '' : 'unmatched'}">${matched ? '✓' : '?'} {{${v}}}</span>`;
  }).join('');
}
```

### Tuner Export JS

```js
function copyAsMarkdown() {
  const template = document.getElementById('template-editor').textContent;
  const vars = [...new Set([...template.matchAll(/\{\{(\w+)\}\}/g)].map(m => m[1]))];
  let md = '# Prompt Template\n\n';
  md += '```\n' + template + '\n```\n\n';
  md += `**Variables:** ${vars.map(v => '`{{' + v + '}}`').join(', ')}\n\n`;
  md += '## Sample Outputs\n\n';
  SAMPLES.forEach((sample, i) => {
    let filled = template;
    Object.entries(sample).forEach(([k, v]) => {
      filled = filled.replace(new RegExp(`\\{\\{${k}\\}\\}`, 'g'), v);
    });
    md += `### Sample ${i + 1}\n\n${filled}\n\n`;
  });
  copyWithFeedback(event.target, md);
}

function copyAsJSON() {
  const template = document.getElementById('template-editor').textContent;
  const vars = [...new Set([...template.matchAll(/\{\{(\w+)\}\}/g)].map(m => m[1]))];
  const output = {
    template: template,
    variables: vars,
    samples: SAMPLES.map(s => {
      let filled = template;
      Object.entries(s).forEach(([k, v]) => {
        filled = filled.replace(new RegExp(`\\{\\{${k}\\}\\}`, 'g'), v);
      });
      return { inputs: s, rendered: filled };
    }),
  };
  copyWithFeedback(event.target, JSON.stringify(output, null, 2));
}

function resetState() {
  document.getElementById('template-editor').textContent =
    'You are a {{role}} assistant. Help the user {{task}}. Respond in {{tone}} tone.';
  renderPreviews();
  resetPendingCount();
}
```

---

## Pattern Selection Guide

| Need | Editor Type | Key Patterns |
|---|---|---|
| Reorder / categorize items | Kanban triage | Drag-drop, columns, tag filters, count badges |
| Toggle binary settings | Flag editor | Toggle switches, dependency warnings, diff export |
| Edit text with live preview | Split-pane tuner | Contenteditable, variable highlighting, sample rendering |
| Pick from constrained options | Config editor | Select dropdowns, radio groups, validation, export |
| Curate a dataset | List editor | Inline edit, add/remove rows, bulk select, CSV export |

---

## Shared Anti-Patterns

| Pattern | Why Wrong | Do Instead |
|---|---|---|
| Editor without export | User made decisions but can't extract them | Always include the export bar |
| `<input type="text">` for rich editing | Can't highlight variables or format content | Use `contenteditable` with variable slot highlighting |
| Alert-based feedback ("Copied!") | Blocks interaction, jarring | Use inline visual feedback (button text change) |
| No reset button | User can't undo mistakes | Always include reset in export bar |
| Hardcoded data in HTML | Can't adapt to different content | Define data as a JS object, render dynamically |
| `<div>` for tag filters | Not keyboard accessible | Use `<button>` elements for clickable tags |
| No pending changes indicator | User loses track of what changed | Show change count badge in export bar |
