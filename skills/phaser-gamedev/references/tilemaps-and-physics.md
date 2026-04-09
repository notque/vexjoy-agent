---
name: Phaser Tilemaps and Physics
description: Tiled map integration, Matter.js vs Arcade physics decision table, collision groups, slopes, object layers for enemy spawning, and physics performance patterns
agent: phaser-gamedev
category: patterns
version_range: "Phaser 3.60+"
---

# Tilemaps and Physics Reference

> **Scope**: Loading and configuring tilemaps from Tiled, choosing and configuring physics systems, collision categories in Matter.js, slopes, object layers for spawning. Extends core tilemaps.md and arcade-physics.md with advanced patterns.
> **Version range**: Phaser 3.60+
> **Generated**: 2026-04-08

---

## Tiled Map Integration

### Complete Tilemap Loading Pipeline

```typescript
// BootScene.preload() — load all map assets
preload(): void {
  this.load.tilemapTiledJSON('level1', 'assets/maps/level1.json');
  this.load.image('terrain', 'assets/tilesets/terrain.png');
  this.load.image('decor',   'assets/tilesets/decor.png');
  // For extruded tilesets (eliminates seam artifacts):
  // this.load.image('terrain-extruded', 'assets/tilesets/terrain-extruded.png');
}

// GameScene.create() — build tilemap
create(): void {
  const map = this.make.tilemap({ key: 'level1' });

  // Add each tileset — name must match what's in Tiled's JSON
  const terrainTiles = map.addTilesetImage('terrain', 'terrain');
  const decorTiles   = map.addTilesetImage('decor',   'decor');

  // Create layers in draw order (background first)
  const bgLayer       = map.createLayer('Background', decorTiles, 0, 0)!;
  const groundLayer   = map.createLayer('Ground', terrainTiles, 0, 0)!;
  const platformLayer = map.createLayer('Platforms', terrainTiles, 0, 0)!;
  const fgLayer       = map.createLayer('Foreground', decorTiles, 0, 0)!;

  // Enable collision by Tiled tile property 'collides: true'
  groundLayer.setCollisionByProperty({ collides: true });
  platformLayer.setCollisionByProperty({ collides: true });

  // Camera bounds from map size
  this.cameras.main.setBounds(0, 0, map.widthInPixels, map.heightInPixels);

  // Store reference for physics setup
  this.groundLayer = groundLayer;
  this.map = map;
}
```

### Tile Property Workflow (Tiled Editor)

In Tiled: select tiles in the tileset editor → add boolean property `collides` = `true`. Check exact property name — Phaser's `setCollisionByProperty` is case-sensitive.

```typescript
// Verify which tiles have collision (dev debugging)
groundLayer.forEachTile((tile) => {
  if (tile.collides) {
    console.log(`Colliding tile: ${tile.index} at (${tile.x}, ${tile.y})`);
  }
});
```

---

## Matter.js vs Arcade Physics Decision Table

| Criterion | Arcade | Matter.js |
|-----------|--------|-----------|
| Performance (100+ bodies) | Excellent | Degraded above 60 active bodies |
| Rectangular collisions | Native AABB | Polygon support (heavier) |
| Slopes / wedges | No native support | Via `MatterTilemapLayer` or custom bodies |
| Rotating physics bodies | No | Yes |
| One-way platforms | `checkCollision.up = false` | Via `collisionFilter` + callback |
| Physics constraints / joints | No | Yes (chains, ragdolls) |
| Setup complexity | Low | High |

**Decision rule**: Arcade physics for platformers, shooters, and anything with rectangular hitboxes. Switch to Matter.js ONLY when you need rotating bodies, polygon shapes, or joints. Mixed engines (Arcade for player, Matter for specific objects) are possible but complex — avoid unless the feature requires it.

---

## Matter.js Setup and Collision Groups

```typescript
// Game config — use Matter.js
const config: Phaser.Types.Core.GameConfig = {
  physics: {
    default: 'matter',
    matter: {
      gravity: { x: 0, y: 1 },
      debug: false, // set true during development
    },
  },
};

// GameScene.create() — collision categories (bit flags, must be powers of 2)
create(): void {
  const CATEGORY_PLAYER  = this.matter.world.nextCategory(); // returns 1, 2, 4, 8...
  const CATEGORY_ENEMY   = this.matter.world.nextCategory();
  const CATEGORY_BULLET  = this.matter.world.nextCategory();
  const CATEGORY_TERRAIN = this.matter.world.nextCategory();

  // Player body — collides with terrain and enemies, not bullets
  const player = this.matter.add.sprite(200, 100, 'player');
  player.setCollisionCategory(CATEGORY_PLAYER);
  player.setCollidesWith([CATEGORY_TERRAIN, CATEGORY_ENEMY]);

  // Enemy body — collides with everything except other enemies
  const enemy = this.matter.add.sprite(500, 100, 'enemy');
  enemy.setCollisionCategory(CATEGORY_ENEMY);
  enemy.setCollidesWith([CATEGORY_TERRAIN, CATEGORY_PLAYER, CATEGORY_BULLET]);

  // Bullet — only collides with enemies and terrain
  const bullet = this.matter.add.image(0, 0, 'bullet');
  bullet.setCollisionCategory(CATEGORY_BULLET);
  bullet.setCollidesWith([CATEGORY_TERRAIN, CATEGORY_ENEMY]);
}
```

