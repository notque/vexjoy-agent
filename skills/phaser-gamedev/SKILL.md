---
name: phaser-gamedev
description: "Phaser 3 2D game dev: scenes, physics, tilemaps, sprites, polish."
version: 1.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
routing:
  triggers:
    - phaser
    - 2d game
    - platformer
    - arcade physics
    - tilemap
    - sprite sheet
    - side scroller
  pairs_with:
    - typescript-frontend-engineer
    - game-asset-generator
  complexity: Medium
  category: game-development
---

# Phaser Gamedev Skill

## Overview

This skill builds complete Phaser 3 2D games using a **Phased Construction** pattern: DESIGN (plan game type, physics, scenes) → BUILD (scene lifecycle, sprites, tilemaps) → ANIMATE (physics, animation state machines, input) → POLISH (camera effects, particles, tweens, sound, mobile). Targets Phaser 3.60+ throughout.

**Scope**: Platformers, arcade shooters, top-down RPGs, puzzle games, side-scrollers — anything 2D in Phaser 3. Do NOT use for 3D games (use threejs-builder), native mobile games, or non-Phaser canvas work.

---

## Instructions

### Phase 1: DESIGN

**Goal**: Understand what to build, select the physics system, and plan the scene graph before writing any code.

**Core constraints**:
- **Read repository CLAUDE.md before building** — local standards override defaults here
- **Select physics system before any other decision** — Arcade (fast AABB), Matter.js (complex shapes), or no physics cannot be mixed per scene without deliberate design
- **Plan scenes upfront** — Boot → Preload → Game → UI is the standard flow; diverge only when the game requires it

**Step 1: Identify the game type**

From the user's request, determine:
- Game genre (platformer, shooter, RPG, puzzle, side-scroller)
- Primary physics need (precise platforming → Arcade; polygon collisions → Matter.js; none → skip physics)
- Number of scenes (Boot, Preload, Game, GameOver, UI overlay)
- Tilemap or procedural world?
- Spritesheet or texture atlas?

**Step 2: Select the physics system**

| Physics | Use When | Avoid When |
|---------|----------|------------|
| Arcade | Platformers, shooters, simple AABB | Rotating bodies, non-rectangular shapes |
| Matter.js | Physics puzzles, destructible terrain | Performance-critical (100+ bodies) |
| None | Puzzles, card games, UI-only | Any meaningful collision detection |

**Step 3: Document the scene plan and load references**

```markdown
## Scene Plan
- Boot: asset loading with progress bar
- Game: [primary gameplay description]
- UI: [HUD, menus — parallel scene or separate?]
- Physics: [Arcade / Matter.js / none]
- World: [tilemap key or procedural]
- Sprites: [spritesheet keys and frame dimensions — measure the PNG first]
```

Load these references based on the plan:
- Always: `references/core-patterns.md` (scene lifecycle, transitions, input)
- If tilemap: `references/tilemaps.md`
- If sprites/animation: `references/spritesheets.md`
- If Arcade physics: `references/arcade-physics.md`
- If performance concern or many moving objects: `references/performance.md`

**Gate**: Scene plan documented. Physics system selected. References loaded. Proceed only when gate passes.

---

### Phase 2: BUILD

**Goal**: Implement the scene lifecycle skeleton, load assets, place sprites, wire up tilemaps.

**Core constraints**:
- **MEASURE spritesheet frames before loading** — wrong `frameWidth`/`frameHeight` is the #1 Phaser bug; open the PNG, count pixels per frame before writing `this.load.spritesheet()`
- **Preload all assets in `preload()`** — never load assets in `create()` or `update()`
- **Use a Boot scene for asset loading** — shows a progress bar, keeps Game scene clean

**Step 1: TypeScript project setup**

```typescript
// game.ts — entry point
import Phaser from 'phaser';
import { BootScene } from './scenes/BootScene';
import { GameScene } from './scenes/GameScene';

const config: Phaser.Types.Core.GameConfig = {
  type: Phaser.AUTO,
  width: 800,
  height: 600,
  physics: {
    default: 'arcade',
    arcade: { gravity: { x: 0, y: 300 }, debug: false },
  },
  scene: [BootScene, GameScene],
  parent: 'game-container',
};

new Phaser.Game(config);
```

**Step 2: Boot scene with progress bar**

