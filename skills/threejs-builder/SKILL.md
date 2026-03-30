---
name: threejs-builder
description: "Three.js app builder: Design, Build, Animate, Polish in 4 phases."
version: 2.0.0
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
    - 3D animation
    - 3D graphics
  pairs_with:
    - typescript-frontend-engineer
    - distinctive-frontend-design
---

# Three.js Builder Skill

## Overview

This skill builds complete Three.js web applications using a **Phased Construction** pattern with four phases: Design, Build, Animate, Polish. It is designed for modern Three.js (r150+) ES module patterns and produces scene-graph-driven 3D visualizations.

**Scope**: Use for 3D web apps, interactive scenes, WebGL visualizations, and product viewers. Do NOT use for game engines, 3D model creation, VR/AR experiences, or CAD workflows.

---

## Instructions

### Phase 1: DESIGN

**Goal**: Understand what the user wants and select appropriate Three.js components.

**Core Constraints**:
- **Build only what the user asked for** — no speculative features or "while I'm here" additions
- **Use modern Three.js (r150+) ES modules only** — always import from CDN (`https://unpkg.com/three@0.160.0/build/three.module.js`) or npm, never use legacy global `THREE` variable or CommonJS
- **Structure through the scene graph** — use `Group` for logical groupings and maintain proper hierarchy
- **Vary style by context** — portfolio/showcase use elegant muted palettes; games use bright colors; data viz uses clean lines; backgrounds use subtle slow movement; product viewers use realistic PBR lighting
- **Read repository CLAUDE.md before building** — ensure compliance with local development standards

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

**Core Constraints**:
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

**Core Constraints**:
- **Never allocate geometry or materials inside the animation loop** — this causes garbage collection pauses and frame rate collapse
- **Use the `time` parameter (in milliseconds) for time-based animation** — multiply by small factors (0.001, 0.0005) for smooth motion
- **Include OrbitControls by default** for interactive scenes (unless user requests a specific control scheme)
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

- `${CLAUDE_SKILL_DIR}/references/advanced-topics.md`: GLTF loading, post-processing, shaders, raycasting, physics, InstancedMesh, TypeScript support
