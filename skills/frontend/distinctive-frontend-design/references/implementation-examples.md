# Implementation Examples

Reference implementations for distinctive frontend design specifications.

---

## CSS Design Tokens

Complete CSS custom properties template derived from design specification output.

```css
/* design-tokens.css */

:root {
  /* Typography */
  --font-display: "Unbounded", sans-serif;
  --font-heading: "Crimson Pro", serif;
  --font-body: "Crimson Pro", serif;
  --font-mono: "JetBrains Mono", monospace;

  /* Font Sizes (fluid typography) */
  --text-xs: clamp(0.75rem, 0.7rem + 0.25vw, 0.875rem);
  --text-sm: clamp(0.875rem, 0.8rem + 0.375vw, 1rem);
  --text-base: clamp(1rem, 0.925rem + 0.375vw, 1.125rem);
  --text-lg: clamp(1.125rem, 1rem + 0.625vw, 1.5rem);
  --text-xl: clamp(1.5rem, 1.25rem + 1.25vw, 2.25rem);
  --text-2xl: clamp(2rem, 1.5rem + 2.5vw, 3.5rem);
  --text-3xl: clamp(2.5rem, 1.75rem + 3.75vw, 5rem);

  /* Font Weights */
  --weight-normal: 400;
  --weight-medium: 500;
  --weight-semibold: 600;
  --weight-bold: 700;
  --weight-extrabold: 800;

  /* Colors - Dominant */
  --surface: #E8E6E3;
  --surface-dark: #D1CFC8;
  --surface-darker: #B8B6B0;

  /* Colors - Secondary */
  --container: #3A3A3A;
  --container-light: #5C5C5C;
  --container-lighter: #7A7A7A;

  /* Colors - Accent */
  --accent: #FFDE00;
  --accent-hover: #FFE94D;
  --accent-dark: #CDB100;

  /* Colors - Functional */
  --success: #00C853;
  --warning: #FF6D00;
  --error: #D32F2F;
  --info: #0091EA;

  /* Spacing (geometric scale) */
  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 1.5rem;
  --space-xl: 2rem;
  --space-2xl: 3rem;
  --space-3xl: 4.5rem;

  /* Border Radius */
  --radius-sm: 0.25rem;
  --radius-md: 0.5rem;
  --radius-lg: 1rem;

  /* Shadows */
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.1);
  --shadow-md: 0 4px 8px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 12px 24px rgba(0, 0, 0, 0.15);

  /* Animation */
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
  --ease-in: cubic-bezier(0.4, 0, 1, 1);
  --ease-elastic: cubic-bezier(0.68, -0.55, 0.265, 1.55);

  --duration-fast: 150ms;
  --duration-normal: 300ms;
  --duration-slow: 500ms;
  --duration-stagger: 150ms;
}
```

---

## Base Styles

```css
/* base.css */

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: var(--font-body);
  font-size: var(--text-base);
  font-weight: var(--weight-normal);
  line-height: 1.6;
  color: var(--container);

  /* Atmospheric background */
  background:
    radial-gradient(
      ellipse 80% 50% at 50% 0%,
      rgba(255, 222, 0, 0.08),
      transparent
    ),
    repeating-linear-gradient(
      90deg,
      transparent,
      transparent 99px,
      rgba(58, 58, 58, 0.02) 99px,
      rgba(58, 58, 58, 0.02) 100px
    ),
    var(--surface);
  min-height: 100vh;
}

h1, h2, h3, h4, h5, h6 {
  font-family: var(--font-heading);
  font-weight: var(--weight-bold);
  line-height: 1.2;
  margin-bottom: var(--space-md);
}

h1 {
  font-family: var(--font-display);
  font-size: var(--text-3xl);
  font-weight: var(--weight-extrabold);
}

h2 { font-size: var(--text-2xl); }
h3 { font-size: var(--text-xl); }

code, pre {
  font-family: var(--font-mono);
  font-size: 0.9em;
}
```

---

## React + Tailwind CSS

