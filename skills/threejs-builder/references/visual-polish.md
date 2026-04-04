# Visual Polish Reference

Cross-paradigm techniques that make Three.js scenes look impressive rather than basic.
Load this file alongside the paradigm-specific reference when the user wants high visual
quality, or when the context is a portfolio, game, showcase, or anything meant to impress.

These techniques apply to imperative Three.js, React Three Fiber, and WebGPU — the code
examples use imperative syntax but the principles and parameter values transfer directly.
For R3F equivalents, wrap in JSX components (e.g., `<directionalLight intensity={3.6} />`).

---

## The Biggest Single Quality Jump: HDR Environment

Adding an HDR environment map is the single most impactful change you can make. It provides
realistic reflections AND ambient lighting in one step. A scene with HDR environment looks
professional; without it, metallic and glossy surfaces look flat and lifeless.

```javascript
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js'

const rgbeLoader = new RGBELoader()
rgbeLoader.load('environment.hdr', (texture) => {
  texture.mapping = THREE.EquirectangularReflectionMapping
  scene.background = texture       // Visible background
  scene.environment = texture      // Reflection source for all PBR materials
})

// Fine-tune without changing the HDR file:
scene.backgroundBlurriness = 0.3   // 0-1: soften background without killing reflections
scene.backgroundIntensity = 0.8    // 0-3: dim/brighten background independently
// Per-material override:
material.envMapIntensity = 1.5     // Boost reflections on specific objects
```

**R3F equivalent** (drei):
```tsx
import { Environment } from '@react-three/drei'
<Environment preset="city" background backgroundBlurriness={0.3} />
// Available presets: apartment, city, dawn, forest, lobby, night, park, studio, sunset, warehouse
```

**Free HDR sources**: Poly Haven (polyhaven.com/hdris) — CC0, production quality, multiple resolutions.

---

## PBR Material Recipes

Specific parameter values that produce convincing real-world materials. These are tested
combinations — don't guess at roughness/metalness values.

### Metal Surfaces

```javascript
// Gold
const gold = new THREE.MeshStandardMaterial({
  color: 0xfbbf24,
  roughness: 0.15,
  metalness: 0.95,
})

// Brushed steel
const steel = new THREE.MeshStandardMaterial({
  color: 0x888888,
  roughness: 0.35,
  metalness: 0.9,
})

// Chrome (mirror)
const chrome = new THREE.MeshStandardMaterial({
  color: 0xffffff,
  roughness: 0.05,
  metalness: 1.0,
})
```

### Glass and Transparent Materials

```javascript
// Glass (MeshPhysicalMaterial for transmission)
const glass = new THREE.MeshPhysicalMaterial({
  transmission: 0.95,    // 0-1: how see-through
  ior: 1.45,             // Index of refraction (glass ~1.5, water ~1.33, diamond ~2.42)
  thickness: 0.5,        // Simulated thickness for refraction
  roughness: 0.05,
  clearcoat: 1.0,
  clearcoatRoughness: 0.1,
  attenuationColor: new THREE.Color(0xa855f7),  // Tinted glass color
  attenuationDistance: 0.5,
})
```

### Special Surface Effects

```javascript
// Iridescent (oil slick, soap bubble, beetle shell)
const iridescent = new THREE.MeshPhysicalMaterial({
  iridescence: 1.0,
  iridescenceIOR: 1.8,
  iridescenceThicknessRange: [100, 800],  // nm — controls color shift range
  metalness: 0.8,
  roughness: 0.15,
})

// Fabric/velvet (sheen)
const fabric = new THREE.MeshPhysicalMaterial({
  color: 0x2244aa,
  sheen: 1.0,
  sheenRoughness: 0.3,
  sheenColor: new THREE.Color(0xff88cc),
  roughness: 0.8,
})

// Toon/cel-shading
const toon = new THREE.MeshToonMaterial({
  color: 0x44aa88,
  // gradientMap: fiveToneTexture  // Load from threejs.org's fiveTone.jpg with NearestFilter
})
```

---

## Dramatic Lighting Setup

Default Three.js lighting (single ambient + directional) produces flat, boring results.
Professional-looking scenes use a three-point lighting setup with specific intensity values.

### Three-Point Lighting Recipe

