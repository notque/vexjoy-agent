# Core Web Vitals Implementation

Comprehensive Core Web Vitals monitoring and optimization patterns.

## Core Web Vitals Thresholds

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| LCP (Largest Contentful Paint) | ≤2.5s | 2.5s - 4.0s | >4.0s |
| FID (First Input Delay) | ≤100ms | 100ms - 300ms | >300ms |
| CLS (Cumulative Layout Shift) | ≤0.1 | 0.1 - 0.25 | >0.25 |
| FCP (First Contentful Paint) | ≤1.8s | 1.8s - 3.0s | >3.0s |
| TTFB (Time to First Byte) | ≤800ms | 800ms - 1800ms | >1800ms |

## Implementation Example

```typescript
// Comprehensive Core Web Vitals monitoring
import { getCLS, getFCP, getFID, getLCP, getTTFB } from 'web-vitals'

interface PerformanceConfig {
  enableAnalytics: boolean
  sampleRate: number
  reportingEndpoint: string
  thresholds: {
    lcp: { good: number; poor: number }
    fid: { good: number; poor: number }
    cls: { good: number; poor: number }
    fcp: { good: number; poor: number }
    ttfb: { good: number; poor: number }
  }
}

const performanceConfig: PerformanceConfig = {
  enableAnalytics: process.env.NODE_ENV === 'production',
  sampleRate: 0.1, // 10% sampling
  reportingEndpoint: '/api/performance',
  thresholds: {
    lcp: { good: 2500, poor: 4000 },
    fid: { good: 100, poor: 300 },
    cls: { good: 0.1, poor: 0.25 },
    fcp: { good: 1800, poor: 3000 },
    ttfb: { good: 800, poor: 1800 }
  }
}

class CoreWebVitalsMonitor {
  private config: PerformanceConfig
  private metrics: Map<string, any> = new Map()
  private queue: any[] = []

  constructor(config: PerformanceConfig) {
    this.config = config
    this.initializeMonitoring()
  }

  private initializeMonitoring(): void {
    // Only monitor if sampling allows
    if (Math.random() > this.config.sampleRate) return

    // Monitor Core Web Vitals
    getCLS(this.handleMetric.bind(this), true)
    getFCP(this.handleMetric.bind(this))
    getFID(this.handleMetric.bind(this))
    getLCP(this.handleMetric.bind(this), true)
    getTTFB(this.handleMetric.bind(this))

    this.setupReporting()
  }

  private handleMetric(metric: any): void {
    const performanceMetric = {
      name: metric.name,
      value: metric.value,
      rating: this.getRating(metric.name, metric.value),
      delta: metric.delta || 0,
      id: metric.id,
      navigationType: this.getNavigationType()
    }

    this.metrics.set(metric.name, performanceMetric)
    this.queue.push(performanceMetric)

    // Immediate reporting for poor metrics
    if (performanceMetric.rating === 'poor') {
      this.reportMetrics([performanceMetric], 'urgent')
    }
  }

  private getRating(name: string, value: number): 'good' | 'needs-improvement' | 'poor' {
    const thresholds = this.config.thresholds[name as keyof typeof this.config.thresholds]
    if (!thresholds) return 'good'

    if (value <= thresholds.good) return 'good'
    if (value <= thresholds.poor) return 'needs-improvement'
    return 'poor'
  }

  private setupReporting(): void {
    // Report metrics periodically
    setInterval(() => {
      if (this.queue.length > 0) {
        this.reportMetrics([...this.queue])
        this.queue = []
      }
    }, 30000) // Every 30 seconds

    // Report on page unload
    window.addEventListener('beforeunload', () => {
      if (this.queue.length > 0) {
        this.reportMetrics([...this.queue], 'beacon')
      }
    })

    // Report on visibility change
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden' && this.queue.length > 0) {
        this.reportMetrics([...this.queue], 'beacon')
        this.queue = []
      }
    })
  }

  private async reportMetrics(metrics: any[], method: 'fetch' | 'beacon' | 'urgent' = 'fetch'): Promise<void> {
    if (!this.config.enableAnalytics) return

    try {
      const payload = {
        metrics,
        timestamp: Date.now(),
        url: window.location.href,
        userAgent: navigator.userAgent,
        connection: this.getConnectionInfo(),
        viewport: {
          width: window.innerWidth,
          height: window.innerHeight
        }
      }

      if (method === 'beacon' && 'sendBeacon' in navigator) {
        navigator.sendBeacon(this.config.reportingEndpoint, JSON.stringify(payload))
      } else {
        await fetch(this.config.reportingEndpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          keepalive: method === 'beacon'
        })
      }
    } catch (error) {
      console.error('Failed to report performance metrics:', error)
    }
  }

  private getConnectionInfo(): any {
    if ('connection' in navigator) {
      const conn = (navigator as any).connection
      return {
        effectiveType: conn.effectiveType,
        downlink: conn.downlink,
        rtt: conn.rtt,
        saveData: conn.saveData
      }
    }
    return {}
  }

  private getNavigationType(): string {
    if ('navigation' in performance) {
      const nav = performance.navigation as any
      switch (nav.type) {
        case 0: return 'navigate'
        case 1: return 'reload'
        case 2: return 'back_forward'
        default: return 'unknown'
      }
    }
    return 'unknown'
  }

  getCurrentMetrics(): Record<string, number> {
    const current: Record<string, number> = {}
    this.metrics.forEach((metric, name) => {
      current[name] = metric.value
    })
    return current
  }

  getPerformanceScore(): number {
    const scores = {
      lcp: this.getMetricScore('LCP'),
      fid: this.getMetricScore('FID'),
      cls: this.getMetricScore('CLS')
    }

    return (scores.lcp + scores.fid + scores.cls) / 3
  }

  private getMetricScore(name: string): number {
    const metric = this.metrics.get(name)
    if (!metric) return 100

    switch (metric.rating) {
      case 'good': return 100
      case 'needs-improvement': return 75
      case 'poor': return 25
      default: return 100
    }
  }
}

// Initialize performance monitoring
export const performanceMonitor = new CoreWebVitalsMonitor(performanceConfig)
```

