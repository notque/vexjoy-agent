# Next.js App Router Reference

> **Scope**: App Router patterns specific to portfolio/gallery sites: Server vs Client components, metadata API, static generation, and data fetching.
> **Version range**: Next.js 13.4+ (App Router stable), 14+ (recommended)
> **Generated**: 2026-04-12 — verify against Next.js changelog for latest changes

---

## Overview

Portfolio sites built with Next.js App Router should default to Server Components for all static content (gallery grids, about pages, artwork metadata) and use Client Components only for interactive elements (lightbox, filtering UI, touch gestures). The most common failure mode is marking entire page trees as `'use client'` — this disables static generation and ships full JavaScript bundles for content that needs none.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `generateStaticParams` | 13.4+ | Gallery pages with known slugs | Dynamic content from user input |
| `generateMetadata` | 13.4+ | Per-artwork SEO titles/OG images | Static metadata for all pages |
| `export const dynamic = 'force-static'` | 13.4+ | Page must never run server-side | Page reads cookies/headers |
| `<Suspense>` with `loading.tsx` | 13.4+ | Data fetching in Server Components | Wrapping non-async content |
| `unstable_cache` | 14.0+ | Repeated CMS/API fetches per build | One-off requests |

---

## Correct Patterns

### Server Component for Gallery Grid

Gallery grids render the same content for all visitors. Use a Server Component: no `'use client'`, data fetch directly in the component, no bundle cost.

```tsx
// app/gallery/page.tsx — Server Component (no 'use client')
import { GalleryGrid } from '@/components/GalleryGrid'
import { getArtworks } from '@/lib/artworks'

export default async function GalleryPage() {
  const artworks = await getArtworks() // runs at build time (SSG)
  return <GalleryGrid artworks={artworks} />
}

// GalleryGrid can also be a Server Component if it has no event handlers
// components/GalleryGrid.tsx
import Image from 'next/image'

export function GalleryGrid({ artworks }: { artworks: Artwork[] }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {artworks.map(art => (
        <Image
          key={art.id}
          src={art.src}
          alt={art.alt}
          width={600}
          height={400}
          sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
        />
      ))}
    </div>
  )
}
```

**Why**: Server Components ship zero JavaScript for the component itself. A gallery grid serving 50 artworks with plain img tags still renders as static HTML.

---

### Isolate Interactivity at the Leaf

Client Components should be small, leaf nodes. Hoist `'use client'` as deep as possible to preserve static generation of parent content.

```tsx
// ✅ Correct: only the lightbox trigger is a Client Component
// components/ArtworkCard.tsx — Server Component
import { LightboxTrigger } from './LightboxTrigger' // Client Component

export function ArtworkCard({ artwork }: { artwork: Artwork }) {
  return (
    <article>
      <Image src={artwork.src} alt={artwork.alt} width={600} height={400} />
      <h2>{artwork.title}</h2>
      <LightboxTrigger artworkId={artwork.id} /> {/* Only interactive part */}
    </article>
  )
}

// components/LightboxTrigger.tsx
'use client'
import { useLightbox } from '@/hooks/useLightbox'

export function LightboxTrigger({ artworkId }: { artworkId: string }) {
  const { open } = useLightbox()
  return (
    <button onClick={() => open(artworkId)} aria-label="View full size">
      Expand
    </button>
  )
}
```

---

### Per-Artwork Metadata with generateMetadata

Each artwork detail page should have unique title and OG image for social sharing.

```tsx
// app/gallery/[slug]/page.tsx
import { getArtworkBySlug } from '@/lib/artworks'
import type { Metadata } from 'next'

export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  const artwork = await getArtworkBySlug(params.slug)
  return {
    title: `${artwork.title} — Portfolio`,
    description: artwork.description,
    openGraph: {
      images: [{ url: artwork.src, width: 1200, height: 630 }],
    },
  }
}

export async function generateStaticParams() {
  const artworks = await getArtworkBySlug('*') // get all slugs
  return artworks.map(art => ({ slug: art.slug }))
}
```

---

## Anti-Pattern Catalog

### ❌ Marking the Whole Page as Client Component

**Detection**:
```bash
grep -rn "'use client'" app/ --include="*.tsx" | grep "page.tsx"
rg "'use client'" --type tsx -l | xargs grep -l "export default function"
```

**What it looks like**:
```tsx
// app/gallery/page.tsx
'use client'  // ← entire page becomes a Client Component
import { useState } from 'react'
import Image from 'next/image'
import { artworks } from '@/data/artworks'

export default function GalleryPage() {
  const [filter, setFilter] = useState('all')
  // ...gallery rendering with Image components
}
```

**Why wrong**: The entire gallery tree becomes client-rendered JavaScript. Static generation is disabled — Next.js must rerun the page on every request. Images lose build-time optimization hints. Bundle size includes all artwork metadata in the initial JS payload.

