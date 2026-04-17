# Animation Performance Budgets Reference

> **Scope**: Concrete frame budgets, CSS property render costs, layout thrashing detection, and performance anti-patterns for CSS animations and transitions.
> **Version range**: CSS3+, Chrome/Safari/Firefox (2022+), applies to all animation strategies
> **Generated**: 2026-04-16 — compositor-thread promotion behavior is stable across modern browsers

---

## Overview

Animation performance lives or dies on one constraint: the browser has ~16ms per frame at 60fps, ~11ms at 90fps. CSS animations that trigger layout or paint run on the main thread and steal from that budget. Animations that only affect `transform` and `opacity` run on the compositor thread and cost essentially nothing. The single most impactful performance decision is choosing the right CSS property.

---

## Pattern Table: CSS Property Render Cost

| Property | Render Path | Thread | Use For |
|----------|-------------|--------|---------|
| `transform: translate/scale/rotate` | Composite only | Compositor | All movement, scaling, rotation |
| `opacity` | Composite only | Compositor | Fades, reveals, stagger effects |
| `filter: blur/brightness` | Paint + Composite | Main | Glow effects — use sparingly |
| `background-color` | Paint | Main | Avoid animating — use opacity overlay instead |
| `width` / `height` | Layout + Paint + Composite | Main | Never animate — use `transform: scale` |
| `top` / `left` / `margin` | Layout + Paint + Composite | Main | Never animate — use `transform: translate` |
| `box-shadow` | Paint + Composite | Main | Costly — animate opacity of a pseudo-element instead |
| `border-radius` | Paint | Main | Acceptable for slow UI transitions (> 300ms) |
| `clip-path` | Paint + Composite | Main | Expensive on large elements — test on target hardware |

---

## Correct Patterns

### Compositor-Safe Movement (transform instead of top/left)

All movement animations must use `transform: translate()`, not `top`/`left`/`margin`. This is the highest-impact performance rule.

```css
/* ✅ Compositor thread — zero layout cost */
.hero-title {
  transform: translateY(24px);
  opacity: 0;
  animation: slide-up 0.8s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes slide-up {
  to { transform: translateY(0); opacity: 1; }
}

/* ❌ Main thread layout — causes jank on mid-range devices */
.hero-title {
  position: relative;
  top: 24px;
  animation: slide-up 0.8s ease both;
}
@keyframes slide-up {
  to { top: 0; }
}
```

**Why**: `transform` does not affect document flow — the compositor can run it on the GPU without touching the DOM layout tree. `top` triggers layout recalculation on every frame.

---

### GPU Layer Promotion with `will-change`

Use `will-change` only on elements that will actually animate, and remove it after the animation completes.

```css
/* ✅ Promote before animation, demote after */
.hero-title {
  will-change: transform, opacity;
  animation: slide-up 0.8s cubic-bezier(0.22, 1, 0.36, 1) both;
}

/* Remove after — excessive will-change wastes GPU memory */
.hero-title.animation-complete {
  will-change: auto;
}
```

**Why**: `will-change` tells the browser to create a new compositor layer ahead of time. Without it, the browser creates the layer at animation start, causing a frame spike. But every active `will-change` layer consumes GPU memory — leaving it on all elements exhausts the budget on low-end devices.

---

### Animating box-shadow via Pseudo-Element

`box-shadow` triggers paint on every frame. For hover glow effects, animate the opacity of a pre-rendered pseudo-element instead.

```css
/* ✅ Pre-renders shadow, animates only opacity (compositor) */
.cta-button {
  position: relative;
}
.cta-button::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  box-shadow: 0 0 32px rgba(99, 102, 241, 0.6);
  opacity: 0;
  transition: opacity 0.3s ease;
}
.cta-button:hover::after {
  opacity: 1;
}

/* ❌ Animates box-shadow directly — paint on every frame */
.cta-button {
  box-shadow: none;
  transition: box-shadow 0.3s ease;
}
.cta-button:hover {
  box-shadow: 0 0 32px rgba(99, 102, 241, 0.6);
}
```

---

## Anti-Pattern Catalog
<!-- no-pair-required: section-header-only; pairs live in each sub-section below -->

### ❌ Animating Layout Properties (width/height/top/left/margin)

**Detection**:
```bash
# Find @keyframes blocks that animate layout properties
grep -rn 'width\|height\|top:\|left:\|margin\|padding' --include="*.css" --include="*.scss" -A2 | grep -B2 '%\|from\|to'

# More targeted: find keyframe blocks with layout properties
rg '@keyframes' --type css -A 20 | grep -E '(width|height|top:|left:|margin|padding):'

# Find transition on layout properties
grep -rn 'transition:.*\(width\|height\|top\|left\|margin\)' --include="*.css" --include="*.scss"
rg 'transition-property:\s*(width|height|top|left|margin)' --type css
```

**What it looks like**:
```css
@keyframes expand {
  from { width: 0; height: 0; }
  to   { width: 200px; height: 200px; }
}
.card {
  transition: margin-top 0.3s ease; /* layout shift on hover */
}
```

