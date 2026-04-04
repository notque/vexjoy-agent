# Game Architecture Reference

Architecture patterns for Three.js games: EventBus, GameState, Constants, restart-safety,
and pre-ship validation. Load this file when the project has game-like structure (enemies,
scoring, player lifecycle, multiple game systems).

---

## EventBus: Decoupled System Communication

The EventBus is a central message bus that lets game systems (audio, visuals, scoring,
networking) communicate without direct references. This is the core decoupling pattern
for games with multiple interacting systems.

```javascript
class EventBus {
  constructor() {
    this._listeners = {}
  }

  on(event, callback) {
    if (!this._listeners[event]) this._listeners[event] = []
    this._listeners[event].push(callback)
    // Return unsubscribe function
    return () => this.off(event, callback)
  }

  off(event, callback) {
    if (!this._listeners[event]) return
    this._listeners[event] = this._listeners[event].filter((cb) => cb !== callback)
  }

  emit(event, data) {
    const listeners = this._listeners[event] ?? []
    listeners.forEach((cb) => cb(data))
  }

  // Remove all listeners for an event — use during restart
  clear(event) {
    delete this._listeners[event]
  }

  // Remove ALL listeners — use on full reset
  reset() {
    this._listeners = {}
  }
}

// Singleton — one bus for the whole game
export const bus = new EventBus()
```

### SPECTACLE_* Event Convention

Pre-wire visual effect events using the `SPECTACLE_` prefix. All visual/audio systems
subscribe to these events. Game logic emits them — it never calls visual systems directly.

```javascript
// Game events — emitted by logic, consumed by any number of systems
const EVENTS = {
  // Spectacle events: visual/audio systems subscribe to these
  SPECTACLE_EXPLOSION:   'spectacle:explosion',    // { position, radius, intensity }
  SPECTACLE_HIT:         'spectacle:hit',          // { position, attacker, defender }
  SPECTACLE_LEVELUP:     'spectacle:levelup',      // { position, level }
  SPECTACLE_DEATH:       'spectacle:death',        // { position, entity }
  SPECTACLE_COLLECTIBLE: 'spectacle:collectible',  // { position, type }

  // Game state events
  GAME_START:   'game:start',
  GAME_PAUSE:   'game:pause',
  GAME_RESUME:  'game:resume',
  GAME_OVER:    'game:over',    // { score, cause }
  GAME_RESTART: 'game:restart',

  // Gameplay events
  PLAYER_DAMAGED:  'player:damaged',   // { amount, source }
  PLAYER_DIED:     'player:died',
  ENEMY_KILLED:    'enemy:killed',     // { enemy, position, points }
  SCORE_CHANGED:   'score:changed',    // { score, delta }
}

// Visual system subscribes — doesn't know who emitted
bus.on(EVENTS.SPECTACLE_EXPLOSION, ({ position, radius }) => {
  spawnExplosionParticles(position, radius)
  screenShake(0.3)
})

// Audio system subscribes independently
bus.on(EVENTS.SPECTACLE_EXPLOSION, ({ intensity }) => {
  playSound('explosion', { volume: intensity })
})

// Scoring system subscribes to game events
bus.on(EVENTS.ENEMY_KILLED, ({ points }) => {
  gameState.score += points
  bus.emit(EVENTS.SCORE_CHANGED, { score: gameState.score, delta: points })
})

// Game logic emits — no knowledge of what subscribes
function killEnemy(enemy) {
  const points = ENEMY_POINTS[enemy.type]
  scene.remove(enemy.mesh)
  bus.emit(EVENTS.SPECTACLE_DEATH, { position: enemy.position, entity: enemy })
  bus.emit(EVENTS.ENEMY_KILLED, { enemy, position: enemy.position, points })
}
```

---

## GameState Singleton

Centralized, reset-capable state. All systems read from here. Mutation goes through
methods that emit events as side effects.

