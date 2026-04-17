# JS Controller Patterns — Frontend Slides Reference

> **Load this file during Phase 4 (BUILD) when implementing SlideController.**

---

## Canonical SlideController Implementation

The full class below satisfies all requirements in Phase 4 rule 6. Use it verbatim and extend
with preset-specific animation logic — do not rewrite from scratch.

```javascript
class SlideController {
  constructor(deck) {
    this.deck = deck;
    this.slides = Array.from(deck.querySelectorAll('.slide'));
    this.current = 0;
    this.total = this.slides.length;
    this.navigating = false;       // blocks re-entry during transition
    this.wheelTimer = null;        // debounce handle
    this.touchStartX = 0;
    this.touchStartY = 0;

    this._initIndicator();
    this._initKeyboard();
    this._initTouch();
    this._initWheel();
    this._initIntersectionObserver();
    this._updateIndicator();
  }

  go(index) {
    if (this.navigating) return;
    if (index < 0 || index >= this.total) return;
    this.navigating = true;
    this.current = index;
    this.deck.scrollTo({ left: index * this.deck.offsetWidth, behavior: 'smooth' });
    this._updateIndicator();
    setTimeout(() => { this.navigating = false; }, 500);
  }

  next() { this.go(this.current + 1); }
  prev() { this.go(this.current - 1); }

  _initKeyboard() {
    document.addEventListener('keydown', e => {
      if (e.key === 'ArrowRight' || e.key === 'Space') { e.preventDefault(); this.next(); }
      if (e.key === 'ArrowLeft'  || e.key === 'Backspace') { e.preventDefault(); this.prev(); }
      if (e.key === 'Home') { e.preventDefault(); this.go(0); }
      if (e.key === 'End')  { e.preventDefault(); this.go(this.total - 1); }
    });
  }

  _initTouch() {
    this.deck.addEventListener('touchstart', e => {
      this.touchStartX = e.changedTouches[0].screenX;
      this.touchStartY = e.changedTouches[0].screenY;
    }, { passive: true });

    this.deck.addEventListener('touchend', e => {
      const dx = e.changedTouches[0].screenX - this.touchStartX;
      const dy = e.changedTouches[0].screenY - this.touchStartY;
      if (Math.abs(dx) < 50 || Math.abs(dy) > Math.abs(dx)) return;
      dx < 0 ? this.next() : this.prev();
    }, { passive: true });
  }

  _initWheel() {
    this.deck.addEventListener('wheel', e => {
      e.preventDefault();
      clearTimeout(this.wheelTimer);
      this.wheelTimer = setTimeout(() => {
        e.deltaY > 0 ? this.next() : this.prev();
      }, 150); // 150ms debounce prevents multi-slide jumps on trackpad
    }, { passive: false });
  }

  _initIntersectionObserver() {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) entry.target.classList.add('visible');
      });
    }, { threshold: 0.5 });
    this.slides.forEach(s => observer.observe(s));
  }

  _initIndicator() {
    this.indicator = document.createElement('div');
    this.indicator.className = 'slide-indicator';
    document.body.appendChild(this.indicator);
  }

  _updateIndicator() {
    this.indicator.textContent = `${this.current + 1} / ${this.total}`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  new SlideController(document.querySelector('.deck'));
});
```

---

<!-- no-pair-required: section heading — each Anti-Pattern block below has its own Do-instead -->
## Anti-Pattern Catalog

### Anti-Pattern 1: Missing `navigating` flag

Do instead: add `if (this.navigating) return;` as the first line of `go()` and reset it via `setTimeout`.

**Detection**:
```bash
grep -c 'navigating' output.html
# Count 0 means the guard is absent — deck will skip slides on rapid key presses
rg 'scrollTo' output.html
```

**Wrong**:
```javascript
go(index) {
  this.current = index;
  this.deck.scrollTo({ left: index * this.deck.offsetWidth, behavior: 'smooth' });
}
```

**Why wrong**: Rapid key presses or trackpad flicks queue multiple `go()` calls before the
first scroll animation completes, causing the deck to skip 2-3 slides.

**Fix**: `if (this.navigating) return;` as first line in `go()`. Set `navigating = false`
in a `setTimeout` matching the slide transition duration (typically 400-600ms).

**Do instead**

```javascript
go(index) {
  if (this.navigating) return;          // guard: reject re-entrant calls
  if (index < 0 || index >= this.total) return;
  this.navigating = true;
  this.current = index;
  this.deck.scrollTo({ left: index * this.deck.offsetWidth, behavior: 'smooth' });
  this._updateIndicator();
  setTimeout(() => { this.navigating = false; }, 500);
}
```

