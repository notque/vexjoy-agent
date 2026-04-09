---
name: Three.js Advanced Animation
description: AnimationMixer with morph targets, skeletal animation, procedural IK approximation, GSAP integration, particle system animation via BufferGeometry attributes
agent: threejs-builder
category: visual-techniques
version_range: "Three.js r150+"
---

# Advanced Animation Reference

> **Scope**: Three.js animation systems beyond basic rotation — AnimationMixer, morph targets, skeletal rigs, procedural IK, GSAP integration, and GPU-driven particle animation. GLTF model loading patterns live in gltf-loading.md.
> **Version range**: Three.js r150+
> **Generated**: 2026-04-08

---

## AnimationMixer with Morph Targets

Morph targets (blend shapes) animate between pre-defined geometry states. Common for facial expressions and soft-body deformation.

```javascript
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const loader = new GLTFLoader();
const gltf = await loader.loadAsync('/models/character.glb');
scene.add(gltf.scene);

// AnimationMixer drives both skeleton and morph targets from GLTF
const mixer = new THREE.AnimationMixer(gltf.scene);

// Morph targets are accessed via mesh.morphTargetInfluences[]
// Three.js r150+: morphTargetDictionary maps names to indices
const mesh = gltf.scene.getObjectByName('Face');
if (mesh && mesh.morphTargetDictionary) {
  const smileIndex = mesh.morphTargetDictionary['smile'];  // name from blender
  const angryIndex = mesh.morphTargetDictionary['angry'];

  // Animate morph weights directly (0.0 = neutral, 1.0 = full morph)
  mesh.morphTargetInfluences[smileIndex] = 0.0;

  // GSAP tween for smooth expression transition
  gsap.to(mesh.morphTargetInfluences, {
    [smileIndex]: 1.0,
    duration: 0.3,
    ease: 'power2.out',
  });
}

// Play an AnimationClip from the GLTF (drives skeleton + morph via keyframes)
const clip = gltf.animations.find(a => a.name === 'Idle');
if (clip) {
  const action = mixer.clipAction(clip);
  action.play();
}

// Update mixer in animation loop
const clock = new THREE.Clock();
renderer.setAnimationLoop(() => {
  const delta = clock.getDelta();
  mixer.update(delta); // delta in seconds, not ms
  renderer.render(scene, camera);
});
```

### Crossfading Between Animations

```javascript
// Crossfade from current action to next
function crossFadeTo(mixer, fromAction, toAction, duration = 0.3) {
  toAction.enabled = true;
  toAction.setEffectiveTimeScale(1);
  toAction.setEffectiveWeight(1);
  toAction.time = 0;

  fromAction.crossFadeTo(toAction, duration, true);
  toAction.play();
}

const idleAction = mixer.clipAction(gltf.animations.find(a => a.name === 'Idle'));
const walkAction = mixer.clipAction(gltf.animations.find(a => a.name === 'Walk'));

idleAction.play();
// Later:
crossFadeTo(mixer, idleAction, walkAction, 0.3);
```

---

## Skeletal Animation and Bone Manipulation

### Direct Bone Manipulation (Procedural Override)

```javascript
// Access skeleton from a SkinnedMesh
const skinnedMesh = gltf.scene.getObjectByName('Body');
const skeleton = skinnedMesh.skeleton;

// List all bones
skeleton.bones.forEach((bone, i) => {
  console.log(i, bone.name);
});

// Get specific bone by name
const headBone = skeleton.bones.find(b => b.name === 'Head');
const spineBone = skeleton.bones.find(b => b.name === 'Spine');

// Rotate bones procedurally (overrides AnimationMixer for those bones)
renderer.setAnimationLoop(() => {
  const t = clock.getElapsedTime();
  // Head tracks mouse position
  headBone.rotation.y = THREE.MathUtils.lerp(
    headBone.rotation.y,
    mouseTargetY,
    0.1 // lerp factor — controls follow speed
  );
  headBone.rotation.x = THREE.MathUtils.clamp(
    THREE.MathUtils.lerp(headBone.rotation.x, mouseTargetX, 0.1),
    -0.4, 0.4
  );

  mixer.update(clock.getDelta());
  renderer.render(scene, camera);
});
```

### SkeletonHelper for Debug Visualization

```javascript
// Visualize bone positions during development
const helper = new THREE.SkeletonHelper(gltf.scene);
helper.visible = true; // set false in production
scene.add(helper);

// Remove before shipping:
// scene.remove(helper);
// helper.dispose();
```

---

## Procedural Animation

