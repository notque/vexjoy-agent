# Rive Performance Reference

> **Scope**: Canvas sizing, WebGL context limits, frame budget, runtime lazy loading for 60fps mobile.
> **Version range**: `@rive-app/react-canvas` 4.x, React 18/19
> **Generated**: 2026-04-14

---

Rive renders into WebGL canvas. Primary performance killers: canvas resolution (900px at 2x DPR = 1800x1800px) and exceeding browser WebGL context limit (~16). Lazy load WASM runtime (~150KB). All three required for 60fps on mid-range mobile.

## Pattern Table

| Pattern | Use When | Avoid When |
|---------|----------|------------|
| `layout={new Layout({ fit: Fit.Contain })}` | character fits fixed canvas | pixel-perfect sprite replacement |
| `React.lazy` + `Suspense` for Rive component | combat screen not on initial load | animation needed at page load |
| `rive.cleanup()` on unmount | component unmounts/remounts | canvas stays mounted |
| `useRive({ autoplay: false })` + manual play | deferring until user action | should start on load |

---

## Correct Patterns

### Lazy Load the Rive Component

```tsx
const CombatScene = React.lazy(() => import('./CombatScene'));

function App() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      {showCombat && <CombatScene />}
    </Suspense>
  );
}
```

WASM bundle ~150KB gzipped loads synchronously on first import. Lazy loading amortizes to first combat encounter.

---

### Explicit Canvas Size via Container Div

```tsx
// Correct — container controls size
<div style={{ width: 400, height: 400, position: 'relative' }}>
  <RiveComponent />
</div>

// Wrong — RiveComponent does not accept width/height reliably
<RiveComponent width={400} height={400} />
```

`RiveComponent` mounts `<canvas>` and observes container via `ResizeObserver`. Direct canvas dimensions bypass the observer.

---

### Downscale Large Characters on Mobile

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

900px at 2x DPR = 3.24M pixels/frame. 450px = 810K — 4x cheaper.

---

### Cleanup on Unmount

```tsx
useEffect(() => {
  return () => { rive?.cleanup(); };
}, [rive]);
```

Browsers cap WebGL contexts at ~16. Each `useRive` without cleanup holds a slot. After 16, new canvases silently fail.

---

## Pattern Catalog

### Use CSS Transitions Instead of Framer Motion for Rive

**Detection**:
```bash
grep -rn 'motion\.' --include="*.tsx" | grep -i 'rive'
```

**Signal**: `<motion.div animate={{ opacity: 1 }}><RiveComponent /></motion.div>`

Both Framer Motion and Rive own animation timing. Framer driving opacity/transform on the container forces composite layer repaints, doubling GPU work.

**Fix**:
```tsx
<div style={{ opacity: loaded ? 1 : 0, transition: 'opacity 0.3s ease' }}>
  <RiveComponent />
</div>
```

---

### Create Rive Instances via useRive Hook

**Detection**:
```bash
grep -rn 'new Rive(' --include="*.ts" --include="*.tsx"
```

**Signal**: `const riveInstance = new Rive({ src: '...', canvas: canvasEl })` outside React.

Manual instances lose cleanup path. `useRive` manages lifecycle (loading, resize, cleanup) tied to component tree. Manual instances leak WebGL contexts.

**Fix**: Use `useRive` inside component. Pass fire-input callback to Zustand, not the instance.

---

### Share WebGL Context Across Multiple Canvases

**Detection**:
```bash
grep -rn 'useRive' --include="*.tsx" | grep -v 'test\|spec\|story'
```

Count active `useRive` calls. If >12, context exhaustion is likely.

**Signal**: Character select with 8 previews + combat with 2 = 10+ contexts.

Exceeding limit silently produces blank canvases with no console error.

**Fix**: Use Rive's `SharedRenderer` to share one WebGL context.

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| Blank canvas, no error | WebGL context limit (>16) | `rive.cleanup()` on unmount; `SharedRenderer` |
| `ResizeObserver loop limit exceeded` | Container div has no explicit dimensions | Set `width`/`height` on wrapper |
| FPS drops 60→30 on mobile | Canvas too large at 2x DPR | Halve dimensions at 768px breakpoint |
| Animation plays once, freezes | `autoplay: false` without `rive.play()` | Set `autoplay: true` or call `rive.play()` |
| WASM load failure in Vite | Vite doesn't serve `.wasm` by default | Add `assetsInclude: ['**/*.wasm']` |

## Version Notes

| Version | Change | Impact |
|---------|--------|--------|
| 4.0 | `useRive` hook (replaced `useRiveFile`) | Old constructor pattern deprecated |
| 4.7 | `SharedRenderer` exported from main package | No longer need `canvas-advanced` |
| React 19 | StrictMode double-invokes effects | `rive.cleanup()` essential — double-mount creates then destroys one instance |

---

## Detection Commands

```bash
# Framer Motion wrappers around Rive
grep -rn 'motion\.' --include="*.tsx" | grep -i 'rive'

# Manual Rive constructor (context leak)
grep -rn 'new Rive(' --include="*.ts" --include="*.tsx"

# Active useRive count (context exhaustion)
grep -rn 'useRive' --include="*.tsx" | grep -v 'test\|spec\|story'

# RiveComponent without container sizing
grep -rn 'RiveComponent' --include="*.tsx" -A2 | grep -v 'width\|height\|style'

# Missing cleanup
grep -rn 'useRive' --include="*.tsx" -l | xargs grep -L 'cleanup'
```

## See Also

- `rive-react-setup.md` — useRive parameters, Vite WASM config, lazy loading
- `rive-animation-library.md` — State machine timing, frame sync with CombatEngine
