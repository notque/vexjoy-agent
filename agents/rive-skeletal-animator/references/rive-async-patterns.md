# Rive Async Patterns Reference

> **Scope**: Async instance lifecycle, null-guarding the `rive` instance, loading states, and event callback sequencing. Does not cover state machine design (see `rive-animation-library.md`) or canvas sizing (see `rive-performance.md`).
> **Version range**: `@rive-app/react-canvas` 4.x, React 18/19
> **Generated**: 2026-04-14

---

## Overview

`useRive` returns a null `rive` instance until the `.riv` file is fetched and the WASM runtime is initialized. This async gap is the most common source of runtime errors in Rive integrations — firing inputs before the instance is ready silently fails or throws. Three things must be guarded: state machine input access, manual playback calls, and any Zustand/store bridging that depends on the live instance.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `if (!rive) return` guard in `useEffect` | 4.x+ | accessing rive instance in effects | synchronous render path (no effect needed) |
| `onLoad` callback for post-load setup | 4.x+ | running setup once after .riv fully loads | polling rive for non-null in effects |
| `onStateChange` for animation complete detection | 4.x+ | waiting for animation to finish before next action | setTimeout-based animation sequencing |
| `isLoading` from `useRive` return | 4.x+ | showing loading placeholder | always — should always show some feedback |

---

## Correct Patterns

### Null-Guarding the Rive Instance in Effects

`rive` is `null` on the first render and remains null until the `.riv` file loads and the WASM runtime initializes.

```tsx
const { rive, RiveComponent } = useRive({
  src: '/assets/characters/player.riv',
  stateMachines: 'CombatStateMachine',
  autoplay: true,
});

// Correct: guard in effect with rive as dependency
useEffect(() => {
  if (!rive) return;  // Skip until loaded
  const attackInput = rive
    .stateMachineInputs('CombatStateMachine')
    ?.find(i => i.name === 'triggerAttack');
  attackInput?.fire();
}, [rive, triggerAttack]);  // Re-runs when rive becomes non-null
```

**Why**: `rive` transitions from `null` → instance once after load. Listing `rive` as an effect dependency ensures the effect re-fires at the exact moment the instance is ready, without polling.

---

### Using onLoad for One-Time Post-Load Setup

For setup that should run exactly once after the `.riv` file loads (caching input refs, logging, telemetry), use `onLoad` instead of an effect.

```tsx
const inputsRef = useRef<Record<string, StateMachineInput>>({});

const { rive, RiveComponent } = useRive({
  src: '/assets/characters/player.riv',
  stateMachines: 'CombatStateMachine',
  autoplay: true,
  onLoad: () => {
    // rive is guaranteed non-null here
    const inputs = rive!
      .stateMachineInputs('CombatStateMachine') ?? [];
    inputs.forEach(input => {
      inputsRef.current[input.name] = input;
    });
    console.debug('Rive loaded, inputs cached:', Object.keys(inputsRef.current));
  },
});
```

**Why**: `onLoad` fires once after the Rive runtime signals the artboard is ready. Using an effect with `rive` dependency also works, but `onLoad` is more semantically correct for initialization logic.

---

### Detecting Animation Completion via onStateChange

Do not use `setTimeout` to wait for an animation to finish. Use `onStateChange` to detect when the state machine transitions.

```tsx
const { rive, RiveComponent } = useRive({
  src: '/assets/characters/player.riv',
  stateMachines: 'CombatStateMachine',
  autoplay: true,
  onStateChange: (event: StateChangeEvent) => {
    // event.data is string[] of active state names
    if (event.data.includes('idle')) {
      // Animation returned to idle — safe to queue next action
      dispatch({ type: 'ANIMATION_COMPLETE' });
    }
  },
});
```

**Why**: `setTimeout` durations drift from actual animation completion if frame rate drops below 60fps. `onStateChange` is driven by the Rive runtime's internal clock, which stays in sync with the playing animation regardless of frame rate.

---

### Bridging Rive Inputs to Zustand Store

Store a callback (not the Rive instance) in Zustand so other components can fire inputs without holding a direct reference to the async instance.

```tsx
// In the character component
const { rive, RiveComponent } = useRive({ ... });

useEffect(() => {
  if (!rive) return;
  // Register a callback, not the rive instance
  useCombatStore.getState().registerFireInput(
    (inputName: string) => {
      const inputs = rive.stateMachineInputs('CombatStateMachine');
      inputs?.find(i => i.name === inputName)?.fire();
    }
  );
  return () => useCombatStore.getState().registerFireInput(null);
}, [rive]);
```

**Why**: Zustand stores are not aware of React rendering. Storing the Rive instance directly would give the store a reference to the object before it's initialized (when `rive` is still null), and the store would hold a stale reference after cleanup. A callback defers the instance lookup to call time.

---

## Anti-Pattern Catalog

### ❌ Accessing Rive Instance Outside Effect or Callback

