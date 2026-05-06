# Core Patterns Reference — Phaser Gamedev

Scene lifecycle, transitions, input handling, and entity state machines for Phaser 3.60+.

---

## Scene Lifecycle

Every Phaser scene has three lifecycle methods. Understanding their contract prevents the most common bugs.

```
preload()  → Queues asset loads. Runs once. Never access game objects here.
create()   → Runs after all assets are loaded. Build the world here.
update()   → Runs every frame. Only transform existing objects — never allocate.
```

**What belongs where:**

| Task | preload() | create() | update() |
|------|-----------|----------|----------|
| Load images, audio, tilemaps | YES | NO | NO |
| Create sprites, groups, colliders | NO | YES | NO |
| Define animations | NO | YES | NO |
| Apply velocity, check input | NO | NO | YES |
| Create new objects dynamically | NO | Only once | Never |

**Boot scene pattern** — separates loading from gameplay:

```typescript
export class BootScene extends Phaser.Scene {
  constructor() { super({ key: 'Boot' }); }

  preload(): void {
    // Progress bar UI (safe — these are graphics, not loaded assets)
    const { width, height } = this.scale;
    const bg = this.add.rectangle(width / 2, height / 2, 300, 6, 0x333333);
    const bar = this.add.rectangle(width / 2 - 150, height / 2, 0, 6, 0x00ff88)
      .setOrigin(0, 0.5);
    const label = this.add.text(width / 2, height / 2 + 20, 'Loading...', {
      fontSize: '14px', color: '#ffffff',
    }).setOrigin(0.5);

    this.load.on('progress', (p: number) => {
      bar.width = 300 * p;
      label.setText(`Loading... ${Math.round(p * 100)}%`);
    });

    // Queue all game assets
    this.load.spritesheet('player', 'assets/player.png', { frameWidth: 48, frameHeight: 48 });
    this.load.tilemapTiledJSON('map', 'assets/map.json');
    this.load.image('tiles', 'assets/tileset.png');
    this.load.audio('bgm', 'assets/music.ogg');
    this.load.audio('jump', 'assets/jump.ogg');
  }

  create(): void {
    this.scene.start('Game');
  }
}
```

---

## Scene Transitions

**Start** — stops current scene and launches new one:
```typescript
this.scene.start('GameOver', { score: this.score }); // pass data as second arg
```

**Launch** — runs a scene in parallel (useful for HUD overlays):
```typescript
// In GameScene.create():
this.scene.launch('HUD');

// Pass live data via events (not constructor — HUD is already created)
this.events.on('scoreChanged', (score: number) => {
  this.scene.get('HUD').events.emit('updateScore', score);
});
```

**Pause / Resume** — freeze a scene without destroying it:
```typescript
this.scene.pause('Game');   // stops update(), keeps objects in memory
this.scene.resume('Game');  // resumes update()
```

**Receiving data from scene.start()**:
```typescript
// In the receiving scene's init() method (runs before preload/create)
init(data: { score: number }): void {
  this.finalScore = data.score;
}
```

**Transition order**: `init()` → `preload()` → `create()` → `update()` (every frame)

---

## Input Handling

### Keyboard — cursor keys

```typescript
// In create():
this.cursors = this.input.keyboard!.createCursorKeys();
// Provides: left, right, up, down, shift, space — all as Phaser.Input.Keyboard.Key

// In update():
if (this.cursors.left.isDown) { /* held */ }
if (Phaser.Input.Keyboard.JustDown(this.cursors.up)) { /* pressed this frame only */ }
if (Phaser.Input.Keyboard.JustUp(this.cursors.space)) { /* released this frame only */ }
```

### Keyboard — arbitrary keys

```typescript
// In create():
this.keyW = this.input.keyboard!.addKey(Phaser.Input.Keyboard.KeyCodes.W);
this.keySpace = this.input.keyboard!.addKey(Phaser.Input.Keyboard.KeyCodes.SPACE);

// In update():
if (this.keyW.isDown) { /* WASD movement */ }
```

### Pointer (mouse / touch)

```typescript
// In create():
this.input.on('pointerdown', (pointer: Phaser.Input.Pointer) => {
  console.log(pointer.worldX, pointer.worldY); // world coordinates (accounts for camera)
  console.log(pointer.x, pointer.y);           // screen coordinates
});

this.input.on('pointermove', (pointer: Phaser.Input.Pointer) => {
  if (pointer.isDown) { /* dragging */ }
});

// Make a game object interactive:
sprite.setInteractive();
sprite.on('pointerdown', () => { /* clicked */ });
sprite.on('pointerover', () => { /* hover */ });
```