```javascript
class GameState {
  constructor() {
    this.reset()
  }

  reset() {
    this.score = 0
    this.health = CONSTANTS.PLAYER_MAX_HEALTH
    this.level = 1
    this.lives = 3
    this.inventory = []
    this.isRunning = false
    this.isPaused = false
    this.elapsedTime = 0
    this.enemiesKilled = 0
  }

  start() {
    this.reset()
    this.isRunning = true
    bus.emit(EVENTS.GAME_START, {})
  }

  pause() {
    this.isPaused = true
    bus.emit(EVENTS.GAME_PAUSE, {})
  }

  resume() {
    this.isPaused = false
    bus.emit(EVENTS.GAME_RESUME, {})
  }

  takeDamage(amount) {
    this.health = Math.max(0, this.health - amount)
    bus.emit(EVENTS.PLAYER_DAMAGED, { amount, source: null })

    if (this.health <= 0) {
      this.isRunning = false
      bus.emit(EVENTS.GAME_OVER, { score: this.score, cause: 'health' })
    }
  }

  addScore(points) {
    this.score += points
    bus.emit(EVENTS.SCORE_CHANGED, { score: this.score, delta: points })
  }

  levelUp() {
    this.level++
    bus.emit(EVENTS.SPECTACLE_LEVELUP, { level: this.level })
  }
}

export const gameState = new GameState()
```

---

## Constants Module

All magic numbers in one file. Constants are read-only, grouped by system.
No number should appear in game logic without a name from this module.

```javascript
// constants.js
export const CONSTANTS = {
  // Physics
  GRAVITY: -20,
  JUMP_FORCE: 8,
  PLAYER_SPEED: 5,
  PLAYER_SPRINT_MULTIPLIER: 1.8,

  // Player
  PLAYER_MAX_HEALTH: 100,
  PLAYER_INVINCIBILITY_FRAMES: 0.5,  // seconds

  // Enemies
  ENEMY_SPEED_BASE: 2.5,
  ENEMY_SPEED_BOSS: 1.2,
  ENEMY_DETECTION_RADIUS: 15,
  ENEMY_ATTACK_RANGE: 1.5,
  ENEMY_ATTACK_DAMAGE: 10,
  ENEMY_ATTACK_COOLDOWN: 1.0,  // seconds

  // Spawning
  SPAWN_INTERVAL_INITIAL: 5.0,    // seconds between waves
  SPAWN_INTERVAL_MIN: 1.0,        // fastest spawn rate
  SPAWN_COUNT_INITIAL: 3,
  SPAWN_COUNT_MAX: 20,

  // Scoring
  POINTS_ENEMY_BASIC: 10,
  POINTS_ENEMY_ELITE: 50,
  POINTS_ENEMY_BOSS: 500,
  SCORE_MULTIPLIER_COMBO: 1.5,

  // Visual
  CAMERA_FOV: 60,
  CAMERA_NEAR: 0.1,
  CAMERA_FAR: 1000,
  SHADOW_MAP_SIZE: 2048,

  // Delta cap — prevent physics explosion after tab-away
  MAX_DELTA: 0.05,
}
```

---

## Restart-Safety

Every game system must cleanly reset. This is non-negotiable — stale state from a
previous game session causes impossible-to-reproduce bugs.

**Restart-safety checklist for each system**:
1. Remove all scene objects added during the session
2. Cancel all scheduled callbacks (setTimeout, setInterval, mixer listeners)
3. Reset all internal state variables to initial values
4. Unsubscribe event listeners added during the session (or call `bus.reset()`)

