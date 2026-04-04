# React Three Fiber (R3F) Reference

Paradigm-specific reference for building 3D applications with React Three Fiber.
Load this file when the project uses `@react-three/fiber`, Drei, or any React-based 3D setup.

---

## Core Architecture

R3F wraps Three.js in a declarative React layer. Every Three.js object becomes a JSX element.
The mental model shift: you don't call `new THREE.Mesh()` — you render `<mesh>`.

### Project Setup

```bash
npm create vite@latest my-3d-app -- --template react-ts
cd my-3d-app
npm install three @react-three/fiber @react-three/drei
npm install -D @types/three
```

**Key packages and when to use them:**

| Package | Purpose | Always Install? |
|---------|---------|-----------------|
| `three` | Core Three.js | Yes |
| `@react-three/fiber` | React renderer for Three.js | Yes |
| `@react-three/drei` | Helper components (OrbitControls, Text, Environment, etc.) | Yes — almost always needed |
| `@react-three/postprocessing` | Post-processing effects (Bloom, SSAO, etc.) | When effects needed |
| `zustand` | State management for game/interactive state | When complex state needed |
| `leva` | Debug GUI controls | During development |
| `@react-three/rapier` | Physics (Rapier WASM) | When physics needed |

### Canvas Component

Every R3F app starts with `<Canvas>`, which creates the WebGL renderer, scene, and default camera:

```tsx
import { Canvas } from '@react-three/fiber'

function App() {
  return (
    <Canvas
      camera={{ position: [0, 2, 5], fov: 50 }}
      gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
      shadows
    >
      <Scene />
    </Canvas>
  )
}
```

**Canvas props that matter:**
- `camera` — set position and fov here, not inside the scene (avoids re-creation on re-render)
- `gl` — renderer options; `antialias: true` and tone mapping are common defaults
- `shadows` — enables shadow maps (still need `castShadow`/`receiveShadow` on objects)
- `dpr` — device pixel ratio; `[1, 2]` caps at 2x for performance
- `frameloop="demand"` — only render when state changes (for static scenes or manual invalidation)

---

## Component Patterns

### Basic Mesh

```tsx
function Box({ position }: { position: [number, number, number] }) {
  const meshRef = useRef<THREE.Mesh>(null!)

  useFrame((state, delta) => {
    meshRef.current.rotation.x += delta
  })

  return (
    <mesh ref={meshRef} position={position}>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color="orange" />
    </mesh>
  )
}
```

**Key pattern**: geometry and material are children of `<mesh>`, not props. The `args` prop maps to constructor arguments. `<boxGeometry args={[1, 1, 1]} />` = `new THREE.BoxGeometry(1, 1, 1)`.

### Lighting Setup

```tsx
function Lighting() {
  return (
    <>
      <ambientLight intensity={0.4} />
      <directionalLight
        position={[10, 10, 5]}
        intensity={1}
        castShadow
        shadow-mapSize={[2048, 2048]}
      />
    </>
  )
}
```

**R3F dash notation**: `shadow-mapSize` sets `light.shadow.mapSize`. This works for any nested property: `position-x={5}` sets `mesh.position.x = 5`.

---

## Camera Controls — The #1 R3F Pitfall

This is the most common source of bugs in R3F projects. OrbitControls and custom camera controllers **conflict silently** — both try to update the camera every frame, causing jitter, locked cameras, or unexpected behavior.

### Decision Tree

```
Do you need the user to orbit/pan/zoom freely?
  YES → Use OrbitControls from drei
  NO → Does the camera follow a target or path?
    YES → Use useFrame + refs for custom camera
    NO → Set camera position on <Canvas> and leave it static
```

### OrbitControls (user-controlled camera)

```tsx
import { OrbitControls } from '@react-three/drei'

// Inside Canvas:
<OrbitControls
  enableDamping
  dampingFactor={0.05}
  minDistance={2}
  maxDistance={20}
  maxPolarAngle={Math.PI / 2}  // Prevent looking below ground
/>
```

**When to use**: Product viewers, 3D model inspectors, sandbox scenes where the user explores freely.

### Custom Camera Controller (app-controlled camera)

```tsx
function CameraController({ target }: { target: THREE.Vector3 }) {
  useFrame((state) => {
    // Smoothly move camera to follow target
    state.camera.position.lerp(
      new THREE.Vector3(target.x, target.y + 5, target.z + 10),
      0.05
    )
    state.camera.lookAt(target)
  })
  return null
}
```

**When to use**: Games, guided experiences, cinematic sequences, any scene where the app decides camera position.

### NEVER Do This

```tsx
// BAD: OrbitControls + custom camera = conflict
<OrbitControls />
<CameraController target={playerPos} />
```

