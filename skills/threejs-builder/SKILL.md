---
name: threejs-builder
description: "Three.js app builder: imperative, React Three Fiber, and WebGPU in 4 phases."
version: 3.1.0
user-invocable: false
command: /threejs
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
routing:
  triggers:
    - threejs
    - three.js
    - 3D web
    - 3D scene
    - WebGL
    - WebGPU
    - 3D animation
    - 3D graphics
    - react three fiber
    - r3f
    - drei
    - react-three
    - "@react-three/fiber"
    - postprocessing 3D
    - TSL shader
    - three shading language
    - compute shader three
    - WebGPURenderer
    - node material three
    - game architecture three
    - gltf loading
    - glb model
    - animation state machine three
    - eventbus game
    - game state management three
    - three.js game
  pairs_with:
    - typescript-frontend-engineer
    - react-native-engineer
    - distinctive-frontend-design
  complexity: Medium
  category: frontend
---

# Three.js Builder Skill

## Overview

This skill builds complete Three.js web applications using a **Phased Construction** pattern with four phases: Design, Build, Animate, Polish. It supports three paradigms — imperative Three.js, React Three Fiber (R3F), and WebGPU — detected automatically from project context. Only the relevant paradigm's reference is loaded.

**Scope**: Use for 3D web apps, interactive scenes, WebGL/WebGPU visualizations, R3F declarative 3D, and product viewers. Do NOT use for game engines, 3D model creation, VR/AR experiences, or CAD workflows.

---

## Instructions

### Phase 1: DESIGN

**Goal**: Detect the paradigm, understand what the user wants, and select appropriate components.

**Core Constraints**:
- **Build only what the user asked for** — no speculative features or "while I'm here" additions
- **Detect the paradigm before selecting components** — imperative, R3F, and WebGPU have fundamentally different patterns; using the wrong one is the #1 source of bugs
- **Structure through the scene graph** — use `Group` for logical groupings and maintain proper hierarchy
- **Vary style by context** — portfolio/showcase use elegant muted palettes; games use bright colors; data viz uses clean lines; backgrounds use subtle slow movement; product viewers use realistic PBR lighting
- **Read repository CLAUDE.md before building** — ensure compliance with local development standards

**Step 0: Detect paradigm**

Scan the user's request, existing project files (package.json, imports), and stated requirements to identify which paradigm applies:

| Signal | Paradigm / Context | Reference to Load |
|--------|-------------------|-------------------|
| `@react-three/fiber`, `r3f`, `drei`, `useFrame`, `<Canvas>`, `<mesh>`, React project with 3D | **React Three Fiber** | `references/react-three-fiber.md` |
| `WebGPURenderer`, `TSL`, `tsl`, `compute shader`, `wgsl`, `node material`, WebGPU mentioned | **WebGPU** | `references/webgpu.md` |
| Standalone HTML, CDN imports, `new THREE.Scene()`, no React, vanilla JS/TS | **Imperative** | `references/advanced-topics.md` (load as needed) |
| Game project: `EventBus`, `GameState`, player controller, enemies, scoring, multiple game systems | **Game architecture** | `references/game-architecture.md` + `references/game-patterns.md` (alongside paradigm reference) |
| GLTF/GLB model loading, `.glb` files, animated characters, skeletal rigs, model import | **GLTF loading** | `references/gltf-loading.md` (alongside paradigm reference) |

If ambiguous (e.g., user says "3D scene" with no project context), ask which paradigm — don't guess, because imperative Three.js patterns actively conflict with R3F patterns (OrbitControls setup, animation loops, component lifecycle).

Game and GLTF references load **alongside** the paradigm reference — they are complementary, not alternative. A game project using R3F loads both `react-three-fiber.md` and the relevant game references.

**After detecting paradigm**: Read the corresponding reference file. The reference contains paradigm-specific patterns, anti-patterns, and component selection guidance that override the generic steps below.

**Visual quality signal**: If the user's request implies high visual quality (portfolio, game, showcase, "make it look good", "impressive", "polished"), also load `references/visual-polish.md` alongside the paradigm reference. It contains specific material recipes, lighting setups, and post-processing configurations that bridge the gap between technically correct and visually impressive.

**Custom shader signal**: If the user mentions custom shaders, GLSL, ShaderMaterial, vertex displacement, postprocessing effects (bloom, chromatic aberration, dissolve), or custom visual effects, load `references/shader-patterns.md`. It contains complete GLSL patterns with working code, anti-patterns with detection commands, and the postprocessing pipeline setup.

**Performance signal**: If the user mentions many objects (particles, foliage, crowds), InstancedMesh, performance profiling, draw call reduction, texture compression, or memory issues, load `references/performance-patterns.md`.

