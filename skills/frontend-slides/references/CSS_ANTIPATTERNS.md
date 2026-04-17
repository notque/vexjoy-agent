# CSS Anti-Patterns Reference

> **Scope**: CSS gotchas specific to single-file HTML presentations — viewport sizing, font loading, overflow, and layout.
> **Version range**: CSS3+ (all modern browsers); `dvh` unit requires Chrome 108+, Firefox 109+, Safari 15.4+
> **Generated**: 2026-04-17

---

## Overview

HTML slide decks fail silently on specific CSS patterns: text disappears, slides scroll when they
shouldn't, fonts flash blank, and safe-area overflows break on notched phones. Each of these has
a detectable grep signature. Run these checks before delivery — they catch issues that look correct
on the dev machine but break in a projector or mobile context.

---

## Anti-Pattern Catalog

### ❌ Negated `clamp()` with Unary Minus

**Detection**:
```bash
grep -n '\-clamp(' output.html
rg '\-clamp\(' output.html
```

**What it looks like**:
```css
.slide-title {
  margin-top: -clamp(1rem, 2vw, 3rem);   /* silently becomes 0 */
}
```

**Why wrong**: The CSS unary minus operator cannot be applied directly to a CSS function.
Browsers silently resolve `-clamp(...)` to `0` — no error, no warning. Text collapses or
negative spacing disappears entirely.

**Fix**:
```css
.slide-title {
  margin-top: calc(-1 * clamp(1rem, 2vw, 3rem));   /* correct */
}
```

**Version note**: This is a spec behavior, not a browser bug. It applies to all versions of CSS.

---

### ❌ `100vh` Only (No `dvh` Fallback)

**Detection**:
```bash
grep -n '100vh' output.html | grep -v '100dvh'
# Any line with 100vh but NOT on a line that also has 100dvh needs fixing.
# More precise:
grep -n 'height:\s*100vh' output.html
```

**What it looks like**:
```css
.slide {
  height: 100vh;   /* breaks on mobile — includes browser chrome */
}
```

**Why wrong**: On mobile browsers, `100vh` includes the address bar and tab bar height.
Slides overflow or get partially hidden behind browser UI. `100dvh` (dynamic viewport height)
excludes the browser chrome and is the correct unit for full-screen slides.

**Fix**:
```css
.slide {
  height: 100vh;    /* fallback for browsers without dvh support */
  height: 100dvh;   /* overrides when supported (Chrome 108+, FF 109+, Safari 15.4+) */
}
```

**Version note**: `dvh` is broadly supported since mid-2023. The two-declaration pattern is
required because older browsers ignore the `dvh` line without error.

---

### ❌ Missing `font-display: swap` on `@font-face`

**Detection**:
```bash
grep -n '@font-face' output.html
grep -c 'font-display' output.html
# Count of @font-face blocks should equal count of font-display lines.
# Quick check: if font-display count is 0 and @font-face count > 0: broken.
```

**What it looks like**:
```css
@font-face {
  font-family: 'Inter';
  src: url('...') format('woff2');
  /* no font-display */
}
```

**Why wrong**: Without `font-display: swap`, text is invisible (FOIT — flash of invisible text)
while the font loads. On a slow network or projector WiFi, slides display blank text for
several seconds — worst possible presentation experience.

**Fix**:
```css
@font-face {
  font-family: 'Inter';
  src: url('...') format('woff2');
  font-display: swap;   /* show fallback font immediately, swap when loaded */
}
```

---

### ❌ Fixed Pixel Heights on Inner Containers

**Detection**:
```bash
grep -n 'height:\s*[0-9]\+px' output.html | grep -v '\.slide\b'
rg 'height:\s*\d+px' output.html
```

**What it looks like**:
```css
.slide-image {
  height: 300px;   /* overflows at small viewports */
}
.code-block {
  height: 200px;   /* can't adapt to 375x667 viewport */
}
```

**Why wrong**: Fixed pixel heights overflow at small viewports. A slide that fits at 1920×1080
clips content at 375×667 (iPhone SE). The validation script tests 9 breakpoints — fixed heights
fail at least 2-3 of them.

**Fix**:
```css
.slide-image {
  max-height: min(50vh, 300px);   /* constrains without overflowing */
  width: 100%;
  object-fit: contain;
}
.code-block {
  max-height: min(40vh, 200px);
  overflow: hidden;
}
```