**Fix**: Extract `useState` filtering into a `FilterBar` Client Component. Keep `GalleryPage` as a Server Component that passes artworks down.

```tsx
// app/gallery/page.tsx — Server Component
import { FilterBar } from '@/components/FilterBar' // 'use client'
import { artworks } from '@/data/artworks'

export default function GalleryPage() {
  return <FilterBar artworks={artworks} /> // FilterBar handles state internally
}
```

---

### ❌ Using useRouter for Category Filtering Instead of URL Search Params

**Detection**:
```bash
grep -rn "useRouter\|router.push" --include="*.tsx" app/
rg "setFilter\|activeFilter" --type tsx
```

**What it looks like**:
```tsx
'use client'
const [activeCategory, setActiveCategory] = useState('all')
// Filter applied in memory, URL does not reflect state
```

**Why wrong**: Filtering state disappears on page refresh. Users cannot share links to specific gallery categories. Back button loses filter context. Browser history is not updated.

**Fix**: Use `useSearchParams` + `useRouter` to sync filter with URL:

```tsx
'use client'
import { useSearchParams, useRouter } from 'next/navigation'

export function FilterBar({ categories }: { categories: string[] }) {
  const searchParams = useSearchParams()
  const router = useRouter()
  const active = searchParams.get('category') ?? 'all'

  const setFilter = (cat: string) => {
    const params = new URLSearchParams(searchParams)
    if (cat === 'all') params.delete('category')
    else params.set('category', cat)
    router.push(`?${params.toString()}`, { scroll: false })
  }

  return (
    <nav>
      {['all', ...categories].map(cat => (
        <button key={cat} onClick={() => setFilter(cat)}
          aria-current={active === cat ? 'true' : undefined}>
          {cat}
        </button>
      ))}
    </nav>
  )
}
```

**Version note**: `useSearchParams` requires a `<Suspense>` boundary in Next.js 14+. Wrap the component in `<Suspense>` or use the `params` prop from the page.

---

### ❌ Calling getServerSideProps in App Router Pages

**Detection**:
```bash
grep -rn "getServerSideProps\|getStaticProps" app/ --include="*.tsx"
```

**What it looks like**:
```tsx
// app/gallery/page.tsx — WRONG in App Router
export async function getStaticProps() { ... }
export async function getServerSideProps() { ... }
```

**Why wrong**: These are Pages Router APIs. In App Router they are silently ignored — the functions exist but never run. Data fetching must happen in the `async` component body directly.

**Fix**: Fetch data directly in the async Server Component:

```tsx
export default async function GalleryPage() {
  const artworks = await fetch('https://api.example.com/artworks').then(r => r.json())
  return <GalleryGrid artworks={artworks} />
}
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `Error: useState is not a function` in Server Component | `useState` imported in non-'use client' file | Add `'use client'` to the file or extract hook to a Client Component |
| `Error: useSearchParams() should be wrapped in a suspense boundary` | Next.js 14 requires Suspense for useSearchParams | Wrap with `<Suspense fallback={null}>` |
| `Warning: Each child in a list should have a unique "key" prop` | Missing `key` on mapped artwork elements | Add `key={artwork.id}` to mapped Image/article elements |
| `Image with src "..." was detected as the Largest Contentful Paint` without `priority` | Hero image not marked as priority | Add `priority` prop to the first visible Image |
| `next/image Un-configured Host` | External image domain not in next.config.js | Add domain to `images.domains` or `images.remotePatterns` |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| 13.4 | App Router stable; `generateStaticParams` replaces `getStaticPaths` | Portfolio pages should migrate from Pages Router |
| 14.0 | `useSearchParams` requires Suspense boundary | Wrap all filter components in Suspense |
| 14.1 | `unstable_cache` added for deduplicating CMS fetches | Use for Sanity/Contentful per-build calls |
| 15.0 | Partial Prerendering (PPR) experimental; static shell + dynamic holes | Useful for galleries with analytics-driven "popular" sections |

---

## Detection Commands Reference

```bash
# Pages incorrectly marked as Client Components
grep -rn "'use client'" app/ --include="*.tsx" | grep "page.tsx"

# Legacy Pages Router APIs used in App Router
grep -rn "getServerSideProps\|getStaticProps" app/ --include="*.tsx"

# useState-based category filter (should be URL search params)
rg "useState.*category|useState.*filter" --type tsx

# Missing Suspense around useSearchParams (Next.js 14+)
grep -rn "useSearchParams" --include="*.tsx" | grep -v "Suspense"
```

---

## See Also

- `image-optimization.md` — next/image props, WebP/AVIF config, blur placeholders
- `performance.md` — Core Web Vitals, LCP optimization, bundle analysis