Both components write to the camera every frame. OrbitControls overwrites the custom position, or vice versa, depending on execution order. The result is a frozen or jittering camera. **Pick one approach per scene.**

If you need both (e.g., orbit in menu, follow in gameplay), conditionally render only one:

```tsx
{gameState === 'menu' ? <OrbitControls /> : <CameraController target={playerPos} />}
```

---

## useFrame — The Animation Loop

`useFrame` is R3F's equivalent of `requestAnimationFrame`. It runs every frame inside the React reconciler.

```tsx
useFrame((state, delta) => {
  // state.clock — THREE.Clock
  // state.camera — the active camera
  // state.mouse — normalized mouse position [-1, 1]
  // state.scene — the THREE.Scene
  // delta — time since last frame in seconds
  meshRef.current.rotation.y += delta * 0.5
})
```

### useFrame Rules

| Do | Don't | Why |
|----|-------|-----|
| Mutate refs (`meshRef.current.rotation.y += delta`) | Set React state (`setPosition(...)`) | State triggers re-render; refs don't. Re-renders in useFrame = 60 re-renders/sec = frozen app |
| Use `delta` for time-based animation | Use fixed increments (`+= 0.01`) | Fixed increments run faster on high-refresh displays |
| Create vectors/objects outside useFrame | Create `new THREE.Vector3()` inside useFrame | Allocations inside the loop cause GC pauses every few seconds |
| Access `state.clock.elapsedTime` for absolute time | Track your own timer | The clock is already there and synchronized |

### Pre-allocating Vectors

```tsx
// GOOD: allocate once, reuse in frame loop
const tempVec = useMemo(() => new THREE.Vector3(), [])

useFrame(() => {
  tempVec.set(target.x, target.y + 2, target.z + 5)
  meshRef.current.position.lerp(tempVec, 0.1)
})
```

```tsx
// BAD: allocates every frame (60 allocations/sec)
useFrame(() => {
  const targetPos = new THREE.Vector3(target.x, target.y + 2, target.z + 5)
  meshRef.current.position.lerp(targetPos, 0.1)
})
```

---

## Post-Processing

