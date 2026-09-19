# Background & Atmosphere Techniques

## Philosophy

Backgrounds create mood and depth. Avoid flat solid colors.

Every background should contribute to the overall aesthetic story:
- **Layered gradients** create atmospheric depth
- **Geometric patterns** add technical precision
- **Textures** provide organic warmth
- **Contextual effects** immerse in theme

---

## Technique 1: Layered Radial Gradients

### Atmospheric Glow

**Use case**: Landing pages, hero sections, feature showcases

**Effect**: Soft colored glows that create depth and focus attention

```css
/* Example: Warm glow from top-right */
.section {
  background:
    radial-gradient(
      ellipse 80% 50% at 80% 20%,
      rgba(255, 222, 0, 0.12),
      transparent 60%
    ),
    radial-gradient(
      ellipse 60% 40% at 20% 80%,
      rgba(58, 58, 58, 0.08),
      transparent 60%
    ),
    #E8E6E3;
  min-height: 100vh;
}
```

**Variations**:

```css
/* Dual spotlights (opposite corners) */
background:
  radial-gradient(circle at top left, rgba(255, 100, 100, 0.15), transparent 40%),
  radial-gradient(circle at bottom right, rgba(100, 100, 255, 0.15), transparent 40%),
  var(--surface);

/* Central vignette effect */
background:
  radial-gradient(ellipse at center, var(--surface), rgba(0, 0, 0, 0.3) 120%);

/* Aurora effect (multiple overlapping glows) */
background:
  radial-gradient(ellipse at 20% 30%, rgba(255, 100, 200, 0.1), transparent 50%),
  radial-gradient(ellipse at 80% 50%, rgba(100, 200, 255, 0.1), transparent 50%),
  radial-gradient(ellipse at 50% 80%, rgba(200, 255, 100, 0.1), transparent 50%),
  var(--surface);
```

---

## Technique 2: Geometric Patterns

### Grid Lines (Technical Precision)

**Use case**: Developer tools, technical documentation, SaaS products

**Effect**: Subtle grid that suggests precision and structure

```css
/* Vertical line grid */
.background-grid {
  background-image:
    repeating-linear-gradient(
      90deg,
      transparent,
      transparent 99px,
      rgba(58, 58, 58, 0.03) 99px,
      rgba(58, 58, 58, 0.03) 100px
    );
  background-color: var(--surface);
}

/* Graph paper grid */
.background-graph {
  background-image:
    repeating-linear-gradient(
      0deg,
      transparent,
      transparent 49px,
      rgba(58, 58, 58, 0.02) 49px,
      rgba(58, 58, 58, 0.02) 50px
    ),
    repeating-linear-gradient(
      90deg,
      transparent,
      transparent 49px,
      rgba(58, 58, 58, 0.02) 49px,
      rgba(58, 58, 58, 0.02) 50px
    );
  background-color: var(--surface);
}

/* Diagonal stripes */
.background-stripes {
  background-image:
    repeating-linear-gradient(
      45deg,
      transparent,
      transparent 35px,
      rgba(58, 58, 58, 0.03) 35px,
      rgba(58, 58, 58, 0.03) 70px
    );
  background-color: var(--surface);
}
```

### Dots Pattern

```css
.background-dots {
  background-image:
    radial-gradient(circle, rgba(58, 58, 58, 0.05) 1px, transparent 1px);
  background-size: 20px 20px;
  background-color: var(--surface);
}

/* Larger dots with spacing */
.background-dots-large {
  background-image:
    radial-gradient(circle, rgba(58, 58, 58, 0.08) 2px, transparent 2px);
  background-size: 40px 40px;
  background-color: var(--surface);
}
```

---

## Technique 3: Noise Textures

### Subtle Grain (Organic Feel)

**Use case**: Portfolios, creative showcases, artisan brands

**Effect**: Adds tactile quality, prevents sterile digital feel

