# Game Patterns Reference

Game-specific Three.js patterns for animation state machines, player controllers,
camera-relative movement, delta capping, and mobile input.
Load this file alongside the paradigm reference when building games.

---

## Animation State Machine

Character animation in games requires blending between clips (idle, walk, run, attack)
with smooth crossfades and one-shot handling (death, hit reactions).

```javascript
class AnimationController {
  constructor(model, animations) {
    this.mixer = new THREE.AnimationMixer(model)
    this.clips = {}
    this.currentAction = null

    // Index clips by name for fast lookup
    animations.forEach((clip) => {
      this.clips[clip.name] = clip
    })
  }

  switchAnimation(name, options = {}) {
    const { fadeTime = 0.1, clampWhenFinished = false } = options

    const clip = this.clips[name]
    if (!clip) {
      console.warn(`Animation "${name}" not found. Available:`, Object.keys(this.clips))
      return
    }

    const nextAction = this.mixer.clipAction(clip)

    // Don't restart if already playing this animation
    if (this.currentAction === nextAction) return

    nextAction.reset()
    nextAction.clampWhenFinished = clampWhenFinished
    nextAction.loop = clampWhenFinished ? THREE.LoopOnce : THREE.LoopRepeat

    if (this.currentAction) {
      this.currentAction.crossFadeTo(nextAction, fadeTime, true)
    }

    nextAction.play()
    this.currentAction = nextAction
  }

  // Safe clip selection for ambient entities (skip death/die/dead clips)
  playAmbientAnimation(preferredName = 'Idle') {
    const EXCLUDED = /death|die|dead|ko|ragdoll/i

    // Try preferred name first
    if (this.clips[preferredName] && !EXCLUDED.test(preferredName)) {
      this.switchAnimation(preferredName)
      return
    }

    // Fall back to first non-excluded clip
    const safeClip = Object.keys(this.clips).find((name) => !EXCLUDED.test(name))
    if (safeClip) {
      this.switchAnimation(safeClip)
    } else {
      console.warn('No safe ambient animation found — all clips match exclusion filter')
    }
  }

  // One-shot: play once and return to previous animation
  playOnce(name, fadeTime = 0.1, returnTo = 'Idle') {
    const clip = this.clips[name]
    if (!clip) return

    const action = this.mixer.clipAction(clip)
    action.reset()
    action.clampWhenFinished = true
    action.loop = THREE.LoopOnce

    if (this.currentAction) {
      this.currentAction.crossFadeTo(action, fadeTime, true)
    }

    action.play()
    this.currentAction = action

    // Listen for finish and crossfade back
    const onFinish = (e) => {
      if (e.action === action) {
        this.switchAnimation(returnTo, { fadeTime })
        this.mixer.removeEventListener('finished', onFinish)
      }
    }
    this.mixer.addEventListener('finished', onFinish)
  }

  update(delta) {
    this.mixer.update(delta)
  }
}

// Usage:
const anim = new AnimationController(character, gltf.animations)
anim.switchAnimation('Idle')

// In game loop:
anim.update(delta)

// On input change:
if (isMoving) anim.switchAnimation('Walk', { fadeTime: 0.2 })
else anim.switchAnimation('Idle', { fadeTime: 0.3 })

// On damage:
anim.playOnce('Hit', 0.05, 'Idle')
```

---

## Camera-Relative Movement

For isometric and third-person games, the player's movement direction must come from
the camera's orientation — not world axes. Moving "forward" means moving in the direction
the camera is facing, projected onto the ground plane.

```javascript
// Assumes: camera is the Three.js camera, inputDir is a normalized {x, z} input vector
// where x = strafe, z = forward/back from player perspective

const cameraForward = new THREE.Vector3()
const cameraRight = new THREE.Vector3()
const moveDirection = new THREE.Vector3()

function getCameraRelativeMovement(camera, input) {
  // Extract camera forward projected onto XZ plane (ground)
  camera.getWorldDirection(cameraForward)
  cameraForward.y = 0
  cameraForward.normalize()

  // Camera right is perpendicular to forward in XZ plane
  cameraRight.crossVectors(cameraForward, new THREE.Vector3(0, 1, 0)).normalize()

  // Combine: forward/back from camera direction, strafe from camera right
  moveDirection.set(0, 0, 0)
  moveDirection.addScaledVector(cameraForward, -input.z)  // -z = forward in most input conventions
  moveDirection.addScaledVector(cameraRight, input.x)

  if (moveDirection.length() > 0) moveDirection.normalize()

  return moveDirection
}

// In game loop:
const input = { x: keys.d - keys.a, z: keys.s - keys.w }  // -1 to +1
const move = getCameraRelativeMovement(camera, input)
player.position.addScaledVector(move, speed * delta)

// Face the direction of travel
if (move.length() > 0.01) {
  const targetAngle = Math.atan2(move.x, move.z)
  player.rotation.y = THREE.MathUtils.lerp(
    player.rotation.y,
    targetAngle,
    10 * delta  // Rotation speed — higher = snappier
  )
}
```

