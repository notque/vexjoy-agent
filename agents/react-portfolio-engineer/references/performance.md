# Performance Optimization Reference

> **Scope**: Core Web Vitals optimization for portfolio/gallery sites: LCP, CLS, INP targets, bundle analysis, and Next.js-specific strategies.
> **Version range**: Next.js 14+, React 18+
> **Generated**: 2026-04-12 — verify LCP/CLS/INP thresholds against web.dev/vitals

---

## Overview

Portfolio sites are image-heavy by definition, which makes them high-risk for poor Core Web Vitals. The two most impactful metrics are LCP (Largest Contentful Paint — the hero image load time) and CLS (Cumulative Layout Shift — images causing layout jumps before they load). The third metric, INP (Interaction to Next Paint), primarily affects filtering and lightbox open/close interactions. Getting LCP below 2.5s on a portfolio requires correct `priority`, explicit `width/height` on every image, and proper format negotiation.

---

## Pattern Table

| Metric | Good | Needs Improvement | Poor | Primary Cause for Portfolios |
|--------|------|-------------------|------|------------------------------|
| LCP | < 2.5s | 2.5–4.0s | > 4.0s | Hero image not `priority`, wrong `sizes` |
| CLS | < 0.1 | 0.1–0.25 | > 0.25 | Missing width/height on images |
| INP | < 200ms | 200–500ms | > 500ms | Heavy JS on filter interactions |

---

## Correct Patterns

### Priority Loading for Hero Image

The hero image IS the LCP element for portfolio sites. It must be preloaded — `priority` tells Next.js to inject a `<link rel="preload">` in the document head.

```tsx
// app/page.tsx — hero section
import Image from 'next/image'

export default function HomePage() {
  return (
    <section className="hero">
      <Image
        src="/artwork/featured-2024.jpg"
        alt="Featured artwork: oil painting of winter coastline at dusk"
        width={1920}
        height={1080}
        priority           // ← preloads in <head>, critical for LCP
        sizes="100vw"      // hero takes full viewport width
        className="object-cover w-full h-screen"
      />
    </section>
  )
}
```

**Why**: Without `priority`, Next.js lazy-loads the image. For a full-bleed hero, this means the LCP element starts loading only after the page's critical CSS is parsed — typically adding 400-800ms to LCP on mobile.

---

### Explicit Width/Height on Every Gallery Image

Prevents CLS by reserving space before the image loads. The browser calculates the aspect ratio from `width` and `height` and reserves that space immediately.

```tsx
// ✅ Correct: explicit dimensions prevent layout shift
<Image
  src={artwork.src}
  alt={artwork.alt}
  width={600}         // intrinsic pixel dimensions of source image
  height={400}        // NOT display dimensions — use CSS for that
  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
/>

// ❌ Wrong: fill without container dimensions causes CLS
<div>  {/* no height set on container */}
  <Image src={artwork.src} alt={artwork.alt} fill />
</div>
```

**When using `fill`**: The container MUST have `position: relative` and an explicit height (or `aspect-ratio`):

```tsx
<div className="relative aspect-[3/2]">  {/* aspect-ratio reserves space */}
  <Image src={artwork.src} alt={artwork.alt} fill className="object-cover" />
</div>
```

---

### Responsive `sizes` Prop

Without `sizes`, Next.js generates a srcSet but the browser picks the largest size by default. A correct `sizes` string cuts image payload by 50-70% on mobile.

```tsx
// Single-column mobile, two-column tablet, three-column desktop grid
<Image
  src={artwork.src}
  alt={artwork.alt}
  width={600}
  height={400}
  sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
/>

// Full-width hero
<Image ... sizes="100vw" />

// Fixed sidebar thumbnail (never changes size)
<Image ... width={150} height={150} />
// (no sizes needed when dimensions are truly fixed)
```

---

### Route-Level Code Splitting for Heavy Gallery Features

Lightbox libraries and masonry layout engines should not ship on initial load. Use dynamic imports with `ssr: false` for client-only UI.

```tsx
// components/Lightbox.tsx — heavy keyboard/touch handler
import dynamic from 'next/dynamic'

const LightboxModal = dynamic(
  () => import('./LightboxModal'),
  {
    ssr: false,       // Lightbox is client-only
    loading: () => null,  // render nothing while loading (not a spinner — it opens fast)
  }
)

export function Lightbox(props: LightboxProps) {
  return <LightboxModal {...props} />
}
```

**Why**: Lightbox code is only needed after a user clicks. Dynamic import defers its ~15-30KB until interaction, improving initial bundle size and TTI.

---

## Anti-Pattern Catalog

### ❌ Multiple `priority` Images

**Detection**:
```bash
grep -rn "priority" --include="*.tsx" | grep -v "//.*priority"
rg "priority(?:={true})?" --type tsx
```

**What it looks like**:
```tsx
// Every gallery card has priority — defeats the purpose
{artworks.map(art => (
  <Image src={art.src} alt={art.alt} width={600} height={400} priority />
))}
```

**Why wrong**: `priority` injects a `<link rel="preload">` for each image. With 12 gallery items, that's 12 preloads competing for bandwidth at page load. The browser's preload queue is limited; excess preloads are ignored or delay the actual LCP image. Initial page load slows down.

