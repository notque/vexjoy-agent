# Meshy AI 3D Pipeline

Meshy AI generates 3D models from text or images, rigs humanoids, and animates them. API endpoint: `https://api.meshy.ai`. Auth: `Authorization: Bearer $MESHY_API_KEY`.

All requests require `MESHY_API_KEY` from `~/.env`. Assets are retained for **3 days only** — download GLB files immediately after generation completes.

---

## Text-to-3D (Two-Step Pipeline)

Generation is always two steps: **preview** (fast, low-poly, confirms the prompt works) then **refine** (full quality). Never skip the preview step — it validates the prompt before spending refine credits.

### Step 1: Submit Preview

```bash
curl -X POST https://api.meshy.ai/openapi/v2/3d-model-preview \
  -H "Authorization: Bearer $MESHY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "object_prompt": "a fantasy warrior with a sword and shield",
    "style_prompt": "game-ready, low-poly, PBR textures",
    "art_style": "realistic",
    "should_remesh": true
  }'
# Returns: {"result": "task-uuid-here"}
```

**art_style options**: `realistic`, `cartoon`, `low-poly`, `sculpture`, `pbr`

### Step 2: Poll Preview Status

```bash
curl -H "Authorization: Bearer $MESHY_API_KEY" \
  https://api.meshy.ai/openapi/v2/3d-model-preview/TASK_ID
# Returns status: PENDING | IN_PROGRESS | SUCCEEDED | FAILED
# On SUCCEEDED: response includes model_urls.glb
```

Poll every 5 seconds. Preview typically completes in 30-90 seconds.

### Step 3: Submit Refine (using preview task ID)

```bash
curl -X POST https://api.meshy.ai/openapi/v2/3d-model \
  -H "Authorization: Bearer $MESHY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "preview_task_id": "PREVIEW_TASK_ID",
    "enable_pbr": true,
    "texture_richness": "high"
  }'
# Returns: {"result": "refine-task-uuid"}
```

### Step 4: Poll Refine and Download

```bash
curl -H "Authorization: Bearer $MESHY_API_KEY" \
  https://api.meshy.ai/openapi/v2/3d-model/REFINE_TASK_ID
# On SUCCEEDED: response.model_urls.glb = download URL
```

Refine takes 2-5 minutes. Download the GLB immediately on SUCCEEDED.

### Full Script (non-blocking)

Use `scripts/meshy-generate.mjs` for polling logic. Quick inline version:

```bash
# Submit and save task ID
TASK=$(curl -s -X POST https://api.meshy.ai/openapi/v2/3d-model-preview \
  -H "Authorization: Bearer $MESHY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"object_prompt":"warrior","art_style":"realistic","should_remesh":true}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['result'])")
echo "Task ID: $TASK"

# Poll until done (check manually or use the script)
node scripts/meshy-generate.mjs status $TASK
```

---

## Image-to-3D

Takes an image (URL, local file path, or base64) and generates a 3D model from it. Faster than text-to-3D when you have reference art.

```bash
# From URL
curl -X POST https://api.meshy.ai/openapi/v2/image-to-3d \
  -H "Authorization: Bearer $MESHY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/character.png",
    "enable_pbr": true,
    "should_remesh": true
  }'

# From local file (base64 encode)
B64=$(base64 -w 0 /path/to/image.png)
curl -X POST https://api.meshy.ai/openapi/v2/image-to-3d \
  -H "Authorization: Bearer $MESHY_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"image_url\": \"data:image/png;base64,$B64\", \"enable_pbr\": true}"
```

Poll at `https://api.meshy.ai/openapi/v2/image-to-3d/TASK_ID` same as text-to-3D.

**Image requirements**: Clear subject on solid or transparent background, square or near-square aspect ratio preferred, PNG with transparency works best.

---

## Rigging (Humanoids Only)

Auto-rigging creates a skeleton for animation. **Only works if all conditions are met**:
- Bipedal (two legs, two arms, one head)
- Textured (not solid color)
- Clearly defined limbs (no capes/skirts covering legs, no merged geometry)
- Standing upright in a T-pose or A-pose

