# JS Controller Reference

> **Scope**: SlideController implementation patterns — navigation, events, Intersection Observer, animation gating.
> **Version range**: All modern browsers (Chrome 80+, Firefox 75+, Safari 14+)
> **Generated**: 2026-04-17

---

## Overview

Every HTML slide deck requires a `SlideController` class wiring up keyboard, touch, wheel, and IO events.
The most common failure modes are wheel events that skip multiple slides, Intersection Observer callbacks
that never fire, and broken reduced-motion compliance. All three stem from specific implementation
choices that are detectable with grep.

---

## Pattern Table

| Pattern | Correct Approach | Failure if Missing |
|---------|------------------|--------------------|
| Wheel debounce | 150ms `setTimeout` + `navigating` flag | Multi-slide jumps on trackpad scroll |
| Touch threshold | `Math.abs(delta) >= 50` | Accidental swipes trigger navigation |
| Slide visibility | `opacity: 0; pointer-events: none` | Intersection Observer callbacks never fire |
| IO threshold | `threshold: 0.5` in observer options | Reveals trigger too early on partial overlap |
| Keyboard Home/End | `'Home'` → index 0; `'End'` → last index | No way to jump to first/last slide |

---

## Correct Patterns

### SlideController Skeleton

All six event types must be present. Omitting any one causes user-facing navigation failures.

```javascript
class SlideController {
  constructor(deck) {
    this.deck = deck;
    this.slides = Array.from(deck.querySelectorAll('.slide'));
    this.current = 0;
    this.navigating = false;       // blocks re-entry during transition
    this._wheelTimer = null;

    document.addEventListener('keydown', this._onKey.bind(this));
    deck.addEventListener('touchstart', this._onTouchStart.bind(this), { passive: true });
    deck.addEventListener('touchend', this._onTouchEnd.bind(this));
    deck.addEventListener('wheel', this._onWheel.bind(this), { passive: true });

    this._initIO();
    this._updateIndicator();
  }
}
```

**Why**: Missing `navigating` flag causes `wheel` events to queue multiple slide advances.
The `{ passive: true }` option on `touchstart` prevents scroll-blocking warnings in Chrome.

---

### Debounced Wheel Navigation

```javascript
_onWheel(e) {
  if (this.navigating) return;              // re-entry guard
  clearTimeout(this._wheelTimer);
  this._wheelTimer = setTimeout(() => {
    if (e.deltaY > 0) this.next();
    else if (e.deltaY < 0) this.prev();
  }, 150);
}
```

**Why**: Without the 150ms debounce, a single two-finger scroll fires 20-30 `wheel` events.
Each one advances a slide, jumping the user 20+ slides forward.

---

### Intersection Observer Reveal

```javascript
_initIO() {
  const io = new IntersectionObserver(
    entries => entries.forEach(e => e.target.classList.toggle('visible', e.isIntersecting)),
    { threshold: 0.5 }
  );
  this.slides.forEach(s => io.observe(s));
}
```

Required CSS for initial hidden state:

```css
.slide { opacity: 0; transform: translateY(20px); transition: opacity 0.4s, transform 0.4s; }
.slide.visible { opacity: 1; transform: none; }
```

**Why**: `display: none` removes the element from layout — the observer callback never fires,
so `.visible` is never added and reveal animations never trigger.

---

### Touch Swipe

```javascript
_onTouchStart(e) { this._touchX = e.touches[0].clientX; }

_onTouchEnd(e) {
  const delta = this._touchX - e.changedTouches[0].clientX;
  if (Math.abs(delta) >= 50) {             // 50px threshold
    delta > 0 ? this.next() : this.prev();
  }
}
```

**Why**: Threshold below 50px fires on incidental touch movement. Above 80px misses
intentional short swipes on 375px-wide phones.

---

### Keyboard Handler

```javascript
_onKey(e) {
  const map = {
    ArrowRight: () => this.next(),
    Space:      () => this.next(),
    ArrowLeft:  () => this.prev(),
    Backspace:  () => this.prev(),
    Home:       () => this.goTo(0),
    End:        () => this.goTo(this.slides.length - 1),
  };
  const handler = map[e.key];
  if (handler) { e.preventDefault(); handler(); }
}
```

**Why**: `e.preventDefault()` on Space prevents page scrolling. Without `Home`/`End`,
presenters have no way to jump to the first or last slide quickly.

---

## Anti-Pattern Catalog

### ❌ No `navigating` Flag (Multi-Slide Jumps)