**Fix**: Use `priority` only for the first visible image (hero or first above-fold gallery item). For the rest, use default lazy loading:

```tsx
{artworks.map((art, index) => (
  <Image
    key={art.id}
    src={art.src}
    alt={art.alt}
    width={600}
    height={400}
    priority={index === 0}  // only the first image
  />
))}
```

---

### ❌ Missing `sizes` on Responsive Gallery Images

**Detection**:
```bash
grep -rn "next/image\|from 'next/image'" --include="*.tsx" -l | xargs grep -L "sizes="
rg "width=\{[0-9]+\}.*height=\{[0-9]+\}" --type tsx | grep -v "sizes="
```

**What it looks like**:
```tsx
<Image
  src={artwork.src}
  alt={artwork.alt}
  width={1200}
  height={800}
  // no sizes prop — browser defaults to requesting 1200px image on all viewports
/>
```

**Why wrong**: The browser requests a 1200px image even on a 375px mobile screen. The generated srcSet is useless without a `sizes` hint. A 3-column desktop grid serving 300px thumbnails will download 1200px source images on mobile — typically 4-8x the necessary payload.

**Fix**: Add a `sizes` prop that matches the CSS layout:

```tsx
<Image
  src={artwork.src}
  alt={artwork.alt}
  width={1200}
  height={800}
  sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
/>
```

**Version note**: This applies to all Next.js versions. The default 100vw assumption was introduced intentionally to fail safe (never load too small) but portfolio sites pay the mobile bandwidth cost.

---

### ❌ Synchronous Heavy Computation on Filter Interaction

**Detection**:
```bash
grep -rn "\.filter\(.*\.map\|\.sort\(.*\.filter" --include="*.tsx"
rg "useMemo|useCallback" --type tsx -l
```

**What it looks like**:
```tsx
'use client'
const filtered = artworks
  .filter(a => a.category === activeCategory)
  .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
  .map(a => ({ ...a, formattedDate: formatDate(a.date) }))
// Runs on every render, including every keystroke in a search input
```

**Why wrong**: Synchronous sort + map on 100+ artworks blocks the main thread. INP for the filter interaction will exceed 200ms on mid-range mobile devices. React re-renders include this computation on every state change.

**Fix**: Memoize with `useMemo` and stable dependencies:

```tsx
const filtered = useMemo(() =>
  artworks
    .filter(a => activeCategory === 'all' || a.category === activeCategory)
    .sort((a, b) => b.date.localeCompare(a.date)),
  [artworks, activeCategory]  // only recomputes when these change
)
```

---

### ❌ Importing Full Icon Libraries

**Detection**:
```bash
grep -rn "from 'react-icons'" --include="*.tsx"
grep -rn "from '@heroicons/react'" --include="*.tsx" | grep "^[^/]"
```

**What it looks like**:
```tsx
import { FaArrowLeft, FaArrowRight, FaTimes } from 'react-icons/fa'
// Imports entire react-icons/fa barrel — adds ~50KB to bundle
```

**Why wrong**: Named imports from barrel files like `react-icons/fa` often pull in the entire icon set due to CommonJS export semantics. Even with tree-shaking, some bundler configurations ship the whole 500+ icon set.

**Fix**: Import from the specific icon's module path, or use inline SVGs for a handful of icons:

```tsx
// Option A: path-specific import
import FaArrowLeft from 'react-icons/fa/FaArrowLeft'

// Option B: inline SVG (best for <5 icons in a portfolio lightbox)
export function CloseIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" />
    </svg>
  )
}
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `Image is missing required "width" property` | Using `fill` without container or missing props | Add `width` and `height`, or use `fill` with a positioned container |
| `Error: Image optimization using the default loader is not compatible with next export` | Using `next export` (static HTML) with next/image | Add `unoptimized: true` in next.config.js, or use Vercel/custom loader |
| `Warning: Image with src "X" has "fill" but is missing "sizes" prop` | Next.js 13+ fill images need `sizes` | Add `sizes` matching the layout breakpoints |
| `Hydration failed because the initial UI does not match what was rendered on the server` | Client-only state (lightbox open) rendered in SSR | Move to `useEffect` or use `suppressHydrationWarning` for ephemeral UI state |

---

## Detection Commands Reference

```bash
# Multiple priority images (only first above-fold image should have priority)
grep -rn "priority" --include="*.tsx" app/ components/

# Images missing sizes prop
rg "<Image" --type tsx | grep -v "sizes="

# Heavy filter/sort without memoization
rg "\.filter\(.*\.sort\(" --type tsx | grep -v "useMemo"

# Full icon library barrel imports
grep -rn "from 'react-icons'" --include="*.tsx"

# Plain img tags (should be next/image)
rg "<img " --type tsx | grep -v "// "
```

---

## See Also

- `image-optimization.md` — next/image props, blur placeholders, format config
- `nextjs-app-router.md` — Server vs Client Component split, generateStaticParams
- [web.dev/vitals](https://web.dev/vitals) — current LCP/CLS/INP thresholds and tooling
