# Portfolio SEO Reference

> **Scope**: Structured data (JSON-LD) for artworks, Open Graph for portfolio pages, semantic HTML conventions, and sitemap generation. Does NOT cover general Next.js performance or image optimization (see image-optimization.md).
> **Version range**: Next.js 13.4+ metadata API; schema.org vocabulary all versions
> **Generated**: 2026-04-13 — verify JSON-LD types against schema.org/VisualArtwork

---

## Overview

Portfolio SEO has two distinct layers: machine-readable structured data that tells search engines what the artwork is (JSON-LD), and social preview metadata that controls how the portfolio looks when shared on Instagram, Twitter, or LinkedIn (Open Graph). Both are required. Missing structured data means Google cannot display rich results; missing Open Graph means social shares show plain text instead of the artwork.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `schema.org/VisualArtwork` JSON-LD | all | Artwork detail pages | Gallery index pages (use `schema.org/CollectionPage`) |
| `schema.org/Person` + `schema.org/ProfilePage` | all | Artist about/bio page | Individual artwork pages |
| `og:type = "article"` | all | Individual artwork or series pages | The homepage or gallery index |
| `og:type = "website"` | all | Homepage, gallery index | Artwork detail pages |
| `next/image` for `og:image` | 13.4+ | Social preview images | External URLs not in `next.config.js` domains |
| `next-sitemap` package | all | Sites with 10+ pages | Single-page portfolios |

---

## Correct Patterns

### JSON-LD for Individual Artwork Pages

```tsx
// app/gallery/[slug]/page.tsx
export default async function ArtworkPage({ params }: { params: { slug: string } }) {
  const artwork = await getArtwork(params.slug)

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'VisualArtwork',
    name: artwork.title,
    description: artwork.description,
    image: `https://yourportfolio.com${artwork.imageUrl}`,
    creator: {
      '@type': 'Person',
      name: artwork.artistName,
      url: 'https://yourportfolio.com',
    },
    dateCreated: artwork.year, // "2024" or "2024-03-15"
    artMedium: artwork.medium, // "Oil on canvas"
    artworkSurface: artwork.surface, // "Canvas"
    width: { '@type': 'Distance', name: `${artwork.widthCm} cm` },
    height: { '@type': 'Distance', name: `${artwork.heightCm} cm` },
    artEdition: artwork.edition ?? undefined, // omit if unique work
  }

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <ArtworkDetail artwork={artwork} />
    </>
  )
}
```

**Why**: Google uses `VisualArtwork` schema to generate rich results (image carousels, knowledge panels). The `creator` field connects to the artist's entity, improving authority signals across the portfolio.

---

### JSON-LD for Gallery Collection Page

```tsx
// app/gallery/page.tsx
export default async function GalleryPage() {
  const artworks = await getArtworks()

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: 'Portfolio Gallery | Artist Name',
    description: 'Oil paintings and drawings by Artist Name, 2020–2024.',
    url: 'https://yourportfolio.com/gallery',
    author: {
      '@type': 'Person',
      name: 'Artist Name',
    },
    hasPart: artworks.map(a => ({
      '@type': 'VisualArtwork',
      name: a.title,
      url: `https://yourportfolio.com/gallery/${a.slug}`,
    })),
  }

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <GalleryGrid artworks={artworks} />
    </>
  )
}
```

---

### Open Graph and Twitter Cards via Next.js Metadata API

```tsx
// app/gallery/[slug]/page.tsx
export async function generateMetadata(
  { params }: { params: { slug: string } }
): Promise<Metadata> {
  const artwork = await getArtwork(params.slug)
  const imageUrl = `https://yourportfolio.com${artwork.imageUrl}`

  return {
    title: `${artwork.title} | Artist Portfolio`,
    description: artwork.description,
    openGraph: {
      type: 'article',            // individual artwork = article
      title: artwork.title,
      description: artwork.description,
      url: `https://yourportfolio.com/gallery/${artwork.slug}`,
      images: [{
        url: imageUrl,
        width: artwork.width,
        height: artwork.height,
        alt: `${artwork.title} by ${artwork.artistName}`,
      }],
    },
    twitter: {
      card: 'summary_large_image', // shows the artwork at full width
      title: artwork.title,
      description: artwork.description,
      images: [imageUrl],
    },
  }
}
```

**Why**: `summary_large_image` on Twitter/X shows the artwork at full banner width — critical for visual portfolios. `article` type for individual artworks signals to crawlers that this is a specific item, not a homepage.

---

### Semantic HTML for Portfolio Structure

Search engines and screen readers use semantic elements to understand page hierarchy. Portfolio-specific conventions:

```tsx
// Correct semantic structure for a gallery page
export default function GalleryPage() {
  return (
    <main>
      <header>
        <h1>Portfolio Gallery</h1>
        <p>Oil paintings and mixed media, 2020–2024</p>
      </header>

      {/* Category nav — NOT a nav landmark, it's within page content */}
      <div role="group" aria-label="Gallery categories">
        <CategoryFilter />
      </div>

      {/* Gallery grid — ul/li signals list of equivalent items */}
      <ul className="grid grid-cols-2 gap-4" aria-label="Artwork gallery">
        {artworks.map(artwork => (
          <li key={artwork.id}>
            <article> {/* each artwork is a standalone content item */}
              <figure>
                <Image src={artwork.src} alt={artwork.alt} width={600} height={400} />
                <figcaption>{artwork.title}, {artwork.year}</figcaption>
              </figure>
            </article>
          </li>
        ))}
      </ul>
    </main>
  )
}
```

**Why**: `<article>` signals self-contained content that makes sense independently (each artwork). `<figure>` + `<figcaption>` creates the semantic image-caption pair that structured data extractors and screen readers expect.

---

### Sitemap Generation with `next-sitemap`

```javascript
// next-sitemap.config.js (project root)
/** @type {import('next-sitemap').IConfig} */
module.exports = {
  siteUrl: 'https://yourportfolio.com',
  generateRobotsTxt: true,
  changefreq: 'monthly',      // portfolios don't change daily
  priority: 0.7,
  exclude: ['/api/*'],        // exclude API routes
  additionalPaths: async (config) => {
    const artworks = await getArtworks()
    return artworks.map(a => ({
      loc: `/gallery/${a.slug}`,
      changefreq: 'yearly',   // finished artwork pages rarely change
      priority: 0.9,          // individual artwork pages are high-value
      lastmod: a.updatedAt,
    }))
  },
}
```

```json
// package.json — add to scripts
{
  "scripts": {
    "postbuild": "next-sitemap"
  }
}
```

---

## Anti-Pattern Catalog

### Using `dangerouslySetInnerHTML` Without JSON.stringify

```tsx
// BAD — XSS risk if artwork title contains quotes or script tags
<script
  type="application/ld+json"
  dangerouslySetInnerHTML={{ __html: `{"name": "${artwork.title}"}` }}