**Advanced animation signal**: If the user mentions AnimationMixer, morph targets, skeletal rigs, IK, spring physics, GSAP + Three.js, or GPU particle animation, load `references/advanced-animation.md`.

**Step 1: Identify the core visual element**

Determine from the user request:
- What is the primary 3D content? (geometric shapes, loaded model, particles, terrain)
- What interaction is needed? (none, orbit, click, mouse tracking)
- What animation brings it to life? (rotation, oscillation, morphing, physics)
- What is the context? (portfolio, game, data viz, background, product viewer)

**Step 2: Select components**

```markdown
## Scene Plan
- Geometry: [primitives or model loading]
- Material: [Basic/Standard/Physical/Shader]
- Lighting: [ambient + directional + fill / custom]
- Animation: [rotation / wave / mouse / physics]
- Controls: [OrbitControls / none / custom]
- Extras: [post-processing / raycasting / particles]
```

**Step 3: Document visual style**

Record the visual direction for this scene (e.g., "elegant minimal portfolio style", "vibrant interactive game", "clean data visualization"). Use this to guide material colors, lighting warmth, and animation pacing.

**Gate**: Scene plan documented with geometry, material, lighting, animation, and controls selected. Proceed only when gate passes.

### Phase 2: BUILD

**Goal**: Construct the scene with proper structure and modern patterns.

**Paradigm-specific build instructions**: If you loaded a paradigm reference in Step 0, follow its build patterns instead of the imperative defaults below. R3F uses JSX components and `<Canvas>`, not manual renderer setup. WebGPU uses `WebGPURenderer` with different initialization. The reference file is authoritative for its paradigm.

**Core Constraints (imperative paradigm)**:
- **Single HTML file output by default** unless user specifies otherwise
- **Include resize handling** that caps `devicePixelRatio` at 2 and updates camera aspect on window change
- **Use a top-level `CONFIG` object** for all visual constants (colors, speeds, sizes) — no magic numbers scattered through code
- **Separate concerns into modular setup functions**: `createScene()`, `createLights()`, `createMeshes()` — this enables testing and reuse
- **Include three-point lighting by default**: ambient light + directional light + fill light, unless user specifies a different lighting strategy
- **Use `renderer.setAnimationLoop()` instead of manual `requestAnimationFrame()`** for cleaner animation setup

**Step 1: Create HTML boilerplate**

