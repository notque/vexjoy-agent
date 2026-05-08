# Shape: Design Prototype

Loaded when `detect-shape.py` returns `prototype`. For artifacts where the user adjusts parameters and sees results live: design systems, component variants, animation sandboxes, clickable flows.

**Theme:** Interactive Warm (default). Clean surface, blue accent for actions, prominent shadows on controls.

**Core principle:** Prototypes are INTERACTIVE. Every parameter the user can change updates the preview in real time. Every prototype ends with an export mechanism (Copy Parameters, Copy CSS, Copy Config).

---

## Layout Patterns

| Layout | Use When | Structure |
|---|---|---|
| Split panel | Controls + live preview | Left: controls panel (280-320px fixed), Right: preview (flex: 1) |
| Contact sheet | Variant comparison | Grid of equal cells, each with rendered preview + label |
| Sandbox | Animation tuning | Top: preview area with play/reset, Bottom: control panel |
| Swatch grid | Color/token display | Grid of clickable swatches with copy-on-click |

### Split Panel (controls + preview)

Primary layout. Controls on the left, live preview on the right. Stacks on mobile.

```html
<div class="prototype-layout">
  <aside class="controls-panel" aria-label="Design controls">
    <h2>Controls</h2>
    <!-- Sliders, selectors, toggles -->
    <button class="export-btn" onclick="copyParams()">Copy Parameters</button>
  </aside>
  <section class="preview-panel" aria-label="Live preview">
    <div class="preview-surface" id="preview">
      <!-- Rendered output updates here -->
    </div>
  </section>
</div>
```

```css
.prototype-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: var(--sp-5);
  min-height: 80vh;
}

@media (max-width: 640px) {
  .prototype-layout {
    grid-template-columns: 1fr;
  }
}

.controls-panel {
  padding: var(--sp-5);
  background: var(--bg-surface);
  border-right: 1px solid var(--border-subtle);
  overflow-y: auto;
  max-height: 100vh;
  position: sticky;
  top: 0;
}

.controls-panel h2 {
  font: var(--type-caption);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: var(--sp-4);
}

.preview-panel {
  padding: var(--sp-6);
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-surface {
  width: 100%;
  min-height: 300px;
  background: var(--bg-muted);
  border-radius: var(--radius-md);
  padding: var(--sp-6);
  transition: all 0.2s ease;
}
```

### Sandbox (animation tuning)

Preview area with play/reset buttons above a controls panel.

```html
<div class="sandbox">
  <section class="sandbox-preview" aria-label="Animation preview">
    <div class="animated-element" id="target">
      <!-- The thing being animated -->
    </div>
    <div class="sandbox-actions">
      <button onclick="playAnimation()" aria-label="Play animation">&#9654; Play</button>
      <button onclick="resetAnimation()" aria-label="Reset animation">&#8634; Reset</button>
    </div>
  </section>
  <section class="sandbox-controls" aria-label="Animation controls">
    <!-- Sliders, selectors, checkboxes -->
  </section>
</div>
```

```css
.sandbox {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
}

.sandbox-preview {
  background: var(--bg-muted);
  border-radius: var(--radius-md);
  padding: var(--sp-7);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-5);
  min-height: 300px;
}

.sandbox-actions {
  display: flex;
  gap: var(--sp-3);
}

.sandbox-controls {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--sp-4);
  padding: var(--sp-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
}
```

```js
function playAnimation() {
  const target = document.getElementById('target');
  const duration = document.getElementById('duration-slider').value;
  const easing = document.getElementById('easing-select').value;
  target.style.transition = 'all ' + duration + 'ms ' + easing;
  target.classList.add('animated');
}

function resetAnimation() {
  const target = document.getElementById('target');
  target.style.transition = 'none';
  target.classList.remove('animated');
}
```

---

## Control Patterns

### Slider with Live CSS Variable Update

The fundamental prototype control. Label, range input, value readout. Changing the slider instantly updates a CSS custom property on the preview.

```html
<div class="control-row">
  <label for="padding-slider">Padding</label>
  <input type="range" id="padding-slider" min="4" max="64" value="16"
         oninput="updateVar('--preview-padding', this.value + 'px'); updateReadout('padding-value', this.value + 'px')">
  <span id="padding-value" class="value-display" aria-live="polite">16px</span>
</div>
```

