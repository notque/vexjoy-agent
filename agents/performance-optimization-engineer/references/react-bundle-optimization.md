# React Bundle Optimization Reference
<!-- Loaded by performance-optimization-engineer when task involves bundle size, code splitting, imports, or tree shaking -->

## Dynamic Imports for Heavy Components
**Impact:** CRITICAL — directly affects TTI and LCP

Lazy-loading large components not needed on initial render keeps the main bundle small and reduces Time to Interactive. `React.lazy` combined with `Suspense` is the standard pattern; framework-specific wrappers like Next.js `dynamic()` provide the same capability with additional options like SSR control.

**Instead of:**
```tsx
import { MonacoEditor } from './monaco-editor'
// MonacoEditor (~300KB) bundles with the main chunk — loaded even for users who never open the editor

function CodePanel({ code }: { code: string }) {
  return <MonacoEditor value={code} />
}
```

**Use:**
```tsx
import { lazy, Suspense } from 'react'

const MonacoEditor = lazy(() =>
  import('./monaco-editor').then(m => ({ default: m.MonacoEditor }))
)

function CodePanel({ code }: { code: string }) {
  return (
    <Suspense fallback={<div>Loading editor...</div>}>
      <MonacoEditor value={code} />
    </Suspense>
  )
}
```

Next.js variant with SSR disabled:
```tsx
import dynamic from 'next/dynamic'

const MonacoEditor = dynamic(
  () => import('./monaco-editor').then(m => m.MonacoEditor),
  { ssr: false }
)
```

---

## Use Direct Imports for Tree-Shaking Efficiency
**Impact:** CRITICAL — 200-800ms import cost, slow builds

Direct imports enable tree-shaking — bundlers can eliminate unused exports when import paths are specific. Barrel files (index files that re-export many modules) force the bundler to load every module in the barrel before it can determine what to eliminate. Popular libraries can have up to 10,000 re-exports, adding 200-800ms on every cold start.

**Instead of:**
```tsx
import { Check, X, Menu } from 'lucide-react'
// Loads 1,583+ modules — bundler must process all before tree-shaking

import { Button, TextField } from '@mui/material'
// Loads 2,225+ modules
```

**Use (direct import path):**
```tsx
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
// Loads only what you use
```

For Next.js 13.5+, the `optimizePackageImports` config option transforms barrel imports at build time without requiring manual path changes:
```js
// next.config.js
module.exports = {
  experimental: {
    optimizePackageImports: ['lucide-react', '@mui/material']
  }
}
// Standard import syntax still works, Next.js rewrites to direct paths
```

TypeScript note: some libraries (notably `lucide-react`) do not ship `.d.ts` files for subpath imports. Verify the library exports types for its subpaths before switching to direct imports in strict TypeScript projects.

Libraries commonly affected: `lucide-react`, `@mui/material`, `@mui/icons-material`, `@tabler/icons-react`, `react-icons`, `@headlessui/react`, `@radix-ui/react-*`, `lodash`, `ramda`, `date-fns`, `rxjs`, `react-use`.

Typical gains: 15-70% faster dev boot, 28% faster builds, 40% faster cold starts.

---

## Conditional Module Loading
**Impact:** HIGH — loads large data only when a feature is activated

Loading modules conditionally at runtime — rather than statically at startup — keeps the initial bundle lean. The module only downloads when the user actually needs the feature.

**Use:**
```tsx
function AnimationPlayer({
  enabled,
  setEnabled
}: {
  enabled: boolean
  setEnabled: React.Dispatch<React.SetStateAction<boolean>>
}) {
  const [frames, setFrames] = useState<Frame[] | null>(null)

  useEffect(() => {
    if (enabled && !frames) {
      import('./animation-frames.js')
        .then(mod => setFrames(mod.frames))
        .catch(() => setEnabled(false))
    }
  }, [enabled, frames, setEnabled])

  if (!frames) return <Skeleton />
  return <Canvas frames={frames} />
}
```

The dynamic `import()` inside `useEffect` prevents the module from being included in the SSR bundle, reducing server bundle size and build time as a side effect.

---

## Defer Non-Critical Third-Party Scripts
**Impact:** MEDIUM — loads after hydration, does not block interactivity

Analytics, logging, and error tracking do not block user interaction. Loading them after the page hydrates keeps them off the critical path.

**Instead of:**
```tsx
// Statically imported — always in the main bundle
import { Analytics } from 'some-analytics-library'

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  )
}
```

**Use (React.lazy for post-hydration load):**
```tsx
import { lazy, Suspense } from 'react'

const Analytics = lazy(() =>
  import('some-analytics-library').then(m => ({ default: m.Analytics }))
)

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        {children}
        <Suspense fallback={null}>
          <Analytics />
        </Suspense>
      </body>
    </html>
  )
}
```

Next.js variant with explicit SSR opt-out:
```tsx
import dynamic from 'next/dynamic'

const Analytics = dynamic(
  () => import('@vercel/analytics/react').then(m => m.Analytics),
  { ssr: false }
)
```

---

## Preload Based on User Intent Signals
**Impact:** MEDIUM — reduces perceived latency when users navigate to heavy features

Triggering dynamic imports on hover or focus starts the download before the user clicks, so the component is ready (or nearly ready) when needed. This pattern works with any dynamic import — no framework-specific API required.

**Use (preload on hover/focus):**
```tsx
function EditorButton({ onClick }: { onClick: () => void }) {
  const preload = () => {
    void import('./monaco-editor')
  }

  return (
    <button
      onMouseEnter={preload}
      onFocus={preload}
      onClick={onClick}
    >
      Open Editor
    </button>
  )
}
```

**Use (preload when feature flag activates):**
```tsx
function FlagsProvider({ children, flags }: Props) {
  useEffect(() => {
    if (flags.editorEnabled) {
      void import('./monaco-editor').then(mod => mod.init())
    }
  }, [flags.editorEnabled])

  return (
    <FlagsContext.Provider value={flags}>
      {children}
    </FlagsContext.Provider>
  )
}
```

The `void` operator discards the promise return value explicitly, signaling that the import is intentionally fire-and-forget.

---
