# Performance Optimization Patterns to Detect and Fix

## Pattern 1: Premature Optimization Without Profiling

**Signal:** Adding useMemo everywhere, complex code splitting, aggressive caching, rewriting fine code — before measuring.

**Fix:** Profile first, identify bottlenecks with data, prioritize by impact, measure again.
```bash
npm run build -- --profile
npx webpack-bundle-analyzer build/bundle-stats.json
lighthouse https://example.com --view
```

---

## Pattern 2: Micro-Optimizations Over Real Bottlenecks

**Signal:** `useMemo` on trivial ops, caching tiny data, code-splitting small components.

**Fix:** Profile for actual bottlenecks (>16ms ops). Optimize: large list rendering (virtualization), heavy calculations, big bundles. Split routes/features, not tiny components.

```typescript
// Real targets: expensive list rendering, heavy computation
const VirtualizedList = memo(({ items }) => (
  <VirtualList items={items} height={600} itemSize={50} />
))
const ExpensiveChart = memo(({ data }) => {
  const processedData = useMemo(() => processLargeDataset(data), [data])
  return <Chart data={processedData} />
})
```

---

## Pattern 3: Ignoring RUM Data

**Signal:** "Lighthouse 95, no optimization needed" while users complain.

**Fix:** Implement RUM with web-vitals. Track p75/p95. Segment by device, network, geography. RUM wins over synthetic.

```typescript
import { getCLS, getFID, getLCP } from 'web-vitals'
function sendToAnalytics(metric) {
  navigator.sendBeacon('/api/web-vitals', JSON.stringify({
    name: metric.name, value: metric.value, rating: metric.rating,
    connection: navigator.connection?.effectiveType,
    deviceMemory: navigator.deviceMemory
  }))
}
getCLS(sendToAnalytics)
getFID(sendToAnalytics)
getLCP(sendToAnalytics)
```

---

## Pattern 4: Bundle Optimization Without Analysis

**Signal:** Blindly lazy-loading everything, splitting every component, removing all libraries.

**Fix:** Analyze first. Identify deps >100KB. Split by routes, not components. Initial bundle <200KB. Lazy load below-fold only.

```bash
npm run build
npx webpack-bundle-analyzer build/stats.json
# Look for: deps >100KB, duplicates, unused code, misconfigured chunks
```

---

## Pattern 5: Gaming Metrics Instead of Improving UX

**Signal:** Hiding content for LCP, delaying JS for FID, removing images for CLS, loading everything after metrics recorded.

**Fix:** Optimize the actual resource. Make content load faster, not appear faster. Reserve space for CLS, don't remove features.

```typescript
<Image src="/hero.webp" priority width={1200} height={600} alt="Hero" />
<div style={{ aspectRatio: '16/9', position: 'relative' }}>
  <Image src="/banner.jpg" fill alt="Banner" />
</div>
```

---

## Pattern 6: Performance Budgets Without Context

**Signal:** "Total bundle must be <200KB" for a data visualization dashboard.

**Fix:** Context-appropriate budgets by app type:

```yaml
Marketing site:   JS 150KB, CSS 50KB, Images 500KB
E-commerce:       JS 250KB, CSS 75KB, Images 800KB
Data dashboard:   JS 400KB, CSS 100KB, lazy-chunks 200KB/route
```

---

## Checklist

1. Have baseline metrics (Lighthouse, RUM, bundle analysis)
2. Know what's actually slow (profiling data, not assumptions)
3. Understand user context (devices, networks, geography)
4. Set context-appropriate budgets
5. Optimize real bottlenecks (data-driven)
6. Measure impact (before/after)
7. Monitor in production (RUM)
8. Avoid over-engineering
