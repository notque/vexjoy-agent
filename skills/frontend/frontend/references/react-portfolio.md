# React Portfolio and Gallery Sites

React portfolios and galleries for artists and photographers (React 18+, Next.js App Router). Use functional components, hooks, composition, and the App Router Server/Client split. Prioritize image quality, loading performance, accessibility, responsive layouts, and SEO. Use code splitting, static generation, and route prefetching for portfolio pages. Compress high-resolution images and support screen readers.

Not for: carts, Stripe, or checkout (`nextjs-ecommerce.md`); general React or Next.js architecture (`typescript-frontend.md`); React Native apps (`react-native.md`); generating the artwork itself (`image-gen` skill).

## Hard rules (always apply)

- **Read before editing.** Never edit a file you have not read in this session.
- **Run build and tests before reporting done.** Run `npm run build` (or equivalent) and show the actual output. Do not summarize as "build succeeds."
- **Feature branch, never main.** If on main, create a branch before committing.
- **Verify dependencies before importing.** Check `package.json` first.
- **`next/image`** for portfolio images, never plain `img`.
- **Alt text** on every image, descriptive.
- **Responsive images:** `sizes` prop or `srcset` on all gallery images.
- **Lazy loading** for images below the fold.
- **Touch-friendly:** every gallery interaction works on touch (swipe, tap).

## Portfolio design defaults (override with a stated reason)

Let the artist's work guide the layout. For an unfamiliar genre, new artist voice, or brand reset, go deeper with DISTINCTIVE mode in this skill.

- **The work is the hero.** The first viewport shows the strongest piece at full bleed, not a row of thumbnails around a name tag. No cards in the hero.
- **One composition per section.** Hero (strongest work), Body (supporting pieces), Detail (single piece or series deep-dive), Credits (statement and contact). Do not mix "about the artist" with the gallery grid in one section.
- **Real work, not Lorem Ipsum or stock photos.** Use the actual portfolio images from day one. Placeholder images produce placeholder decisions about scale, crop, density, and color.
- **Two typefaces maximum.** Display face for titles, body face for statements. One family with weight variation is often stronger.
- **One accent color.** The artwork carries the color; extra UI color fights it.
- **Motion budget (2-3 slots):** (1) one hero entrance on load, (2) one scroll-linked effect for the body grid (cross-fade, lazy reveal, or parallax), (3) one interaction effect on image hover or lightbox open. Ambient decorative motion buries the work.
- **Tells check.** Before building, check the tells table in `skills/shared-patterns/ui-design-judgment.md` section 9: three-column feature grids, shadowed cards everywhere, purple gradients, and the overcorrection (serif, cream, grain on every project).
- **Litmus:** remove the artist's name and leave only the work. Can a new visitor describe the artist's voice in one sentence? If not, the portfolio is not communicating yet.

## Defaults (on unless disabled)

- Blur-up placeholders while images load.
- WebP/AVIF with JPEG fallback.
- URL-based category filtering (for example `?category=paintings`).
- Lightbox keyboard navigation: arrow keys and Escape.

## Optional (off unless enabled)

- Masonry layout: only when requested.
- Infinite scroll: only when pagination is not enough.
- Image zoom: only when detailed artwork viewing is needed.
- Video embedding: only when multimedia content is requested.

## Implementation details

Use CSS Grid or Flexbox for galleries. Preserve detail with responsive formats, device-specific sizes, and base64 blur placeholders. Set `priority` on above-fold images.

Lightboxes need arrow keys, Escape, swipe, adjacent-image preloading, backdrop dismissal, and focus trapping. Add pinch-zoom when detailed viewing is needed. Use sm/md/lg/xl breakpoints and fluid grids.

Add JSON-LD for artworks, Open Graph tags, semantic HTML, and meta descriptions.

Related references: visual identity, color schemes, responsive layout, and accessibility in `ui-design.md`; type-safe components and build in `typescript-frontend.md`.

Out of scope: brand design, artist bios and statements (`writing` skill), CMS setup (CMS specialist), video editing (`video-editing` skill).

## Workflow (implementation schema)

1. **ANALYZE.** Confirm real artwork is available (not Lorem Ipsum or stock). Pick the strongest piece for the full-bleed hero. Write the brief: visual thesis, content plan, interaction thesis. Identify gallery needs (grid or masonry, filtering, lightbox), image needs (formats, sizes, lazy loading), and breakpoints.
2. **DESIGN.** Component architecture (Gallery, ImageCard, Lightbox), state (filtering, lightbox), image loading strategy (priority, lazy, blur).
3. **IMPLEMENT.** Gallery components with `next/image`, URL-based filtering, lightbox with keyboard and touch navigation, responsive design and image optimization.
4. **VALIDATE.** LCP < 2.5s, accessibility (alt text, keyboard), responsive (mobile, tablet, desktop), SEO (structured data, meta tags).

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| Any layout, typography, color, or visual design choice (load first) | `skills/shared-patterns/ui-design-judgment.md`, then `ui-design-recipes.md` and `ui-design-examples.md` in the same folder | Design defaults with reasons and the look-then-fix loop |
| Gallery component, filtering, image patterns, anti-rationalization table | `react-portfolio/gallery-patterns.md` | Gallery code, `next/image` priority and lazy examples, preferred patterns, anti-rationalization table |
| Lightbox implementation, keyboard/touch navigation | `react-portfolio/lightbox-patterns.md` | Full lightbox with keyboard and touch navigation |
| next/image, blur placeholders, WebP/AVIF, format config | `react-portfolio/image-optimization.md` | Image formats, blur placeholders, config |
| Breakpoints, mobile-first CSS, touch interactions | `react-portfolio/responsive-design.md` | Breakpoints and touch patterns |
| App Router pages, Server vs Client components, metadata API, URL filtering, SSG | `react-portfolio/nextjs-app-router.md` | App Router structure for portfolios |
| Portfolio LCP, CLS, INP, gallery bundle size, `priority`, `sizes` prop | `react-portfolio/performance.md` | Portfolio-specific Web Vitals fixes; general web performance is `performance-optimization.md` |
| SEO, structured data, JSON-LD, Open Graph, sitemap, social preview | `react-portfolio/portfolio-seo.md` | Artwork structured data and social previews |

## Common errors

| Error | Cause | Fix |
|---|---|---|
| Image not optimized | Plain `img` instead of `next/image` | Replace every `img` with `next/image` |
| Missing alt text | Images without `alt` | Add descriptive alt text to every Image |
| Poor LCP | Large unoptimized images, no priority | `priority` on above-fold images; lazy-load below the fold |

## Blocker criteria

Resolve routine issues from repository evidence. When you are sure, decide, record the assumption, and continue; ask Jev when genuinely unsure. Ask only when these leave a material decision open.

| Situation | Why stop | Ask |
|---|---|---|
| Masonry vs grid unclear | Different implementations | "Grid layout or masonry (Pinterest-style)?" |
| Video content needed | Different optimization | "Include video in portfolio or images only?" |
| CMS integration requested | Needs a CMS specialist | "Which CMS? (Sanity, Contentful, custom?)" |
| Animation level unclear | Simple vs complex | "Simple hover effects or complex transitions?" |

Decide explicitly before acting on: layout style, video handling, CMS platform, animation level.

Shared patterns: [anti-rationalization-core.md](../../../shared-patterns/anti-rationalization-core.md), [verification-checklist.md](../../../shared-patterns/verification-checklist.md).