---

### Anti-Pattern 2: Wheel without debounce

Do instead: wrap the `wheel` handler body in `clearTimeout` + `setTimeout(() => { ... }, 150)` to collapse burst events.

**Detection**:
```bash
rg 'addEventListener.*wheel' output.html
rg 'clearTimeout|debounce' output.html
# If first matches but second does not, debounce is missing
```

**Wrong**:
```javascript
deck.addEventListener('wheel', e => {
  e.deltaY > 0 ? this.next() : this.prev();
});
```

**Why wrong**: A single trackpad gesture fires 30-80 `wheel` events. Without debounce, the
deck advances to the last slide in under a second.

**Fix**: Use `clearTimeout(this.wheelTimer)` + `setTimeout(() => { ... }, 150)` pattern from
the canonical implementation above. The 150ms window collapses burst events into one action.

**Do instead**

```javascript
_initWheel() {
  this.deck.addEventListener('wheel', e => {
    e.preventDefault();
    clearTimeout(this.wheelTimer);
    this.wheelTimer = setTimeout(() => {
      e.deltaY > 0 ? this.next() : this.prev();
    }, 150); // collapses burst events into a single slide advance
  }, { passive: false });
}
```

---

### Anti-Pattern 3: `display:none` on slides

**Detection**:
```bash
grep -n 'display.*none' output.html
rg 'display:\s*none' output.html
```

**Wrong**:
```css
.slide { display: none; }
.slide.active { display: flex; }
```

**Why wrong**: `display: none` removes the element from layout, so `IntersectionObserver`
callbacks never fire. Reveal animations (`opacity: 0 → 1`) silently break for all hidden slides.

**Fix**: The canonical `SlideController` uses `scrollTo` — all slides stay in DOM flow and are
always "display: flex". No manual show/hide is needed. If you must hide off-screen slides,
use `opacity: 0; pointer-events: none; position: absolute` instead.

**Do instead**

```css
/* All slides remain in DOM flow — no display toggling */
.slide {
  display: flex;
  flex: 0 0 100%;         /* each slide occupies exactly one viewport width */
  scroll-snap-align: start;
}
/* Use IntersectionObserver to trigger reveal animations, not display toggling */
.slide { opacity: 0; transition: opacity 0.4s ease; }
.slide.visible { opacity: 1; }
```

---

### Anti-Pattern 4: Touch swipe fires on vertical scroll

Do instead: record `screenY` on `touchstart` and reject gestures where `Math.abs(dy) > Math.abs(dx)`.

**Detection**:
```bash
grep -n 'touchend\|screenY' output.html
# If 'touchend' matches but 'screenY' does not, vertical axis is not checked
```

**Wrong**:
```javascript
deck.addEventListener('touchend', e => {
  const dx = e.changedTouches[0].screenX - this.touchStartX;
  if (Math.abs(dx) > 50) dx < 0 ? this.next() : this.prev();
});
```

**Why wrong**: A vertical scroll with slight horizontal drift triggers slide advance. Users
trying to scroll content on a mobile slide accidentally navigate.

**Fix**: Record `screenY` on `touchstart`. On `touchend`, reject if `Math.abs(dy) > Math.abs(dx)`
(gesture is more vertical than horizontal). See canonical implementation.

**Do instead**

```javascript
_initTouch() {
  this.deck.addEventListener('touchstart', e => {
    this.touchStartX = e.changedTouches[0].screenX;
    this.touchStartY = e.changedTouches[0].screenY;  // record Y to detect vertical gestures
  }, { passive: true });

  this.deck.addEventListener('touchend', e => {
    const dx = e.changedTouches[0].screenX - this.touchStartX;
    const dy = e.changedTouches[0].screenY - this.touchStartY;
    if (Math.abs(dx) < 50 || Math.abs(dy) > Math.abs(dx)) return; // reject vertical-dominant gestures
    dx < 0 ? this.next() : this.prev();
  }, { passive: true });
}
```

---

### Anti-Pattern 5: `Space` key not prevented from scrolling page

Do instead: call `e.preventDefault()` before `this.next()` on every navigation key including Space.

**Detection**:
```bash
grep -n 'Space' output.html
# If 'Space' matches but 'preventDefault' is not on the same or adjacent line, page scrolls
```

**Wrong**:
```javascript
if (e.key === 'Space') this.next();
```

**Why wrong**: `Space` is the browser's default page-down key. Without `e.preventDefault()`,
both slide advance and page scroll fire simultaneously, causing a jarring visible jump.

