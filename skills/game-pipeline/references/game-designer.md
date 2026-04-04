# Game Designer Reference

Visual polish and "juice" patterns — the effects that make a game feel great. All effects wire to EventBus events, not game logic, so they can be added or removed without touching gameplay code.

---

## EventBus Wiring Pattern

Every effect subscribes to an event. The game emits the event; effects respond. No direct coupling.

```javascript
// src/effects/index.js
import { on } from '../EventBus.js';
import { screenShake } from './ScreenShake.js';
import { hitFreeze } from './HitFreeze.js';
import { particleBurst } from './ParticleBurst.js';
import { floatingText } from './FloatingText.js';

export function initEffects(scene) {
  on('ENEMY_HIT',    ({ x, y, damage }) => {
    screenShake(scene, { intensity: 0.006, duration: 120 });
    particleBurst(scene, { x, y, count: 12, color: 0xff4444 });
    floatingText(scene, { x, y, text: `-${damage}`, color: '#ff4444' });
  });
  on('LEVEL_UP',    () => spectacleEvent(scene, 'LEVEL_UP'));
  on('GAME_OVER',   () => spectacleEvent(scene, 'GAME_OVER'));
  on('COMBO_REACHED', ({ combo }) => {
    floatingText(scene, { x: 400, y: 200, text: `${combo}x COMBO!`, scale: 1.5, color: '#ffdd00' });
    screenShake(scene, { intensity: 0.003 * combo, duration: 80 });
  });
}
```

---

## Screen Shake

Short (100–200ms), small intensity (0.005–0.01). Anything larger feels wrong.

**Three.js** (camera offset):
```javascript
// src/effects/ScreenShake.js
export function screenShake(camera, { intensity = 0.007, duration = 150 } = {}) {
  const start = performance.now();
  const origin = camera.position.clone();

  function shake() {
    const elapsed = performance.now() - start;
    if (elapsed >= duration) { camera.position.copy(origin); return; }
    const decay = 1 - elapsed / duration;
    camera.position.x = origin.x + (Math.random() - 0.5) * intensity * decay * 2;
    camera.position.y = origin.y + (Math.random() - 0.5) * intensity * decay * 2;
    requestAnimationFrame(shake);
  }
  requestAnimationFrame(shake);
}
```

**Phaser** (camera shake):
```javascript
export function screenShake(scene, { intensity = 0.006, duration = 120 } = {}) {
  scene.cameras.main.shake(duration, intensity);
}
```

---

## Hit Freeze Frame

Pause the game for 50–100ms on a big hit. The pause duration is what creates the impact feel.

```javascript
// src/effects/HitFreeze.js
export function hitFreeze(scene, durationMs = 80) {
  // Phaser: pause physics + tweens
  scene.physics.pause();
  scene.tweens.pauseAll();

  scene.time.delayedCall(durationMs, () => {
    scene.physics.resume();
    scene.tweens.resumeAll();
  });
}

// Three.js: set a deltaTime multiplier to 0 for N frames
let freezeFrames = 0;
export function hitFreeze3D(frames = 5) { freezeFrames = frames; }
export function getFreezeMultiplier() {
  if (freezeFrames > 0) { freezeFrames--; return 0; }
  return 1;
}
// In animation loop: delta *= getFreezeMultiplier();
```

---

## Particle System

**Phaser particle emitter** (one-shot burst):
```javascript
// src/effects/ParticleBurst.js
export function particleBurst(scene, { x, y, count = 10, color = 0xff4444 } = {}) {
  const particles = scene.add.particles(x, y, 'pixel', {
    speed:     { min: 80, max: 200 },
    angle:     { min: 0, max: 360 },
    scale:     { start: 1.0, end: 0 },
    lifespan:  400,
    quantity:  count,
    tint:      color,
    emitting:  false,
  });
  particles.explode(count);
  scene.time.delayedCall(500, () => particles.destroy());
}
```

