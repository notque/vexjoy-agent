---
name: PixiJS Combat Visual Effects
description: Custom GLSL filters for hit effects, glow chaining, DisplacementFilter shockwaves, Spine integration, particle emitter combat patterns, z-ordering, and alpha masking in PixiJS v8+
agent: pixijs-combat-renderer
category: visual-techniques
version_range: "PixiJS v8+"
---

# Combat Visual Effects Reference

> **Scope**: PixiJS v8-specific visual effects for combat rendering — custom filters, displacement ripples, Spine animation, particle combat presets, z-index control, and UI masking. Performance budget and batching lives in pixi-performance.md.
> **Version range**: PixiJS v8+
> **Generated**: 2026-04-08

---

## PIXI.Filter Custom GLSL for Hit Effects

PixiJS v8 uses a shader-based Filter pipeline. Each Filter wraps a fragment shader applied to a RenderTexture copy of the container.

```typescript
import { Filter } from 'pixi.js';

// Hit flash: brief white-to-transparent overlay
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
    // Preserve alpha, push RGB toward white
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

// Usage on a combat sprite
const hitFilter = new HitFlashFilter();
characterSprite.filters = [hitFilter];

// Animate the flash via GSAP or useTick
gsap.to(hitFilter, {
  flash: 1.0,
  duration: 0.06,
  yoyo: true,
  repeat: 1,
  onComplete: () => { characterSprite.filters = []; },
});
```

---

## BlurFilter Chaining for Glow Effects

PixiJS v8's `pixi-filters` package (v6+) includes `AdvancedBloomFilter`. For a manual glow, chain blur on a duplicated sprite:

```typescript
import { BlurFilter, Container, Sprite } from 'pixi.js';
import { AdvancedBloomFilter } from '@pixi/filter-advanced-bloom'; // pixi-filters v6+

// Simple glow: add bloom to a character container
const characterContainer = new Container();
scene.addChild(characterContainer);

const bloomFilter = new AdvancedBloomFilter({
  threshold: 0.4,    // luminance required to bloom (0-1)
  bloomScale: 0.8,
  brightness: 1.2,
  kernelSize: 5,     // 5 = medium quality, 15 = high (expensive on mobile)
  quality: 4,
});
characterContainer.filters = [bloomFilter];

// Pulse glow on power-up
function pulseGlow(duration = 600): void {
  const tween = { brightness: 1.2 };
  gsap.to(tween, {
    brightness: 2.0,
    duration: duration / 1000,
    ease: 'sine.inOut',
    yoyo: true,
    repeat: 3,
    onUpdate: () => { bloomFilter.brightness = tween.brightness; },
  });
}

// Manual two-pass glow (no external package needed)
function addManualGlow(target: Sprite, glowColor: number, blur = 12): Container {
  const wrapper = new Container();
  const glow = Sprite.from(target.texture); // duplicate texture
  glow.tint = glowColor;
  glow.alpha = 0.7;
  glow.filters = [new BlurFilter({ strength: blur })];
  glow.anchor.set(target.anchor.x, target.anchor.y);

  wrapper.addChild(glow); // glow behind
  wrapper.addChild(target); // original on top
  return wrapper;
}
```

---

## DisplacementFilter for Shockwave and Ripple

```typescript
import { Sprite, DisplacementFilter, Assets, Container } from 'pixi.js';

// Shockwave: growing ring displacement
export async function createShockwave(
  stage: Container,
  x: number,
  y: number,
): Promise<void> {
  // Displacement maps are grayscale sprites; use a blurred circle
  const dispTexture = await Assets.load('/textures/displacement_circle.png');
  const dispSprite = new Sprite(dispTexture);
  dispSprite.anchor.set(0.5);
  dispSprite.position.set(x, y);
  dispSprite.scale.set(0.1); // start small
  stage.addChild(dispSprite);

  const displacementFilter = new DisplacementFilter({
    sprite: dispSprite,
    scale: { x: 80, y: 80 },
  });

  stage.filters = stage.filters
    ? [...stage.filters, displacementFilter]
    : [displacementFilter];

  // Expand the displacement sprite
  gsap.to(dispSprite.scale, {
    x: 3.0,
    y: 3.0,
    duration: 0.6,
    ease: 'power2.out',
  });
  // Reduce intensity as it expands
  gsap.to(displacementFilter.scale, {
    x: 0,
    y: 0,
    duration: 0.6,
    ease: 'power3.in',
    onComplete: () => {
      stage.filters = stage.filters!.filter(f => f !== displacementFilter);
      dispSprite.destroy();
    },
  });
}
```

