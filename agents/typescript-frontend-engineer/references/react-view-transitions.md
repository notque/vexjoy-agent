# React View Transitions Reference
<!-- Loaded by typescript-frontend-engineer when task involves ViewTransition, page animations, shared element transitions, or navigation animations -->

## Overview

`<ViewTransition>` is a React component (canary/React 19+) that wraps content to animate its enter, exit, and update. Animations activate when state updates are wrapped in `startTransition`, driven by `useDeferredValue`, or triggered by `<Suspense>` resolving.

**Browser support:** Chromium 111+, Firefox 144+, Safari 18.2+. Always include reduced-motion CSS.

**Framework setup:**
- Next.js: enable `experimental.viewTransition: true` in `next.config.js` to also animate `<Link>` navigations.
- Other frameworks: `<ViewTransition>` works for `startTransition`/`useDeferredValue`/`Suspense` updates without any config.

---

## ViewTransition Component API

```tsx
<ViewTransition
  name="unique-name"           // for shared element transitions — must be globally unique
  enter="class-name"           // CSS class for entering element
  exit="class-name"            // CSS class for exiting element
  update="class-name"          // CSS class for same-element updates
  share="morph"                // CSS class for shared element morph between views
  default="none"               // fallback when no other prop matches ("none" | "auto" | class)
  onEnter={(instance, types) => { /* ... */; return () => cleanup() }}
  onExit={(instance, types) => { /* ... */; return () => cleanup() }}
  onUpdate={(instance, types) => { /* ... */; return () => cleanup() }}
  onShare={(instance, types) => { /* ... */; return () => cleanup() }}
>
  <Component />
</ViewTransition>
```

**Type-keyed objects** — map transition types to animation classes:
```tsx
<ViewTransition
  enter={{ 'nav-forward': 'slide-from-right', 'nav-back': 'slide-from-left', default: 'none' }}
  exit={{ 'nav-forward': 'slide-to-left', 'nav-back': 'slide-to-right', default: 'none' }}
  default="none"
>
  <PageContent />
</ViewTransition>
```

**`instance` object in event handlers:** `instance.old`, `instance.new`, `instance.group`, `instance.imagePair`, `instance.name`.

`onShare` takes precedence over `onEnter`/`onExit`. Always return a cleanup function from event handlers.

---

## Activation Triggers

| Trigger | When it fires |
|---------|--------------|
| `startTransition(() => setState(...))` | Manual state update marked as transition |
| `useDeferredValue(value)` | Deferred value update (e.g., search filter) |
| `<Suspense>` resolve | Content replaces fallback |
| `<Link transitionTypes={[...]}>` | Next.js link navigation (requires config flag) |

**`flushSync` skips animations** — use `startTransition` instead.

---

## CSS Animation Recipes

Copy into your global stylesheet. These handle timing, motion blur on morphs, and reduced motion — customize timing variables rather than rewriting from scratch.

### Timing Variables

```css
:root {
  --duration-exit: 150ms;
  --duration-enter: 210ms;
  --duration-move: 400ms;
}
```

### Shared Keyframes

```css
@keyframes fade {
  from { filter: blur(3px); opacity: 0; }
  to { filter: blur(0); opacity: 1; }
}

@keyframes slide {
  from { translate: var(--slide-offset); }
  to { translate: 0; }
}

@keyframes slide-y {
  from { transform: translateY(var(--slide-y-offset, 10px)); }
  to { transform: translateY(0); }
}
```

### Fade

```css
::view-transition-old(.fade-out) {
  animation: var(--duration-exit) ease-in fade reverse;
}
::view-transition-new(.fade-in) {
  animation: var(--duration-enter) ease-out var(--duration-exit) both fade;
}
```

Usage: `<ViewTransition enter="fade-in" exit="fade-out" />`

### Slide (Vertical — for Suspense reveals)

```css
::view-transition-old(.slide-down) {
  animation:
    var(--duration-exit) ease-out both fade reverse,
    var(--duration-exit) ease-out both slide-y reverse;
}
::view-transition-new(.slide-up) {
  animation:
    var(--duration-enter) ease-in var(--duration-exit) both fade,
    var(--duration-move) ease-in both slide-y;
}
```

Usage:
```jsx
<Suspense fallback={<ViewTransition exit="slide-down"><Skeleton /></ViewTransition>}>
  <ViewTransition default="none" enter="slide-up"><Content /></ViewTransition>
</Suspense>
```

### Directional Navigation (Forward / Back)

