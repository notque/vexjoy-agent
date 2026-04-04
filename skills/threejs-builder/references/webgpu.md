# WebGPU Three.js Reference

Paradigm-specific reference for building 3D applications with Three.js WebGPU renderer.
Load this file when the project uses `WebGPURenderer`, TSL (Three Shading Language),
node materials, or compute shaders.

**Status**: WebGPU support in Three.js requires r171+ minimum for stable TSL. Target r183+
for full feature set. The API surface is larger than WebGL and requires understanding
node-based materials.

---

## Core Architecture

Three.js WebGPU uses the same scene graph as WebGL but replaces the rendering backend.
The key differences:

| Aspect | WebGL (default) | WebGPU |
|--------|----------------|--------|
| Renderer | `WebGLRenderer` | `WebGPURenderer` |
| Materials | `MeshStandardMaterial` etc. | `MeshStandardNodeMaterial` (node-based) |
| Shaders | GLSL (vertex + fragment) | TSL (Three Shading Language) — JS-authored |
| Compute | Not supported | Compute shaders via `compute()` |
| Performance | Mature, wide support | Better batching, GPU compute, less CPU overhead |
| Browser support | Universal | Chrome 113+, Edge 113+, Firefox (behind flag), Safari (partial) |

### Project Setup

```bash
npm create vite@latest my-webgpu-app -- --template vanilla-ts
cd my-webgpu-app
npm install three
```

### WebGPU Renderer Initialization

```typescript
// IMPORTANT: Import from 'three/webgpu', NOT 'three' — this is the r171+ pattern
import * as THREE from 'three/webgpu'
import { color, time, oscSine } from 'three/tsl'

const renderer = new THREE.WebGPURenderer({ antialias: true })
renderer.setSize(window.innerWidth, window.innerHeight)
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
document.body.appendChild(renderer.domElement)

// CRITICAL: WebGPU requires async initialization
await renderer.init()

// Then proceed with scene setup as normal
const scene = new THREE.Scene()
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000)
```

**Two critical differences from WebGL**:
1. Import from `three/webgpu` not `three` — this gives you `WebGPURenderer` on `THREE` namespace
2. `renderer.init()` is async — the renderer is not ready until the promise resolves. Always `await` it before rendering or adding objects

### Fallback Pattern

```typescript
async function createRenderer() {
  if (navigator.gpu) {
    const renderer = new WebGPURenderer({ antialias: true })
    await renderer.init()
    return renderer
  }
  // Fallback to WebGL
  console.warn('WebGPU not available, falling back to WebGL')
  return new THREE.WebGLRenderer({ antialias: true })
}
```

---

## TSL (Three Shading Language)

TSL replaces GLSL for WebGPU shaders. Instead of writing shader text, you write JavaScript functions that build a shader node graph. This is the biggest paradigm shift.

### Why TSL Over GLSL

- **Cross-backend**: TSL compiles to both WGSL (WebGPU) and GLSL (WebGL) — write once, run on both
- **Type-safe**: Shader logic is JavaScript — you get IDE autocomplete and type checking
- **Composable**: Node functions compose like regular functions, no string concatenation
- **Debuggable**: Errors are JavaScript errors with stack traces, not opaque GLSL compilation errors

### Basic TSL Patterns

```typescript
import {
  uniform, attribute, varying, vec3, vec4, float,
  sin, cos, mul, add, mix, normalize, dot,
  positionLocal, positionWorld, normalLocal, normalWorld,
  uv, time, cameraPosition,
  MeshStandardNodeMaterial
} from 'three/tsl'

// Time-based color animation
const material = new MeshStandardNodeMaterial()
material.colorNode = mix(
  vec3(1.0, 0.0, 0.0),  // red
  vec3(0.0, 0.0, 1.0),  // blue
  sin(mul(time, 0.5)).mul(0.5).add(0.5)  // oscillate 0-1
)
```

### TSL Method Chaining (No Operator Syntax)

TSL uses method chaining, not JavaScript operators. There is no `+`, `-`, `*` syntax for nodes:

```typescript
// CORRECT: method chaining
time.mul(2.0).add(offset).sin().mul(0.5).add(0.5)

// WRONG: JavaScript operators don't work on TSL nodes
time * 2.0 + offset  // Returns NaN or type error
```

### Built-in Oscillators

TSL provides oscillators that return 0-1 range, saving common boilerplate:

