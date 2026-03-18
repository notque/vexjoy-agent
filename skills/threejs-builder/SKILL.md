---
name: threejs-builder
description: |
  Scene-graph-driven 4-phase Three.js app builder: Design, Build, Animate,
  Polish. Use when user wants a 3D web app, interactive scene, WebGL
  visualization, or product viewer. Use for "create a threejs scene",
  "build 3D web app", "make a 3D animation", or "interactive 3D showcase".
  Do NOT use for full game engines, 3D model creation, VR/AR experiences,
  or CAD workflows.
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

## Operator Context

This skill operates as an operator for Three.js web application creation, configuring Claude's behavior for structured, scene-graph-driven 3D development. It implements the **Phased Construction** architectural pattern -- Design, Build, Animate, Polish -- with **Domain Intelligence** embedded in modern Three.js (r150+) ES module patterns.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before building
- **Over-Engineering Prevention**: Build only what the user asked for. No speculative features, no "while I'm here" additions
- **ES Modules Only**: Always use modern ES module imports from CDN or npm. Never use legacy global `THREE` variable or CommonJS
- **Scene Graph First**: Structure all objects through the scene graph hierarchy. Use `Group` for logical groupings
- **Responsive by Default**: Every app must handle window resize and cap `devicePixelRatio` at 2
- **Single HTML File**: Default output is one self-contained HTML file unless user specifies otherwise

### Default Behaviors (ON unless disabled)
- **Three-Point Lighting**: Set up ambient + directional + fill light for standard scenes
- **OrbitControls**: Include orbit camera controls for interactive scenes
- **Animation Loop via setAnimationLoop**: Use `renderer.setAnimationLoop()` over manual `requestAnimationFrame`
- **Configuration Object**: Define visual constants (colors, speeds, sizes) in a top-level `CONFIG` object
- **Modular Setup Functions**: Separate scene creation into `createScene()`, `createLights()`, `createMeshes()` functions

### Optional Behaviors (OFF unless enabled)
- **Post-Processing**: Bloom, depth of field via EffectComposer
- **Model Loading**: GLTF/GLB loading with auto-center and scale
- **Custom Shaders**: ShaderMaterial with GLSL vertex/fragment shaders
- **Shadow Mapping**: PCFSoft shadows with configurable map resolution
- **Physics Integration**: Cannon.js gravity and collision simulation
- **Raycasting**: Mouse/touch picking of 3D objects

## What This Skill CAN Do
- Create complete Three.js web applications from a user description
- Set up scenes with proper lighting, camera, renderer, and resize handling
- Use built-in geometries (Box, Sphere, Cylinder, Torus, Plane, Cone, Icosahedron)
- Apply PBR materials (Standard, Physical) and basic materials (Basic, Phong, Normal)
- Implement animations: rotation, oscillation, wave motion, mouse tracking
- Add OrbitControls, GLTF model loading, post-processing, raycasting
- Vary visual style to match context (portfolio, game, data viz, background effect)

## What This Skill CANNOT Do
- Create complex game engines (use Unity, Unreal instead)
- Generate or edit 3D model files (modeling is done in Blender, etc.)
- Implement VR/AR experiences (specialized WebXR knowledge needed)
- Replace dedicated CAD software for engineering drawings
- Optimize scenes with 1M+ polygons (requires specialized LOD/culling strategies)

---

## Instructions

### Phase 1: DESIGN

**Goal**: Understand what the user wants and select appropriate Three.js components.

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

**Step 3: Choose visual style based on context**

| Context | Style Guidance |
|---------|---------------|
| Portfolio/showcase | Elegant, smooth animations, muted palette |
| Game/interactive | Bright colors, snappy controls, particle effects |
| Data visualization | Clean lines, grid helpers, clear labels |
| Background effect | Subtle, slow movement, dark gradients |
| Product viewer | Realistic PBR lighting, smooth orbit, neutral backdrop |

**Gate**: Scene plan documented with geometry, material, lighting, animation, and controls selected. Proceed only when gate passes.

### Phase 2: BUILD

**Goal**: Construct the scene with proper structure and modern patterns.

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

Build each component from the Phase 1 plan. Create geometry once, reuse where possible. Use `Group` for hierarchical transforms.

**Gate**: Scene renders without errors. All planned geometry, materials, and lights are present. Proceed only when gate passes.

### Phase 3: ANIMATE

**Goal**: Add motion, interaction, and life to the scene.