```css
.control-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) 0;
}

.control-row label {
  min-width: 120px;
  font: var(--type-small);
  color: var(--text-secondary);
}

.control-row input[type="range"] {
  flex: 1;
  accent-color: var(--accent);
}

.value-display {
  min-width: 60px;
  text-align: right;
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-muted);
  user-select: all;
}
```

```js
function updateVar(property, value) {
  document.getElementById('preview').style.setProperty(property, value);
}

function updateReadout(id, value) {
  document.getElementById(id).textContent = value;
}
```

### Easing Curve Selector

Dropdown for timing functions. Common easing options plus custom cubic-bezier for spring effects.

```html
<div class="control-row">
  <label for="easing-select">Easing</label>
  <select id="easing-select" onchange="updateEasing(this.value)">
    <option value="linear">Linear</option>
    <option value="ease">Ease</option>
    <option value="ease-in">Ease In</option>
    <option value="ease-out" selected>Ease Out</option>
    <option value="ease-in-out">Ease In-Out</option>
    <option value="cubic-bezier(.34,1.56,.64,1)">Spring</option>
    <option value="cubic-bezier(.16,1,.3,1)">Smooth Out</option>
    <option value="cubic-bezier(.68,-.55,.27,1.55)">Back</option>
  </select>
</div>
```

```js
function updateEasing(value) {
  document.getElementById('target').style.transitionTimingFunction = value;
}
```

### Toggle Switch

Boolean control for on/off states (e.g., "Show border", "Enable shadow").

```html
<div class="control-row">
  <label for="shadow-toggle">Shadow</label>
  <label class="toggle-switch">
    <input type="checkbox" id="shadow-toggle" checked
           onchange="toggleFeature('--preview-shadow', this.checked ? 'var(--shadow-md)' : 'none')">
    <span class="toggle-track" aria-hidden="true"></span>
  </label>
</div>
```

```css
.toggle-switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-track {
  position: absolute;
  inset: 0;
  background: var(--border-default);
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.toggle-track::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  background: var(--bg-surface);
  border-radius: 50%;
  box-shadow: var(--shadow-sm);
  transition: transform 0.2s ease;
}

.toggle-switch input:checked + .toggle-track {
  background: var(--accent);
}

.toggle-switch input:checked + .toggle-track::after {
  transform: translateX(20px);
}

.toggle-switch input:focus-visible + .toggle-track {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
```

```js
function toggleFeature(property, value) {
  document.getElementById('preview').style.setProperty(property, value);
}
```

### Color Picker

Inline color input with hex readout and copy-on-click.

```html
<div class="control-row">
  <label for="accent-picker">Accent</label>
  <input type="color" id="accent-picker" value="#5B8DEF"
         oninput="updateVar('--accent', this.value); updateReadout('accent-value', this.value)">
  <span id="accent-value" class="value-display" onclick="navigator.clipboard.writeText(this.textContent)"
        role="button" tabindex="0" aria-label="Copy color value">#5B8DEF</span>
</div>
```

### Control Group Separator

Visually separates control groups within the panel.

```html
<div class="control-group-label">Typography</div>
```

```css
.control-group-label {
  font: var(--type-caption);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  padding: var(--sp-3) 0 var(--sp-2);
  margin-top: var(--sp-3);
  border-top: 1px solid var(--border-subtle);
}
```

---

## Component Variant Contact Sheet

Grid of rendered component variants for visual comparison. Each cell shows one parameter combination with a label.

```html
<section aria-label="Component variants">
  <h2>Button Variants</h2>
  <div class="variant-grid">
    <div class="variant-cell">
      <div class="variant-preview">
        <!-- Rendered component at this variant -->
        <button class="btn-sm btn-primary">Submit</button>
      </div>
      <div class="variant-label">
        <code>size=sm intent=primary</code>
      </div>
    </div>
    <div class="variant-cell">
      <div class="variant-preview">
        <button class="btn-md btn-primary">Submit</button>
      </div>
      <div class="variant-label">
        <code>size=md intent=primary</code>
      </div>
    </div>
    <!-- repeat for each variant combination -->
  </div>
</section>
```

```css
.variant-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--sp-4);
}

.variant-cell {
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.variant-preview {
  padding: var(--sp-5);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-muted);
  min-height: 80px;
}

.variant-label {
  padding: var(--sp-2) var(--sp-3);
  border-top: 1px solid var(--border-subtle);
  background: var(--bg-surface);
}

.variant-label code {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-muted);
}
```

