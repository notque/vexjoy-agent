# Gallery Patterns

Component patterns for React portfolio galleries.

## Image Gallery with Filtering

```tsx
'use client'
import { useState } from 'react'
import Image from 'next/image'

export function Gallery({ images, categories }) {
  const [filter, setFilter] = useState('all')
  const filtered = filter === 'all' ? images : images.filter(img => img.category === filter)

  return (
    <div>
      <CategoryFilter categories={categories} active={filter} onChange={setFilter} />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map(image => <ImageCard key={image.id} image={image} />)}
      </div>
    </div>
  )
}
```

## Next.js Image Quick Reference

**Priority (above-fold)**:
```tsx
<Image src="/hero.jpg" alt="Featured artwork" width={1200} height={800}
  priority placeholder="blur" blurDataURL="data:image/jpeg;base64,..." />
```

**Lazy (below-fold)**:
```tsx
<Image src="/gallery.jpg" alt="Artwork description" width={600} height={400}
  loading="lazy" sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw" />
```

## Preferred Patterns

### Plain img Tags
`<img src="/artwork.jpg" />` — No optimization, no responsive images, no lazy loading.
**Do instead**: `<Image src="/artwork.jpg" width={600} height={400} alt="..." />`

### Missing Alt Text
`alt=""` — Accessibility violation, poor SEO.
**Do instead**: `alt="Oil painting of sunset over mountains"`

### All Images Priority
Every Image with `priority={true}` defeats lazy loading.
**Do instead**: Only priority for above-fold hero images.

## Anti-Rationalization

| Rationalization | Required Action |
|----------------|-----------------|
| "Empty alt is fine for decorative images" | Portfolio images are content — write descriptive alt |
| "Plain img is simpler" | Always use next/image |
| "All images can be priority" | Only priority for above-fold |
| "JPEG is good enough" | Serve WebP/AVIF with fallback |
| "Fixed width is simpler" | Use sizes prop for responsive |
| "Start with Lorem Ipsum" | Use real artwork from day one |
| "Hero card with artist name works" | Full-bleed hero with strongest piece |
| "Three-column grid is standard" | Justify layout from the work |
| "Every hover should zoom" | One interaction effect for the whole gallery |
| "Two accent colors for categories" | One accent; use typography for hierarchy |

## See Also

- `lightbox-patterns.md` — lightbox with keyboard/touch
- `image-optimization.md` — next/image, blur, WebP/AVIF
- `performance.md` — Core Web Vitals, LCP, CLS, INP
