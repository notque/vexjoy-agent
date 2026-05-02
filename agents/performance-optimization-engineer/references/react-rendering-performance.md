# React Rendering Performance Reference
<!-- Loaded by performance-optimization-engineer when task involves rendering, layout, CLS, hydration, or visual performance -->

## CSS content-visibility for Long Lists
**Impact:** HIGH — 10x improvement for 1000+ item lists

`content-visibility: auto` skips layout/paint for off-screen items. `contain-intrinsic-size` provides a placeholder size for accurate scrollbar.

```css
.message-item {
  content-visibility: auto;
  contain-intrinsic-size: 0 80px; /* estimated item height */
}
```

```tsx
function MessageList({ messages }: { messages: Message[] }) {
  return (
    <div className="overflow-y-auto h-screen">
      {messages.map(msg => (
        <div key={msg.id} className="message-item">
          <Avatar user={msg.author} />
          <div>{msg.content}</div>
        </div>
      ))}
    </div>
  )
}
```

---

## Hoist Static JSX Outside Render
**Impact:** LOW — avoids object re-creation per render

Static elements that never change can be declared at module scope. Especially valuable for large static SVG nodes.

**Instead of:**
```tsx
function Container() {
  return (
    <div>
      {loading && <div className="animate-pulse h-20 bg-gray-200" />}
    </div>
  )
}
```

**Use:**
```tsx
const loadingSkeleton = (
  <div className="animate-pulse h-20 bg-gray-200" />
)

function Container() {
  return (
    <div>
      {loading && loadingSkeleton}
    </div>
  )
}
```

Note: React Compiler auto-hoists static JSX — manual hoisting unnecessary if enabled.

---

## SVG Precision Optimization
**Impact:** LOW — reduces file size

Precision beyond 1 decimal place is rarely visible. Automate with SVGO:

```bash
npx svgo --precision=1 --multipass icon.svg
```

---

## Hydration Mismatch Prevention
**Impact:** MEDIUM — avoids visual flicker and hydration errors

Client-side storage (localStorage, cookies) causes flash when read in `useEffect`. Inject a synchronous inline script that runs before React hydrates:

```tsx
function ThemeWrapper({ children }: { children: ReactNode }) {
  return (
    <>
      <div id="theme-wrapper">
        {children}
      </div>
      <script
        dangerouslySetInnerHTML={{
          __html: `
            (function() {
              try {
                var theme = localStorage.getItem('theme') || 'light';
                var el = document.getElementById('theme-wrapper');
                if (el) el.className = theme;
              } catch (e) {}
            })();
          `,
        }}
      />
    </>
  )
}
```

Useful for: theme toggles, user preferences, authentication states, locale settings.

---

## Script defer and async Placement
**Impact:** HIGH — eliminates render-blocking

- `defer`: downloads in parallel, executes after HTML parsing, maintains order — DOM-dependent scripts
- `async`: downloads in parallel, executes immediately when ready, no order guarantee — analytics

```html
<script src="https://example.com/analytics.js" async></script>
<script src="/scripts/utils.js" defer></script>
```

Next.js variant:
```tsx
import Script from 'next/script'

<Script src="https://example.com/analytics.js" strategy="afterInteractive" />
<Script src="/scripts/utils.js" strategy="beforeInteractive" />
```

---

## Explicit Conditional Rendering
**Impact:** LOW — prevents rendering `0` or `NaN` as visible text

`&&` renders falsy values `0` and `NaN` as visible text. Use explicit ternary:

```tsx
{count > 0 ? <span className="badge">{count}</span> : null}
```

---

## React DOM Resource Hints
**Impact:** HIGH — reduces load time for critical resources

```tsx
import { prefetchDNS, preconnect, preload, preinit } from 'react-dom'

export default function App() {
  prefetchDNS('https://analytics.example.com')
  preconnect('https://api.example.com')
  preload('/fonts/inter.woff2', { as: 'font', type: 'font/woff2', crossOrigin: 'anonymous' })
  preinit('/styles/critical.css', { as: 'style' })
  return <main>{/* content */}</main>
}
```

Preload modules on hover:
```tsx
<a href="/dashboard" onMouseEnter={() => preloadModule('/dashboard.js', { as: 'script' })}>
  Dashboard
</a>
```

| API | Use case |
|-----|----------|
| `prefetchDNS` | Third-party domains you will connect to later |
| `preconnect` | APIs or CDNs you will fetch from immediately |
| `preload` | Critical resources needed for current page |
| `preloadModule` | JS modules for likely next navigation |
| `preinit` | Stylesheets/scripts that must execute early |
| `preinitModule` | ES modules that must execute early |

Reference: [React DOM Resource Preloading APIs](https://react.dev/reference/react-dom#resource-preloading-apis)

---

## useTransition for Loading States
**Impact:** LOW — reduces re-renders, auto-resets on error

`useTransition` provides `isPending` that auto-resets even on throw. Eliminates forgotten `setIsLoading(false)` in error paths. New transitions cancel pending ones.

```tsx
import { useTransition, useState } from 'react'

function SearchResults() {
  const [results, setResults] = useState([])
  const [isPending, startTransition] = useTransition()

  const handleSearch = (value: string) => {
    startTransition(async () => {
      const data = await fetchResults(value)
      setResults(data)
    })
  }

  return (
    <>
      <input onChange={e => handleSearch(e.target.value)} />
      {isPending && <Spinner />}
      <ResultsList results={results} />
    </>
  )
}
```

Reference: [useTransition](https://react.dev/reference/react/useTransition)

---

## Activity Component for Show/Hide
**Impact:** MEDIUM — preserves state and DOM for frequently-toggled components

`<Activity>` keeps tree mounted and state intact when hidden. Avoids unmount/remount cost.

```tsx
import { Activity } from 'react'

function Dropdown({ isOpen }: Props) {
  return (
    <Activity mode={isOpen ? 'visible' : 'hidden'}>
      <ExpensiveMenu />
    </Activity>
  )
}
```

Use when: expensive initialization, stateful forms, animations needing DOM continuity.

---

## SVG Animation Wrapping
**Impact:** LOW — enables hardware acceleration for SVG animations

Browsers lack GPU acceleration for CSS animations on SVG elements directly. Wrap SVG in a `<div>` and animate the wrapper:

```tsx
function LoadingSpinner() {
  return (
    <div className="animate-spin">
      <svg width="24" height="24" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" stroke="currentColor" />
      </svg>
    </div>
  )
}
```

Applies to `transform`, `opacity`, `translate`, `scale`, `rotate` on SVG elements.

---

## Suppress Expected Hydration Warnings
**Impact:** LOW-MEDIUM — eliminates noisy console warnings for known server/client differences

For intentionally different values (timestamps, random IDs, timezone-formatted dates):

```tsx
<span suppressHydrationWarning>
  {new Date().toLocaleString()}
</span>
```

Apply at the specific element with the known mismatch, not at container level. Do not use to hide real bugs.

---