---

## Design Token Display

### Color Swatch Grid

Clickable swatches that copy the hex value on click.

```html
<section aria-label="Color palette">
  <h2>Colors</h2>
  <div class="swatch-grid">
    <button class="swatch" style="--swatch-color: #D97757"
            onclick="copySwatch(this, '#D97757')" aria-label="Copy color Clay #D97757">
      <span class="swatch-sample" style="background: var(--swatch-color)"></span>
      <span class="swatch-name">Clay</span>
      <span class="swatch-value">#D97757</span>
    </button>
    <button class="swatch" style="--swatch-color: #141413"
            onclick="copySwatch(this, '#141413')" aria-label="Copy color Slate #141413">
      <span class="swatch-sample" style="background: var(--swatch-color)"></span>
      <span class="swatch-name">Slate</span>
      <span class="swatch-value">#141413</span>
    </button>
    <!-- more swatches -->
  </div>
</section>
```

```css
.swatch-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: var(--sp-3);
}

.swatch {
  all: unset;
  cursor: pointer;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  overflow: hidden;
  text-align: center;
  transition: box-shadow 0.15s ease;
}

.swatch:hover {
  box-shadow: var(--shadow-md);
}

.swatch:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.swatch-sample {
  display: block;
  height: 64px;
}

.swatch-name {
  display: block;
  font: var(--type-small);
  font-weight: 500;
  padding: var(--sp-2) var(--sp-2) 0;
  color: var(--text-primary);
}

.swatch-value {
  display: block;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-muted);
  padding: 0 var(--sp-2) var(--sp-2);
}
```

```js
function copySwatch(el, hex) {
  navigator.clipboard.writeText(hex);
  var name = el.querySelector('.swatch-name');
  var original = name.textContent;
  name.textContent = 'Copied!';
  setTimeout(function() { name.textContent = original; }, 1200);
}
```

### Typography Scale Display

```html
<section aria-label="Typography scale">
  <h2>Type Scale</h2>
  <div class="type-specimen">
    <div class="type-row">
      <span class="type-label">Display</span>
      <span class="type-sample" style="font: var(--type-display)">The quick brown fox</span>
    </div>
    <div class="type-row">
      <span class="type-label">H1</span>
      <span class="type-sample" style="font: var(--type-h1)">The quick brown fox</span>
    </div>
    <div class="type-row">
      <span class="type-label">H2</span>
      <span class="type-sample" style="font: var(--type-h2)">The quick brown fox</span>
    </div>
    <div class="type-row">
      <span class="type-label">Body</span>
      <span class="type-sample" style="font: var(--type-body)">The quick brown fox</span>
    </div>
    <div class="type-row">
      <span class="type-label">Small</span>
      <span class="type-sample" style="font: var(--type-small)">The quick brown fox</span>
    </div>
    <div class="type-row">
      <span class="type-label">Caption</span>
      <span class="type-sample" style="font: var(--type-caption)">THE QUICK BROWN FOX</span>
    </div>
  </div>
</section>
```

```css
.type-specimen {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.type-row {
  display: flex;
  align-items: baseline;
  gap: var(--sp-4);
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--border-subtle);
}

.type-label {
  min-width: 80px;
  font: var(--type-caption);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}
```

### Spacing Scale Display

```html
<section aria-label="Spacing scale">
  <h2>Spacing</h2>
  <div class="spacing-specimen">
    <div class="spacing-row">
      <span class="spacing-label">sp-1 (4px)</span>
      <div class="spacing-bar" style="width: 4px;"></div>
    </div>
    <div class="spacing-row">
      <span class="spacing-label">sp-2 (8px)</span>
      <div class="spacing-bar" style="width: 8px;"></div>
    </div>
    <!-- sp-3 through sp-8 -->
  </div>
</section>
```

```css
.spacing-specimen {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.spacing-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.spacing-label {
  min-width: 100px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
}

.spacing-bar {
  height: 24px;
  background: var(--accent);
  border-radius: var(--radius-xs);
  opacity: 0.6;
}
```

---

## Animation Patterns

### Staggered Keyframe Sequence

Multi-step choreographed animation. Each step fires at a specific delay. Use for completion sequences, loading choreography, or multi-element entrances.

