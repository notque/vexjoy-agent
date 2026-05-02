---
description: Custom GLSL filters for hit effects, glow chaining, DisplacementFilter shockwaves, Spine integration, particle emitter combat patterns, z-ordering, and alpha masking in PixiJS v8+
agent: pixijs-combat-renderer
category: visual-techniques
version_range: "PixiJS v8+"
---

# Combat Visual Effects Reference

> **Scope**: PixiJS v8 visual effects for combat rendering. Performance/batching in pixi-performance.md.

---

## PIXI.Filter Custom GLSL for Hit Effects

```typescript
import { Filter } from 'pixi.js';

const hitFlashVert = `
  attribute vec2 aPosition;
  varying vec2 vTextureCoord;
  uniform vec4 inputSize;
  uniform vec4 outputFrame;

  vec4 filterVertexPosition() {
    vec2 position = aPosition * max(outputFrame.zw, vec2(0.)) + outputFrame.xy;
    return vec4((position / (inputSize.xy / inputSize.zw)) * 2.0 - 1.0, 0.0, 1.0);
  }

  void main() {
    gl_Position = filterVertexPosition();
    vTextureCoord = aPosition * (outputFrame.zw * inputSize.zw);
  }
`;

const hitFlashFrag = `
  varying vec2 vTextureCoord;
  uniform sampler2D uSampler;
  uniform float uFlash;  // 0.0 = normal, 1.0 = full white

  void main() {
    vec4 sample = texture2D(uSampler, vTextureCoord);
    gl_FragColor = vec4(mix(sample.rgb, vec3(1.0), uFlash * sample.a), sample.a);
  }
`;

export class HitFlashFilter extends Filter {
  constructor() {
    super({ glProgram: { vertex: hitFlashVert, fragment: hitFlashFrag } });
    this.resources.uniforms = { uFlash: 0.0 };
  }
  get flash(): number { return this.resources.uniforms.uFlash; }
  set flash(v: number) { this.resources.uniforms.uFlash = v; }
}

// Animate via GSAP
gsap.to(hitFilter, {
  flash: 1.0, duration: 0.06, yoyo: true, repeat: 1,
  onComplete: () => { characterSprite.filters = []; },
});
```

---

## BlurFilter Chaining for Glow

```typescript
import { AdvancedBloomFilter } from '@pixi/filter-advanced-bloom';

const bloomFilter = new AdvancedBloomFilter({
  threshold: 0.4, bloomScale: 0.8, brightness: 1.2, kernelSize: 5, quality: 4,
});
characterContainer.filters = [bloomFilter];

// Manual two-pass glow (no external package)
function addManualGlow(target: Sprite, glowColor: number, blur = 12): Container {
  const wrapper = new Container();
  const glow = Sprite.from(target.texture);
  glow.tint = glowColor;
  glow.alpha = 0.7;
  glow.filters = [new BlurFilter({ strength: blur })];
  glow.anchor.set(target.anchor.x, target.anchor.y);
  wrapper.addChild(glow);
  wrapper.addChild(target);
  return wrapper;
}
```

---

## DisplacementFilter for Shockwave

```typescript
export async function createShockwave(stage: Container, x: number, y: number): Promise<void> {
  const dispTexture = await Assets.load('/textures/displacement_circle.png');
  const dispSprite = new Sprite(dispTexture);
  dispSprite.anchor.set(0.5);
  dispSprite.position.set(x, y);
  dispSprite.scale.set(0.1);
  stage.addChild(dispSprite);

  const displacementFilter = new DisplacementFilter({ sprite: dispSprite, scale: { x: 80, y: 80 } });
  stage.filters = stage.filters ? [...stage.filters, displacementFilter] : [displacementFilter];

  gsap.to(dispSprite.scale, { x: 3.0, y: 3.0, duration: 0.6, ease: 'power2.out' });
  gsap.to(displacementFilter.scale, {
    x: 0, y: 0, duration: 0.6, ease: 'power3.in',
    onComplete: () => { stage.filters = stage.filters!.filter(f => f !== displacementFilter); dispSprite.destroy(); },
  });
}
```

---

## Spine Animation Integration

