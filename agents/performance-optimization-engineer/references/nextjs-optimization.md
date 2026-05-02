# Next.js Performance Optimization Reference
<!-- Loaded by performance-optimization-engineer when task involves Next.js, App Router, SSR, ISR, next/image, next/font, streaming, or server components -->

> **Scope**: Next.js-specific performance patterns for App Router (13.4+). Pages Router patterns are noted where they differ.
> **Version range**: Next.js 13.4+ (App Router stable); Next.js 14+ (Server Actions, partial prerendering)
> **Generated**: 2026-04-09

---

## Overview

App Router changes the performance playbook (RSC, streaming, partial prerendering). Most common failure: applying Pages Router patterns — `getServerSideProps` mental models or blocking streaming in layout files.

---

## Pattern Table

| Pattern | API | Version | Pages Router Equivalent |
|---------|-----|---------|-------------------------|
| Route-level caching | `export const revalidate = 60` | Next.js 13.4+ | `getStaticProps` revalidate |
| Opt out of caching | `export const dynamic = 'force-dynamic'` | Next.js 13.4+ | `getServerSideProps` |
| Parallel data fetching | Multiple `await` in Server Component | Next.js 13.4+ | `getServerSideProps` with `Promise.all` |
| Streaming UI | `<Suspense>` around Server Components | Next.js 13.4+ | No equivalent (client-only) |
| Preconnect/DNS prefetch | `<link rel="preconnect">` in `<head>` | All versions | `next/head` |
| Optimized images | `next/image` with `sizes` prop | Next.js 13+ | Same |
| Font optimization | `next/font` | Next.js 13+ | `@next/font` (deprecated) |

---

## Correct Patterns

### Parallel Data Fetching in Server Components

Fetch data in parallel, not sequentially. Each `await` in series adds to LCP.

```typescript
// app/dashboard/page.tsx
async function DashboardPage() {
  // BAD: Sequential — each fetch waits for the previous
  // const user = await getUser()
  // const posts = await getPosts(user.id)
  // const analytics = await getAnalytics()

  // GOOD: Parallel — all fetches start simultaneously
  const [user, posts, analytics] = await Promise.all([
    getUser(),
    getPosts(),
    getAnalytics(),
  ])

  return <Dashboard user={user} posts={posts} analytics={analytics} />
}
```

**Why**: Sequential: 3 x 200ms = 600ms. Parallel: max(200ms) = 200ms. Directly impacts TTFB and LCP.

---

### Streaming with Suspense for Slow Data

Use Suspense to stream fast content immediately while slow data loads.

```typescript
// app/dashboard/page.tsx
import { Suspense } from 'react'
import { AnalyticsSkeleton } from './skeletons'

export default function DashboardPage() {
  return (
    <main>
      {/* Fast: renders immediately from cache */}
      <UserProfile />

      {/* Slow: streams in when ready, shows skeleton until then */}
      <Suspense fallback={<AnalyticsSkeleton />}>
        <AnalyticsPanel /> {/* Server Component with slow DB query */}
      </Suspense>
    </main>
  )
}
```

**Why**: Without Suspense, entire page waits for slowest source. With it, HTML streams progressively — above-fold content doesn't block on slow queries.

---

### next/image with Proper `sizes` Attribute

Always provide `sizes` to prevent downloading oversized images.

```tsx
import Image from 'next/image'

// BAD: Missing sizes — Next.js downloads the largest srcset variant
<Image src="/hero.jpg" width={800} height={600} alt="Hero" />

// GOOD: sizes tells browser which breakpoint variant to download
<Image
  src="/hero.jpg"
  width={800}
  height={600}
  alt="Hero"
  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 800px"
  priority // Add for LCP image — disables lazy loading
/>
```

**Why**: Without `sizes`, browser downloads full-width image regardless of viewport (4-5x size regression on mobile). `priority` skips lazy loading for LCP candidates.

---

### next/font for Zero Layout Shift

Use `next/font` instead of `@import` in CSS to eliminate font-related CLS.

```typescript
// app/layout.tsx
import { Inter } from 'next/font/google'

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  // Preload reduces FOUT; variable improves load efficiency
  variable: '--font-inter',
})

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={inter.variable}>
      <body>{children}</body>
    </html>
  )
}
```

**Why**: `@import` blocks rendering. `next/font` downloads at build time, serves from same domain, inlines font-face — eliminating CLS from font swapping.

---

### Route Segment Config for Caching Control

Use route segment config to set cache behavior per page — not global middleware.

```typescript
// app/dashboard/page.tsx

// Static: cached at build time, revalidated every 60s (ISR)
export const revalidate = 60

// Dynamic: no caching, runs on every request (like getServerSideProps)
export const dynamic = 'force-dynamic'

// Static: cached permanently until manually revalidated
export const revalidate = false // or: export const dynamic = 'force-static'
```

