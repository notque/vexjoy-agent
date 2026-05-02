# Rive React Setup Reference
<!-- Loaded by rive-skeletal-animator when task involves: installing Rive, mounting canvas, useRive hook, useStateMachineInput, Zustand wiring, CombatEngine events, lazy loading, Vite WASM config -->

`@rive-app/react-canvas` — React wrapper over Rive Web runtime. Handles canvas lifecycle, WASM loading, resize. Version 4.x supports React 16.8–19. WASM bundle ~150KB gzip.

## Installation

```bash
npm install @rive-app/react-canvas
```

WASM bundled in npm package, loaded at runtime on first mount.

## Basic useRive Pattern

```tsx
import { useRive } from '@rive-app/react-canvas';

function PlayerCharacter() {
  const { RiveComponent, rive } = useRive({
    src: '/assets/characters/player.riv',
    stateMachines: 'CombatStateMachine',
    autoplay: true,
  });

  // rive is null until the .riv file loads — always guard before use
  useEffect(() => {
    if (!rive) return;
    // rive instance is ready here
  }, [rive]);

  return (
    <div style={{ width: 400, height: 400, position: 'relative' }}>
      <RiveComponent />
    </div>
  );
}
```

`RiveComponent` fills its container. Wrap in explicit-sized div. Do not set width/height on `RiveComponent` directly.

## useRive Parameters

```ts
useRive({
  src: string,                   // path to .riv file, or ArrayBuffer
  artboard?: string,             // specific artboard (default: first artboard)
  animations?: string | string[], // animation clip names to play directly (no state machine)
  stateMachines?: string | string[], // state machine name(s) to activate
  autoplay?: boolean,            // default: false — set true for immediate playback
  layout?: Layout,               // canvas fit/alignment — import Layout from @rive-app/react-canvas
  onLoad?: () => void,           // fires when .riv finishes loading
  onStateChange?: (event: StateChangeEvent) => void, // fires on state machine transition
  onPlay?: () => void,
  onPause?: () => void,
  onStop?: () => void,
})
```

`stateMachines` name is case-sensitive, must match Rive Editor exactly.

## Return Values

```ts
const {
  rive,            // Rive instance — null until loaded
  RiveComponent,   // JSX element — mount this in render
  setCanvasRef,    // ref setter for custom canvas placement
  setContainerRef, // ref setter for custom container placement
} = useRive(params);
```

`rive` exposes Web runtime API: `rive.play()`, `rive.pause()`, `rive.reset()`, `rive.stop()`.

## State Machine Inputs

`useStateMachineInput` returns a reference to a named input from the active state machine.

```tsx
import { useRive, useStateMachineInput } from '@rive-app/react-canvas';

const SM = 'CombatStateMachine'; // exact name from Rive Editor

function PlayerCharacter() {
  const { RiveComponent, rive } = useRive({
    src: playerRiv,
    stateMachines: SM,
    autoplay: true,
  });

  // Trigger — one-shot event (attack, hit, signature)
  const attackTrigger = useStateMachineInput(rive, SM, 'attack');
  const hitTrigger    = useStateMachineInput(rive, SM, 'hit');

  // Boolean — sustained state (blocking, stunned)
  const blockInput    = useStateMachineInput(rive, SM, 'isBlocking');

  // Number — health, charge level, anger meter
  const healthInput   = useStateMachineInput(rive, SM, 'health');

  // All inputs are null until rive loads — always guard
  const fireAttack = () => { if (attackTrigger) attackTrigger.fire(); };
  const setBlock   = (v: boolean) => { if (blockInput) blockInput.value = v; };
  const setHealth  = (hp: number) => { if (healthInput) healthInput.value = hp; };

  return <div style={{ width: 400, height: 400 }}><RiveComponent /></div>;
}
```

Input names are case-sensitive, must match Rive Editor. Mismatch returns `null` silently — log return values in dev to catch typos.

## Input Object Types

| Input type | Hook return type | API |
|------------|-----------------|-----|
| Trigger | `SMITrigger \| null` | `.fire()` — one-shot event |
| Boolean | `SMIBoolean \| null` | `.value` (get/set boolean) |
| Number | `SMINumber \| null` | `.value` (get/set number) |

## Replacing img + motion.div

**Before:**
```tsx
<motion.div
  animate={{ y: [0, -3, 0] }}
  transition={{ duration: 4, repeat: Infinity }}
  style={{ width: 400, height: 400 }}
>
  <img src="/sprites/player.png" alt="player" style={{ width: '100%' }} />
</motion.div>
```

**After (Rive):**
```tsx
<div style={{ width: 400, height: 400 }}>
  <RiveComponent />
</div>
```

Remove `motion.div` entirely. Idle bob lives in the `.riv` file. Do not wrap `RiveComponent` in `motion.div`.

## Wiring to Zustand Combat Store

Zustand is source of truth. Bridge to Rive inputs via `useEffect`. Never call `input.fire()` inside Zustand actions — keep Rive coupling in the component.

