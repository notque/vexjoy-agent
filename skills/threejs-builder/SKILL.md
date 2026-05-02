---
name: threejs-builder
description: "Three.js app builder: imperative, React Three Fiber, and WebGPU in 4 phases."
agent: typescript-frontend-engineer
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

Builds complete Three.js web applications using **Phased Construction**: Design, Build, Animate, Polish. Supports three paradigms -- imperative Three.js, React Three Fiber (R3F), and WebGPU -- detected automatically from project context. Only the relevant paradigm's reference is loaded.

**Scope**: 3D web apps, interactive scenes, WebGL/WebGPU visualizations, R3F declarative 3D, product viewers. For game engines, 3D model creation, VR/AR, or CAD, use a specialized skill.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| `@react-three/fiber`, `r3f`, `drei`, `useFrame`, `<Canvas>`, `<mesh>`, React project with 3D | `react-three-fiber.md` | **React Three Fiber** |
| `WebGPURenderer`, `TSL`, `tsl`, `compute shader`, `wgsl`, `node material`, WebGPU mentioned | `webgpu.md` | **WebGPU** |
| Standalone HTML, CDN imports, `new THREE.Scene()`, no React, vanilla JS/TS | `advanced-topics.md` (load as needed)` | **Imperative** |
| Game project: `EventBus`, `GameState`, player controller, enemies, scoring, multiple game systems | `game-patterns.md` (alongside paradigm reference)` | **Game architecture** |
| GLTF/GLB model loading, `.glb` files, animated characters, skeletal rigs, model import | `gltf-loading.md` (alongside paradigm reference)` | **GLTF loading** |
| `references/build-recipes.md` | `build-recipes.md` | Phase 2/3 build, error diagnosis |
| `references/advanced-topics.md` | `advanced-topics.md` | Imperative paradigm |
| `references/react-three-fiber.md` | `react-three-fiber.md` | R3F paradigm |
| `references/webgpu.md` | `webgpu.md` | WebGPU paradigm |
| `references/visual-polish.md` | `visual-polish.md` | Visual quality signal |
| `references/gltf-loading.md` | `gltf-loading.md` | GLTF/GLB model loading signal |
| `references/game-patterns.md` | `game-patterns.md` | Game project signal |
| `references/game-architecture.md` | `game-architecture.md` | Game project signal |
| `references/shader-patterns.md` | `shader-patterns.md` | Custom GLSL / visual effects |
| `references/performance-patterns.md` | `performance-patterns.md` | Performance / many objects |
| `references/advanced-animation.md` | `advanced-animation.md` | Animation systems / skeletal rigs |

## Instructions

### Phase 1: DESIGN

**Goal**: Detect paradigm, understand requirements, select components.

**Core Constraints**:
- Build only what the user asked for -- no speculative features
- Detect paradigm before selecting components -- imperative, R3F, and WebGPU have fundamentally different patterns
- Use `Group` for logical scene graph hierarchy
- Vary style by context -- portfolio: elegant muted; games: bright; data viz: clean; backgrounds: subtle slow; product viewers: realistic PBR
- Read repository CLAUDE.md first

**Step 0: Detect paradigm**

Scan request, project files (package.json, imports), and requirements:

| Signal | Paradigm / Context | Reference to Load |
|--------|-------------------|-------------------|
| `@react-three/fiber`, `r3f`, `drei`, `useFrame`, `<Canvas>`, `<mesh>`, React+3D | **React Three Fiber** | `references/react-three-fiber.md` |
| `WebGPURenderer`, `TSL`, `tsl`, `compute shader`, `wgsl`, `node material` | **WebGPU** | `references/webgpu.md` |
| Standalone HTML, CDN imports, `new THREE.Scene()`, no React, vanilla JS/TS | **Imperative** | `references/advanced-topics.md` (as needed) |
| `EventBus`, `GameState`, player controller, enemies, scoring | **Game architecture** | `references/game-architecture.md` + `references/game-patterns.md` (alongside paradigm) |
| GLTF/GLB loading, `.glb` files, animated characters, skeletal rigs | **GLTF loading** | `references/gltf-loading.md` (alongside paradigm) |

If ambiguous, ask which paradigm -- imperative patterns actively conflict with R3F (OrbitControls setup, animation loops, component lifecycle).

Game and GLTF references load **alongside** the paradigm reference -- they are complementary, not alternative.

**After detecting paradigm**: Read the corresponding reference file. It contains paradigm-specific patterns and anti-patterns that override generic steps below.

Additional reference loading signals in `${CLAUDE_SKILL_DIR}/references/build-recipes.md` (Phase 1: Additional Reference Loading Signals).

**Step 1: Identify core visual element** -- Primary 3D content? Interaction needed? Animation? Context (portfolio, game, data viz, background, product viewer)?

**Step 2: Select components** -- See Scene Plan template in `${CLAUDE_SKILL_DIR}/references/build-recipes.md` (Phase 1).

**Step 3: Document visual style** -- Record direction (e.g., "elegant minimal portfolio"). Guides material colors, lighting warmth, animation pacing.

**Gate**: Scene plan documented with geometry, material, lighting, animation, and controls. Proceed only when gate passes.

### Phase 2: BUILD

**Goal**: Construct the scene with proper structure and modern patterns.

**Paradigm-specific**: Follow loaded paradigm reference patterns. R3F uses JSX and `<Canvas>`, not manual renderer setup. WebGPU uses `WebGPURenderer`. The reference file is authoritative.

Core imperative constraints (single HTML, resize handling, CONFIG object, modular setup, three-point lighting, `renderer.setAnimationLoop()`) in `${CLAUDE_SKILL_DIR}/references/build-recipes.md` (Phase 2).

**Step 1: Create HTML boilerplate** -- See `${CLAUDE_SKILL_DIR}/references/build-recipes.md` (Phase 2).

**Step 2: Build scene infrastructure** -- CONFIG object, scene/camera/renderer, resize handler. See `${CLAUDE_SKILL_DIR}/references/build-recipes.md` (Phase 2).

**Step 3: Add lighting, geometry, materials per scene plan** -- Create geometry once and reuse. Use `Group` for hierarchical transforms.

**Gate**: Scene renders without errors. All planned components present. Proceed only when gate passes.

### Phase 3: ANIMATE

**Goal**: Add motion, interaction, and life.

**Paradigm-specific**: R3F uses `useFrame` (never `requestAnimationFrame`/`setAnimationLoop`). WebGPU may use compute shaders. See loaded paradigm reference.

Core imperative constraints (no allocation in loop, `time` parameter, OrbitControls default, transforms-only-per-frame) in `${CLAUDE_SKILL_DIR}/references/build-recipes.md` (Phase 3).

**Step 1: Set up animation loop** -- See `${CLAUDE_SKILL_DIR}/references/build-recipes.md` (Phase 3).

**Step 2: Implement planned animations** -- Time-based transforms per `references/build-recipes.md`.

**Step 3: Add interaction handlers** -- Mouse/touch events, orbit controls, raycasting per scene plan.

**Gate**: Animations run smoothly. Interactions respond correctly. No console errors. Proceed only when gate passes.

### Phase 4: POLISH

**Goal**: Quality, performance, completeness.

Core constraints (remove debug/commented code, handle resize, ensure visible lighting, match visual style) and four verification steps in `${CLAUDE_SKILL_DIR}/references/build-recipes.md` (Phase 4).

**Gate**: All verification steps pass. Output complete and ready to deliver.

---

## Error Handling

See `${CLAUDE_SKILL_DIR}/references/build-recipes.md` for: black screen / nothing renders, OrbitControls not defined, model loads but invisible or tiny.

---

## References

| Reference | When to Load | Content |
|-----------|-------------|---------|
| `references/build-recipes.md` | Phase 2/3 build, error diagnosis | HTML boilerplate, CONFIG + scene setup, animation loop, error handling |
| `references/advanced-topics.md` | Imperative paradigm | GLTF, post-processing, shaders, raycasting, physics, InstancedMesh, TypeScript |
| `references/react-three-fiber.md` | R3F paradigm | Declarative patterns, Drei helpers, camera pitfalls, Zustand, performance |
| `references/webgpu.md` | WebGPU paradigm | WebGPURenderer, TSL shaders, compute shaders, device loss |
| `references/visual-polish.md` | Visual quality | Material recipes, dramatic lighting, post-processing, HDR, shadows |
| `references/gltf-loading.md` | GLTF/GLB loading | Coordinate contract, SkeletonUtils.clone, caching, auto-centering, bones |
| `references/game-patterns.md` | Game project | Animation state machine, camera-relative movement, delta capping, mobile input |
| `references/game-architecture.md` | Game project | EventBus, GameState singleton, Constants, restart-safety, pre-ship checklist |
| `references/shader-patterns.md` | Custom GLSL / effects | ShaderMaterial vs Raw, vertex displacement, fragment effects, EffectComposer |
| `references/performance-patterns.md` | Performance / many objects | InstancedMesh, BufferGeometry, draw call batching, LOD, KTX2, dispose |
| `references/advanced-animation.md` | Animation / skeletal rigs | AnimationMixer, morph targets, bone manipulation, procedural IK, springs, GSAP |
