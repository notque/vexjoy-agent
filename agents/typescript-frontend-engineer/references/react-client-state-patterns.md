# React Client State Patterns Reference
<!-- Loaded by typescript-frontend-engineer when task involves useState, useEffect, derived state, memo, useRef, transitions, or rendering optimization -->

## Calculate Derived State During Rendering
**Impact:** MEDIUM — avoids redundant renders and state drift

If a value can be computed from current props or state, derive it during render rather than storing it in state and syncing it via `useEffect`. The extra state and effect add a render cycle and risk divergence.

**Instead of:**
```tsx
function Form() {
  const [firstName, setFirstName] = useState('First')
  const [lastName, setLastName] = useState('Last')
  const [fullName, setFullName] = useState('')

  useEffect(() => {
    setFullName(firstName + ' ' + lastName)
  }, [firstName, lastName])

  return <p>{fullName}</p>
}
```

**Use:**
```tsx
function Form() {
  const [firstName, setFirstName] = useState('First')
  const [lastName, setLastName] = useState('Last')
  const fullName = firstName + ' ' + lastName  // derived during render

  return <p>{fullName}</p>
}
```

---

## Functional setState Updates
**Impact:** MEDIUM — prevents stale closures and unnecessary callback recreations

When updating state based on its current value, use the functional form of setState. This eliminates the state variable from the dependency array, produces stable callback references, and prevents stale closure bugs.

**Instead of:**
```tsx
function TodoList() {
  const [items, setItems] = useState(initialItems)

  // Recreated on every items change; stale closure if deps are wrong
  const addItems = useCallback((newItems: Item[]) => {
    setItems([...items, ...newItems])
  }, [items])

  // Missing dependency — always uses stale initial items
  const removeItem = useCallback((id: string) => {
    setItems(items.filter(item => item.id !== id))
  }, [])

  return <ItemsEditor items={items} onAdd={addItems} onRemove={removeItem} />
}
```

**Use:**
```tsx
function TodoList() {
  const [items, setItems] = useState(initialItems)

  // Stable — no state dependency needed
  const addItems = useCallback((newItems: Item[]) => {
    setItems(curr => [...curr, ...newItems])
  }, [])

  // Always uses latest state, no stale closure risk
  const removeItem = useCallback((id: string) => {
    setItems(curr => curr.filter(item => item.id !== id))
  }, [])

  return <ItemsEditor items={items} onAdd={addItems} onRemove={removeItem} />
}
```

Use functional updates whenever: the new state depends on the current state, the setter is inside `useCallback` or `useMemo`, or the update happens inside an async operation.

---

## Lazy State Initialization
**Impact:** MEDIUM — avoids expensive computation on every render

Pass a function to `useState` for expensive initial values. Without the function form, the initializer expression is evaluated on every render even though its result is only used on the first.

**Instead of:**
```tsx
// buildSearchIndex() runs on EVERY render
const [searchIndex, setSearchIndex] = useState(buildSearchIndex(items))

// JSON.parse runs on EVERY render
const [settings, setSettings] = useState(
  JSON.parse(localStorage.getItem('settings') || '{}')
)
```

**Use:**
```tsx
// buildSearchIndex() runs only on initial render
const [searchIndex, setSearchIndex] = useState(() => buildSearchIndex(items))

// JSON.parse runs only on initial render
const [settings, setSettings] = useState(() => {
  const stored = localStorage.getItem('settings')
  return stored ? JSON.parse(stored) : {}
})
```

Apply lazy initialization when computing initial values from localStorage/sessionStorage, building data structures (indexes, maps), reading from the DOM, or performing heavy transformations. For simple primitives (`useState(0)`), the function form is unnecessary.

---

## useDeferredValue for Non-Urgent Renders
**Impact:** MEDIUM — keeps input responsive during heavy computation

When user input triggers expensive filtering or rendering, `useDeferredValue` lets React prioritize the input update and schedule the expensive result when idle. Pair with `useMemo` so the computation only re-runs when the deferred value changes.

**Instead of:**
```tsx
function Search({ items }: { items: Item[] }) {
  const [query, setQuery] = useState('')
  const filtered = items.filter(item => fuzzyMatch(item, query))  // blocks input

  return (
    <>
      <input value={query} onChange={e => setQuery(e.target.value)} />
      <ResultsList results={filtered} />
    </>
  )
}
```

