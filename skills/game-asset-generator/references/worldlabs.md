# World Labs Marble API — Gaussian Splat Environments

World Labs generates photorealistic Gaussian Splat environments from images or text. Output is a `.spz` file (Gaussian Splat), a `.glb` collision mesh, and a panorama `.jpg`. Generation takes **3-8 minutes**.

API base: `https://api.worldlabs.ai` (verify current endpoint at platform.worldlabs.ai)
Auth: `WLT-Api-Key: $WLT_API_KEY` header — **not Bearer, not Authorization**.

---

## Authentication

```bash
# Correct header format
curl -H "WLT-Api-Key: $WLT_API_KEY" https://api.worldlabs.ai/...

# Wrong — these do NOT work
# -H "Authorization: Bearer $WLT_API_KEY"
# -H "Authorization: $WLT_API_KEY"
```

Get `WLT_API_KEY` from platform.worldlabs.ai. Add to `~/.env`.

---

## Generation Workflow

### Step 1: Submit Generation Request

Image input is preferred over text-only. An image anchor produces dramatically more coherent geometry.

```bash
# Image-anchored generation (recommended)
curl -X POST https://api.worldlabs.ai/v1/worlds \
  -H "WLT-Api-Key: $WLT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/reference-scene.jpg",
    "prompt": "a medieval castle courtyard at dusk",
    "quality": "full_res"
  }'

# Text-only fallback (less coherent geometry)
curl -X POST https://api.worldlabs.ai/v1/worlds \
  -H "WLT-Api-Key: $WLT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a dense forest clearing with a stream",
    "quality": "500k"
  }'
# Returns: {"world_id": "wld-uuid-here"}
```

**quality tiers**:
- `"100k"` — 100k Gaussians, fast preview, smallest file (~5MB)
- `"500k"` — 500k Gaussians, good quality, mid file (~25MB)
- `"full_res"` — Maximum Gaussians, highest quality, largest file (~100MB+)

### Step 2: Poll for Status

```bash
curl -H "WLT-Api-Key: $WLT_API_KEY" \
  https://api.worldlabs.ai/v1/worlds/WORLD_ID

# Response when complete:
{
  "world_id": "wld-abc123",
  "status": "completed",
  "outputs": {
    "spz": "https://cdn.worldlabs.ai/wld-abc123/scene.spz",
    "glb": "https://cdn.worldlabs.ai/wld-abc123/collision.glb",
    "panorama": "https://cdn.worldlabs.ai/wld-abc123/panorama.jpg"
  }
}
```

Status values: `"queued"`, `"processing"`, `"completed"`, `"failed"`

Poll every 15 seconds. Typical completion: 3-8 minutes.

### Step 3: Download All Three Files

```bash
WORLD_ID="wld-abc123"
mkdir -p public/assets/environments/$WORLD_ID

# Download SPZ (Gaussian Splat data)
curl -o public/assets/environments/$WORLD_ID/scene.spz \
  "$(curl -s -H "WLT-Api-Key: $WLT_API_KEY" \
    https://api.worldlabs.ai/v1/worlds/$WORLD_ID \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['outputs']['spz'])")"

# Download GLB collision mesh
curl -o public/assets/environments/$WORLD_ID/collision.glb \
  "$SPZ_RESPONSE_GLB_URL"

# Download panorama (for skybox / loading screens)
curl -o public/assets/environments/$WORLD_ID/panorama.jpg \
  "$SPZ_RESPONSE_PANORAMA_URL"
```

---

## Three.js Integration

### Renderer: @sparkjsdev/spark SplatMesh

World Labs SPZ files require the `@sparkjsdev/spark` renderer. It drops directly into a Three.js scene.

```bash
npm install @sparkjsdev/spark
```

```javascript
import * as THREE from 'three';
import { SplatMesh } from '@sparkjsdev/spark';

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.01, 1000);
camera.position.set(0, 1.6, 5); // Eye height, looking into scene

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

// Load Gaussian Splat
const splat = new SplatMesh('/assets/environments/wld-abc123/scene.spz');
scene.add(splat);

// CRITICAL: Y-axis flip required — World Labs uses Y-up, but SPZ is Y-down
splat.rotation.x = Math.PI;
splat.updateMatrixWorld(true); // Must call before first raycast
```