**Detection**:
```bash
grep -c 'navigating' output.html
# Expected: >= 2 (set true + set false). If 0 or 1: missing guard.
grep -n 'addEventListener.*wheel' output.html
```

**What it looks like**:
```javascript
deck.addEventListener('wheel', (e) => {
  if (e.deltaY > 0) this.next();   // fires on every single wheel event
});
```

**Why wrong**: Each `wheel` event triggers `next()`. A single scroll fires 20-30 events,
advancing the deck by 20+ slides before the user notices.

**Fix**: Add `navigating` flag set to `true` at transition start, `false` after 300-400ms.
Add 150ms debounce on the wheel handler itself.

---

### ❌ `display: none` on Slides (IO Never Fires)

**Detection**:
```bash
grep -n 'display.*none' output.html | grep -v '@media'
rg 'display:\s*none' output.html
```

**What it looks like**:
```css
.slide { display: none; }
.slide.active { display: flex; }
```

**Why wrong**: `display: none` takes elements out of layout entirely. `IntersectionObserver`
only reports entries for elements that are in layout — so the observer callback never fires,
the `.visible` class never gets added, and reveal animations never trigger.

**Fix**:
```css
.slide { opacity: 0; pointer-events: none; position: absolute; }
.slide.active { opacity: 1; pointer-events: auto; position: relative; }
```

---

### ❌ Missing Reduced-Motion on JS-Applied Transitions

**Detection**:
```bash
grep -c 'prefers-reduced-motion' output.html
# Expected: >= 1. If 0: reduced-motion not handled anywhere.
```

**What it looks like**:
```javascript
// JS directly sets transition, bypassing CSS media query
slide.style.transition = 'opacity 0.6s, transform 0.6s';
```

**Why wrong**: JS-applied inline styles override the CSS `prefers-reduced-motion` block.
Users with vestibular disorders or motion sensitivity still get full animations.

**Fix**:
```javascript
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
slide.style.transition = reducedMotion ? 'none' : 'opacity 0.6s, transform 0.6s';
```

---

### ❌ Missing Slide Index Indicator

**Detection**:
```bash
grep -n 'currentSlide\|totalSlides\|slide-indicator\|slideCount\|/ ${' output.html
# Expected: at least one hit showing N/M display.
```

**What it looks like**: No visible `N / M` counter anywhere in the HTML output.

**Why wrong**: Without a position indicator, the audience has no sense of progress.
Presenters lose track of timing during live delivery.

**Fix**:
```javascript
_updateIndicator() {
  if (this.indicator) {
    this.indicator.textContent = `${this.current + 1} / ${this.slides.length}`;
  }
}
// Call this.updateIndicator() inside goTo(), next(), prev()
```

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Deck jumps 10+ slides on scroll | `wheel` event not debounced | Add 150ms `setTimeout` debounce + `navigating` flag |
| Reveal animations never fire | Slides hidden with `display: none` | Switch to `opacity: 0; pointer-events: none` |
| Touch swipes randomly navigate | Touch threshold too low (< 50px) | Set `Math.abs(delta) >= 50` check in `_onTouchEnd` |
| Space key scrolls the page | No `e.preventDefault()` in keydown | Add `e.preventDefault()` before calling `this.next()` |
| Animations play with reduced-motion on | JS sets `transition` inline | Check `matchMedia('(prefers-reduced-motion)')` before setting |
| IO callback fires on partial overlap | `threshold` missing (defaults to 0) | Set `threshold: 0.5` in `IntersectionObserver` options |
| First/last slide unreachable by keyboard | `Home`/`End` not in keydown map | Add `Home` → `goTo(0)` and `End` → `goTo(last)` |

---

## Detection Commands Reference

```bash
# Wheel debounce: check timer and navigating flag exist
grep -n 'setTimeout.*wheel\|_wheelTimer\|wheelTimer' output.html
grep -c 'navigating' output.html

# display:none on slides (bad)
grep -n 'display.*none' output.html | grep -v '@media'

# Reduced-motion handling
grep -c 'prefers-reduced-motion' output.html

# Slide indicator
grep -n 'currentSlide\|totalSlides\|slideCount' output.html

# IntersectionObserver present
grep -n 'IntersectionObserver' output.html

# Touch handling present
grep -n 'touchstart\|touchend' output.html

# Home/End keys handled
grep -n "'Home'\|\"Home\"" output.html
```

---

## See Also

- `skills/frontend-slides/references/STYLE_PRESETS.md` — CSS base block, preset variables, animation feel per preset
- `skills/frontend-slides/references/CSS_ANTIPATTERNS.md` — CSS-side anti-patterns with detection commands
