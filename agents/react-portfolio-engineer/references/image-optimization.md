# Image Optimization Reference
<!-- Loaded by react-portfolio-engineer when task involves image performance, next/image, formats, or loading strategies -->

## next/image Core Configuration

Every portfolio image uses `next/image`. It handles format negotiation (WebP/AVIF), responsive sizing, and lazy loading automatically.

```tsx
<Image
  src="/artwork/oil-on-canvas-2024.jpg"
  alt="Oil painting: autumn forest with morning light filtering through birch trees"
  width={1200}
  height={800}
/>
```

Automatic: WebP for supporting browsers, responsive `srcSet` from `sizes`, lazy loading (unless `priority`), CLS prevention via reserved space.

---

## WebP/AVIF Format Negotiation

```javascript
// next.config.js
const nextConfig = {
  images: {
    formats: ['image/avif', 'image/webp'], // AVIF first (~50% smaller than JPEG), WebP fallback (~30%)
  },
}
```

---

## Blur Placeholders

### Static (build-time, local images)
```tsx
<Image src="/portrait.jpg" alt="Portrait" width={800} height={1200}
  placeholder="blur" blurDataURL="data:image/jpeg;base64,/9j/4AAQ..." />
```

### Dynamic (CMS/remote images)
```tsx
import { getPlaiceholder } from 'plaiceholder'

export async function getBlurData(src: string) {
  const buffer = await fetch(src).then(r => r.arrayBuffer()).then(Buffer.from)
  const { base64, metadata } = await getPlaiceholder(buffer)
  return { blurDataURL: base64, width: metadata.width, height: metadata.height }
}
```

Call during `generateStaticParams` or in Server Components.

---

## Responsive Images with `sizes`

Without `sizes`, next/image assumes full viewport width — wasteful on mobile.

```tsx
// Gallery: 2 columns mobile, 3 tablet, 4 desktop
<Image src={image.src} alt={image.alt} fill
  sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 25vw" />

// Hero: full width
<Image ... priority sizes="100vw" />

// Fixed thumbnail
<Image ... width={200} height={200} sizes="200px" />
```

Correct `sizes` reduces mobile downloads by 50-75%.

---

## Priority Loading (Above the Fold)

```tsx
<Image src="/hero.jpg" alt="Featured work" width={1920} height={1080}
  priority sizes="100vw" />

{images.map((image, index) => (
  <Image key={image.id} src={image.src} alt={image.alt} width={600} height={600}
    priority={index < 2} sizes="(max-width: 768px) 50vw, 25vw" />
))}
```

Only first 1-2 visible images. Setting `priority` on all defeats lazy loading.

---

## Art Direction (Different Images per Breakpoint)

Only when composition requires different crops per viewport:

```tsx
<picture>
  <source media="(min-width: 768px)" srcSet={landscape.src} type="image/webp" />
  <source media="(max-width: 767px)" srcSet={portrait.src} type="image/webp" />
  <img src={landscape.src} alt={landscape.alt} className="w-full h-auto" />
</picture>
```

Most images benefit more from correct `sizes` + `fill`.

---

## Remote Image Configuration

```javascript
// next.config.js
const nextConfig = {
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'cdn.sanity.io', pathname: '/images/**' },
      { protocol: 'https', hostname: 'images.unsplash.com' },
    ],
    formats: ['image/avif', 'image/webp'],
  },
}
```

Use `remotePatterns`, not `domains` (deprecated 13+, removed 15+).

---

## Image Quality Settings

Default quality 75 is fine for thumbnails. Use 85-90 for fine art hero/lightbox:

```tsx
<Image src="/watercolor-detail.jpg" alt="Watercolor detail" width={2400} height={1600}
  quality={90} sizes="(max-width: 1024px) 100vw, 80vw" />
```
