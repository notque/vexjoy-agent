# Bundle Optimization

Bundle analysis and optimization strategies for JavaScript applications.

## Bundle Size Targets

| Application Type | Initial JS | Initial CSS | Images | Total |
|------------------|-----------|-------------|--------|-------|
| Marketing Site | <150KB | <50KB | <500KB | <700KB |
| E-commerce | <250KB | <75KB | <800KB | <1.1MB |
| SaaS Dashboard | <400KB | <100KB | <300KB | <800KB |
| Content Site | <200KB | <60KB | <600KB | <860KB |

## Bundle Analysis Workflow

```bash
# 1. Build with stats
npm run build -- --profile --json > stats.json

# 2. Analyze bundle
npx webpack-bundle-analyzer stats.json

# 3. Check for duplicates
npx webpack-bundle-analyzer stats.json --mode static

# 4. Generate report
webpack-bundle-analyzer stats.json --mode json --report bundle-report.json
```

## Common Bundle Problems

### 1. Large Dependencies

**Problem**: Single library taking >100KB

**Detection**:
```bash
npx webpack-bundle-analyzer build/stats.json
# Look for packages >100KB in treemap
```

**Solutions**:
- Replace with smaller alternative
- Use tree-shakeable ES modules version
- Lazy load if not critical
- Import specific functions only

**Example**:
```typescript
// BAD: Import entire library (300KB)
import _ from 'lodash'
const result = _.uniq(array)

// GOOD: Import specific function (5KB)
import uniq from 'lodash/uniq'
const result = uniq(array)

// BETTER: Use native alternative (0KB)
const result = [...new Set(array)]
```

### 2. Duplicate Modules

**Problem**: Same module bundled multiple times

**Detection**:
```bash
npx webpack-bundle-analyzer build/stats.json
# Look for duplicate package names at different paths
```

**Solutions**:
- Configure webpack `resolve.alias`
- Update dependencies to use same version
- Use `splitChunks` optimization

**Example**:
```javascript
// webpack.config.js
module.exports = {
  optimization: {
    splitChunks: {
      chunks: 'all',
      cacheGroups: {
        vendor: {
          test: /[\\/]node_modules[\\/]/,
          name: 'vendors',
          priority: 10
        }
      }
    }
  },
  resolve: {
    alias: {
      // Force single version
      'react': path.resolve(__dirname, 'node_modules/react')
    }
  }
}
```

### 3. Unused Code

**Problem**: Dead code included in bundle

**Detection**:
```bash
# Check tree-shaking
npx webpack --mode production --analyze

# Check coverage in Chrome DevTools
# Coverage tab -> Record -> Reload
```

**Solutions**:
- Enable tree-shaking (use ES modules)
- Remove unused imports
- Use dynamic imports for code not needed initially
- Configure sideEffects in package.json

**Example**:
```json
// package.json
{
  "sideEffects": false  // Enable tree-shaking
}
```

```typescript
// BAD: Import entire module
import * as utils from './utils'

// GOOD: Import only what's needed
import { formatDate, formatCurrency } from './utils'
```

### 4. No Code Splitting

**Problem**: Everything in one bundle, slow initial load

**Solutions**:
```typescript
// Route-based code splitting
const ProductPage = lazy(() => import('./pages/ProductPage'))
const CartPage = lazy(() => import('./pages/CartPage'))

// Component-based code splitting (for large components)
const HeavyChart = lazy(() => import('./components/HeavyChart'))

// Feature-based code splitting
const AdminPanel = lazy(() => import('./features/admin'))
```

## Optimization Strategies

### 1. Code Splitting Configuration

```javascript
// next.config.js
module.exports = {
  webpack: (config) => {
    config.optimization.splitChunks = {
      chunks: 'all',
      cacheGroups: {
        default: false,
        vendors: false,
        // Vendor chunk
        vendor: {
          name: 'vendor',
          chunks: 'all',
          test: /node_modules/,
          priority: 20
        },
        // Common chunk
        common: {
          name: 'common',
          minChunks: 2,
          chunks: 'all',
          priority: 10,
          reuseExistingChunk: true,
          enforce: true
        }
      }
    }
    return config
  }
}
```