Every app starts with this structure:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>[App Title]</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { overflow: hidden; background: #000; }
        canvas { display: block; }
    </style>
</head>
<body>
    <script type="module">
        import * as THREE from 'https://unpkg.com/three@0.160.0/build/three.module.js';
        // Additional imports as needed
    </script>
</body>
</html>
```

**Step 2: Build scene infrastructure**

```javascript
// CONFIG object at top level
const CONFIG = {
    colors: { /* color hex values */ },
    speeds: { /* animation speeds */ },
    sizes: { /* geometric dimensions */ }
};

// Scene, camera, renderer
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(
    75, window.innerWidth / window.innerHeight, 0.1, 1000
);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
document.body.appendChild(renderer.domElement);

// Resize handler (always include)
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});
```

**Step 3: Add lighting, geometry, and materials per scene plan**

Build each component from the Phase 1 plan. Create geometry once and reuse where possible (avoid allocating new geometries in animation loops). Use `Group` for hierarchical transforms and logical scene organization.

**Gate**: Scene renders without errors. All planned geometry, materials, and lights are present. Proceed only when gate passes.

### Phase 3: ANIMATE

**Goal**: Add motion, interaction, and life to the scene.

**Paradigm-specific animation**: R3F uses `useFrame` hooks (never `requestAnimationFrame` or `setAnimationLoop`). WebGPU may use compute shaders for GPU-driven animation. See the loaded paradigm reference for patterns.

**Core Constraints (imperative paradigm)**:
- **Never allocate geometry or materials inside the animation loop** — this causes garbage collection pauses and frame rate collapse
- **Use the `time` parameter (in milliseconds) for time-based animation** — multiply by small factors (0.001, 0.0005) for smooth motion
- **Include OrbitControls by default** for interactive scenes (unless user requests a specific control scheme) — but in R3F, OrbitControls from `@react-three/drei` conflicts with custom camera controllers; see the R3F reference for when to use which
- **Transform only position, rotation, and scale per frame** — all geometry and materials are static

**Step 1: Set up animation loop**

```javascript
renderer.setAnimationLoop((time) => {
    // Update animations
    // Update controls if present
    renderer.render(scene, camera);
});
```

**Step 2: Implement planned animations**

Apply transforms per frame. Time-based animation should follow the pattern:
```javascript
mesh.rotation.x += CONFIG.speeds.rotation * (time * 0.001);
```

**Step 3: Add interaction handlers**

Wire up mouse/touch events, orbit controls, or raycasting per the scene plan.

**Gate**: Animations run smoothly. Interactions respond correctly. No console errors. Proceed only when gate passes.

### Phase 4: POLISH

**Goal**: Ensure quality, performance, and completeness.

**Core Constraints**:
- **Remove all debug helpers** (AxesHelper, GridHelper, Stats) unless user explicitly requested them
- **Remove all commented-out code and TODO markers**
- **Every scene must handle window resize** and render correctly at all viewport sizes
- **Lighting must produce visible surfaces** — no black screens from missing lights
- **Colors and visual style must match the intended context** — this is non-negotiable quality bar

**Step 1: Verify responsive behavior**
- Resize browser window — canvas fills viewport without distortion
- `devicePixelRatio` capped at 2
- Test at common mobile/tablet/desktop breakpoints

**Step 2: Verify visual quality**
- Lighting produces visible surfaces (no black screen from missing lights)
- Materials look correct (metalness/roughness values appropriate)
- Colors and style match the intended context

**Step 3: Test the output**
- Open the HTML file in a browser or serve it locally
- Confirm no console errors or warnings
- Confirm animations and interactions work as intended

**Step 4: Clean up**
- Remove any debug helpers (AxesHelper, GridHelper, Stats) unless user wanted them
- Ensure no commented-out code or TODO markers remain

**Gate**: All verification steps pass. Output is complete and ready to deliver.

---

## Error Handling

### Error: "Black Screen / Nothing Renders"
Cause: Missing lights (StandardMaterial requires light), object not added to scene, or camera pointing wrong direction
Solution:
1. Verify at least one light is added to the scene (AmbientLight + DirectionalLight)
2. Confirm all meshes are added with `scene.add(mesh)`
3. Check camera position -- `camera.position.z = 5` as baseline
4. If using BasicMaterial or NormalMaterial, lights are not the issue -- check geometry and camera

### Error: "OrbitControls is not defined"
Cause: Incorrect import path or missing import statement
Solution:
1. For CDN: `import { OrbitControls } from 'https://unpkg.com/three@0.160.0/examples/jsm/controls/OrbitControls.js'`
2. For npm: `import { OrbitControls } from 'three/addons/controls/OrbitControls.js'`
3. Never use `THREE.OrbitControls` -- addons are not on the THREE namespace in modern Three.js

### Error: "Model Loads But Is Invisible or Tiny"
Cause: Model scale/position does not match scene scale, or model is centered at wrong origin
Solution:
1. Compute bounding box: `new THREE.Box3().setFromObject(gltf.scene)`
2. Center the model: `gltf.scene.position.sub(box.getCenter(new THREE.Vector3()))`
3. Scale camera distance: `camera.position.z = Math.max(size.x, size.y, size.z) * 2`

---

## References

| Reference | When to Load | Content |
|-----------|-------------|---------|
| `references/advanced-topics.md` | Imperative paradigm | GLTF loading, post-processing, shaders, raycasting, physics, InstancedMesh, TypeScript |
| `references/react-three-fiber.md` | R3F paradigm | Declarative patterns, Drei helpers, camera pitfalls, post-processing, Zustand, performance |
| `references/webgpu.md` | WebGPU paradigm | WebGPURenderer, TSL shaders, compute shaders, version-specific changes, device loss |
| `references/visual-polish.md` | Visual quality signal | Material recipes, dramatic lighting, post-processing stacking, HDR environments, shadow quality |
| `references/gltf-loading.md` | GLTF/GLB model loading signal | Coordinate system contract, SkeletonUtils.clone, model caching, auto-centering, bone hierarchy, asset manifest |
| `references/game-patterns.md` | Game project signal | Animation state machine, camera-relative movement, delta capping, mobile input, player controller |
| `references/game-architecture.md` | Game project signal | EventBus, GameState singleton, Constants module, restart-safety, pre-ship checklist |
| `references/shader-patterns.md` | Custom GLSL / visual effects | ShaderMaterial vs RawShaderMaterial, vertex displacement, fragment effects (holographic, dissolve, chromatic aberration), EffectComposer postprocessing pipeline |
| `references/performance-patterns.md` | Performance / many objects | InstancedMesh, BufferGeometry typed arrays, draw call batching, LOD, KTX2 textures, dispose patterns |
| `references/advanced-animation.md` | Animation systems / skeletal rigs | AnimationMixer morph targets, bone manipulation, procedural IK, spring physics, GSAP integration, particle animation |
