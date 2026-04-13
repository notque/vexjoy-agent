# Next.js App Router Reference

> **Scope**: Server/Client Component split, App Router layouts, metadata API, and loading patterns for portfolio sites. Does NOT cover Pages Router or Webpack config.
> **Version range**: Next.js 13.4+ (App Router stable), 14.x, 15.x
> **Generated**: 2026-04-13 — verify against Next.js release notes for current stable

---

## Overview

Portfolio sites built on the App Router split rendering responsibilities cleanly: static gallery pages rendered on the server, interactive lightbox and filtering logic isolated to Client Components. Getting this boundary wrong causes hydration mismatches or unnecessary client-side JS for purely static content.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `'use client'` directive | 13.4+ | useState, useEffect, event handlers | Data fetching, static layout, metadata |
| `generateStaticParams` | 13.4+ | Static routes for each artwork/category | Dynamic user-generated routes |
| `generateMetadata` | 13.4+ | Per-page Open Graph and title | Static metadata object sufficient |
| `loading.tsx` | 13.4+ | Route-level skeleton during navigation | Component-level loading (use Suspense instead) |
| `Suspense` boundary | 18+ | Streaming individual gallery sections | Full-page blocking loads |
| `unstable_cache` | 14.0+ | Caching external CMS fetches | In-memory data that doesn't need revalidation |

---

## Correct Patterns

### Server/Client Component Split for Galleries

The gallery data fetch belongs on the server; the filtering interaction belongs on the client. Keep them separate.

```tsx
// app/gallery/page.tsx — Server Component (no 'use client')
import { GalleryGrid } from '@/components/GalleryGrid'
import { getArtworks } from '@/lib/data'

export default async function GalleryPage() {
  const artworks = await getArtworks() // runs on server, no client JS
  return <GalleryGrid artworks={artworks} />
}
```

```tsx
// components/GalleryGrid.tsx — Client Component (needs useState for filter)
'use client'
import { useState } from 'react'
import Image from 'next/image'

export function GalleryGrid({ artworks }: { artworks: Artwork[] }) {
  const [filter, setFilter] = useState<string>('all')
  const visible = filter === 'all' ? artworks : artworks.filter(a => a.category === filter)
  return (/* grid JSX */)
}
```

**Why**: Server Components have zero client-side JS overhead. Fetching data in a Server Component eliminates a network waterfall (no fetch-on-mount after hydration).

---

### Metadata API for Portfolio Pages

Use `generateMetadata` for dynamic artwork pages; use the static `metadata` export for fixed pages.

```tsx
// app/gallery/[slug]/page.tsx
import type { Metadata } from 'next'

// Static page (e.g., /about)
export const metadata: Metadata = {
  title: 'Artist Portfolio | About',
  description: 'About the artist and their practice.',
  openGraph: {
    type: 'website',
    images: [{ url: '/og-default.jpg', width: 1200, height: 630 }],
  },
}

// Dynamic page — per-artwork metadata
export async function generateMetadata(
  { params }: { params: { slug: string } }
): Promise<Metadata> {
  const artwork = await getArtwork(params.slug)
  return {
    title: `${artwork.title} | Artist Portfolio`,
    description: artwork.description,
    openGraph: {
      type: 'article',
      images: [{ url: artwork.imageUrl, width: artwork.width, height: artwork.height }],
    },
  }
}
```

**Why**: `generateMetadata` runs server-side and resolves before the page streams, so crawlers always see full metadata even for dynamic routes.

---

### `generateStaticParams` for Gallery Routes

Pre-render each artwork detail page at build time — no server needed at runtime.

```tsx
// app/gallery/[slug]/page.tsx
export async function generateStaticParams() {
  const artworks = await getArtworks()
  return artworks.map(artwork => ({ slug: artwork.slug }))
}

// This makes every artwork page static HTML at build time
export default async function ArtworkPage({ params }: { params: { slug: string } }) {
  const artwork = await getArtwork(params.slug)
  return <ArtworkDetail artwork={artwork} />
}
```

**Why**: Static pages serve from CDN edge nodes. For a portfolio with stable content, `generateStaticParams` eliminates server compute per request and achieves sub-50ms TTFB.

---

### Streaming Gallery Sections with Suspense

Stream expensive gallery sections independently rather than blocking the full page.

```tsx
// app/gallery/page.tsx
import { Suspense } from 'react'
import { GalleryGrid } from '@/components/GalleryGrid'
import { GallerySkeleton } from '@/components/GallerySkeleton'

export default function GalleryPage() {
  return (
    <main>
      <HeroSection /> {/* renders immediately */}
      <Suspense fallback={<GallerySkeleton />}>
        <GalleryGrid /> {/* streams when ready */}
      </Suspense>
    </main>
  )
}
```

