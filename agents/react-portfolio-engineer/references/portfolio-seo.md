# Portfolio SEO Reference

> **Scope**: JSON-LD for artworks, Open Graph, semantic HTML, sitemap generation. Not performance or image optimization.
> **Version range**: Next.js 13.4+ metadata API; schema.org all versions
> **Generated**: 2026-04-13

---

## Pattern Table

| Pattern | Use When |
|---------|----------|
| `schema.org/VisualArtwork` JSON-LD | Artwork detail pages |
| `schema.org/CollectionPage` JSON-LD | Gallery index pages |
| `schema.org/Person` + `ProfilePage` | Artist about/bio page |
| `og:type = "article"` | Individual artwork pages |
| `og:type = "website"` | Homepage, gallery index |
| `next-sitemap` | Sites with 10+ pages |

---

## Correct Patterns

### JSON-LD for Artwork Pages

```tsx
const jsonLd = {
  '@context': 'https://schema.org',
  '@type': 'VisualArtwork',
  name: artwork.title,
  description: artwork.description,
  image: `https://yourportfolio.com${artwork.imageUrl}`,
  creator: { '@type': 'Person', name: artwork.artistName, url: 'https://yourportfolio.com' },
  dateCreated: artwork.year,
  artMedium: artwork.medium,
  width: { '@type': 'Distance', name: `${artwork.widthCm} cm` },
  height: { '@type': 'Distance', name: `${artwork.heightCm} cm` },
}

<script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
```

---

### JSON-LD for Gallery Collection Page

```tsx
const jsonLd = {
  '@context': 'https://schema.org',
  '@type': 'CollectionPage',
  name: 'Portfolio Gallery | Artist Name',
  hasPart: artworks.map(a => ({
    '@type': 'VisualArtwork',
    name: a.title,
    url: `https://yourportfolio.com/gallery/${a.slug}`,
  })),
}
```

---

### Open Graph and Twitter Cards

```tsx
export async function generateMetadata({ params }): Promise<Metadata> {
  const artwork = await getArtwork(params.slug)
  return {
    title: `${artwork.title} | Artist Portfolio`,
    openGraph: {
      type: 'article',
      images: [{ url: artwork.imageUrl, width: artwork.width, height: artwork.height,
        alt: `${artwork.title} — ${artwork.medium} by ${artwork.artistName}` }],
    },
    twitter: { card: 'summary_large_image', images: [artwork.imageUrl] },
  }
}
```

`summary_large_image` shows artwork at full banner width.

---

### Semantic HTML

```tsx
<main>
  <header><h1>Portfolio Gallery</h1></header>
  <div role="group" aria-label="Gallery categories"><CategoryFilter /></div>
  <ul className="grid" aria-label="Artwork gallery">
    {artworks.map(artwork => (
      <li key={artwork.id}>
        <article>
          <figure>
            <Image src={artwork.src} alt={artwork.alt} width={600} height={400} />
            <figcaption>{artwork.title}, {artwork.year}</figcaption>
          </figure>
        </article>
      </li>
    ))}
  </ul>
</main>
```

`<article>` = self-contained content. `<figure>` + `<figcaption>` = semantic image-caption pair.

---

### Sitemap Generation

```javascript
// next-sitemap.config.js
module.exports = {
  siteUrl: 'https://yourportfolio.com',
  generateRobotsTxt: true,
  changefreq: 'monthly',
  exclude: ['/api/*'],
  additionalPaths: async () => {
    const artworks = await getArtworks()
    return artworks.map(a => ({
      loc: `/gallery/${a.slug}`, changefreq: 'yearly', priority: 0.9, lastmod: a.updatedAt,
    }))
  },
}
```

---

## Pattern Catalog

### Use JSON.stringify for dangerouslySetInnerHTML

```tsx
// BAD — XSS risk
<script type="application/ld+json" dangerouslySetInnerHTML={{ __html: `{"name": "${artwork.title}"}` }} />

// GOOD
<script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
```

**Detection**: `rg "dangerouslySetInnerHTML.*\\\$\{" --include="*.tsx"`

---

### Per-Artwork og:image (Not Generic Fallback)

**Detection**: `rg "og-default" --include="*.tsx"`

Use `generateMetadata` with artwork-specific image, not a shared fallback.

---

### Title Template in Root Layout

```tsx
// app/layout.tsx
export const metadata: Metadata = {
  title: { default: 'Artist Portfolio', template: '%s | Artist Portfolio' }
}
// app/about/page.tsx
export const metadata: Metadata = { title: 'About' }
// Result: "About | Artist Portfolio"
```

---

## Error-Fix Mapping

| Symptom | Fix |
|---------|-----|
| GSC: "Missing field 'image'" | Use absolute URL in JSON-LD `image` |
| No social preview | Use absolute URL for `og:image` |
| Duplicate title tags | Use `title.template` in root layout |
| "dateCreated must be a date" | Use string `"2024"` or ISO date |
| Sitemap 404s | Add slug to `generateStaticParams` |

---

## Loading Table

| Signal | Load |
|--------|------|
| Structured data, JSON-LD, schema.org | this file |
| Open Graph, og:image, social preview | this file |
| Sitemap, robots.txt, SEO | this file |
| Semantic HTML, figcaption | this file |
| Metadata, generateMetadata, title template | this file + nextjs-app-router.md |