```typescript
export class BootScene extends Phaser.Scene {
  constructor() { super({ key: 'Boot' }); }

  preload(): void {
    const bar = this.add.rectangle(
      this.scale.width / 2, this.scale.height / 2, 0, 20, 0x00ff88
    );
    this.load.on('progress', (p: number) => { bar.width = this.scale.width * p; });

    // Load ALL game assets here — measure frameWidth/frameHeight from the PNG
    this.load.spritesheet('player', 'assets/player.png', { frameWidth: 48, frameHeight: 48 });
    this.load.tilemapTiledJSON('map', 'assets/map.json');
    this.load.image('tiles', 'assets/tileset.png');
    this.load.audio('jump', 'assets/jump.ogg');
  }

  create(): void { this.scene.start('Game'); }
}
```

**Step 3: Game scene skeleton**

```typescript
export class GameScene extends Phaser.Scene {
  private player!: Phaser.Types.Physics.Arcade.SpriteWithDynamicBody;
  private cursors!: Phaser.Types.Input.Keyboard.CursorKeys;

  constructor() { super({ key: 'Game' }); }

  create(): void {
    // World, tilemap, sprites, physics groups — all created here
    // See arcade-physics.md for group patterns
    // See tilemaps.md for tilemap layer setup
    this.cursors = this.input.keyboard!.createCursorKeys();
  }

  update(_time: number, _delta: number): void {
    // Per-frame logic — never allocate here, only transform
  }
}
```

**Gate**: Boot and Game scenes compile. Assets load without console errors. Scene transitions work. Proceed only when gate passes.

---

### Phase 3: ANIMATE

**Goal**: Add physics-driven movement, animation state machines, and player input.

**Core constraints**:
- **Never allocate objects in `update()`** — no `new Phaser.Math.Vector2()`, no `this.physics.add.sprite()`, no array creation per frame; allocate in `create()`, reuse in `update()`
- **Use `delta` for frame-rate-independent movement** — `velocity = speed * (delta / 1000)` ensures consistent feel at any FPS
- **State machine over boolean flags** — `'idle' | 'walk' | 'jump' | 'attack' | 'dead'` prevents impossible states like `isJumping && isAttacking`

**Step 1: Animation definitions (in `create()`)**

```typescript
this.anims.create({
  key: 'walk',
  frames: this.anims.generateFrameNumbers('player', { start: 0, end: 7 }),
  frameRate: 12,
  repeat: -1,
});
this.anims.create({
  key: 'jump',
  frames: this.anims.generateFrameNumbers('player', { start: 8, end: 11 }),
  frameRate: 8,
  repeat: 0,
});
this.anims.create({
  key: 'idle',
  frames: this.anims.generateFrameNumbers('player', { start: 12, end: 15 }),
  frameRate: 6,
  repeat: -1,
});
```

**Step 2: Entity state machine**

```typescript
type PlayerState = 'idle' | 'walk' | 'jump' | 'attack' | 'dead';

class Player {
  private state: PlayerState = 'idle';

  setState(next: PlayerState): void {
    if (this.state === next) return;
    this.state = next;
    switch (next) {
      case 'idle':   this.sprite.play('idle'); break;
      case 'walk':   this.sprite.play('walk'); break;
      case 'jump':   this.sprite.play('jump'); break;
      case 'attack': this.sprite.play('attack'); break;
      case 'dead':
        this.sprite.play('die');
        this.sprite.body.setVelocityX(0);
        break;
    }
  }

  update(cursors: Phaser.Types.Input.Keyboard.CursorKeys): void {
    if (this.state === 'dead') return;
    const onGround = this.sprite.body.blocked.down;

    if (cursors.left.isDown) {
      this.sprite.body.setVelocityX(-160);
      this.sprite.setFlipX(true);
      if (onGround) this.setState('walk');
    } else if (cursors.right.isDown) {
      this.sprite.body.setVelocityX(160);
      this.sprite.setFlipX(false);
      if (onGround) this.setState('walk');
    } else {
      this.sprite.body.setVelocityX(0);
      if (onGround) this.setState('idle');
    }

    if (cursors.up.isDown && onGround) {
      this.sprite.body.setVelocityY(-400);
      this.setState('jump');
    }
  }
}
```

See `references/arcade-physics.md` for collision groups, overlap callbacks, and physics tuning.

**Gate**: Player moves. Animations transition correctly. State machine has no impossible state combinations. No per-frame allocations. Proceed only when gate passes.

---

### Phase 4: POLISH

**Goal**: Add camera work, particles, tweens, sound, and mobile controls. Verify performance.

**Core constraints**:
- **Remove `debug: true` from physics config** before shipping
- **Remove all `console.log` calls** unless the user explicitly requested logging
- **Test on a 60 FPS budget** — Arcade + 200 active bodies + 50 particles is the practical ceiling on mid-range mobile