**Three.js Points-based burst**:
```javascript
export function particleBurst3D(scene, { x, y, z = 0, count = 20, color = 0xff4444 } = {}) {
  const geo = new THREE.BufferGeometry();
  const positions = new Float32Array(count * 3);
  const velocities = [];
  for (let i = 0; i < count; i++) {
    positions[i * 3] = x; positions[i * 3 + 1] = y; positions[i * 3 + 2] = z;
    velocities.push(new THREE.Vector3(
      (Math.random() - 0.5) * 0.2,
      (Math.random() - 0.5) * 0.2,
      (Math.random() - 0.5) * 0.2
    ));
  }
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const mat = new THREE.PointsMaterial({ color, size: 0.05 });
  const points = new THREE.Points(geo, mat);
  scene.add(points);

  let life = 0;
  const tick = () => {
    life++;
    if (life > 30) { scene.remove(points); geo.dispose(); mat.dispose(); return; }
    const pos = geo.attributes.position.array;
    for (let i = 0; i < count; i++) {
      pos[i * 3]     += velocities[i].x;
      pos[i * 3 + 1] += velocities[i].y;
      pos[i * 3 + 2] += velocities[i].z;
      velocities[i].multiplyScalar(0.92); // friction
    }
    geo.attributes.position.needsUpdate = true;
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
```

---

## Floating Text (Damage Numbers / Score Popups)

**Phaser**:
```javascript
// src/effects/FloatingText.js
export function floatingText(scene, { x, y, text, color = '#ffffff', scale = 1.0 } = {}) {
  const t = scene.add.text(x, y, text, {
    fontSize:  `${Math.round(24 * scale)}px`,
    fontStyle: 'bold',
    color,
    stroke:    '#000000',
    strokeThickness: 3,
  }).setOrigin(0.5);

  scene.tweens.add({
    targets:  t,
    y:        y - 60,
    alpha:    0,
    scaleX:   scale * 1.3,
    scaleY:   scale * 1.3,
    duration: 800,
    ease:     'Power2',
    onComplete: () => t.destroy(),
  });
}
```

---

## Spectacle Events

Pre-wire `SPECTACLE_*` events on the EventBus so any system can trigger a big moment:

```javascript
// src/effects/SpectacleEvents.js
import { on, emit } from '../EventBus.js';

export function initSpectacle(scene) {
  on('SPECTACLE_LEVEL_UP', () => {
    screenShake(scene, { intensity: 0.012, duration: 300 });
    // Full-screen flash
    const flash = scene.add.rectangle(400, 300, 800, 600, 0xffffff, 0.8);
    scene.tweens.add({ targets: flash, alpha: 0, duration: 400, onComplete: () => flash.destroy() });
  });
  on('SPECTACLE_GAME_OVER', () => {
    scene.cameras.main.fade(500, 0, 0, 0);
  });
}

// Emit from anywhere:
// emit('SPECTACLE_LEVEL_UP');
```

---

## Opening Moment Rule

The first 3 seconds must hook the player. Start with immediate visual spectacle.

**Checklist**:
- [ ] Game starts with action visible on screen within 1 second of load
- [ ] At least one moving element before player input is required
- [ ] Camera or environment establishes the world immediately
- [ ] No loading spinner visible (preload assets ahead of scene transition)

**Anti-patterns**:
- Starting on a static title screen with no animation
- Requiring a button click before anything appears
- Empty black screen while assets load (show progress bar or instant placeholder)

---

## Error Handling

### Error: Particles Accumulate and Slow the Game
**Cause**: Emitter not destroyed after burst completes
**Fix**: Always destroy the emitter after `lifespan` + buffer: `scene.time.delayedCall(lifespan + 100, () => particles.destroy())`.

### Error: Screen Shake Causes Camera Drift
**Cause**: Shake accumulates offset without resetting to origin
**Fix**: Store `origin` before shake starts and restore it exactly when duration elapses. Use the pattern above that copies origin and restores on completion.

### Error: Hit Freeze Breaks Audio
**Cause**: `scene.physics.pause()` does not pause the Web Audio clock
**Fix**: Hit freeze is visual only — do not pause AudioContext. SFX playing during freeze are expected and feel correct (they reinforce the impact).

### Error: Floating Text Overlaps When Multiple Hits Fire Simultaneously
**Cause**: All floating texts spawn at the same (x, y)
**Fix**: Add random offset: `y: y - 10 + Math.random() * 20`. Or queue texts and stagger spawn by 50ms each.