---

## Spine Animation Integration

Spine v4 animations in PixiJS v8 via `@esotericsoftware/spine-pixi-v8`:

```typescript
import { Spine as PixiSpine } from '@esotericsoftware/spine-pixi-v8';
import { Assets } from 'pixi.js';

// Load Spine assets
async function loadSpineCharacter(key: string): Promise<PixiSpine> {
  await Assets.load([
    { alias: `${key}-skel`, src: `/spine/${key}.skel` },
    { alias: `${key}-atlas`, src: `/spine/${key}.atlas` },
  ]);

  return PixiSpine.from({ skeleton: `${key}-skel`, atlas: `${key}-atlas` });
}

// Animation state machine for combat
class SpineCombatCharacter {
  private spine: PixiSpine;
  private state: string = 'idle';

  constructor(spine: PixiSpine) {
    this.spine = spine;
    this.spine.state.setAnimation(0, 'idle', true); // track 0, loop
  }

  attack(): void {
    if (this.state === 'hit') return;
    this.state = 'attack';
    this.spine.state.setAnimation(0, 'attack', false);
    this.spine.state.addAnimation(0, 'idle', true, 0);
    this.spine.state.addListener({
      complete: (entry) => {
        if (entry.animation?.name === 'attack') this.state = 'idle';
      },
    });
  }

  takeHit(): void {
    this.state = 'hit';
    // Track 1 for hit reaction — plays over top of attack/idle
    this.spine.state.setAnimation(1, 'hit', false);
    this.spine.state.addAnimation(1, null!, false, 0);
    setTimeout(() => { this.state = 'idle'; }, 300);
  }
}
```

---

## Particle Emitter Patterns for Combat

```typescript
import { Emitter } from '@spd789562/pixi-v8-particle-emitter';
import { Container } from 'pixi.js';

// Impact burst — one-shot, auto-destroys
function burstImpact(stage: Container, x: number, y: number): void {
  const particleContainer = new Container();
  particleContainer.position.set(x, y);
  stage.addChild(particleContainer);

  const emitter = new Emitter(particleContainer, {
    lifetime: { min: 0.2, max: 0.5 },
    frequency: 0.001,
    spawnChance: 1,
    particlesPerWave: 12,
    maxParticles: 12,
    pos: { x: 0, y: 0 },
    behaviors: [
      { type: 'alpha', config: { alpha: { list: [{ value: 1, time: 0 }, { value: 0, time: 1 }] } } },
      { type: 'scale', config: { scale: { list: [{ value: 0.6, time: 0 }, { value: 0.1, time: 1 }] } } },
      { type: 'color', config: { color: { list: [
        { value: 'ff6600', time: 0 },
        { value: 'ff2200', time: 0.3 },
        { value: '330000', time: 1 },
      ] } } },
      { type: 'moveSpeedStatic', config: { min: 150, max: 400 } },
      { type: 'rotationStatic', config: { min: 0, max: 360 } },
    ],
  });

  emitter.emit = true;
  setTimeout(() => {
    emitter.emit = false;
    setTimeout(() => {
      emitter.destroy();
      particleContainer.destroy();
    }, 600); // > max lifetime (500ms)
  }, 50); // one burst wave
}
```

---

## Z-Index and Sorting in PixiJS

```typescript
import { Container, Sprite } from 'pixi.js';

// Strategy 1: sortableChildren + zIndex (flexible, sort cost)
const stage = new Container();
stage.sortableChildren = true;

const background = Sprite.from('bg');
background.zIndex = 0;
const player = Sprite.from('player');
player.zIndex = 10;
const hitEffect = Sprite.from('hit_flash');
hitEffect.zIndex = 20; // above player
const uiContainer = new Container();
uiContainer.zIndex = 100; // always on top
stage.addChild(background, player, hitEffect, uiContainer);

// Strategy 2: explicit layer containers (faster, no sort)
const bgLayer      = new Container();
const entityLayer  = new Container();
const effectLayer  = new Container();
const uiLayer      = new Container();
stage.addChild(bgLayer, entityLayer, effectLayer, uiLayer);
entityLayer.addChild(player);
effectLayer.addChild(hitEffect); // always above entities
uiLayer.addChild(hpBar);
```