**Step 1: Camera effects**

```typescript
// Follow player with smoothing
this.cameras.main.startFollow(this.player.sprite, true, 0.1, 0.1);
this.cameras.main.setDeadzone(100, 50);
this.cameras.main.setBounds(0, 0, map.widthInPixels, map.heightInPixels);

// On-demand effects
this.cameras.main.shake(200, 0.01);      // hit feedback
this.cameras.main.flash(300, 255, 0, 0); // death flash
```

**Step 2: Particles (Phaser 3.60+ API)**

```typescript
const emitter = this.add.particles(x, y, 'spark', {
  speed: { min: 50, max: 150 },
  lifespan: 600,
  quantity: 8,
  scale: { start: 0.5, end: 0 },
  alpha: { start: 1, end: 0 },
  emitting: false,
});
emitter.explode(8, x, y); // fire on demand
```

**Step 3: Tweens**

```typescript
// Score popup
this.tweens.add({
  targets: scoreText,
  y: scoreText.y - 40,
  alpha: 0,
  duration: 800,
  ease: 'Power2',
  onComplete: () => scoreText.destroy(),
});

// Idle bounce
this.tweens.add({
  targets: coin,
  y: coin.y - 8,
  duration: 600,
  yoyo: true,
  repeat: -1,
  ease: 'Sine.easeInOut',
});
```

**Step 4: Sound**

```typescript
const jumpSound = this.sound.add('jump', { volume: 0.5 });
const music = this.sound.add('bgm', { loop: true, volume: 0.3 });
music.play();
// In update() or callback:
jumpSound.play();
```

**Step 5: Mobile virtual controls (when needed)**

```typescript
const jumpBtn = this.add.rectangle(700, 540, 80, 80, 0xffffff, 0.3)
  .setInteractive()
  .setScrollFactor(0); // fixed to camera

jumpBtn.on('pointerdown', () => {
  if (this.player.sprite.body.blocked.down) {
    this.player.sprite.body.setVelocityY(-400);
  }
});
```

**Step 6: Final verification**

- DevTools → Performance → record 5 seconds of gameplay → confirm under 16.7ms/frame
- No `debug: true` in physics config
- No `console.log` calls remaining
- No TODO markers remaining

**Gate**: Polish checks pass. Performance within budget. Debug config removed. Game is shippable.

---

## Error Handling

### "Spritesheet frame dimensions wrong / animation looks corrupt"
Cause: `frameWidth` or `frameHeight` does not match the actual PNG.
Fix: Open the spritesheet in an image editor. Count total pixel width ÷ columns = frameWidth. Total height ÷ rows = frameHeight. Never estimate. See `references/spritesheets.md`.

### "Cannot read properties of undefined (reading 'body')"
Cause: Accessing a physics body before `create()` completes, or on a non-physics sprite.
Fix: Only use `.body` on sprites created via `this.physics.add.sprite()` or `this.physics.add.existing()`. Static images do not have bodies.

### "Tilemap layer collision has no effect"
Cause: Missing `setCollisionByProperty` or property name mismatch in Tiled.
Fix: In Tiled, verify the tile property is named exactly `collides` (boolean true). Call `layer.setCollisionByProperty({ collides: true })`. See `references/tilemaps.md`.

### "Physics bodies not colliding"
Cause: `this.physics.add.collider()` called before both objects exist, or wrong group types.
Fix: Call all collider setup at the end of `create()`, after all sprites and groups are created.

### "Animation not playing"
Cause: Animation key typo, `anims.create()` called before texture is loaded, or wrong frame range.
Fix: Animations must be defined in `create()`, not `preload()`. Verify key strings match exactly between `anims.create({ key: 'walk' })` and `sprite.play('walk')`.

### "Game runs slow on mobile"
Cause: Too many active physics bodies, continuously emitting particles, or per-frame allocations.
Fix: Pool bullets and enemies (see `references/performance.md`). Set emitters to `emitting: false` and call `explode()` on demand. Display `game.loop.actualFps` to profile.

---

## References

| Reference | When to Load | Content |
|-----------|-------------|---------|
| `references/core-patterns.md` | Always | Scene lifecycle, transitions, input, state machines |
| `references/arcade-physics.md` | Arcade physics | Groups, colliders, velocity, physics tuning, pitfalls |
| `references/tilemaps.md` | Tilemap / Tiled | Layer system, collision, animated tiles, object layers |
| `references/spritesheets.md` | Sprites / animation | Frame measurement, loading, atlases, nine-slice |
| `references/performance.md` | Performance concern | Object pooling, GC avoidance, texture atlases, mobile |