**Use:**
```tsx
function Search({ items }: { items: Item[] }) {
  const [query, setQuery] = useState('')
  const deferredQuery = useDeferredValue(query)
  const filtered = useMemo(
    () => items.filter(item => fuzzyMatch(item, deferredQuery)),
    [items, deferredQuery]
  )
  const isStale = query !== deferredQuery

  return (
    <>
      <input value={query} onChange={e => setQuery(e.target.value)} />
      <div style={{ opacity: isStale ? 0.7 : 1 }}>
        <ResultsList results={filtered} />
      </div>
    </>
  )
}
```

Apply when: filtering or searching large lists, expensive visualizations reacting to input, any derived state that causes noticeable render delays.

---

## useTransition for Interaction Responsiveness
**Impact:** MEDIUM — maintains UI responsiveness during frequent non-urgent updates

Mark state updates as non-urgent with `startTransition` so React can interrupt them to handle higher-priority input. Useful for scroll tracking, tab switching, or any update where the UI should stay responsive.

**Instead of:**
```tsx
function ScrollTracker() {
  const [scrollY, setScrollY] = useState(0)
  useEffect(() => {
    const handler = () => setScrollY(window.scrollY)  // urgent — blocks other updates
    window.addEventListener('scroll', handler, { passive: true })
    return () => window.removeEventListener('scroll', handler)
  }, [])
}
```

**Use:**
```tsx
import { startTransition } from 'react'

function ScrollTracker() {
  const [scrollY, setScrollY] = useState(0)
  useEffect(() => {
    const handler = () => {
      startTransition(() => setScrollY(window.scrollY))
    }
    window.addEventListener('scroll', handler, { passive: true })
    return () => window.removeEventListener('scroll', handler)
  }, [])
}
```

---

## useRef for Transient Values
**Impact:** MEDIUM — avoids unnecessary re-renders on frequent updates

Store frequently-changing values that don't drive UI in a ref rather than state. Updating a ref does not trigger a re-render — use it for mouse tracking, interval IDs, transient flags, and direct DOM manipulation.

**Instead of:**
```tsx
function Tracker() {
  const [lastX, setLastX] = useState(0)  // re-renders on every mouse move

  useEffect(() => {
    const onMove = (e: MouseEvent) => setLastX(e.clientX)
    window.addEventListener('mousemove', onMove)
    return () => window.removeEventListener('mousemove', onMove)
  }, [])

  return <div style={{ position: 'fixed', top: 0, left: lastX }} />
}
```

**Use:**
```tsx
function Tracker() {
  const lastXRef = useRef(0)
  const dotRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      lastXRef.current = e.clientX
      const node = dotRef.current
      if (node) node.style.transform = `translateX(${e.clientX}px)`
    }
    window.addEventListener('mousemove', onMove)
    return () => window.removeEventListener('mousemove', onMove)
  }, [])

  return (
    <div
      ref={dotRef}
      style={{ position: 'fixed', top: 0, left: 0, transform: 'translateX(0px)' }}
    />
  )
}
```

---

## Extract to Memoized Components
**Impact:** MEDIUM — enables early returns before expensive computation

Moving expensive work into a `memo`-wrapped child allows the parent to short-circuit (e.g., return a skeleton) before the child is ever evaluated. A memoized component only re-renders when its own props change.

**Instead of:**
```tsx
function Profile({ user, loading }: Props) {
  const avatar = useMemo(() => {
    const id = computeAvatarId(user)  // runs even when loading
    return <Avatar id={id} />
  }, [user])

  if (loading) return <Skeleton />
  return <div>{avatar}</div>
}
```

**Use:**
```tsx
const UserAvatar = memo(function UserAvatar({ user }: { user: User }) {
  const id = useMemo(() => computeAvatarId(user), [user])
  return <Avatar id={id} />
})

function Profile({ user, loading }: Props) {
  if (loading) return <Skeleton />  // skips UserAvatar entirely
  return (
    <div>
      <UserAvatar user={user} />
    </div>
  )
}
```

---

## Split Combined Hook Computations
**Impact:** MEDIUM — avoids recomputing independent steps when unrelated deps change

When a single `useMemo` or `useEffect` combines independent tasks with different dependencies, split them. A combined hook reruns all tasks when any dependency changes, even steps that don't use the changed value.

**Instead of:**
```tsx
// Changing sortOrder recomputes filtering even though filtering doesn't use sortOrder
const sortedProducts = useMemo(() => {
  const filtered = products.filter(p => p.category === category)
  const sorted = filtered.toSorted((a, b) =>
    sortOrder === 'asc' ? a.price - b.price : b.price - a.price
  )
  return sorted
}, [products, category, sortOrder])
```