---

### ❌ Missing `viewport-fit=cover` Meta Tag

**Detection**:
```bash
grep -n 'viewport' output.html
grep -n 'viewport-fit' output.html
# If first hits but second doesn't: meta tag is incomplete.
```

**What it looks like**:
```html
<meta name="viewport" content="width=device-width, initial-scale=1">
<!-- missing viewport-fit=cover -->
```

**Why wrong**: Without `viewport-fit=cover`, `env(safe-area-inset-*)` values resolve to `0px`
on notched devices (iPhone X and later). The mandatory CSS base block uses
`env(safe-area-inset-top, 0px)` for padding — it silently does nothing without this meta tag.
Slides overlap the notch on iPhone.

**Fix**:
```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
```

---

### ❌ External Font CDN Without Local Fallback

**Detection**:
```bash
grep -n 'fonts.googleapis\|fonts.gstatic\|cdnfonts\|typekit' output.html
# Any CDN font reference without a local @font-face fallback is a risk.
grep -c '@font-face' output.html
# If CDN fonts present but @font-face count is 0: no offline fallback.
```

**What it looks like**:
```html
<link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet">
```

**Why wrong**: Conference projectors, hotel WiFi, and demo environments frequently block
external CDN requests or have no internet. The presentation renders in Times New Roman
or similar browser default — ruins carefully chosen preset aesthetics.

**Fix**:
```css
/* Load from CDN but define local fallback stack */
@font-face {
  font-family: 'Inter';
  src: local('Inter'),
       url('https://fonts.gstatic.com/...') format('woff2');
  font-display: swap;
}
/* Always include a system font fallback in the stack */
--body-font: 'Inter', system-ui, -apple-system, sans-serif;
```

---

### ❌ `min-height` on `.slide` Allowing Growth Past Viewport

**Detection**:
```bash
grep -n 'min-height.*slide\|\.slide.*min-height' output.html
rg 'min-height' output.html
```

**What it looks like**:
```css
.slide {
  min-height: 100vh;   /* allows slide to grow beyond viewport */
}
```

**Why wrong**: `min-height` lets the slide grow taller than the viewport when content overflows.
This creates scrollable slides — slides become web pages. The correct behavior is to split
content across multiple slides, not allow the container to grow.

**Fix**: Use `height: 100vh; height: 100dvh` with `overflow: hidden` instead of `min-height`.
If content exceeds the slide, split it into two slides.

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Text disappears or spacing collapses | `-clamp(...)` resolves to `0` | Replace with `calc(-1 * clamp(...))` |
| Slides clip behind browser UI on mobile | `height: 100vh` only | Add `height: 100dvh` as second declaration |
| Text blank for 2-3s on load | Missing `font-display: swap` | Add `font-display: swap` to every `@font-face` |
| Overflow at 375×667 but not 1920×1080 | Fixed pixel height on inner element | Switch to `max-height: min(Xvh, Ypx)` |
| Content overlaps phone notch | Missing `viewport-fit=cover` in meta | Update viewport meta tag |
| Presentation renders in Times New Roman | CDN font blocked, no fallback | Add `local('FontName')` src + system font stack |
| Validation passes visually but fails script | `min-height` on `.slide` | Replace with `height` + `overflow: hidden` |

---

## Detection Commands Reference

```bash
# Negated clamp (silently becomes 0)
grep -n '\-clamp(' output.html

# 100vh without 100dvh fallback
grep -n 'height:\s*100vh' output.html

# Missing font-display:swap
grep -n '@font-face' output.html
grep -c 'font-display' output.html

# Fixed pixel heights on inner elements
grep -n 'height:\s*[0-9]\+px' output.html | grep -v '\.slide\b'

# Missing viewport-fit=cover
grep -n 'viewport' output.html | grep -v 'viewport-fit'

# CDN fonts without local fallback
grep -n 'fonts.googleapis\|fonts.gstatic' output.html

# min-height on slides
grep -n 'min-height' output.html
```

---

## See Also

- `skills/frontend-slides/references/STYLE_PRESETS.md` — CSS base block (mandatory), preset variables, CSS Gotchas table
- `skills/frontend-slides/references/JS_CONTROLLER.md` — JavaScript anti-patterns with detection commands
