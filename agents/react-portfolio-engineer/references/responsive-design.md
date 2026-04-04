# Responsive Design Reference
<!-- Loaded by react-portfolio-engineer when task involves breakpoints, mobile layout, fluid typography, or touch interactions -->

Mobile-first responsive design means starting from the smallest screen and layering in enhancements. Portfolio sites live or die on mobile — most visitors arrive from social media on phones.

## Mobile-First Breakpoints
**When to use:** Every layout. Write base styles for mobile, add breakpoint modifiers for larger screens.

Tailwind's default scale works well for portfolios:

```
sm:  640px   — large phones, small tablets in portrait
md:  768px   — tablets in portrait, large phones landscape
lg:  1024px  — tablets in landscape, small laptops
xl:  1280px  — desktops
2xl: 1536px  — large monitors (rarely needed for portfolios)
```

```tsx
// Gallery grid — 1 column on mobile, scales up
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 md:gap-4 lg:gap-6">
  {images.map(img => <GalleryCard key={img.id} image={img} />)}
</div>
```

```tsx
// Navigation — stacked on mobile, horizontal on desktop
<nav className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-6">
  <a href="/work">Work</a>
  <a href="/about">About</a>
  <a href="/contact">Contact</a>
</nav>
```

---

## Fluid Typography
**When to use:** Headings and display text that should scale smoothly between mobile and desktop without abrupt jumps.

CSS `clamp()` creates a fluid range between a minimum and maximum:

```css
/* clamp(minimum, preferred, maximum) */
/* preferred = viewport-relative unit that scales between min and max */

.heading-hero {
  font-size: clamp(2rem, 5vw + 1rem, 4.5rem);
  /* mobile: ~2rem, scales up, desktop: max 4.5rem */
}

.heading-section {
  font-size: clamp(1.5rem, 3vw + 0.75rem, 3rem);
}

.body-copy {
  font-size: clamp(1rem, 1vw + 0.875rem, 1.25rem);
}
```

Tailwind equivalent using arbitrary values:

```tsx
<h1 className="text-[clamp(2rem,5vw+1rem,4.5rem)] font-bold leading-tight">
  Featured Work
</h1>
```

**Instead of:** Separate font sizes for every breakpoint with `text-2xl md:text-3xl lg:text-4xl xl:text-5xl` — produces visible jumps at each breakpoint. `clamp()` interpolates smoothly.

---

## Container Queries
**When to use:** Gallery cards or sidebar components that need to respond to their container width, not the viewport. Particularly useful when the same card component appears in both a 3-column grid and a 1-column list.

```tsx
// Enable container queries on the parent
<div className="@container grid grid-cols-1 md:grid-cols-3 gap-4">
  {images.map(img => (
    <div key={img.id} className="@container">
      {/* Card responds to its own width, not the viewport */}
      <div className="flex flex-col @[300px]:flex-row gap-3">
        <Image src={img.src} alt={img.alt} width={200} height={200} />
        <div>
          <h3 className="text-sm @[300px]:text-base font-medium">{img.title}</h3>
          <p className="hidden @[300px]:block text-sm text-gray-600">{img.description}</p>
        </div>
      </div>
    </div>
  ))}
</div>
```

Requires `@tailwindcss/container-queries` plugin:

```javascript
// tailwind.config.js
module.exports = {
  plugins: [require('@tailwindcss/container-queries')],
}
```

---

## Aspect Ratios for Galleries
**When to use:** Gallery grids where images have varying source dimensions. Enforcing a consistent aspect ratio creates visual rhythm regardless of original proportions.

```tsx
// Square grid (Instagram-style)
<div className="aspect-square relative overflow-hidden">
  <Image src={img.src} alt={img.alt} fill className="object-cover" />
</div>

// 4:3 landscape (photography-friendly)
<div className="aspect-[4/3] relative overflow-hidden">
  <Image src={img.src} alt={img.alt} fill className="object-cover" />
</div>

// 2:3 portrait (fashion/portrait photography)
<div className="aspect-[2/3] relative overflow-hidden">
  <Image src={img.src} alt={img.alt} fill className="object-cover" />
</div>

// Masonry alternative: preserve original aspect ratio
// Use this when the artwork's proportions matter (paintings, prints)
<div style={{ aspectRatio: `${img.width} / ${img.height}` }} className="relative overflow-hidden">
  <Image src={img.src} alt={img.alt} fill className="object-contain" />
</div>
```

---

## Touch Targets
**When to use:** All interactive elements on mobile. WCAG 2.5.5 requires 44x44px minimum touch targets.

```tsx
// Gallery filter buttons — adequate touch target
<button className="min-h-[44px] min-w-[44px] px-4 py-2 rounded-full text-sm font-medium">
  Paintings
</button>

// Lightbox navigation — large touch area, even if visual icon is small
<button
  aria-label="Next image"
  className="absolute right-0 top-0 h-full w-16 flex items-center justify-center"
>
  {/* icon is small but the button hitbox spans the right edge */}
  <svg className="w-8 h-8" .../>
</button>

// Thumbnail grid — ensure the button wrapping each image meets minimum size
<button
  className="relative block w-full aspect-square min-h-[44px]"
  aria-label={`View: ${image.alt}`}
>
  <Image src={image.src} alt={image.alt} fill className="object-cover" />
</button>
```

**Instead of:** Small icon-only buttons without padding — `<button className="p-1">` creates a ~24px target that's hard to tap accurately.

---

## Responsive Image Sizes for Gallery Layouts
**When to use:** Whenever using `next/image` in a grid. The `sizes` prop must match the actual rendered width at each breakpoint.

```tsx
// 2-col mobile, 3-col tablet, 4-col desktop with gap
<Image
  src={img.src}
  alt={img.alt}
  fill
  sizes={[
    '(max-width: 639px) calc(50vw - 12px)',   // 2-col, subtract gap
    '(max-width: 1023px) calc(33vw - 16px)',  // 3-col, subtract gap
    'calc(25vw - 18px)',                       // 4-col, subtract gap
  ].join(', ')}
  className="object-cover"
/>
```

Subtracting gap from vw produces more accurate srcSet selection, preventing the browser from fetching slightly-too-large images.

---

## Mobile Navigation Patterns
**When to use:** Portfolio sites with more than 3-4 navigation links.

```tsx
'use client'
import { useState } from 'react'

export function MobileNav({ links }: { links: Array<{ href: string; label: string }> }) {
  const [open, setOpen] = useState(false)

  return (
    <nav aria-label="Main navigation">
      {/* Mobile: hamburger toggle */}
      <button
        className="sm:hidden min-h-[44px] min-w-[44px] flex items-center justify-center"
        aria-expanded={open}
        aria-controls="mobile-menu"
        aria-label={open ? 'Close menu' : 'Open menu'}
        onClick={() => setOpen(o => !o)}
      >
        {/* icon */}
      </button>

      {/* Mobile: slide-down menu */}
      <ul
        id="mobile-menu"
        className={`sm:hidden flex flex-col gap-1 ${open ? 'block' : 'hidden'}`}
      >
        {links.map(link => (
          <li key={link.href}>
            <a href={link.href} className="block py-3 px-4 min-h-[44px]">
              {link.label}
            </a>
          </li>
        ))}
      </ul>

      {/* Desktop: always visible */}
      <ul className="hidden sm:flex gap-6">
        {links.map(link => (
          <li key={link.href}>
            <a href={link.href}>{link.label}</a>
          </li>
        ))}
      </ul>
    </nav>
  )
}
```