```javascript
// 1. Key light (warm, main shadow caster) — the dominant light
const keyLight = new THREE.DirectionalLight(0xfff0dd, 3.6)
keyLight.position.set(3.8, 5.6, 3.5)
keyLight.castShadow = true
keyLight.shadow.mapSize.set(2048, 2048)
keyLight.shadow.bias = -0.0008  // Prevents shadow acne without detaching
scene.add(keyLight)

// 2. Fill light (cool, opposite side) — softens harsh shadows
const fillLight = new THREE.DirectionalLight(0xaaccff, 0.8)
fillLight.position.set(-4, 3, -2)
scene.add(fillLight)

// 3. Rim/back light — separates objects from background
const rimLight = new THREE.SpotLight(0xff8844, 42)  // SpotLights need higher intensity
rimLight.position.set(-2, 4, -5)
rimLight.penumbra = 0.4   // Soft edge falloff
rimLight.decay = 1.5
rimLight.angle = Math.PI / 6
scene.add(rimLight)

// 4. Ambient fill — prevents pure black in shadow areas
const ambientLight = new THREE.AmbientLight(0x404060, 0.3)
scene.add(ambientLight)
```

**Intensity calibration** (physically-based, r155+):
- DirectionalLight: 1-5 range for primary lights
- PointLight: ~26 to match equivalent directional
- SpotLight: ~42 to match equivalent directional
- AmbientLight: 0.1-0.5 (too high flattens everything)

### Tone Mapping

Always set tone mapping — it compresses HDR values into displayable range and adds cinematic feel:

```javascript
renderer.toneMapping = THREE.ACESFilmicToneMapping  // Best general-purpose
renderer.toneMappingExposure = 1.0  // Adjust brightness
// Other options: ReinhardToneMapping (softer), CineonToneMapping (film-like)
```

---

## Post-Processing Stack

Post-processing is what separates "tech demo" from "polished product." The pass ordering matters.

### Required Pass Order

```
RenderPass → SSAO → UnrealBloomPass → Color Grading → Film Grain → OutputPass
```

Earlier passes operate on HDR data. Later passes operate on the combined image. Getting the order
wrong produces subtle visual artifacts (bloom applied to SSAO halos, grain affecting bloom, etc.).

### Imperative Setup

```javascript
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js'
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js'

const composer = new EffectComposer(renderer)
composer.addPass(new RenderPass(scene, camera))

// Bloom — sweet spot values for subtle, not blown-out glow
const bloomPass = new UnrealBloomPass(
  new THREE.Vector2(window.innerWidth, window.innerHeight),
  0.15,  // strength — keep LOW for subtlety (0.1-0.3 for accents, 1.0+ for neon)
  0.4,   // radius — blur spread
  0.8    // threshold — only bloom values above this (0.8 = only bright things glow)
)
composer.addPass(bloomPass)

composer.addPass(new OutputPass())  // Always last — handles tone mapping + color space

// In animation loop: replace renderer.render() with composer.render()
```

### Selective Bloom (Advanced)

The default bloom haloes everything bright. For selective bloom (only specific objects glow):

1. Create a second scene with only emissive objects
2. Render and bloom that scene separately
3. Composite the bloom layer back onto the main render

This prevents UI elements, white surfaces, and bright materials from getting unwanted halos.

### Bloom + Emissive Materials

For bloom to work on emissive materials, two things must be true:
1. `emissiveIntensity` must be > 1.0 (HDR value, above the bloom threshold)
2. `toneMapped: false` on the material — otherwise the renderer clamps values to [0,1] before bloom sees them

```javascript
const glowMaterial = new THREE.MeshStandardMaterial({
  color: 0xff6600,
  emissive: 0xff6600,
  emissiveIntensity: 3.0,  // Must exceed bloom threshold
  toneMapped: false,        // CRITICAL for bloom pickup
})
```

---

## Shadow Quality

### Soft Shadows

```javascript
renderer.shadowMap.enabled = true
renderer.shadowMap.type = THREE.VSMShadowMap  // Variance Shadow Map — softest edges

// On the shadow-casting light:
light.shadow.mapSize.set(2048, 2048)  // 2048 for quality, 1024 for performance
light.shadow.blurSamples = 25         // VSM blur quality
light.shadow.radius = 15              // VSM blur spread
light.shadow.normalBias = 0.02        // Prevents acne without detaching shadows
```

### Contact Shadows (R3F)

```tsx
import { ContactShadows } from '@react-three/drei'
<ContactShadows
  position={[0, -0.5, 0]}
  opacity={0.4}
  blur={2}
  far={4}
  resolution={256}
/>
```