```javascript
class EnemySystem {
  constructor() {
    this.enemies = []
    this.spawnTimer = 0
    this._unsubscribers = []
  }

  init() {
    // Subscribe and store unsubscribe functions
    this._unsubscribers.push(
      bus.on(EVENTS.GAME_OVER, () => this.reset()),
      bus.on(EVENTS.GAME_RESTART, () => this.init())
    )
  }

  reset() {
    // Remove all enemy meshes from scene
    this.enemies.forEach((e) => {
      scene.remove(e.mesh)
      e.mesh.geometry.dispose()
      e.mesh.material.dispose()
    })
    this.enemies = []
    this.spawnTimer = 0

    // Unsubscribe listeners from previous session
    this._unsubscribers.forEach((unsub) => unsub())
    this._unsubscribers = []
  }

  update(delta) {
    if (!gameState.isRunning) return
    // ... spawn and update logic
  }
}

// Top-level game restart handler
function restartGame() {
  // 1. Reset all systems
  enemySystem.reset()
  projectileSystem.reset()
  uiSystem.reset()
  particleSystem.reset()

  // 2. Reset shared state
  gameState.reset()
  bus.reset()  // Clear all event subscriptions

  // 3. Re-initialize systems (re-subscribe after bus.reset)
  enemySystem.init()
  projectileSystem.init()
  uiSystem.init()

  // 4. Start fresh
  gameState.start()
}
```

**Restart stress test**: Run `restartGame()` 5 times in rapid succession from the browser
console. No console errors, no ghost enemies, no leaked subscriptions, score starts at 0.
This is the acceptance test for restart-safety.

---

## Pre-Ship Checklist

Run this before delivery. Every item is a pass/fail check, not a judgment call.

```markdown
## Build
- [ ] `npm run build` completes without errors
- [ ] Output file size is reasonable (< 5MB for typical games)

## Runtime
- [ ] No console errors on initial load
- [ ] No console errors after 60 seconds of play
- [ ] No console errors after restart

## Responsiveness
- [ ] Canvas fills viewport at 1280x720
- [ ] Canvas fills viewport at 375x812 (iPhone)
- [ ] Resize mid-game does not break layout or camera aspect ratio

## Input
- [ ] Keyboard controls work (WASD / arrow keys)
- [ ] Mouse/touch controls work on mobile
- [ ] Virtual joystick appears on touch devices (if applicable)

## Game Loop
- [ ] Restart works without page reload
- [ ] Restart works 5 times rapidly — no leaked state
- [ ] Pause/resume works correctly

## Performance
- [ ] > 30fps on target hardware at target resolution
- [ ] No memory leaks after 5 minutes of play (Chrome DevTools > Memory > Heap snapshot)
- [ ] `Math.min(delta, MAX_DELTA)` applied — verified by pausing tab and resuming

## Audio (if applicable)
- [ ] Audio plays on first user interaction
- [ ] Audio does not play before user interaction (browser policy)
- [ ] Volume levels balanced

## Final
- [ ] No debug console.log statements in production build
- [ ] No AxesHelper or GridHelper visible
- [ ] All placeholder text/assets replaced with final content
```

---

## Error Handling

### Ghost enemies after restart

Cause: Enemy meshes not removed from scene, or `enemies` array not cleared on reset.
Solution: In `reset()`, call `scene.remove(e.mesh)` for every enemy, then set `this.enemies = []`.

### Score persisting across restarts

Cause: `gameState.score` not reset, or UI not re-reading from `gameState`.
Solution: `gameState.reset()` must be called first in `restartGame()`, before system init.

### Event listeners firing multiple times per event

Cause: `bus.on()` called in `init()` but `bus.off()` not called before next `init()` call.
Solution: Store and call unsubscribers before re-subscribing, or call `bus.reset()` before
re-running `init()` on all systems.

### Memory growing steadily during play

Cause: Geometries and materials not disposed when enemies are removed.
Solution: Call `mesh.geometry.dispose()` and `mesh.material.dispose()` when removing objects.
For textures: `texture.dispose()`. Three.js does NOT garbage-collect GPU resources automatically.

### Delta cap causing slow-motion after tab-away

Cause: This is the correct behavior — the cap prevents physics explosion at the cost of
running slower than real-time for one frame after a long pause.
Solution: This is a feature. The alternative (uncapped delta) causes tunneling and explosions.
If the effect is noticeable, reduce `MAX_DELTA` further (e.g., `0.033` = 30fps minimum).