### Matter.js Collision Events

```typescript
// Use collisionstart/collisionend events instead of overlap callbacks
this.matter.world.on('collisionstart', (event: Phaser.Physics.Matter.Events.CollisionStartEvent) => {
  const pairs = event.pairs;
  for (const pair of pairs) {
    const { bodyA, bodyB } = pair;

    // Bodies carry custom data via gameObject reference
    const goA = bodyA.gameObject as Phaser.GameObjects.GameObject | null;
    const goB = bodyB.gameObject as Phaser.GameObjects.GameObject | null;

    if (!goA || !goB) continue;

    if (goA.getData('type') === 'bullet' && goB.getData('type') === 'enemy') {
      this.onBulletHitEnemy(goA as Phaser.Physics.Matter.Image, goB as Phaser.Physics.Matter.Sprite);
    }
  }
});
```

---

## Slopes and Complex Terrain

### MatterTilemapLayer (Built-in Slope Support, Phaser 3.60+)

```typescript
// MatterTilemapLayer automatically creates concave polygon bodies for slopes
import MatterTilemapLayer from 'phaser/src/physics/matter-js/MatterTilemapLayer';

create(): void {
  const map = this.make.tilemap({ key: 'level1' });
  const tiles = map.addTilesetImage('terrain', 'terrain');
  const groundLayer = map.createLayer('Ground', tiles, 0, 0)!;

  // Convert ground layer to Matter.js compound body (handles slopes from Tiled shape data)
  this.matter.add.tilemapLayer(groundLayer, {
    isStatic: true,
    friction: 0.2,        // reduces sliding on slopes
    frictionStatic: 0.3,
  });

  // Note: tilemapLayer takes precedence over setCollisionByProperty
  // Don't call both — use one or the other
}
```

### Custom Slope Bodies (Manual)

```typescript
// Define slope hitbox manually when Tiled shapes aren't sufficient
const slope = this.matter.add.fromVertices(x, y, [
  { x: 0, y: 0 },        // left (top of slope)
  { x: 100, y: 50 },     // right (bottom)
  { x: 100, y: 0 },      // right top
], {
  isStatic: true,
  friction: 0.3,
  label: 'slope',
});
```

---

## Object Layers from Tiled (Enemy/Item Spawning)

Tiled Object Layers let designers place spawn points without touching code. The standard pattern:

```typescript
// In Tiled: add Object Layer → place Point/Rectangle objects with name/type properties
// Properties: type='enemy', enemyType='bat', patrolDistance=200

create(): void {
  const map = this.make.tilemap({ key: 'level1' });

  // Read object layer — returns array of Tiled objects
  const enemyObjects = map.getObjectLayer('Enemies')?.objects ?? [];

  for (const obj of enemyObjects) {
    const x = obj.x! + (obj.width ?? 0) / 2;  // center of object rectangle
    const y = obj.y! + (obj.height ?? 0) / 2;

    // Read custom properties from Tiled
    const enemyType = this.getProperty<string>(obj, 'enemyType', 'basic');
    const patrol    = this.getProperty<number>(obj, 'patrolDistance', 100);

    this.spawnEnemy(x, y, enemyType, patrol);
  }

  // Item pickups
  const itemObjects = map.getObjectLayer('Items')?.objects ?? [];
  for (const obj of itemObjects) {
    const itemType = this.getProperty<string>(obj, 'itemType', 'coin');
    this.spawnItem(obj.x!, obj.y!, itemType);
  }
}

// Helper — Tiled properties are typed as { name, type, value }[]
private getProperty<T>(obj: Phaser.Types.Tilemaps.TiledObject, name: string, fallback: T): T {
  const prop = obj.properties?.find(p => p.name === name);
  return prop ? (prop.value as T) : fallback;
}
```

---

## Performance: Static Group vs Dynamic Group for Background Tiles

| Group Type | Physics | Reposition Cost | Best For |
|------------|---------|-----------------|----------|
| `StaticGroup` | Static bodies (no gravity) | Must call `refresh()` after move | Platforms, walls — never move |
| `DynamicGroup` | Full physics bodies | Normal velocity/force API | Enemies, projectiles — move via physics |
| `Group` (no physics) | None | Just set x/y | Decorative objects, UI elements |

```typescript
// Static group for fixed platform tiles
const platforms = this.physics.add.staticGroup();
platforms.create(100, 500, 'platform');
platforms.create(300, 400, 'platform');
// After placing all platforms — refresh once, not per-frame
platforms.refresh();

// Player vs static group collision
this.physics.add.collider(this.player, platforms);

// Never call platforms.refresh() in update() — costs a full broadphase rebuild
```