```css
/* Stagger delays for choreographed sequence */
.step-1 { animation-delay: 0ms; }
.step-2 { animation-delay: 80ms; }
.step-3 { animation-delay: 120ms; }
.step-4 { animation-delay: 200ms; }
.step-5 { animation-delay: 600ms; }

/* Spring easing — "feels alive" bounce */
.spring {
  transition-timing-function: cubic-bezier(.34, 1.56, .64, 1);
}

/* Smooth deceleration — natural stop */
.smooth-out {
  transition-timing-function: cubic-bezier(.16, 1, .3, 1);
}

/* Snap — quick response, no overshoot */
.snap {
  transition-timing-function: cubic-bezier(0, 0.7, 0.3, 1);
}
```

### CSS Keyframe Templates

```css
@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slide-up {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes scale-in {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

@keyframes check-draw {
  from { stroke-dashoffset: 24; }
  to { stroke-dashoffset: 0; }
}

@keyframes fill-bar {
  from { width: 0; }
  to { width: var(--fill-target, 100%); }
}
```

### Reduced Motion Override

Already handled by the global CSS reset in design-system.md. But for prototype-specific animation controls, offer an explicit toggle:

```html
<div class="control-row">
  <label for="motion-toggle">Reduced Motion</label>
  <label class="toggle-switch">
    <input type="checkbox" id="motion-toggle"
           onchange="document.body.classList.toggle('reduce-motion', this.checked)">
    <span class="toggle-track" aria-hidden="true"></span>
  </label>
</div>
```

```css
body.reduce-motion *,
body.reduce-motion *::before,
body.reduce-motion *::after {
  animation-duration: 0.01ms !important;
  animation-iteration-count: 1 !important;
  transition-duration: 0.01ms !important;
}
```

---

## Drag-to-Reorder

Interactive flow or sequence reordering. Items are draggable, drop zones highlight on dragover.

```html
<div class="reorder-list" id="flow-steps" aria-label="Reorderable flow steps">
  <div class="flow-step" draggable="true"
       ondragstart="dragStart(event)" ondragover="dragOver(event)"
       ondrop="drop(event)" ondragend="dragEnd(event)">
    <span class="grip" aria-hidden="true">&#8942;&#8942;</span>
    <span class="step-content">Step 1: Validate input</span>
  </div>
  <div class="flow-step" draggable="true"
       ondragstart="dragStart(event)" ondragover="dragOver(event)"
       ondrop="drop(event)" ondragend="dragEnd(event)">
    <span class="grip" aria-hidden="true">&#8942;&#8942;</span>
    <span class="step-content">Step 2: Transform data</span>
  </div>
  <div class="flow-step" draggable="true"
       ondragstart="dragStart(event)" ondragover="dragOver(event)"
       ondrop="drop(event)" ondragend="dragEnd(event)">
    <span class="grip" aria-hidden="true">&#8942;&#8942;</span>
    <span class="step-content">Step 3: Persist to store</span>
  </div>
</div>
```

```css
.reorder-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.flow-step {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--sp-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  cursor: default;
  transition: opacity 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}

.flow-step[dragging] {
  opacity: 0.35;
  transform: rotate(2deg);
}

.flow-step.drag-over {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 20%, transparent);
}

.grip {
  cursor: grab;
  color: var(--text-muted);
  font-size: 14px;
  line-height: 1;
  user-select: none;
}

.grip:hover {
  color: var(--text-secondary);
}

.step-content {
  font: var(--type-small);
  flex: 1;
}
```

```js
var draggedEl = null;

function dragStart(e) {
  draggedEl = e.currentTarget;
  draggedEl.setAttribute('dragging', '');
  e.dataTransfer.effectAllowed = 'move';
}

function dragOver(e) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  var target = e.currentTarget;
  if (target !== draggedEl) {
    target.classList.add('drag-over');
  }
}

function drop(e) {
  e.preventDefault();
  var target = e.currentTarget;
  target.classList.remove('drag-over');
  if (target !== draggedEl && draggedEl) {
    var list = target.parentNode;
    var items = Array.from(list.children);
    var draggedIdx = items.indexOf(draggedEl);
    var targetIdx = items.indexOf(target);
    if (draggedIdx < targetIdx) {
      list.insertBefore(draggedEl, target.nextSibling);
    } else {
      list.insertBefore(draggedEl, target);
    }
  }
}

function dragEnd(e) {
  e.currentTarget.removeAttribute('dragging');
  document.querySelectorAll('.drag-over').forEach(function(el) {
    el.classList.remove('drag-over');
  });
  draggedEl = null;
}
```

