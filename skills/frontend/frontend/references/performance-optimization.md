# Web Performance Optimization

Optimize web loading, JavaScript runtime, rendering, memory, bundles, and Next.js SSR/SSG by measured user impact. Use RUM, synthetic monitoring, and performance budgets.

Not for: backend or algorithmic performance in a specific language (the `programming` skill); MCP server development. Only web and frontend runtime and load performance. Animation render cost (compositor-safe properties, `will-change`): `distinctive-frontend-design-refs/performance-budgets.md`.

## Verification STOP blocks

- **Before optimizing:** STOP. Give baseline metrics (LCP, FID, CLS, bundle size) with the measurement source. Optimization without a baseline is guessing.
- **After each optimization:** STOP. Give before/after metrics for that change. "It should be faster" is not evidence; show the numbers.
- **Before reporting done:** STOP. Every recommendation has metric, baseline, target, and evidence source. Without numbers it is an opinion.

## Output contract

Every recommendation carries all four fields; omitting one makes it unverifiable:

- **Metric:** what is measured (LCP, bundle size, FID).
- **Baseline:** current value with source ("3.2s via Lighthouse").
- **Target:** numeric goal ("<=2.5s").
- **Evidence:** how the improvement was or will be measured.

## Hard rules (always apply)

- **Profile before optimizing.** Measure with real data first; no guessing or premature optimization.
- **Core Web Vitals thresholds:** LCP <=2.5s, FID <=100ms, CLS <=0.1 are the non-negotiable "good" targets.
- **RUM over synthetic** when they conflict; real user experience beats lab conditions.
- **Bundle size validation:** every recommendation includes before/after bundle analysis (webpack-bundle-analyzer or equivalent).
- **Regression prevention:** performance budgets with automated CI/CD checks.

## Defaults (on unless disabled)

- `web-vitals` tracking for Core Web Vitals with sampling and reporting.
- Intersection-observer lazy loading for images, components, and below-fold content.
- Route- and component-based code splitting for bundles over 200KB.
- Budget recommendations from industry standards (total JS <200KB, images <500KB).
- Actionable reports with file references, size impact, and priority.

## Optional (off unless enabled)

- Aggressive service worker caching (adds cache-invalidation complexity).
- Responsive images in multiple formats (WebP, AVIF) with `srcset`.
- Lighthouse CI regression detection.
- Deep dependency-tree analysis for duplicate modules and `splitChunks` tuning.

## Scope and limits

Profile web apps, analyze webpack dependencies, prioritize resources, fix loading and runtime bottlenecks. Assess compression, caching, and CDN delivery from the client side; infrastructure changes need the right specialist.

Limits: no guaranteed scores (devices, networks, and usage vary); no optimization without profiling data; no server or CDN configuration changes; no predicting future performance. When asked for guarantees, explain that the work is measurement-driven and results depend on real usage, while the fixes follow proven practice.

For test work, use the `testing` skill.

## Output format

Implementation schema ([output-schemas.md](../../../shared-patterns/output-schemas.md)):

````markdown
## Performance Optimization: [Component/Feature]

### Current Baseline Metrics

| Metric | Before | Threshold | Status |
|--------|--------|-----------|--------|
| LCP | X.Xs | ≤2.5s | ❌ POOR |
| FID | Xms | ≤100ms | ✅ GOOD |
| CLS | X.XX | ≤0.1 | ⚠️ NEEDS IMPROVEMENT |
| Bundle Size | XKB | <200KB | ❌ EXCEEDS |

### Optimizations Implemented

1. **[Optimization Name]**
   - **Change**: [What was changed]
   - **Impact**: [Metric improvement]
   - **File**: `path/to/file.ts:line`

### After Optimization Metrics

| Metric | Before | After | Improvement | Status |
|--------|--------|-------|-------------|--------|
| LCP | X.Xs | Y.Ys | -Z% | ✅ GOOD |
| FID | Xms | Yms | -Z% | ✅ GOOD |
| CLS | X.XX | Y.YY | -Z% | ✅ GOOD |
| Bundle Size | XKB | YKB | -ZKB | ✅ WITHIN BUDGET |

### Performance Budget

```json
{
  "js": { "max": 200, "current": 180 },
  "css": { "max": 50, "current": 35 },
  "images": { "max": 500, "current": 420 }
}
```

### Next Steps

- [ ] Monitor RUM data for 7 days
- [ ] Verify improvements on slow networks
- [ ] Update performance budgets in CI/CD
````

## Common errors

| Error | Cause | Fix |
|---|---|---|
| Premature optimization without baseline | Changing code before measuring | STOP. Profile first: `lighthouse`, `webpack-bundle-analyzer`, RUM. Get baselines before changes |
| RUM vs synthetic conflict | Lighthouse good, real users slow | Prioritize RUM; check network, device, and geography in RUM. Synthetic only approximates |
| Bundle size regression | Optimization added dependencies | Run the analyzer before and after. If the bundle grew, find another approach or justify the trade-off |

## Preferred patterns

