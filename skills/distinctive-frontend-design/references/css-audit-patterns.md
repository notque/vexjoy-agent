# CSS Audit Patterns Reference

> **Scope**: grep/rg detection commands for banned fonts, hardcoded colors, anti-pattern CSS structures, and over-animation in frontend source files.
> **Version range**: CSS3+, all frameworks (Tailwind, CSS Modules, plain CSS/SCSS)
> **Generated**: 2026-04-16 — patterns apply to .css, .scss, .module.css, .tsx, .jsx, .html files

---

## Overview

This file provides runnable detection commands to audit a frontend codebase for design anti-patterns. Run these after generating a design specification to verify the implementation matches the intent. The most common failure mode is banned fonts slipping in through fallback stacks or Google Fonts imports, and hardcoded hex values bypassing the CSS custom property system.

---

## Anti-Pattern Catalog
<!-- no-pair-required: section-header-only; pairs live in each sub-section below -->

### ❌ Banned Fonts in CSS/HTML

**Detection**:
```bash
# Find banned font families in CSS/SCSS/style tags
grep -rn 'font-family.*\(Inter\|Roboto\|Arial\|Helvetica\|Space Grotesk\)' --include="*.css" --include="*.scss" --include="*.module.css"
grep -rn 'font-family.*\(Inter\|Roboto\|Arial\|Helvetica\|Space Grotesk\)' --include="*.tsx" --include="*.jsx" --include="*.html"

# Find system font stacks (banned: -apple-system, BlinkMacSystemFont, 'Segoe UI')
rg '-apple-system|BlinkMacSystemFont|Segoe UI' --type css
rg '-apple-system|BlinkMacSystemFont|Segoe UI' -g "*.tsx" -g "*.jsx"

# Find Google Fonts imports loading banned fonts
grep -rn 'fonts.googleapis.com.*\(Inter\|Roboto\|Space.Grotesk\)' --include="*.html" --include="*.tsx" --include="*.jsx"
grep -rn "next/font.*\(inter\|roboto\)" --include="*.tsx" --include="*.jsx" -i
```

**What it looks like**:
```css
body {
  font-family: Inter, -apple-system, sans-serif; /* banned: Inter + system stack */
}
h1 {
  font-family: 'Space Grotesk', Roboto, Arial; /* banned: all three */
}
```

**Why wrong**: These fonts are overused to the point of invisibility. They signal generic AI output, not contextual design. Every project that reaches for Inter as a default produces the same page. Using them makes the design indistinguishable from a template.

**Do instead**: Select from `references/font-catalog.json` under the matching aesthetic category. An editorial serif or a constructed grotesque chosen for the project context will distinguish the work from every other Inter page:
```css
/* Use a pre-approved font from references/font-catalog.json */
body {
  font-family: 'DM Sans', sans-serif;
}
h1 {
  font-family: 'Fraunces', Georgia, serif; /* editorial, distinctive */
}
```

---

### ❌ Hardcoded Colors Bypassing CSS Custom Properties

**Detection**:
```bash
# Find hardcoded hex values in CSS (skip lines that define custom properties)
grep -rn '#[0-9a-fA-F]\{3,6\}' --include="*.css" --include="*.scss" | grep -v '^\s*--'

# Find hardcoded rgb/rgba in style rules
rg 'color:\s*(rgb|rgba|hsl|hsla)\(' --type css
rg 'background(-color)?:\s*(rgb|rgba|hsl|hsla)\(' --type css

# Find Tailwind arbitrary color values (should use CSS vars via theme config instead)
rg 'text-\[#[0-9a-fA-F]+\]|bg-\[#[0-9a-fA-F]+\]|border-\[#[0-9a-fA-F]+\]' -g "*.tsx" -g "*.jsx"
```

**What it looks like**:
```css
.hero-title {
  color: #1a1a2e;           /* hardcoded — bypasses token system */
  background: #4a90e2;      /* hardcoded — impossible to audit ratio */
}
```

