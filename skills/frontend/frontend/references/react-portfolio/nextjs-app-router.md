# Next.js App Router Reference

> **Scope**: App Router patterns for portfolio sites: Server vs Client components, metadata API, static generation, data fetching.
> **Version range**: Next.js 13.4+ (App Router stable), 14+ recommended
> **Generated**: 2026-04-12

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `generateStaticParams` | 13.4+ | Gallery pages with known slugs | Dynamic user input |
| `generateMetadata` | 13.4+ | Per-artwork SEO/OG images | Static metadata for all pages |
| `export const dynamic = 'force-static'` | 13.4+ | Page must never run server-side | Page reads cookies/headers |
| `<Suspense>` with `loading.tsx` | 13.4+ | Data fetching in Server Components | Non-async content |
| `unstable_cache` | 14.0+ | Repeated CMS/API fetches | One-off requests |

---

## Correct Patterns

### Server Component for Gallery Grid

Gallery grids render same content for all visitors. No `'use client'`, fetch directly, zero bundle cost.

```tsx
// app/gallery/page.tsx — Server Component
export default async function GalleryPage() {
  const artworks = await getArtworks()
  return <GalleryGrid artworks={artworks} />
}
```

---

### Isolate Interactivity at the Leaf

Push `'use client'` as deep as possible to preserve static generation.

```tsx
// components/ArtworkCard.tsx — Server Component
import { LightboxTrigger } from './LightboxTrigger' // Client Component

export function ArtworkCard({ artwork }: { artwork: Artwork }) {
  return (
    <article>
      <Image src={artwork.src} alt={artwork.alt} width={600} height={400} />
      <h2>{artwork.title}</h2>
      <LightboxTrigger artworkId={artwork.id} />
    </article>
  )
}
```

---

### Per-Artwork Metadata with generateMetadata

```tsx
// app/gallery/[slug]/page.tsx
export async function generateMetadata({ params }): Promise<Metadata> {
  const artwork = await getArtworkBySlug(params.slug)
  return {
    title: `${artwork.title} — Portfolio`,
    description: artwork.description,
    openGraph: { images: [{ url: artwork.src, width: 1200, height: 630 }] },
  }
}

export async function generateStaticParams() {
  const artworks = await getArtworkBySlug('*')
  return artworks.map(art => ({ slug: art.slug }))
}
```

---

## Pattern Catalog

### Keep Pages as Server Components

**Detection**:
```bash
grep -rn "'use client'" app/ --include="*.tsx" | grep "page.tsx"
```

Entire page as Client Component disables static generation, ships all metadata as JS. Extract `useState` into a small Client Component leaf.

---

### Sync Filter State with URL Search Params

**Detection**:
```bash
rg "setFilter\|activeFilter" --type tsx
```

In-memory filter state disappears on refresh, breaks sharing/back button.

**Preferred action**: Use `useSearchParams` + `useRouter`:
```tsx
const active = searchParams.get('category') ?? 'all'
const setFilter = (cat: string) => {
  const params = new URLSearchParams(searchParams)
  if (cat === 'all') params.delete('category')
  else params.set('category', cat)
  router.push(`?${params.toString()}`, { scroll: false })
}
```

**Note**: `useSearchParams` requires `<Suspense>` in Next.js 14+.

---

### Fetch Data in Async Server Components

**Detection**:
```bash
grep -rn "getServerSideProps\|getStaticProps" app/ --include="*.tsx"
```

These are Pages Router APIs — silently ignored in App Router. Fetch in the async component body:
```tsx
export default async function GalleryPage() {
  const artworks = await fetch('...').then(r => r.json())
  return <GalleryGrid artworks={artworks} />
}
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `useState is not a function` in Server Component | Missing `'use client'` | Add directive or extract to Client Component |
| `useSearchParams() should be wrapped in suspense` | Next.js 14 requirement | Wrap with `<Suspense>` |
| `Each child should have a unique "key" prop` | Missing key on mapped elements | Add `key={artwork.id}` |
| `Image detected as LCP` without `priority` | Hero not marked priority | Add `priority` prop |
| `Un-configured Host` | External domain not in config | Add to `images.remotePatterns` |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| 13.4 | App Router stable | Migrate from Pages Router |
| 14.0 | `useSearchParams` requires Suspense | Wrap filter components |
| 14.1 | `unstable_cache` for CMS dedup | Use for Sanity/Contentful |
| 15.0 | Partial Prerendering experimental | Galleries with dynamic sections |

---

## Detection Commands Reference

```bash
grep -rn "'use client'" app/ --include="*.tsx" | grep "page.tsx"
grep -rn "getServerSideProps\|getStaticProps" app/ --include="*.tsx"
rg "useState.*category|useState.*filter" --type tsx
grep -rn "useSearchParams" --include="*.tsx" | grep -v "Suspense"
```

---

## See Also

- `image-optimization.md` — next/image props, WebP/AVIF, blur placeholders
- `performance.md` — Core Web Vitals, LCP, bundle analysis