---

## Anti-Pattern Catalog

### ❌ Calling setCollisionByProperty After Layer Already Has Colliders

**Detection**:
```bash
grep -rn "setCollisionByProperty\|setCollision\b" --include="*.ts" --include="*.js"
rg "setCollision" --type ts
```

**What it looks like**:
```typescript
// BAD: setting collision after a Matter tilemapLayer already generated bodies
this.matter.add.tilemapLayer(groundLayer, { isStatic: true });
groundLayer.setCollisionByProperty({ collides: true }); // no effect — Matter ignores this
```

**Why wrong**: `matter.add.tilemapLayer()` generates Matter.js body shapes from the layer's existing collision data. Calling `setCollisionByProperty` after has no effect — the bodies are already created and don't re-read tile properties.

**Fix**: Set tile collision BEFORE creating the Matter layer body:
```typescript
groundLayer.setCollisionByProperty({ collides: true });  // first
this.matter.add.tilemapLayer(groundLayer, { isStatic: true }); // then
```

---

### ❌ Creating Physics Bodies Inside update()

**Detection**:
```bash
grep -rn "matter\.add\.\(sprite\|image\|circle\|rectangle\)" --include="*.ts" --include="*.js"
rg "update\b" --type ts -A 40 | grep "matter\.add\|physics\.add\.sprite"
```

**What it looks like**:
```typescript
update(_time: number, delta: number): void {
  if (this.fireButton.isDown) {
    // BAD: creates a new Matter body every frame
    const bullet = this.matter.add.image(this.player.x, this.player.y, 'bullet');
    bullet.setVelocity(8, 0);
  }
}
```

**Why wrong**: Matter.js body creation is expensive — it runs constraint solving, broadphase insertion, and event binding. Creating bodies in `update()` causes progressive frame time growth. At 60fps with rapid fire, frame time doubles within 3 seconds.

**Fix**: Pool bullets, set active/inactive, reposition via `setPosition()`:
```typescript
create(): void {
  this.bulletPool = this.matter.world.add; // use matter composite for pooling
  // Pre-create bullet bodies, then toggle isSleeping to activate/deactivate
}
```

---

### ❌ Using `overlap()` Instead of `collider()` for Terrain

**Detection**:
```bash
grep -rn "physics\.add\.overlap" --include="*.ts" --include="*.js"
```

**What it looks like**:
```typescript
// BAD: overlap doesn't apply physics resolution (no bounce, no stop)
this.physics.add.overlap(this.player, this.groundLayer, () => {
  this.player.setVelocityY(0);
});
```

**Why wrong**: `overlap()` detects intersection but does NOT resolve physics. The player clips through the terrain; `setVelocityY(0)` is a manual patch that doesn't handle slope normals, one-way platforms, or edge cases. The player will jitter and occasionally fall through.

**Fix**: Use `collider()` for terrain:
```typescript
this.physics.add.collider(this.player, this.groundLayer);
// overlap() is correct for triggers (item pickups, damage zones) — not terrain
```

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|-----------|-----|
| `Tilemap layer has no tileset` | `addTilesetImage()` name doesn't match Tiled export | Check Tiled File → Export → Tileset name exactly matches first arg to `addTilesetImage()` |
| Player falls through floor | Missing `setCollisionByProperty` or property name typo | Verify `collides` boolean property exists on tiles in Tiled, check exact property name |
| Matter.js slope physics jitter | Friction too low on terrain body | Set `friction: 0.2, frictionStatic: 0.3` on Matter tilemapLayer |
| Object layer returns `null` | Layer name typo between Tiled and `getObjectLayer()` | `map.getObjectLayer('Enemies')` must match layer name in Tiled exactly |
| `Cannot read 'objects' of null` | `getObjectLayer()` returns null when layer missing | Guard: `map.getObjectLayer('Enemies')?.objects ?? []` |

---

## Detection Commands Reference

```bash
# Find all tilemap creation calls — verify correct tileset name usage
grep -rn "make\.tilemap\|createLayer\|addTilesetImage" --include="*.ts" --include="*.js"

# Find Matter.js collision category setup — verify categories are powers of 2
grep -rn "setCollisionCategory\|setCollidesWith\|nextCategory" --include="*.ts"

# Find object layer reads — verify null-guard pattern
grep -rn "getObjectLayer" --include="*.ts" --include="*.js"

# Find physics.add.collider vs overlap usage
grep -rn "physics\.add\.\(collider\|overlap\)" --include="*.ts" --include="*.js"
```

---

## See Also

- `references/arcade-physics.md` — Arcade physics groups, collider tuning, velocity patterns
- `references/tilemaps.md` — Tilemap layer system basics, animated tiles
- `references/game-feel-patterns.md` — Screen shake, particles, hit-stop timing
- `references/performance.md` — Object pooling, GC avoidance for physics bodies
