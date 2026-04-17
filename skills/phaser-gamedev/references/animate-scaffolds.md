# Phaser Animate Scaffolds

Verbatim TypeScript scaffolds for Phase 3 (ANIMATE): animation definitions and entity state machine.

## Step 1: Animation definitions (in `create()`)

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

## Step 2: Entity state machine

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
