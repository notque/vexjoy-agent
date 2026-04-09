---
name: Phaser Game Feel Patterns
description: Screen shake, particle bursts, hit pause, scale punch, tween chaining, sound timing — techniques that make Phaser 3 games feel polished and responsive
agent: phaser-gamedev
category: visual-techniques
version_range: "Phaser 3.60+"
---

# Game Feel Patterns Reference

> **Scope**: "Juice" — the collection of micro-feedback effects that make a game feel satisfying. Camera shake, particles, time dilation, hit stop, scale punch, tween chains, and audio timing. Does NOT cover physics setup or tilemap config.
> **Version range**: Phaser 3.60+
> **Generated**: 2026-04-08

---

## Screen Shake

Camera shake is the most visceral hit-feedback tool. Phaser 3.60+ has `camera.shake()` built in.

```typescript
// Basic shake on hit — parameters: duration (ms), intensity (0-1)
this.cameras.main.shake(150, 0.008);

// Directional shake via camera.pan() + tween
// Use for knockback-directional feedback (e.g., hit from left = camera moves left then returns)
hitFromLeft(): void {
  this.tweens.add({
    targets: this.cameras.main,
    scrollX: this.cameras.main.scrollX - 12, // push camera left
    duration: 60,
    ease: 'Power2',
    yoyo: true,   // return to original position
    repeat: 2,    // 2 oscillations
  });
}

// Strong boss hit: combined shake + flash
onBossHit(): void {
  this.cameras.main.shake(300, 0.02);
  this.cameras.main.flash(100, 255, 200, 0, false); // flash: duration, r, g, b, force
}
```

**Shake intensity guide**:
| Event | Duration (ms) | Intensity |
|-------|--------------|-----------|
| Player takes damage | 120 | 0.006 |
| Enemy dies | 200 | 0.012 |
| Explosion | 350 | 0.025 |
| Boss attack | 400 | 0.035 |

---

## Particle Burst Effects (Phaser 3.60+ API)

Phaser 3.60 rewrote the particle system. The old `ParticleEmitterManager` API is removed.

```typescript
// Coin collect burst — Phaser 3.60+ API
onCoinCollect(x: number, y: number): void {
  const emitter = this.add.particles(x, y, 'spark', {
    speed: { min: 80, max: 200 },
    angle: { min: 0, max: 360 },
    scale: { start: 0.6, end: 0 },
    alpha: { start: 1, end: 0 },
    lifespan: 500,
    quantity: 12,
    tint: [0xffdd00, 0xffaa00, 0xffffff],
    gravityY: 300,
    emitting: false, // don't emit continuously
  });

  emitter.explode(12, x, y); // fire burst, then auto-destroy after all particles die
  // Emitter auto-destroys when all particles expire (Phaser 3.60+ default)
}

// Hit sparks (directional)
onHit(x: number, y: number, directionX: number): void {
  const emitter = this.add.particles(x, y, 'spark', {
    speed: { min: 100, max: 250 },
    angle: { min: -30, max: 30 },          // narrow cone forward
    rotate: { min: 0, max: 360 },
    scale: { start: 0.4, end: 0 },
    lifespan: 300,
    quantity: 6,
    gravityY: 500,
    emitting: false,
  });

  emitter.setParticleRotation(directionX > 0 ? 0 : 180); // face hit direction
  emitter.explode(6, x, y);
}

// Continuous trail effect (stops when assigned sprite is recycled)
attachTrail(sprite: Phaser.GameObjects.Sprite): Phaser.GameObjects.Particles.ParticleEmitter {
  return this.add.particles(0, 0, 'trail', {
    follow: sprite,           // emitter follows sprite
    followOffset: { x: -sprite.width / 2, y: 0 },
    speed: 20,
    lifespan: 200,
    scale: { start: 0.3, end: 0 },
    alpha: { start: 0.6, end: 0 },
    frequency: 16,            // emit every 16ms (~60fps)
  });
}
```

---

## Hit Pause / Time Dilation

Briefly stopping time on a heavy hit makes the impact feel weighty. Phaser uses `this.physics.world.timeScale` and scene's `this.time.timeScale`.

```typescript
// Hit stop: freeze game time for N ms then resume
hitStop(duration: number = 80): void {
  if (this.hitStopActive) return; // prevent stacking
  this.hitStopActive = true;

  this.physics.world.timeScale = 0.0001; // near-zero (can't be exactly 0)
  this.tweens.timeScale = 0.0001;
  this.time.timeScale = 0.0001;

  this.time.delayedCall(duration, () => {
    this.physics.world.timeScale = 1;
    this.tweens.timeScale = 1;
    this.time.timeScale = 1;
    this.hitStopActive = false;
  });
}

// Slow-motion mode (bullet time)
enterSlowMo(duration: number = 2000): void {
  this.physics.world.timeScale = 0.25;
  this.tweens.timeScale = 0.25;
  this.time.timeScale = 0.25;
  this.sound.setRate(0.8); // Phaser 3.60+: slow audio pitch

  this.time.delayedCall(duration, () => {
    this.physics.world.timeScale = 1;
    this.tweens.timeScale = 1;
    this.time.timeScale = 1;
    this.sound.setRate(1.0);
  });
}
```