```typescript
import { oscSine, oscSquare, oscTriangle, oscSawtooth } from 'three/tsl'

material.colorNode = mix(colorA, colorB, oscSine())  // Smooth sine wave 0-1
// oscSquare — hard on/off toggle
// oscTriangle — linear ramp up and down
// oscSawtooth — linear ramp up, hard reset
```

### TSL Node Types

| Node | Purpose | Example |
|------|---------|---------|
| `uniform(value)` | CPU-controlled value updated per frame | `uniform(0.0)` |
| `attribute(name)` | Vertex attribute access | `attribute('position')` |
| `positionLocal` | Object-space vertex position | Vertex displacement |
| `positionWorld` | World-space vertex position | Distance-based effects |
| `normalLocal` / `normalWorld` | Surface normals (r178+: renamed from `transformedNormal*`) | Lighting calculations |
| `normalView` | View-space normal (r178+: renamed from `transformedNormalView`) | Rim/fresnel effects |
| `uv()` | UV coordinates | Texture mapping |
| `screenUV` | Screen-space UV coordinates | Full-screen effects |
| `screenSize` | Screen dimensions in pixels | Resolution-dependent effects |
| `time` | Elapsed time in seconds | Animation |
| `cameraPosition` | Camera world position | View-dependent effects |
| `instanceIndex` | Current instance ID in compute | Per-instance logic |

### Built-in Effect Functions

TSL includes pre-built effect functions that save significant boilerplate:

```typescript
import { fresnel, triplanarTexture } from 'three/tsl'

// Rim glow — one-liner instead of manual dot/pow calculation
material.emissiveNode = fresnel()  // Bright at edges, dark at center

// Triplanar texture mapping — no UV unwrap needed for organic/terrain shapes
material.colorNode = triplanarTexture(texture(myTexture), null, null, float(1.0))
```

### Auto-Updating Uniforms

Control when uniforms update — avoids unnecessary per-frame updates:

```typescript
const u = uniform(0.0)
u.onFrameUpdate(() => performance.now() * 0.001)   // Update every frame
u.onObjectUpdate((obj) => obj.position.y)            // Update per-object render
u.onRenderUpdate((obj, cam) => cam.position.length()) // Update per render call
```

### CRITICAL: TSL Variable Reassignment Footgun

**This is the #1 source of silent bugs in TSL.** TSL intercepts property assignments on node
objects but CANNOT intercept JavaScript variable reassignment. The result is silently wrong output
with no error message.

```typescript
// BROKEN — TSL can't see JS variable reassignment
let value = buffer.element(index).toFloat()
If(condition, () => {
  value = value.add(1.0)  // Creates new node, JS var reassigns — TSL lost the connection
})
// 'value' now points to an orphaned node. The buffer was never updated.

// CORRECT — Pattern 1: select() for simple conditionals
const result = select(condition, trueVal, falseVal)

// CORRECT — Pattern 2: .toVar() + .assign() for mutable state
const value = buffer.element(index).toFloat().toVar()
If(condition, () => {
  value.assign(value.add(1.0))  // TSL tracks .assign() — buffer IS updated
})

// CORRECT — Pattern 3: Direct .assign() on buffer element
If(condition, () => {
  element.assign(element.add(1.0))
})
```

### TSL Control Flow

```typescript
import { If, Switch, Loop, select } from 'three/tsl'

// Conditional (simple)
const result = select(condition, trueValue, falseValue)

// Conditional (complex, with side effects)
If(condition, () => {
  // true branch — use .assign() for mutations
}).ElseIf(otherCondition, () => {
  // else-if branch
}).Else(() => {
  // else branch
})

// Switch
Switch(integerNode)
  .Case(0, () => { /* handle 0 */ })
  .Case(1, () => { /* handle 1 */ })
  .Default(() => { /* fallback */ })

// Loop
Loop(count, ({ i }) => {
  // i is the iteration index node
})
```

### Noise Functions (MaterialX)

```typescript
import { mx_noise_float, mx_worley_noise, mx_fractal_noise } from 'three/tsl'

// Perlin noise
material.colorNode = mx_noise_float(positionWorld.mul(2.0))

// Cellular/Voronoi noise
material.colorNode = mx_worley_noise(positionWorld.mul(3.0))

// Fractal Brownian Motion (layered noise)
material.colorNode = mx_fractal_noise(positionWorld.mul(1.5))
```

