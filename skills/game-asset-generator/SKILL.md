---
name: game-asset-generator
description: "Deterministic palette/matrix pixel art (not AI). Use for procedural tile art, color-quantized output, matrix sprites."
agent: typescript-frontend-engineer
user-invocable: false
command: /game-assets
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    - pixel art
    - tile pattern
    - palette quantize
    - matrix sprite
    - meshy
    - meshyai
    - generate 3d model
    - text to 3d
    - image to 3d
    - world labs
    - gaussian splat
    - splat environment
    - game asset
    - fal ai
    - fal.ai
    - generate texture
    - generate image for game
    - 3d character
    - game model
    - rig model
    - animate model
    - game environment
    - sketchfab
    - poly pizza
    - poly haven
  pairs_with:
    - threejs-builder
    - typescript-frontend-engineer
  complexity: Medium
  category: game-development
---

# Game Asset Generator Skill

Generates game-ready assets (3D models, Gaussian Splat environments, 2D sprites, images/textures) using AI APIs and free sources. Three phases: DETECT asset type -> GENERATE via appropriate API/source -> INTEGRATE into game. Load only the relevant reference per task.

**Scope**: AI-generated 3D models, world environments, pixel art sprites, concept art, textures, and free pre-built assets. Game engine scripting, physics, game loop logic, and shaders belong in `threejs-builder`.

---

## Phase 1: DETECT

**Goal**: Identify asset type and load the corresponding reference.

**Step 1: Classify the request**

| Signal | Asset Type | Reference |
|--------|-----------|-----------|
| "3D model", "character model", GLB, mesh, rig, animate, humanoid | **3D Model** | `references/meshyai.md` |
| "environment", "world", "gaussian splat", "splat", volumetric | **Environment** | `references/worldlabs.md` |
| "sprite", "pixel art", "2D character", "tile", "tileset" | **2D Sprite** | `references/pixel-art-sprites.md` |
| "image", "texture", "concept art", "icon", chroma key | **Image / Texture** | `references/fal-ai-image.md` |
| No API key, "free asset", "find model", generation failed | **Existing Assets** | `references/asset-sources.md` |

If ambiguous between 3D Model and Image, ask: "Do you need a 3D mesh (GLB for Three.js) or a 2D image/texture?"

**Step 2: Check API key availability**

```bash
grep -E "MESHY_API_KEY|WLT_API_KEY|FAL_KEY" ~/.env 2>/dev/null
```

If required key missing, load `references/asset-sources.md` alongside primary reference.

**Fallback chain**: Meshy API -> Sketchfab -> Poly Haven -> Poly.pizza -> BoxGeometry placeholder. All output GLB to same path so loading code stays unchanged.

**Gate**: Asset type identified, reference loaded.

---

## Phase 2: GENERATE

**Goal**: Produce the asset following the loaded reference exactly.

**Core constraints (all types)**:
- **Download immediately** -- Meshy retains assets only 3 days; World Labs SPZ files expire similarly.
- **Output to stable path** -- `public/assets/` or equivalent game-accessible directory.
- **Save .meta.json sidecar** -- prompt, model, timestamp, asset ID for regeneration/auditing.
- **Validate output** -- file size > 0 and correct extension before proceeding.

**Per-type summary** (full API details in reference):

**3D Model (Meshy)**: Preview (fast, confirms prompt) -> refine (full quality). Auto-rig only for humanoids (bipedal, textured, defined limbs). Animate with walk/run/idle presets. Post-process with `scripts/optimize-glb.mjs` for 80-95% size reduction.

**Environment (World Labs)**: Upload reference image -> poll 3-8 min -> download SPZ + GLB collider + panorama JPG. Y-axis flip (`rotation.x = Math.PI`) required in Three.js.

**2D Sprite (code-only)**: Canvas-based, no API. Use palette and matrix system from `references/pixel-art-sprites.md`.

**Image / Texture (fal.ai)**: Queue-based -- submit -> poll. Choose model by need (GPT Image 1.5 for transparency, Nano Banana 2 for speed). Use `#00FF00` chroma-key for transparency extraction.

**Gate**: Asset downloaded and validated (size > 0, correct extension). .meta.json saved.