---

## Delta Capping

After a tab-away or window focus loss, `requestAnimationFrame` delivers a large delta
(several seconds of elapsed time). Uncapped, this causes physics objects to tunnel through
geometry, velocities to explode, and animations to skip.

**Always cap delta before physics or animation updates.**

```javascript
renderer.setAnimationLoop((timestamp) => {
  const rawDelta = clock.getDelta()

  // Cap at 50ms (= 20fps minimum effective simulation rate)
  // Prevents physics explosion after tab-away or browser pause
  const delta = Math.min(rawDelta, 0.05)

  updatePhysics(delta)
  updateAnimations(delta)
  renderer.render(scene, camera)
})
```

Without the cap, a 5-second tab-away delivers delta=5.0 to physics — projectiles
teleport through walls, enemies fly off-screen, and spring systems explode.

---

## Player Controller

Separate physics state from render state. Input is read each frame, applied to velocity,
velocity applied to position, position applied to the mesh.

```javascript
class PlayerController {
  constructor(mesh, config = {}) {
    this.mesh = mesh
    this.position = mesh.position.clone()
    this.velocity = new THREE.Vector3()

    this.speed = config.speed ?? 5
    this.jumpForce = config.jumpForce ?? 8
    this.gravity = config.gravity ?? -20
    this.groundY = config.groundY ?? 0

    this.isGrounded = true
    this.input = { x: 0, z: 0, jump: false }
  }

  setInput(x, z, jump = false) {
    this.input.x = x
    this.input.z = z
    this.input.jump = jump
  }

  update(delta, camera) {
    // Camera-relative horizontal movement
    const move = getCameraRelativeMovement(camera, this.input)
    this.velocity.x = move.x * this.speed
    this.velocity.z = move.z * this.speed

    // Jump
    if (this.input.jump && this.isGrounded) {
      this.velocity.y = this.jumpForce
      this.isGrounded = false
    }

    // Gravity
    if (!this.isGrounded) {
      this.velocity.y += this.gravity * delta
    }

    // Apply velocity
    this.position.addScaledVector(this.velocity, delta)

    // Ground collision (simple flat ground)
    if (this.position.y <= this.groundY) {
      this.position.y = this.groundY
      this.velocity.y = 0
      this.isGrounded = true
    }

    // Sync mesh
    this.mesh.position.copy(this.position)

    // Face direction of travel
    if (Math.abs(this.velocity.x) + Math.abs(this.velocity.z) > 0.1) {
      const angle = Math.atan2(this.velocity.x, this.velocity.z)
      this.mesh.rotation.y = THREE.MathUtils.lerp(this.mesh.rotation.y, angle, 10 * delta)
    }
  }
}

// Key binding setup
const keys = { w: false, a: false, s: false, d: false, space: false }
window.addEventListener('keydown', (e) => { keys[e.key.toLowerCase()] = true })
window.addEventListener('keyup', (e) => { keys[e.key.toLowerCase()] = false })

// In game loop:
const input = {
  x: (keys.d ? 1 : 0) - (keys.a ? 1 : 0),
  z: (keys.s ? 1 : 0) - (keys.w ? 1 : 0),
}
player.setInput(input.x, input.z, keys[' '])
player.update(delta, camera)
```

---

## Mobile Input

### Gyroscope Tilt Controls

