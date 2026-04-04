# State Management Reference
<!-- Loaded by react-native-engineer when task involves useState, derived state, Zustand, state structure, dispatchers, ground truth -->

## Use Dispatch Updaters When Next State Depends on Current State
**Impact:** MEDIUM — prevents stale closures, ensures comparison against latest value

When the next state depends on the current state, pass a function to the setter instead of reading the state variable directly. This prevents stale closure bugs in callbacks and ensures the comparison runs against the latest value.

**Instead of:**
```tsx
const [size, setSize] = useState<Size | undefined>(undefined)

const onLayout = (e: LayoutChangeEvent) => {
  const { width, height } = e.nativeEvent.layout
  // size may be stale in this closure
  if (size?.width !== width || size?.height !== height) {
    setSize({ width, height })
  }
}
```

**Use:**
```tsx
const [size, setSize] = useState<Size | undefined>(undefined)

const onLayout = (e: LayoutChangeEvent) => {
  const { width, height } = e.nativeEvent.layout
  setSize((prev) => {
    if (prev?.width === width && prev?.height === height) return prev  // skips re-render
    return { width, height }
  })
}
```

For simple counters or other state where the next value depends on the previous:
```tsx
// Instead of: setCount(count + 1)
setCount((prev) => prev + 1)
```

For primitive state where you are setting a new value directly (not derived from current), you do not need a dispatch updater.

---

## Use Fallback State — undefined Means "User Hasn't Chosen Yet"
**Impact:** MEDIUM — reactive fallbacks that update when source changes, no stale initialState

Initialize state as `undefined` and use nullish coalescing to fall back to parent or server values. State represents user intent only. `initialState` locks in the value at mount time and doesn't update when the source changes.

**Instead of:**
```tsx
// locks in defaultEnabled at mount — stale if parent prop changes
const [enabled, setEnabled] = useState(defaultEnabled)
```

**Use:**
```tsx
const [_enabled, setEnabled] = useState<boolean | undefined>(undefined)
const enabled = _enabled ?? defaultEnabled
// undefined = user hasn't touched it — falls back to parent prop
// If defaultEnabled changes, component reflects it
// Once the user interacts, their choice persists
```

With server data:
```tsx
function ProfileForm({ data }: { data: User }) {
  const [_theme, setTheme] = useState<string | undefined>(undefined)
  const theme = _theme ?? data.theme  // shows server value until user overrides
  return <ThemePicker value={theme} onChange={setTheme} />
}
```

---

## Minimize State — Derive Values During Render
**Impact:** MEDIUM — fewer re-renders, no state drift, simpler code

If a value can be computed from existing state or props, derive it during render. Redundant state causes extra re-renders and can drift out of sync.

**Instead of:**
```tsx
const [total, setTotal] = useState(0)
const [itemCount, setItemCount] = useState(0)

useEffect(() => {
  setTotal(items.reduce((sum, item) => sum + item.price, 0))
  setItemCount(items.length)
}, [items])
```

**Use:**
```tsx
// derived directly — no state, no effect, no drift
const total = items.reduce((sum, item) => sum + item.price, 0)
const itemCount = items.length
```

Another example:
```tsx
// Instead of storing fullName in state alongside firstName/lastName
const [firstName, setFirstName] = useState('')
const [lastName, setLastName] = useState('')
const fullName = `${firstName} ${lastName}`  // derived
```

State is the minimal source of truth. Everything else is derived.

---

## State Must Represent Ground Truth
**Impact:** HIGH — cleaner logic, single source of truth, easier debugging

State variables — both React `useState` and Reanimated shared values — should represent what is actually happening (`pressed`, `progress`, `isOpen`), not derived visual outputs (`scale`, `opacity`, `height`). Derive visual values from state.

**Instead of:**
```tsx
// isExpanded is the state, but height is also stored
const [isExpanded, setIsExpanded] = useState(false)
const [height, setHeight] = useState(0)
useEffect(() => { setHeight(isExpanded ? 200 : 0) }, [isExpanded])
```

**Use:**
```tsx
// derive height from state — no extra state, no effect
const [isExpanded, setIsExpanded] = useState(false)
const height = isExpanded ? 200 : 0
```

The same principle applies to Reanimated shared values — see `animation-patterns.md` for the animation-specific version.

---

## Track Scroll Position in Shared Values or Refs
**Impact:** HIGH — prevents render thrashing during scroll

Scroll events fire 60 times per second. Storing scroll position in `useState` triggers a re-render on every scroll event — this causes dropped frames.

**Instead of:**
```tsx
const [scrollY, setScrollY] = useState(0)
const onScroll = (e) => setScrollY(e.nativeEvent.contentOffset.y)  // re-renders on every frame
```

**Use (Reanimated for animations driven by scroll):**
```tsx
import Animated, { useSharedValue, useAnimatedScrollHandler } from 'react-native-reanimated'

const scrollY = useSharedValue(0)
const onScroll = useAnimatedScrollHandler({
  onScroll: (e) => { scrollY.value = e.contentOffset.y }  // UI thread, no re-render
})

return <Animated.ScrollView onScroll={onScroll} scrollEventThrottle={16} />
```

**Use (ref for non-reactive tracking):**
```tsx
const scrollY = useRef(0)
const onScroll = (e) => { scrollY.current = e.nativeEvent.contentOffset.y }  // no re-render
```
