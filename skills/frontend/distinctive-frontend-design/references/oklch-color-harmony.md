# oklch() Color Harmony

<!-- Loaded by distinctive-frontend-design when task involves color palette, harmony, oklch, perceptual color, or color generation -->

Build harmonious palettes with oklch(). The oklch() color space is perceptually uniform: the same lightness (L) and chroma (C) values produce visually balanced colors regardless of hue (H). This makes it the right tool for generating palette companions — fix L and C, vary only H, and every resulting color looks like it belongs in the same family.

## Why oklch Beats HSL

HSL's "50% lightness" produces wildly different perceived brightness across hues. Yellow at `hsl(60, 100%, 50%)` looks bright and light. Blue at `hsl(240, 100%, 50%)` looks dark and heavy. They are mathematically equivalent in HSL and perceptually incompatible on screen.

oklch fixes this. `oklch(55% 0.15 60)` (yellow region) and `oklch(55% 0.15 240)` (blue region) have the same perceived brightness. This means you can rotate the hue wheel and every stop produces a color that pairs naturally with the others.

```css
/* HSL: these "match" mathematically but look unbalanced */
--yellow: hsl(60, 100%, 50%);   /* appears very light */
--blue:   hsl(240, 100%, 50%);  /* appears very dark */

/* oklch: these actually match perceptually */
--yellow: oklch(70% 0.15 90);   /* warm, balanced */
--blue:   oklch(70% 0.15 250);  /* cool, same visual weight */
```

## Core Technique: Fix L and C, Vary H

The foundation of oklch harmony: pick a lightness and chroma, then select hues based on their angular relationship on the color wheel.

```css
:root {
  --primary:   oklch(55% 0.15 250);  /* blue */
  --secondary: oklch(55% 0.15 200);  /* teal */
  --accent:    oklch(55% 0.15 330);  /* rose */
}
```

All three colors share the same visual weight. They harmonize because their only difference is hue angle.

## Harmony Types

### Analogous Harmony (Hues Within 30 Degrees)

Colors that sit next to each other on the wheel. Produces calm, cohesive palettes with low contrast between hues. Best for backgrounds, navigation, and surfaces that should feel unified.

```css
/* Analogous: ocean palette */
--deep-sea:   oklch(40% 0.12 230);  /* blue */
--coastal:    oklch(40% 0.12 210);  /* blue-teal, 20deg away */
--lagoon:     oklch(40% 0.12 250);  /* blue-indigo, 20deg away */
```

### Complementary Harmony (Hues 180 Degrees Apart)

Maximum contrast between two hues. Creates energy and visual tension. Use for primary/accent pairs where the accent needs to pop against the primary.

```css
/* Complementary: corporate with punch */
--primary: oklch(45% 0.14 250);  /* blue */
--accent:  oklch(60% 0.18 70);   /* warm orange, 180deg away */
```

Note: the accent uses higher lightness (60% vs 45%) and higher chroma (0.18 vs 0.14) because accents need to draw the eye. Exact L/C matching is the starting point, not the final answer — adjust for visual hierarchy after establishing the base relationship.

### Triadic Harmony (Hues 120 Degrees Apart)

Three colors evenly spaced around the wheel. Balanced energy without the tension of complementary. Good for UI that needs three distinct functional zones.

```css
/* Triadic: balanced three-color system */
--primary:   oklch(50% 0.15 250);  /* blue */
--secondary: oklch(50% 0.15 10);   /* red-orange, 120deg */
--tertiary:  oklch(50% 0.15 130);  /* green, 240deg */
```

### Split Complementary (Hue + Two Neighbors of Its Complement)

Take one hue, find its complement (180deg away), then use the two hues 30deg on either side of that complement. Provides contrast without the intensity of pure complementary.

```css
/* Split complementary: sophisticated contrast */
--primary: oklch(50% 0.14 250);  /* blue */
--warm-a:  oklch(55% 0.16 40);   /* complement neighbor: warm red */
--warm-b:  oklch(55% 0.16 100);  /* complement neighbor: warm yellow-green */
```

