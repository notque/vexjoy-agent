---
name: PixiJS Rendering Performance
description: Sprite batching, texture atlases, RenderTexture caching, off-screen culling, object pooling, ParticleContainer vs Container, and anti-patterns that break GPU batching in PixiJS v8+
agent: pixijs-combat-renderer
category: performance
version_range: "PixiJS v8+"
---

# PixiJS Performance Reference

> **Scope**: PixiJS v8-specific rendering performance — what breaks batching, how to measure draw calls, when to use ParticleContainer, texture atlas format, RenderTexture caching, and object pooling patterns.
> **Version range**: PixiJS v8+
> **Generated**: 2026-04-08

---

## How PixiJS Batching Works and When It Breaks

PixiJS v8 batches sprites sharing the same texture, blend mode, alpha, and no active filters into a single draw call. Understanding what breaks batching is the core performance skill.

```typescript
import { Application, Sprite, Texture } from 'pixi.js';

// Batching diagnostic — check draw calls per frame
const app = new Application();
await app.init({ resizeTo: window });

app.ticker.add(() => {
  // Access renderer stats
  const stats = (app.renderer as any).runners; // internal — use sparingly
  // Better: use pixi-stats package for dev overlay
  // import { addStats } from 'pixi-stats';
  // const stats = addStats(document, app);
});
```

### What Breaks Batching (Forces New Draw Call)

| Cause | Triggers New Draw Call | Prevention |
|-------|----------------------|------------|
| Different texture | Each atlas break | Pack sprites into one atlas |
| Filter on any ancestor | Yes — filter renders to RenderTexture | Use filters on container root only |
| Different blend mode | Yes | Group by blend mode |
| Per-sprite tint change per frame | Yes — tint changes trigger batch flush | Use one tint value per atlas batch |
| Changing `alpha` on parent Container | Yes — alpha is baked per draw | Set alpha on sprites, not containers |
| Mask on any ancestor | Yes | Pool masked containers, not per-sprite |

---

## Texture Atlases with TexturePacker Output

Pack all combat sprites into one atlas to eliminate texture-switch draw calls.

```typescript
import { Assets, Spritesheet, Texture } from 'pixi.js';

// Load TexturePacker JSON atlas
await Assets.load('/atlases/combat.json'); // loads .json + .png together

// Access individual frames
const playerIdleTexture  = Texture.from('player_idle_000');
const playerAttackTexture = Texture.from('player_attack_001');
const hitSparkTexture    = Texture.from('hit_spark_000');

// AnimatedSprite from atlas frames (character animation)
const frames = [];
for (let i = 0; i < 8; i++) {
  frames.push(Texture.from(`player_idle_${String(i).padStart(3, '0')}`));
}
const animSprite = new AnimatedSprite(frames);
animSprite.animationSpeed = 0.15;
animSprite.play();

// Verify all combat sprites use the same atlas
// Detection: any Texture.from() that points to a DIFFERENT file breaks the batch
```

### TexturePacker Settings for PixiJS v8

```
Format: Pixi JS (JSON Hash or JSON Array)
Algorithm: MaxRects
Power of Two: YES (GPU texture requirement)
Max texture: 2048x2048 (safe on all devices)
Padding: 2 (prevents bleeding at atlas edges)
Trim sprites: YES (reduces atlas size)
Extrude: 1 (prevents seam artifacts when filtering)
```

---

## RenderTexture for Cached Complex Composites

When a composite (character + equipment + effects) is expensive to re-render and doesn't change every frame, bake it to a RenderTexture:

```typescript
import { RenderTexture, Sprite, Container, Application } from 'pixi.js';

// Bake a character composite to a RenderTexture
function bakeCharacterToTexture(
  app: Application,
  character: Container,
  width: number,
  height: number,
): Sprite {
  const renderTexture = RenderTexture.create({ width, height });

  // Render the container once to the texture
  app.renderer.render({ container: character, target: renderTexture });

  // Use as a regular sprite — one draw call, no children
  const baked = new Sprite(renderTexture);
  return baked;
}

// Use case: character select screen — bake each character preview
// Re-bake on state change (equip item, take damage), not every frame
```

---

## Culling Off-Screen Objects

PixiJS does not cull off-screen objects by default. For combat with many off-screen effects:

