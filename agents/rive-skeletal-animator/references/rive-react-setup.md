# Rive React Setup Reference
<!-- Loaded by rive-skeletal-animator when task involves: installing Rive, mounting canvas, useRive hook, useStateMachineInput, Zustand wiring, CombatEngine events, lazy loading, Vite WASM config -->

Rive's React runtime is `@rive-app/react-canvas` — a React wrapper over the Rive Web runtime that handles canvas lifecycle, WASM loading, and resize observation. Version 4.x supports React 16.8 through 19. The WASM bundle is ~150KB gzipped, so lazy loading to the combat screen only is worth the one-time setup cost.

## Installation

```bash
npm install @rive-app/react-canvas
```

No other dependencies. The WASM is bundled inside the npm package and loaded at runtime on first mount.

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

`RiveComponent` fills its container by default. Wrap in an explicit-sized div. Do not set width/height directly on `RiveComponent` — the canvas scales to the container.

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

`stateMachines` takes the name string exactly as defined in the Rive Editor — case-sensitive.

## Return Values

```ts
const {
  rive,            // Rive instance — null until loaded
  RiveComponent,   // JSX element — mount this in render
  setCanvasRef,    // ref setter for custom canvas placement
  setContainerRef, // ref setter for custom container placement
} = useRive(params);
```

The `rive` instance exposes the Web runtime API directly: `rive.play()`, `rive.pause()`, `rive.reset()`, `rive.stop()`.

## State Machine Inputs

`useStateMachineInput` grabs a reference to a named input from the active state machine.

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

Input name strings are case-sensitive and must match the Rive Editor exactly. A mismatch returns `null` silently. Log `useStateMachineInput` return values in dev to catch typos early.

## Input Object Types

| Input type | Hook return type | API |
|------------|-----------------|-----|
| Trigger | `SMITrigger \| null` | `.fire()` — one-shot event |
| Boolean | `SMIBoolean \| null` | `.value` (get/set boolean) |
| Number | `SMINumber \| null` | `.value` (get/set number) |

## Replacing img + motion.div

**Before (Framer Motion sprite):**
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

Remove the `motion.div` entirely. The idle bob is an animation state in the `.riv` file. Do not wrap `RiveComponent` in `motion.div` — Rive owns all animation.

## Wiring to Zustand Combat Store

Zustand state is the source of truth. Bridge changes to Rive inputs via `useEffect`. Never call `input.fire()` inside Zustand actions — keep Rive coupling inside the component.

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

### The timestamp trick for re-triggering same action type

Zustand `useEffect` won't re-fire if the same action type repeats consecutively. Use a timestamp to guarantee re-trigger:

```ts
// combatStore.ts
interface CombatAction {
  type: 'attack' | 'hit' | 'block_start' | 'block_end' | 'signature' | 'finisher' | 'idle';
  timestamp: number; // Date.now()
}

// In dispatchAction:
dispatchAction: (type) => set({ playerLastAction: { type, timestamp: Date.now() } }),
```

The timestamp change causes a new object reference on every dispatch, so the `useEffect` fires even for consecutive identical action types.

## CombatEngine Event Wiring

Wire CombatEngine events through the Zustand store rather than directly to Rive. CombatEngine stays decoupled from the renderer:

```ts
// CombatEngine.ts — when an attack lands
import { useCombatStore } from '../stores/combatStore';

function resolveAttack(attackerId: 'player' | 'enemy') {
  const store = useCombatStore.getState();
  store.dispatchAction(attackerId === 'player' ? 'attack' : 'idle');
  store.dispatchEnemyAction('hit'); // enemy character reacts
}
```

Components subscribe and fire their own Rive inputs. This keeps CombatEngine decoupled from `@rive-app/react-canvas`.

## Lazy Loading the Runtime

Load the WASM (~150KB gzip) only when the combat screen mounts:

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

Optional: preload on hover over the Fight button to hide download latency:

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
  // WASM handled automatically by Vite 5+ — no additional config needed
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

For a 400×400 artboard designed for that exact canvas size, `Fit.Contain` + `Alignment.BottomCenter` is the right default — no letterboxing, feet stay on the ground line.

## WebGL Context Limit

Browsers cap active WebGL contexts at 8–16 per page. The Canvas renderer (`@rive-app/react-canvas`) uses 2D canvas context — no WebGL, no context limit. Use this package for the AEW game's two-character setup. Only consider `@rive-app/react-webgl2-canvas` if profiling shows 2D canvas compositing as a bottleneck.

## onStateChange for Game Logic Sync

Signal animation completion back to the game engine without setTimeout:

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

CombatEngine listens for `animationComplete` before dispatching the next action, so it never races ahead of the active animation.

## Conditional Rendering

Unmount, don't hide. Hidden Rive canvases still animate and consume CPU:

```tsx
// Correct — unmount stops the Rive instance
{isCombatActive && <PlayerCharacter />}

// Wrong — hidden canvas keeps animating
<PlayerCharacter style={{ visibility: isCombatActive ? 'visible' : 'hidden' }} />
```

`useRive` cleans up the Rive instance automatically on unmount.

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

Cast to specific input type to access type-specific API:

```ts
const hitTrigger = useStateMachineInput(rive, SM, 'hit') as SMITrigger | null;
if (hitTrigger) hitTrigger.fire();

const healthInput = useStateMachineInput(rive, SM, 'health') as SMINumber | null;
if (healthInput) healthInput.value = 75;
```

## Isolation Pattern

Rive instances bind tightly to their canvas element. If you need isolated character instances (player and enemy must never share a Rive instance), ensure each character component mounts its own `useRive` call. Do not pass the `rive` instance from one component to another.
