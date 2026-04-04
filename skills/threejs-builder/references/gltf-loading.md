# GLTF Loading Reference

Patterns for loading, cloning, centering, and rigging GLTF/GLB models in Three.js.
Load this file when the project involves `.glb` files, GLTF model import, animated characters,
or skeletal rigs.

---

## Coordinate System Contract

Three.js is **right-handed**: +X right, +Y up, +Z toward the camera.

GLTF's default forward direction is **-Z** (away from camera). A model exported facing
"forward" in Blender will face away from you in Three.js without correction.

**Fix: 180° Y-axis rotation on the loaded scene root.**

```javascript
loader.load('character.glb', (gltf) => {
  const model = gltf.scene
  model.rotation.y = Math.PI  // 180° — face toward camera
  scene.add(model)
})
```

This is the #1 cause of "model faces wrong direction" bugs. Apply it by default for
character and prop models. Do NOT apply it for environment meshes or terrain (those
are authored to match the scene coordinate system).

---

## Basic GLTF Load

```javascript
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'

const loader = new GLTFLoader()

loader.load(
  'path/to/model.glb',
  (gltf) => {
    const model = gltf.scene
    model.rotation.y = Math.PI   // Face camera (see coordinate system above)
    scene.add(model)

    // If animated:
    const mixer = new THREE.AnimationMixer(model)
    gltf.animations.forEach((clip) => {
      mixer.clipAction(clip).play()
    })
  },
  (progress) => {
    const pct = (progress.loaded / progress.total * 100).toFixed(1)
    console.log(`Loading: ${pct}%`)
  },
  (error) => {
    console.error('GLTF load error:', error)
  }
)
```

---

## Model Caching: Load Once, Clone Many

A GLTF scene object can only exist **once** in the scene graph. Adding the same
`gltf.scene` to two different parents silently removes it from the first.

**Pattern**: Load once into a cache, clone for each instance.

```javascript
const modelCache = new Map()

async function loadModel(path) {
  if (modelCache.has(path)) {
    return modelCache.get(path)
  }
  return new Promise((resolve, reject) => {
    loader.load(path, (gltf) => {
      modelCache.set(path, gltf)
      resolve(gltf)
    }, undefined, reject)
  })
}

// Later — clone for each character instance:
const gltf = await loadModel('character.glb')
const instance = SkeletonUtils.clone(gltf.scene)  // NOT gltf.scene.clone() — see below
instance.rotation.y = Math.PI
scene.add(instance)
```

---

## SkeletonUtils.clone() — Critical for Animated Models

`Object3D.clone()` breaks skeleton bindings. Cloned animated models will freeze in
**T-pose** because the clone's skinned mesh still points to the original skeleton's bones.

**Always use `SkeletonUtils.clone()` for animated models.**

```javascript
import { SkeletonUtils } from 'three/addons/utils/SkeletonUtils.js'

// WRONG — T-pose on all clones:
const badClone = gltf.scene.clone()

// CORRECT — preserves bone bindings:
const goodClone = SkeletonUtils.clone(gltf.scene)
```

For non-animated (static) models, `object.clone()` is fine.

**Full clone + animate pattern**:

```javascript
async function spawnCharacter(position) {
  const gltf = await loadModel('character.glb')
  const clone = SkeletonUtils.clone(gltf.scene)

  clone.rotation.y = Math.PI
  clone.position.copy(position)
  scene.add(clone)

  // Each clone needs its own AnimationMixer
  const mixer = new THREE.AnimationMixer(clone)
  const idleClip = THREE.AnimationClip.findByName(gltf.animations, 'Idle')
  if (idleClip) mixer.clipAction(idleClip).play()

  return { model: clone, mixer }
}
```

---

## Auto-Centering and Camera Fitting

Models exported from different tools have wildly different scales and origins.
Always compute the bounding box and fit the camera to it.

```javascript
loader.load('model.glb', (gltf) => {
  const model = gltf.scene
  scene.add(model)

  // Step 1: Compute bounding box
  const box = new THREE.Box3().setFromObject(model)
  const center = box.getCenter(new THREE.Vector3())
  const size = box.getSize(new THREE.Vector3())

  // Step 2: Center model at world origin
  model.position.sub(center)

  // Step 3: Fit camera — distance = longest dimension * 1.5
  const maxDim = Math.max(size.x, size.y, size.z)
  camera.position.set(0, maxDim * 0.5, maxDim * 1.5)
  camera.lookAt(0, 0, 0)

  // Update OrbitControls target if present
  if (controls) {
    controls.target.set(0, 0, 0)
    controls.update()
  }
})
```

