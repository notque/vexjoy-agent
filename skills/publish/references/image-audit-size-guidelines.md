# Image Size Guidelines

Reference for maximum recommended file sizes by image type and use case.

---

## Size Thresholds by Type

| Image Type | Target Size | Maximum | Action if Exceeded |
|------------|-------------|---------|-------------------|
| Icons | <20 KB | 50 KB | Convert to SVG or reduce dimensions |
| Logos | <50 KB | 100 KB | Use SVG, optimize PNG |
| Screenshots | <150 KB | 300 KB | Compress, reduce dimensions |
| Diagrams | <100 KB | 200 KB | Use SVG, simplify if raster |
| Photos | <300 KB | 500 KB | Resize, increase compression |
| Hero/Banner | <500 KB | 800 KB | Resize to viewport width |

---

## Dimension Guidelines

### Maximum Dimensions by Use Case

| Use Case | Max Width | Max Height | Notes |
|----------|-----------|------------|-------|
| Inline content | 800px | - | Standard content width |
| Full-width | 1200px | - | Blog container width |
| Hero images | 1920px | 1080px | Above fold, critical |
| Thumbnails | 400px | 300px | Lists, cards |
| Icons | 64px | 64px | UI elements |
| Favicons | 32px | 32px | Browser tab |

### Responsive Considerations

For responsive designs, provide:
- 1x: Standard dimensions
- 2x: Retina/HiDPI (optional, increases file size)

---

## Format-Specific Size Expectations

### JPEG/JPG
- Quality 80-85: Good balance of size/quality
- Quality 60-75: Acceptable for thumbnails
- Quality 90+: Rarely needed, large files

Typical sizes at 1200px width:
- Simple photo: 80-150 KB
- Complex photo: 150-300 KB
- High detail: 300-500 KB

### PNG
- Best for screenshots, diagrams with text
- Can be large due to lossless compression
- Consider PNG-8 for simple graphics (<256 colors)

Typical sizes:
- Simple diagram: 20-50 KB
- Screenshot (cropped): 50-150 KB
- Full screenshot: 150-400 KB

### WebP
- 25-35% smaller than JPEG at equivalent quality
- Supports transparency like PNG
- Recommended for web use

Typical sizes (vs JPEG equivalent):
- Photo: 60-200 KB (was 80-300 KB)
- Screenshot: 40-100 KB (was 50-150 KB)

### SVG
- Size depends on complexity, not dimensions
- Simple icons: 1-5 KB
- Complex illustrations: 10-50 KB
- Detailed diagrams: 50-200 KB

Warning signs:
- SVG >100 KB: Probably should be raster
- SVG with embedded bitmaps: Convert to PNG/WebP

### GIF
- Avoid for static images (PNG/WebP better)
- For animations:
  - Simple loop: 100-500 KB
  - Complex animation: 500 KB - 2 MB
  - Consider video (MP4/WebM) for >1 MB

---

## Page Weight Budgets

### Per-Page Recommendations

| Page Type | Total Image Budget | Notes |
|-----------|-------------------|-------|
| Blog post | <1 MB | 3-5 images typical |
| Landing page | <2 MB | Hero + features |
| Gallery | <3 MB | Use lazy loading |
| Documentation | <500 KB | Mostly text |

### Cumulative Thresholds

| Status | Total Images | Action |
|--------|--------------|--------|
| Good | <500 KB | No action needed |
| Acceptable | 500 KB - 1 MB | Monitor growth |
| Warning | 1 MB - 2 MB | Optimize largest images |
| Critical | >2 MB | Immediate optimization needed |

---

## Optimization Techniques

### Resizing
- Never serve images larger than display size
- 1200px max for full-width blog content
- 800px for inline content images
- Use srcset for responsive images

### Compression
- JPEG: Quality 80-85 for web
- PNG: Use pngquant for lossy, optipng for lossless
- WebP: Quality 80 default
- SVG: Minify, remove metadata

### Format Selection
1. Is it a photo? -> WebP or JPEG
2. Needs transparency? -> WebP or PNG
3. Is it vector art? -> SVG
4. Is it animated? -> WebP or MP4

### Tools

Command-line optimization:
```bash
# JPEG optimization
jpegoptim --size=300k image.jpg

# PNG optimization
pngquant --quality=65-80 image.png

# WebP conversion
cwebp -q 80 image.png -o image.webp

# Resize with ImageMagick
convert image.jpg -resize 1200x\> resized.jpg

# Bulk WebP conversion
for f in *.png; do cwebp -q 80 "$f" -o "${f%.png}.webp"; done
```

---

## Red Flags

### Immediate Action Required
- Any image >1 MB
- Screenshot >500 KB
- Icon/logo >100 KB
- Multiple images >500 KB on same page

### Investigation Needed
- PNG used for photos
- JPEG used for screenshots with text
- Images wider than 2000px
- Animated GIF >2 MB

### Consider Optimization
- Any image that could be WebP but isn't
- Photos at quality >90
- Uncompressed PNGs
