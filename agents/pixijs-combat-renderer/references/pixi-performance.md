---
description: Sprite batching, texture atlases, RenderTexture caching, off-screen culling, object pooling, ParticleContainer vs Container, and anti-patterns that break GPU batching in PixiJS v8+
agent: pixijs-combat-renderer
category: performance
version_range: "PixiJS v8+"
---

# PixiJS Performance Reference

> **Scope**: What breaks batching, draw call measurement, ParticleContainer, texture atlases, RenderTexture caching, object pooling.

---

## Batching — What Breaks It

PixiJS v8 batches sprites sharing same texture, blend mode, alpha, and no active filters into one draw call.

| Cause | Prevention |
|-------|------------|
| Different texture | Pack into one atlas |
| Filter on ancestor | Filters on container root only |
| Different blend mode | Group by blend mode |
| Per-sprite tint per frame | One tint per atlas batch |
| Alpha on parent Container | Set alpha on sprites, not containers |
| Mask on ancestor | Pool masked containers |

---

## Texture Atlases

```typescript
await Assets.load('/atlases/combat.json');
const playerIdleTexture = Texture.from('player_idle_000');

const frames = [];
for (let i = 0; i < 8; i++) {
  frames.push(Texture.from(`player_idle_${String(i).padStart(3, '0')}`));
}
const animSprite = new AnimatedSprite(frames);
animSprite.animationSpeed = 0.15;
animSprite.play();
```

### TexturePacker Settings
```
Format: Pixi JS (JSON Hash or JSON Array)
Algorithm: MaxRects
Power of Two: YES
Max texture: 2048x2048
Padding: 2
Trim sprites: YES
Extrude: 1
```

---

## RenderTexture for Cached Composites

Bake expensive composites that don't change every frame:

```typescript
function bakeCharacterToTexture(app: Application, character: Container, width: number, height: number): Sprite {
  const renderTexture = RenderTexture.create({ width, height });
  app.renderer.render({ container: character, target: renderTexture });
  return new Sprite(renderTexture);
}
// Re-bake on state change, not every frame
```

---

## Off-Screen Culling

PixiJS does not cull by default.

```typescript
const screenBounds = new Rectangle(0, 0, app.screen.width, app.screen.height);

function cullChildren(container: Container): void {
  for (const child of container.children) {
    if (child instanceof Sprite) {
      const bounds = child.getBounds();
      child.visible = screenBounds.intersects(new Rectangle(
        bounds.x - 50, bounds.y - 50, bounds.width + 100, bounds.height + 100,
      ));
    }
  }
}

// Every 3 frames is sufficient
let cullFrame = 0;
app.ticker.add(() => { if (++cullFrame % 3 === 0) cullChildren(entityLayer); });
```

---

## Object Pooling

```typescript
class SpritePool {
  private pool: Sprite[] = [];
  constructor(texture: Texture, parent: Container, initialSize = 20) {
    this.texture = texture;
    this.parent = parent;
    for (let i = 0; i < initialSize; i++) {
      const sprite = new Sprite(texture);
      sprite.visible = false;
      parent.addChild(sprite);
      this.pool.push(sprite);
    }
  }
  get(): Sprite | null {
    const sprite = this.pool.find(s => !s.visible);
    if (!sprite) return null;
    sprite.visible = true; sprite.alpha = 1; sprite.rotation = 0; sprite.scale.set(1);
    return sprite;
  }
  release(sprite: Sprite): void {
    sprite.visible = false;
    sprite.position.set(-9999, -9999);
  }
}
```

---

## ParticleContainer vs Container

| Feature | ParticleContainer | Container |
|---------|------------------|-----------|
| Max sprites | 100,000+ | ~5,000 |
| Filters | No | Yes |
| Children of children | No | Yes |
| Blend mode per sprite | No | Yes |

```typescript
const particleContainer = new ParticleContainer(10000, {
  position: true, rotation: true, scale: true, alpha: true,
  uvs: false,  // disable if single texture
  tint: false, // disable if no tint variation
});
```

**When NOT to use**: Mixed textures, particles needing filters, particles with children.

---

## Pattern Catalog

### Group Tint Changes by Value
Per-frame `.tint` flushes batch per sprite. 100 sprites = 100 draw calls.
**Fix**: Use custom shader uniform or group sprites by tint value.

### Use ParticleContainer for 500+ Uniform Particles
Regular Container: each child inspected in JS every frame (O(n)). Above ~500, JS cost exceeds GPU gain.

### Pack Sprites into Texture Atlas
Each unique GPU texture = batch boundary = draw call. One atlas = one draw call for all sprites.

**Detection**:
```bash
grep -rn "Texture\.from\|Assets\.load.*\.png" --include="*.ts"
```

---

## Detection Commands

```bash
# Per-frame tint mutations
grep -rn "\.tint\s*=" --include="*.ts"

# Non-ParticleContainer particle patterns
grep -rn "addChild.*new Sprite" --include="*.ts" | grep -v "ParticleContainer"

# Individual texture loads (no atlas)
grep -rn "Assets\.load.*\.png\|Texture\.from.*\.png" --include="*.ts"

# Filter application level
grep -rn "\.filters\s*=" --include="*.ts"
```
