# Phaser Polish Scaffolds

Verbatim TypeScript scaffolds for Phase 4 (POLISH): camera effects, particles, tweens, sound, mobile controls.

## Step 1: Camera effects

```typescript
// Follow player with smoothing
this.cameras.main.startFollow(this.player.sprite, true, 0.1, 0.1);
this.cameras.main.setDeadzone(100, 50);
this.cameras.main.setBounds(0, 0, map.widthInPixels, map.heightInPixels);

// On-demand effects
this.cameras.main.shake(200, 0.01);      // hit feedback
this.cameras.main.flash(300, 255, 0, 0); // death flash
```

## Step 2: Particles (Phaser 3.60+ API)

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

## Step 3: Tweens

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

## Step 4: Sound

```typescript
const jumpSound = this.sound.add('jump', { volume: 0.5 });
const music = this.sound.add('bgm', { loop: true, volume: 0.3 });
music.play();
// In update() or callback:
jumpSound.play();
```

## Step 5: Mobile virtual controls (when needed)

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

## Step 6: Final verification

- DevTools → Performance → record 5 seconds of gameplay → confirm under 16.7ms/frame
- No `debug: true` in physics config
- No `console.log` calls remaining
- No TODO markers remaining
