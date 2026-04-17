# SlideController Reference

> **Scope**: JavaScript `SlideController` class implementation for single-file HTML presentations — keyboard, touch, wheel, Intersection Observer, and transition guard patterns.
> **Version range**: Modern browsers (Chrome 88+, Firefox 87+, Safari 14+). Vanilla JS; no framework dependencies.
> **Generated**: 2026-04-17

---

## Overview

`SlideController` manages navigation between full-viewport slides. The two most common failure modes are (1) multi-slide jumps on wheel events because wheel fires many times per scroll gesture, and (2) reveal animations silently broken because `display: none` removes elements from the Intersection Observer callback tree. Every controller must guard both.

---

## Correct Patterns

### Canonical SlideController skeleton

Complete, copy-pasteable implementation satisfying all Phase 4 requirements.

```javascript
class SlideController {
  constructor() {
    this.slides = Array.from(document.querySelectorAll('.slide'));
    this.current = 0;
    this.navigating = false;
    this._wheelTimer = null;

    this._bindKeyboard();
    this._bindTouch();
    this._bindWheel();
    this._bindIO();
    this._updateIndicator();
  }

  go(index) {
    const target = Math.max(0, Math.min(index, this.slides.length - 1));
    if (target === this.current || this.navigating) return;

    this.navigating = true;
    this.current = target;
    this.slides[target].scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' });
    this._updateIndicator();

    // Release guard after transition completes
    setTimeout(() => { this.navigating = false; }, 600);
  }

  _bindKeyboard() {
    document.addEventListener('keydown', (e) => {
      switch (e.key) {
        case 'ArrowRight': case 'Space':     e.preventDefault(); this.go(this.current + 1); break;
        case 'ArrowLeft':  case 'Backspace': e.preventDefault(); this.go(this.current - 1); break;
        case 'Home': this.go(0); break;
        case 'End':  this.go(this.slides.length - 1); break;
      }
    });
  }

  _bindTouch() {
    let startX = 0;
    document.addEventListener('touchstart', (e) => { startX = e.changedTouches[0].clientX; }, { passive: true });
    document.addEventListener('touchend', (e) => {
      const dx = e.changedTouches[0].clientX - startX;
      if (Math.abs(dx) > 50) this.go(this.current + (dx < 0 ? 1 : -1));
    }, { passive: true });
  }

  _bindWheel() {
    document.addEventListener('wheel', (e) => {
      clearTimeout(this._wheelTimer);
      this._wheelTimer = setTimeout(() => {
        if (!this.navigating) this.go(this.current + (e.deltaY > 0 ? 1 : -1));
      }, 150);
    }, { passive: true });
  }

  _bindIO() {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) entry.target.classList.add('visible');
      });
    }, { threshold: 0.5 });
    this.slides.forEach(s => observer.observe(s));
  }

  _updateIndicator() {
    const el = document.getElementById('slide-indicator');
    if (el) el.textContent = `${this.current + 1} / ${this.slides.length}`;
  }
}

document.addEventListener('DOMContentLoaded', () => new SlideController());
```

**Why**: The `navigating` flag blocks re-entry until the 600ms scroll animation completes. The 150ms wheel debounce collapses a single scroll gesture (which fires 10–40 wheel events) into one navigation call.

---

### Reveal animation CSS pairing

Slides must start hidden via CSS transforms, not `display: none`, so Intersection Observer fires.

```css
.slide {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 400ms ease, transform 400ms ease;
}

.slide.visible {
  opacity: 1;
  transform: translateY(0);
}

@media (prefers-reduced-motion: reduce) {
  .slide, .slide.visible {
    transition: none;
    opacity: 1;
    transform: none;
  }
}
```

**Why**: `display: none` removes elements from the layout tree entirely. IntersectionObserver never fires for hidden elements because they have no intersection with the viewport. `opacity: 0` keeps the element in the tree while hiding it visually.

---

### Slide indicator markup

```html
<div id="slide-indicator" aria-live="polite" style="
  position: fixed; bottom: 1.5rem; right: 2rem;
  font-size: clamp(0.75rem, 1.5vw, 0.9rem);
  color: var(--text-secondary);
  pointer-events: none;
  z-index: 100;
">1 / 1</div>
```

---

## Pattern Catalog

### ❌ Missing `navigating` guard

**Detection**:
```bash
grep -n 'go(' output.html | grep -v 'navigating'
rg 'scrollIntoView' output.html | grep -v 'navigating'
```

**What it looks like**:
```javascript
go(index) {
  this.current = Math.max(0, Math.min(index, this.slides.length - 1));
  this.slides[this.current].scrollIntoView({ behavior: 'smooth' });
  // No guard — holding ArrowRight fires 10+ go() calls per second
}
```

