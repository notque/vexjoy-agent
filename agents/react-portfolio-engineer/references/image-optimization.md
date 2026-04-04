# Image Optimization Reference
<!-- Loaded by react-portfolio-engineer when task involves image performance, next/image, formats, or loading strategies -->

Proper image optimization is the single highest-leverage performance change for portfolio sites. The gap between an unoptimized JPEG and a correctly configured next/image component is typically 60-80% in payload size.

## next/image Core Configuration
**When to use:** Every portfolio image, without exception.

The `next/image` component handles format negotiation (WebP/AVIF), responsive sizing, and lazy loading automatically — but only if configured correctly.

```tsx
import Image from 'next/image'

<Image
  src="/artwork/oil-on-canvas-2024.jpg"
  alt="Oil painting: autumn forest with morning light filtering through birch trees"
  width={1200}   // intrinsic width of the source image
  height={800}   // intrinsic height of the source image
/>
```

**What next/image does automatically:**
- Serves WebP to browsers that support it, JPEG as fallback
- Generates responsive `srcSet` based on `sizes` prop
- Applies lazy loading (except when `priority` is set)
- Prevents cumulative layout shift (CLS) via reserved space

---

## WebP/AVIF Format Negotiation
**When to use:** Always — automatic with next/image but requires correct `next.config.js`.

```javascript
// next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    formats: ['image/avif', 'image/webp'], // AVIF first (smaller), WebP fallback
  },
}

module.exports = nextConfig
```

AVIF achieves ~50% smaller files than JPEG at equivalent quality. WebP achieves ~30%.

**Instead of:** Manually converting images to WebP before deploying — next/image handles this at the CDN/cache layer, and static pre-conversion locks you into one format.

---

## Blur Placeholders
**When to use:** Every gallery image, especially on slower connections. The blur-up effect signals content is loading rather than broken.

### Static blur (build-time, preferred for local images)

```tsx
const BLUR_DATA_URL = 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD...'

<Image
  src="/artwork/portrait.jpg"
  alt="Portrait: woman reading in afternoon light"
  width={800}
  height={1200}
  placeholder="blur"
  blurDataURL={BLUR_DATA_URL}
/>
```

### Dynamic blur (for CMS or remote images)

```tsx
// lib/blur.ts
import { getPlaiceholder } from 'plaiceholder'

interface BlurResult {
  blurDataURL: string
  width: number
  height: number
}

export async function getBlurData(src: string): Promise<BlurResult> {
  const buffer = await fetch(src).then(r => r.arrayBuffer()).then(Buffer.from)
  const { base64, metadata } = await getPlaiceholder(buffer)
  return {
    blurDataURL: base64,
    width: metadata.width,
    height: metadata.height,
  }
}
```

Call during `generateStaticParams` or in a Server Component to pre-compute blur data at build time.

---

## Responsive Images with `sizes`
**When to use:** Any image that changes width at different viewport breakpoints. Without `sizes`, next/image assumes full viewport width — generating unnecessarily large files for mobile.

```tsx
// Gallery thumbnail: 2 columns mobile, 3 tablet, 4 desktop
<Image
  src={image.src}
  alt={image.alt}
  fill
  sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 25vw"
  className="object-cover"
/>

// Hero image: always full width
<Image
  src={hero.src}
  alt={hero.alt}
  width={1920}
  height={1080}
  priority
  sizes="100vw"
/>

// Sidebar thumbnail: fixed 200px regardless of viewport
<Image
  src={thumb.src}
  alt={thumb.alt}
  width={200}
  height={200}
  sizes="200px"
/>
```

Correct `sizes` can reduce mobile image download sizes by 50-75% versus the default 100vw assumption.

---

## Priority Loading (Above the Fold)
**When to use:** The first visible image on any page — typically a hero or the first 1-2 gallery items.

```tsx
// Hero image — always priority
<Image
  src="/hero.jpg"
  alt="Featured work: large-scale installation at the Whitechapel Gallery"
  width={1920}
  height={1080}
  priority  // disables lazy loading, adds <link rel="preload">
  sizes="100vw"
/>

// First gallery row — first 2 can benefit from priority
{images.map((image, index) => (
  <Image
    key={image.id}
    src={image.src}
    alt={image.alt}
    width={600}
    height={600}
    priority={index < 2}
    sizes="(max-width: 768px) 50vw, 25vw"
  />
))}
```

**Instead of:** Setting `priority` on all images — defeats lazy loading, blocks bandwidth for above-fold content, and worsens LCP.

---

## Lazy Loading (Below the Fold)
**When to use:** Everything not immediately visible. This is the default — no explicit configuration needed.

```tsx
// Default behavior — lazy loaded automatically
<Image
  src="/gallery/piece-12.jpg"
  alt="Sculpture: cast bronze, 2023"
  width={600}
  height={800}
  // No priority prop = lazy by default
  sizes="(max-width: 768px) 100vw, 50vw"
/>
```

---

## Art Direction (Different Images per Breakpoint)
**When to use:** When the composition only works at certain aspect ratios — landscape crop for desktop, portrait crop for mobile.

```tsx
export function ArtDirectedHero({ landscape, portrait }: {
  landscape: { src: string; alt: string }
  portrait: { src: string; alt: string }
}) {
  return (
    <picture>
      <source
        media="(min-width: 768px)"
        srcSet={landscape.src}
        type="image/webp"
      />
      <source
        media="(max-width: 767px)"
        srcSet={portrait.src}
        type="image/webp"
      />
      <img
        src={landscape.src}
        alt={landscape.alt}
        className="w-full h-auto"
      />
    </picture>
  )
}
```

Only use art direction when genuinely needed. Most gallery images benefit more from correct `sizes` + `fill`.

---

## Remote Image Configuration
**When to use:** Images served from a CDN, Sanity, Cloudinary, or any external origin.

```javascript
// next.config.js
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'cdn.sanity.io',
        pathname: '/images/**',
      },
      {
        protocol: 'https',
        hostname: 'images.unsplash.com',
      },
    ],
    formats: ['image/avif', 'image/webp'],
  },
}
```

**Instead of:** Using `domains` (deprecated in Next.js 13+, removed in 15+) instead of `remotePatterns`.

---

## Image Quality Settings
**When to use:** When default quality (75) is too aggressive for fine art requiring accurate color reproduction.

```tsx
<Image
  src="/artwork/watercolor-detail.jpg"
  alt="Watercolor detail: translucent washes in cerulean and burnt sienna"
  width={2400}
  height={1600}
  quality={90}  // default is 75; use 85-90 for fine art lightbox views
  sizes="(max-width: 1024px) 100vw, 80vw"
/>
```

Higher quality = larger file. Use 85-90 for hero/lightbox images, keep 75 for thumbnails.