```css
::view-transition-old(.nav-forward) {
  --slide-offset: -60px;
  animation:
    var(--duration-exit) ease-in both fade reverse,
    var(--duration-move) ease-in-out both slide reverse;
}
::view-transition-new(.nav-forward) {
  --slide-offset: 60px;
  animation:
    var(--duration-enter) ease-out var(--duration-exit) both fade,
    var(--duration-move) ease-in-out both slide;
}

::view-transition-old(.nav-back) {
  --slide-offset: 60px;
  animation:
    var(--duration-exit) ease-in both fade reverse,
    var(--duration-move) ease-in-out both slide reverse;
}
::view-transition-new(.nav-back) {
  --slide-offset: -60px;
  animation:
    var(--duration-enter) ease-out var(--duration-exit) both fade,
    var(--duration-move) ease-in-out both slide;
}
```

### Shared Element Morph

```css
::view-transition-group(.morph) {
  animation-duration: var(--duration-move);
}
::view-transition-image-pair(.morph) {
  animation-name: via-blur;
}
@keyframes via-blur {
  30% { filter: blur(3px); }
}
```

Usage: `<ViewTransition name={`product-${id}`} share="morph" />`

For text elements (avoids raster scaling artifacts on size changes):

```css
::view-transition-group(.text-morph) { animation-duration: var(--duration-move); }
::view-transition-old(.text-morph) { display: none; }
::view-transition-new(.text-morph) { animation: none; object-fit: none; object-position: left top; }
```

### Persistent Element Isolation

```css
::view-transition-group(persistent-nav) {
  animation: none;
  z-index: 100;
}
```

For elements with `backdrop-filter` (hide old snapshot to avoid flash):
```css
::view-transition-old(persistent-nav) { display: none; }
::view-transition-new(persistent-nav) { animation: none; }
```

### Reduced Motion (Required)

```css
@media (prefers-reduced-motion: reduce) {
  ::view-transition-old(*),
  ::view-transition-new(*),
  ::view-transition-group(*) {
    animation-duration: 0s !important;
    animation-delay: 0s !important;
  }
}
```

---

## Searchable Grid with useDeferredValue

`useDeferredValue` makes filter updates a transition, activating `<ViewTransition>` on the results container. Use `default="none"` on per-item transitions to prevent cross-fading every item on every keystroke.

```tsx
'use client'
import { useDeferredValue, useState, ViewTransition, Suspense } from 'react'

export default function SearchableGrid({ itemsPromise }: { itemsPromise: Promise<Item[]> }) {
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)

  return (
    <>
      <input value={search} onChange={e => setSearch(e.currentTarget.value)} />
      <ViewTransition>
        <Suspense fallback={<GridSkeleton />}>
          <ItemGrid itemsPromise={itemsPromise} search={deferredSearch} />
        </Suspense>
      </ViewTransition>
    </>
  )
}

// Per-item transitions with default="none" prevent animation on every keystroke
{filteredItems.map(item => (
  <ViewTransition key={item.id} name={`item-${item.id}`} share="morph" default="none">
    <ItemCard item={item} />
  </ViewTransition>
))}
```

---

## Card Expand/Collapse with Shared Element Morph

Toggle between a grid and a detail view with shared element transitions. The card morphs from its grid position to the detail layout.

```tsx
'use client'
import { useState, useRef, startTransition, ViewTransition } from 'react'

export default function ItemGrid({ items }: { items: Item[] }) {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const scrollRef = useRef(0)

  if (expandedId) {
    return (
      <ViewTransition enter="slide-in" name={`item-${expandedId}`}>
        <ItemDetail
          item={items.find(i => i.id === expandedId)!}
          onClose={() => {
            startTransition(() => {
              setExpandedId(null)
              setTimeout(() => window.scrollTo({ behavior: 'smooth', top: scrollRef.current }), 100)
            })
          }}
        />
      </ViewTransition>
    )
  }

  return (
    <div className="grid grid-cols-3 gap-4">
      {items.map(item => (
        <ViewTransition key={item.id} name={`item-${item.id}`}>
          <ItemCard
            item={item}
            onSelect={() => {
              scrollRef.current = window.scrollY
              startTransition(() => setExpandedId(item.id))
            }}
          />
        </ViewTransition>
      ))}
    </div>
  )
}
```

---

## Type-Safe Transition Helpers

Use `as const` arrays and derived types to prevent name clashes and get autocomplete on transition class names.

