# CSS Particle Migration Reference
<!-- Loaded by combat-effects-upgrade when task involves DOM particle replacement, element pooling, or CSS @keyframes for effects.ts -->

## Overview

The game's `effects.ts` creates and destroys DOM elements for every particle using this anti-pattern:

```typescript
// ANTI-PATTERN — runs on every effect call
const el = document.createElement('div');
Object.assign(el.style, { position: 'fixed', left: x + 'px', top: y + 'px' });
document.body.appendChild(el);
setTimeout(() => el.remove(), duration);
```

This causes two compounding problems: (1) GC pressure from frequent allocation/deallocation, and (2) each `appendChild`/`remove` forces a style recalculation. The fix is a pre-allocated pool with CSS class toggling — elements are created once at mount and reused indefinitely.

---

## ParticlePool: TypeScript Implementation

```typescript
// src/lib/ParticlePool.ts

type PoolOptions = {
  count: number;
  className: string;
  container?: HTMLElement;
};

export class ParticlePool {
  private readonly pool: HTMLDivElement[] = [];
  private readonly className: string;
  private readonly container: HTMLElement;

  constructor({ count, className, container }: PoolOptions) {
    this.className = className;
    this.container = container ?? document.body;

    // Pre-allocate all elements at construction time
    for (let i = 0; i < count; i++) {
      const el = document.createElement('div');
      el.style.position = 'fixed';
      el.style.pointerEvents = 'none';
      el.style.willChange = 'transform, opacity'; // hint GPU layer — set here, not inline per-effect
      el.setAttribute('aria-hidden', 'true');
      this.container.appendChild(el);
      this.pool.push(el);
    }
  }

  /**
   * Acquire a particle from the pool.
   * Returns null if all particles are in use — caller should degrade gracefully.
   */
  acquire(x: number, y: number): HTMLDivElement | null {
    const el = this.pool.find(p => !p.classList.contains('particle-active'));
    if (!el) return null;

    // Reset stale values from previous animation
    el.style.transform = '';
    el.style.opacity = '';
    el.style.left = x + 'px';
    el.style.top = y + 'px';

    el.classList.add('particle-active', this.className);

    // Auto-return on animation end — synchronous, no timer drift
    const onEnd = () => {
      el.classList.remove('particle-active', this.className);
      el.removeEventListener('animationend', onEnd);
    };
    el.addEventListener('animationend', onEnd, { once: true });

    return el;
  }

  /** Force-return all elements (e.g. on combat scene unmount) */
  releaseAll(): void {
    for (const el of this.pool) {
      el.classList.remove('particle-active', this.className);
    }
  }

  /** Clean up — call in useEffect cleanup when component unmounts */
  destroy(): void {
    this.releaseAll();
    for (const el of this.pool) {
      el.remove();
    }
    this.pool.length = 0;
  }
}
```

---

## Pool Registry: Shared Pools Per Effect Type

```typescript
// src/lib/effectPools.ts
import { ParticlePool } from './ParticlePool';

// Pools are module-level singletons — created once, shared across all effect calls
// Pool sizes: effect max count + 25% buffer

let _pools: Record<string, ParticlePool> | null = null;

export function getEffectPools(): Record<string, ParticlePool> {
  if (_pools) return _pools;
  _pools = {
    impact:    new ParticlePool({ count: 8,  className: 'particle-impact' }),
    confetti:  new ParticlePool({ count: 24, className: 'particle-confetti' }),
    gold:      new ParticlePool({ count: 16, className: 'particle-gold' }),
    sparkle:   new ParticlePool({ count: 16, className: 'particle-sparkle' }),
    heal:      new ParticlePool({ count: 8,  className: 'particle-heal' }),
    finisher:  new ParticlePool({ count: 16, className: 'particle-finisher' }),
    damage:    new ParticlePool({ count: 4,  className: 'particle-damage' }),
    block:     new ParticlePool({ count: 4,  className: 'particle-damage' }), // reuses damage class
    floating:  new ParticlePool({ count: 4,  className: 'particle-floating' }),
    buff:      new ParticlePool({ count: 4,  className: 'particle-buff' }),
    debuff:    new ParticlePool({ count: 4,  className: 'particle-debuff' }),
  };
  return _pools;
}

export function destroyEffectPools(): void {
  if (!_pools) return;
  for (const pool of Object.values(_pools)) {
    pool.destroy();
  }
  _pools = null;
}
```

---

## Migrated Effect Functions

### Before / After: `createImpactBurst`