---

## Scale Punch (Squash and Stretch)

Scale punch on hit makes sprites feel physical. Classic squash-and-stretch on impact:

```typescript
// Scale punch: fast enlarge → squash → return to normal
scalePunch(target: Phaser.GameObjects.Sprite, punchX = 1.4, punchY = 0.7): void {
  this.tweens.add({
    targets: target,
    scaleX: punchX,
    scaleY: punchY,
    duration: 60,
    ease: 'Back.easeOut',
    yoyo: true,                           // auto-return to original scale
    onComplete: () => {
      target.setScale(1);                 // ensure perfect reset
    },
  });
}

// Wobble: oscillating scale for collecting items
wobble(target: Phaser.GameObjects.Sprite): void {
  this.tweens.add({
    targets: target,
    scaleX: { from: 1, to: 1.2 },
    scaleY: { from: 1, to: 0.85 },
    duration: 80,
    ease: 'Sine.easeInOut',
    yoyo: true,
    repeat: 2,
    onComplete: () => target.setScale(1),
  });
}

// Death spin: rotation + scale fade for enemies
dieEffect(target: Phaser.GameObjects.Sprite): void {
  this.tweens.add({
    targets: target,
    angle: 720,               // two full rotations
    scaleX: 0,
    scaleY: 0,
    alpha: 0,
    duration: 400,
    ease: 'Power2.easeIn',
    onComplete: () => target.destroy(),
  });
}
```

---

## Tween Chaining

Tween chains let you sequence effects without manual timers:

```typescript
// Chain: damage flash → shake → return to normal
onPlayerHit(player: Phaser.GameObjects.Sprite): void {
  // Prevent multiple chains running simultaneously
  if (player.getData('invincible')) return;
  player.setData('invincible', true);

  this.tweens.chain({
    targets: player,
    tweens: [
      {
        alpha: 0.2,
        duration: 60,
        ease: 'Linear',
        yoyo: true,
        repeat: 5, // 6 flashes total = 720ms invincibility
      },
      {
        alpha: 1,
        duration: 1,
        onComplete: () => player.setData('invincible', false),
      },
    ],
  });

  this.cameras.main.shake(100, 0.005);
}

// Score popup: rise + fade
showScorePopup(x: number, y: number, points: number): void {
  const text = this.add.text(x, y, `+${points}`, {
    fontSize: '20px',
    color: '#ffdd00',
    stroke: '#000',
    strokeThickness: 3,
  }).setOrigin(0.5).setDepth(100);

  this.tweens.chain({
    targets: text,
    tweens: [
      { y: y - 40, scaleX: 1.2, scaleY: 1.2, duration: 200, ease: 'Back.easeOut' },
      { y: y - 80, scaleX: 1, scaleY: 1, alpha: 0, duration: 400, ease: 'Power2.easeIn' },
    ],
    onComplete: () => text.destroy(),
  });
}
```

---

## Sound Cue Timing Patterns

Sound timing is critical for feeling responsive. Phaser 3.60+ Web Audio has predictable latency.

```typescript
// Play sound with attack on physics contact (not on timer)
setupSoundCues(): void {
  // Preload in BootScene.preload():
  // this.load.audio('hit', ['assets/sounds/hit.ogg', 'assets/sounds/hit.mp3']);
  // this.load.audio('pickup', ['assets/sounds/pickup.ogg']);

  this.hitSound = this.sound.add('hit', { volume: 0.7 });
  this.pickupSound = this.sound.add('pickup', { volume: 0.5 });

  // Multiple hit sounds avoid "machine gun" repetition
  this.hitSounds = [
    this.sound.add('hit_1', { volume: 0.7 }),
    this.sound.add('hit_2', { volume: 0.6 }),
    this.sound.add('hit_3', { volume: 0.8 }),
  ];
}

playHit(): void {
  // Randomize pitch to avoid identical sounds feeling robotic
  const sound = Phaser.Utils.Array.GetRandom(this.hitSounds) as Phaser.Sound.WebAudioSound;
  sound.setRate(Phaser.Math.FloatBetween(0.9, 1.1));
  sound.play();
}

// Sound with camera shake: start at same frame for synchronized feel
onEnemyDeath(x: number, y: number): void {
  this.sound.play('explosion', { volume: 0.9 });
  this.cameras.main.shake(200, 0.015);    // same frame — synchronized impact
  this.createDeathParticles(x, y);         // same frame
}
```