### Raw WGSL Integration

When TSL math is insufficient (complex PBR terms, optimized noise), embed raw WGSL:

```typescript
import { wgslFn, vec3 } from 'three/tsl'

const simplexNoise = wgslFn(`
  fn simplex3d(v: vec3f) -> f32 {
    // Full WGSL implementation here
    return noise_value;
  }
`)

material.colorNode = vec3(simplexNoise(positionWorld), 0.5, 0.5)
```

### Vertex Displacement

```typescript
import { positionLocal, sin, mul, time, normalLocal, float } from 'three/tsl'

const material = new MeshStandardNodeMaterial()

// Wave displacement along normals
const displacement = sin(
  mul(positionLocal.y, float(4.0)).add(mul(time, float(2.0)))
).mul(float(0.2))

material.positionNode = positionLocal.add(
  normalLocal.mul(displacement)
)
```

### Custom Fresnel Effect

```typescript
import {
  normalWorld, cameraPosition, positionWorld,
  normalize, dot, pow, sub, float, vec3, mix
} from 'three/tsl'

const viewDir = normalize(sub(cameraPosition, positionWorld))
const fresnel = pow(sub(float(1.0), dot(normalWorld, viewDir)), float(3.0))

const material = new MeshStandardNodeMaterial()
material.colorNode = mix(
  vec3(0.1, 0.1, 0.3),  // base color
  vec3(0.3, 0.6, 1.0),  // edge color
  fresnel
)
```

---

## Compute Shaders

WebGPU enables GPU compute — parallel processing that runs on the GPU independently from rendering. This is new capability not available in WebGL.

### Use Cases

| Use Case | Why Compute | Alternative |
|----------|-------------|-------------|
| Particle simulation (10k+) | CPU can't update 10k+ positions at 60fps | InstancedMesh with CPU loop (slow at scale) |
| Terrain generation | Procedural generation is embarrassingly parallel | Pre-generate on CPU (slow, no real-time updates) |
| Physics (cloth, fluid) | Constraint solving benefits from GPU parallelism | CPU physics library (Cannon, Rapier) |
| Image processing | Per-pixel operations map perfectly to GPU threads | WebGL shader pass (limited flexibility) |

### Basic Compute Pattern

```typescript
import {
  storageObject, instanceIndex, float, vec3,
  compute, sin, mul, time
} from 'three/tsl'

// Create storage buffer
const count = 10000
const positionBuffer = new THREE.StorageBufferAttribute(
  new Float32Array(count * 3), 3
)

// Define compute function
const computePositions = compute(() => {
  const i = instanceIndex
  const t = time

  // Each GPU thread updates one particle
  const x = sin(mul(float(i), float(0.01)).add(t))
  const y = sin(mul(float(i), float(0.013)).add(mul(t, float(1.3))))
  const z = sin(mul(float(i), float(0.017)).add(mul(t, float(0.7))))

  storageObject(positionBuffer).element(i).assign(vec3(x, y, z))
}, count)  // Dispatch count threads

// In animation loop (synchronous since r181 — computeAsync() is deprecated):
renderer.compute(computePositions)
```

### Storage Buffer Types

| Function | Access | Use Case |
|----------|--------|----------|
| `instancedArray(count, 'vec3')` | Read-write | Particle positions, mutable state |
| `attributeArray(data, 'float')` | Read-only | Input data, lookup tables |

This distinction is often missed — using `instancedArray` for read-only data wastes GPU resources,
and `attributeArray` for write targets silently fails.

### Atomic Operations

For compute shaders that need thread-safe accumulation (counting, finding min/max across threads):

```typescript
import { atomicAdd, atomicMax, atomicMin, atomicStore } from 'three/tsl'

// Thread-safe counter increment
atomicAdd(counterBuffer.element(0), int(1))

// Find maximum value across all threads
atomicMax(resultBuffer.element(0), currentValue)
```

### Workgroup Configuration

```typescript
// Default workgroup size
const shader = compute(fn, count)

// Custom workgroup size — critical for shared memory patterns
const shader = compute(fn, count, [64])  // 64 threads per workgroup

// Workgroup barriers for synchronization
import { workgroupBarrier, storageBarrier, textureBarrier } from 'three/tsl'
workgroupBarrier()   // Sync all threads in workgroup
storageBarrier()     // Ensure storage buffer writes are visible
textureBarrier()     // Ensure texture writes are visible
```