---

## Camera Systems for Games

| Control Type | Use Case | Import |
|-------------|----------|--------|
| `OrbitControls` | Model viewers, inspection | `three/addons/controls/OrbitControls.js` |
| `PointerLockControls` | First-person games | `three/addons/controls/PointerLockControls.js` |
| `FlyControls` | Free flight, level editors | `three/addons/controls/FlyControls.js` |
| Cinematic path | Cutscenes, tours | `THREE.CatmullRomCurve3` + `getPointAt(t)` |

### Cinematic Camera Path

```javascript
const path = new THREE.CatmullRomCurve3([
  new THREE.Vector3(-10, 5, 10),
  new THREE.Vector3(0, 8, 0),
  new THREE.Vector3(10, 3, -10),
  new THREE.Vector3(0, 5, 0),
], true)  // true = closed loop

// In animation loop:
const t = (time * 0.0001) % 1  // 0-1 along path
const pos = path.getPointAt(t)
const lookAt = path.getPointAt((t + 0.01) % 1)
camera.position.copy(pos)
camera.lookAt(lookAt)
```

---

## Particle Effects

### Simple Particle System (Imperative)

```javascript
const count = 5000
const geometry = new THREE.BufferGeometry()
const positions = new Float32Array(count * 3)
const colors = new Float32Array(count * 3)

for (let i = 0; i < count; i++) {
  positions[i * 3] = (Math.random() - 0.5) * 20
  positions[i * 3 + 1] = Math.random() * 10
  positions[i * 3 + 2] = (Math.random() - 0.5) * 20
  colors[i * 3] = Math.random()
  colors[i * 3 + 1] = Math.random() * 0.5 + 0.5
  colors[i * 3 + 2] = 1.0
}

geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

const material = new THREE.PointsMaterial({
  size: 0.05,
  vertexColors: true,
  transparent: true,
  opacity: 0.8,
  blending: THREE.AdditiveBlending,  // Particles add light — key for glow effect
  depthWrite: false,                 // Prevents sorting artifacts
})

const particles = new THREE.Points(geometry, material)
scene.add(particles)
```

### R3F Shortcut (Drei)

```tsx
import { Sparkles, Stars } from '@react-three/drei'

<Sparkles count={200} scale={10} size={2} speed={0.4} />
<Stars radius={100} depth={50} count={5000} factor={4} fade speed={1} />
```

---

## Animation Polish

### AnimationMixer with Crossfade

For character animation (walk cycles, idle, run), blend between clips smoothly:

```javascript
const mixer = new THREE.AnimationMixer(model)
const idleAction = mixer.clipAction(idleClip)
const walkAction = mixer.clipAction(walkClip)

// Crossfade from idle to walk over 0.3 seconds
idleAction.crossFadeTo(walkAction, 0.3, true)
walkAction.play()

// In animation loop:
mixer.update(delta)
```

**Morph targets** for facial expressions or shape deformations:
```javascript
mesh.morphTargetInfluences[0] = Math.sin(time) * 0.5 + 0.5  // Blend 0-1
```

**Additive animation layers** for breathing on top of other animations:
```javascript
breathAction.setEffectiveWeight(0.3)
breathAction.blendMode = THREE.AdditiveAnimationBlendMode
breathAction.play()
```

---

## Additional Post-Processing Effects

Beyond bloom, these passes add cinematic quality:

```javascript
import { FilmPass } from 'three/addons/postprocessing/FilmPass.js'
import { OutlinePass } from 'three/addons/postprocessing/OutlinePass.js'
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js'
import { FXAAShader } from 'three/addons/shaders/FXAAShader.js'

// Film grain — adds texture, reduces "CG look"
const filmPass = new FilmPass(0.35, false)  // intensity, grayscale
composer.addPass(filmPass)

// Outline — highlight selected/hovered objects
const outlinePass = new OutlinePass(
  new THREE.Vector2(window.innerWidth, window.innerHeight),
  scene, camera
)
outlinePass.edgeStrength = 3
outlinePass.edgeGlow = 0.5
outlinePass.edgeThickness = 1
outlinePass.selectedObjects = [highlightedMesh]
composer.addPass(outlinePass)

// FXAA anti-aliasing (cheaper than MSAA, applied as post-pass)
const fxaaPass = new ShaderPass(FXAAShader)
fxaaPass.uniforms['resolution'].value.set(1 / window.innerWidth, 1 / window.innerHeight)
composer.addPass(fxaaPass)
```