**Why wrong**: Hardcoded colors scattered across files break the 60/30/10 dominance ratio audit. You cannot verify palette coherence when the palette exists only in scattered hex literals. Palette changes require grep-and-replace across dozens of files instead of one `:root` edit.

**Do instead**: Define all palette values as CSS custom properties in a single `:root` block, then reference them everywhere via `var()`. Palette auditing becomes a one-file operation:
```css
:root {
  --color-dominant: #1a1a2e;
  --color-accent: #4a90e2;
}
.hero-title {
  color: var(--color-dominant);
  background: var(--color-accent);
}
```

---

### ❌ Over-Animation (Violating the 2-to-3 Rule)

**Detection**:
```bash
# Count animation declarations per CSS file (flag files with > 5)
grep -c 'animation:' **/*.css **/*.scss 2>/dev/null

# Find all animation declarations
grep -rn '^\s*animation:' --include="*.css" --include="*.scss" --include="*.module.css"

# Find Framer Motion animated elements (count total — over 6 per route is a signal)
rg 'motion\.(div|section|h[1-6]|p|span|article|header|footer)' -g "*.tsx" -g "*.jsx" | wc -l

# Find blanket transition (anti-pattern: animating everything with *)
grep -rn '\*\s*{[^}]*transition' --include="*.css" --include="*.scss"
grep -rn 'transition:\s*all' --include="*.css" --include="*.scss"
```

**What it looks like**:
```css
/* Animating everything — loses impact */
.hero         { animation: fade-in 0.4s ease; }
.hero-title   { animation: slide-up 0.5s ease 0.1s; }
.hero-subtitle{ animation: slide-up 0.5s ease 0.2s; }
.hero-cta     { animation: slide-up 0.5s ease 0.3s; }
.nav          { animation: slide-down 0.4s ease; }
.feature-card { animation: scale-in 0.5s ease; }
.feature-icon { animation: rotate-in 0.6s ease; }
/* 7 animations — three times over budget */
```

**Why wrong**: When everything moves, nothing stands out. Motion creates hierarchy; animating every element collapses that hierarchy. Ten animations communicate noise, three intentional animations communicate craft.

**Do instead**: Fill exactly three motion slots (entrance, scroll-reveal, interaction) and animate nothing else. Silence is hierarchy:
```css
/* 3 intentional slots: entrance, scroll-reveal (JS), interaction */
.hero-title { animation: slide-up 0.8s cubic-bezier(0.22, 1, 0.36, 1) both; }
.hero-cta   { animation: fade-in 0.6s ease 0.4s both; }
/* Scroll reveal on one feature block via IntersectionObserver fills the third slot */
/* Everything else: no animation */
```

---

### ❌ Single-Layer Flat Backgrounds

**Detection**:
```bash
# Find background: or background-color: with only a color (no gradient)
grep -rn '^\s*background-color:' --include="*.css" --include="*.scss" --include="*.module.css"
grep -rn '^\s*background:\s*#\|^\s*background:\s*rgb\|^\s*background:\s*var(' --include="*.css" --include="*.scss"

# Verify hero/section elements have gradient layers (count should be > 0)
grep -rn '\.hero\b\|\.landing\b\|\.page-hero\b' --include="*.css" -A 8 | grep -c 'gradient'
```

**What it looks like**:
```css
.hero {
  background-color: #0a0a1a; /* flat — fails the 2-layer Phase 5 gate */
}
.landing-section {
  background: #f5f5f0;       /* single value — no atmospheric depth */
}
```

**Why wrong**: A flat background creates no visual depth, no focal point, no mood. It is the visual equivalent of saying nothing. The Phase 5 gate requires at least two layers (base color plus gradient layer) because depth is what separates distinctive design from a stylesheet reset.