### IK Approximation (Cyclic Coordinate Descent)

Full IK solvers are complex. For 2-3 bone chains (arms, legs), CCD gives good results without a library:

```javascript
// Two-bone IK: shoulder → elbow → wrist targeting a point
function solveTwoBoneIK(root, mid, tip, target) {
  const rootPos = new THREE.Vector3().setFromMatrixPosition(root.matrixWorld);
  const midPos = new THREE.Vector3().setFromMatrixPosition(mid.matrixWorld);
  const tipPos = new THREE.Vector3().setFromMatrixPosition(tip.matrixWorld);

  const upperLen = rootPos.distanceTo(midPos);
  const lowerLen = midPos.distanceTo(tipPos);
  const totalLen = upperLen + lowerLen;
  const targetDist = rootPos.distanceTo(target);

  // Clamp target to reachable range
  const reach = Math.min(targetDist, totalLen * 0.99);
  const reachTarget = new THREE.Vector3()
    .subVectors(target, rootPos)
    .normalize()
    .multiplyScalar(reach)
    .add(rootPos);

  // Law of cosines for elbow angle
  const d = rootPos.distanceTo(reachTarget);
  const cosAngle = (upperLen * upperLen + d * d - lowerLen * lowerLen)
    / (2 * upperLen * d);
  const angle = Math.acos(THREE.MathUtils.clamp(cosAngle, -1, 1));

  // Apply rotation to root bone (simplified — assumes Y-up local space)
  const dir = new THREE.Vector3().subVectors(reachTarget, rootPos).normalize();
  root.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
  root.rotateZ(angle);
}
```

### Spring Physics (Secondary Animation)

```javascript
// Spring system for hair, tail, or accessory bounce
class Spring {
  constructor(stiffness = 100, damping = 15, mass = 1) {
    this.stiffness = stiffness;
    this.damping = damping;
    this.mass = mass;
    this.position = 0;
    this.velocity = 0;
    this.target = 0;
  }

  update(delta) {
    const force = -this.stiffness * (this.position - this.target)
                  - this.damping * this.velocity;
    this.velocity += (force / this.mass) * delta;
    this.position += this.velocity * delta;
    return this.position;
  }
}

const tailSpring = new Spring(80, 12, 1);

renderer.setAnimationLoop(() => {
  const delta = clock.getDelta();
  tailSpring.target = characterVelocityX * 0.3; // tail lags behind movement
  const tailAngle = tailSpring.update(delta);
  tailBone.rotation.z = tailAngle;
  renderer.render(scene, camera);
});
```

---

## GSAP Integration with Three.js Objects

GSAP can tween any numeric property, including Three.js uniforms, positions, and quaternions:

```javascript
import gsap from 'gsap';

// Basic position tween
gsap.to(mesh.position, {
  y: 2,
  duration: 1.5,
  ease: 'elastic.out(1, 0.4)',
});

// Rotation — use radians
gsap.to(mesh.rotation, {
  y: Math.PI * 2,
  duration: 2,
  ease: 'power2.inOut',
});

// Shader uniform tween
gsap.to(material.uniforms.uProgress, {
  value: 1.0,
  duration: 1.2,
  ease: 'power3.in',
  onUpdate: () => {
    material.needsUpdate = false; // uniforms don't need needsUpdate
  },
});

// Camera animation with timeline
const tl = gsap.timeline({ defaults: { ease: 'power2.inOut', duration: 1.5 } });
tl.to(camera.position, { x: 5, y: 3, z: 8 })
  .to(camera.position, { x: -5, y: 1, z: 5 }, '+=0.5') // 0.5s after previous
  .to(camera.position, { x: 0, y: 2, z: 10 }, '<0.3'); // 0.3s before previous end

// Quaternion tween via fromRotationMatrix (GSAP doesn't natively support quaternions)
const targetQuat = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, Math.PI, 0));
gsap.to({}, {
  duration: 1,
  ease: 'power2.inOut',
  onUpdate: function() {
    camera.quaternion.slerp(targetQuat, this.ratio);
  },
});
```

---

## Particle System Animation via BufferGeometry

GPU-friendly particle system using custom BufferGeometry attributes:

```javascript
const count = 10000;
const positions = new Float32Array(count * 3);
const velocities = new Float32Array(count * 3);
const lifetimes = new Float32Array(count);
const phases = new Float32Array(count); // random phase offset per particle

// Initialize
for (let i = 0; i < count; i++) {
  const i3 = i * 3;
  positions[i3]     = (Math.random() - 0.5) * 20;
  positions[i3 + 1] = Math.random() * 10;
  positions[i3 + 2] = (Math.random() - 0.5) * 20;

  velocities[i3]     = (Math.random() - 0.5) * 0.02;
  velocities[i3 + 1] = Math.random() * 0.05;
  velocities[i3 + 2] = (Math.random() - 0.5) * 0.02;

  lifetimes[i] = Math.random() * 3.0 + 1.0; // 1-4 second lifetime
  phases[i] = Math.random() * Math.PI * 2;
}

const geometry = new THREE.BufferGeometry();
geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
geometry.setAttribute('aVelocity', new THREE.BufferAttribute(velocities, 3));
geometry.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));

const material = new THREE.PointsMaterial({
  size: 0.05,
  sizeAttenuation: true,
  transparent: true,
  alphaTest: 0.001,
  depthWrite: false,
});

const particles = new THREE.Points(geometry, material);
scene.add(particles);

// CPU-side animation (for < 10k particles)
renderer.setAnimationLoop((time) => {
  const t = time * 0.001;
  const pos = geometry.attributes.position.array;
  const vel = geometry.attributes.aVelocity.array;

  for (let i = 0; i < count; i++) {
    const i3 = i * 3;
    pos[i3]     += vel[i3];
    pos[i3 + 1] += vel[i3 + 1];
    pos[i3 + 2] += vel[i3 + 2];

    // Reset when off-screen
    if (pos[i3 + 1] > 10) {
      pos[i3 + 1] = 0;
    }
  }

  geometry.attributes.position.needsUpdate = true;
  renderer.render(scene, camera);
});
```

---

## Anti-Pattern Catalog

### ❌ Calling mixer.update() with Raw Timestamp (Not Delta)

**Detection**:
```bash
grep -rn "mixer\.update" --include="*.js" --include="*.ts"
rg "mixer\.update\(time\)" --type js
```

**What it looks like**:
```javascript
renderer.setAnimationLoop((time) => {
  mixer.update(time); // BAD: time is ms since page load (~120000ms after 2 minutes)
});
```

**Why wrong**: `mixer.update()` expects elapsed seconds since last frame (delta), not absolute timestamp. Passing raw `time` makes animations play at 1000x speed because time is in milliseconds.

**Fix**:
```javascript
const clock = new THREE.Clock();
renderer.setAnimationLoop(() => {
  const delta = clock.getDelta(); // seconds since last call, typically 0.016 at 60fps
  mixer.update(delta);
  renderer.render(scene, camera);
});
```

---

### ❌ Applying Bone Rotation After mixer.update()

**Detection**:
```bash
grep -rn "bone\.rotation\|bone\.quaternion" --include="*.js" --include="*.ts"
```

**What it looks like**:
```javascript
renderer.setAnimationLoop(() => {
  mixer.update(delta); // sets bone transforms from keyframe data
  headBone.rotation.y = mouseTargetY; // immediately overwritten — no effect seen
});
```

**Why wrong**: `mixer.update()` overwrites bone transforms from animation keyframes on the same frame tick. Manual bone changes set before or on the same tick are overwritten.

**Fix**: Apply bone overrides AFTER `mixer.update()` in the same frame:
```javascript
renderer.setAnimationLoop(() => {
  mixer.update(delta);
  // Now override specific bones AFTER the mixer writes
  headBone.rotation.y += (mouseTargetY - headBone.rotation.y) * 0.1;
  renderer.render(scene, camera);
});
```

---

### ❌ Not Disposing Mixer on Component Unmount

**Detection**:
```bash
grep -rn "AnimationMixer" --include="*.js" --include="*.ts"
rg "mixer\." --type js | grep -v "dispose\|update\|stopAll"
```

**What it looks like**:
```javascript
// In a React Three Fiber component:
useEffect(() => {
  const mixer = new THREE.AnimationMixer(scene);
  // No cleanup
}, []);
```

**Why wrong**: `AnimationMixer` holds references to scene objects, preventing GC. Multiple mixers accumulate on route changes.

**Fix**:
```javascript
useEffect(() => {
  const mixer = new THREE.AnimationMixer(scene);
  const action = mixer.clipAction(clip);
  action.play();

  return () => {
    mixer.stopAllAction();
    mixer.uncacheRoot(scene); // releases internal refs
  };
}, []);
```

---

## See Also

- `references/gltf-loading.md` — GLTF model loading, SkeletonUtils.clone, asset manifests
- `references/performance-patterns.md` — InstancedMesh for particle systems at scale
- `references/shader-patterns.md` — GPU-driven animation via vertex shaders