```typescript
import { Container, Sprite, Rectangle } from 'pixi.js';

// Simple frustum cull — check bounds against screen rect
const screenBounds = new Rectangle(0, 0, app.screen.width, app.screen.height);

function cullChildren(container: Container): void {
  for (const child of container.children) {
    if (child instanceof Sprite) {
      const bounds = child.getBounds();
      // Add margin to prevent pop-in
      child.visible = screenBounds.intersects(new Rectangle(
        bounds.x - 50, bounds.y - 50,
        bounds.width + 100, bounds.height + 100,
      ));
    }
  }
}

// Call in ticker at a reduced rate (every 3 frames is sufficient)
let cullFrame = 0;
app.ticker.add(() => {
  if (++cullFrame % 3 === 0) cullChildren(entityLayer);
});
```

---

## Object Pooling in PixiJS

```typescript
import { Sprite, Texture, Container } from 'pixi.js';

// Generic sprite pool
class SpritePool {
  private pool: Sprite[] = [];
  private texture: Texture;
  private parent: Container;

  constructor(texture: Texture, parent: Container, initialSize = 20) {
    this.texture = texture;
    this.parent = parent;
    // Pre-warm pool
    for (let i = 0; i < initialSize; i++) {
      const sprite = new Sprite(texture);
      sprite.visible = false;
      parent.addChild(sprite);
      this.pool.push(sprite);
    }
  }

  get(): Sprite | null {
    const sprite = this.pool.find(s => !s.visible);
    if (!sprite) return null; // pool exhausted

    sprite.visible = true;
    sprite.alpha = 1;
    sprite.rotation = 0;
    sprite.scale.set(1);
    return sprite;
  }

  release(sprite: Sprite): void {
    sprite.visible = false;
    // Reset to a safe position off-screen
    sprite.position.set(-9999, -9999);
  }
}

// Usage — projectiles
const bulletPool = new SpritePool(Texture.from('bullet'), entityLayer, 30);

function fireBullet(x: number, y: number, vx: number, vy: number): void {
  const bullet = bulletPool.get();
  if (!bullet) return; // pool exhausted — silent drop

  bullet.position.set(x, y);
  bullet.setData('vx', vx);
  bullet.setData('vy', vy);
}

// In ticker — update and recycle
app.ticker.add((ticker) => {
  const dt = ticker.deltaTime;
  for (const bullet of entityLayer.children) {
    if (!bullet.visible) continue;
    const sprite = bullet as Sprite;
    sprite.x += sprite.getData('vx') * dt;
    sprite.y += sprite.getData('vy') * dt;

    if (sprite.x < -50 || sprite.x > app.screen.width + 50) {
      bulletPool.release(sprite);
    }
  }
});
```

---

## ParticleContainer vs Container for Particles

| Feature | ParticleContainer | Container |
|---------|------------------|-----------|
| Max sprites | 100,000+ | ~5,000 comfortable |
| Tint per sprite | Yes | Yes |
| Alpha per sprite | Yes | Yes |
| Rotation per sprite | Yes (if enabled) | Yes |
| Filters | No | Yes |
| Children of children | No | Yes |
| Blend mode per sprite | No | Yes |
| Draw calls | 1 | 1 per texture |

```typescript
import { ParticleContainer, Sprite, Texture } from 'pixi.js';

// ParticleContainer — all particles must use the SAME texture
const particleContainer = new ParticleContainer(10000, {
  position: true,   // enable per-particle position upload
  rotation: true,   // enable per-particle rotation upload
  scale: true,      // enable per-particle scale upload
  alpha: true,      // enable per-particle alpha upload
  uvs: false,       // disable if single texture (saves bandwidth)
  tint: false,      // disable if no tint variation needed
});

// Only enable what you need — unused uploads waste GPU bandwidth
const spark = Texture.from('spark');

for (let i = 0; i < 5000; i++) {
  const sprite = new Sprite(spark);
  sprite.position.set(Math.random() * 800, Math.random() * 600);
  sprite.alpha = Math.random();
  particleContainer.addChild(sprite);
}

stage.addChild(particleContainer);
```

**When NOT to use ParticleContainer**:
- Mixed textures (multiple atlas frames) — use regular Container with single atlas
- Particles that need filters (glow, blur) — regular Container + filter on parent
- Particles with children (labels, icons) — regular Container

---

## Anti-Pattern Catalog

### ❌ Changing Tint Per Frame on Many Sprites

**Detection**:
```bash
grep -rn "\.tint\s*=" --include="*.ts" --include="*.js"
rg "ticker\.add|useTick" --type ts -A 20 | grep "\.tint"
```