/>

// GOOD — JSON.stringify escapes all special characters
<script
  type="application/ld+json"
  dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
/>
```

**Detection**: `rg "dangerouslySetInnerHTML.*\\\$\{" --include="*.tsx" --include="*.jsx"`

---

### Empty or Duplicate `og:image`

```tsx
// BAD — uses same generic image for every artwork page
export const metadata = {
  openGraph: { images: ['/og-default.jpg'] }, // all artwork pages look the same when shared
}

// GOOD — per-artwork Open Graph image
export async function generateMetadata({ params }) {
  const artwork = await getArtwork(params.slug)
  return {
    openGraph: { images: [{ url: artwork.imageUrl, width: artwork.width, height: artwork.height }] }
  }
}
```

**Detection**: `rg "og-default" --include="*.tsx" -l | xargs -I{} rg "generateMetadata" {} | wc -l` — if zero, pages use static fallback.

---

### Missing `alt` on Social Preview Images

```tsx
// BAD — social preview lacks accessible description
images: [{ url: artwork.imageUrl }]

// GOOD — alt text travels with the OG image
images: [{
  url: artwork.imageUrl,
  width: 1200,
  height: 800,
  alt: `${artwork.title} — ${artwork.medium} by ${artwork.artistName}`,
}]
```

---

### `<title>` Tag Duplication Between Layout and Page

```tsx
// BAD — both layout.tsx and page.tsx export metadata.title, causing duplication
// layout.tsx: title = "Artist Portfolio"
// page.tsx:   title = "About | Artist Portfolio"
// Result: "Artist Portfolio | About | Artist Portfolio"

// GOOD — use title template in root layout, override in pages
// app/layout.tsx
export const metadata: Metadata = {
  title: { default: 'Artist Portfolio', template: '%s | Artist Portfolio' }
}
// app/about/page.tsx
export const metadata: Metadata = { title: 'About' }
// Result: "About | Artist Portfolio" ✓
```

**Detection**: `rg "metadata.*title" app/ --include="layout.tsx" --include="page.tsx" -l | wc -l` — if more than 2, check for template vs. literal collision.

---

## Error-Fix Mapping

| Error / Symptom | Cause | Fix |
|-----------------|-------|-----|
| Google Search Console: "Missing field 'image'" in VisualArtwork | JSON-LD omits required `image` field | Add `image: absoluteUrl` (must be absolute URL, not relative path) |
| Social share shows no preview image | `og:image` URL is relative (`/image.jpg`) | Use absolute URL: `${process.env.NEXT_PUBLIC_SITE_URL}/image.jpg` |
| Duplicate title tags in `<head>` | Both layout and page set static `title` strings | Use `title.template` in root layout, plain string in page |
| Structured data validation error: "The value of 'dateCreated' must be a date" | Passing a year number (`2024`) instead of string | Use `"2024"` (string) or ISO date `"2024-03-15"` |
| `next-sitemap` generates paths but Googlebot gets 404 | Dynamic routes not in `generateStaticParams` | Add the slug to `generateStaticParams` or set `dynamicParams = true` |

---

## Loading Table

| Task signal | Load this reference |
|-------------|-------------------|
| "structured data", "JSON-LD", "schema.org" | this file |
| "Open Graph", "og:image", "social preview", "Twitter Card" | this file |
| "sitemap", "robots.txt", "SEO" | this file |
| "semantic HTML", "figcaption", "article element" | this file |
| "metadata", "generateMetadata", "title template" | this file (and next-app-router.md) |