**Why wrong**: Each `go()` call triggers a smooth scroll. When the second call fires before the first completes, slides jump out of sync with `this.current`. On fast keyboards or trackpads, the deck can advance 3-5 slides per keypress.

**Do instead:** Set `this.navigating = true` at the start of `go()`, clear it with `setTimeout(() => this.navigating = false, 600)`, and guard entry with `if (this.navigating) return`.

---

### ❌ No wheel debounce

**Detection**:
```bash
grep -n 'wheel' output.html | grep -v 'clearTimeout\|debounce\|timer\|Timer'
```

**What it looks like**:
```javascript
document.addEventListener('wheel', (e) => {
  this.go(this.current + (e.deltaY > 0 ? 1 : -1));
});
```

**Why wrong**: A single trackpad scroll fires 20-80 `wheel` events. Without debounce, one swipe advances 20+ slides. The `navigating` guard alone is insufficient — it blocks concurrent calls, but debounce collapses burst events before they enter `go()`.

**Do instead:** `clearTimeout(this._wheelTimer); this._wheelTimer = setTimeout(() => { ... }, 150);`

---

### ❌ `display: none` on slides

**Detection**:
```bash
grep -n 'display.*none' output.html | grep -iv 'comment\|//'
rg '\.slide[^}]*display\s*:\s*none' output.html
```

**What it looks like**:
```css
.slide { display: none; }
.slide.active { display: flex; }
```

**Why wrong**: `display: none` removes the element from the accessibility tree and from the IntersectionObserver callback cycle. The `.visible` class never gets added. All reveal animations silently fail. Screen readers skip hidden slides.

**Do instead:** Use `opacity: 0; pointer-events: none; position: absolute` to hide, and `.visible { opacity: 1; pointer-events: auto; position: relative }` to show.

---

### ❌ Missing `{ passive: true }` on touch/wheel listeners

**Detection**:
```bash
grep -n 'touchstart\|touchend\|wheel' output.html | grep -v 'passive'
```

**What it looks like**:
```javascript
document.addEventListener('touchstart', handler);
document.addEventListener('wheel', handler);
```

**Why wrong**: Without `{ passive: true }`, the browser must wait for the handler to return before scrolling, causing 50–200ms jank on mobile. Chrome 73+ logs a console warning.

**Do instead:** Add `{ passive: true }` to all touch and wheel listeners. HTML slide decks should not call `preventDefault()` on these events.

---

### ❌ `Space` key not captured

**Detection**:
```bash
grep -n "case 'Space'" output.html
```

**What it looks like**:
```javascript
document.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowRight') this.go(this.current + 1);
  // Space not handled — browser default scrolls the page
});
```

**Why wrong**: Space is the standard "advance" key in every presentation app. Missing it breaks presenter muscle memory. The browser default scrolls the viewport, causing visible flicker before the controller corrects position.

**Do instead:** `case 'Space': e.preventDefault(); this.go(this.current + 1); break;`

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Deck jumps 3-5 slides on single keypress | Missing `navigating` guard | Add flag; clear with `setTimeout(, 600)` |
| One trackpad swipe advances entire deck | No wheel debounce | `clearTimeout` + 150ms `setTimeout` pattern |
| Reveal animations never fire | `display: none` on `.slide` | Use `opacity: 0` + `transform` instead |
| Touch swipe does nothing | Missing `touchstart`/`touchend` listeners | Add both with `{ passive: true }` |
| Slide indicator always shows "1 / 1" | `_updateIndicator()` not called in `go()`, or `#slide-indicator` element missing from HTML | Call in `go()` and `constructor`; add element to markup |
| Space bar scrolls page | `Space` key not captured; no `preventDefault()` | Handle in `keydown` switch with `e.preventDefault()` |
| Last slide unreachable | Off-by-one: clamping to `slides.length` | Use `Math.min(index, this.slides.length - 1)` |

---

## Detection Commands Reference

```bash
# Missing navigating guard
grep -n 'scrollIntoView' output.html | grep -v 'navigating'

# No wheel debounce
grep -n 'addEventListener.*wheel' output.html | grep -v 'clearTimeout\|debounce'

# display:none on slides
grep -n 'display.*none' output.html

# Missing passive listeners
grep -n "addEventListener('touchstart\|addEventListener('wheel" output.html | grep -v 'passive'

# Space key missing
grep -cn "case 'Space'" output.html   # should be >= 1

# Negated clamp (CSS bug from STYLE_PRESETS)
grep -n '\-clamp(' output.html
```

---

## See Also

- `STYLE_PRESETS.md` — CSS base block, theme presets, density limits, validation breakpoints
- `pptx-conversion.md` — python-pptx extraction patterns for PPTX-to-HTML path