---

## Phase 3: INTEGRATE

**Goal**: Load asset into the game scene.

**Critical**: Use `SkeletonUtils.clone()` for animated models -- never `.clone()`. Regular `.clone()` breaks skeleton bindings, leaving permanent T-pose.

```javascript
import { SkeletonUtils } from 'three/addons/utils/SkeletonUtils.js';

loader.load('/assets/character.glb', (gltf) => {
  const instance = SkeletonUtils.clone(gltf.scene);
  scene.add(instance);
});
```

**GLB loading (Three.js)**:
```javascript
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';

const dracoLoader = new DRACOLoader();
dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/');

const loader = new GLTFLoader();
loader.setDRACOLoader(dracoLoader);
loader.load('/assets/model.glb', (gltf) => {
  const model = gltf.scene;
  const box = new THREE.Box3().setFromObject(model);
  const center = box.getCenter(new THREE.Vector3());
  model.position.sub(center);
  scene.add(model);
});
```

**Gaussian Splat (World Labs)** -- see `references/worldlabs.md` for `@sparkjsdev/spark` SplatMesh integration. Y-axis flip and raycast direction inversion are required.

**Animation playback**:
```javascript
const mixer = new THREE.AnimationMixer(model);
const action = mixer.clipAction(gltf.animations[0]);
action.play();
// In animation loop:
mixer.update(deltaTime);
```

**Gate**: Asset visible in scene. No console errors. Animations play if applicable.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| "3D model", GLB, mesh, rig, animate, humanoid | `meshyai.md` | **3D Model** |
| "environment", "gaussian splat", "splat", volumetric | `worldlabs.md` | **Environment** |
| "sprite", "pixel art", "tile", "tileset" | `pixel-art-sprites.md` | **2D Sprite** |
| "image", "texture", "concept art", "icon", chroma key | `fal-ai-image.md` | **Image / Texture** |
| No API key, "free asset", "find model", generation failed | `asset-sources.md` | **Existing Assets** |

## Error Handling

### Error: "GLB loads but model is in T-pose"
Cause: Used `.clone()` instead of `SkeletonUtils.clone()`.
Solution: Replace with `SkeletonUtils.clone(gltf.scene)`. Import from `three/addons/utils/SkeletonUtils.js`.

### Error: "Meshy task stuck in PENDING"
Cause: Invalid API key, quota exceeded, or service issue.
Solution: Verify `MESHY_API_KEY` in `~/.env`. Check quota at app.meshy.ai. If exhausted, use `references/asset-sources.md` fallback. Status: `node scripts/meshy-generate.mjs status <task_id>`

### Error: "Downloaded GLB is 0 bytes or corrupt"
Cause: URL expired (Meshy 3-day limit) or network error.
Solution: Regenerate using prompt from `.meta.json`.

### Error: "Gaussian Splat objects fall through floor"
Cause: Raycast direction inverted after Y-axis flip.
Solution: See `references/worldlabs.md` raycast inversion section.

### Error: "fal.ai returns 401"
Cause: `FAL_KEY` missing or wrong format. fal.ai uses `Key $FAL_KEY`, not `Bearer`.
Solution: Confirm `FAL_KEY` in `~/.env`. Authorization header: `Key <your-key>`.

### Error: "gltf-transform command not found"
Cause: `@gltf-transform/cli` not installed.
Solution: `npm install -g @gltf-transform/cli`

---

## References

| Reference | When to load | Content |
|-----------|-------------|---------|
| `references/meshyai.md` | 3D model request | Meshy API: text-to-3D, image-to-3D, rig, animate, optimize-glb |
| `references/worldlabs.md` | Environment / Gaussian Splat | World Labs Marble API: SPZ generation, SplatMesh, Y-flip |
| `references/fal-ai-image.md` | Image / texture / concept art | fal.ai: 8 model endpoints, queue API, cost tracking, chroma-key |
| `references/asset-sources.md` | No API key or fallback | Sketchfab, Poly Haven, Poly.pizza search and download |
| `references/pixel-art-sprites.md` | 2D sprite / pixel art | Canvas sprite matrices, palette system, animation frames |