**Fix**: `if (e.key === 'Space') { e.preventDefault(); this.next(); }`

**Do instead**

```javascript
_initKeyboard() {
  document.addEventListener('keydown', e => {
    // e.preventDefault() called before this.next()/prev() on every navigation key
    if (e.key === 'ArrowRight' || e.key === 'Space') { e.preventDefault(); this.next(); }
    if (e.key === 'ArrowLeft'  || e.key === 'Backspace') { e.preventDefault(); this.prev(); }
    if (e.key === 'Home') { e.preventDefault(); this.go(0); }
    if (e.key === 'End')  { e.preventDefault(); this.go(this.total - 1); }
  });
}
```

---

## Indicator CSS

The slide counter must be visible over any preset background:

```css
.slide-indicator {
  position: fixed;
  bottom: clamp(0.75rem, 2vw, 1.5rem);
  right: clamp(0.75rem, 2vw, 1.5rem);
  background: rgba(0, 0, 0, 0.45);
  color: #ffffff;
  padding: 0.25em 0.6em;
  border-radius: 0.25em;
  font-size: clamp(0.7rem, 1.2vw, 0.9rem);
  font-family: var(--body-font, system-ui, sans-serif);
  z-index: 100;
  pointer-events: none;
  backdrop-filter: blur(4px);
}
```

The `rgba(0,0,0,0.45)` + `backdrop-filter` approach works on both light presets (arctic-minimal,
glacier-blue) and dark presets (void-neon, obsidian-gold) without needing per-preset overrides.

---

## Optional Feature Snippets

Add only when the user explicitly requests (see Phase 4 optional features list).

### Speaker notes panel (`n` key)

```javascript
// Inside _initKeyboard() event listener:
if (e.key === 'n') {
  const panel = document.getElementById('notes-panel');
  if (!panel) return;
  const hidden = panel.getAttribute('aria-hidden') === 'true';
  panel.setAttribute('aria-hidden', String(!hidden));
  panel.style.visibility = hidden ? 'visible' : 'hidden';
  panel.style.transform = hidden ? 'translateY(0)' : 'translateY(100%)';
}
```

```css
#notes-panel {
  position: fixed;
  bottom: 0; left: 0; right: 0;
  height: 25vh;
  background: rgba(0, 0, 0, 0.85);
  color: #e0e0e0;
  font-size: clamp(0.8rem, 1.5vw, 1rem);
  overflow-y: auto;
  padding: 1rem;
  z-index: 200;
  transition: transform 0.2s ease;
  visibility: hidden;
  transform: translateY(100%);
}
```

### Countdown timer

```javascript
class CountdownTimer {
  constructor(totalSeconds) {
    this.remaining = totalSeconds;
    this.el = document.createElement('div');
    this.el.className = 'countdown-timer';
    document.body.appendChild(this.el);
    this._render();
    this.interval = setInterval(() => {
      this.remaining = Math.max(0, this.remaining - 1);
      this._render();
      if (this.remaining === 0) clearInterval(this.interval);
    }, 1000);
  }
  _render() {
    const m = Math.floor(this.remaining / 60).toString().padStart(2, '0');
    const s = (this.remaining % 60).toString().padStart(2, '0');
    this.el.textContent = `${m}:${s}`;
    this.el.classList.toggle('urgent', this.remaining < 120);
  }
}
```

---

## Error-Fix Mapping

| Symptom | Root Cause | Detection Command | Fix |
|---------|-----------|-------------------|-----|
| Deck skips 2-3 slides on arrow key | Missing `navigating` guard | `grep -c 'navigating' output.html` → 0 | Add `navigating` flag to `go()` |
| Trackpad flick jumps to last slide | `wheel` not debounced | `rg 'clearTimeout' output.html` → no match | Add `clearTimeout` + 150ms debounce |
| Reveal animations never fire | Slides hidden with `display:none` | `grep 'display.*none' output.html` | Replace with `opacity:0; position:absolute` |
| Swipe fires on vertical scroll | No Y-axis rejection | `grep 'screenY' output.html` → no match | Add `Math.abs(dy) > Math.abs(dx)` guard |
| `Space` scrolls page AND advances slide | Missing `preventDefault` | `grep -A1 'Space' output.html` | Add `e.preventDefault()` before `this.next()` |
| Indicator invisible on white preset | Hard-coded color | Visual check | Use `rgba(0,0,0,0.45)` + `backdrop-filter` |
| `Home`/`End` scrolls page | No `preventDefault` | `grep -A1 'Home' output.html` | Add `e.preventDefault()` in keyboard handler |
