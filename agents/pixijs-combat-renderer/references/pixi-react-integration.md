# @pixi/react v8 Integration Reference

> **Scope**: @pixi/react v8 + React 19, hybrid canvas/DOM, Zustand sharing, lazy loading, Vite splitting
> **Version range**: @pixi/react ^8.0.0, pixi.js ^8.5.0, React ^19.0.0, Vite ^5+
> **Note**: @pixi/react v8 requires React 19 — do not use with React 18.

---

## Installation

```bash
npm install pixi.js@^8 @pixi/react@^8
npm install @spd789562/pixi-v8-particle-emitter  # v8 particles
npm install pixi-filters                          # post-processing
```

---

## extend() API

Declare which PixiJS classes the reconciler knows about. Module-level, imported once:

```typescript
// src/combat/pixi-setup.ts
import { extend } from '@pixi/react';
import { Application, Container, Sprite, AnimatedSprite, ParticleContainer, Graphics, Text } from 'pixi.js';

extend({ Application, Container, Sprite, AnimatedSprite, ParticleContainer, Graphics, Text });
```

After extending: `Container` → `<container>`, `Sprite` → `<sprite>`, etc.

---

## Application Setup

```typescript
import './pixi-setup';
import { Application } from '@pixi/react';

export function PixiCombatCanvas({ width, height }: { width: number; height: number }) {
  return (
    <Application width={width} height={height} backgroundColor={0x000000}
      antialias resolution={window.devicePixelRatio} autoDensity
      onInit={(app) => { console.debug('[pixi] ready', app.renderer.type); }}>
      <CombatScene />
    </Application>
  );
}
```

---

## Hybrid Canvas + DOM Layout

PixiJS = canvas (combat). React DOM = UI chrome (HP bars, buttons). Stacked via CSS absolute positioning:

```typescript
const PixiCombatCanvas = React.lazy(() => import('../combat/PixiCombatCanvas').then(m => ({ default: m.PixiCombatCanvas })));

export function CombatScreen() {
  return (
    <div className="relative w-full h-screen overflow-hidden bg-black">
      <div className="absolute inset-0 pointer-events-none">
        <Suspense fallback={<div className="absolute inset-0 bg-black" />}>
          <PixiCombatCanvas width={1280} height={720} />
        </Suspense>
      </div>
      <div className="absolute inset-0 pointer-events-auto">
        <CombatHUD />
      </div>
    </div>
  );
}
```

Canvas layer: `pointer-events: none`. DOM UI: `pointer-events: auto`. Never put HP bars/buttons in PixiJS canvas.

---

## Zustand State Sharing

Both PixiJS and React DOM subscribe to the same store. PixiJS reads in ticker (zero re-renders), not in render:

```typescript
// PixiJS component — read via subscribe, mutate display objects directly
useEffect(() => {
  return useCombatStore.subscribe(
    (state) => state.lastEffectType,
    (effectType) => {
      if (!spriteRef.current || !effectType) return;
      if (effectType === 'hit') {
        spriteRef.current.tint = 0xff4444;
        setTimeout(() => { if (spriteRef.current) spriteRef.current.tint = 0xffffff; }, 150);
      }
    }
  );
}, []);

// React DOM — use hooks normally
const playerHP = useCombatStore((state) => state.playerHP);
```

---

## Lazy Loading + Vite Bundle Splitting

PixiJS ~800KB raw / ~250KB gzipped. Split from main bundle:

```typescript
// vite.config.ts
build: {
  chunkSizeWarningLimit: 900,
  rollupOptions: {
    output: {
      manualChunks(id: string) {
        if (id.includes('pixi.js') || id.includes('@pixi/') || id.includes('pixi-filters')) return 'pixi-vendor';
        if (id.includes('react') || id.includes('react-dom')) return 'react-vendor';
      },
    },
  },
},
```

Users on main menu never download PixiJS. Verify: `npx vite build && ls -lh dist/assets/ | grep pixi`

---

## useTick — Ticker Animation

Runs on `requestAnimationFrame`. No React re-renders — mutates display objects directly:

```typescript
useTick(() => {
  if (!spriteRef.current) return;
  spriteRef.current.y = BASE_Y + Math.sin(performance.now() / 1000 * Math.PI) * 8;
});
```

Must be inside `<Application>` tree.

---

## Sprite/Texture Loading

```typescript
export function useCombatTextures() {
  const [textures, setTextures] = useState<Record<string, Texture> | null>(null);
  useEffect(() => {
    Assets.load([
      { alias: 'player', src: '/sprites/player-sheet.json' },
      { alias: 'enemy', src: '/sprites/enemy-sheet.json' },
    ]).then(setTextures);
  }, []);
  return textures;
}
```

Never use `Texture.from()` for combat sprites in production — bypasses loading queue.

---

## AnimatedSprite

```typescript
const sheet = await Assets.load('/sprites/player-sheet.json');
const idleFrames = sheet.animations['idle'];

<animatedSprite textures={idleFrames} animationSpeed={0.1} loop autoPlay anchor={{ x: 0.5, y: 1 }} />
```

---

## Patterns to Fix

### Store Display Objects in useRef
```typescript
// WRONG: const [sprite, setSprite] = useState<Sprite | null>(null);
const spriteRef = useRef<Sprite>(null); // CORRECT
```

### Mutate in useTick, Not setState
```typescript
// WRONG: useTick(() => { setPosition(prev => prev + 1); });
useTick(() => { if (spriteRef.current) spriteRef.current.x += 1; }); // CORRECT
```

### extend() at Module Top Level
```typescript
// WRONG: function CombatCanvas() { extend({ Sprite }); ... }
extend({ Sprite }); // Module scope, runs once
```

### UI in DOM Layer
```typescript
// WRONG: <text text={`HP: ${hp}`} />
<div className="absolute top-4 left-4">HP: {hp}</div> // CORRECT
```
