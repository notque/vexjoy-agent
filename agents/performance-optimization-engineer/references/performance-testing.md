# Performance Testing Reference
<!-- Loaded by performance-optimization-engineer when task involves Lighthouse CI, performance budgets, regression testing, synthetic monitoring, or CI/CD performance gates -->

> **Scope**: Automated performance testing in CI/CD, Lighthouse CI setup, performance budgets, and regression detection. Does NOT cover RUM/real-user monitoring (see `metrics-and-monitoring.md`).
> **Version range**: Lighthouse CI 0.12+, @lhci/cli 0.12+
> **Generated**: 2026-04-09

---

## Overview

Synthetic performance testing in CI/CD catches regressions before they reach production. The most common failure mode is running Lighthouse manually during development and never catching performance regressions in CI — so bundle size grows 20% over 6 months with no alerts. Performance budgets with automated gates prevent this category of problem entirely.

---

## Pattern Table

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `@lhci/cli` | Lighthouse CI — runs Lighthouse in CI, stores results, enforces assertions | Primary CI performance gate |
| `bundlesize` / `size-limit` | Bundle size gates — fail CI if JS bundle exceeds limit | Add alongside @lhci when bundle size is the primary concern |
| `playwright` + tracing | Real browser performance measurement with network control | Integration tests that need timing precision |
| `web-vitals` + Vitest | Unit-level performance assertions | Catching regressions in specific components |

---

## Correct Patterns

### Lighthouse CI Configuration with Assertions

`.lighthouserc.js` at repo root is the standard config location.

```javascript
// .lighthouserc.js
module.exports = {
  ci: {
    collect: {
      // Run against the built app served locally
      url: ['http://localhost:3000/', 'http://localhost:3000/products'],
      numberOfRuns: 3, // Average over 3 runs to reduce variance
      startServerCommand: 'npm run start', // Production build
      startServerReadyPattern: 'ready on',
    },
    assert: {
      // Fail CI if these thresholds aren't met
      assertions: {
        'categories:performance': ['error', { minScore: 0.9 }], // 90+ score
        'categories:accessibility': ['warn', { minScore: 0.9 }],
        'first-contentful-paint': ['error', { maxNumericValue: 2000 }], // 2s
        'largest-contentful-paint': ['error', { maxNumericValue: 2500 }], // 2.5s
        'total-blocking-time': ['error', { maxNumericValue: 300 }],
        'cumulative-layout-shift': ['error', { maxNumericValue: 0.1 }],
        // Bundle size gates via Lighthouse
        'total-byte-weight': ['error', { maxNumericValue: 1_600_000 }], // 1.6MB
        'uses-optimized-images': ['warn', {}],
        'unused-javascript': ['warn', { maxLength: 2 }], // Max 2 unused JS chunks
      },
    },
    upload: {
      target: 'temporary-public-storage', // Free LHCI storage for 30 days
      // Or: target: 'lhci', serverBaseUrl: 'https://lhci.yourcompany.com'
    },
  },
}
```

**Why**: `numberOfRuns: 3` is essential — single-run Lighthouse scores have 10-15 point variance on CI machines. Assertions use `'error'` to fail CI (not just warn). The upload step stores historical data so you can see score trends over time.

---

### GitHub Actions Workflow for Lighthouse CI

```yaml
# .github/workflows/lighthouse.yml
name: Lighthouse CI
on: [push, pull_request]

jobs:
  lighthouse:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
      - run: npm ci
      - run: npm run build
      - name: Run Lighthouse CI
        run: |
          npm install -g @lhci/cli@0.14
          lhci autorun
        env:
          LHCI_GITHUB_APP_TOKEN: ${{ secrets.LHCI_GITHUB_APP_TOKEN }}
```

**Why**: Running `lhci autorun` reads `.lighthouserc.js` automatically. The `LHCI_GITHUB_APP_TOKEN` enables PR status checks and comments. Without it, Lighthouse results don't appear inline in PRs.

---

### size-limit for Bundle Size Gates

```javascript
// package.json
{
  "size-limit": [
    {
      "path": ".next/static/chunks/main-*.js",
      "limit": "80 kB",
      "gzip": true
    },
    {
      "path": ".next/static/chunks/pages/**/*.js",
      "limit": "50 kB",
      "gzip": true,
      "ignore": ["node_modules"]
    }
  ],
  "scripts": {
    "size": "size-limit",
    "analyze": "ANALYZE=true next build"
  }
}
```

```yaml
# Add to CI workflow
- name: Check bundle size
  run: npx size-limit --json > size-report.json
- name: Report size
  uses: andresz1/size-limit-action@v1
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
```

**Why**: `size-limit` measures gzipped output, which is what the browser actually downloads. Failing CI on bundle size regressions prevents the incremental growth pattern where no single PR is "bad" but 6 months of PRs add 150KB.

---

## Anti-Pattern Catalog

### ❌ Running Lighthouse Once (Not Averaging Multiple Runs)