**Why wrong**: Layout properties trigger the full pipeline (Layout, Paint, Composite) on every frame. At 60fps this means 60 layout recalculations per second. On mid-range mobile this consistently drops below 30fps and causes visible jank.

**Do instead**: Replace layout properties with their `transform` equivalents. `transform: scale` replaces `width`/`height` expansion; `transform: translate` replaces `top`/`left` movement:
```css
@keyframes expand {
  from { transform: scale(0); }
  to   { transform: scale(1); }
}
.card {
  transition: transform 0.3s ease; /* composite only */
}
```

---

### ❌ Animating background-color or color

**Detection**:
```bash
# Find transitions/animations on color properties
grep -rn 'transition:.*color\b\|transition-property:\s*color\b' --include="*.css" --include="*.scss"
grep -rn 'transition:.*background-color\|transition-property:\s*background-color' --include="*.css" --include="*.scss"

# Find color in keyframes
rg '@keyframes' --type css -A 15 | grep -E 'color:|background-color:'
```

**What it looks like**:
```css
.nav-link {
  transition: color 0.2s ease, background-color 0.2s ease;
}
```

**Why wrong**: Both `color` and `background-color` trigger paint. For short transitions (under 200ms) this is acceptable on desktop. On mobile, or for elements that appear many times on the page (nav items, list rows), it causes accumulated paint cost.

**Do instead**: Animate the opacity of a positioned pseudo-element that contains the colored state. The pseudo-element is pre-rendered; only its opacity changes, keeping the transition on the compositor:
```css
/* Animate a positioned pseudo-element's opacity instead of the text color */
.nav-link {
  position: relative;
}
.nav-link::before {
  content: attr(data-hover-text);
  position: absolute;
  color: var(--color-accent);
  opacity: 0;
  transition: opacity 0.2s ease;
}
.nav-link:hover::before { opacity: 1; }

/* Or accept the paint cost for subtle nav transitions; not every hover needs optimization */
```

---

### ❌ `transition: all` (Blanket Transitions)

**Detection**:
```bash
# Find transition: all declarations
grep -rn 'transition:\s*all\b' --include="*.css" --include="*.scss" --include="*.module.css"
rg 'transition:\s*all\b' --type css
```

**What it looks like**:
```css
.card {
  transition: all 0.3s ease; /* animates everything that changes */
}
```

**Why wrong**: `transition: all` watches every animatable property. Adding a layout-triggering property later (even indirectly through a media query) silently introduces jank. It also animates properties you never intended to animate (e.g., `display`, `visibility`, inherited colors).

**Do instead**: Declare only the compositor-safe properties you actually want to animate. Explicit lists are self-documenting and immune to accidental layout animations:
```css
.card {
  transition: transform 0.3s ease, opacity 0.2s ease; /* explicit, compositor-safe */
}
```

---

### ❌ `will-change` on Everything

**Detection**:
```bash
# Find will-change declarations
grep -rn 'will-change:' --include="*.css" --include="*.scss" --include="*.module.css"
rg 'will-change:' --type css
```

**What it looks like**:
```css
* { will-change: transform; }  /* nuclear option — crashes low-end devices */
.card { will-change: transform, opacity, filter; } /* too many properties */
```

**Why wrong**: Each `will-change` layer consumes GPU memory. Blanket use exhausts VRAM on low-end mobile (typically 512MB to 1GB GPU memory budget), causing the browser to fall back to software rendering, which is slower than not using `will-change` at all.

**Do instead**: Apply `will-change` only to the element immediately before its animation starts, and remove it via JS after the animation ends. Use the AnimationEvent `animationend` listener or a class swap:
```js
el.classList.add('is-animating'); // CSS sets will-change: transform
el.addEventListener('animationend', () => {
  el.classList.remove('is-animating'); // CSS removes will-change
}, { once: true });
```

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Jank on scroll (Chrome DevTools shows "Forced reflow") | Animating `top`/`left` or reading `offsetTop` in a rAF loop | Switch to `transform: translate`; use `IntersectionObserver` instead of scroll position reads |
| Green paint flashes in Chrome "Paint flashing" overlay | `background-color` or `box-shadow` animating | Switch to pseudo-element opacity trick for box-shadow; avoid animating background-color |
| GPU memory warning in DevTools Layers panel | Too many `will-change` layers active simultaneously | Scope `will-change` to only actively-animating elements |
| 30fps on mobile but 60fps on desktop | Layout properties animating (`width`/`margin`) | Replace with `transform: scale/translate` equivalent |
| `transition: all` catching unexpected properties | Media query or JS adds a layout-triggering property to the element | Replace `transition: all` with explicit property list |

---

## Quick Frame Budget Reference

| Target FPS | Frame Budget | Comfortable animation budget (half) |
|------------|-------------|--------------------------------------|
| 60fps | 16.67ms | ~8ms for JS + CSS combined |
| 90fps | 11.11ms | ~5ms |
| 120fps | 8.33ms | ~4ms |

**Rule**: If DevTools Performance panel shows any frame over 16ms during an animation, investigate. Frames over 33ms are visible jank to most users.

---

## See Also

- `animation-patterns.md` — choreography patterns with easing curves and timing values
- `background-techniques.md` — layered gradient recipes (background gradients do not animate, so no paint cost)