### Device Limits for Large Compute

WebGPU devices use conservative default limits. Large particle systems or buffers silently fail
without explicit limit requests:

```typescript
const renderer = new THREE.WebGPURenderer({
  requiredLimits: {
    maxBufferSize: 1024 * 1024 * 1024,              // 1 GiB (default: 256 MiB)
    maxStorageBufferBindingSize: 1024 * 1024 * 512,  // 512 MiB (default: 128 MiB)
  },
})

// Safe pattern — check adapter limits first:
const adapter = await navigator.gpu.requestAdapter()
const maxBuffer = adapter.limits.maxBufferSize
console.log(`GPU supports up to ${maxBuffer / 1024 / 1024} MiB buffers`)
```

---

## Node Materials Reference

WebGPU node materials extend standard materials with programmable nodes:

### MeshStandardNodeMaterial

The most commonly used — PBR material with customizable nodes.

```typescript
const material = new MeshStandardNodeMaterial({
  color: 0x44aa88,
  metalness: 0.5,
  roughness: 0.3,
})

// Override specific nodes:
material.colorNode = /* TSL expression */        // Surface color
material.normalNode = /* TSL expression */        // Surface normal modification
material.positionNode = /* TSL expression */      // Vertex displacement
material.emissiveNode = /* TSL expression */      // Emissive light
material.opacityNode = /* TSL expression */       // Transparency
material.metalnessNode = /* TSL expression */     // Per-pixel metalness
material.roughnessNode = /* TSL expression */     // Per-pixel roughness
```

### MeshBasicNodeMaterial

Unlit material — useful for UI elements, wireframes, post-processing.

### SpriteNodeMaterial

For particle systems and billboards.

---

## Migration from WebGL

### Drop-in Replacement (Level 1)

Switch renderer only — existing materials continue to work:

```typescript
// Before (WebGL)
const renderer = new THREE.WebGLRenderer({ antialias: true })

// After (WebGPU)
import WebGPURenderer from 'three/webgpu'
const renderer = new WebGPURenderer({ antialias: true })
await renderer.init()
```

Standard Three.js materials (`MeshStandardMaterial`, etc.) work with WebGPU renderer. No code changes needed beyond the renderer swap.

### Node Materials (Level 2)

Replace standard materials with node variants for custom effects:

```typescript
// Before (WebGL GLSL shader)
const material = new THREE.ShaderMaterial({
  vertexShader: '...',
  fragmentShader: '...',
  uniforms: { time: { value: 0 } }
})

// After (WebGPU TSL)
import { MeshStandardNodeMaterial, time, sin, vec3 } from 'three/tsl'
const material = new MeshStandardNodeMaterial()
material.colorNode = vec3(sin(time), 0.5, 0.5)
// No uniform management needed — time is a built-in node
```

### Compute Shaders (Level 3)

Add GPU compute for particle systems, procedural generation, physics. This has no WebGL equivalent — it's new capability.

---

## Performance Patterns

### WebGPU-Specific Optimizations

| Pattern | Benefit |
|---------|---------|
| Use `StorageBufferAttribute` for dynamic data | GPU reads directly, no CPU → GPU copy per frame |
| Batch draw calls with same material | WebGPU already batches better than WebGL, but same-material still helps |
| Use compute shaders for particle updates | 100x faster than CPU loop for 10k+ particles |
| Avoid frequent uniform changes between draw calls | Uniform buffers have binding cost per change |

### When NOT to Use WebGPU

- **Wide browser support needed** — Safari/Firefox support is incomplete
- **Simple scenes** — WebGPU's advantages emerge at scale (many objects, compute, complex shaders)
- **Existing WebGL codebase with GLSL shaders** — migration cost may exceed benefit unless compute is needed
- **Mobile targets** — WebGPU mobile support is limited

---

## Version-Specific Breaking Changes

| Version | Change | Migration |
|---------|--------|-----------|
| r171+ | Minimum for stable TSL | Use `three/webgpu` import path |
| r178+ | `PI2` renamed to `TWO_PI` | Find/replace |
| r178+ | `transformedNormalView` → `normalView` | Find/replace |
| r178+ | `transformedNormalWorld` → `normalWorld` | Find/replace |
| r181+ | `renderer.compute()` is synchronous | Remove `await` from compute calls |
| r181+ | `renderer.computeAsync()` deprecated | Use `renderer.compute()` |
| r183+ | `PostProcessing` replaced by `RenderPipeline` | Use `pass(scene, camera)` + `renderPipeline.outputNode` |

