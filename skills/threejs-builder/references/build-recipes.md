# Three.js Builder — Build Recipes and Error Handling

## Phase 1: Additional Reference Loading Signals

**Visual quality signal**: If the user's request implies high visual quality (portfolio, game, showcase, "make it look good", "impressive", "polished"), also load `references/visual-polish.md` alongside the paradigm reference. It contains specific material recipes, lighting setups, and post-processing configurations that bridge the gap between technically correct and visually impressive.

**Custom shader signal**: If the user mentions custom shaders, GLSL, ShaderMaterial, vertex displacement, postprocessing effects (bloom, chromatic aberration, dissolve), or custom visual effects, load `references/shader-patterns.md`. It contains complete GLSL patterns with working code, anti-patterns with detection commands, and the postprocessing pipeline setup.

**Performance signal**: If the user mentions many objects (particles, foliage, crowds), InstancedMesh, performance profiling, draw call reduction, texture compression, or memory issues, load `references/performance-patterns.md`.

**Advanced animation signal**: If the user mentions AnimationMixer, morph targets, skeletal rigs, IK, spring physics, GSAP + Three.js, or GPU particle animation, load `references/advanced-animation.md`.

## Phase 1: Scene Plan Template

```markdown
## Scene Plan
- Geometry: [primitives or model loading]
- Material: [Basic/Standard/Physical/Shader]
- Lighting: [ambient + directional + fill / custom]
- Animation: [rotation / wave / mouse / physics]
- Controls: [OrbitControls / none / custom]
- Extras: [post-processing / raycasting / particles]
```

---

## Phase 2: Core Constraints (Imperative Paradigm)

- **Single HTML file output by default** unless user specifies otherwise
- **Include resize handling** that caps `devicePixelRatio` at 2 and updates camera aspect on window change
- **Use a top-level `CONFIG` object** for all visual constants (colors, speeds, sizes) — no magic numbers scattered through code
- **Separate concerns into modular setup functions**: `createScene()`, `createLights()`, `createMeshes()` — this enables testing and reuse
- **Include three-point lighting by default**: ambient light + directional light + fill light, unless user specifies a different lighting strategy
- **Use `renderer.setAnimationLoop()` instead of manual `requestAnimationFrame()`** for cleaner animation setup

## Phase 3: Core Constraints (Imperative Paradigm)

- **Never allocate geometry or materials inside the animation loop** — this causes garbage collection pauses and frame rate collapse
- **Use the `time` parameter (in milliseconds) for time-based animation** — multiply by small factors (0.001, 0.0005) for smooth motion
- **Include OrbitControls by default** for interactive scenes (unless user requests a specific control scheme) — but in R3F, OrbitControls from `@react-three/drei` conflicts with custom camera controllers; see the R3F reference for when to use which
- **Transform only position, rotation, and scale per frame** — all geometry and materials are static

## Phase 4: Core Constraints

- **Remove all debug helpers** (AxesHelper, GridHelper, Stats) unless user explicitly requested them
- **Remove all commented-out code and TODO markers**
- **Every scene must handle window resize** and render correctly at all viewport sizes
- **Lighting must produce visible surfaces** — no black screens from missing lights
- **Colors and visual style must match the intended context** — this is non-negotiable quality bar

---

## Phase 2: HTML Boilerplate (Imperative)

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

## Phase 2: Scene Infrastructure (Imperative)

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

## Phase 3: Animation Loop (Imperative)

```javascript
renderer.setAnimationLoop((time) => {
    // Update animations
    // Update controls if present
    renderer.render(scene, camera);
});
```

Apply transforms per frame. Time-based animation should follow the pattern:
```javascript
mesh.rotation.x += CONFIG.speeds.rotation * (time * 0.001);
```

---

## Phase 4: Polish Verification Steps

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
