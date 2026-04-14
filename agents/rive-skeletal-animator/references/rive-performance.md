# Rive Performance Reference

> **Scope**: Canvas sizing, WebGL context limits, frame budget management, and runtime lazy loading for 60fps mobile targets. Does not cover state machine logic or animation clip design (see `rive-animation-library.md`).
> **Version range**: `@rive-app/react-canvas` 4.x, React 18/19
> **Generated**: 2026-04-14 — verify against current Rive runtime changelog

---

## Overview

Rive renders into a WebGL canvas. The two primary performance killers are canvas resolution (a 900px canvas at 2x DPR draws 1800×1800px) and exceeding the browser's WebGL context limit (typically 16 simultaneous contexts). Lazy loading the WASM runtime (~150KB) keeps initial bundle lean. Getting all three right is required for 60fps on mid-range mobile.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `layout={new Layout({ fit: Fit.Contain })}` | 4.x+ | character fits inside fixed canvas | pixel-perfect sprite replacement needed |
| `React.lazy` + `Suspense` for Rive component | React 18+ | combat screen not visible on initial load | animation needed at page load |
| `rive.cleanup()` on unmount | 4.x+ | component unmounts and remounts | canvas element stays mounted |
| `useRive({ autoplay: false })` + manual `rive.play()` | 4.x+ | deferring playback until user action | animation should start on load |

---

## Correct Patterns

### Lazy Load the Rive Component

Only import `@rive-app/react-canvas` when the combat screen mounts. The WASM bundle is ~150KB gzipped and loads synchronously on first import.

```tsx
// In your route or screen component
const CombatScene = React.lazy(() => import('./CombatScene'));

function App() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      {showCombat && <CombatScene />}
    </Suspense>
  );
}
```

**Why**: Shipping WASM on the initial bundle adds ~150KB to every page load, even for users who never reach combat. Lazy loading amortizes the cost to the first combat encounter only.

---

### Explicit Canvas Size via Container Div

Set `width`/`height` on the wrapper `div`, not on `RiveComponent`. Rive fills its container.

```tsx
// Correct — container controls size
<div style={{ width: 400, height: 400, position: 'relative' }}>
  <RiveComponent />
</div>

// Wrong — RiveComponent does not accept width/height props reliably
<RiveComponent width={400} height={400} />
```

**Why**: `RiveComponent` mounts a `<canvas>` and observes its container's `ResizeObserver`. Setting dimensions on the canvas directly bypasses the observer and may leave the canvas logical size out of sync with its CSS size, causing blurry rendering at 2x DPR.

---

### Downscale Large Characters on Mobile

For characters originally designed at 900px, scale the canvas at mobile breakpoints rather than rendering full resolution.

```tsx
function EnemyCharacter() {
  const isMobile = useMediaQuery('(max-width: 768px)');
  const size = isMobile ? 450 : 900;

  return (
    <div style={{ width: size, height: size }}>
      <RiveComponent />
    </div>
  );
}
```

**Why**: WebGL canvas draw calls scale quadratically with resolution. A 900px canvas at 2x DPR = 1800×1800 = 3.24M pixels per frame. At 450px: 810K pixels — 4× cheaper.

---

### Cleanup on Unmount

Always call `rive.cleanup()` when a component unmounts to release the WebGL context.

```tsx
useEffect(() => {
  return () => {
    rive?.cleanup();
  };
}, [rive]);
```

**Why**: Browsers cap WebGL contexts at ~16. Each `useRive` mount without cleanup holds a context slot. After 16 mounts (across tabs, rerenders, or HMR cycles), new canvases silently fail to initialize.

---

## Anti-Pattern Catalog

### ❌ Wrapping RiveComponent in Framer Motion

**Detection**:
```bash
grep -rn 'motion\.' --include="*.tsx" | grep -i 'rive'
rg 'motion\.(div|span)' --type tsx -l | xargs grep -l 'RiveComponent'
```

**What it looks like**:
```tsx
<motion.div animate={{ opacity: 1 }} initial={{ opacity: 0 }}>
  <RiveComponent />
</motion.div>
```

**Why wrong**: Framer Motion and Rive both own animation timing. When Framer Motion drives opacity/transform on the container, it forces composite layer repaints on every frame, doubling GPU work. For Rive characters, transition effects belong in the Rive state machine or in CSS transitions on the wrapper.

