# Image Format Selection Guide

Reference for choosing the right image format based on content type and use case.

---

## Quick Reference

| Content Type | First Choice | Fallback | Avoid |
|--------------|--------------|----------|-------|
| Photos | WebP | JPEG | PNG, GIF |
| Screenshots | WebP | PNG | JPEG (artifacts) |
| Diagrams | SVG | WebP/PNG | JPEG |
| Icons | SVG | PNG (small) | JPEG, GIF |
| Logos | SVG | PNG (transparent) | JPEG |
| Animations | WebP | GIF, MP4 | APNG |
| Text-heavy | PNG | WebP | JPEG |

---

## Format Characteristics

### JPEG/JPG

**Best for:**
- Photographs
- Complex images with gradients
- Images without transparency
- When file size is critical

**Avoid for:**
- Screenshots (text gets artifacts)
- Diagrams with sharp edges
- Images requiring transparency
- Icons and logos

**Compression:**
- Lossy only
- Quality 80-85 recommended
- Lower quality = smaller files, more artifacts

**Browser support:** Universal

---

### PNG

**Best for:**
- Screenshots with text
- Diagrams with sharp edges
- Images requiring transparency
- Graphics with limited colors

**Avoid for:**
- Photographs (file size too large)
- Anything that could be SVG
- Large images where WebP works

**Variants:**
- PNG-8: 256 colors max, smaller files
- PNG-24: Full color, larger files
- PNG-32: Full color + alpha transparency

**Compression:** Lossless (or lossy with pngquant)

**Browser support:** Universal

---

### WebP

**Best for:**
- Everything (modern browsers)
- Replacing both JPEG and PNG
- When file size matters
- Animated images (replacing GIF)

**Avoid for:**
- When broad compatibility required
- Email images
- Documents requiring print quality

**Features:**
- 25-35% smaller than JPEG
- Supports transparency
- Supports animation
- Lossy and lossless modes

**Browser support:** All modern browsers (Chrome, Firefox, Safari, Edge)

---

### SVG

**Best for:**
- Icons
- Logos
- Simple diagrams
- Illustrations
- Any vector graphics

**Avoid for:**
- Photographs
- Complex images with many colors
- Screenshots
- Raster-originated content

**Features:**
- Scales infinitely without quality loss
- Small file size for simple graphics
- Can be styled with CSS
- Accessible (text is text)

**Warning signs:**
- SVG file >100 KB (probably too complex)
- Embedded bitmaps (defeats purpose)
- Thousands of path elements (performance)

**Browser support:** Universal (some features vary)

---

### GIF

**Best for:**
- Simple animations (legacy)
- When WebP animation not supported

**Avoid for:**
- Static images (PNG/WebP better)
- Complex animations (video better)
- Photos (256 color limit)
- Modern browsers (WebP preferred)

**Limitations:**
- 256 color maximum
- Large file sizes for animation
- No alpha transparency (only binary)

**Browser support:** Universal

---

## Decision Flowchart

```
Is it a vector graphic (logo, icon, diagram)?
├─ YES: Use SVG
└─ NO: Continue...

Is animation required?
├─ YES: Is it simple (<5 seconds, <256 colors)?
│   ├─ YES: WebP animation (or GIF fallback)
│   └─ NO: Consider MP4/WebM video
└─ NO: Continue...

Is it a photograph or complex gradient?
├─ YES: Use WebP (JPEG fallback)
└─ NO: Continue...

Does it have transparency?
├─ YES: Use WebP (PNG fallback)
└─ NO: Continue...

Does it have text or sharp edges?
├─ YES: Use PNG or WebP
└─ NO: Use WebP (JPEG fallback)
```

---

## Filename Detection Heuristics

The image auditor uses filename patterns to suggest format corrections:

### Screenshot Indicators
- Contains: "screenshot", "screen-", "capture", "snap"
- Pattern: `YYYY-MM-DD` date prefix
- Expected: PNG or WebP

### Photo Indicators
- Contains: "photo", "hero", "banner", "background", "cover"
- Pattern: Camera-generated names (IMG_, DSC_, DCIM)
- Expected: JPEG or WebP

### Diagram Indicators
- Contains: "diagram", "chart", "graph", "flow", "architecture"
- Expected: SVG or PNG

### Icon/Logo Indicators
- Contains: "icon", "logo", "favicon", "badge", "avatar"
- Pattern: Small dimensions (<200px)
- Expected: SVG or PNG

---

## Common Mismatches

### PNG Photo (High Priority Fix)
**Problem:** Photo saved as PNG
**Impact:** 3-5x larger than needed
**Solution:** Convert to WebP or JPEG

Detection:
- Large dimensions (>1000px)
- File size >500 KB
- Filename suggests photo

### JPEG Screenshot (Medium Priority)
**Problem:** Screenshot saved as JPEG
**Impact:** Text appears blurry/artifacted
**Solution:** Convert to PNG or WebP

Detection:
- Filename contains "screenshot" or "screen"
- Contains visible text/UI elements

### Raster Icon (Low Priority)
**Problem:** Icon as PNG instead of SVG
**Impact:** Scaling issues, larger than needed
**Solution:** Convert to SVG if possible

Detection:
- Small dimensions (<100px)
- Filename contains "icon" or "logo"

### Animated GIF (Medium Priority)
**Problem:** Animation as GIF instead of WebP
**Impact:** Large file size, poor quality
**Solution:** Convert to WebP animation

Detection:
- GIF file >200 KB
- Contains "anim" in filename

---

## Browser Compatibility Table

| Format | Chrome | Firefox | Safari | Edge | IE11 |
|--------|--------|---------|--------|------|------|
| JPEG | Yes | Yes | Yes | Yes | Yes |
| PNG | Yes | Yes | Yes | Yes | Yes |
| GIF | Yes | Yes | Yes | Yes | Yes |
| WebP | Yes | Yes | Yes | Yes | No |
| SVG | Yes | Yes | Yes | Yes | Yes* |
| AVIF | Yes | Yes | Yes | Yes | No |

*IE11 SVG support has limitations with some features

---

## Conversion Commands

```bash
# JPEG to WebP
cwebp -q 80 photo.jpg -o photo.webp

# PNG to WebP (with transparency)
cwebp -q 80 -alpha_q 100 screenshot.png -o screenshot.webp

# PNG to WebP (lossless)
cwebp -lossless screenshot.png -o screenshot.webp

# Raster to SVG (for simple graphics)
# Use potrace or vectorizer.io for best results

# Check if PNG could be PNG-8
pngquant --quality=65-80 --skip-if-larger image.png

# GIF to WebP animation
gif2webp -q 80 animation.gif -o animation.webp
```