## Optimization Strategies

### LCP Optimization

**Target**: Largest Contentful Paint ≤2.5s

**Common Causes**:
- Large unoptimized images
- Slow server response time
- Render-blocking resources
- Client-side rendering delays

**Solutions**:
```typescript
// 1. Preload critical resources
<link rel="preload" as="image" href="/hero.webp" fetchpriority="high" />

// 2. Optimize images with Next.js Image
import Image from 'next/image'

<Image
  src="/hero.webp"
  width={1200}
  height={600}
  priority // Preload above-the-fold images
  alt="Hero image"
/>

// 3. Remove unused CSS
// Use PurgeCSS or similar to remove unused styles

// 4. Optimize fonts
<link
  rel="preload"
  href="/fonts/primary.woff2"
  as="font"
  type="font/woff2"
  crossOrigin="anonymous"
/>
```

### FID Optimization

**Target**: First Input Delay ≤100ms

**Common Causes**:
- Long JavaScript tasks blocking main thread
- Large JavaScript bundles
- Heavy third-party scripts

**Solutions**:
```typescript
// 1. Code splitting by route
const ProductPage = lazy(() => import('./pages/ProductPage'))

// 2. Break up long tasks
function processLargeDataset(data: any[]) {
  const chunks = chunkArray(data, 100)

  async function processChunk(chunk: any[]) {
    // Process chunk
    await new Promise(resolve => setTimeout(resolve, 0)) // Yield to browser
  }

  chunks.forEach(processChunk)
}

// 3. Use web workers for heavy computation
const worker = new Worker('/workers/heavy-computation.js')
worker.postMessage({ task: 'process-data', data })

// 4. Use requestIdleCallback for non-critical work
requestIdleCallback(() => {
  // Non-critical analytics, logging
})
```

### CLS Optimization

**Target**: Cumulative Layout Shift ≤0.1

**Common Causes**:
- Images without dimensions
- Ads/embeds/iframes without reserved space
- Dynamic content inserted above existing content
- Web fonts causing FOIT/FOUT

**Solutions**:
```typescript
// 1. Set explicit dimensions for images
<Image
  src="/product.jpg"
  width={800}
  height={600}
  alt="Product"
/>

// 2. Reserve space with aspect-ratio
<div style={{ aspectRatio: '16/9' }}>
  <iframe src="..." />
</div>

// 3. Preload fonts to prevent layout shifts
<link
  rel="preload"
  href="/fonts/primary.woff2"
  as="font"
  type="font/woff2"
  crossOrigin="anonymous"
/>

// 4. Use font-display: optional to prevent FOUT
@font-face {
  font-family: 'Primary';
  src: url('/fonts/primary.woff2') format('woff2');
  font-display: optional;
}
```

## Performance Budgets

```json
{
  "budgets": [
    {
      "resourceSizes": [
        {
          "resourceType": "script",
          "budget": 200
        },
        {
          "resourceType": "stylesheet",
          "budget": 50
        },
        {
          "resourceType": "image",
          "budget": 500
        },
        {
          "resourceType": "font",
          "budget": 100
        }
      ]
    },
    {
      "timings": [
        {
          "metric": "lcp",
          "budget": 2500
        },
        {
          "metric": "fid",
          "budget": 100
        },
        {
          "metric": "cls",
          "budget": 0.1
        }
      ]
    }
  ]
}
```

## CI/CD Integration

```yaml
# .github/workflows/performance.yml
name: Performance Check

on: [pull_request]

jobs:
  lighthouse:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4

      - name: Build app
        run: npm run build

      - name: Run Lighthouse
        uses: treosh/lighthouse-ci-action@v9
        with:
          urls: |
            http://localhost:3000
            http://localhost:3000/products
          budgetPath: ./budget.json
          temporaryPublicStorage: true
```