### 2. Dynamic Imports

```typescript
// Lazy load heavy libraries
async function generatePDF() {
  const { jsPDF } = await import('jspdf')
  const doc = new jsPDF()
  // Generate PDF
}

// Lazy load by condition
if (user.isAdmin) {
  const { AdminTools } = await import('./AdminTools')
  renderAdminTools(AdminTools)
}

// Lazy load on interaction
button.addEventListener('click', async () => {
  const { showModal } = await import('./modal')
  showModal()
})
```

### 3. Tree Shaking

```typescript
// Enable in package.json
{
  "sideEffects": [
    "*.css",
    "*.scss"
  ]
}

// Use named exports (tree-shakeable)
export function utilA() {}
export function utilB() {}

// Don't use default export of object (not tree-shakeable)
// BAD:
export default {
  utilA,
  utilB
}
```

### 4. Bundle Analysis Report

```typescript
interface BundleAnalysis {
  totalSize: number
  gzippedSize: number
  chunks: BundleChunk[]
  dependencies: DependencyInfo[]
  duplicates: DuplicateModule[]
}

interface BundleChunk {
  name: string
  size: number
  files: string[]
  isInitial: boolean
  isAsync: boolean
}

interface DependencyInfo {
  name: string
  version: string
  size: number
  isTreeShakeable: boolean
}

interface DuplicateModule {
  name: string
  instances: number
  totalWastedSize: number
}

function analyzeBundleSize(statsPath: string): BundleAnalysis {
  const stats = require(statsPath)

  const chunks = stats.chunks.map(chunk => ({
    name: chunk.names[0] || chunk.id,
    size: chunk.size,
    files: chunk.files,
    isInitial: chunk.initial,
    isAsync: !chunk.initial
  }))

  const dependencies = analyzeDependencies(stats.modules)
  const duplicates = findDuplicateModules(stats.modules)

  return {
    totalSize: stats.assets.reduce((sum, asset) => sum + asset.size, 0),
    gzippedSize: estimateGzippedSize(stats.assets),
    chunks,
    dependencies,
    duplicates
  }
}
```

## Before/After Validation

Always include before/after metrics in optimization reports:

```markdown
## Bundle Optimization Results

### Before
| Asset | Size | Gzipped |
|-------|------|---------|
| main.js | 450KB | 135KB |
| vendor.js | 200KB | 60KB |
| Total | 650KB | 195KB |

### After
| Asset | Size | Gzipped | Change |
|-------|------|---------|--------|
| main.js | 180KB | 54KB | -60% |
| vendor.js | 120KB | 36KB | -40% |
| Total | 300KB | 90KB | -54% |

### Optimizations Applied
1. Replaced moment.js with date-fns (-50KB)
2. Lazy loaded admin routes (-80KB)
3. Removed unused lodash functions (-30KB)
4. Optimized webpack splitChunks (-40KB)
```

## Performance Budget Enforcement

```json
// budget.json
{
  "budgets": [
    {
      "resourceSizes": [
        {
          "resourceType": "script",
          "budget": 200,
          "warning": 175
        },
        {
          "resourceType": "total",
          "budget": 500,
          "warning": 450
        }
      ]
    }
  ]
}
```

```yaml
# .github/workflows/budget.yml
name: Bundle Size Check

on: [pull_request]

jobs:
  check-bundle-size:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4

      - name: Install dependencies
        run: npm ci

      - name: Build
        run: npm run build

      - name: Check bundle size
        run: |
          npm run bundle-analyzer -- --json > bundle-stats.json
          node scripts/check-bundle-size.js

      - name: Comment PR
        uses: actions/github-script@v6
        with:
          script: |
            const stats = require('./bundle-stats.json')
            const comment = `
            ## Bundle Size Report

            | Asset | Size | Budget | Status |
            |-------|------|--------|--------|
            | main.js | ${stats.main.size}KB | 200KB | ${stats.main.status} |
            | vendor.js | ${stats.vendor.size}KB | 150KB | ${stats.vendor.status} |
            `
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment
            })
```
