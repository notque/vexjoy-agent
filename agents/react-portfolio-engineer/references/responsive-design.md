# Responsive Design Reference
<!-- Loaded by react-portfolio-engineer when task involves breakpoints, mobile layout, fluid typography, or touch interactions -->

## Mobile-First Breakpoints

```
sm: 640px    md: 768px    lg: 1024px    xl: 1280px    2xl: 1536px
```

```tsx
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 md:gap-4 lg:gap-6">
  {images.map(img => <GalleryCard key={img.id} image={img} />)}
</div>
```

---

## Fluid Typography

`clamp()` scales smoothly between mobile and desktop without breakpoint jumps.

```css
.heading-hero { font-size: clamp(2rem, 5vw + 1rem, 4.5rem); }
.heading-section { font-size: clamp(1.5rem, 3vw + 0.75rem, 3rem); }
.body-copy { font-size: clamp(1rem, 1vw + 0.875rem, 1.25rem); }
```

Tailwind: `className="text-[clamp(2rem,5vw+1rem,4.5rem)]"`

---

## Container Queries

For components that respond to container width, not viewport. Same card in 3-col grid and 1-col list.

```tsx
<div className="@container grid grid-cols-1 md:grid-cols-3 gap-4">
  <div className="@container">
    <div className="flex flex-col @[300px]:flex-row gap-3">
      <Image ... />
      <div>
        <h3 className="text-sm @[300px]:text-base">{img.title}</h3>
        <p className="hidden @[300px]:block text-sm">{img.description}</p>
      </div>
    </div>
  </div>
</div>
```

Requires `@tailwindcss/container-queries` plugin.

---

## Aspect Ratios for Galleries

```tsx
// Square grid
<div className="aspect-square relative overflow-hidden">
  <Image src={img.src} alt={img.alt} fill className="object-cover" />
</div>

// 4:3 landscape
<div className="aspect-[4/3] relative overflow-hidden">...</div>

// Preserve original (paintings, prints)
<div style={{ aspectRatio: `${img.width} / ${img.height}` }} className="relative overflow-hidden">
  <Image ... fill className="object-contain" />
</div>
```

---

## Touch Targets

WCAG 2.5.5: minimum 44x44px touch targets.

```tsx
<button className="min-h-[44px] min-w-[44px] px-4 py-2 rounded-full">Paintings</button>

// Lightbox nav: large hitbox, small icon
<button aria-label="Next image" className="absolute right-0 top-0 h-full w-16 flex items-center justify-center">
  <svg className="w-8 h-8" .../>
</button>
```

---

## Responsive Image Sizes for Grids

`sizes` must match actual rendered width at each breakpoint:

```tsx
<Image ... fill sizes={[
  '(max-width: 639px) calc(50vw - 12px)',
  '(max-width: 1023px) calc(33vw - 16px)',
  'calc(25vw - 18px)',
].join(', ')} />
```

Subtracting gap from vw prevents fetching slightly-too-large images.

---

## Mobile Navigation

```tsx
'use client'
export function MobileNav({ links }) {
  const [open, setOpen] = useState(false)
  return (
    <nav aria-label="Main navigation">
      <button className="sm:hidden min-h-[44px] min-w-[44px]"
        aria-expanded={open} aria-controls="mobile-menu"
        aria-label={open ? 'Close menu' : 'Open menu'}
        onClick={() => setOpen(o => !o)} />

      <ul id="mobile-menu" className={`sm:hidden flex flex-col gap-1 ${open ? 'block' : 'hidden'}`}>
        {links.map(link => (
          <li key={link.href}><a href={link.href} className="block py-3 px-4 min-h-[44px]">{link.label}</a></li>
        ))}
      </ul>

      <ul className="hidden sm:flex gap-6">
        {links.map(link => <li key={link.href}><a href={link.href}>{link.label}</a></li>)}
      </ul>
    </nav>
  )
}
```