**Pass ordering reminder**: `RenderPass` → `SSAO` → `UnrealBloomPass` → `OutlinePass` → color grading → `FilmPass` → `FXAA` → `OutputPass`

---

## Performance Optimization Techniques

### BatchedMesh (Varied Geometries, One Draw Call)

Unlike `InstancedMesh` (identical objects), `BatchedMesh` batches different geometries:

```javascript
const batchedMesh = new THREE.BatchedMesh(100, 5000, 10000, material)
const boxId = batchedMesh.addGeometry(new THREE.BoxGeometry(1, 1, 1))
const sphereId = batchedMesh.addGeometry(new THREE.SphereGeometry(0.5))

// Add instances of different geometries
for (let i = 0; i < 50; i++) {
  const instanceId = batchedMesh.addInstance(i % 2 === 0 ? boxId : sphereId)
  batchedMesh.setMatrixAt(instanceId, matrix)
}
scene.add(batchedMesh)
```

### LOD (Level of Detail)

Switch to simpler geometry at distance — critical for large scenes:

```javascript
const lod = new THREE.LOD()
lod.addLevel(highDetailMesh, 0)    // Full detail when close
lod.addLevel(mediumDetailMesh, 50) // Simpler at 50 units
lod.addLevel(lowDetailMesh, 200)   // Minimal at 200 units
scene.add(lod)
```

### Asset Compression

| Technique | What It Does | Import |
|-----------|-------------|--------|
| KTX2/Basis | GPU-compressed textures (4-8x smaller, decoded on GPU) | `KTX2Loader` from `three/addons/loaders/KTX2Loader.js` |
| Draco | Compressed GLTF geometry (60-90% smaller meshes) | `DRACOLoader` from `three/addons/loaders/DRACOLoader.js` |
| meshopt | Alternative mesh compression (better for animation) | `MeshoptDecoder` |

```javascript
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js'
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js'

// Draco for GLTF geometry
const dracoLoader = new DRACOLoader()
dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/')
gltfLoader.setDRACOLoader(dracoLoader)

// KTX2 for textures
const ktx2Loader = new KTX2Loader()
ktx2Loader.setTranscoderPath('https://unpkg.com/three@0.160.0/examples/jsm/libs/basis/')
ktx2Loader.detectSupport(renderer)
```

---

## Spatial Audio

For immersive 3D scenes and games:

```javascript
const listener = new THREE.AudioListener()
camera.add(listener)

const sound = new THREE.PositionalAudio(listener)
const audioLoader = new THREE.AudioLoader()
audioLoader.load('sound.mp3', (buffer) => {
  sound.setBuffer(buffer)
  sound.setRefDistance(10)    // Distance at which volume starts falling off
  sound.setRolloffFactor(1)  // How quickly volume decreases with distance
  sound.setLoop(true)
  sound.play()
})

// Attach to an object — sound follows it in 3D space
soundEmitter.add(sound)
```

---

## Special Effects

### Clipping Planes (Portals, Cutaways, Reveals)

```javascript
const clipPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 1)  // Normal + distance

const material = new THREE.MeshStandardMaterial({
  color: 0x44aa88,
  clippingPlanes: [clipPlane],  // Per-material clipping
  clipShadows: true,
})

renderer.clippingPlanes = [clipPlane]  // Or global clipping
renderer.localClippingEnabled = true   // Required for per-material clipping

// Animate the clip plane for a reveal effect:
// clipPlane.constant += delta * 2
```

---

## Quick Polish Checklist

Before delivering any Three.js scene, verify these in order:

1. **Tone mapping set** — `ACESFilmicToneMapping` prevents washed-out colors
2. **DPR capped** — `Math.min(devicePixelRatio, 2)` prevents 4K mobile GPU meltdown
3. **At least 2 light sources** — single light = flat; 3-point = dramatic
4. **Shadows enabled** if ground plane exists — floating objects look wrong
5. **Resize handler** — test at 3 different viewport sizes
6. **Background is not default** — black `#000` or gradient or HDR environment
7. **Antialiasing on** — `{ antialias: true }` on renderer
8. **Post-processing** if emissive materials — bloom makes glow visible
9. **No console errors** — check browser devtools
10. **Animation uses delta/time** — not fixed increments (breaks on high-refresh displays)
