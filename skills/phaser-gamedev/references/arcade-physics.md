# Arcade Physics Reference — Phaser Gamedev

AABB collision detection, physics groups, velocity-based movement, and tuning for Phaser 3.60+.

---

## Arcade Physics Fundamentals

Arcade physics uses **Axis-Aligned Bounding Box (AABB)** collision — rectangles only. It is fast and sufficient for 90% of 2D games. Bodies cannot rotate.

**Enable in game config:**

```typescript
const config: Phaser.Types.Core.GameConfig = {
  physics: {
    default: 'arcade',
    arcade: {
      gravity: { x: 0, y: 300 }, // world gravity applied to all dynamic bodies
      debug: false,               // set true during dev to see hitboxes; REMOVE before shipping
    },
  },
};
```

**Two body types:**
- `DynamicBody` — moves, is affected by gravity and forces (player, enemies, bullets)
- `StaticBody` — never moves, not affected by gravity (platforms, walls, static obstacles)

```typescript
// Dynamic (moves, has gravity)
const player = this.physics.add.sprite(100, 200, 'player');

// Static (immovable, optimized for many objects)
const platforms = this.physics.add.staticGroup();
platforms.create(400, 568, 'ground');
platforms.refresh(); // required after creating static bodies
```

---

## Collision vs Overlap

| Method | Bodies stop? | Callback fires? | Use for |
|--------|-------------|-----------------|---------|
| `add.collider()` | YES | Optional | Solid ground, walls |
| `add.overlap()` | NO | YES | Pickups, triggers, bullets hitting enemies |

```typescript
// Solid collision — player stands on platforms
this.physics.add.collider(player, platforms);

// Overlap — player collects coin (no physical stop)
this.physics.add.overlap(player, coins, this.collectCoin, undefined, this);

// Overlap with process callback — filter which pairs trigger the handler
this.physics.add.overlap(
  bullets,
  enemies,
  this.bulletHitEnemy,       // onCollide
  (_bullet, enemy) => !enemy.getData('dead'), // process — return false to skip
  this
);

private collectCoin(
  player: Phaser.Types.Physics.Arcade.GameObjectWithBody,
  coin: Phaser.Types.Physics.Arcade.GameObjectWithBody
): void {
  (coin as Phaser.Physics.Arcade.Sprite).destroy();
  this.score += 10;
}
```

---

## Physics Groups — Pooling Bullets, Enemies, Collectibles

Groups let you create, reuse, and manage many objects of the same type.

```typescript
// In create():
this.bullets = this.physics.add.group({
  classType: Phaser.Physics.Arcade.Image,
  maxSize: 20,          // pool size — get() returns null when exhausted
  runChildUpdate: true, // calls update() on active children each frame
});

// Fire a bullet:
private fireBullet(x: number, y: number, dirX: number): void {
  const bullet = this.bullets.get(x, y, 'bullet') as Phaser.Physics.Arcade.Image | null;
  if (!bullet) return; // pool exhausted

  bullet.setActive(true).setVisible(true);
  bullet.body.reset(x, y);
  bullet.setVelocityX(dirX * 400);

  // Auto-kill when off screen
  bullet.body.setAllowGravity(false);
}

// In update() — recycle bullets that leave the world
this.bullets.getChildren().forEach((b) => {
  const bullet = b as Phaser.Physics.Arcade.Image;
  if (bullet.active && !this.physics.world.bounds.contains(bullet.x, bullet.y)) {
    this.bullets.killAndHide(bullet);
    bullet.body.reset(0, 0);
  }
});
```

**Enemy group pattern:**

```typescript
this.enemies = this.physics.add.group();

// Spawn an enemy
const enemy = this.enemies.create(x, y, 'enemy') as Phaser.Physics.Arcade.Sprite;
enemy.setBounceX(1);         // reverse direction on wall hit
enemy.setCollideWorldBounds(true);
enemy.setVelocityX(60);

// Collide enemies with ground so they don't fall through
this.physics.add.collider(this.enemies, groundLayer);

// Player hits enemy
this.physics.add.overlap(player, this.enemies, this.playerHitEnemy, undefined, this);
```