**Use:**
```tsx
// Filtering only reruns when products or category change
const filteredProducts = useMemo(
  () => products.filter(p => p.category === category),
  [products, category]
)

// Sorting only reruns when filteredProducts or sortOrder change
const sortedProducts = useMemo(
  () => filteredProducts.toSorted((a, b) =>
    sortOrder === 'asc' ? a.price - b.price : b.price - a.price
  ),
  [filteredProducts, sortOrder]
)
```

Same principle applies to `useEffect` — split effects with different dependencies into separate effect calls.

---

## No Inline Component Definitions
**Impact:** HIGH — prevents remount and state loss on every parent render

Defining a component inside another component creates a new component type on every render. React sees a different type and fully unmounts the old instance, destroying all state and DOM, then mounts a fresh one.

**Instead of:**
```tsx
function UserProfile({ user, theme }: Props) {
  // New type on every render — remounts every time
  const Avatar = () => (
    <img src={user.avatarUrl} className={theme === 'dark' ? 'avatar-dark' : 'avatar-light'} />
  )
  return <div><Avatar /></div>
}
```

**Use:**
```tsx
function Avatar({ src, theme }: { src: string; theme: string }) {
  return (
    <img src={src} className={theme === 'dark' ? 'avatar-dark' : 'avatar-light'} />
  )
}

function UserProfile({ user, theme }: Props) {
  return <div><Avatar src={user.avatarUrl} theme={theme} /></div>
}
```

Symptoms of inline component bugs: input fields lose focus on every keystroke, animations restart unexpectedly, `useEffect` cleanup and setup run on every parent render, scroll position resets.

---

## Effect Event Dependencies
**Impact:** LOW — avoids unnecessary effect re-runs from unstable callback references

Effect Event functions (from `useEffectEvent`) have intentionally unstable identity — their reference changes on every render. Do not include them in `useEffect` dependency arrays.

**Instead of:**
```tsx
import { useEffect, useEffectEvent } from 'react'

function ChatRoom({ roomId, onConnected }: { roomId: string; onConnected: () => void }) {
  const handleConnected = useEffectEvent(onConnected)

  useEffect(() => {
    const connection = createConnection(roomId)
    connection.on('connected', handleConnected)
    connection.connect()
    return () => connection.disconnect()
  }, [roomId, handleConnected])  // handleConnected re-runs effect every render
}
```

**Use:**
```tsx
function ChatRoom({ roomId, onConnected }: { roomId: string; onConnected: () => void }) {
  const handleConnected = useEffectEvent(onConnected)

  useEffect(() => {
    const connection = createConnection(roomId)
    connection.on('connected', handleConnected)
    connection.connect()
    return () => connection.disconnect()
  }, [roomId])  // only roomId is reactive
}
```

---

## Event Handler Refs for Stable Subscriptions
**Impact:** LOW — prevents re-subscribing to events when callbacks change

Store event handlers in refs when used inside effects that should not re-run when the callback identity changes. The ref always holds the latest version without triggering effect teardown/setup.

**Instead of:**
```tsx
function useWindowEvent(event: string, handler: (e: Event) => void) {
  useEffect(() => {
    window.addEventListener(event, handler)
    return () => window.removeEventListener(event, handler)
  }, [event, handler])  // re-subscribes whenever handler reference changes
}
```

**Use:**
```tsx
function useWindowEvent(event: string, handler: (e: Event) => void) {
  const handlerRef = useRef(handler)
  useEffect(() => { handlerRef.current = handler }, [handler])

  useEffect(() => {
    const listener = (e: Event) => handlerRef.current(e)
    window.addEventListener(event, listener)
    return () => window.removeEventListener(event, listener)
  }, [event])  // stable subscription — only re-runs when event name changes
}
```

On React's latest releases, `useEffectEvent` provides the same guarantee with a cleaner API — prefer it when available.

---

## Initialize-Once Patterns
**Impact:** LOW-MEDIUM — prevents duplicate init in development and on remount

Do not put app-wide initialization inside `useEffect([])` — effects re-run when a component remounts (including React 18+ Strict Mode double-invocation in development). Use a module-level guard for truly once-per-app-load work.

**Instead of:**
```tsx
function App() {
  useEffect(() => {
    loadFromStorage()    // runs twice in development (Strict Mode)
    checkAuthToken()
  }, [])
}
```

**Use:**
```tsx
let didInit = false

function App() {
  useEffect(() => {
    if (didInit) return
    didInit = true
    loadFromStorage()
    checkAuthToken()
  }, [])
}
```

For truly one-time module-level initialization that has no DOM dependency, move it outside the component entirely:

```tsx
// Runs once when the module is imported
initAnalytics()
loadPersistedState()

function App() {
  // ...
}
```