---

## Export: Copy Parameters Button

**CRITICAL: Every prototype MUST include an export button.** The user tunes parameters interactively, then copies the result as structured data.

### Copy as JSON

```html
<button class="export-btn" onclick="copyParams()">
  Copy Parameters
</button>
```

```css
.export-btn {
  width: 100%;
  margin-top: var(--sp-4);
  padding: var(--sp-3) var(--sp-4);
  background: var(--accent);
  color: #FFFFFF;
  border: none;
  border-radius: var(--radius-sm);
  font: var(--type-small);
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s ease, box-shadow 0.15s ease;
}

.export-btn:hover {
  background: var(--color-primary-hover, var(--accent));
  box-shadow: var(--shadow-interactive-hover, var(--shadow-md));
}

.export-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.export-btn.copied {
  background: var(--color-success);
}
```

```js
function copyParams() {
  var params = {};

  // Collect all range inputs
  document.querySelectorAll('.controls-panel input[type="range"]').forEach(function(input) {
    params[input.id] = input.value;
  });

  // Collect all selects
  document.querySelectorAll('.controls-panel select').forEach(function(select) {
    params[select.id] = select.value;
  });

  // Collect all checkboxes
  document.querySelectorAll('.controls-panel input[type="checkbox"]').forEach(function(cb) {
    params[cb.id] = cb.checked;
  });

  // Collect all color inputs
  document.querySelectorAll('.controls-panel input[type="color"]').forEach(function(color) {
    params[color.id] = color.value;
  });

  navigator.clipboard.writeText(JSON.stringify(params, null, 2));

  // Visual feedback
  var btn = document.querySelector('.export-btn');
  var original = btn.textContent;
  btn.textContent = 'Copied!';
  btn.classList.add('copied');
  setTimeout(function() {
    btn.textContent = original;
    btn.classList.remove('copied');
  }, 1500);
}
```

### Copy as CSS Variables

Alternative export for design token prototypes. Emits `:root { ... }` block.

```js
function copyCSSVars() {
  var lines = [':root {'];
  document.querySelectorAll('.controls-panel input[type="range"]').forEach(function(input) {
    var prop = input.dataset.cssVar;  // data-css-var="--sp-4"
    var unit = input.dataset.unit || 'px';
    if (prop) {
      lines.push('  ' + prop + ': ' + input.value + unit + ';');
    }
  });
  document.querySelectorAll('.controls-panel input[type="color"]').forEach(function(input) {
    var prop = input.dataset.cssVar;
    if (prop) {
      lines.push('  ' + prop + ': ' + input.value + ';');
    }
  });
  lines.push('}');
  navigator.clipboard.writeText(lines.join('\n'));
}
```

---

## Accessibility Requirements

| Requirement | Implementation |
|---|---|
| Slider labels | Every `<input type="range">` has a `<label>` with matching `for` |
| Live readouts | Value displays use `aria-live="polite"` for screen reader updates |
| Keyboard nav | All controls reachable via Tab; sliders adjustable via arrow keys (native) |
| Focus visible | `:focus-visible` ring on all interactive elements |
| Color swatches | Use `<button>` not `<div onclick>`; include `aria-label` with color name and hex |
| Drag-and-drop | Provide keyboard reorder alternative (up/down buttons) for flow reordering |
| Toggle switches | Underlying `<input type="checkbox">` provides native semantics; visible track is `aria-hidden` |
| Reduced motion | Global reset covers animations; prototype offers explicit toggle for testing |
| Touch targets | All buttons and interactive controls minimum 44x44px hit area |

---

## Shape Selection Guidance

Use **prototype** shape when the user's request matches any of:

| Signal | Example Request |
|---|---|
| Tune/adjust parameters | "Let me try different border radius values" |
| Animation sandbox | "Build an animation playground for this transition" |
| Component variants | "Show all button states in a contact sheet" |
| Design system | "Create a living design system preview" |
| Color exploration | "Let me pick colors and see the palette" |
| Flow reordering | "Let me drag steps into different orders" |
| CSS variable tuning | "Build a tool to adjust spacing tokens" |

Do NOT use prototype when:
- The user wants a static report (use **report**)
- The user wants to edit content, not design parameters (use **editor**)
- The user wants data charts (use **data-viz**)
