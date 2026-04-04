# PixiJS v8 Particle Systems Reference

> **Scope**: GPU particles with @spd789562/pixi-v8-particle-emitter, wrestling-specific effect presets, DOM particle replacement
> **Version range**: pixi.js ^8.5.0, @spd789562/pixi-v8-particle-emitter (JSR package)
> **Context**: The game's effects.ts creates DOM elements per particle with setTimeout removal — this is the primary replacement target

---

## Why Replace DOM Particles

The DOM particle pattern in `effects.ts`:

```typescript
// Current effects.ts anti-pattern — causes reflow on every particle
function spawnStrikeEffect(x: number, y: number): void {
  const el = document.createElement('div');
  el.className = 'particle strike-particle';
  el.style.left = `${x}px`;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 300);  // no RAF coordination
}
```

GPU particles via `ParticleContainer`: 1000 particles = 1 draw call. No DOM, no reflow, no style recalc. PixiJS v8 `ParticleContainer` handles 1M particles at 60fps on desktop.

---

## Installation

`@spd789562/pixi-v8-particle-emitter` is on JSR (not npm — the original `@pixi/particle-emitter` is v7 only):

```bash
npx jsr add @spd789562/particle-emitter
# or
pnpm dlx jsr add @spd789562/particle-emitter
```

---

## Core Emitter Setup

```typescript
// src/combat/particles/ParticleManager.ts
import { Emitter } from '@spd789562/particle-emitter';
import { ParticleContainer, Assets } from 'pixi.js';
import type { Container, EmitterConfig } from 'pixi.js';

export class ParticleManager {
  private particleContainer: ParticleContainer;
  private activeEmitters: Map<string, Emitter> = new Map();

  constructor(parentContainer: Container) {
    // maxSize covers burst peak — finisher emits 50 at once
    this.particleContainer = new ParticleContainer(5000, {
      position: true, alpha: true, scale: true, rotation: true, tint: true,
    });
    parentContainer.addChild(this.particleContainer);
  }

  update(deltaMS: number): void {
    for (const [id, emitter] of this.activeEmitters) {
      emitter.update(deltaMS * 0.001);
      if (!emitter.emit && emitter.particleCount === 0) {
        emitter.destroy();
        this.activeEmitters.delete(id);
      }
    }
  }

  async spawnEffect(type: WrestlingEffect, x: number, y: number): Promise<void> {
    const config = EFFECT_CONFIGS[type];
    if (!config) return;
    const texture = await Assets.load(config.texturePath);
    const emitter = new Emitter(this.particleContainer, { ...config.emitterConfig, pos: { x, y } });
    this.activeEmitters.set(`${type}-${Date.now()}`, emitter);
  }

  destroy(): void {
    for (const emitter of this.activeEmitters.values()) emitter.destroy();
    this.activeEmitters.clear();
    this.particleContainer.destroy();
  }
}
```

---

## Wrestling Effect Presets

All presets follow the same `EmitterConfig` shape. Key fields:
- `emitterLifetime: 0.05-0.15` = burst (one-shot); `-1` = infinite (manual stop)
- `maxParticles`: set to burst peak, not average — silent drops if too low
- `frequency`: lower = faster emission (0.001 = nearly instant burst)

### Strike Impact — orange/gold radial burst, 300ms

```typescript
const STRIKE_CONFIG: EmitterConfig = {
  lifetime: { min: 0.15, max: 0.3 },
  frequency: 0.001, emitterLifetime: 0.05, maxParticles: 20,
  pos: { x: 0, y: 0 },
  behaviors: [
    { type: 'alpha', config: { alpha: { list: [{ value: 1, time: 0 }, { value: 0, time: 1 }] } } },
    { type: 'scale', config: { scale: { list: [{ value: 0.8, time: 0 }, { value: 0.1, time: 1 }] }, minMult: 0.5 } },
    { type: 'color', config: { color: { list: [{ value: 'ff9500', time: 0 }, { value: 'ffcc00', time: 0.5 }, { value: 'ffffff', time: 1 }] } } },
    { type: 'moveSpeedStatic', config: { min: 200, max: 400 } },
    { type: 'rotationStatic', config: { min: 0, max: 360 } },
    { type: 'spawnShape', config: { type: 'circle', data: { radius: 5 } } },
  ],
};
```

### Aerial Landing — dust cloud + impact ring, 500ms

