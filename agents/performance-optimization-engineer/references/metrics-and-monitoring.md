# Metrics & RUM Monitoring Reference
<!-- Loaded by performance-optimization-engineer when task involves metrics collection, RUM, monitoring setup, or analytics -->

> **Scope**: Real User Monitoring (RUM) implementation, metric reporting pipelines, and sampling strategies. Does NOT cover Core Web Vitals thresholds (see `core-web-vitals.md`).
> **Version range**: web-vitals 3.0+ (API changed in 3.0 — `getFID` replaced by `getINP`)
> **Generated**: 2026-04-09

---

## Overview

Performance monitoring requires two layers: **synthetic** (Lighthouse, lab conditions) and **RUM** (real users in production). RUM data always wins when they conflict — lab conditions don't reflect CDN variance, device diversity, or real network conditions. The most common failure mode is measuring only in lab and shipping regressions that only appear at P75 percentile in production.

---

## Pattern Table

| Metric | API | Version | Successor |
|--------|-----|---------|-----------|
| LCP | `onLCP()` | web-vitals 3.0+ | — |
| INP | `onINP()` | web-vitals 3.0+ | Replaces FID (deprecated) |
| CLS | `onCLS()` | web-vitals 3.0+ | — |
| FCP | `onFCP()` | web-vitals 3.0+ | — |
| TTFB | `onTTFB()` | web-vitals 3.0+ | — |
| FID | `getFID()` | web-vitals 2.x only | **Removed in 3.0** — use INP |

---

## Correct Patterns

### INP-First RUM Setup (web-vitals 3.0+)

Use the event-based API with `reportAllChanges` for INP to capture interaction updates throughout the session.

```typescript
import { onCLS, onFCP, onINP, onLCP, onTTFB } from 'web-vitals'

type MetricPayload = {
  name: string
  value: number
  rating: 'good' | 'needs-improvement' | 'poor'
  delta: number
  id: string
}

function sendToAnalytics(metric: MetricPayload) {
  // Use sendBeacon for reliability on page unload
  const body = JSON.stringify(metric)
  navigator.sendBeacon('/api/vitals', body)
}

// Register all metrics — INP needs reportAllChanges to capture updates
onLCP(sendToAnalytics)
onFCP(sendToAnalytics)
onCLS(sendToAnalytics)
onTTFB(sendToAnalytics)
onINP(sendToAnalytics, { reportAllChanges: true }) // INP updates on each interaction
```

**Why**: `onINP` without `reportAllChanges` only fires on page unload. Interactions throughout the session that degrade INP are invisible without this flag.

---

### Sampling Strategy for High-Traffic Sites

Don't send 100% of metric events — use sampling to reduce costs without losing statistical significance.

```typescript
const SAMPLE_RATE = 0.1 // 10% sample

function sendToAnalytics(metric: MetricPayload) {
  if (Math.random() > SAMPLE_RATE) return // Drop 90% of events

  const body = JSON.stringify({
    ...metric,
    url: window.location.href,
    // Add device context for segmentation
    connection: (navigator as any).connection?.effectiveType ?? 'unknown',
    deviceMemory: (navigator as any).deviceMemory ?? 'unknown',
  })
  navigator.sendBeacon('/api/vitals', body)
}
```

**Why**: At 1M pageviews/day, 100% reporting generates 5M+ events. 10% sampling gives P75 accuracy with 500K events. Below 1% loses statistical significance at the page-segment level.

---

### Attribution Data for LCP Debugging

Use `attribution` build of web-vitals to identify *what* caused the LCP element to be slow.

```typescript
import { onLCP } from 'web-vitals/attribution'

onLCP((metric) => {
  const attribution = metric.attribution
  sendToAnalytics({
    name: metric.name,
    value: metric.value,
    rating: metric.rating,
    // Attribution fields identify root cause
    lcpElement: attribution.lcpEntry?.element?.tagName ?? 'unknown',
    loadDelay: attribution.timeToFirstByte,
    resourceLoadDelay: attribution.resourceLoadDelay,
    resourceLoadDuration: attribution.resourceLoadDuration,
  })
})
```

**Why**: LCP value alone doesn't tell you if the delay is TTFB, resource load time, or render blocking. Attribution data cuts debugging time from hours to minutes.

---

## Anti-Pattern Catalog

### ❌ Using FID Instead of INP in New Code

**Detection**:
```bash
grep -rn 'getFID\|onFID\|FID' --include="*.ts" --include="*.tsx" --include="*.js"
rg 'getFID|onFID' --type ts --type js
```

**What it looks like**:
```typescript
import { getFID } from 'web-vitals' // deprecated in 3.0, removed in 3.5+
getFID(sendToAnalytics)
```