**Why**: Overusing `force-dynamic` bypasses the data cache. Misconfigured `dynamic` is a top cause of slow Next.js apps. Profile which routes need fresh data vs. can be cached.

---

## Pattern Catalog

### Stream Slow Data with Suspense Boundaries

**Detection**:
```bash
grep -rn "async function.*Layout\|async.*layout" --include="*.tsx" --include="*.ts" app/
rg "await.*fetch\|await.*db\|await.*prisma" app/layout.tsx app/**/layout.tsx
```

**What it looks like**:
```typescript
// app/layout.tsx
export default async function RootLayout({ children }) {
  const config = await fetchSiteConfig() // Blocks EVERY page render
  return (
    <html>
      <body><Header config={config} />{children}</body>
    </html>
  )
}
```

**Why wrong**: `layout.tsx` wraps every route. Slow await in root layout adds latency to every page load. Layouts don't stream — they must fully resolve first.

**Fix**:
```typescript
// Option 1: Cache aggressively if data changes rarely
const config = await fetchSiteConfig()
// Add: export const revalidate = 3600 // revalidate hourly

// Option 2: Move slow data to the specific page that needs it
// Option 3: Use Suspense with a fallback if it must be in layout
```

---

### Prefer Server Components Over next/dynamic

**Detection**:
```bash
grep -rn "next/dynamic" --include="*.tsx" --include="*.ts"
rg "dynamic\(" --type ts --type tsx -A 3 | grep -v "ssr: false"
```

**What it looks like**:
```typescript
// Using dynamic() for a component with no browser-only dependencies
import dynamic from 'next/dynamic'
const ProductCard = dynamic(() => import('./ProductCard'))
```

**Why wrong**: In App Router, `dynamic()` forces client-side rendering. For components without browser-only APIs, Server Components render faster with less JS. Only use `dynamic()` for browser-only APIs, `ssr: false`, or heavy client components.

**Fix**:
```typescript
// If ProductCard has no browser-only code, make it a Server Component:
// Simply don't add 'use client' — it's a Server Component by default
import { ProductCard } from './ProductCard' // Server Component
```

**Version note**: This anti-pattern is App Router (Next.js 13.4+) specific. In Pages Router, `dynamic()` is the correct way to code-split.

---

### Set priority={true} on Above-Fold Images

**Detection**:
```bash
grep -rn "next/image" --include="*.tsx" -A 5 | grep -B 3 -v "priority"
rg '<Image' --type tsx -A 4 | grep -v "priority"
```

**What it looks like**:
```tsx
// Hero image — the LCP element — without priority
<Image src="/hero.jpg" width={1200} height={600} alt="Hero" />
```

**Why wrong**: `next/image` lazy-loads by default. Hero image is the LCP element — lazy loading causes 300-800ms LCP regression.

**Fix**:
```tsx
<Image
  src="/hero.jpg"
  width={1200}
  height={600}
  alt="Hero"
  priority // Adds <link rel="preload"> in <head>, skips lazy loading
/>
```

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| `Error: Image with src "/hero.jpg" is missing required "width" property` | next/image requires explicit dimensions | Add `width` and `height` props, or use `fill` with a positioned container |
| CLS from images despite next/image | Missing `width`/`height` props causing no aspect ratio reservation | Add explicit `width` and `height`, or use `fill` in sized container |
| Font causes FOUT despite next/font | Using CSS `@import` alongside next/font | Remove all `@import` for Google Fonts; let next/font handle entirely |
| Layout shifts on navigation | Using CSS transitions on elements that shift layout | Switch to `transform` and `opacity` animations (compositor-only) |
| Streaming not working for Suspense | Using `dynamic = 'force-dynamic'` in a layout | Move `force-dynamic` to the specific page; layouts block streaming |

---

## Detection Commands Reference

```bash
# Find async layouts that could block rendering
grep -rn "async function.*Layout" --include="*.tsx" app/

# Find dynamic() usage that may be unnecessary in App Router
grep -rn "next/dynamic" --include="*.tsx" --include="*.ts"

# Find Images without priority (check manually if they're above fold)
rg '<Image' --type tsx -A 5 | grep -v "priority" | grep "src="

# Find CSS @import for Google Fonts (should use next/font instead)
grep -rn "@import.*fonts.googleapis" --include="*.css" --include="*.scss"

# Find sequential awaits in Server Components (should be Promise.all)
rg "await\s+\w" --type ts --type tsx app/ | grep -v "\.test\." | head -20
```

---

## See Also

- `react-bundle-optimization.md` — dynamic imports, code splitting (covers `next/dynamic` ssr:false pattern)
- `react-async-patterns.md` — concurrent features, Suspense patterns
- `browser-dom-optimizations.md` — layout shift causes and fixes
