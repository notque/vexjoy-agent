# Design Tokens Reference
<!-- Loaded by ui-design-engineer when task involves design systems, Tailwind theme config, color scales, typography scales, or dark mode -->

Design tokens are the single source of truth for a design system. Centralizing colors, spacing, and typography in one place means a brand change touches one file, not hundreds.

## CSS Custom Properties (Design Token Foundation)
**When to use:** When you want tokens accessible in both CSS and JavaScript, or when Tailwind alone is insufficient.

```css
/* styles/tokens.css */
:root {
  /* Color primitives — raw values, not semantic */
  --color-blue-50:  #eff6ff;
  --color-blue-100: #dbeafe;
  --color-blue-500: #3b82f6;
  --color-blue-600: #2563eb;
  --color-blue-700: #1d4ed8;
  --color-blue-900: #1e3a8a;

  --color-gray-50:  #f9fafb;
  --color-gray-100: #f3f4f6;
  --color-gray-500: #6b7280;
  --color-gray-600: #4b5563;
  --color-gray-700: #374151;
  --color-gray-900: #111827;

  /* Semantic tokens — reference primitives, describe intent */
  --color-bg-primary:    var(--color-gray-50);
  --color-bg-surface:    #ffffff;
  --color-text-primary:  var(--color-gray-900);
  --color-text-muted:    var(--color-gray-600);
  --color-border:        var(--color-gray-100);
  --color-accent:        var(--color-blue-600);
  --color-accent-hover:  var(--color-blue-700);

  /* Spacing scale — 4px base unit */
  --space-1:  0.25rem;   /*  4px */
  --space-2:  0.5rem;    /*  8px */
  --space-3:  0.75rem;   /* 12px */
  --space-4:  1rem;      /* 16px */
  --space-6:  1.5rem;    /* 24px */
  --space-8:  2rem;      /* 32px */
  --space-12: 3rem;      /* 48px */
  --space-16: 4rem;      /* 64px */

  /* Typography */
  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;

  --text-xs:   0.75rem;
  --text-sm:   0.875rem;
  --text-base: 1rem;
  --text-lg:   1.125rem;
  --text-xl:   1.25rem;
  --text-2xl:  1.5rem;
  --text-3xl:  1.875rem;
  --text-4xl:  2.25rem;

  /* Border radius */
  --radius-sm: 0.25rem;
  --radius:    0.5rem;
  --radius-lg: 0.75rem;
  --radius-xl: 1rem;
  --radius-full: 9999px;

  /* Shadows */
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow:    0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
}
```

---

## Tailwind Theme Configuration
**When to use:** Projects using Tailwind CSS. Extends the default theme with custom tokens, making them available as Tailwind utility classes.

```javascript
// tailwind.config.js
const defaultTheme = require('tailwindcss/defaultTheme')

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Semantic color tokens
        brand: {
          50:  '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',   // primary action — 4.54:1 on white (AA)
          700: '#1d4ed8',   // hover state
          900: '#1e3a8a',
        },
        // Surface and content tokens
        surface: {
          DEFAULT: '#ffffff',
          raised: '#f9fafb',
          overlay: '#f3f4f6',
        },
        content: {
          DEFAULT: '#111827',  // primary text
          muted: '#4b5563',    // secondary text — 5.74:1 on white (AA)
          subtle: '#9ca3af',   // disabled — 2.85:1 (decorative only)
        },
      },
      fontFamily: {
        sans: ['Inter', ...defaultTheme.fontFamily.sans],
        mono: ['JetBrains Mono', ...defaultTheme.fontFamily.mono],
      },
      fontSize: {
        // Tailwind default scale works well — extend if needed
        // Each entry: [font-size, { lineHeight, letterSpacing, fontWeight }]
        'display': ['3.75rem', { lineHeight: '1', letterSpacing: '-0.02em' }],
        'heading': ['2.25rem', { lineHeight: '1.2', letterSpacing: '-0.01em' }],
      },
      spacing: {
        // Tailwind's 4px base is standard — add custom values only if needed
        '18': '4.5rem',   // 72px — useful for nav heights
        '22': '5.5rem',   // 88px
        '88': '22rem',    // sidebar widths
      },
      borderRadius: {
        // Override default to match your design language
        DEFAULT: '0.5rem',
      },
      boxShadow: {
        // Layered shadows for elevation system
        'elevation-1': '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
        'elevation-2': '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
        'elevation-3': '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
      },
    },
  },
  plugins: [],
}
```