```bash
curl -X POST https://api.meshy.ai/openapi/v1/3d-model/TASK_ID/rig \
  -H "Authorization: Bearer $MESHY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"skeleton_type": "humanoid"}'
# Returns: {"result": "rig-task-uuid"}
```

Poll at `https://api.meshy.ai/openapi/v1/3d-model-rig/RIG_TASK_ID`. Download the rigged GLB on SUCCEEDED.

**Do not attempt rigging if**: the model is a vehicle, creature (non-bipedal), environment piece, or weapon/prop. The API will reject it or produce a broken skeleton.

---

## Animation

Animate a rigged model with preset motions. Requires a successfully rigged GLB task ID.

```bash
curl -X POST https://api.meshy.ai/openapi/v1/3d-model/RIG_TASK_ID/animate \
  -H "Authorization: Bearer $MESHY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "animation_preset": "walk"
  }'
# animation_preset options: "walk" | "run" | "idle" | "jump" | "dance"
```

Poll at `https://api.meshy.ai/openapi/v1/3d-model-animation/ANIM_TASK_ID`. The resulting GLB includes embedded animation clips.

---

## Status Polling

```bash
# Check any task by type and ID
node scripts/meshy-generate.mjs status <task_id>

# Or raw curl for any endpoint
curl -H "Authorization: Bearer $MESHY_API_KEY" \
  "https://api.meshy.ai/openapi/v2/3d-model/TASK_ID"
```

Status values: `PENDING` (queued), `IN_PROGRESS` (generating), `SUCCEEDED` (done), `FAILED` (error — check `task_error.message`).

---

## Post-Processing: GLB Optimization

Run after every Meshy download. Reduces file size 80-95% via texture compression and mesh quantization.

```bash
node scripts/optimize-glb.mjs input.glb output-optimized.glb
```

The script runs `gltf-transform` with:
- Texture resize to 1024x1024 max
- WebP conversion (vs PNG/JPEG)
- Meshopt compression (quantization + filter)
- Dedup + prune for clean output

Requires `@gltf-transform/cli`: `npm install -g @gltf-transform/cli`

---

## .meta.json Sidecar

Save alongside every downloaded GLB:

```json
{
  "prompt": "a fantasy warrior with a sword and shield",
  "style": "realistic",
  "preview_task_id": "abc123",
  "refine_task_id": "def456",
  "rig_task_id": "ghi789",
  "anim_task_id": "jkl012",
  "animation_preset": "walk",
  "generated_at": "2026-04-04T12:00:00Z",
  "source": "meshyai",
  "original_url": "https://assets.meshy.ai/...",
  "expires_at": "2026-04-07T12:00:00Z"
}
```

`expires_at` is 3 days from generation. If the GLB is lost, resubmit using `prompt` and `style`.

---

## Fallback Chain

When Meshy fails or `MESHY_API_KEY` is missing:

1. Meshy API (text-to-3D or image-to-3D)
2. Sketchfab search (see `references/asset-sources.md`)
3. Poly.pizza search (see `references/asset-sources.md`)
4. `new THREE.BoxGeometry(1,1,1)` placeholder (always works, no download needed)

All fallbacks write to the same output path. The game's asset loader does not care which fallback was used.

---

## Error Reference

| Error | Cause | Fix |
|-------|-------|-----|
| 401 Unauthorized | Invalid or missing `MESHY_API_KEY` | Check `~/.env`, regenerate at app.meshy.ai |
| 402 Payment Required | Credit quota exhausted | Buy credits or use fallback chain |
| task_error: "Invalid prompt" | Prompt violates content policy | Rephrase without weapons/violence details |
| task_error: "Rigging failed" | Model doesn't meet humanoid criteria | Skip rigging, use un-rigged GLB |
| 0-byte GLB download | URL expired (>3 days) | Regenerate using `.meta.json` prompt |
| PENDING indefinitely (>10 min) | Service overload | Retry or use fallback chain |