```css
/* Using pseudo-element for noise overlay */
.section-with-noise {
  position: relative;
  background: var(--surface);
}

.section-with-noise::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image: url('data:image/svg+xml,<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg"><filter id="noiseFilter"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" stitchTiles="stitch"/></filter><rect width="100%" height="100%" filter="url(%23noiseFilter)"/></svg>');
  opacity: 0.4;
  mix-blend-mode: multiply;
  pointer-events: none;
}
```

**Alternative: CSS-only noise effect**:

```css
.noise-background {
  background-image:
    repeating-linear-gradient(90deg, transparent 0, rgba(0,0,0,.03) 1px, transparent 2px),
    repeating-linear-gradient(180deg, transparent 0, rgba(0,0,0,.03) 1px, transparent 2px);
  background-size: 1px 1px;
  background-color: var(--surface);
}
```

---

## Technique 4: Contextual Effects

### Code Editor Theme (Dark Background)

```css
.code-theme-background {
  background:
    /* Subtle scanline effect */
    repeating-linear-gradient(
      0deg,
      transparent,
      transparent 2px,
      rgba(255, 255, 255, 0.02) 2px,
      rgba(255, 255, 255, 0.02) 4px
    ),
    /* IDE-style grid */
    repeating-linear-gradient(
      90deg,
      transparent,
      transparent 79px,
      rgba(255, 255, 255, 0.01) 79px,
      rgba(255, 255, 255, 0.01) 80px
    ),
    /* Base color */
    #1E1E2E;
}
```

### Portfolio Spotlight Effect

```css
/* Spotlight follows cursor (requires JavaScript) */
.portfolio-background {
  background: radial-gradient(
    circle at var(--mouse-x, 50%) var(--mouse-y, 50%),
    rgba(255, 255, 255, 0.1) 0%,
    transparent 20%
  ),
  #1A1A1A;
}
```

```javascript
// JavaScript to track mouse position
document.addEventListener('mousemove', (e) => {
  const x = (e.clientX / window.innerWidth) * 100;
  const y = (e.clientY / window.innerHeight) * 100;
  document.documentElement.style.setProperty('--mouse-x', `${x}%`);
  document.documentElement.style.setProperty('--mouse-y', `${y}%`);
});
```

### Documentation Texture

```css
/* Subtle paper texture for docs */
.docs-background {
  background:
    /* Paper texture via noise */
    url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAIklEQVQIW2NkQAKrVq36zwjjgzhhYWGMYAEYB8RmROaABADeOQ8CXl/xfgAAAABJRU5ErkJggg==')
    repeat,
    /* Slight gradient for depth */
    linear-gradient(180deg, #FAFAF8 0%, #F5F5F2 100%);
}
```

---

## Technique 5: Multi-Layer Composition

### Complex Atmospheric Depth

Combine multiple techniques for rich backgrounds:

```css
.rich-background {
  position: relative;
  background-color: var(--surface);
}

.rich-background::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    /* Radial glow accent */
    radial-gradient(
      ellipse 60% 40% at 70% 30%,
      rgba(255, 222, 0, 0.08),
      transparent 60%
    ),
    /* Geometric pattern */
    repeating-linear-gradient(
      90deg,
      transparent,
      transparent 99px,
      rgba(58, 58, 58, 0.02) 99px,
      rgba(58, 58, 58, 0.02) 100px
    );
  pointer-events: none;
}

.rich-background::after {
  content: '';
  position: absolute;
  inset: 0;
  /* Noise texture overlay */
  background-image: url('data:image/svg+xml,...');
  opacity: 0.3;
  mix-blend-mode: multiply;
  pointer-events: none;
}
```

---

## Technique 6: Animated Backgrounds

### Subtle Movement (Use Sparingly!)

