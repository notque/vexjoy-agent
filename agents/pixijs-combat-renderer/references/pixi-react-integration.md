# @pixi/react v8 Integration Reference

> **Scope**: @pixi/react v8 setup with React 19, hybrid canvas/DOM mounting, Zustand state sharing, lazy loading, and Vite bundle splitting
> **Version range**: @pixi/react ^8.0.0, pixi.js ^8.5.0, React ^19.0.0, Vite ^5+
> **Compatibility note**: @pixi/react v8 is built exclusively for React 19 — it relies on React 19's internal reconciler APIs. Do not use with React 18.

---

## Installation

```bash
npm install pixi.js@^8 @pixi/react@^8
# For v8-compatible particles:
npm install @spd789562/pixi-v8-particle-emitter
# For post-processing filters:
npm install pixi-filters
```

---

## The extend() API

@pixi/react v8 does not import all of PixiJS automatically. You declare exactly which PixiJS classes the React reconciler should know about. This keeps bundle size proportional to what you use.

```typescript
// src/combat/pixi-setup.ts — module-level, imported once
import { extend } from '@pixi/react';
import {
  Application,
  Container,
  Sprite,
  AnimatedSprite,
  ParticleContainer,
  Graphics,
  Text,
} from 'pixi.js';

extend({
  Application,
  Container,
  Sprite,
  AnimatedSprite,
  ParticleContainer,
  Graphics,
  Text,
});
```

Import `pixi-setup.ts` at the top of `PixiCombatCanvas.tsx` before any JSX that uses PixiJS components. The extend call is idempotent — calling it multiple times with the same classes is safe, but calling it inside a component body on every render is wasteful and can cause reconciler state inconsistencies.

After extending, PixiJS classes become lowercase JSX elements:

```typescript
// Container → <container>
// Sprite    → <sprite>
// AnimatedSprite → <animatedSprite>
```

---

## Application Component Setup

```typescript
// src/combat/PixiCombatCanvas.tsx
import './pixi-setup';  // extend() call — must be first
import { Application } from '@pixi/react';
import { CombatScene } from './CombatScene';

interface PixiCombatCanvasProps {
  width: number;
  height: number;
}

export function PixiCombatCanvas({ width, height }: PixiCombatCanvasProps): React.JSX.Element {
  return (
    <Application
      width={width}
      height={height}
      backgroundColor={0x000000}
      antialias={true}
      resolution={window.devicePixelRatio}
      autoDensity={true}
      // onInit fires once after the renderer is ready — safe to access app.renderer here
      onInit={(app) => {
        console.debug('[pixi] renderer ready', app.renderer.type);
      }}
    >
      <CombatScene />
    </Application>
  );
}
```

The `resizeTo` prop accepts either an HTML element or a React ref, which allows the canvas to fill its container:

```typescript
const containerRef = useRef<HTMLDivElement>(null);

<div ref={containerRef} className="absolute inset-0">
  <Application resizeTo={containerRef} backgroundColor={0x1a1a2e}>
    <CombatScene />
  </Application>
</div>
```

---

## Hybrid Canvas + DOM Layout

PixiJS handles the canvas. React DOM handles the UI. They stack via CSS absolute positioning:

```typescript
// src/screens/CombatScreen.tsx
import React, { Suspense, useRef } from 'react';
import { CombatHUD } from '../components/CombatHUD';

const PixiCombatCanvas = React.lazy(() =>
  import('../combat/PixiCombatCanvas').then(m => ({ default: m.PixiCombatCanvas }))
);

export function CombatScreen(): React.JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null);

  return (
    // Outer container: relative positioning context
    <div ref={containerRef} className="relative w-full h-screen overflow-hidden bg-black">

      {/* Layer 1: PixiJS WebGL canvas — fills the container, pointer-events none */}
      <div className="absolute inset-0 pointer-events-none">
        <Suspense fallback={<div className="absolute inset-0 bg-black" />}>
          <PixiCombatCanvas width={containerRef.current?.clientWidth ?? 1280} height={containerRef.current?.clientHeight ?? 720} />
        </Suspense>
      </div>

      {/* Layer 2: React DOM UI — HP bars, card hand, ability buttons */}
      {/* pointer-events-auto so buttons receive clicks */}
      <div className="absolute inset-0 pointer-events-auto">
        <CombatHUD />
      </div>
    </div>
  );
}
```