```typescript
import { Spine as PixiSpine } from '@esotericsoftware/spine-pixi-v8';

async function loadSpineCharacter(key: string): Promise<PixiSpine> {
  await Assets.load([
    { alias: `${key}-skel`, src: `/spine/${key}.skel` },
    { alias: `${key}-atlas`, src: `/spine/${key}.atlas` },
  ]);
  return PixiSpine.from({ skeleton: `${key}-skel`, atlas: `${key}-atlas` });
}

class SpineCombatCharacter {
  private spine: PixiSpine;
  private state: string = 'idle';

  constructor(spine: PixiSpine) {
    this.spine = spine;
    this.spine.state.setAnimation(0, 'idle', true);
  }

  attack(): void {
    if (this.state === 'hit') return;
    this.state = 'attack';
    this.spine.state.setAnimation(0, 'attack', false);
    this.spine.state.addAnimation(0, 'idle', true, 0);
    this.spine.state.addListener({
      complete: (entry) => { if (entry.animation?.name === 'attack') this.state = 'idle'; },
    });
  }

  takeHit(): void {
    this.state = 'hit';
    this.spine.state.setAnimation(1, 'hit', false);
    this.spine.state.addAnimation(1, null!, false, 0);
    setTimeout(() => { this.state = 'idle'; }, 300);
  }
}
```

---

## Particle Emitter — Impact Burst

```typescript
function burstImpact(stage: Container, x: number, y: number): void {
  const particleContainer = new Container();
  particleContainer.position.set(x, y);
  stage.addChild(particleContainer);

  const emitter = new Emitter(particleContainer, {
    lifetime: { min: 0.2, max: 0.5 }, frequency: 0.001, spawnChance: 1,
    particlesPerWave: 12, maxParticles: 12, pos: { x: 0, y: 0 },
    behaviors: [
      { type: 'alpha', config: { alpha: { list: [{ value: 1, time: 0 }, { value: 0, time: 1 }] } } },
      { type: 'scale', config: { scale: { list: [{ value: 0.6, time: 0 }, { value: 0.1, time: 1 }] } } },
      { type: 'color', config: { color: { list: [{ value: 'ff6600', time: 0 }, { value: 'ff2200', time: 0.3 }, { value: '330000', time: 1 }] } } },
      { type: 'moveSpeedStatic', config: { min: 150, max: 400 } },
      { type: 'rotationStatic', config: { min: 0, max: 360 } },
    ],
  });
  emitter.emit = true;
  setTimeout(() => { emitter.emit = false; setTimeout(() => { emitter.destroy(); particleContainer.destroy(); }, 600); }, 50);
}
```

---

## Z-Index and Sorting

```typescript
// Strategy 1: sortableChildren + zIndex
const stage = new Container();
stage.sortableChildren = true;
background.zIndex = 0; player.zIndex = 10; hitEffect.zIndex = 20; uiContainer.zIndex = 100;

// Strategy 2: explicit layer containers (faster — no sort)
const bgLayer = new Container();
const entityLayer = new Container();
const effectLayer = new Container();
const uiLayer = new Container();
stage.addChild(bgLayer, entityLayer, effectLayer, uiLayer);
```

Layer containers are faster. Use `zIndex` only for dynamic y-sorting (top-down RPG).

---

## Alpha Masking for Health Bars

```typescript
export class HealthBar extends Container {
  private fill: Sprite;
  private fillMask: Graphics;
  private maxWidth: number;

  constructor(width = 200, height = 20) {
    super();
    this.maxWidth = width;
    const bg = new Graphics().roundRect(0, 0, width, height, 4).fill({ color: 0x220000, alpha: 0.9 });
    this.addChild(bg);
    this.fill = Sprite.from('health_bar_fill');
    this.fill.width = width; this.fill.height = height;
    this.addChild(this.fill);
    this.fillMask = new Graphics();
    this.addChild(this.fillMask);
    this.fill.mask = this.fillMask;
    this.setHealth(1.0);
  }

  setHealth(ratio: number): void {
    const r = Math.max(0, Math.min(1, ratio));
    this.fillMask.clear().rect(0, 0, this.maxWidth * r, this.fill.height).fill(0xffffff);
    if (r > 0.6) this.fill.tint = 0x44ff44;
    else if (r > 0.3) this.fill.tint = 0xffcc00;
    else this.fill.tint = 0xff2222;
  }
}
```

---

## Preferred Patterns

### Pre-load Textures and Pool Sprites
Never create sprites in ticker. Pre-load textures, use object pool.

### Apply Filters to Parent Containers
Per-sprite filters = N render passes per frame. One filter on parent container = one pass for all.

---

## Error-Fix Mappings

| Error | Fix |
|-------|-----|
| `Filter vertex program undefined` | Use `new Filter({ glProgram: { vertex, fragment } })` (v8 API) |
| Displacement map invisible | `stage.addChild(dispSprite)` before setting filters |
| Spine character invisible | `await Assets.load()` both `.skel` and `.atlas` first |
| `zIndex` not sorting | `parentContainer.sortableChildren = true` |
| Health bar mask full | Clamp ratio: `Math.max(0, Math.min(1, ratio))` |