R3F post-processing uses `@react-three/postprocessing`, which wraps the `postprocessing` library (not Three.js's built-in EffectComposer — the `postprocessing` npm package is significantly more performant).

### Setup

```bash
npm install @react-three/postprocessing postprocessing
```

### Bloom (Makes Emissive Materials Glow)

Bloom is what makes emissive materials actually visible as glowing. Without bloom, `emissiveIntensity` just makes the surface brighter — it doesn't produce the glow halo effect.

```tsx
import { EffectComposer, Bloom } from '@react-three/postprocessing'

function Effects() {
  return (
    <EffectComposer>
      <Bloom
        luminanceThreshold={0.9}
        luminanceSmoothing={0.025}
        intensity={1.5}
        mipmapBlur
      />
    </EffectComposer>
  )
}

// Material that glows:
<meshStandardMaterial
  color="#ff6600"
  emissive="#ff6600"
  emissiveIntensity={2}
  toneMapped={false}  // Required for bloom to pick up the HDR value
/>
```

**Critical**: `toneMapped={false}` on the material is required for bloom. Without it, the renderer clamps emissive values to [0,1] before the bloom pass sees them, and nothing glows.

### Common Effects

```tsx
import { EffectComposer, Bloom, ChromaticAberration, Vignette, SSAO } from '@react-three/postprocessing'

<EffectComposer>
  <Bloom luminanceThreshold={0.9} intensity={1.5} mipmapBlur />
  <ChromaticAberration offset={[0.002, 0.002]} />
  <Vignette eskil={false} offset={0.1} darkness={1.1} />
  <SSAO radius={0.05} intensity={15} />
</EffectComposer>
```

**Effect order matters** — effects run in the order they appear in the JSX. Bloom should generally come first (operates on HDR values), then color effects, then vignette (screen-space overlay).

---

## Drei Helper Components

`@react-three/drei` provides 100+ helper components. Here are the most commonly needed:

### Environment and Lighting

```tsx
import { Environment, ContactShadows, Sky } from '@react-three/drei'

// HDR environment for reflections + ambient light
<Environment preset="city" />  // presets: apartment, city, dawn, forest, lobby, night, park, studio, sunset, warehouse

// Soft contact shadows on a ground plane
<ContactShadows position={[0, -0.5, 0]} opacity={0.4} blur={2} />

// Procedural sky
<Sky sunPosition={[100, 20, 100]} />
```

### Text

```tsx
import { Text, Text3D } from '@react-three/drei'

// 2D billboard text (always faces camera)
<Text fontSize={0.5} color="white" anchorX="center" anchorY="middle">
  Hello World
</Text>

// 3D extruded text (needs a font JSON)
<Text3D font="/fonts/helvetiker_regular.typeface.json" size={0.75} height={0.2}>
  Hello
  <meshStandardMaterial color="gold" />
</Text3D>
```

### Loading Models

```tsx
import { useGLTF, Clone } from '@react-three/drei'

function Model({ url }: { url: string }) {
  const { scene } = useGLTF(url)
  return <Clone object={scene} />
}

// Preload for no loading flash:
useGLTF.preload('/models/robot.glb')
```

**Use `<Clone>`** instead of `<primitive object={scene} />` when you need multiple instances — `primitive` reuses the same Three.js object (can only appear once in the scene graph), while `Clone` creates a deep copy.

### Other Essential Drei Components

| Component | Purpose |
|-----------|---------|
| `<Html>` | Embed HTML/CSS inside the 3D scene (follows 3D position) |
| `<Float>` | Gentle floating animation on children |
| `<PresentationControls>` | Drag-to-rotate for product viewers (alternative to OrbitControls) |
| `<RoundedBox>` | Box with rounded edges |
| `<Center>` | Auto-center children in the scene |
| `<useTexture>` | Load textures with suspense |
| `<Instances>` / `<Instance>` | Declarative instanced meshes |
| `<Sparkles>` | Particle sparkle effect |
| `<Stars>` | Starfield background |
| `<Grid>` | Configurable ground grid |

---

## State Management with Zustand

For interactive or game-like R3F apps, use Zustand for state. It works seamlessly with R3F because both use refs and subscriptions, not React re-renders.

```tsx
import { create } from 'zustand'

interface GameState {
  score: number
  playerPosition: [number, number, number]
  incrementScore: () => void
  setPlayerPosition: (pos: [number, number, number]) => void
}

const useGameStore = create<GameState>((set) => ({
  score: 0,
  playerPosition: [0, 0, 0],
  incrementScore: () => set((state) => ({ score: state.score + 1 })),
  setPlayerPosition: (pos) => set({ playerPosition: pos }),
}))
```

### Reading State in useFrame Without Re-renders

```tsx
function Player() {
  const meshRef = useRef<THREE.Mesh>(null!)

  useFrame(() => {
    // Direct subscription — no re-render
    const pos = useGameStore.getState().playerPosition
    meshRef.current.position.set(...pos)
  })

  return <mesh ref={meshRef}><boxGeometry /><meshStandardMaterial /></mesh>
}
```

**Key pattern**: Use `getState()` inside `useFrame`, not the hook's return value. The hook triggers re-renders; `getState()` reads the latest value without triggering React's reconciler.

### UI Overlay Reading State

```tsx
function HUD() {
  const score = useGameStore((state) => state.score)
  return <div className="hud">Score: {score}</div>
}
```

For UI components that render outside `<Canvas>`, use the normal Zustand hook — re-renders are fine for DOM elements.

---

## Performance Patterns

### Instanced Meshes

When rendering 100+ identical objects, use instancing:

```tsx
import { Instances, Instance } from '@react-three/drei'

function Particles({ count = 1000 }) {
  const particles = useMemo(() =>
    Array.from({ length: count }, () => ({
      position: [
        (Math.random() - 0.5) * 20,
        (Math.random() - 0.5) * 20,
        (Math.random() - 0.5) * 20,
      ] as [number, number, number],
      scale: Math.random() * 0.5 + 0.1,
    })),
    [count]
  )

  return (
    <Instances limit={count}>
      <sphereGeometry args={[1, 8, 8]} />
      <meshStandardMaterial color="#88ccff" />
      {particles.map((p, i) => (
        <Instance key={i} position={p.position} scale={p.scale} />
      ))}
    </Instances>
  )
}
```

### Geometry and Material Reuse

```tsx
// GOOD: Define geometry/material once, use in multiple meshes
const sharedGeo = useMemo(() => new THREE.BoxGeometry(1, 1, 1), [])
const sharedMat = useMemo(() => new THREE.MeshStandardMaterial({ color: 'orange' }), [])

return (
  <>
    <mesh geometry={sharedGeo} material={sharedMat} position={[0, 0, 0]} />
    <mesh geometry={sharedGeo} material={sharedMat} position={[2, 0, 0]} />
    <mesh geometry={sharedGeo} material={sharedMat} position={[4, 0, 0]} />
  </>
)
```

### Performance Monitoring

```tsx
import { Perf } from 'r3f-perf'

// Inside Canvas, during development only:
<Perf position="top-left" />
```

### Common Performance Killers

| Problem | Detection | Fix |
|---------|-----------|-----|
| State updates in useFrame | Search for `useState` or `set` calls inside `useFrame` | Use refs instead of state for per-frame mutations |
| Geometry allocation in render | Search for `new THREE.` inside `useFrame` or component body without `useMemo` | Allocate once with `useMemo`, mutate in `useFrame` |
| Too many draw calls | r3f-perf shows draw call count > 200 | Use `<Instances>`, merge static geometries, use LOD |
| Large textures | GPU memory > 500MB | Compress textures (KTX2), use `useTexture` with responsive sizes |
| Shadow map too large | Frame time spikes | Cap `shadow-mapSize` at `[1024, 1024]` unless close-up detail needed |
| Re-rendering entire scene | React DevTools shows frequent renders | Memoize components, use refs for animation, isolate state consumers |

---

## Common Anti-Patterns

### 1. Mixing Imperative and Declarative

```tsx
// BAD: Imperative Three.js inside R3F
useEffect(() => {
  const geometry = new THREE.BoxGeometry(1, 1, 1)
  const material = new THREE.MeshStandardMaterial({ color: 'red' })
  const mesh = new THREE.Mesh(geometry, material)
  scene.add(mesh)  // Manual scene manipulation
  return () => { scene.remove(mesh) }
}, [])

// GOOD: Declarative R3F
<mesh>
  <boxGeometry args={[1, 1, 1]} />
  <meshStandardMaterial color="red" />
</mesh>
```

R3F manages the scene graph. Manual `scene.add()` bypasses React's reconciler and causes orphaned objects, missing cleanup, and state desync.

### 2. useEffect for Animation

```tsx
// BAD: useEffect + requestAnimationFrame
useEffect(() => {
  let id: number
  function animate() {
    id = requestAnimationFrame(animate)
    meshRef.current.rotation.y += 0.01
  }
  animate()
  return () => cancelAnimationFrame(id)
}, [])

// GOOD: useFrame
useFrame((_, delta) => {
  meshRef.current.rotation.y += delta
})
```

`useFrame` is managed by R3F's render loop. Using `requestAnimationFrame` directly creates a separate loop that's not synchronized with R3F's renderer, causing double-renders and timing issues.

### 3. Heavy Computation in Components

```tsx
// BAD: Recalculates on every render
function Terrain() {
  const vertices = generateTerrain(1000, 1000)  // Expensive!
  return <mesh><bufferGeometry>...</bufferGeometry></mesh>
}

// GOOD: Memoize expensive computations
function Terrain() {
  const vertices = useMemo(() => generateTerrain(1000, 1000), [])
  return <mesh><bufferGeometry>...</bufferGeometry></mesh>
}
```

### 4. Forgetting Suspense for Asset Loading

```tsx
// BAD: No loading state — white flash or error
function App() {
  return (
    <Canvas>
      <Model url="/heavy-model.glb" />
    </Canvas>
  )
}

// GOOD: Suspense boundary with fallback
function App() {
  return (
    <Canvas>
      <Suspense fallback={<LoadingIndicator />}>
        <Model url="/heavy-model.glb" />
      </Suspense>
    </Canvas>
  )
}

function LoadingIndicator() {
  return (
    <mesh>
      <sphereGeometry args={[0.5, 16, 16]} />
      <meshBasicMaterial color="#666" wireframe />
    </mesh>
  )
}
```

`useGLTF`, `useTexture`, and other loaders throw promises (React Suspense). Without a `<Suspense>` boundary, the app crashes.

---

## Error Handling

### Error: "R3F: Canvas is not allowed to have children that aren't THREE elements"
Cause: Regular HTML elements inside `<Canvas>` (e.g., `<div>`, `<p>`)
Solution: Use `<Html>` from drei to embed HTML, or place HTML outside the Canvas.

### Error: "Cannot read properties of null (reading 'rotation')"
Cause: Ref accessed before mount, or conditional rendering removed the mesh
Solution: Add null check in useFrame: `if (!meshRef.current) return`

### Error: Objects appear but no lighting/all black
Cause: Missing lights in the scene, or using `MeshStandardMaterial` without any light source
Solution: Add `<ambientLight intensity={0.5} />` and a directional light. Or use `<Environment>` from drei.

### Error: Model loads but is invisible
Cause: Model scale is extremely small or large relative to camera, or model is at a distant position
Solution: Use drei's `<Center>` component, or compute bounding box and adjust camera.

### Error: Controls feel laggy or jittery
Cause: OrbitControls + custom camera controller both active, or state updates causing re-renders during orbit
Solution: Use only one camera control method. Check for useState calls triggered by mouse events.

### Error: Post-processing bloom has no visible effect
Cause: `toneMapped` is not set to `false` on emissive materials, or `emissiveIntensity` is too low
Solution: Set `toneMapped={false}` on the material AND increase `emissiveIntensity` above 1.0.
