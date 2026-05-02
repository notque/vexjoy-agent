# State Management Reference
<!-- Loaded by react-native-engineer when task involves useState, derived state, Zustand, state structure, dispatchers, ground truth -->

## Use Dispatch Updaters When Next State Depends on Current
**Impact:** MEDIUM — prevents stale closures

**Instead of:**
```tsx
const onLayout = (e: LayoutChangeEvent) => {
  const { width, height } = e.nativeEvent.layout
  if (size?.width !== width || size?.height !== height) setSize({ width, height })
}
```

**Use:**
```tsx
const onLayout = (e: LayoutChangeEvent) => {
  const { width, height } = e.nativeEvent.layout
  setSize((prev) => {
    if (prev?.width === width && prev?.height === height) return prev
    return { width, height }
  })
}
```

For simple cases: `setCount((prev) => prev + 1)` instead of `setCount(count + 1)`.

Not needed for primitive state set to a new value directly.

---

## Use Fallback State — undefined Means "User Hasn't Chosen Yet"
**Impact:** MEDIUM — reactive fallbacks, no stale initialState

**Instead of:**
```tsx
const [enabled, setEnabled] = useState(defaultEnabled)  // locks at mount
```

**Use:**
```tsx
const [_enabled, setEnabled] = useState<boolean | undefined>(undefined)
const enabled = _enabled ?? defaultEnabled
// undefined = user hasn't touched it — falls back to parent prop
// Once user interacts, their choice persists
```

With server data:
```tsx
const [_theme, setTheme] = useState<string | undefined>(undefined)
const theme = _theme ?? data.theme
```

---

## Minimize State — Derive Values During Render
**Impact:** MEDIUM — fewer re-renders, no state drift

**Instead of:**
```tsx
const [total, setTotal] = useState(0)
useEffect(() => { setTotal(items.reduce(...)) }, [items])
```

**Use:**
```tsx
const total = items.reduce((sum, item) => sum + item.price, 0)
const itemCount = items.length
```

State is the minimal source of truth. Everything else is derived.

---

## State Must Represent Ground Truth
**Impact:** HIGH — single source of truth, easier debugging

State variables represent what is happening (`pressed`, `progress`, `isOpen`), not derived visuals (`scale`, `opacity`, `height`). Derive visuals from state.

**Instead of:**
```tsx
const [isExpanded, setIsExpanded] = useState(false)
const [height, setHeight] = useState(0)
useEffect(() => { setHeight(isExpanded ? 200 : 0) }, [isExpanded])
```

**Use:**
```tsx
const [isExpanded, setIsExpanded] = useState(false)
const height = isExpanded ? 200 : 0
```

Same principle applies to Reanimated shared values — see `animation-patterns.md`.

---

## Track Scroll Position in Shared Values or Refs
**Impact:** HIGH — prevents render thrashing during scroll

Scroll events fire 60/s. `useState` for scroll position = re-render every frame = dropped frames.

**Instead of:**
```tsx
const [scrollY, setScrollY] = useState(0)
const onScroll = (e) => setScrollY(e.nativeEvent.contentOffset.y)
```

**Use (Reanimated for scroll-driven animations):**
```tsx
const scrollY = useSharedValue(0)
const onScroll = useAnimatedScrollHandler({
  onScroll: (e) => { scrollY.value = e.contentOffset.y }
})
return <Animated.ScrollView onScroll={onScroll} scrollEventThrottle={16} />
```

**Use (ref for non-reactive tracking):**
```tsx
const scrollY = useRef(0)
const onScroll = (e) => { scrollY.current = e.nativeEvent.contentOffset.y }
```
