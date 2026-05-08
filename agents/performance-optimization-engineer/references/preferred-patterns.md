# Performance Optimization Patterns to Detect and Fix

Common performance optimization mistakes, preferred fixes, and why they matter.

## Pattern 1: Premature Optimization Without Profiling

**Signal:**
```typescript
// User: "Make my app faster"
// Agent immediately starts optimizing:
- Adding useMemo everywhere
- Implementing complex code splitting
- Setting up aggressive caching
- Rewriting perfectly fine code
```

**Why it matters:**
- No baseline measurements to know what's actually slow
- Optimizing the wrong things wastes time and adds complexity
- May introduce bugs or make maintenance harder
- Can't prove the optimizations actually helped

**Preferred action:**
1. Profile first: Run Lighthouse, measure Core Web Vitals, check bundle sizes
2. Identify bottlenecks: Find the actual performance problems with data
3. Prioritize: Fix the biggest impact items first
4. Measure again: Verify optimizations actually improved metrics

```bash
# Start with measurements
npm run build -- --profile
npx webpack-bundle-analyzer build/bundle-stats.json
lighthouse https://example.com --view
```

---

## Pattern 2: Over-Engineering with Micro-Optimizations

**Signal:**
```typescript
// Optimizing trivial operations that don't matter
const memoizedAdd = useMemo(() => (a, b) => a + b, [])

// Creating complex caching for tiny data
const [cachedValue] = useState(() => {
  const cached = localStorage.getItem('trivialValue')
  return cached ? JSON.parse(cached) : computeTrivialValue()
})

// Premature code splitting of small components
const TinyButton = lazy(() => import('./TinyButton'))
```

**Why it matters:**
- Simple operations are already fast (microseconds)
- Optimization overhead costs more than the operation itself
- Adds complexity that makes code harder to maintain
- Distracts from real performance issues

**Preferred action:**
- Profile to find actual bottlenecks (operations taking >16ms)
- Optimize expensive operations: large list rendering, heavy calculations, large data fetching
- Focus on bundle size: Split large routes/features, not tiny components
- Use performance budgets: Only optimize when metrics exceed thresholds

**Real optimization targets:**
```typescript
// Optimize expensive list rendering
const VirtualizedList = memo(({ items }) => {
  // Virtual scrolling for 10,000+ items
  return <VirtualList items={items} height={600} itemSize={50} />
})

// Optimize heavy computation
const ExpensiveChart = memo(({ data }) => {
  const processedData = useMemo(() => {
    // Complex statistical analysis on large dataset
    return processLargeDataset(data) // Actual expensive operation
  }, [data])
  return <Chart data={processedData} />
})
```

---

## Pattern 3: Ignoring Real User Monitoring (RUM) Data

**Signal:**
```
User: "Lighthouse shows 95 score but users complain it's slow"
Agent: "Lighthouse score is good, no optimization needed"
```

**Why it matters:**
- Lab tests use fast networks and powerful devices
- Real users have slow connections, old devices, poor conditions
- 95 Lighthouse score doesn't mean good user experience
- Missing the actual performance problems users face

**Preferred action:**
- Implement Real User Monitoring with web-vitals library
- Track p75 and p95 metrics, not just averages
- Segment by device, network, geography
- Prioritize RUM data over synthetic tests when they conflict

```typescript
// Implement proper RUM tracking
import { getCLS, getFID, getLCP } from 'web-vitals'

function sendToAnalytics(metric) {
  const body = JSON.stringify({
    name: metric.name,
    value: metric.value,
    rating: metric.rating,
    // Include user context
    connection: navigator.connection?.effectiveType,
    deviceMemory: navigator.deviceMemory
  })
  navigator.sendBeacon('/api/web-vitals', body)
}

getCLS(sendToAnalytics)
getFID(sendToAnalytics)
getLCP(sendToAnalytics)
```

---

## Pattern 4: Bundle Optimization Without Analysis

**Signal:**
```typescript
// Blindly applying "best practices"
- Lazy load everything
- Split every component into separate chunks
- Remove all libraries "to reduce bundle size"
- Implement aggressive tree shaking configs
```

**Why it matters:**
- Too many chunks hurt performance (HTTP overhead)
- Critical components shouldn't be lazy loaded
- Some libraries provide essential functionality efficiently
- Can break builds or introduce runtime errors

**Preferred action:**
1. Analyze current bundle with webpack-bundle-analyzer
2. Identify large dependencies (>100KB)
3. Split by routes, not components
4. Keep initial bundle under 200KB
5. Lazy load below-fold content only

```bash
# Proper bundle analysis workflow
npm run build
npx webpack-bundle-analyzer build/stats.json

# Look for:
# - Dependencies >100KB (moment.js, lodash, etc)
# - Duplicate packages
# - Unused code
# - Misconfigured chunks
```

---

## Pattern 5: Optimizing Metrics Instead of User Experience

**Signal:**
```typescript
// Gaming the metrics without improving UX
- Hiding content to improve LCP, showing it later
- Delaying JavaScript to improve FID
- Removing images to improve CLS
- Serving minimal page, loading everything after metrics recorded
```

**Why it matters:**
- Metrics are proxies for UX, not the goal itself
- Gaming metrics makes real experience worse
- Users notice the tricks (delayed content, missing features)
- Violates the purpose of performance optimization

**Preferred action:**
- Optimize metrics by improving actual UX
- Make content load faster, not appear faster
- Fix layout shifts by reserving space, not removing features
- Reduce JavaScript execution time, don't just defer it

**Real improvements:**
```typescript
// Improve LCP by optimizing the actual resource
<Image
  src="/hero.webp"
  priority // Preload critical image
  width={1200}
  height={600}
  alt="Hero"
/>

// Fix CLS by reserving space
<div style={{ aspectRatio: '16/9', position: 'relative' }}>
  <Image src="/banner.jpg" fill alt="Banner" />
</div>
```

---

## Pattern 6: Performance Budgets Without Context

**Signal:**
```
Agent: "Total bundle must be <200KB"
User: "But my app is a data visualization dashboard with charts"
Agent: "No exceptions, remove libraries until under 200KB"
```

**Why it matters:**
- Different app types have different requirements
- Some features require certain library sizes
- Arbitrary limits don't consider business value
- May force poor technical decisions

**Preferred action:**
- Set context-appropriate budgets
- Justify exceptions with business value
- Monitor budgets as trends, not hard limits
- Balance performance with functionality

**Context-appropriate budgets:**
```yaml
# Marketing site
initial-js: 150KB
initial-css: 50KB
images: 500KB

# E-commerce platform
initial-js: 250KB  # Cart, checkout, analytics
initial-css: 75KB
images: 800KB

# Data dashboard
initial-js: 400KB  # Charting libraries necessary
initial-css: 100KB
lazy-chunks: 200KB per route
```

---

## Summary: Performance Optimization Checklist

Before optimizing, verify:

1. ✅ Have current baseline metrics (Lighthouse, RUM, bundle analysis)
2. ✅ Know what's actually slow (profiling data, not assumptions)
3. ✅ Understand user context (devices, networks, geography)
4. ✅ Set appropriate budgets (based on app type and business needs)
5. ✅ Optimize real bottlenecks (data-driven priorities)
6. ✅ Measure impact (before/after comparisons)
7. ✅ Monitor in production (RUM tracking implemented)
8. ✅ Maintain simplicity (avoid over-engineering)

**Remember:** Performance optimization is about improving user experience with measurable results, not blindly applying "best practices" or gaming metrics.
