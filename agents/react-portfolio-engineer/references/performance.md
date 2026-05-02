# Performance Optimization Reference

> **Scope**: Core Web Vitals for portfolio/gallery sites: LCP, CLS, INP, bundle analysis, Next.js strategies.
> **Version range**: Next.js 14+, React 18+
> **Generated**: 2026-04-12

---

## Pattern Table

| Metric | Good | Needs Improvement | Poor | Primary Cause |
|--------|------|-------------------|------|---------------|
| LCP | < 2.5s | 2.5–4.0s | > 4.0s | Hero not `priority`, wrong `sizes` |
| CLS | < 0.1 | 0.1–0.25 | > 0.25 | Missing width/height on images |
| INP | < 200ms | 200–500ms | > 500ms | Heavy JS on filter interactions |

---

## Correct Patterns

### Priority Loading for Hero Image

```tsx
<Image src="/artwork/featured.jpg" alt="Featured artwork"
  width={1920} height={1080} priority sizes="100vw" />
```

Without `priority`, Next.js lazy-loads the hero — adds 400-800ms to LCP on mobile.

---

### Explicit Width/Height on Every Image

Prevents CLS by reserving space before load.

```tsx
<Image src={artwork.src} alt={artwork.alt} width={600} height={400}
  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw" />
```

When using `fill`, container MUST have `position: relative` and explicit height or `aspect-ratio`:
```tsx
<div className="relative aspect-[3/2]">
  <Image src={artwork.src} alt={artwork.alt} fill className="object-cover" />
</div>
```

---

### Responsive `sizes` Prop

Without `sizes`, browser picks largest size. Correct `sizes` cuts payload 50-70% on mobile.

```tsx
<Image ... sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw" />
```

---

### Route-Level Code Splitting for Heavy Features

```tsx
const LightboxModal = dynamic(() => import('./LightboxModal'), {
  ssr: false,
  loading: () => null,
})
```

Lightbox ~15-30KB deferred until user clicks.

---

## Pattern Catalog

### Use priority Only on First Above-Fold Image

**Detection**:
```bash
grep -rn "priority" --include="*.tsx" | grep -v "//.*priority"
```

12 images with `priority` = 12 preloads competing for bandwidth. Only the first image benefits.

**Preferred action**:
```tsx
{artworks.map((art, index) => (
  <Image key={art.id} ... priority={index === 0} />
))}
```

---

### Add sizes Prop to Responsive Images

**Detection**:
```bash
rg "<Image" --type tsx | grep -v "sizes="
```

Without `sizes`, 1200px images downloaded on 375px mobile — 4-8x excess payload.

---

### Memoize Heavy Computation on Filter

**Detection**:
```bash
grep -rn "\.filter\(.*\.map\|\.sort\(.*\.filter" --include="*.tsx"
```

Sort + map on 100+ artworks blocks main thread. INP exceeds 200ms on mid-range mobile.

**Preferred action**:
```tsx
const filtered = useMemo(() =>
  artworks
    .filter(a => activeCategory === 'all' || a.category === activeCategory)
    .sort((a, b) => b.date.localeCompare(a.date)),
  [artworks, activeCategory]
)
```

---

### Import Icons from Specific Module Paths

**Detection**:
```bash
grep -rn "from 'react-icons'" --include="*.tsx"
```

Barrel imports pull entire icon set (~50KB). Use path-specific imports or inline SVGs.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `Missing required "width" property` | Missing props or `fill` without container | Add width/height or use fill with positioned container |
| `Not compatible with next export` | Static HTML with default loader | Add `unoptimized: true` or use custom loader |
| `"fill" but missing "sizes" prop` | Fill images need sizes | Add `sizes` matching breakpoints |
| `Hydration failed` | Client-only state rendered in SSR | Move to `useEffect` |

---

## Detection Commands Reference

```bash
grep -rn "priority" --include="*.tsx" app/ components/
rg "<Image" --type tsx | grep -v "sizes="
rg "\.filter\(.*\.sort\(" --type tsx | grep -v "useMemo"
grep -rn "from 'react-icons'" --include="*.tsx"
rg "<img " --type tsx | grep -v "// "
```

---

## See Also

- `image-optimization.md` — next/image props, blur, format config
- `nextjs-app-router.md` — Server vs Client, generateStaticParams