**Why wrong**: FID was removed from web-vitals 3.0. It only captures the *first* interaction delay, missing the broader picture of all interactions. Google replaced it with INP for Core Web Vitals in March 2024. Code using `getFID` silently does nothing on web-vitals 3.0+.

**Fix**:
```typescript
import { onINP } from 'web-vitals'
onINP(sendToAnalytics, { reportAllChanges: true })
```

**Version note**: FID removed from web-vitals 3.0.0 (November 2022). INP became an official Core Web Vitals metric in March 2024. INP threshold: ≤200ms Good, ≤500ms Needs Improvement, >500ms Poor.

---

### ❌ Using `fetch()` Instead of `sendBeacon()` for Metric Reporting

**Detection**:
```bash
grep -rn "fetch.*vitals\|fetch.*analytics\|fetch.*metrics" --include="*.ts" --include="*.tsx"
rg "fetch\(" --type ts -A 2 | grep -A 2 "vitals\|metric\|lcp\|cls\|inp"
```

**What it looks like**:
```typescript
function sendToAnalytics(metric) {
  fetch('/api/vitals', {
    method: 'POST',
    body: JSON.stringify(metric),
  })
}
```

**Why wrong**: `fetch()` calls initiated during page unload are cancelled by the browser. Metrics like CLS and INP report on page unload — fetch-based reporting loses 20-40% of metric events in production. The browser kills in-flight fetch requests when the user navigates away.

**Fix**:
```typescript
function sendToAnalytics(metric) {
  // sendBeacon is fire-and-forget: survives page unload
  const success = navigator.sendBeacon('/api/vitals', JSON.stringify(metric))
  if (!success) {
    // Fallback: keepalive fetch for large payloads (>64KB limit of sendBeacon)
    fetch('/api/vitals', {
      method: 'POST',
      body: JSON.stringify(metric),
      keepalive: true, // Survives page unload
    })
  }
}
```

---

### ❌ Blocking Metric Reporting in the Critical Path

**Detection**:
```bash
grep -rn "await.*vitals\|vitals.*await\|onLCP.*await" --include="*.ts" --include="*.tsx"
```

**What it looks like**:
```typescript
// In _app.tsx or layout.tsx
await setupVitalsMonitoring() // Blocks rendering
```

**Why wrong**: Metric setup code in the render critical path adds to LCP. Vitals measurement is observational — it should never affect what it's measuring.

**Fix**:
```typescript
// Use useEffect or defer to after first paint
useEffect(() => {
  import('web-vitals').then(({ onLCP, onCLS, onINP }) => {
    onLCP(sendToAnalytics)
    onCLS(sendToAnalytics)
    onINP(sendToAnalytics, { reportAllChanges: true })
  })
}, [])
```

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| INP never fires in analytics | Using `onINP` without `reportAllChanges` on high-interaction page | Add `{ reportAllChanges: true }` to `onINP` call |
| CLS reported as 0 in all sessions | CLS collected before layout-shifting content loads | Ensure metric collection starts before any dynamic content insertion |
| 40%+ metric drop-off in production | Using `fetch()` instead of `sendBeacon()` for reporting | Replace with `navigator.sendBeacon()` or `fetch` with `keepalive: true` |
| `getFID is not a function` runtime error | web-vitals upgraded from 2.x to 3.x — FID removed | Replace `getFID` with `onINP` from web-vitals 3.0+ |
| LCP reports wrong element | Dynamically loaded images not registered as LCP candidates | Ensure LCP candidates are in initial HTML, not injected by JS |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| web-vitals 3.0.0 | `getFID` removed; new event-based `on*` API replaces get-based | All `getFID()` calls break silently |
| web-vitals 3.0.0 | `onINP` introduced | INP now measurable; use `reportAllChanges: true` |
| web-vitals 4.0.0 | Attribution builds fully integrated (no separate import path change) | `/attribution` import still works |
| Chrome 96+ | INP available via PerformanceObserver natively | `web-vitals` polyfills for older browsers |

---

## Detection Commands Reference

```bash
# Find FID usage (deprecated since web-vitals 3.0)
grep -rn 'getFID\|onFID' --include="*.ts" --include="*.tsx" --include="*.js"

# Find fetch-based metric reporting (should be sendBeacon)
grep -rn "fetch.*vitals\|fetch.*metric" --include="*.ts" --include="*.tsx"

# Find blocking vitals setup (should be deferred)
grep -rn "await.*vitals\|vitals.*await" --include="*.ts" --include="*.tsx"

# Verify sendBeacon usage exists
grep -rn "sendBeacon" --include="*.ts" --include="*.tsx" --include="*.js"
```

---

## See Also

- `core-web-vitals.md` — thresholds, LCP/CLS/INP optimization strategies
- `react-async-patterns.md` — async data loading patterns that affect INP
- [web-vitals changelog](https://github.com/GoogleChrome/web-vitals/blob/main/CHANGELOG.md)
