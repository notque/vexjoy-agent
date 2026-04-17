# Gallery Patterns

Component patterns and implementation examples for React portfolio galleries.

## Image Gallery with Filtering

**Component Structure**:
```tsx
// components/Gallery.tsx
'use client'
import { useState } from 'react'
import Image from 'next/image'

export function Gallery({ images, categories }) {
  const [filter, setFilter] = useState('all')

  const filtered = filter === 'all'
    ? images
    : images.filter(img => img.category === filter)

  return (
    <div>
      <CategoryFilter
        categories={categories}
        active={filter}
        onChange={setFilter}
      />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map(image => (
          <ImageCard key={image.id} image={image} />
        ))}
      </div>
    </div>
  )
}
```

## Next.js Image Optimization Quick Reference

**Priority Loading (above-the-fold)**:
```tsx
<Image
  src="/hero-artwork.jpg"
  alt="Featured artwork title"
  width={1200}
  height={800}
  priority // Load immediately, no lazy loading
  placeholder="blur"
  blurDataURL="data:image/jpeg;base64,..."
/>
```

**Lazy Loading (below-the-fold)**:
```tsx
<Image
  src="/gallery-artwork.jpg"
  alt="Artwork description"
  width={600}
  height={400}
  loading="lazy" // Default, but explicit
  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
/>
```

## Preferred Patterns

### Plain img Tags
**What it looks like**: `<img src="/artwork.jpg" />`
**Why wrong**: No automatic optimization, no responsive images, no lazy loading
**Do instead**: `<Image src="/artwork.jpg" width={600} height={400} alt="..." />`

### Missing Alt Text
**What it looks like**: `<Image src="/art.jpg" width={600} height={400} alt="" />`
**Why wrong**: Accessibility violation, poor SEO
**Do instead**: `<Image ... alt="Oil painting of sunset over mountains" />`

### All Images Priority
**What it looks like**: Every Image component has priority={true}
**Why wrong**: Defeats lazy loading, slows initial page load
**Do instead**: Only use priority for above-the-fold hero images

## Anti-Rationalization: Domain-Specific

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "Empty alt text is fine for decorative images" | Portfolio images are content, not decoration | Write descriptive alt text for every artwork |
| "Plain img is simpler than next/image" | No optimization, poor performance | Always use next/image component |
| "All images can be priority loaded" | Defeats lazy loading purpose | Only priority for above-the-fold images |
| "JPEG is good enough" | WebP/AVIF save 30-50% file size | Serve modern formats with fallback |
| "Fixed width is simpler than responsive" | Poor mobile experience | Use sizes prop for responsive images |
| "I'll start with Lorem Ipsum and real images later" | Placeholder content produces placeholder layout decisions | Use the real artwork from day one, even if only a subset |
| "A hero card with the artist name works fine" | Portfolios must show the work first, not metadata about the work | Full-bleed hero with the strongest piece, name goes elsewhere |
| "Three-column grid is the standard for galleries" | It is a cliche that signals template output | Justify the layout from the work; grid is one option among many |
| "Every image hover should have a zoom effect" | Decorative motion competes with the work | Ship one interaction effect for the whole gallery, not per-image flourishes |
| "Two accent colors let me highlight different categories" | Accent colors compete with the artwork | One accent; use typography weight or position for category hierarchy |

## See Also

- `references/lightbox-patterns.md` — complete lightbox implementation with keyboard/touch
- `references/image-optimization.md` — next/image, blur placeholders, WebP/AVIF, format config
- `references/performance.md` — Core Web Vitals, LCP, CLS, INP, bundle size