| Instead of | Why wrong | Do |
|---|---|---|
| Changing code without measuring | No view of what is slow, may fix the wrong thing, cannot prove improvement | Profile with Lighthouse, RUM, bundle analyzer; find real bottlenecks |
| Micro-optimizations while big bundles and slow images remain | Negligible gains, misses real impact | Fix measurable bottlenecks: large bundles, unoptimized images, blocking resources |
| "Lighthouse is 95, performance is fine" while users complain | Lab tests miss slow networks and old devices | RUM with `web-vitals`; prioritize p75/p95 from real users |

Full catalog with detection and fixes: `performance-optimization/preferred-patterns.md`.

## Anti-rationalization

| Rationalization | Why it's wrong | Required action |
|---|---|---|
| "Looks fast enough" | Subjective without data | Profile with real metrics |
| "Lighthouse score is good" | Lab is not real users | Implement RUM tracking |
| "Small optimization, skip measurement" | Cannot prove improvement | Before/after metrics required |
| "Users won't notice X ms" | Delays add up | Optimize all measured bottlenecks |
| "It's the user's slow device" | You cannot control devices; optimize for them | Optimize for p75/p95 devices |
| "Bundle size doesn't matter with fast networks" | Many users have slow networks | Enforce bundle budgets |

## Hard gate patterns

On any of these: STOP, report the issue, fix with the correct approach.

| Pattern | Why blocked | Correct approach |
|---|---|---|
| Arbitrary `setTimeout`/delays | Masks timing issues | Proper async/await or event-driven patterns |
| Main thread blocked >50ms | Poor FID | Chunk work, web workers, or `requestIdleCallback` |
| Layout shifts from dynamic content | Poor CLS | Reserve space with `aspect-ratio` or explicit dimensions |
| Unoptimized images >500KB | Slow LCP | Next.js Image, responsive images, modern formats |
| Bundle >200KB without code splitting | Slow initial load | Route-based code splitting |

## Blocker criteria

Resolve routine issues from repository evidence. When you are sure, decide, record the assumption, and continue; ask Jev when genuinely unsure. Ask only when these leave a material decision open.

| Situation | Why stop | Ask |
|---|---|---|
| No baseline metrics | Cannot measure improvement | "Should I run profiling to get baseline metrics first?" |
| RUM vs synthetic conflict | User decides priority | "RUM shows slow, Lighthouse shows fast - which to prioritize?" |
| Performance vs feature trade-off | Business decision | "Feature X adds 50KB - acceptable trade-off?" |
| Budget vs target conflict | User sets priorities | "Can't meet both <200KB budget and <2.5s LCP - which is priority?" |

Decide explicitly first: budget limits, acceptable trade-offs, target device and network profile, whether to add service workers.

## Reference loading table

Load on demand; each holds patterns, code, and quantified impact.

| Signal | Load | Content |
|---|---|---|
| async, waterfall, parallel, Promise.all, fetch, Suspense, streaming, API route | `performance-optimization/react-async-patterns.md` | CRITICAL: 6 waterfall elimination patterns |
| bundle, import, code split, tree shaking, barrel file, lazy load, dynamic import, third-party script | `performance-optimization/react-bundle-optimization.md` | CRITICAL: 5 bundle size patterns |
| render, CLS, layout shift, hydration, SVG, content-visibility, script defer, conditional render, resource hint, Activity, useTransition | `performance-optimization/react-rendering-performance.md` | MEDIUM: 10 rendering patterns |
| Set, Map, array, loop, sort, flatMap, early return, index map, cache | `performance-optimization/js-algorithm-optimizations.md` | LOW-MEDIUM: 10 algorithm and data structure fixes |
| DOM, CSS, requestIdleCallback, localStorage, RegExp, batch reads, batch writes | `performance-optimization/browser-dom-optimizations.md` | LOW-MEDIUM: 4 browser and DOM hot-path fixes |
| INP, FID, sendBeacon, web-vitals, RUM, sampling, attribution, metric reporting | `performance-optimization/metrics-and-monitoring.md` | CRITICAL: INP setup, detection patterns, metric-collection error fixes |
| Next.js, App Router, next/image, next/font, streaming, ISR, revalidate, Server Component, dynamic | `performance-optimization/nextjs-optimization.md` | CRITICAL: Next.js 13.4+ performance patterns with detection |
| Lighthouse CI, performance budget, lhci, size-limit, CI/CD performance, regression, synthetic | `performance-optimization/performance-testing.md` | HIGH: Lighthouse CI setup, assertions, bundle gates, CI config |
| Core Web Vitals implementation, LCP optimization, FID reduction, CLS fixes, web-vitals library | `performance-optimization/core-web-vitals.md` | CRITICAL: Core Web Vitals patterns and thresholds |
| webpack analyzer, chunk optimization, splitChunks, bundle analysis | `performance-optimization/bundle-optimization.md` | HIGH: bundle analysis and splitting strategies |
| pattern examples, premature optimization, ignoring RUM, blocking main thread | `performance-optimization/preferred-patterns.md` | MEDIUM: pattern catalog with detection and fixes |