```tsx
const transitionTypes = ['default', 'transition-to-detail', 'transition-to-list'] as const
const animationTypes = ['auto', 'none', 'animate-slide-from-left', 'animate-slide-from-right'] as const

type TransitionType = (typeof transitionTypes)[number]
type AnimationType = (typeof animationTypes)[number]
type TransitionMap = { default: AnimationType } & Partial<Record<Exclude<TransitionType, 'default'>, AnimationType>>

export function DirectionalTransition({
  children,
  enter,
  exit,
}: {
  children: React.ReactNode
  enter: TransitionMap
  exit: TransitionMap
}) {
  return <ViewTransition enter={enter} exit={exit}>{children}</ViewTransition>
}

// Reusable wrapper for hierarchical navigation
export function PageTransition({ children }: { children: React.ReactNode }) {
  return (
    <ViewTransition
      enter={{ 'nav-forward': 'nav-forward', 'nav-back': 'nav-back', default: 'none' }}
      exit={{ 'nav-forward': 'nav-forward', 'nav-back': 'nav-back', default: 'none' }}
      default="none"
    >
      {children}
    </ViewTransition>
  )
}
```

---

## Cross-Fade Without Remount

Omit `key` to trigger an update (cross-fade) rather than exit + enter. This avoids Suspense remount/refetch when switching between views that share identity.

```jsx
// Cross-fade — same component instance, different prop
<ViewTransition>
  <TabPanel tab={activeTab} />
</ViewTransition>
```

Use `key` when content identity changes and state should reset. Omit `key` for cross-fades (tabs, panels, carousels).

---

## Persistent Element Isolation

Persistent layout elements (headers, navbars, sidebars) are captured in the page's transition snapshot and slide along with page content unless isolated. Give them a unique `viewTransitionName` to pull them out of the snapshot.

```jsx
<nav style={{ viewTransitionName: 'site-nav' }}>{/* ... */}</nav>
```

Then add the persistent element isolation CSS (see CSS Recipes above). For elements with `backdrop-blur`, use the backdrop-blur workaround variant.

---

## Shared Controls Between Skeleton and Content

Give matching controls in the `<Suspense>` fallback and the real content the same `viewTransitionName` so they morph in place rather than cross-fading.

```jsx
// In Suspense fallback (skeleton)
<input disabled placeholder="Search..." style={{ viewTransitionName: 'search-input' }} />

// In real content
<input placeholder="Search..." style={{ viewTransitionName: 'search-input' }} />
```

Do not put manual `viewTransitionName` on the root DOM node directly inside a `<ViewTransition>` — React's auto-generated name overrides it.

---

## Animation Timing Guidelines

| Interaction | Duration |
|------------|----------|
| Direct toggle (expand/collapse) | 100–200ms |
| Route transition (slide) | 150–250ms |
| Suspense reveal (skeleton → content) | 200–400ms |
| Shared element morph | 300–500ms |

---

## Implementation Checklist

When adding view transitions to an existing app:

1. **Audit** — find every `<Link>`/`router.push`, every `<Suspense>`, every persistent element, every shared visual element (thumbnails that expand, etc.)
2. **Add CSS** — copy the complete recipe set from this file into your global stylesheet
3. **Isolate persistent elements** — add `viewTransitionName` to headers, navbars, sidebars
4. **Add directional page transitions** — wrap each page component (not layout) with type-keyed `<ViewTransition>`
5. **Add Suspense reveals** — wrap fallback and content in matching `<ViewTransition enter/exit>`
6. **Add shared element transitions** — add matching named `<ViewTransition name={...}>` on source and target
7. **Verify** — walk every navigation path and confirm animations fire correctly

**Place directional `<ViewTransition>` in page components, not layouts.** Layouts persist across navigations and never unmount — `enter`/`exit` won't fire on route changes.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| VT not activating | State update not inside `startTransition` | Wrap with `startTransition` |
| VT not activating | `<ViewTransition>` is not the first thing before DOM | Ensure `<ViewTransition>` comes before any DOM node |
| "Two ViewTransition components with the same name" | Non-unique name | Use IDs: `name={\`hero-${item.id}\`}` |
| `flushSync` skips animations | Incompatible with view transitions | Use `startTransition` instead |
| Only updates animate, no enter/exit | Missing `<Suspense>` — React treats swaps as updates | Wrap in `<Suspense>` or conditionally render the VT itself |
| Layout VT prevents page VTs | Nested VTs never fire enter/exit inside a parent | Remove the layout-level `<ViewTransition>` |
| List reorder not animating with `useOptimistic` | Optimistic values resolve before snapshot | Use committed state for list order |
| TS error "Property 'default' is missing" | Type-keyed objects require a `default` key | Add `default: 'none'` to every type map object |
| Backdrop-blur flickers | Old snapshot has backdrop-blur | Use the backdrop-blur workaround CSS variant |
| `border-radius` lost during transitions | Not applied to captured element | Apply `border-radius` directly to the captured element |
| Skeleton controls slide away | Controls not matched between skeleton and content | Give both the same `viewTransitionName` |
| `router.back()` skips animation | `popstate` is synchronous, incompatible with VT | Use `router.push()` with explicit URL instead |