```tsx
import { useRive, useStateMachineInput } from '@rive-app/react-canvas';
import { useCombatStore } from '../stores/combatStore';
import playerRiv from '../assets/characters/player.riv?url';

const SM = 'CombatStateMachine';

function PlayerCharacter() {
  const { RiveComponent, rive } = useRive({ src: playerRiv, stateMachines: SM, autoplay: true });

  const attackTrigger = useStateMachineInput(rive, SM, 'attack');
  const hitTrigger    = useStateMachineInput(rive, SM, 'hit');
  const blockInput    = useStateMachineInput(rive, SM, 'isBlocking');

  // Subscribe only to what this component needs
  const lastAction = useCombatStore(s => s.playerLastAction);
  const isBlocking = useCombatStore(s => s.playerIsBlocking);

  useEffect(() => {
    if (lastAction.type === 'attack' && attackTrigger) attackTrigger.fire();
    if (lastAction.type === 'hit'    && hitTrigger)    hitTrigger.fire();
  }, [lastAction, attackTrigger, hitTrigger]);

  useEffect(() => {
    if (blockInput) blockInput.value = isBlocking;
  }, [isBlocking, blockInput]);

  return <div style={{ width: 400, height: 400 }}><RiveComponent /></div>;
}
```

### Timestamp trick for re-triggering same action type

`useEffect` won't re-fire for consecutive identical action types. Use a timestamp:

```ts
// combatStore.ts
interface CombatAction {
  type: 'attack' | 'hit' | 'block_start' | 'block_end' | 'signature' | 'finisher' | 'idle';
  timestamp: number; // Date.now()
}

// In dispatchAction:
dispatchAction: (type) => set({ playerLastAction: { type, timestamp: Date.now() } }),
```

Timestamp change creates new object reference, forcing `useEffect` to fire.

## CombatEngine Event Wiring

Wire CombatEngine events through Zustand, not directly to Rive:

```ts
// CombatEngine.ts — when an attack lands
import { useCombatStore } from '../stores/combatStore';

function resolveAttack(attackerId: 'player' | 'enemy') {
  const store = useCombatStore.getState();
  store.dispatchAction(attackerId === 'player' ? 'attack' : 'idle');
  store.dispatchEnemyAction('hit'); // enemy character reacts
}
```

Components subscribe and fire their own Rive inputs. CombatEngine stays decoupled from `@rive-app/react-canvas`.

## Lazy Loading the Runtime

Load WASM only when combat screen mounts:

```tsx
// CombatScreen.tsx
import { lazy, Suspense } from 'react';

const CombatArena = lazy(() => import('./CombatArena'));

export function CombatScreen() {
  return (
    <Suspense fallback={<CombatLoadingScreen />}>
      <CombatArena />
    </Suspense>
  );
}
```

Preload on hover to hide download latency:

```tsx
function FightButton({ onClick }: { onClick: () => void }) {
  const handleMouseEnter = () => {
    import('@rive-app/react-canvas'); // prime the cache
  };
  return <button onMouseEnter={handleMouseEnter} onClick={onClick}>Fight</button>;
}
```

## Vite 7 Configuration

```ts
// vite.config.ts
export default defineConfig({
  assetsInclude: ['**/*.riv'],
});
```

Import `.riv` files with `?url` for content-hash cache busting:

```tsx
import playerRiv from '../assets/characters/player.riv?url';
const { RiveComponent } = useRive({ src: playerRiv, ... });
```

## Layout and Fit Options

```tsx
import { useRive, Layout, Fit, Alignment } from '@rive-app/react-canvas';

const { RiveComponent } = useRive({
  src: playerRiv,
  stateMachines: SM,
  layout: new Layout({
    fit: Fit.Contain,             // Fit.Cover fills container, may crop
    alignment: Alignment.BottomCenter, // keeps feet grounded
  }),
  autoplay: true,
});
```

For 400x400 artboard: `Fit.Contain` + `Alignment.BottomCenter` — no letterboxing, feet grounded.

## WebGL Context Limit

`@rive-app/react-canvas` uses 2D canvas context — no WebGL, no context limit. Use for the AEW game's two-character setup. Only consider `@rive-app/react-webgl2-canvas` if profiling shows 2D canvas as bottleneck.

## onStateChange for Game Logic Sync

Signal animation completion without setTimeout:

```tsx
const { RiveComponent } = useRive({
  src: playerRiv,
  stateMachines: SM,
  autoplay: true,
  onStateChange: (event) => {
    const stateName = event.data[0];
    if (stateName === 'idle') {
      useCombatStore.getState().setAnimationComplete('player');
    }
  },
});
```

CombatEngine waits for `animationComplete` before dispatching next action.

## Conditional Rendering

Unmount, don't hide. Hidden canvases still animate and consume CPU:

```tsx
// Correct — unmount stops the Rive instance
{isCombatActive && <PlayerCharacter />}

// Wrong — hidden canvas keeps animating
<PlayerCharacter style={{ visibility: isCombatActive ? 'visible' : 'hidden' }} />
```

`useRive` cleans up automatically on unmount.

## TypeScript Types

```ts
import type {
  Rive,
  StateMachineInput,
  SMIBoolean,
  SMINumber,
  SMITrigger,
  StateChangeEvent,
  Layout,
  Fit,
  Alignment,
} from '@rive-app/react-canvas';
```

Cast to specific input type:

```ts
const hitTrigger = useStateMachineInput(rive, SM, 'hit') as SMITrigger | null;
if (hitTrigger) hitTrigger.fire();

const healthInput = useStateMachineInput(rive, SM, 'health') as SMINumber | null;
if (healthInput) healthInput.value = 75;
```

## Isolation Pattern

Each character component must mount its own `useRive` call. Do not share `rive` instances between components — player and enemy must never share a Rive instance.