### Gamepad

```typescript
// In create():
this.input.gamepad!.once('connected', (pad: Phaser.Input.Gamepad.Gamepad) => {
  this.gamepad = pad;
});

// In update():
if (this.gamepad) {
  const leftX = this.gamepad.leftStick.x; // -1 to 1
  if (this.gamepad.A) { /* A button held */ }
}
```

---

## Entity State Machines

Boolean flags like `isJumping`, `isAttacking`, `isDead` lead to impossible combinations. A state machine with a single discriminated type prevents this.

**Pattern — typed state union:**

```typescript
type EntityState = 'idle' | 'walk' | 'run' | 'jump' | 'attack' | 'hurt' | 'dead';

class Enemy {
  private sprite: Phaser.Types.Physics.Arcade.SpriteWithDynamicBody;
  private state: EntityState = 'idle';
  private stateTimer = 0;

  constructor(scene: Phaser.Scene, x: number, y: number) {
    this.sprite = scene.physics.add.sprite(x, y, 'enemy');
  }

  private setState(next: EntityState): void {
    if (this.state === next) return; // no-op if already in state

    const prev = this.state;
    this.state = next;
    this.stateTimer = 0;

    // Exit current state
    switch (prev) {
      case 'attack':
        this.sprite.body.setVelocityX(0);
        break;
    }

    // Enter next state
    switch (next) {
      case 'idle':
        this.sprite.play('enemy-idle');
        this.sprite.body.setVelocityX(0);
        break;
      case 'walk':
        this.sprite.play('enemy-walk');
        break;
      case 'attack':
        this.sprite.play('enemy-attack');
        this.sprite.once('animationcomplete', () => this.setState('idle'));
        break;
      case 'hurt':
        this.sprite.play('enemy-hurt');
        this.sprite.setTintFill(0xff0000);
        this.sprite.once('animationcomplete', () => {
          this.sprite.clearTint();
          this.setState('idle');
        });
        break;
      case 'dead':
        this.sprite.play('enemy-die');
        this.sprite.body.setVelocityX(0);
        this.sprite.body.setAllowGravity(false);
        this.sprite.once('animationcomplete', () => this.sprite.destroy());
        break;
    }
  }

  takeDamage(amount: number): void {
    if (this.state === 'dead' || this.state === 'hurt') return;
    this.hp -= amount;
    if (this.hp <= 0) {
      this.setState('dead');
    } else {
      this.setState('hurt');
    }
  }

  update(delta: number, player: Phaser.GameObjects.Sprite): void {
    if (this.state === 'dead' || this.state === 'hurt') return;

    this.stateTimer += delta;
    const dist = Phaser.Math.Distance.Between(
      this.sprite.x, this.sprite.y,
      player.x, player.y
    );

    if (dist < 40) {
      this.setState('attack');
    } else if (dist < 200) {
      this.setState('walk');
      const dir = player.x < this.sprite.x ? -1 : 1;
      this.sprite.body.setVelocityX(80 * dir);
      this.sprite.setFlipX(dir < 0);
    } else {
      this.setState('idle');
    }
  }
}
```

**Key rules**:
- `setState` is the only place state transitions happen
- Guard at top of `update()`: `if (this.state === 'dead') return;`
- Use `animationcomplete` events to auto-transition one-shot animations (attack, hurt, die)
- Never mutate `this.state` directly from outside `setState()`

---

## TypeScript Scene Configuration

```typescript
// Typed scene data interface
interface GameSceneData {
  level: number;
  score: number;
}

export class GameScene extends Phaser.Scene {
  private data!: GameSceneData;

  constructor() {
    super({ key: 'Game' });
  }

  init(data: GameSceneData): void {
    this.data = data;
  }

  create(): void {
    // this.data.level is available here
  }
}

// Starting with typed data:
this.scene.start('Game', { level: 1, score: 0 } satisfies GameSceneData);
```

**Phaser type imports** — use Phaser's built-in types:

```typescript
// Common typed handles
private player!: Phaser.Types.Physics.Arcade.SpriteWithDynamicBody;
private ground!: Phaser.Tilemaps.TilemapLayer;
private enemies!: Phaser.Physics.Arcade.Group;
private cursors!: Phaser.Types.Input.Keyboard.CursorKeys;
private camera!: Phaser.Cameras.Scene2D.Camera;
```
