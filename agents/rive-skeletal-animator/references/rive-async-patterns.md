# Rive Async Patterns Reference

> **Scope**: Async instance lifecycle, null-guarding `rive`, loading states, event callback sequencing.
> **Version range**: `@rive-app/react-canvas` 4.x, React 18/19
> **Generated**: 2026-04-14

---

`useRive` returns null `rive` until `.riv` loads and WASM initializes. This async gap is the most common runtime error source — firing inputs before ready silently fails or throws. Guard: state machine input access, manual playback, and Zustand bridging.

## Pattern Table

| Pattern | Use When | Avoid When |
|---------|----------|------------|
| `if (!rive) return` guard in `useEffect` | accessing rive in effects | synchronous render path |
| `onLoad` callback | one-time post-load setup | polling rive for non-null |
| `onStateChange` for animation complete | waiting for animation finish | setTimeout sequencing |
| `isLoading` from `useRive` | showing loading placeholder | — (always show feedback) |

---

## Correct Patterns

### Null-Guarding the Rive Instance in Effects

```tsx
const { rive, RiveComponent } = useRive({
  src: '/assets/characters/player.riv',
  stateMachines: 'CombatStateMachine',
  autoplay: true,
});

useEffect(() => {
  if (!rive) return;
  const attackInput = rive
    .stateMachineInputs('CombatStateMachine')
    ?.find(i => i.name === 'triggerAttack');
  attackInput?.fire();
}, [rive, triggerAttack]);
```

`rive` transitions null → instance once. Listing it as dependency ensures the effect fires at the exact moment it's ready.

---

### Using onLoad for One-Time Post-Load Setup

```tsx
const inputsRef = useRef<Record<string, StateMachineInput>>({});

const { rive, RiveComponent } = useRive({
  src: '/assets/characters/player.riv',
  stateMachines: 'CombatStateMachine',
  autoplay: true,
  onLoad: () => {
    const inputs = rive!.stateMachineInputs('CombatStateMachine') ?? [];
    inputs.forEach(input => { inputsRef.current[input.name] = input; });
  },
});
```

`onLoad` fires once after the Rive runtime signals artboard ready.

---

### Detecting Animation Completion via onStateChange

Do not use `setTimeout`. Use `onStateChange`:

```tsx
const { rive, RiveComponent } = useRive({
  src: '/assets/characters/player.riv',
  stateMachines: 'CombatStateMachine',
  autoplay: true,
  onStateChange: (event: StateChangeEvent) => {
    if (event.data.includes('idle')) {
      dispatch({ type: 'ANIMATION_COMPLETE' });
    }
  },
});
```

`onStateChange` is driven by Rive's internal clock, stays in sync regardless of frame rate.

---

### Bridging Rive Inputs to Zustand Store

Store a callback, not the Rive instance, in Zustand:

```tsx
const { rive, RiveComponent } = useRive({ ... });

useEffect(() => {
  if (!rive) return;
  useCombatStore.getState().registerFireInput(
    (inputName: string) => {
      const inputs = rive.stateMachineInputs('CombatStateMachine');
      inputs?.find(i => i.name === inputName)?.fire();
    }
  );
  return () => useCombatStore.getState().registerFireInput(null);
}, [rive]);
```

A callback defers instance lookup to call time, avoiding stale references.

---

## Pattern Catalog

### Guard Rive Instance Access in Effects

**Detection**:
```bash
grep -rn 'rive\.' --include="*.tsx" | grep -v 'useEffect\|onLoad\|onStateChange\|useCallback\|//' | grep -v 'RiveComponent\|useRive\|import'
```

**Signal**: `rive.stateMachineInputs(...)` outside a guarded effect — `rive` is null on first render, throws `TypeError`.

**Fix**: Move to `useEffect` with `[rive]` dependency and `if (!rive) return` guard.

---

### Use onStateChange for Animation Sequencing

**Detection**:
```bash
grep -rn 'setTimeout' --include="*.tsx" | grep -i 'anim\|rive\|attack\|hit\|state'
```

**Signal**: `setTimeout(() => { recoverInput?.fire(); }, 300)` — duration drifts from actual animation at non-60fps.

**Fix**: Use `onStateChange` to detect state transitions. In `@rive-app/react-canvas` 4.x, `event.data` is `string[]` of current state names.

---

### Use Effect Dependencies Instead of Polling

**Detection**:
```bash
grep -rn 'setInterval\|while.*rive\|poll' --include="*.tsx" | grep -i 'rive'
```

**Signal**: `setInterval` polling for `rive !== null`. Reimplements what `useRive` already does with `onLoad`.

**Fix**: Use `useEffect([rive])` or `onLoad` callback.

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| `TypeError: Cannot read properties of null (reading 'stateMachineInputs')` | `rive` accessed before load | `if (!rive) return` guard; `useEffect([rive])` |
| `useStateMachineInput returns null` | Input name typo or state machine name mismatch | Check Rive Editor for exact case-sensitive names |
| Animation fires once then stops | `autoplay: true` with one-shot, no loop | Use state machine with looping idle |
| `onStateChange` not firing | State machine name mismatch | Check `stateMachines:` param spelling |
| Inputs fire, no visual change | Wrong artboard selected | Add `artboard: 'ArtboardName'` param |

---

## Detection Commands

```bash
# Direct rive access outside effect/callback (null dereference risk)
grep -rn 'rive\.' --include="*.tsx" | grep -v 'useEffect\|onLoad\|onStateChange\|useCallback\|//'

# setTimeout animation sequencing (timing drift)
grep -rn 'setTimeout' --include="*.tsx" | grep -i 'anim\|attack\|hit\|fire\|input'

# Polling for rive instance
rg 'setInterval' --type tsx -l | xargs grep -l 'rive'

# Missing null guard in effects
grep -rn 'useEffect' --include="*.tsx" -A5 | grep -v 'if.*rive\|!rive' | grep 'rive\.'
```

---

## See Also

- `rive-react-setup.md` — Full `useRive` parameter reference
- `rive-performance.md` — WebGL cleanup, lazy loading, canvas sizing
- `rive-animation-library.md` — State machine design, `onStateChange` states
