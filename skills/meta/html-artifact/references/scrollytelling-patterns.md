# Scrollytelling Patterns (Vanilla JS)

Scroll-triggered animation patterns for html-artifact. No frameworks, no build steps — pure IntersectionObserver + CSS transitions. Use when the artifact benefits from progressive reveal as the user scrolls.

**Load when:** Request mentions "scrollytelling", "scroll animation", "progressive reveal", "scroll-triggered", or when shape is report/diagram with long-form content that benefits from section-by-section reveal.

---

## Core Pattern: IntersectionObserver

One observer instance handles all scroll-revealed elements. Elements start hidden, get a `.visible` class when they enter the viewport.

```html
<script>
  document.addEventListener('DOMContentLoaded', () => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target); // fire once
          }
        }
      },
      { threshold: 0.15, rootMargin: '0px' }
    );

    document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
  });
</script>
```

### Threshold Guide

| Content Type | Threshold | Rationale |
|---|---|---|
| Prose blocks | `0.15` | Trigger early — text should be readable as it enters |
| Stat callouts | `0.3` | Trigger later — counter animation needs visible area |
| Timeline entries | `0.15` | Same as prose, but with stagger delay |
| Pullquotes | `0.2` | Slightly later — draws attention |
| Full sections | `0.1` | Very early — large sections shouldn't wait |

---

## Reveal Animations

### Fade Up (Default)

Standard reveal for all blocks. Element fades in while sliding up 30px.

```css
.reveal {
  opacity: 0;
  transform: translateY(30px);
  transition: opacity 600ms ease-out, transform 600ms ease-out;
}

.reveal.visible {
  opacity: 1;
  transform: translateY(0);
}
```

### Fade In (No Movement)

For elements that should appear without vertical shift (stats, callouts).

```css
.fade-in {
  opacity: 0;
  transition: opacity 800ms ease-out;
}

.fade-in.visible {
  opacity: 1;
}
```

### Slide From Left

For timeline entries or comparison cards entering from the side.

```css
.slide-left {
  opacity: 0;
  transform: translateX(-40px);
  transition: opacity 500ms ease-out, transform 500ms ease-out;
}

.slide-left.visible {
  opacity: 1;
  transform: translateX(0);
}
```

---

## Stagger Pattern

Multiple children animate sequentially with increasing delay via CSS custom properties.

```html
<div class="stagger-group reveal">
  <div class="stagger-child" style="--i: 0">First</div>
  <div class="stagger-child" style="--i: 1">Second</div>
  <div class="stagger-child" style="--i: 2">Third</div>
</div>
```

```css
.stagger-child {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 400ms ease-out, transform 400ms ease-out;
  transition-delay: calc(var(--i) * 100ms);
}

.stagger-group.visible .stagger-child {
  opacity: 1;
  transform: translateY(0);
}
```

---

## Animated Counter

Animate a number from 0 to target using requestAnimationFrame. Vanilla JS version.

```html
<span class="counter" data-target="42000" data-suffix="+">0</span>
```

```javascript
function animateCounters() {
  const counters = document.querySelectorAll('.counter');
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        const el = entry.target;
        const target = parseInt(el.dataset.target, 10);
        const suffix = el.dataset.suffix || '';
        const duration = 800;
        const start = performance.now();

        function tick(now) {
          const elapsed = now - start;
          const progress = Math.min(elapsed / duration, 1);
          const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
          el.textContent = Math.round(target * eased).toLocaleString() + suffix;
          if (progress < 1) requestAnimationFrame(tick);
        }

        requestAnimationFrame(tick);
        observer.unobserve(el);
      }
    }
  }, { threshold: 0.3 });

  counters.forEach(el => observer.observe(el));
}
```

---

## Reading Progress Bar

Fixed-top bar showing scroll progress. Pure vanilla JS.

```html
<div class="progress-bar" role="progressbar" aria-label="Reading progress">
  <div class="progress-fill" id="progress-fill"></div>
</div>
```

```css
.progress-bar {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
  background: transparent;
  z-index: 9999;
}

.progress-fill {
  height: 100%;
  background: var(--color-primary, #D97757);
  width: 0%;
  transition: width 100ms linear;
}
```

```javascript
window.addEventListener('scroll', () => {
  const scrollTop = window.scrollY;
  const docHeight = document.documentElement.scrollHeight - window.innerHeight;
  const progress = docHeight > 0 ? Math.min((scrollTop / docHeight) * 100, 100) : 0;
  document.getElementById('progress-fill').style.width = progress + '%';
}, { passive: true });
```

---

## Performance Rules

| Rule | Why |
|---|---|
| `{ passive: true }` on all scroll listeners | Prevents scroll jank (browser can optimize) |
| `observer.unobserve(el)` after first trigger | Reduces ongoing IntersectionObserver work |
| No `will-change` property | Modern browsers handle opacity/transform compositing automatically |
| `requestAnimationFrame` for counter animations | Smoother than setInterval, syncs with display refresh |
| Batch elements into one observer | One observer is cheaper than N observers |

---

## Reduced Motion

Always respect user preference. Include in every artifact that uses scroll animations:

```css
@media (prefers-reduced-motion: reduce) {
  .reveal,
  .fade-in,
  .slide-left,
  .stagger-child {
    transition: none !important;
    opacity: 1 !important;
    transform: none !important;
  }
  .progress-fill {
    transition: none !important;
  }
}
```

---

## Integration with html-artifact

Add `class="reveal"` to any section or element that should animate on scroll. Initialize the observer in the `<script>` block at the bottom of the artifact.

Scrollytelling works with ALL shapes but is most effective with:
- **report** — progressive section reveals as reader scrolls through long content
- **diagram** — staggered node reveals in figure sheets
- **deck** — alternative to arrow-key navigation (scroll-based slide advance)