```typescript
const AERIAL_CONFIG: EmitterConfig = {
  lifetime: { min: 0.3, max: 0.5 },
  frequency: 0.002, emitterLifetime: 0.1, maxParticles: 25,
  pos: { x: 0, y: 0 },
  behaviors: [
    { type: 'alpha', config: { alpha: { list: [{ value: 0.8, time: 0 }, { value: 0, time: 1 }] } } },
    { type: 'scale', config: { scale: { list: [{ value: 0.3, time: 0 }, { value: 1.5, time: 1 }] } } },
    { type: 'color', config: { color: { list: [{ value: 'c8a882', time: 0 }, { value: '806040', time: 1 }] } } },
    { type: 'moveSpeedStatic', config: { min: 50, max: 150 } },
    { type: 'rotationStatic', config: { min: 0, max: 360 } },
    { type: 'spawnShape', config: { type: 'circle', data: { radius: 30 } } },
  ],
};
```

### Submission Hold — blue/teal tendrils, continuous until stopped

```typescript
const SUBMISSION_CONFIG: EmitterConfig = {
  lifetime: { min: 0.5, max: 1.0 },
  frequency: 0.05, emitterLifetime: -1, maxParticles: 60,  // -1 = infinite
  pos: { x: 0, y: 0 },
  behaviors: [
    { type: 'alpha', config: { alpha: { list: [{ value: 0, time: 0 }, { value: 0.8, time: 0.2 }, { value: 0, time: 1 }] } } },
    { type: 'scale', config: { scale: { list: [{ value: 0.2, time: 0 }, { value: 0.6, time: 0.5 }, { value: 0.1, time: 1 }] }, minMult: 0.3 } },
    { type: 'color', config: { color: { list: [{ value: '00c8ff', time: 0 }, { value: '0080c0', time: 0.5 }, { value: '004080', time: 1 }] } } },
    { type: 'moveSpeedStatic', config: { min: 20, max: 80 } },
    { type: 'spawnShape', config: { type: 'circle', data: { radius: 15 } } },
  ],
};
// Stop: emitter.emit = false; let particles exhaust naturally
```

### Block Shield — cyan flash + scatter, 200ms

```typescript
const BLOCK_CONFIG: EmitterConfig = {
  lifetime: { min: 0.1, max: 0.2 },
  frequency: 0.001, emitterLifetime: 0.02, maxParticles: 15,
  pos: { x: 0, y: 0 },
  behaviors: [
    { type: 'alpha', config: { alpha: { list: [{ value: 1, time: 0 }, { value: 0, time: 1 }] } } },
    { type: 'scale', config: { scale: { list: [{ value: 1.0, time: 0 }, { value: 0.2, time: 1 }] } } },
    { type: 'color', config: { color: { list: [{ value: '80ffff', time: 0 }, { value: '0080ff', time: 1 }] } } },
    { type: 'moveSpeedStatic', config: { min: 100, max: 300 } },
    { type: 'rotationStatic', config: { min: 0, max: 360 } },
    { type: 'spawnShape', config: { type: 'circle', data: { radius: 10 } } },
  ],
};
```

### Finisher — screen-filling gold explosion, 40+ particles, 1s

```typescript
const FINISHER_CONFIG: EmitterConfig = {
  lifetime: { min: 0.5, max: 1.0 },
  frequency: 0.001, emitterLifetime: 0.15, maxParticles: 50,
  pos: { x: 0, y: 0 },
  behaviors: [
    { type: 'alpha', config: { alpha: { list: [{ value: 1, time: 0 }, { value: 0.8, time: 0.5 }, { value: 0, time: 1 }] } } },
    { type: 'scale', config: { scale: { list: [{ value: 1.5, time: 0 }, { value: 0.2, time: 1 }] }, minMult: 0.8 } },
    { type: 'color', config: { color: { list: [{ value: 'ffffff', time: 0 }, { value: 'ffdd00', time: 0.3 }, { value: 'ff8800', time: 0.7 }, { value: 'ff2200', time: 1 }] } } },
    { type: 'moveSpeedStatic', config: { min: 150, max: 500 } },
    { type: 'rotationStatic', config: { min: 0, max: 360 } },
    { type: 'spawnShape', config: { type: 'circle', data: { radius: 20 } } },
  ],
};
```

### Heal — green upward float, 800ms