**Layer container strategy is faster** — no sort required. Use it when layers have clear separation (background / entities / effects / UI). Use `zIndex` only when entities need dynamic y-sorting (top-down RPG, characters in front of/behind each other).

---

## Alpha Masking for Health Bars

```typescript
import { Container, Graphics, Sprite } from 'pixi.js';

export class HealthBar extends Container {
  private fill: Sprite;
  private fillMask: Graphics;
  private maxWidth: number;

  constructor(width = 200, height = 20) {
    super();
    this.maxWidth = width;

    const bg = new Graphics()
      .roundRect(0, 0, width, height, 4)
      .fill({ color: 0x220000, alpha: 0.9 });
    this.addChild(bg);

    this.fill = Sprite.from('health_bar_fill');
    this.fill.width = width;
    this.fill.height = height;
    this.addChild(this.fill);

    this.fillMask = new Graphics();
    this.addChild(this.fillMask);
    this.fill.mask = this.fillMask;
    this.setHealth(1.0);
  }

  setHealth(ratio: number): void {
    const r = Math.max(0, Math.min(1, ratio));
    this.fillMask.clear()
      .rect(0, 0, this.maxWidth * r, this.fill.height)
      .fill(0xffffff);

    if (r > 0.6)      this.fill.tint = 0x44ff44;
    else if (r > 0.3) this.fill.tint = 0xffcc00;
    else               this.fill.tint = 0xff2222;
  }
}
```

---

## Anti-Pattern Catalog

### ❌ Creating New PIXI.Texture Per Frame

**Detection**:
```bash
grep -rn "new PIXI\.Texture\|Texture\.from\|RenderTexture\.create" --include="*.ts" --include="*.js"
rg "useTick|Ticker\.shared" --type ts -A 20 | grep "Texture"
```

**What it looks like**:
```typescript
app.ticker.add(() => {
  const texture = Texture.from('spark_' + Math.floor(Math.random() * 4)); // BAD
  const sprite = new Sprite(texture);
  stage.addChild(sprite);
});
```

**Why wrong**: Each frame adds a sprite with uncleaned GPU texture references. After 60 seconds at 60fps: 3600 leaked sprites, visible GC stutter.

**Fix**: Pre-load textures array, pool sprites:
```typescript
const textures = ['spark_0', 'spark_1', 'spark_2', 'spark_3'].map(k => Texture.from(k));
// Use object pool pattern — never create sprites in ticker
```

---

### ❌ Applying Filters to Individual Sprites Instead of Containers

**Detection**:
```bash
grep -rn "\.filters\s*=\s*\[" --include="*.ts" --include="*.js"
rg "\.filters\s*=" --type ts
```

**What it looks like**:
```typescript
sprites.forEach(sprite => {
  sprite.filters = [new BlurFilter({ strength: 4 })]; // BAD: N filter passes per frame
});
```

**Why wrong**: Each filter on a Sprite triggers one render-to-texture pass. 20 sprites = 20 extra render passes per frame = 20fps drop on mid-range mobile.

**Fix**: Apply filters to a parent Container:
```typescript
const entityContainer = new Container();
entityContainer.filters = [new BlurFilter({ strength: 4 })]; // one pass for all
sprites.forEach(sprite => entityContainer.addChild(sprite));
stage.addChild(entityContainer);
```

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|-----------|-----|
| `Filter vertex program undefined` | PixiJS v8 changed Filter constructor API | Use `new Filter({ glProgram: { vertex, fragment } })` not `new Filter(vert, frag, uniforms)` |
| Displacement map not visible | `dispSprite` not added to the same container | `stage.addChild(dispSprite)` before setting `stage.filters` |
| Spine character invisible | Atlas not loaded before `PixiSpine.from()` | `await Assets.load()` for both `.skel` and `.atlas` first |
| `zIndex` sort not working | `sortableChildren` not `true` on parent | `parentContainer.sortableChildren = true` |
| Health bar mask shows full bar | Mask `rect` width not clamped | `Math.max(0, Math.min(1, ratio))` before multiply |

---

## See Also

- `references/pixi-performance.md` — Sprite batching, texture atlases, ParticleContainer
- `references/pixi-particle-systems.md` — Full particle emitter config reference
- `references/pixi-post-processing.md` — AdvancedBloomFilter, CRTFilter, filter chain ordering