```typescript
// BEFORE — 5 createElement calls per hit
export function createImpactBurst(x: number, y: number, type: 'strike' | 'grapple' | 'aerial'): void {
  const colors = { strike: '#ff4444', grapple: '#ff8800', aerial: '#4488ff' };
  for (let i = 0; i < 5; i++) {
    setTimeout(() => {
      const el = document.createElement('div');
      const angle = (i / 5) * Math.PI * 2;
      Object.assign(el.style, {
        position: 'fixed', left: x + 'px', top: y + 'px',
        width: '8px', height: '8px', borderRadius: '50%',
        background: colors[type],
        transform: `translate(${Math.cos(angle) * 40}px, ${Math.sin(angle) * 40}px)`,
      });
      document.body.appendChild(el);
      setTimeout(() => el.remove(), 600);
    }, i * 30);
  }
}

// AFTER — pool acquire, CSS class drives animation
export function createImpactBurst(x: number, y: number, type: 'strike' | 'grapple' | 'aerial'): void {
  const pools = getEffectPools();
  const angleStep = (Math.PI * 2) / 5;

  for (let i = 0; i < 5; i++) {
    const angle = i * angleStep;
    const el = pools.impact.acquire(x, y);
    if (!el) continue; // pool exhausted — degrade gracefully

    // CSS custom properties drive per-particle direction
    el.style.setProperty('--angle', angle.toString());
    el.style.setProperty('--delay', `${i * 30}ms`);
    el.dataset['type'] = type; // for CSS attr() or data selectors
  }
}
```


---

## CSS @keyframes: Complete Definitions

Add to your global stylesheet or a `particles.css` module. All animations use only GPU-composited properties: `transform` and `opacity`.

```css
/* Timing presets — match original effect durations */
:root {
  --particle-impact-duration:    600ms;
  --particle-confetti-duration:  2500ms;
  --particle-gold-duration:      1000ms;
  --particle-sparkle-duration:   900ms;
  --particle-heal-duration:      1200ms;
  --particle-finisher-duration:  1000ms;
  --particle-damage-duration:    1000ms;
  --particle-floating-duration:  1200ms;
  --particle-buff-duration:      1200ms;
  --particle-debuff-duration:    1200ms;
}

/* Base particle — shared by all types */
[class*="particle-"] {
  position: fixed;
  pointer-events: none;
  will-change: transform, opacity;
}

/* .particle-impact Radial burst outward — replaces createImpactBurst --angle: radians (set per-element via JS) --delay: stagger ms */
@keyframes impact-burst {
  from {
    transform: translate(0, 0) scale(1);
    opacity: 1;
  }
  60% {
    opacity: 0.8;
  }
  to {
    transform:
      translate(
        calc(cos(var(--angle, 0)) * 48px),
        calc(sin(var(--angle, 0)) * 48px)
      )
      scale(0.2);
    opacity: 0;
  }
}

.particle-impact {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--impact-color, #ff4444);
  animation: impact-burst var(--particle-impact-duration) ease-out forwards;
  animation-delay: var(--delay, 0ms);
}

[data-type="strike"] .particle-impact,
.particle-impact[data-type="strike"] { --impact-color: #ff4444; }
[data-type="grapple"] .particle-impact,
.particle-impact[data-type="grapple"] { --impact-color: #ff8800; }
[data-type="aerial"] .particle-impact,
.particle-impact[data-type="aerial"] { --impact-color: #4488ff; }

/* .particle-confetti Upward toss + spin + gravity fall --hue: 0-360 color --delay: stagger ms --drift: horizontal drift px */
@keyframes confetti-toss {
  0% {
    transform: translateY(0) translateX(0) rotate(0deg) scale(1);
    opacity: 1;
  }
  30% {
    transform: translateY(-80px) translateX(var(--drift, 0px)) rotate(180deg) scale(1);
    opacity: 1;
  }
  100% {
    transform: translateY(120px) translateX(calc(var(--drift, 0px) * 1.5)) rotate(540deg) scale(0.4);
    opacity: 0;
  }
}

.particle-confetti {
  width: 8px;
  height: 8px;
  background: hsl(var(--hue, 200), 70%, 60%);
  animation: confetti-toss var(--particle-confetti-duration) cubic-bezier(0.25, 0.46, 0.45, 0.94) forwards;
  animation-delay: var(--delay, 0ms);
}

/* .particle-gold Upward arc + fade — replaces createGoldBurst */
@keyframes gold-arc {
  from {
    transform: translateY(0) scale(1);
    opacity: 1;
  }
  50% {
    transform: translateY(-60px) scale(1.2);
    opacity: 0.9;
  }
  to {
    transform: translateY(-100px) scale(0.3);
    opacity: 0;
  }
}

.particle-gold {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: radial-gradient(circle, #ffd700 0%, #ff8c00 100%);
  animation: gold-arc var(--particle-gold-duration) ease-in-out forwards;
  animation-delay: var(--delay, 0ms);
}

/* .particle-sparkle Grow + rotate + fade — replaces createRaritySparkle */
@keyframes sparkle-pop {
  0% {
    transform: scale(0) rotate(0deg);
    opacity: 0;
  }
  30% {
    transform: scale(1.4) rotate(90deg);
    opacity: 1;
  }
  100% {
    transform: scale(0) rotate(270deg);
    opacity: 0;
  }
}

.particle-sparkle {
  width: 12px;
  height: 12px;
  clip-path: polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%);
  background: var(--sparkle-color, #fff700);
  animation: sparkle-pop var(--particle-sparkle-duration) ease-out forwards;
  animation-delay: var(--delay, 0ms);
}

/* Rarity colors via data attribute */
.particle-sparkle[data-rarity="common"]    { --sparkle-color: #aaaaaa; }
.particle-sparkle[data-rarity="uncommon"]  { --sparkle-color: #00cc44; }
.particle-sparkle[data-rarity="rare"]      { --sparkle-color: #4488ff; }
.particle-sparkle[data-rarity="epic"]      { --sparkle-color: #aa44ff; }
.particle-sparkle[data-rarity="legendary"] { --sparkle-color: #ff8800; }

/* .particle-heal Float up + expand + fade green */
@keyframes heal-float {
  from {
    transform: translateY(0) scale(0.5);
    opacity: 0.8;
  }
  60% {
    transform: translateY(-50px) scale(1.3);
    opacity: 1;
  }
  to {
    transform: translateY(-90px) scale(0.2);
    opacity: 0;
  }
}

.particle-heal {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: radial-gradient(circle, #88ff88 0%, #00aa44 100%);
  animation: heal-float var(--particle-heal-duration) ease-out forwards;
  animation-delay: var(--delay, 0ms);
}

/* .particle-finisher Explosive outward + rotate + fade gold */
@keyframes finisher-explode {
  0% {
    transform: translate(0, 0) scale(1.5) rotate(0deg);
    opacity: 1;
  }
  40% {
    opacity: 1;
  }
  100% {
    transform:
      translate(
        calc(cos(var(--angle, 0)) * 80px),
        calc(sin(var(--angle, 0)) * 80px)
      )
      scale(0.1)
      rotate(720deg);
    opacity: 0;
  }
}

.particle-finisher {
  width: 12px;
  height: 12px;
  clip-path: polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%);
  background: #ffd700;
  animation: finisher-explode var(--particle-finisher-duration) ease-out forwards;
  animation-delay: var(--delay, 0ms);
}

/* .particle-damage / .particle-floating Float up + fade — text particles */
@keyframes damage-float {
  from {
    transform: translateY(0) scale(1);
    opacity: 1;
  }
  to {
    transform: translateY(-60px) scale(0.8);
    opacity: 0;
  }
}

.particle-damage,
.particle-floating {
  font-weight: 700;
  font-size: 1.4rem;
  text-shadow: 0 2px 4px rgba(0,0,0,0.6);
  white-space: nowrap;
  animation: damage-float var(--particle-damage-duration) ease-out forwards;
}

.particle-damage  { color: #ff4444; }
.particle-floating { color: #ffffff; font-size: 1.1rem; }

/* .particle-buff / .particle-debuff */
@keyframes buff-rise {
  from { transform: translateY(0) scale(0.8); opacity: 0; }
  20%  { opacity: 1; }
  to   { transform: translateY(-50px) scale(1.1); opacity: 0; }
}

.particle-buff  {
  color: #88ff88;
  font-weight: 700;
  animation: buff-rise var(--particle-buff-duration) ease-out forwards;
}

.particle-debuff {
  color: #ff8888;
  font-weight: 700;
  animation: buff-rise var(--particle-debuff-duration) ease-out forwards;
}
```