---

## Color Scales
**When to use:** When building a multi-shade color scale for a brand color not in Tailwind's defaults.

Use a perceptual lightness curve — the steps between shades should feel visually equal:

```javascript
// Color scale pattern for a custom brand color
// 50: very light background tint
// 100: light background, hover states
// 200: borders, dividers
// 300: disabled states
// 400: placeholder text
// 500: icons, secondary text
// 600: primary action (check WCAG against white: aim for >= 4.5:1)
// 700: hover state for primary action
// 800: pressed state, dark text
// 900: darkest — headings on light backgrounds

const brandColors = {
  50:  '#faf5ff',
  100: '#f3e8ff',
  200: '#e9d5ff',
  300: '#d8b4fe',
  400: '#c084fc',
  500: '#a855f7',
  600: '#9333ea',  // 5.07:1 on white — AA compliant
  700: '#7e22ce',
  800: '#6b21a8',
  900: '#581c87',
}
```

**Instead of:** Eyeballing a color scale from a single brand color. Use a tool (Radix Colors, Palette by Cloudflare) to generate perceptually uniform steps.

---

## Typography Scale
**When to use:** Defining text styles across an application. A scale prevents ad-hoc font size choices.

```tsx
// Typography component using the scale
// Encapsulates the mapping from semantic names to Tailwind classes

interface TypographyProps {
  variant: 'display' | 'h1' | 'h2' | 'h3' | 'body' | 'small' | 'caption'
  as?: React.ElementType
  children: React.ReactNode
  className?: string
}

const styles: Record<TypographyProps['variant'], string> = {
  display: 'text-5xl md:text-6xl font-bold tracking-tight leading-none',
  h1:      'text-3xl md:text-4xl font-bold tracking-tight leading-tight',
  h2:      'text-2xl md:text-3xl font-semibold tracking-tight leading-snug',
  h3:      'text-xl md:text-2xl font-semibold leading-snug',
  body:    'text-base leading-relaxed',
  small:   'text-sm leading-normal',
  caption: 'text-xs leading-normal text-content-muted',
}

export function Typography({ variant, as, children, className }: TypographyProps) {
  const defaultTags: Record<TypographyProps['variant'], React.ElementType> = {
    display: 'h1', h1: 'h1', h2: 'h2', h3: 'h3',
    body: 'p', small: 'p', caption: 'span',
  }
  const Tag = as ?? defaultTags[variant]

  return <Tag className={`${styles[variant]} ${className ?? ''}`}>{children}</Tag>
}
```

---

## Dark Mode Tokens
**When to use:** When dark mode is requested. Token-based dark mode requires adding a second set of semantic values — primitives stay the same, semantics flip.

```css
/* Dark mode via class strategy (Tailwind: darkMode: 'class') */
:root {
  --color-bg-primary:   #ffffff;
  --color-text-primary: #111827;
  --color-border:       #e5e7eb;
  --color-accent:       #2563eb;
}

.dark {
  --color-bg-primary:   #0f172a;
  --color-text-primary: #f1f5f9;
  --color-border:       #1e293b;
  --color-accent:       #60a5fa;   /* lighter shade for dark bg — still AA compliant */
}
```

```javascript
// tailwind.config.js — enable class-based dark mode
module.exports = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          primary: 'var(--color-bg-primary)',
        },
        text: {
          primary: 'var(--color-text-primary)',
        },
      },
    },
  },
}
```

```tsx
// Toggle implementation
'use client'
import { useState, useEffect } from 'react'

export function DarkModeToggle() {
  const [dark, setDark] = useState(false)

  useEffect(() => {
    // Read system preference on mount
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    setDark(prefersDark)
  }, [])

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
  }, [dark])

  return (
    <button
      onClick={() => setDark(d => !d)}
      aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-pressed={dark}
    >
      {dark ? 'Light' : 'Dark'}
    </button>
  )
}
```