```css
/* Slowly shifting gradient */
@keyframes gradient-shift {
  0%, 100% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
}

.animated-gradient {
  background:
    linear-gradient(
      270deg,
      rgba(255, 100, 100, 0.1),
      rgba(100, 100, 255, 0.1),
      rgba(100, 255, 100, 0.1)
    );
  background-size: 200% 200%;
  animation: gradient-shift 15s ease infinite;
}
```

**Warning**: Animated backgrounds can be distracting. Use only when:
- Animation is very subtle (slow, low opacity)
- It enhances the theme (e.g., flowing data for analytics app)
- User can disable it via `prefers-reduced-motion`

```css
@media (prefers-reduced-motion: reduce) {
  .animated-gradient {
    animation: none;
  }
}
```

---

## Dark Mode Considerations

When implementing dark backgrounds:

```css
/* Light mode */
:root {
  --bg-surface: #E8E6E3;
  --bg-glow: rgba(255, 222, 0, 0.08);
  --bg-pattern: rgba(58, 58, 58, 0.03);
}

/* Dark mode */
@media (prefers-color-scheme: dark) {
  :root {
    --bg-surface: #1E1E2E;
    --bg-glow: rgba(255, 222, 0, 0.05);
    --bg-pattern: rgba(255, 255, 255, 0.02);
  }
}

body {
  background:
    radial-gradient(
      ellipse at top,
      var(--bg-glow),
      transparent 50%
    ),
    repeating-linear-gradient(
      90deg,
      transparent,
      transparent 99px,
      var(--bg-pattern) 99px,
      var(--bg-pattern) 100px
    ),
    var(--bg-surface);
}
```

---

## Performance Tips

**Optimize background rendering**:

1. **Use CSS gradients over images** when possible (smaller file size, scalable)
2. **Limit layer count** (3-4 layers max for good performance)
3. **Avoid animating backgrounds** on scroll (causes jank)
4. **Use `will-change` sparingly**:
   ```css
   .animated-bg {
     will-change: background-position;
   }
   ```
5. **Compress SVG noise patterns** for smaller data URLs
6. **Consider `background-attachment: fixed`** carefully (can cause scrolling performance issues)

---

## Aesthetic-Specific Recommendations

### Neo-Brutalist
```css
background:
  repeating-linear-gradient(90deg, transparent, transparent 99px, rgba(58, 58, 58, 0.04) 99px, rgba(58, 58, 58, 0.04) 100px),
  #E8E6E3;
```

### Sophisticated Editorial
```css
background:
  url('subtle-paper-texture.png'),
  linear-gradient(180deg, #FAFAF8 0%, #F5F5F2 100%);
```

### Technical/Developer
```css
background:
  repeating-linear-gradient(0deg, transparent, transparent 19px, rgba(255, 255, 255, 0.02) 19px, rgba(255, 255, 255, 0.02) 20px),
  repeating-linear-gradient(90deg, transparent, transparent 19px, rgba(255, 255, 255, 0.02) 19px, rgba(255, 255, 255, 0.02) 20px),
  #1E1E2E;
```

### Warm Artisan
```css
background:
  radial-gradient(ellipse at 30% 40%, rgba(212, 165, 116, 0.1), transparent 50%),
  url('organic-texture.svg'),
  #F5EFE7;
```

### Retro Synthwave
```css
background:
  radial-gradient(ellipse at top, rgba(189, 147, 249, 0.2), transparent 50%),
  radial-gradient(ellipse at bottom, rgba(255, 121, 198, 0.2), transparent 50%),
  #1A1B26;
```

---

## Testing Backgrounds

**Checklist**:
- [ ] Readable text contrast (WCAG AA minimum)
- [ ] Not distracting from main content
- [ ] Performs smoothly on low-end devices
- [ ] Looks good at different viewport sizes
- [ ] Respects `prefers-reduced-motion` if animated
- [ ] Works in both light and dark modes (if applicable)
- [ ] Enhances aesthetic without overwhelming

**Tools**:
- Chrome DevTools > Rendering > Paint flashing
- WebPageTest for performance
- Contrast checker for text readability