---

## Velocity-Based Movement

Arcade physics uses **velocity** for movement, not direct position updates. Direct position updates break collision detection.

```typescript
// In update():

// Horizontal movement
if (cursors.left.isDown) {
  player.body.setVelocityX(-160);
  player.setFlipX(true);
} else if (cursors.right.isDown) {
  player.body.setVelocityX(160);
  player.setFlipX(false);
} else {
  player.body.setVelocityX(0); // stop — don't let the player drift
}

// Jumping — check blocked.down for "is on ground"
if (cursors.up.isDown && player.body.blocked.down) {
  player.body.setVelocityY(-400);
}

// Delta-scaled speed for frame-rate independence (optional, velocity is already per-second)
// player.body.setVelocityX(SPEED * (delta / 1000)); // only needed for custom integrators
```

**Top-down movement (no gravity):**

```typescript
// In game config: arcade: { gravity: { x: 0, y: 0 } }

const SPEED = 200;
const vel = new Phaser.Math.Vector2(0, 0);

if (cursors.left.isDown)  vel.x = -SPEED;
if (cursors.right.isDown) vel.x =  SPEED;
if (cursors.up.isDown)    vel.y = -SPEED;
if (cursors.down.isDown)  vel.y =  SPEED;

vel.normalize().scale(SPEED); // diagonal normalization
player.body.setVelocity(vel.x, vel.y);
```

---

## Physics Body Tuning

```typescript
// Adjust hitbox to match sprite visuals (call in create() after adding sprite)
player.body.setSize(28, 44);       // narrower than sprite
player.body.setOffset(10, 4);      // offset from sprite top-left

// Physics properties
player.body.setMaxVelocityY(600);   // terminal velocity
player.body.setDragX(800);          // horizontal friction (slows without input)
player.setBounce(0.2);              // bounce coefficient 0=none, 1=full

// Immovable — objects that don't move when hit (alternative to StaticBody)
enemy.body.setImmovable(true);

// Disable gravity per-body
bullet.body.setAllowGravity(false);

// World bounds collision
player.setCollideWorldBounds(true);
player.body.onWorldBounds = true;   // fires worldbounds event
this.physics.world.on('worldbounds', (body: Phaser.Physics.Arcade.Body) => {
  if (body.gameObject === player) { /* hit world edge */ }
});
```

---

## Custom Body Size After setTexture

**Common bug**: calling `setTexture()` after creating a sprite resets the body size to match the new texture. Always call `setSize()` after `setTexture()` if you need a custom hitbox.

```typescript
// WRONG — body size is reset after setTexture
sprite.body.setSize(28, 44);
sprite.setTexture('player-large');

// CORRECT
sprite.setTexture('player-large');
sprite.body.setSize(28, 44); // re-apply after texture change
sprite.body.setOffset(10, 4);
```

---

## Physics Debug Mode

Enable temporarily to visualize hitboxes during development:

```typescript
// In game config:
arcade: { debug: true }

// Per-body debug color (debug mode only)
player.body.debugBodyColor = 0x00ff00;
```

**Remove `debug: true` before shipping** — it renders all body outlines every frame and impacts performance.

---

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Moving `StaticBody` after creation | Body stays at original position | Call `body.reset(x, y)` or `refreshBody()` after moving |
| Calling `collider()` before objects exist | Collider silently does nothing | Wire colliders at end of `create()` |
| Not calling `staticGroup.refresh()` | New static bodies not detected | Call `refresh()` after adding to a static group |
| `setVelocity` in a one-shot callback | Velocity fights gravity on next frame | Set velocity in `update()` each frame, not once |
| `body.blocked.down` always false | No collider between player and ground | Add `this.physics.add.collider(player, ground)` |
