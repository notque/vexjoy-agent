# Browser DOM Optimizations Reference
<!-- Loaded by performance-optimization-engineer when task involves DOM, CSS, requestIdleCallback, localStorage, RegExp, or batch reads/writes -->

Apply these patterns in hot paths: render loops, event handlers called frequently, data processing pipelines. Skip them for code that runs once or rarely — the gains are real but small in isolation, and they compound when applied to high-frequency code.

---

## Batch DOM and CSS Reads and Writes
**Impact:** MEDIUM — prevents forced synchronous layouts (layout thrashing)

Reading a layout property (`offsetWidth`, `getBoundingClientRect()`, `getComputedStyle()`) after making style changes forces the browser to synchronously reflow before returning the value. Batching all reads together and all writes together prevents this.

**Instead of:**
```typescript
function layoutThrashing(element: HTMLElement) {
  element.style.width = '100px'
  const width = element.offsetWidth  // forced reflow
  element.style.height = '200px'
  const height = element.offsetHeight // forced reflow again
}
```

**Use:**
```typescript
// Read phase first — all queries together
const rect = element.getBoundingClientRect()
const offsetWidth = element.offsetWidth

// Write phase after — all style changes together
element.style.width = '100px'
element.style.height = '200px'
```

Prefer CSS classes over inline styles when possible — toggling a class batches all style changes in one operation and keeps styles in the cached stylesheet:
```tsx
function Box({ isHighlighted }: { isHighlighted: boolean }) {
  return (
    <div className={isHighlighted ? 'highlighted-box' : ''}>
      Content
    </div>
  )
}
```

Reference: [Layout-forcing operations](https://gist.github.com/paulirish/5d52fb081b3570c81e3a)

---

## requestIdleCallback for Non-Urgent Work
**Impact:** MEDIUM — keeps UI responsive by deferring background tasks

Analytics, storage writes, prefetching, and lazy initialization do not need to run synchronously during user interactions. `requestIdleCallback` schedules them during browser idle periods, keeping the main thread free for rendering and input handling.

**Instead of:**
```typescript
function handleSearch(query: string) {
  const results = searchItems(query)
  setResults(results)

  analytics.track('search', { query })     // blocks main thread immediately
  saveToRecentSearches(query)              // blocks main thread immediately
}
```

**Use:**
```typescript
function handleSearch(query: string) {
  const results = searchItems(query)
  setResults(results)

  requestIdleCallback(() => analytics.track('search', { query }))
  requestIdleCallback(() => saveToRecentSearches(query))
}
```

With timeout for work that must complete eventually:
```typescript
requestIdleCallback(
  () => analytics.track('page_view', { path: location.pathname }),
  { timeout: 2000 }
)
```

Chunking large dataset processing:
```typescript
function processLargeDataset(items: Item[]) {
  let index = 0

  function processChunk(deadline: IdleDeadline) {
    while (index < items.length && deadline.timeRemaining() > 0) {
      processItem(items[index++])
    }
    if (index < items.length) requestIdleCallback(processChunk)
  }

  requestIdleCallback(processChunk)
}
```

Fallback for older environments:
```typescript
const scheduleIdleWork = window.requestIdleCallback ?? ((cb: () => void) => setTimeout(cb, 1))
```

When not to use: user-initiated actions needing immediate feedback, rendering updates the user is waiting for, time-sensitive operations.

---

## Cache Storage API Calls
**Impact:** LOW-MEDIUM — reduces expensive synchronous I/O

`localStorage`, `sessionStorage`, and `document.cookie` are synchronous and hit actual storage on every call. Caching reads in memory eliminates repeated I/O for the same key within a session.

**Instead of:**
```typescript
function getTheme() {
  return localStorage.getItem('theme') ?? 'light' // storage read on every call
}
```

**Use:**
```typescript
const storageCache = new Map<string, string | null>()

function getLocalStorage(key: string) {
  if (!storageCache.has(key)) {
    storageCache.set(key, localStorage.getItem(key))
  }
  return storageCache.get(key)
}

function setLocalStorage(key: string, value: string) {
  localStorage.setItem(key, value)
  storageCache.set(key, value) // keep cache in sync
}
```

Cookie caching:
```typescript
let cookieCache: Record<string, string> | null = null

function getCookie(name: string) {
  if (!cookieCache) {
    cookieCache = Object.fromEntries(
      document.cookie.split('; ').map(c => c.split('='))
    )
  }
  return cookieCache[name]
}
```

Invalidate when storage can change externally (another tab, server-set cookies):
```typescript
window.addEventListener('storage', e => {
  if (e.key) storageCache.delete(e.key)
})

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') storageCache.clear()
})
```

---

## Hoist RegExp Compilation
**Impact:** LOW-MEDIUM — avoids recreating compiled regex on every render

`new RegExp(...)` compiles the pattern on each call. Hoisting static patterns to module scope compiles once. For dynamic patterns (where the pattern depends on props/state), `useMemo` limits compilation to when inputs change.

**Instead of:**
```tsx
function Highlighter({ text, query }: Props) {
  const regex = new RegExp(`(${query})`, 'gi') // compiled every render
  const parts = text.split(regex)
  return <>{parts.map((part, i) => ...)}</>
}
```

**Use:**
```tsx
// Static pattern — hoist to module scope
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

// Dynamic pattern — memoize on inputs
function Highlighter({ text, query }: Props) {
  const regex = useMemo(
    () => new RegExp(`(${escapeRegex(query)})`, 'gi'),
    [query]
  )
  const parts = text.split(regex)
  return <>{parts.map((part, i) => ...)}</>
}
```

Caution: global regex (`/g` flag) has mutable `lastIndex` state. A module-level `/g` regex shared across calls will produce incorrect results. Use `useMemo` or construct a new regex per call when using the `g` flag.