```javascript
class GyroscopeControls {
  constructor() {
    this.alpha = 0  // Z-axis rotation (compass)
    this.beta = 0   // X-axis tilt (front/back)
    this.gamma = 0  // Y-axis tilt (left/right)
    this.enabled = false
  }

  async requestPermission() {
    // iOS 13+ requires explicit permission
    if (typeof DeviceOrientationEvent?.requestPermission === 'function') {
      const state = await DeviceOrientationEvent.requestPermission()
      if (state !== 'granted') return false
    }
    window.addEventListener('deviceorientation', (e) => this.onOrientation(e))
    this.enabled = true
    return true
  }

  onOrientation(e) {
    this.alpha = e.alpha ?? 0  // 0-360°
    this.beta = e.beta ?? 0    // -180 to 180° (front/back tilt)
    this.gamma = e.gamma ?? 0  // -90 to 90° (left/right tilt)
  }

  // Returns normalized input vector from tilt
  getInput(deadzone = 5, maxTilt = 30) {
    const x = THREE.MathUtils.clamp(this.gamma / maxTilt, -1, 1)
    const z = THREE.MathUtils.clamp(this.beta / maxTilt, -1, 1)
    return {
      x: Math.abs(this.gamma) > deadzone ? x : 0,
      z: Math.abs(this.beta) > deadzone ? z : 0,
    }
  }
}

// Activate on user gesture (required by browsers):
document.getElementById('startBtn').addEventListener('click', async () => {
  const gyro = new GyroscopeControls()
  const granted = await gyro.requestPermission()
  if (!granted) console.warn('Gyroscope permission denied')
})
```

### Virtual Joystick Overlay

```javascript
class VirtualJoystick {
  constructor(container) {
    this.input = { x: 0, z: 0 }
    this.active = false
    this.center = { x: 0, y: 0 }
    this.radius = 60  // px

    this.stick = document.createElement('div')
    Object.assign(this.stick.style, {
      position: 'absolute', bottom: '80px', left: '80px',
      width: '120px', height: '120px',
      borderRadius: '50%', background: 'rgba(255,255,255,0.2)',
      border: '2px solid rgba(255,255,255,0.4)',
      touchAction: 'none',
    })

    this.knob = document.createElement('div')
    Object.assign(this.knob.style, {
      position: 'absolute', top: '30px', left: '30px',
      width: '60px', height: '60px',
      borderRadius: '50%', background: 'rgba(255,255,255,0.6)',
      pointerEvents: 'none',
    })

    this.stick.appendChild(this.knob)
    container.appendChild(this.stick)

    this.stick.addEventListener('touchstart', (e) => this.onStart(e), { passive: true })
    this.stick.addEventListener('touchmove', (e) => this.onMove(e), { passive: true })
    this.stick.addEventListener('touchend', () => this.onEnd())
  }

  onStart(e) {
    const rect = this.stick.getBoundingClientRect()
    this.center = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
    this.active = true
  }

  onMove(e) {
    if (!this.active) return
    const touch = e.touches[0]
    const dx = touch.clientX - this.center.x
    const dy = touch.clientY - this.center.y
    const dist = Math.min(Math.sqrt(dx * dx + dy * dy), this.radius)
    const angle = Math.atan2(dy, dx)

    this.input.x = (dist / this.radius) * Math.cos(angle)
    this.input.z = (dist / this.radius) * Math.sin(angle)

    // Move knob visually
    const kx = 30 + (dist / this.radius) * 30 * Math.cos(angle)
    const ky = 30 + (dist / this.radius) * 30 * Math.sin(angle)
    this.knob.style.left = `${kx}px`
    this.knob.style.top = `${ky}px`
  }

  onEnd() {
    this.active = false
    this.input = { x: 0, z: 0 }
    this.knob.style.left = '30px'
    this.knob.style.top = '30px'
  }
}

const joystick = new VirtualJoystick(document.body)
// In game loop: player.setInput(joystick.input.x, joystick.input.z)
```

---

## Error Handling

### Animation crossfade causes T-pose flash

Cause: Fading out an action that was never played, or crossfading to an action with
reset state issues.
Solution: Always call `nextAction.reset()` before `crossFadeTo`. Ensure `fadeTime > 0`
(zero-duration crossfade causes a one-frame T-pose).

### Camera-relative movement drifts sideways

Cause: `cameraForward` not projected onto XZ plane — includes Y component from camera tilt.
Solution: Always set `cameraForward.y = 0` and renormalize after getting world direction.

### Physics explosion after tab-away

Cause: Large delta (seconds) fed to physics unchanged.
Solution: `const delta = Math.min(rawDelta, 0.05)` before all physics updates.

### Mobile gyro doesn't fire on iOS

Cause: iOS 13+ requires explicit permission prompt triggered by user gesture.
Solution: Call `DeviceOrientationEvent.requestPermission()` inside a click/touchstart handler.

### Virtual joystick jitter on fast swipes

Cause: `touchmove` firing faster than frame rate, causing input oscillation.
Solution: Smooth the input: `this.input.x = lerp(this.input.x, rawX, 0.3)` in `onMove`.