**Detection**:
```bash
grep -rn "numberOfRuns\|number-of-runs" .lighthouserc.* .lhci* 2>/dev/null
# If no output: numberOfRuns is not configured (defaults to 1)
```

**What it looks like**:
```javascript
// .lighthouserc.js
module.exports = {
  ci: {
    collect: {
      url: ['http://localhost:3000'],
      // numberOfRuns missing — defaults to 1
    },
  },
}
```

**Why wrong**: A single Lighthouse run has 10-15 point score variance on CI machines (shared CPU, GC pauses, network jitter). A score of 85 one run, 72 the next — both from the same code. Single-run CI gates either false-positive (blocking good PRs) or miss real regressions.

**Fix**:
```javascript
collect: {
  url: ['http://localhost:3000'],
  numberOfRuns: 3, // Minimum for stable averages
},
```

---

### ❌ Using `warn` Instead of `error` for Critical Thresholds

**Detection**:
```bash
grep -rn "largest-contentful-paint\|first-contentful-paint\|total-blocking-time" .lighthouserc.*
# Check if it uses 'warn' instead of 'error' for core metrics
```

**What it looks like**:
```javascript
assertions: {
  'largest-contentful-paint': ['warn', { maxNumericValue: 2500 }],
  // 'warn' doesn't fail CI — regressions ship silently
},
```

**Why wrong**: `warn` level assertions appear in logs but do NOT fail the CI step. LCP regressions will accumulate indefinitely. The only way a performance budget prevents regressions is if it fails the build.

**Fix**:
```javascript
assertions: {
  'largest-contentful-paint': ['error', { maxNumericValue: 2500 }], // Fails CI
  'categories:performance': ['error', { minScore: 0.9 }],
},
```

---

### ❌ Running Lighthouse Against Development Server

**Detection**:
```bash
grep -rn "next dev\|npm run dev\|yarn dev" .lighthouserc.* .github/workflows/*.yml
```

**What it looks like**:
```javascript
collect: {
  startServerCommand: 'npm run dev', // Development server!
},
```

**Why wrong**: `next dev` doesn't minify, doesn't split bundles, doesn't optimize images. A dev server Lighthouse score is meaningless for production performance — typically 20-40 points lower than production. You're testing the wrong artifact.

**Fix**:
```javascript
collect: {
  startServerCommand: 'npm run build && npm run start', // Production build
  startServerReadyPattern: 'ready on',
},
```

---

### ❌ No Performance Budget in CI for Bundle Size

**Detection**:
```bash
# Check for any bundle size monitoring
grep -rn "size-limit\|bundlesize\|bundle-size\|ANALYZE" package.json
grep -rn "size-limit\|bundlesize" .github/workflows/*.yml
# If neither exists: no automated bundle regression detection
```

**Why wrong**: Without automated bundle size gates, bundle size grows incrementally. Each PR adds "just a small dependency" until the main bundle is 500KB and LCP is 4.5s. Manual review doesn't catch this — bundle analysis is only done when performance is already bad.

**Fix**: Add `size-limit` with `error` thresholds to CI. Start with current bundle size as the baseline and set limits 10% above it to allow headroom, then tighten over time.

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| `lhci: No assertions failed but score fluctuates 15+ points` | `numberOfRuns: 1` — high variance | Set `numberOfRuns: 3` in collect config |
| `AssertionError: largest-contentful-paint failure` in CI but not local | CI machine is slower than dev machine | Increase `maxNumericValue` for CI or use percentile-based assertions |
| `Error: ECONNREFUSED` in Lighthouse CI | Server not ready when Lighthouse starts | Add `startServerReadyPattern` that matches your server's ready message |
| `lhci autorun: command not found` | `@lhci/cli` not installed | Add `npm install -g @lhci/cli` before `lhci autorun` in CI |
| size-limit reports 0KB for Next.js chunks | Glob pattern doesn't match `.next` build output | Use `.next/static/chunks/**/*.js` glob pattern |

---

## Detection Commands Reference

```bash
# Check if Lighthouse CI is configured
ls .lighthouserc.js .lighthouserc.json .lighthouserc.yaml 2>/dev/null

# Check if performance CI job exists
grep -rn "lighthouse\|lhci" .github/workflows/ 2>/dev/null

# Check numberOfRuns configuration
grep -rn "numberOfRuns" .lighthouserc* 2>/dev/null

# Check if using dev server (incorrect) vs build server (correct)
grep -rn "startServerCommand" .lighthouserc* 2>/dev/null

# Check for bundle size gates
grep -rn "size-limit\|bundlesize" package.json .github/workflows/ 2>/dev/null

# Analyze current Next.js bundle manually
ANALYZE=true next build 2>/dev/null || npx @next/bundle-analyzer 2>/dev/null
```

---

## See Also

- `metrics-and-monitoring.md` — RUM implementation for production monitoring
- `react-bundle-optimization.md` — code splitting patterns that reduce bundle size
- `nextjs-optimization.md` — Next.js-specific patterns that affect Lighthouse scores