## Lightness Roles: Text vs Background

Lightness determines where a color works in the layout:

| Role | Lightness Range | Example |
|------|----------------|---------|
| Text on light background | L < 40% | `oklch(25% 0.08 250)` |
| Interactive elements (buttons, links) | L: 40-60% | `oklch(50% 0.15 250)` |
| Borders, dividers | L: 60-75% | `oklch(70% 0.06 250)` |
| Subtle tints, hover backgrounds | L: 85-93% | `oklch(90% 0.03 250)` |
| Page backgrounds | L > 93% | `oklch(97% 0.005 250)` |

```css
/* Full blue scale from one hue, varying only L and C */
:root {
  --blue-text:    oklch(25% 0.08 250);
  --blue-primary: oklch(50% 0.15 250);
  --blue-border:  oklch(72% 0.06 250);
  --blue-hover:   oklch(92% 0.03 250);
  --blue-surface: oklch(97% 0.005 250);
}
```

## Dark Mode Inversion

The dark mode technique: swap lightness values while keeping hue and chroma. Text goes light, backgrounds go dark, interactive elements shift toward the middle.

```css
/* Light mode */
:root {
  --text:    oklch(20% 0.02 250);
  --surface: oklch(97% 0.005 250);
  --primary: oklch(50% 0.15 250);
}

/* Dark mode: invert L, keep H and C */
[data-theme="dark"] {
  --text:    oklch(92% 0.02 250);   /* was 20%, now 92% */
  --surface: oklch(15% 0.02 250);   /* was 97%, now 15% */
  --primary: oklch(65% 0.15 250);   /* bumped from 50% for contrast on dark */
}
```

The primary color shifts from 50% to 65% lightness in dark mode because interactive elements need more lightness to maintain contrast against dark surfaces. The exact bump depends on the surface darkness — test with a contrast checker.

## Chroma Guidelines

Chroma (C) controls color intensity. Higher chroma = more saturated, vivid color. Lower chroma = more muted, greyed.

| Chroma Range | Character | Use For |
|-------------|-----------|---------|
| 0.00 - 0.02 | Nearly neutral | Backgrounds, surfaces, body text |
| 0.03 - 0.08 | Subtle tint | Tinted surfaces, subtle borders, muted states |
| 0.10 - 0.18 | Vivid, clean | Primary colors, buttons, links, accents |
| 0.20+ | Very saturated | Use sparingly — badges, alerts, error states |

Warning: high-chroma colors at extreme lightness values (very light or very dark) may fall outside the sRGB gamut. Check with `color-gamut: srgb` media query or test in browsers that show gamut warnings.

## Building a Complete Palette

Starting from a brand blue of `oklch(50% 0.15 250)`, build a full palette:

```css
:root {
  /* Primary: brand blue */
  --primary:       oklch(50% 0.15 250);
  --primary-hover: oklch(45% 0.15 250);
  --primary-light: oklch(92% 0.03 250);

  /* Secondary: analogous (30deg away) */
  --secondary:       oklch(50% 0.12 220);
  --secondary-hover: oklch(45% 0.12 220);

  /* Accent: complementary (180deg away) */
  --accent:       oklch(58% 0.18 70);
  --accent-hover: oklch(52% 0.18 70);

  /* Neutrals: same hue, minimal chroma */
  --text:         oklch(20% 0.015 250);
  --text-muted:   oklch(45% 0.01 250);
  --border:       oklch(80% 0.01 250);
  --surface:      oklch(97% 0.005 250);
  --surface-alt:  oklch(94% 0.008 250);

  /* Functional: fixed hues, consistent L/C */
  --success: oklch(55% 0.16 145);
  --warning: oklch(65% 0.16 85);
  --error:   oklch(55% 0.18 25);
  --info:    oklch(55% 0.14 250);
}
```

The neutrals carry a whisper of the primary hue (H: 250) with near-zero chroma. This tints the greys ever so slightly toward blue, creating a cohesive feel. Pure grey (`oklch(x% 0 0)`) is fine but feels disconnected from the rest of the palette.