---

## Anti-Pattern Catalog

### ❌ Using Alpha Tweens Instead of Particle Bursts for Hit Effects

**Detection**:
```bash
grep -rn "tween.*alpha\|alpha.*tween" --include="*.ts" --include="*.js"
rg "alpha.*0\b" --type ts -B 2 | grep "onHit\|takeDamage\|damage\|hit"
```

**What it looks like**:
```typescript
// BAD: alpha blink communicates "invisible" not "impact"
onHit(): void {
  this.tweens.add({
    targets: this.player,
    alpha: { from: 0, to: 1 },
    repeat: 5,
    duration: 80,
  });
}
```

**Why wrong**: Alpha blink is invisible feedback — it removes the visual, it doesn't add one. Players learn to "feel" hits through additive signals: particles appear, camera moves, sound plays. Removing the player sprite subtracts the signal.

**Fix**: Use alpha blink for invincibility indication (secondary) and add a particle burst (primary hit feedback):
```typescript
onHit(): void {
  // Primary: add particles at hit position
  this.add.particles(this.player.x, this.player.y, 'spark', {
    speed: { min: 60, max: 150 }, quantity: 8, lifespan: 250, emitting: false,
  }).explode(8);
  // Secondary: blink for invincibility window
  this.tweens.add({ targets: this.player, alpha: { from: 0.3, to: 1 }, repeat: 4, duration: 80 });
}
```

---

### ❌ Creating Physics Bodies Inside update()

**Detection**:
```bash
grep -rn "physics\.add\.\(sprite\|image\|existing\)\|add\.group" --include="*.ts" --include="*.js"
rg "update\(.*delta\)" --type ts -A 30 | grep "physics\.add"
```

**What it looks like**:
```typescript
update(_time: number, _delta: number): void {
  if (this.fireButton.isDown) {
    // BAD: new physics sprite every frame the button is held
    const bullet = this.physics.add.image(this.player.x, this.player.y, 'bullet');
    bullet.setVelocityX(400);
  }
}
```

**Why wrong**: Creating physics bodies in `update()` allocates Box2D/Arcade body objects and THREE.js objects every frame. GC pressure causes visible stuttering at sustained fire rates. Frame rate drops from 60 to 30 after ~5 seconds of firing.

**Fix**: Pool bullets in `create()`, recycle in `update()`:
```typescript
create(): void {
  this.bullets = this.physics.add.group({
    classType: Phaser.Physics.Arcade.Image,
    maxSize: 20,
    runChildUpdate: false,
  });
}

fireBullet(): void {
  const bullet = this.bullets.get(this.player.x, this.player.y, 'bullet');
  if (!bullet) return;
  bullet.setActive(true).setVisible(true);
  bullet.body.setVelocityX(400);
}
```

---

### ❌ Camera Shake Without Bounds

**Detection**:
```bash
grep -rn "camera\.shake\|cameras\.main\.shake" --include="*.ts" --include="*.js"
rg "cameras\.main" --type ts | grep -v "bounds\|follow\|setZoom"
```

**What it looks like**:
```typescript
// BAD: camera shakes past world edge, revealing void outside the map
this.cameras.main.shake(300, 0.05); // no world bounds set
```

**Why wrong**: Camera shake pans the camera. Without bounds, the camera reveals empty space outside the tilemap, breaking immersion.

**Fix**:
```typescript
// Set bounds before any shake call
this.cameras.main.setBounds(0, 0, map.widthInPixels, map.heightInPixels);
this.cameras.main.shake(300, 0.02); // now shake is clamped to world edge
```

---

## Detection Commands Reference

```bash
# Find all shake calls — verify intensity is appropriate
grep -rn "cameras\.main\.shake" --include="*.ts" --include="*.js"

# Find particle emitters — verify using Phaser 3.60+ API (not old ParticleEmitterManager)
grep -rn "ParticleEmitterManager\|createEmitter" --include="*.ts"

# Find tween.add calls — check for yoyo/repeat patterns for polish
grep -rn "tweens\.add\|tweens\.chain" --include="*.ts" --include="*.js"

# Find timeScale usage — verify hit-stop cleanup resets all time scales
grep -rn "timeScale" --include="*.ts" --include="*.js"
```

---

## See Also

- `references/tilemaps-and-physics.md` — Tilemap collision, Matter.js categories, slope terrain
- `references/core-patterns.md` — Scene lifecycle, state machines, input
- `references/performance.md` — Object pooling, GC avoidance
