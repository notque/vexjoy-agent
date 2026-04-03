# React Rendering Performance Reference
<!-- Loaded by performance-optimization-engineer when task involves rendering, layout, CLS, hydration, or visual performance -->

## CSS content-visibility for Long Lists
**Impact:** HIGH — faster initial render; 10x improvement for lists of 1000+ items

`content-visibility: auto` lets the browser skip layout and paint for off-screen items. For a list of 1000 messages, the browser skips those calculations for ~990 off-screen items. `contain-intrinsic-size` provides a placeholder size so the scrollbar remains accurate without forcing layout of every item.

**Use:**
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
**Impact:** LOW — avoids object re-creation on every render

JSX evaluates to object creation. Static elements that never change can be declared once at module scope rather than recreated on every render call. This is especially valuable for large static SVG nodes.

**Instead of:**
```tsx
function Container() {
  // New object created every render
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

Note: If React Compiler is enabled in your project, it automatically hoists static JSX — manual hoisting is unnecessary in that case.

---

## SVG Precision Optimization
**Impact:** LOW — reduces file size

SVG coordinate precision beyond 1 decimal place is rarely visible at typical display sizes. Reducing precision shrinks file size with no perceptible quality loss. The optimal precision depends on the viewBox size.

**Instead of:**
```svg
<path d="M 10.293847 20.847362 L 30.938472 40.192837" />
```

**Use:**
```svg
<path d="M 10.3 20.8 L 30.9 40.2" />
```

Automate with SVGO:
```bash
npx svgo --precision=1 --multipass icon.svg
```

---

## Hydration Mismatch Prevention
**Impact:** MEDIUM — avoids visual flicker and hydration errors

When rendering content that depends on client-side storage (localStorage, cookies), a naive `useEffect` approach causes a visible flash: the server renders a default value, hydration completes, then the effect runs and updates to the real value. Injecting a synchronous inline script that runs before React hydrates avoids both the SSR error and the flash.

**Instead of (SSR error):**
```tsx
function ThemeWrapper({ children }: { children: ReactNode }) {
  const theme = localStorage.getItem('theme') || 'light' // throws on server
  return <div className={theme}>{children}</div>
}
```

**Instead of (visible flash):**
```tsx
function ThemeWrapper({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState('light')
  useEffect(() => {
    const stored = localStorage.getItem('theme')
    if (stored) setTheme(stored) // runs after hydration — user sees flash
  }, [])
  return <div className={theme}>{children}</div>
}
```

**Use (no flash, no hydration error):**
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

The inline script executes synchronously before the first paint, so the DOM already has the correct value when React hydrates — no mismatch, no flash.

Useful for: theme toggles, user preferences, authentication states, locale settings.

---

## Script defer and async Placement
**Impact:** HIGH — eliminates render-blocking

Script tags without `defer` or `async` block HTML parsing while downloading and executing, delaying First Contentful Paint and Time to Interactive. Adding the correct attribute costs nothing and gains significant render-blocking elimination.

- `defer`: downloads in parallel, executes after HTML parsing, maintains order — use for DOM-dependent scripts
- `async`: downloads in parallel, executes immediately when ready, no order guarantee — use for independent scripts like analytics

**Instead of:**
```html
<script src="https://example.com/analytics.js"></script>
<script src="/scripts/utils.js"></script>
```

**Use:**
```html
<script src="https://example.com/analytics.js" async></script>
<script src="/scripts/utils.js" defer></script>
```

In React:
```tsx
export default function Document() {
  return (
    <html>
      <head>
        <script src="https://example.com/analytics.js" async />
        <script src="/scripts/utils.js" defer />
      </head>
      <body>{/* content */}</body>
    </html>
  )
}
```

Next.js variant using the `Script` component with `strategy` prop:
```tsx
import Script from 'next/script'

<Script src="https://example.com/analytics.js" strategy="afterInteractive" />
<Script src="/scripts/utils.js" strategy="beforeInteractive" />
```

---

## Explicit Conditional Rendering
**Impact:** LOW — prevents rendering `0` or `NaN` as visible text

The `&&` operator renders any falsy value that is not `false`, `null`, or `undefined` — notably `0` and `NaN` both render as visible text. Explicit ternary operators avoid this class of bug entirely.

**Instead of:**
```tsx
function Badge({ count }: { count: number }) {
  return (
    <div>
      {count && <span className="badge">{count}</span>}
      {/* When count = 0, renders: <div>0</div> */}
    </div>
  )
}
```

**Use:**
```tsx
function Badge({ count }: { count: number }) {
  return (
    <div>
      {count > 0 ? <span className="badge">{count}</span> : null}
    </div>
  )
}
```

---

## React DOM Resource Hints
**Impact:** HIGH — reduces load time for critical resources

React DOM provides APIs to hint the browser about resources it will need. These are especially useful in server components: the hints travel with the HTML response, so the browser can start loading resources before scripts execute.

```tsx
import { prefetchDNS, preconnect, preload, preinit } from 'react-dom'

export default function App() {
  prefetchDNS('https://analytics.example.com')      // resolve DNS early
  preconnect('https://api.example.com')              // DNS + TCP + TLS
  preload('/fonts/inter.woff2', {
    as: 'font',
    type: 'font/woff2',
    crossOrigin: 'anonymous'
  })
  preinit('/styles/critical.css', { as: 'style' })  // fetch and apply

  return <main>{/* content */}</main>
}
```

Preload modules for likely next navigation on hover:
```tsx
import { preloadModule } from 'react-dom'

function Navigation() {
  return (
    <nav>
      <a
        href="/dashboard"
        onMouseEnter={() => preloadModule('/dashboard.js', { as: 'script' })}
      >
        Dashboard
      </a>
    </nav>
  )
}
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
**Impact:** LOW — reduces re-renders and improves code clarity

`useTransition` provides built-in `isPending` state that automatically resets even when a transition throws. It also lets React keep the UI responsive by marking the update as non-urgent. Compared to manual `useState` + `setIsLoading(true/false)` pairs, it eliminates the risk of forgetting to reset loading state in error paths.

**Instead of:**
```tsx
function SearchResults() {
  const [isLoading, setIsLoading] = useState(false)

  const handleSearch = async (value: string) => {
    setIsLoading(true)
    const data = await fetchResults(value)
    setResults(data)
    setIsLoading(false) // forgotten in error paths = stuck spinner
  }

  return (
    <>
      <input onChange={e => handleSearch(e.target.value)} />
      {isLoading && <Spinner />}
    </>
  )
}
```

**Use:**
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

New transitions automatically cancel pending ones, so rapid input changes cancel earlier in-flight fetches.

Reference: [useTransition](https://react.dev/reference/react/useTransition)

---

## Activity Component for Show/Hide
**Impact:** MEDIUM — preserves state and DOM for frequently-toggled components

React's `<Activity>` keeps the component tree mounted and state intact when switching to `hidden` mode, then makes it visible again without re-initialization. This avoids the cost of unmounting and remounting expensive components on every toggle.

**Use:**
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

Use when: components have expensive initialization, stateful forms that should not reset on hide, or animations that need DOM continuity.

---

## SVG Animation Wrapping
**Impact:** LOW — enables hardware acceleration for SVG animations

Many browsers do not have hardware acceleration for CSS animations applied directly to SVG elements. Wrapping the SVG in a `<div>` and animating the wrapper allows the browser to use GPU compositing for smooth animations.

**Instead of:**
```tsx
function LoadingSpinner() {
  return (
    <svg className="animate-spin" width="24" height="24" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" stroke="currentColor" />
    </svg>
  )
}
```

**Use:**
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

Applies to all CSS transforms and transitions (`transform`, `opacity`, `translate`, `scale`, `rotate`) on SVG elements.

---

## Suppress Expected Hydration Warnings
**Impact:** LOW-MEDIUM — eliminates noisy console warnings for known server/client differences

Some values are intentionally different between server render and client hydration: timestamps, random IDs, timezone-formatted dates. `suppressHydrationWarning` tells React to skip the mismatch warning for that specific element. Use it only for genuinely expected differences — do not use it to hide real bugs.

**Instead of:**
```tsx
function Timestamp() {
  return <span>{new Date().toLocaleString()}</span>
  // Warning: Prop `children` did not match...
}
```

**Use:**
```tsx
function Timestamp() {
  return (
    <span suppressHydrationWarning>
      {new Date().toLocaleString()}
    </span>
  )
}
```

Apply at the specific element with the known mismatch, not at a container level.

---