**Do instead**: Layer at least one radial gradient above the base color to create focal direction and atmospheric depth. Reference `background-techniques.md` for recipe options:
```css
.hero {
  background:
    radial-gradient(ellipse 80% 60% at 20% 40%, rgba(99, 102, 241, 0.15), transparent 60%),
    radial-gradient(ellipse 60% 40% at 80% 80%, rgba(168, 85, 247, 0.10), transparent 50%),
    #0a0a1a; /* base + two glow layers = atmospheric depth */
}
```

---

### ❌ `sans-serif` Bare Fallback (No Named Fallback)

**Detection**:
```bash
# Find font stacks where sans-serif is the only or first value
grep -rn "font-family:\s*sans-serif\b" --include="*.css" --include="*.scss"
rg "font-family:\s*sans-serif\b" --type css

# Find missing fallback (only one font in stack, no comma)
grep -rn "font-family:\s*'[^']*'" --include="*.css" | grep -v ','
```

**What it looks like**:
```css
body { font-family: sans-serif; }        /* OS default — different on every platform */
h1   { font-family: 'Outfit'; }          /* no fallback — FOUT on slow connections */
```

**Why wrong**: `sans-serif` alone renders as Helvetica (macOS), Arial (Windows), or Liberation Sans (Linux): three different pages. A missing fallback causes FOUT (flash of unstyled text) on slow connections when the web font has not loaded.

**Do instead**: Add one named system fallback between the web font and the generic family. The named fallback degrades gracefully while the web font loads:
```css
body { font-family: 'DM Sans', 'Gill Sans', sans-serif; }
h1   { font-family: 'Fraunces', Georgia, serif; }
```

---

## Error-Fix Mappings

| Error (validate_design.py) | Root Cause | Fix |
|----------------------------|------------|-----|
| `"banned font detected"` | Font name matches banned list | Replace with catalog font; audit fallback stacks with grep above |
| `"background: single layer"` | `.hero` has `background-color` only | Add `radial-gradient` layer above base color |
| `"motion count exceeds 3"` | More than 3 CSS `animation:` per route | Remove ambient micro-interactions; keep entrance/scroll/interaction only |
| `"hardcoded color values"` | Hex/rgb outside `:root` definitions | Move to `--color-*` custom property; reference via `var()` |
| `"font-family: bare sans-serif"` | No named fallback before generic family | Add one named fallback font between web font and `sans-serif` |

---

## Detection Commands Reference

```bash
# Banned fonts (CSS/SCSS)
grep -rn 'font-family.*\(Inter\|Roboto\|Arial\|Helvetica\|Space Grotesk\)' --include="*.css" --include="*.scss"

# System font stacks
rg '-apple-system|BlinkMacSystemFont|Segoe UI' --type css

# Hardcoded hex (not in custom property lines)
grep -rn '#[0-9a-fA-F]\{3,6\}' --include="*.css" --include="*.scss" | grep -v '^\s*--'

# Tailwind arbitrary colors
rg 'text-\[#[0-9a-fA-F]+\]|bg-\[#[0-9a-fA-F]+\]' -g "*.tsx" -g "*.jsx"

# Over-animation (all animation declarations)
grep -rn '^\s*animation:' --include="*.css" --include="*.scss" --include="*.module.css"

# Blanket transition (transition: all)
grep -rn 'transition:\s*all' --include="*.css" --include="*.scss"

# Single-layer backgrounds
grep -rn '^\s*background:\s*#\|^\s*background:\s*rgb' --include="*.css" --include="*.scss"

# Bare sans-serif fallback
grep -rn "font-family:\s*sans-serif" --include="*.css" --include="*.scss"
```

---

## See Also

- `anti-patterns.json` — full banned font list, cliche color catalog, layout cliche list
- `font-catalog.json` — pre-approved fonts by aesthetic category
- `background-techniques.md` — layered gradient and atmospheric background recipes
- `animation-patterns.md` — 2-to-3 rule implementation patterns with timing values