**What it looks like**:
```typescript
app.ticker.add(() => {
  // BAD: tint change per frame flushes the batch for each sprite
  sprites.forEach((sprite, i) => {
    sprite.tint = hslToHex(i / sprites.length, 1, 0.5 + Math.sin(Date.now() * 0.001 + i) * 0.2);
  });
});
```

**Why wrong**: Setting `.tint` marks the sprite as dirty and flushes the current batch. 100 sprites with per-frame tint changes = 100 draw calls instead of 1.

**Fix**: Use a custom shader uniform instead of per-sprite tint changes, or group sprites by tint value and update once per group:
```typescript
// Group by tint — batch-friendly
const tintGroups = new Map<number, Sprite[]>();
sprites.forEach(sprite => {
  const tint = computeTint(sprite);
  if (!tintGroups.has(tint)) tintGroups.set(tint, []);
  tintGroups.get(tint)!.push(sprite);
});
tintGroups.forEach((group, tint) => {
  group.forEach(s => { s.tint = tint; }); // same tint = batches together
});
```

---

### ❌ Using Container Instead of ParticleContainer for Hundreds of Uniform Particles

**Detection**:
```bash
grep -rn "new Container\|new PIXI\.Container" --include="*.ts" --include="*.js"
rg "addChild.*Sprite" --type ts | grep -v "ParticleContainer"
```

**What it looks like**:
```typescript
const particleLayer = new Container();
for (let i = 0; i < 1000; i++) {
  const p = new Sprite(sparkTexture);
  particleLayer.addChild(p); // BAD: 1000 children in regular Container
}
```

**Why wrong**: Regular Container renders each child individually during the batch flush. 1000 same-texture sprites in a Container use 1 draw call, but each child is inspected in JavaScript every frame — O(n) per-frame cost even with batching. Above ~500 children, the JS cost exceeds the GPU gain.

**Fix**: Use `ParticleContainer` for homogeneous particle sets:
```typescript
const particleLayer = new ParticleContainer(1000, { position: true, alpha: true });
for (let i = 0; i < 1000; i++) {
  const p = new Sprite(sparkTexture);
  particleLayer.addChild(p);
}
```

---

### ❌ Loading Individual Textures per Sprite (No Atlas)

**Detection**:
```bash
grep -rn "Texture\.from\|Assets\.load.*\.png" --include="*.ts" --include="*.js"
rg "\.load\(['\"].*\.png['\"]" --type ts
```

**What it looks like**:
```typescript
// BAD: each unique PNG = separate GPU texture = separate draw call
const playerTexture = await Assets.load('/sprites/player.png');
const enemyTexture  = await Assets.load('/sprites/enemy.png');
const sparkTexture  = await Assets.load('/sprites/spark.png');
```

**Why wrong**: Each unique GPU texture creates a batch boundary. 10 unique textures in a scene = minimum 10 draw calls, regardless of how many sprites use them. On mobile, each texture switch has a measurable cost.

**Fix**: Pack all sprites into one atlas. One `Assets.load('/atlases/combat.json')` loads everything:
```typescript
await Assets.load('/atlases/combat.json');
// Now all frames share one GPU texture — single draw call for all sprites
const playerTexture = Texture.from('player_idle_000');
const sparkTexture  = Texture.from('hit_spark_000');
```

---

## Detection Commands Reference

```bash
# Find all per-frame tint mutations
grep -rn "\.tint\s*=" --include="*.ts" --include="*.js"

# Find non-ParticleContainer particle patterns
grep -rn "addChild.*new Sprite" --include="*.ts" | grep -v "ParticleContainer"

# Find individual texture loads (no atlas)
grep -rn "Assets\.load.*\.png\|Texture\.from.*\.png" --include="*.ts"

# Find RenderTexture usage — verify baking, not per-frame render
grep -rn "RenderTexture\|renderer\.render" --include="*.ts"

# Find filter application — check container vs sprite level
grep -rn "\.filters\s*=" --include="*.ts"
```

---

## See Also

- `references/combat-visual-effects.md` — Hit filters, shockwave, glow, z-ordering
- `references/pixi-particle-systems.md` — Full particle emitter config and presets
- `references/pixi-post-processing.md` — Filter chain ordering and mobile budgets
- `references/pixi-react-integration.md` — useTick animation, Vite bundle splitting