**Detection**:
```bash
grep -rn 'rive\.' --include="*.tsx" | grep -v 'useEffect\|onLoad\|onStateChange\|useCallback\|//' | grep -v 'RiveComponent\|useRive\|import'
rg '^\s+rive\.' --type tsx
```

**What it looks like**:
```tsx
function PlayerCharacter() {
  const { rive, RiveComponent } = useRive({ ... });

  // BUG: rive is null on first render
  rive.stateMachineInputs('CombatStateMachine')?.find(i => i.name === 'triggerAttack')?.fire();

  return <div><RiveComponent /></div>;
}
```

**Why wrong**: On the first render, `rive` is `null`. Calling `.stateMachineInputs()` on null throws `TypeError: Cannot read properties of null`. React will catch this and unmount the component. No error appears in the Rive runtime — the throw happens before Rive is even involved.

**Fix**: Move to `useEffect` with `rive` in the dependency array and guard with `if (!rive) return`.

---

### ❌ Using setTimeout for Animation Sequencing

**Detection**:
```bash
grep -rn 'setTimeout' --include="*.tsx" | grep -i 'anim\|rive\|attack\|hit\|state'
rg 'setTimeout.*anim' --type tsx
```

**What it looks like**:
```tsx
const handleAttack = () => {
  attackInput?.fire();
  setTimeout(() => {
    recoverInput?.fire(); // assume attack finishes in 300ms
  }, 300);
};
```

**Why wrong**: Animation duration in the Rive editor and the `setTimeout` duration in code drift independently. When a designer adjusts the `attack_strike` clip from 0.3s to 0.25s, the `setTimeout` stays at 300ms — recovery fires 50ms late. At 30fps (mobile under load), actual clip duration is longer still.

**Fix**: Use `onStateChange` to detect when the state machine enters `attack_recover` or `idle`, then dispatch the next action.

**Version note**: `onStateChange` was present in Rive Web runtime 1.x but the event shape changed in 2.x. In `@rive-app/react-canvas` 4.x, `event.data` is `string[]` of current state names.

---

### ❌ Polling rive for Non-Null in a Loop or Interval

**Detection**:
```bash
grep -rn 'setInterval\|while.*rive\|poll' --include="*.tsx" | grep -i 'rive'
rg 'setInterval' --type tsx -l | xargs grep -l 'rive'
```

**What it looks like**:
```tsx
useEffect(() => {
  const poll = setInterval(() => {
    if (rive) {
      clearInterval(poll);
      rive.play();
    }
  }, 50);
  return () => clearInterval(poll);
}, []);
```

**Why wrong**: This re-implements what `useRive` already does with `onLoad`. It's 10-20 polling ticks wasted before the instance is ready, and it captures the `rive` ref from the closure — missing the actual update if React doesn't re-render between polls.

**Fix**: Use `useEffect` with `[rive]` dependency array, or pass `onLoad` callback to `useRive`.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `TypeError: Cannot read properties of null (reading 'stateMachineInputs')` | `rive` accessed before load | Add `if (!rive) return` guard; move to `useEffect([rive])` |
| `useStateMachineInput returns null` | Input name typo or state machine name mismatch | Check Rive Editor for exact case-sensitive names; log `rive.stateMachineInputs(machineName)?.map(i => i.name)` to verify |
| Animation fires once on load then never again | `autoplay: true` with a one-shot animation, no loop | Set `animations: ['clip']` + `rive.loop()`, or use state machine with looping idle state |
| `onStateChange` not firing | State machine name passed to `useRive` does not match `.riv` exactly | Check `stateMachines:` param spelling matches the Rive Editor string |
| Inputs fire but no visual change | Wrong artboard selected | Add `artboard: 'ArtboardName'` param — defaults to first artboard, which may not be the combat one |

---

## Detection Commands Reference

```bash
# Direct rive instance access outside effect/callback (null dereference risk)
grep -rn 'rive\.' --include="*.tsx" | grep -v 'useEffect\|onLoad\|onStateChange\|useCallback\|//'

# setTimeout-based animation sequencing (timing drift risk)
grep -rn 'setTimeout' --include="*.tsx" | grep -i 'anim\|attack\|hit\|fire\|input'

# Polling for rive instance (anti-pattern)
rg 'setInterval' --type tsx -l | xargs grep -l 'rive'

# Missing rive null guard in effects
grep -rn 'useEffect' --include="*.tsx" -A5 | grep -v 'if.*rive\|!rive' | grep 'rive\.'

# useStateMachineInput without null check
grep -rn 'useStateMachineInput' --include="*.tsx" -A3 | grep -v 'if\|?\.'
```

---

## See Also

- `rive-react-setup.md` — Full `useRive` parameter reference, `useStateMachineInput` patterns
- `rive-performance.md` — WebGL context cleanup, lazy loading, canvas sizing
- `rive-animation-library.md` — State machine design, `onStateChange` event states