Key layout rules:
- Canvas layer uses `pointer-events: none` so DOM UI receives all mouse/touch events
- DOM UI layer uses `pointer-events: auto` (default)
- Both layers fill the same container — use `absolute inset-0` on both
- Never put HP bars, card buttons, or text into the PixiJS canvas tree

---

## Zustand State Sharing

Zustand stores are module-level singletons. Both PixiJS display objects and React DOM components can subscribe to the same store slice. The key rule: PixiJS components should read store state in the ticker loop, not in React render — reading in render creates unnecessary re-renders.

```typescript
// src/stores/combatStore.ts
import { create } from 'zustand';

interface CombatState {
  playerHP: number;
  enemyHP: number;
  lastEffectType: string | null;
  setPlayerHP: (hp: number) => void;
  setEnemyHP: (hp: number) => void;
  triggerEffect: (type: string) => void;
}

export const useCombatStore = create<CombatState>((set) => ({
  playerHP: 100,
  enemyHP: 100,
  lastEffectType: null,
  setPlayerHP: (hp) => set({ playerHP: hp }),
  setEnemyHP: (hp) => set({ enemyHP: hp }),
  triggerEffect: (type) => set({ lastEffectType: type }),
}));
```

In PixiJS components, read state via `getState()` in the ticker (zero re-renders) and subscribe for display object updates:

```typescript
// src/combat/PlayerSprite.tsx
import { useRef, useEffect } from 'react';
import { useTick } from '@pixi/react';
import { useCombatStore } from '../stores/combatStore';
import type { Sprite } from 'pixi.js';

export function PlayerSprite(): React.JSX.Element {
  const spriteRef = useRef<Sprite>(null);

  // Subscribe to effect triggers — update display object directly, no React state
  useEffect(() => {
    return useCombatStore.subscribe(
      (state) => state.lastEffectType,
      (effectType) => {
        if (!spriteRef.current || !effectType) return;
        if (effectType === 'hit') {
          // Flash red on hit
          spriteRef.current.tint = 0xff4444;
          setTimeout(() => {
            if (spriteRef.current) spriteRef.current.tint = 0xffffff;
          }, 150);
        }
      }
    );
  }, []);

  // Idle bob via ticker — reads no state, mutates display object only
  useTick((ticker) => {
    if (!spriteRef.current) return;
    const t = performance.now() / 1000;
    spriteRef.current.y = 400 + Math.sin(t * Math.PI) * 8;
  });

  return (
    <sprite
      ref={spriteRef}
      texture={playerTexture}
      anchor={{ x: 0.5, y: 1 }}
      x={320}
      y={400}
    />
  );
}
```

React DOM components use the store normally via hooks — HP bars re-render on HP changes:

```typescript
// src/components/CombatHUD.tsx
export function CombatHUD(): React.JSX.Element {
  const playerHP = useCombatStore((state) => state.playerHP);
  const enemyHP = useCombatStore((state) => state.enemyHP);

  return (
    <div className="absolute top-4 left-0 right-0 flex justify-between px-8">
      <HPBar current={playerHP} max={100} label="Player" />
      <HPBar current={enemyHP} max={100} label="Enemy" />
    </div>
  );
}
```

---

## Lazy Loading + Vite Bundle Splitting

PixiJS v8 is ~800KB raw / ~250KB gzipped. Splitting it from the main bundle prevents it from blocking the initial page load.

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    // Suppress the 500KB warning — pixi-vendor will exceed it by design
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          // Isolate all PixiJS modules into a single lazy chunk
          if (id.includes('pixi.js') || id.includes('@pixi/') || id.includes('pixi-filters')) {
            return 'pixi-vendor';
          }
          // Separate React into its own stable cache chunk
          if (id.includes('react') || id.includes('react-dom')) {
            return 'react-vendor';
          }
        },
      },
    },
  },
});
```

The `pixi-vendor` chunk only loads when `CombatScreen` mounts because `PixiCombatCanvas` is imported via `React.lazy`. Users on the main menu never download PixiJS.

Verify the split worked after building:

```bash
npx vite build && ls -lh dist/assets/ | grep pixi
# Should see: pixi-vendor-[hash].js around 800KB (250KB gzipped)
```

---

## useTick — Ticker-Driven Animation

`useTick` from `@pixi/react` runs a callback on every `requestAnimationFrame`. It does not trigger React re-renders — it mutates display objects directly.

```typescript
import { useTick } from '@pixi/react';
import { useRef } from 'react';
import type { Sprite } from 'pixi.js';