**Why**: The hero (above-fold) paints instantly. The gallery data fetches concurrently without blocking the hero. Reduces perceived load time without requiring client-side state.

---

### Layout Nesting for Portfolio Structure

Use nested layouts to share headers, footers, and navigation across sections without re-mounting.

```tsx
// app/layout.tsx — root layout (applies everywhere)
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <SiteHeader />
        {children}
        <SiteFooter />
      </body>
    </html>
  )
}

// app/gallery/layout.tsx — gallery section layout
export default function GalleryLayout({ children }: { children: React.ReactNode }) {
  return (
    <section>
      <CategoryNav /> {/* only in gallery routes */}
      {children}
    </section>
  )
}
```

**Why**: Layouts persist across navigation — `SiteHeader` never unmounts. Nested layouts let each route group add its own chrome without affecting other sections.

---

## Anti-Pattern Catalog

### Fetching Data Inside Client Components

```tsx
// BAD — network waterfall after hydration
'use client'
import { useEffect, useState } from 'react'

export function Gallery() {
  const [artworks, setArtworks] = useState([])
  useEffect(() => {
    fetch('/api/artworks').then(r => r.json()).then(setArtworks)
  }, [])
  return <div>{artworks.map(...)}</div>
}
```

**Detection**: `rg "'use client'" --include="*.tsx" -l | xargs rg "useEffect.*fetch" -l`

**Fix**: Move the fetch to a Server Component parent. Pass `artworks` as a prop.

---

### Using `'use client'` on the Entire Page

```tsx
// BAD — makes the whole page client-side
'use client'
export default function GalleryPage() { ... }
```

**Detection**: `rg "'use client'" app/ --include="page.tsx" -l`

**Fix**: Move `'use client'` to only the interactive leaf component (e.g., the lightbox opener button, the filter select). The page itself stays a Server Component.

---

### Skipping `sizes` Prop on Responsive Images

```tsx
// BAD — browser can't calculate the right srcSet entry
<Image src="/art.jpg" width={1200} height={800} alt="..." />

// GOOD — browser picks correct size per viewport
<Image
  src="/art.jpg"
  width={1200}
  height={800}
  alt="Oil painting: autumn forest"
  sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
/>
```

**Detection**: `rg "<Image" --include="*.tsx" -A3 | rg -v "sizes="` — flags Image blocks without a `sizes` prop.

---

### Using `router.push` for Category Filtering Instead of URL State

```tsx
// BAD — breaks browser back button, loses filter on refresh
'use client'
const [filter, setFilter] = useState('all')
router.push('/gallery') // loses filter

// GOOD — filter is in the URL, shareable and bookmarkable
// app/gallery/page.tsx
export default function GalleryPage({ searchParams }: { searchParams: { category?: string } }) {
  const category = searchParams.category ?? 'all'
  return <GalleryGrid category={category} />
}
```

**Why**: URL-based state survives hard refresh and is shareable. `searchParams` is available in Server Components with no client JS.

---

## Error-Fix Mapping

| Error | Cause | Fix |
|-------|-------|-----|
| `You're importing a component that needs useState. It only works in a Client Component but none of its parents are marked with "use client"` | Server Component uses a hook | Add `'use client'` to the component that uses the hook |
| `Hydration failed because the initial UI does not match what was rendered on the server` | Server and client render different HTML (often from `Date.now()` or random IDs) | Move non-deterministic logic to `useEffect` or use `useId()` for IDs |
| `Route "/gallery/[slug]" used \`params.slug\` — \`params\` should be awaited before using its properties` | Next.js 15 async params | `const { slug } = await params` (or wrap in React.use(params) in Client Component) |
| `Error: Segment "gallery" is missing a \`page.tsx\` file` | Directory exists without page | Add `page.tsx` or move the component to a layout |
| `Objects are not valid as a React child (found: [object Promise])` | Rendering async component without `await` | Ensure parent is `async` and `await`s the child |

---

## Loading Table

| Task signal | Load this reference |
|-------------|-------------------|
| "App Router", "Server Component", "Client Component" | this file |
| "metadata", "Open Graph", "generateMetadata" | this file |
| "generateStaticParams", "static generation", "SSG" | this file |
| "Suspense", "streaming", "loading.tsx" | this file |
| "hydration error", "use client", "server/client split" | this file |
