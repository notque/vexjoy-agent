# Tilemaps Reference — Phaser Gamedev

Tiled JSON integration, layer system, collision, animated tiles, and object layers for Phaser 3.60+.

---

## Loading a Tiled Map

**Tiled** exports maps as JSON. Load the JSON and the tileset image separately in Boot's `preload()`:

```typescript
// In BootScene.preload():
this.load.tilemapTiledJSON('map', 'assets/map.json');
this.load.image('tiles', 'assets/tileset.png');

// If your tileset has multiple images:
this.load.image('tiles-outdoor', 'assets/outdoor.png');
this.load.image('tiles-indoor', 'assets/indoor.png');
```

**Critical**: The first argument to `load.image()` must match the **tileset name** inside the Tiled JSON's `tilesets[].name` field exactly. A mismatch produces a blank map with no error.

---

## Creating the Map and Layers

```typescript
// In GameScene.create():

// Create the tilemap from the loaded JSON
const map = this.make.tilemap({ key: 'map' });

// Add tileset — name must match Tiled's internal tileset name
const tileset = map.addTilesetImage('outdoor', 'tiles')!;
// Second arg 'tiles' matches the load.image() key

// Create layers — names must match layer names in Tiled
const bgLayer = map.createLayer('Background', tileset, 0, 0)!;
const groundLayer = map.createLayer('Ground', tileset, 0, 0)!;
const decorLayer = map.createLayer('Decoration', tileset, 0, 0)!;
const fgLayer = map.createLayer('Foreground', tileset, 0, 0)!;

// Foreground layer renders on top of player — set depth
fgLayer.setDepth(10);

// Set world bounds to map size
this.physics.world.setBounds(0, 0, map.widthInPixels, map.heightInPixels);
this.cameras.main.setBounds(0, 0, map.widthInPixels, map.heightInPixels);
```

**Standard 4-layer structure** (from simple to complex):

| Layer Name | Purpose | Depth |
|------------|---------|-------|
| Background | Sky, distant scenery — no collision | 0 |
| Ground | Walkable platforms and walls — has collision | 1 |
| Decoration | Props on top of ground, no collision | 2 |
| Foreground | Elements in front of player (trees, rooftops) | 10+ |

---

## Collision from Tilemap

**Method 1 — by custom property** (recommended, most flexible):

In Tiled, select tiles that should collide, open Properties, add boolean property `collides = true`.

```typescript
// Collide all tiles that have the custom "collides" property set to true
groundLayer.setCollisionByProperty({ collides: true });

// Wire player to collide with the ground layer
this.physics.add.collider(player, groundLayer);
```

**Method 2 — by tile index**:

```typescript
// Collide specific tile indices (0-based from tileset)
groundLayer.setCollision([1, 2, 3, 15, 16]);
```

**Method 3 — by exclusion** (all tiles collide except listed):

```typescript
groundLayer.setCollisionByExclusion([-1]); // -1 = empty tile
```

**Tileset margin and spacing**: If your tileset has margin/spacing configured in Tiled, verify the values match exactly when calling `addTilesetImage()`:

```typescript
// With margin=2, spacing=2 in Tiled:
const tileset = map.addTilesetImage('outdoor', 'tiles', 32, 32, 2, 2)!;
// Args: name, key, tileWidth, tileHeight, margin, spacing
```

---

## Animated Tiles

Tile animations are configured in Tiled's tileset editor (select a tile → Animation panel → add frames). Phaser 3.60+ plays them automatically when you add the `AnimatedTiles` plugin, or you can handle them manually.

**Without plugin** — manual animated tile via `setTileIndexCallback`:

```typescript
// Cycle frames every 200ms using Phaser's time events
let waterFrame = 0;
const waterFrames = [40, 41, 42, 43]; // tile indices for water animation

this.time.addEvent({
  delay: 200,
  loop: true,
  callback: () => {
    waterFrame = (waterFrame + 1) % waterFrames.length;
    // Replace all tiles of index 40 with current frame
    groundLayer.replaceByIndex(waterFrames[(waterFrame - 1 + 4) % 4], waterFrames[waterFrame]);
  },
});
```

**With plugin** — automatic (recommended for maps with many animated tiles):

```typescript
// In BootScene.preload():
this.load.scenePlugin('AnimatedTiles',
  'https://cdn.jsdelivr.net/npm/phaser-animated-tiles/dist/AnimatedTiles.min.js',
  'animatedTiles', 'animatedTiles'
);

// In GameScene.create():
(this.sys as any).animatedTiles.init(map);
// Plugin reads animation data from Tiled JSON automatically
```

---

## Object Layers — Spawn Points and Trigger Zones

Tiled's **Object Layer** lets you place non-tile objects: spawn points, doors, item locations, trigger boxes.

**In Tiled**: Layer → Add Object Layer → insert rectangles/points with custom properties.

```typescript
// Retrieve all objects from an object layer
const spawnObjects = map.getObjectLayer('Spawns')!.objects;

// Find the player spawn point (a point object named "PlayerSpawn")
const playerSpawn = spawnObjects.find(o => o.name === 'PlayerSpawn')!;
const player = this.physics.add.sprite(playerSpawn.x!, playerSpawn.y!, 'player');

// Spawn enemies from objects with type "Enemy"
const enemySpawns = spawnObjects.filter(o => o.type === 'Enemy');
enemySpawns.forEach(spawn => {
  const enemy = this.enemies.create(spawn.x!, spawn.y!, 'enemy');
  // Read custom properties
  const patrolDist = spawn.properties?.find((p: any) => p.name === 'patrolDist')?.value ?? 100;
  enemy.setData('patrolDist', patrolDist);
});

// Trigger zones — rectangles that fire events when player overlaps
const triggerLayer = map.getObjectLayer('Triggers')!.objects;
triggerLayer.forEach(obj => {
  const zone = this.add.zone(obj.x!, obj.y!, obj.width!, obj.height!);
  this.physics.add.existing(zone, true); // static body
  this.physics.add.overlap(player, zone, () => {
    const action = obj.properties?.find((p: any) => p.name === 'action')?.value;
    if (action === 'nextLevel') this.scene.start('Game', { level: this.level + 1 });
  });
});
```

---

## Multi-Tileset Maps

A single map can use multiple tilesets:

```typescript
// Load multiple tileset images in preload():
this.load.image('tiles-ground', 'assets/ground.png');
this.load.image('tiles-props', 'assets/props.png');

// In create():
const tilesetGround = map.addTilesetImage('ground', 'tiles-ground')!;
const tilesetProps = map.addTilesetImage('props', 'tiles-props')!;

// Pass array when creating layers that use multiple tilesets
const groundLayer = map.createLayer('Ground', [tilesetGround, tilesetProps], 0, 0)!;
```

---

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Tileset name mismatch | Blank map, no error | `addTilesetImage` first arg must match Tiled's `tilesets[].name` exactly |
| Missing `setCollisionByProperty` | Player falls through ground | Call it before `physics.add.collider` |
| Property name typo | Collision silently skipped | Open Tiled, verify property is named `collides` (lowercase) |
| Wrong margin/spacing | Tiles render as grey boxes | Check Tiled tileset settings, pass matching values to `addTilesetImage` |
| Layer name mismatch | `createLayer` returns null | Check exact layer name in Tiled, including capitalization |
| Not setting world/camera bounds | Camera shows black void | Set bounds to `map.widthInPixels` × `map.heightInPixels` |
