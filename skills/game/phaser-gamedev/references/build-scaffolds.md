# Phaser Build Scaffolds

Verbatim TypeScript scaffolds for Phase 2 (BUILD): project setup, Boot scene, Game scene skeleton.

## Step 1: TypeScript project setup

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

## Step 2: Boot scene with progress bar

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

## Step 3: Game scene skeleton

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