### Y-Axis Flip — Required, Not Optional

Without `rotation.x = Math.PI`, the scene renders upside-down. This is not a bug — it is the coordinate system difference between World Labs output (Y-down) and Three.js (Y-up).

```javascript
splat.rotation.x = Math.PI; // Flip to Y-up
splat.updateMatrixWorld(true); // Recompute matrices immediately
```

### Raycast Direction Inversion After Flip

The Y-axis flip inverts the raycast direction. Any collision raycasts against the SPZ mesh or objects within it must negate the Y component of the ray direction.

```javascript
// Standard raycaster setup
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

function onMouseClick(event) {
  mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
  mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

  raycaster.setFromCamera(mouse, camera);

  // CRITICAL: After Y-flip, invert the ray direction Y component
  const dir = raycaster.ray.direction.clone();
  dir.y *= -1; // Invert Y because of rotation.x = Math.PI
  raycaster.ray.direction.copy(dir);

  const intersects = raycaster.intersectObject(splat, true);
}
```

**Alternative**: Load the GLB collision mesh instead of raycasting against the SPZ. The GLB is already in Y-up coordinates (no inversion needed) and is much cheaper to raycast against.

```javascript
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const gltfLoader = new GLTFLoader();
gltfLoader.load('/assets/environments/wld-abc123/collision.glb', (gltf) => {
  const collider = gltf.scene;
  collider.visible = false; // Invisible — only used for raycasting
  scene.add(collider);
  // Raycast against collider, render the SPZ — no direction inversion needed
});
```

### updateMatrixWorld Requirement

Call `splat.updateMatrixWorld(true)` after setting the rotation and before any raycast or intersection test. If omitted, the first few frames may miss intersections or produce incorrect positions.

```javascript
splat.rotation.x = Math.PI;
splat.updateMatrixWorld(true); // Force immediate matrix recompute
```

---

## Animation Loop

```javascript
function animate() {
  requestAnimationFrame(animate);
  splat.update(camera); // Required: SplatMesh sorts Gaussians per frame
  renderer.render(scene, camera);
}
animate();
```

`splat.update(camera)` must be called every frame before `renderer.render()`. SplatMesh sorts the Gaussian splats by depth relative to the camera each frame — skipping this call produces severe rendering artifacts.

---

## Output File Reference

| File | Format | Use |
|------|--------|-----|
| `scene.spz` | Gaussian Splat | Visual rendering via SplatMesh |
| `collision.glb` | Standard GLB | Collision detection, raycasting, physics |
| `panorama.jpg` | Equirectangular JPEG | Skybox, loading screen, thumbnail |

---

## .meta.json Sidecar

```json
{
  "prompt": "a medieval castle courtyard at dusk",
  "image_url": "https://example.com/reference.jpg",
  "world_id": "wld-abc123",
  "quality": "500k",
  "generated_at": "2026-04-04T12:00:00Z",
  "source": "worldlabs",
  "outputs": {
    "spz": "public/assets/environments/wld-abc123/scene.spz",
    "glb": "public/assets/environments/wld-abc123/collision.glb",
    "panorama": "public/assets/environments/wld-abc123/panorama.jpg"
  }
}
```

---

## Error Reference

| Error | Cause | Fix |
|-------|-------|-----|
| 401 Unauthorized | Wrong header format (using Bearer) | Use `WLT-Api-Key:` header, not `Authorization: Bearer` |
| 403 Forbidden | Invalid key | Regenerate key at platform.worldlabs.ai |
| status: "failed" | Generation failed (bad image, timeout) | Check `error_message` in response, retry with different image |
| Scene upside-down | Missing Y-axis flip | Add `splat.rotation.x = Math.PI` |
| Objects fall through floor | Raycast direction not inverted | Negate `raycaster.ray.direction.y` after flip, or use GLB collider |
| SplatMesh rendering artifacts | `splat.update(camera)` not called | Call `splat.update(camera)` every frame before render |
| First raycast misses | `updateMatrixWorld` not called | Call `splat.updateMatrixWorld(true)` after rotation is set |