**Step 1: Set up animation loop**

```javascript
renderer.setAnimationLoop((time) => {
    // Update animations
    // Update controls if present
    renderer.render(scene, camera);
});
```

**Step 2: Implement planned animations**

Apply transforms per frame. Use `time` parameter (milliseconds) for time-based animation. Multiply by small factors (0.001, 0.0005) for smooth motion.

**Step 3: Add interaction handlers**

Wire up mouse/touch events, orbit controls, or raycasting per the scene plan.

**Gate**: Animations run smoothly. Interactions respond correctly. No console errors. Proceed only when gate passes.

### Phase 4: POLISH

**Goal**: Ensure quality, performance, and completeness.

**Step 1: Verify responsive behavior**
- Resize browser window -- canvas fills viewport without distortion
- `devicePixelRatio` capped at 2

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

## Examples

### Example 1: Simple Animated Scene
User says: "Create a threejs scene with a rotating icosahedron"
Actions:
1. Design: low-poly icosahedron, standard material, three-point lighting, continuous rotation (DESIGN)
2. Build: HTML boilerplate, scene setup, IcosahedronGeometry with flatShading, lighting (BUILD)
3. Animate: rotation on x and y axes using time parameter (ANIMATE)
4. Polish: verify resize, test in browser, remove debug helpers (POLISH)
Result: Single HTML file with responsive, animated 3D scene

### Example 2: Interactive Product Viewer
User says: "Build a 3D product viewer that loads a GLB model"
Actions:
1. Design: GLTF loader, PBR material, realistic lighting, OrbitControls, neutral backdrop (DESIGN)
2. Build: HTML with GLTFLoader import, auto-center/scale model, environment lighting (BUILD)
3. Animate: orbit controls with damping, optional auto-rotate (ANIMATE)
4. Polish: loading progress indicator, responsive, verify model renders (POLISH)
Result: Interactive model viewer with orbit controls and proper lighting

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

## Anti-Patterns

### Anti-Pattern 1: Creating Geometry Inside the Animation Loop
**What it looks like**: `new THREE.BoxGeometry(1,1,1)` called every frame
**Why wrong**: Allocates memory every frame, causes GC pauses and frame rate collapse
**Do instead**: Create all geometries and materials once during setup. Transform only position, rotation, and scale in the loop.

### Anti-Pattern 2: Using Legacy Global THREE Patterns
**What it looks like**: `<script src="three.js">` with `var scene = new THREE.Scene()`
**Why wrong**: CommonJS/global patterns are deprecated. CDN bundles are outdated. Addons like OrbitControls are not available on the global namespace.
**Do instead**: Always use `<script type="module">` with ES module imports from unpkg or npm.

### Anti-Pattern 3: Skipping Pixel Ratio Cap
**What it looks like**: `renderer.setPixelRatio(window.devicePixelRatio)` without cap
**Why wrong**: Retina/HiDPI displays (3x, 4x) render at extreme resolutions, destroying performance on mobile
**Do instead**: `renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))`

### Anti-Pattern 4: Hardcoding Everything With No Configuration
**What it looks like**: Magic numbers scattered throughout -- `0x44aa88`, `0.001`, `75`
**Why wrong**: Impossible to tweak, experiment, or understand intent
**Do instead**: Define a `CONFIG` object at the top with named constants: `CONFIG.color`, `CONFIG.rotationSpeed`, `CONFIG.fov`

### Anti-Pattern 5: Identical Output Every Time
**What it looks like**: Every scene uses green cube, camera at z=5, directional light at (1,1,1)
**Why wrong**: Produces generic, cookie-cutter results that ignore the user's context
**Do instead**: Vary geometry, color palette, camera angle, lighting setup, and animation style based on the scene's purpose (see Phase 1 style guidance).

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "It renders, must be done" | Rendering does not mean correct lighting, animation, or interaction | Complete Phase 4 verification |
| "I'll skip OrbitControls, simpler" | User expects interactive scenes by default | Include controls unless explicitly static |
| "BasicMaterial is fine" | BasicMaterial ignores lighting, looks flat and cheap | Use StandardMaterial unless unlit effect is intentional |
| "Resize handler isn't needed" | Scene breaks on any window change, looks broken on mobile | Always include resize handling |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/advanced-topics.md`: GLTF loading, post-processing, shaders, raycasting, physics, InstancedMesh, TypeScript support