---

## CSS `cos()`/`sin()` Browser Support Note

The `cos()` and `sin()` CSS math functions are supported in Chromium 111+, Firefox 108+, Safari 15.4+. For older targets, compute the X/Y components in JavaScript and pass as separate CSS custom properties:

```typescript
// Fallback for environments where CSS trig isn't supported
const angle = (i / count) * Math.PI * 2;
el.style.setProperty('--dx', `${Math.cos(angle) * 48}px`);
el.style.setProperty('--dy', `${Math.sin(angle) * 48}px`);

// Then in CSS:
// transform: translate(var(--dx, 0), var(--dy, 0)) scale(...)
```

---

## Integration in useEffect

```typescript
// src/components/CombatArena.tsx
import { useEffect } from 'react';
import { getEffectPools, destroyEffectPools } from '../lib/effectPools';

export function CombatArena() {
  useEffect(() => {
    // Initialize pools on mount
    getEffectPools();

    return () => {
      // Clean up all pool elements on unmount
      destroyEffectPools();
    };
  }, []);

  // ...
}
```

---

## Performance Verification

```bash
# Verify no layout-triggering properties remain in effects.ts
grep -n "\.style\.\(width\|height\|top\|left\|margin\|padding\)" src/effects.ts
# Expected: 0 matches after migration

# Verify no DOM creation remains in effects.ts
grep -n "createElement\|appendChild\|\.remove()" src/effects.ts
# Expected: 0 matches after migration (pool elements are created in ParticlePool constructor)
```

Chrome DevTools: open Performance tab, record 5 seconds of combat, check "Layout" in the flame chart. Target: no layout events during particle animations.
