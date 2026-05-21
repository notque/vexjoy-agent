# Shape: Slide Deck

> **Shape**: deck | **Signal words**: slides, presentation, deck, talk, pitch
> CSS layout classes: `templates/shapes/deck.css` (injected by assemble-template.py)

---

## Layout Description

Full-viewport slide container with 16:9 aspect ratio. Slides are stacked absolutely; only `.active` slide is visible. Arrow-key navigation with progress bar and slide counter.

---

## Key CSS Classes (from templates/shapes/deck.css)

| Class | Purpose |
|---|---|
| `.slide-deck` | Container with 16:9 aspect ratio, centered, max-width 960px |
| `.slide` | Absolutely positioned; `display: none` by default, `.active` shows |
| `.slide-nav` | Navigation bar with prev/next buttons + counter |
| `.slide-counter` | "3/12" format monospace counter |
| `.progress-bar` + `.progress-fill` | Thin accent bar tracking position |

---

## Slide Types

| Type | Structure | Use For |
|---|---|---|
| Title slide | Large heading + subtitle, centered | Opening and section dividers |
| Content slide | Heading + bullet list or paragraphs | Core content |
| Split slide | 2-column layout (text + visual) | Text alongside diagram/image |
| Quote slide | Large blockquote + attribution | Key quotes or principles |
| Code slide | Heading + `<pre>` code block | Technical content |

---

## Navigation

- **Arrow keys:** Left/Right navigate slides (request `keyboard-nav` component)
- **Touch:** Swipe left/right via touch event listeners
- **Counter:** Update on every navigation, format "N/Total"
- **Progress bar:** Width percentage = `(current / total) * 100%`
- **Slide transitions:** CSS transitions on opacity; respect `prefers-reduced-motion`

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Slides not 16:9 | Use `aspect-ratio: 16/9` on container |
| No keyboard navigation | Add arrow-key listeners; request `keyboard-nav` component |
| Missing print styles | Print all slides visible with `page-break-after: always` |
| No touch support | Add `touchstart`/`touchend` listeners with swipe threshold |
| Slide counter not updating | Update counter text on every navigation event |
| Content overflows slide | Constrain content with padding; use `overflow: hidden` |

---

## Accessibility

- Arrow keys don't fire when focused on form inputs
- Slide counter provides position context
- Each slide is a semantic `<section>` with heading
- Focus management: set focus to new slide on navigation
- Print renders all slides sequentially