```typescript
const HEAL_CONFIG: EmitterConfig = {
  lifetime: { min: 0.5, max: 0.8 },
  frequency: 0.04, emitterLifetime: 0.4, maxParticles: 20,
  pos: { x: 0, y: 0 },
  behaviors: [
    { type: 'alpha', config: { alpha: { list: [{ value: 0, time: 0 }, { value: 1, time: 0.2 }, { value: 0, time: 1 }] } } },
    { type: 'scale', config: { scale: { list: [{ value: 0.3, time: 0 }, { value: 0.7, time: 1 }] } } },
    { type: 'color', config: { color: { list: [{ value: '40ff80', time: 0 }, { value: '00c040', time: 0.5 }, { value: '008020', time: 1 }] } } },
    { type: 'moveAcceleration', config: { accel: { x: 0, y: -60 }, minStart: 20, maxStart: 60, rotate: true } },
    { type: 'spawnShape', config: { type: 'circle', data: { radius: 20 } } },
  ],
};
```

---

## Effect Config Registry

```typescript
// src/combat/particles/effectConfigs.ts
export type WrestlingEffect = 'strike' | 'aerial' | 'submission' | 'block' | 'finisher' | 'heal';

export const EFFECT_CONFIGS: Record<WrestlingEffect, { texturePath: string; emitterConfig: EmitterConfig }> = {
  strike:     { texturePath: '/particles/spark.webp',      emitterConfig: STRIKE_CONFIG },
  aerial:     { texturePath: '/particles/dust.webp',       emitterConfig: AERIAL_CONFIG },
  submission: { texturePath: '/particles/orb.webp',        emitterConfig: SUBMISSION_CONFIG },
  block:      { texturePath: '/particles/shield.webp',     emitterConfig: BLOCK_CONFIG },
  finisher:   { texturePath: '/particles/explosion.webp',  emitterConfig: FINISHER_CONFIG },
  heal:       { texturePath: '/particles/cross.webp',      emitterConfig: HEAL_CONFIG },
};
// Textures: 32x32 or 64x64 WebP, white/neutral — color behavior handles tinting
```

---

## Integration in the PixiJS React Tree

```typescript
// src/combat/CombatScene.tsx — wire particle manager to ticker and store
export function CombatScene(): React.JSX.Element {
  const containerRef = useRef<Container>(null);
  const particleManagerRef = useRef<ParticleManager | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    particleManagerRef.current = new ParticleManager(containerRef.current);
    return () => { particleManagerRef.current?.destroy(); particleManagerRef.current = null; };
  }, []);

  // Subscribe to combat events → spawn particle effect
  useEffect(() => {
    return useCombatStore.subscribe(
      (state) => state.lastEffectType,
      (effectType) => {
        if (!effectType || !particleManagerRef.current) return;
        particleManagerRef.current.spawnEffect(effectType as WrestlingEffect, 640, 360);
      }
    );
  }, []);

  // Drive emitter update from PixiJS ticker (not React renders)
  useTick((ticker) => { particleManagerRef.current?.update(ticker.deltaMS); });

  return <container ref={containerRef} />;
}
```

---

## Performance Budget by Effect

| Effect | maxParticles | Duration | Mobile reduction |
|--------|-------------|----------|-----------------|
| Strike | 20 | 300ms | None needed |
| Aerial | 25 | 500ms | None needed |
| Submission | 60 (continuous) | Until released | Reduce to 25 |
| Block | 15 | 200ms | None needed |
| Finisher | 50 | 1000ms | Reduce to 20 |
| Heal | 20 | 800ms | None needed |

```typescript
const isMobile = /iPhone|iPad|Android/i.test(navigator.userAgent);
const mobileMultiplier = isMobile ? 0.5 : 1.0;
config.maxParticles = Math.floor(config.maxParticles * mobileMultiplier);
```

---

## Anti-Patterns

### ❌ Using @pixi/particle-emitter (the v7 package) with PixiJS v8
It uses v7's `Container` internally and fails at runtime. Use `@spd789562/pixi-v8-particle-emitter`.

### ❌ Not calling emitter.update() in the ticker
```typescript
// WRONG — particles freeze
// CORRECT:
useTick((ticker) => { emitter.update(ticker.deltaMS * 0.001); });
```

### ❌ Setting maxParticles below the burst peak
A finisher with `maxParticles: 20` silently drops 30 particles when emitting 50 at once. No error is thrown. Always set `maxParticles` to the burst peak, not the average.

### ❌ Not destroying emitters on component unmount
Each emitter holds GPU memory. Emitters that are never destroyed accumulate silently. Always call `emitter.destroy()` or use the `ParticleManager` lifecycle tracking which destroys when particle count reaches zero.