```javascript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      fontFamily: {
        display: ['Unbounded', 'sans-serif'],
        heading: ['Crimson Pro', 'serif'],
        body: ['Crimson Pro', 'serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        surface: {
          DEFAULT: '#E8E6E3',
          dark: '#D1CFC8',
          darker: '#B8B6B0',
        },
        container: {
          DEFAULT: '#3A3A3A',
          light: '#5C5C5C',
          lighter: '#7A7A7A',
        },
        accent: {
          DEFAULT: '#FFDE00',
          hover: '#FFE94D',
          dark: '#CDB100',
        },
      },
      animation: {
        'slide-up': 'slide-up 0.8s cubic-bezier(0.22, 1, 0.36, 1) both',
      },
      keyframes: {
        'slide-up': {
          'from': { opacity: '0', transform: 'translateY(30px)' },
          'to': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
};
```

---

## HTML Starter Template

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Project Name</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Unbounded:wght@600;800&family=Crimson+Pro:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="design-tokens.css">
  <link rel="stylesheet" href="base.css">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <section class="hero">
    <h1 class="hero-title">Your Distinctive Title</h1>
    <p class="hero-subtitle">A compelling subtitle that sets the tone</p>
    <button class="hero-cta">Get Started</button>
  </section>
</body>
</html>
```

---

## Typography Specification Template

```json
{
  "display_font": {
    "family": "Unbounded",
    "weights": [600, 800],
    "usage": "Hero headings, page titles, brand moments",
    "rationale": "Geometric but distinctive, technical feel without being corporate"
  },
  "heading_font": {
    "family": "Crimson Pro",
    "weights": [500, 700],
    "usage": "Section headers, card titles",
    "rationale": "Serif contrast creates sophistication, prevents monotony"
  },
  "body_font": {
    "family": "Crimson Pro",
    "weights": [400, 600],
    "usage": "Body text, UI labels",
    "rationale": "Readable serif that feels crafted, not default"
  },
  "mono_font": {
    "family": "JetBrains Mono",
    "weights": [400, 500],
    "usage": "Code snippets, technical data",
    "rationale": "Purpose-built for code, distinctive ligatures"
  }
}
```

---

## Color Palette Template

```json
{
  "palette_name": "Concrete & Voltage",
  "inspiration": "Brutalist architecture + high-voltage warning signs",
  "dominant": {
    "surface": "#E8E6E3",
    "surface_dark": "#D1CFC8",
    "rationale": "Warm concrete gray, not sterile white"
  },
  "secondary": {
    "container": "#3A3A3A",
    "container_light": "#5C5C5C",
    "rationale": "Charcoal for depth, avoids pure black"
  },
  "accent": {
    "primary": "#FFDE00",
    "primary_hover": "#FFE94D",
    "rationale": "Industrial yellow, high-voltage energy"
  },
  "functional": {
    "success": "#00C853",
    "warning": "#FF6D00",
    "error": "#D32F2F",
    "info": "#0091EA"
  }
}
```

---

## Aesthetic Direction Template

```json
{
  "project_name": "example-app",
  "primary_direction": "Neo-Brutalist Technical",
  "secondary_direction": "Warm Artisan",
  "context_summary": "Developer tool targeting technical audience, needs to feel powerful yet approachable",
  "emotional_goals": ["confidence", "clarity", "craftsmanship"],
  "cultural_context": "Modern software development culture"
}
```

---

## Design Specification Document Template

```markdown
# Design Specification: [Project Name]

## Aesthetic Direction
**Primary**: [Direction Name]
**Inspiration**: [Source]
**Emotional Goals**: [List]

## Typography
- **Display**: [Font] (weights) - [usage]
- **Headings**: [Font] (weights) - [usage]
- **Body**: [Font] (weights) - [usage]
- **Monospace**: [Font] (weights) - [usage]

## Color Palette
**Name**: [Palette Name]
- Dominant (60-70%): [colors + rationale]
- Secondary (20-30%): [colors + rationale]
- Accent (5-10%): [colors + rationale]
- Functional: success, warning, error, info

## Animation Strategy
[High-impact moments + timing]

## Backgrounds
[Technique + layers]

## Validation Score: [X]/100 (Grade [X])
```