**Fix**:
```tsx
// Use CSS transition on wrapper instead
<div style={{ opacity: loaded ? 1 : 0, transition: 'opacity 0.3s ease' }}>
  <RiveComponent />
</div>
```

---

### ❌ Creating Rive Instances Outside React Lifecycle

**Detection**:
```bash
grep -rn 'new Rive(' --include="*.ts" --include="*.tsx"
rg 'new Rive\(' --type ts
```

**What it looks like**:
```ts
// In a Zustand store or utility function
const riveInstance = new Rive({ src: '/characters/player.riv', canvas: canvasEl });
```

**Why wrong**: Rive instances created outside React components lose their cleanup path. `useRive` manages the instance lifecycle — loading, resize observation, cleanup — and ties it to the component tree. Manual instances bypass all of this, causing WebGL context leaks when the canvas element is removed from the DOM.

**Fix**: Use `useRive` inside the React component. Pass the Rive instance to Zustand if other components need to fire inputs, but do not construct the instance in the store.

```tsx
// In component
const { rive, RiveComponent } = useRive({ ... });

// Pass fire-input callback to store, not the instance
useEffect(() => {
  if (!rive) return;
  combatStore.setFireInput((name: string) => {
    rive.stateMachineInputs('CombatStateMachine')
      ?.find(i => i.name === name)
      ?.fire();
  });
}, [rive]);
```

---

### ❌ Rendering Multiple Rive Canvases Simultaneously Without Shared Context

**Detection**:
```bash
grep -rn 'useRive' --include="*.tsx" | grep -v 'test\|spec\|story'
```

Count the number of `useRive` calls active at once. If more than 12, context exhaustion is likely.

**What it looks like**:
```tsx
// Character select screen with 8 previews + combat scene with 2 active characters = 10+ contexts
{characters.map(c => <CharacterPreview key={c.id} rivFile={c.riv} />)}
```

**Why wrong**: Each `useRive` acquires one WebGL context. Browser limit is typically 16. Exceeding it silently produces blank canvases with no error in the console.

**Fix**: Use Rive's `SharedRenderer` to share one WebGL context across multiple canvases.

```tsx
import { useRive, RiveComponent, RuntimeLoader } from '@rive-app/react-canvas';
// OR for @rive-app/canvas-advanced:
// SharedRenderer batches multiple Rive canvases into one GL context
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| Canvas is blank, no error logged | WebGL context limit exceeded (>16 active) | Add `rive.cleanup()` on unmount; use `SharedRenderer` for multi-canvas pages |
| `ResizeObserver loop limit exceeded` in console | Rive container div has no explicit dimensions | Set explicit `width`/`height` on the wrapper div |
| FPS drops from 60 to 30 on mobile | Canvas too large at 2x DPR | Halve canvas dimensions at `max-width: 768px` breakpoint |
| Animation plays once then freezes | `autoplay: false` with no manual `rive.play()` call | Set `autoplay: true` or call `rive.play()` after load |
| WASM load failure in Vite dev server | Vite does not serve `.wasm` by default | Add `assetsInclude: ['**/*.wasm']` to `vite.config.ts` |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| `@rive-app/react-canvas` 4.0 | Introduced `useRive` hook (replaced `useRiveFile`) | Old `useRiveFile` + manual Rive constructor pattern deprecated |
| `@rive-app/react-canvas` 4.7 | `SharedRenderer` exported from main package | No longer need `@rive-app/canvas-advanced` for shared GL context |
| React 19 | Concurrent rendering with StrictMode double-invokes effects | `rive.cleanup()` in effect cleanup is essential — double-mount creates then immediately destroys one instance |

---

## Detection Commands Reference

```bash
# Find Framer Motion wrappers around Rive
grep -rn 'motion\.' --include="*.tsx" | grep -i 'rive'

# Find manual Rive constructor usage (context leak risk)
grep -rn 'new Rive(' --include="*.ts" --include="*.tsx"

# Count active useRive calls (context exhaustion check)
grep -rn 'useRive' --include="*.tsx" | grep -v 'test\|spec\|story'

# Find RiveComponent without explicit container sizing
grep -rn 'RiveComponent' --include="*.tsx" -A2 | grep -v 'width\|height\|style'

# Find missing cleanup calls
grep -rn 'useRive' --include="*.tsx" -l | xargs grep -L 'cleanup'
```

---

## See Also

- `rive-react-setup.md` — useRive hook parameters, Vite WASM config, lazy loading patterns
- `rive-animation-library.md` — State machine timing, clip durations, frame sync with CombatEngine