**Common mistake**: calling `setFromObject` before adding to scene. The bounding box
uses world-space transforms, so add the model first.

---

## Bone Hierarchy: Attaching Objects to Bones

For weapons, accessories, or anything that should follow a character's animation,
find the bone by name and attach the object as a child.

```javascript
function attachToSkeleton(model, boneName, attachment) {
  let targetBone = null

  model.traverse((node) => {
    if (node.isBone && node.name === boneName) {
      targetBone = node
    }
  })

  if (!targetBone) {
    console.warn(`Bone "${boneName}" not found. Available bones:`)
    model.traverse((node) => {
      if (node.isBone) console.warn(' -', node.name)
    })
    return
  }

  targetBone.add(attachment)

  // Offset attachment relative to bone origin — adjust per model
  attachment.position.set(0, 0, 0.1)
  attachment.rotation.set(0, 0, 0)
}

// Usage:
const sword = await loadModel('sword.glb')
attachToSkeleton(character, 'mixamorig:RightHand', sword.scene)
```

**Bone naming conventions**:
- Mixamo rigs: `mixamorig:Hips`, `mixamorig:RightHand`, `mixamorig:Head`
- Blender default: `hand.R`, `hand.L`, `spine.001`
- Custom rigs: varies — log all bones with the warning branch above when debugging

---

## Asset Manifest Pattern

For games with many models, define a central manifest instead of hardcoding paths:

```json
// assets/manifest.json
{
  "characters": {
    "Warrior": "models/characters/warrior.glb",
    "Mage": "models/characters/mage.glb",
    "Archer": "models/characters/archer.glb"
  },
  "props": {
    "Sword": "models/props/sword.glb",
    "Chest": "models/props/chest.glb"
  },
  "environment": {
    "TreePine": "models/env/tree_pine.glb",
    "Rock": "models/env/rock.glb"
  }
}
```

```javascript
class AssetManager {
  constructor() {
    this.loader = new GLTFLoader()
    this.cache = new Map()
    this.manifest = null
  }

  async init(manifestPath = 'assets/manifest.json') {
    const response = await fetch(manifestPath)
    this.manifest = await response.json()
  }

  async load(category, name) {
    const key = `${category}/${name}`
    if (this.cache.has(key)) return this.cache.get(key)

    const path = this.manifest[category]?.[name]
    if (!path) throw new Error(`Asset not found in manifest: ${key}`)

    return new Promise((resolve, reject) => {
      this.loader.load(path, (gltf) => {
        this.cache.set(key, gltf)
        resolve(gltf)
      }, undefined, reject)
    })
  }

  spawnInstance(category, name) {
    const gltf = this.cache.get(`${category}/${name}`)
    if (!gltf) throw new Error(`Asset not cached: ${category}/${name} — call load() first`)
    return SkeletonUtils.clone(gltf.scene)
  }
}

// Usage:
const assets = new AssetManager()
await assets.init()
await assets.load('characters', 'Warrior')
const warrior1 = assets.spawnInstance('characters', 'Warrior')
const warrior2 = assets.spawnInstance('characters', 'Warrior')  // Second clone, same GLB
```

---

## Error Handling

### Model loads but is invisible

Cause: Model is too small, too large, or centered far from origin.
Solution: Always run auto-centering. Log `size` to diagnose:
```javascript
const size = box.getSize(new THREE.Vector3())
console.log('Model size:', size)  // Tiny values = scale issue, huge = unit mismatch
```

### Model faces wrong direction

Cause: GLTF -Z forward vs Three.js +Z-toward-camera.
Solution: `model.rotation.y = Math.PI` on the scene root after load.

### Cloned character stuck in T-pose

Cause: Used `.clone()` on an animated model — skeleton bindings broken.
Solution: Replace with `SkeletonUtils.clone()` from `three/addons/utils/SkeletonUtils.js`.

### Animations don't play on clone

Cause: `AnimationMixer` created for original model, not the clone.
Solution: Each clone needs its own `new THREE.AnimationMixer(clone)`.

### Bone attachment not following animation

Cause: Object attached to the scene root, not to the bone node.
Solution: Use `traverse` to find the bone by `node.isBone && node.name === boneName`,
then attach to `targetBone` directly.

### Load progress never reaches 100%

Cause: `progress.total` is 0 on servers that omit Content-Length headers.
Solution: Guard against division by zero:
```javascript
const pct = progress.total ? (progress.loaded / progress.total * 100) : 0
```
