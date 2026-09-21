# Scrollytelling Patterns (Vanilla JS)

Scroll-triggered animation patterns for html-artifact. No frameworks, no build steps — pure IntersectionObserver + CSS transitions. CSS/JS implementations live in `templates/components/scrollytelling.css` and `scrollytelling.js`, injected by `assemble-template.py --components scrollytelling`.

**Load when:** Request mentions "scrollytelling", "scroll animation", "progressive reveal", "scroll-triggered", or when shape is report/diagram with long-form content that benefits from section-by-section reveal.

---

## When to Use

- **report** — progressive section reveals for long-form content
- **diagram** — staggered node reveals in figure sheets
- **deck** — scroll-based slide advance (alternative to arrow-key nav)
- Any shape with sequential content that benefits from progressive disclosure

---

## Available Animations

| Class | Effect | Best For |
|---|---|---|
| `.reveal` | Fade up 30px + opacity | Default for all blocks |
| `.fade-in` | Opacity only, no movement | Stats, callouts, badges |
| `.slide-left` | Slide from left 40px + opacity | Timeline entries, comparison cards |
| `.stagger-group` + `.stagger-child` | Sequential children with `--i` delay | Lists, grids, card groups |
| `.counter[data-target]` | Animated number 0 → target | Metric callouts |
| `.progress-bar` + `#progress-fill` | Fixed-top reading progress | Long-form reports |

### Stagger Usage

Set `style="--i: N"` on each `.stagger-child` (0-indexed). Delay = `N * 100ms`.

---

## Threshold Guide

| Content Type | Threshold | Rationale |
|---|---|---|
| Prose blocks | `0.15` | Trigger early — text should be readable as it enters |
| Stat callouts | `0.3` | Counter animation needs visible area |
| Timeline entries | `0.15` | Same as prose, with stagger delay |
| Pullquotes | `0.2` | Slightly later — draws attention |
| Full sections | `0.1` | Large sections shouldn't wait |

---

## Performance Rules

| Rule | Why |
|---|---|
| `{ passive: true }` on scroll listeners | Prevents scroll jank |
| `observer.unobserve(el)` after first trigger | Reduces ongoing observer work |
| No `will-change` property | Browsers handle opacity/transform compositing automatically |
| `requestAnimationFrame` for counters | Syncs with display refresh |
| Batch elements into one observer | One observer is cheaper than N |

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Forgetting `prefers-reduced-motion` | Already handled in scrollytelling.css |
| Multiple observer instances per element type | Use one observer, query all selectors |
| Missing `--i` on stagger children | Elements animate simultaneously without it |
| Using `setInterval` for counters | Use `requestAnimationFrame` instead |
| Scroll listener without `passive: true` | Always pass `{ passive: true }` |