// Idle bobbing animation — zero React overhead
export function IdleBobbingSprite(): React.JSX.Element {
  const spriteRef = useRef<Sprite>(null);

  useTick(() => {
    if (!spriteRef.current) return;
    const t = performance.now() / 1000;
    // Sine wave: amplitude 8px, period 2s
    spriteRef.current.y = BASE_Y + Math.sin(t * Math.PI) * 8;
  });

  return <sprite ref={spriteRef} texture={texture} />;
}
```

`useTick` must be called inside a component that is a descendant of `<Application>`. Calling it outside the Application tree throws: `useTick called outside Application context`.

---

## useApp — Access the PixiJS Application

```typescript
import { useApp } from '@pixi/react';

export function DebugOverlay(): React.JSX.Element {
  const app = useApp();

  useEffect(() => {
    // Access renderer type, resolution, screen size
    console.debug('Renderer:', app.renderer.type === 1 ? 'WebGPU' : 'WebGL');
    console.debug('Resolution:', app.renderer.resolution);
    console.debug('Screen:', app.screen.width, 'x', app.screen.height);
  }, [app]);

  return null;
}
```

---

## Sprite and Texture Loading

Load textures via `Assets.load()` before the canvas mounts, or use a loading state:

```typescript
import { Assets, Texture } from 'pixi.js';
import { useState, useEffect } from 'react';

export function useCombatTextures() {
  const [textures, setTextures] = useState<Record<string, Texture> | null>(null);

  useEffect(() => {
    Assets.load([
      { alias: 'player', src: '/sprites/player-sheet.json' },
      { alias: 'enemy', src: '/sprites/enemy-sheet.json' },
      { alias: 'arena', src: '/sprites/arena-bg.webp' },
    ]).then((loaded) => {
      setTextures({
        player: loaded.player,
        enemy: loaded.enemy,
        arena: loaded.arena,
      });
    });
  }, []);

  return textures;
}
```

Never use `Texture.from()` for combat sprites in production — it bypasses the asset loading queue and causes individual network requests per sprite. Use `Assets.load()` with a spritesheet JSON.

---

## AnimatedSprite for Frame Animations

```typescript
import { AnimatedSprite, Assets } from 'pixi.js';

// Load a spritesheet JSON (TexturePacker format)
const sheet = await Assets.load('/sprites/player-sheet.json');

// Access named animations from the spritesheet
const idleFrames = sheet.animations['idle'];    // Array<Texture>
const attackFrames = sheet.animations['attack'];

// In JSX:
<animatedSprite
  textures={idleFrames}
  animationSpeed={0.1}  // frames per tick (60fps ticker → ~6fps animation)
  loop={true}
  autoPlay={true}
  anchor={{ x: 0.5, y: 1 }}
  x={320}
  y={400}
/>
```

---

## Anti-Patterns

### ❌ Storing display objects in React state
```typescript
// WRONG — triggers reconciliation on every mutation
const [sprite, setSprite] = useState<Sprite | null>(null);
setSprite(existingSprite); // causes re-render
```
```typescript
// CORRECT — useRef bypasses React state
const spriteRef = useRef<Sprite>(null);
```

### ❌ Animating via React setState in useTick
```typescript
// WRONG — 60 setState calls per second = 60 React re-renders per second
useTick(() => {
  setPosition(prev => prev + 1); // catastrophic
});
```
```typescript
// CORRECT — mutate the display object directly
useTick(() => {
  if (spriteRef.current) spriteRef.current.x += 1;
});
```

### ❌ Calling extend() inside a component
```typescript
// WRONG — re-registers on every render
function CombatCanvas() {
  extend({ Sprite, Container }); // runs every render
  return <Application>...</Application>;
}
```
```typescript
// CORRECT — module top-level, runs once at import time
extend({ Sprite, Container });
function CombatCanvas() {
  return <Application>...</Application>;
}
```

### ❌ Rendering UI in the PixiJS tree
```typescript
// WRONG — PixiJS Text has no accessibility, no DOM events
<text text={`HP: ${playerHP}`} x={10} y={10} />
```
```typescript
// CORRECT — HP bars are DOM elements, overlaid via CSS
<div className="absolute top-4 left-4">HP: {playerHP}</div>
```