### r183+ Post-Processing with RenderPipeline

The `PostProcessing` class was replaced by `RenderPipeline` in r183. This is a significant API
change that most tutorials and examples haven't caught up with yet.

```typescript
import { pass, RenderPipeline } from 'three/tsl'

// Create render pass
const scenePass = pass(scene, camera)

// Create pipeline and set output
const renderPipeline = new RenderPipeline(renderer)
renderPipeline.outputNode = scenePass

// In animation loop:
renderPipeline.render()
```

---

## Device Loss Recovery

Production apps must handle GPU device loss (driver crash, GPU hang, tab backgrounding):

```typescript
async function initWebGPU() {
  const renderer = new THREE.WebGPURenderer({ antialias: true })
  await renderer.init()

  // Monitor for device loss
  renderer.backend.device.lost.then((info) => {
    console.error(`GPU device lost: ${info.reason}`, info.message)

    if (info.reason === 'destroyed') return  // Intentional, don't recover

    // 'unknown' = driver crash or GPU hang — attempt recovery
    renderer.dispose()
    initWebGPU()  // Re-initialize everything
  })

  return renderer
}

// Testing device loss:
// renderer.backend.device.destroy()  // Programmatic trigger
// Chrome: about:gpucrash for real GPU crash simulation
// Chrome flags for repeated testing (disables crash rate limiting):
//   --disable-domain-blocking-for-3d-apis --disable-gpu-process-crash-limit
```

For production apps, preserve state across recovery using `localStorage` before
`renderer.dispose()`, then restore after re-initialization.

---

## Common Anti-Patterns

### 1. Forgetting Async Init

```typescript
// BAD: Renderer not ready
const renderer = new WebGPURenderer()
renderer.render(scene, camera)  // Fails silently or crashes

// GOOD: Always await init
const renderer = new WebGPURenderer()
await renderer.init()
renderer.render(scene, camera)
```

### 2. Importing from 'three' Instead of 'three/webgpu'

```typescript
// BAD: Missing WebGPU-specific exports
import * as THREE from 'three'

// GOOD: Full WebGPU namespace (r171+)
import * as THREE from 'three/webgpu'
import { color, time } from 'three/tsl'
```

### 3. TSL Variable Reassignment (Silent Data Corruption)

See the detailed explanation in the TSL section above. This is the single most common
source of silent bugs. Use `.toVar()` + `.assign()`, never `let x = ...; x = x.add(1)`.

### 4. Using GLSL ShaderMaterial with WebGPU

```typescript
// BAD: GLSL doesn't work with WebGPU renderer
const material = new THREE.ShaderMaterial({
  vertexShader: '...',  // GLSL — not compatible
  fragmentShader: '...',
})

// GOOD: Use TSL node materials
const material = new MeshStandardNodeMaterial()
material.colorNode = /* TSL expression */
```

### 5. CPU-Side Particle Updates at Scale

```typescript
// BAD: Updating 10k particles on CPU every frame
for (let i = 0; i < 10000; i++) {
  particles[i].position.x += Math.sin(time + i) * 0.01
}
instancedMesh.instanceMatrix.needsUpdate = true  // Full CPU→GPU upload

// GOOD: Use compute shader
renderer.compute(particleComputeFunction)  // GPU-only, no CPU→GPU transfer
```

---

## Error Handling

### Error: "navigator.gpu is undefined"
Cause: Browser doesn't support WebGPU, or not using HTTPS
Solution: Add fallback to WebGL renderer. WebGPU requires HTTPS in production.

### Error: "WebGPU: Adapter request failed"
Cause: GPU hardware or driver not supported
Solution: Check `navigator.gpu.requestAdapter()` returns non-null before proceeding.

### Error: TSL node type mismatch
Cause: Mixing incompatible node types (e.g., `float` + `vec3`)
Solution: TSL is strictly typed. Ensure operations match: `vec3 * float` works, `vec3 + float` does not — use `vec3.add(float(x))`.

### Error: Compute shader produces no visible result
Cause: Storage buffer not connected to rendering, or compute dispatch count is wrong
Solution: Verify the storage buffer is used as a geometry attribute AND the compute dispatch matches buffer element count.
