# Free 3D Asset Sources

Fallback chain when no API key is available or generation fails. All sources output GLB (or provide GLB download) so the game's asset loader doesn't change.

**Order of preference**:
1. Sketchfab — largest library, best quality, requires `SKETCHFAB_TOKEN` for download
2. Poly Haven — CC0 licensed, no account needed, HDRIs + models + textures
3. Poly.pizza — free low-poly game assets, requires `POLY_PIZZA_API_KEY` for search API
4. BoxGeometry placeholder — always works, no download needed

---

## Sketchfab

Largest free 3D model library. Search is public. Download requires `SKETCHFAB_TOKEN`.

Get token: sketchfab.com/settings/password (API token section). Add to `~/.env` as `SKETCHFAB_TOKEN`.

### Search (Public, No Token Needed)

```bash
# Search for free, downloadable models
curl "https://api.sketchfab.com/v3/models?q=warrior+character&type=models&downloadable=true&license=by&sort_by=-likeCount&count=10" \
  | python3 -m json.tool | grep -E '"name"|"uid"|"likeCount"'

# Search parameters:
# q=<search term>
# downloadable=true — only models with download enabled
# license=by — CC Attribution (most permissive free license)
#   other values: by-sa, by-nd, by-nc, by-nc-sa, by-nc-nd, cc0
# sort_by=-likeCount — most popular first
# count=10 — results per page
```

### Check Download Formats

```bash
curl -H "Authorization: Token $SKETCHFAB_TOKEN" \
  "https://api.sketchfab.com/v3/models/MODEL_UID/download"

# Returns available formats:
# gltf, glb, usd, fbx, obj, stl, ply, x3d, bim, abc
# Always request "glb" — it's self-contained with textures
```

### Download GLB

```bash
MODEL_UID="abc123def456"

# Step 1: Get download URL
DOWNLOAD_URL=$(curl -s -H "Authorization: Token $SKETCHFAB_TOKEN" \
  "https://api.sketchfab.com/v3/models/$MODEL_UID/download" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['glb']['url'])")

# Step 2: Download (redirects to CDN)
curl -L -o "public/assets/$MODEL_UID.glb" "$DOWNLOAD_URL"
echo "Downloaded: public/assets/$MODEL_UID.glb"
```

### Save .meta.json

```json
{
  "source": "sketchfab",
  "model_uid": "abc123def456",
  "model_name": "Fantasy Warrior",
  "license": "CC-BY-4.0",
  "author": "artist_username",
  "sketchfab_url": "https://sketchfab.com/3d-models/fantasy-warrior-abc123def456",
  "downloaded_at": "2026-04-04T12:00:00Z",
  "output_path": "public/assets/abc123def456.glb"
}
```

---

## Poly Haven

CC0 licensed — no attribution required. HDRIs, models, and textures. No API key needed for downloads.

Site: polyhaven.com | API: api.polyhaven.com

### Search Assets

```bash
# List all free models (type=models)
curl "https://api.polyhaven.com/assets?type=models" \
  | python3 -c "import sys,json; assets=json.load(sys.stdin); [print(k,v['name']) for k,v in list(assets.items())[:20]]"

# Search by category (no keyword search in API — browse by type)
# type options: hdris | textures | models
curl "https://api.polyhaven.com/assets?type=hdris" | python3 -m json.tool | head -50
```

### Get Asset Details and Download URL

```bash
ASSET_ID="medieval_barrel"

# Get asset info
curl "https://api.polyhaven.com/info/$ASSET_ID" | python3 -m json.tool

# Get download files (lists all formats and resolutions)
curl "https://api.polyhaven.com/files/$ASSET_ID" \
  | python3 -c "
import sys, json
files = json.load(sys.stdin)
# For models: look for blend or gltf
if 'blend' in files:
    for res, data in files['blend'].items():
        print(f'BLEND {res}:', data['url'])
if 'gltf' in files:
    for res, data in files['gltf'].items():
        print(f'GLTF {res}:', data['url'])
"
```

### Download HDRI (for skybox/environment lighting)

```bash
HDRI_ID="studio_small_09"
RESOLUTION="1k"  # options: 1k, 2k, 4k, 8k, 16k

curl -o "public/assets/hdri/$HDRI_ID-$RESOLUTION.hdr" \
  "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/$RESOLUTION/$HDRI_ID_$RESOLUTION.hdr"
```

### Use in Three.js

```javascript
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';

const rgbeLoader = new RGBELoader();
rgbeLoader.load('/assets/hdri/studio_small_09-1k.hdr', (texture) => {
  texture.mapping = THREE.EquirectangularReflectionMapping;
  scene.environment = texture; // Used for PBR reflections
  scene.background = texture; // Optional: show as skybox
});
```

---

## Poly.pizza

Free low-poly game assets. Optimized for web games — files are already small. Requires `POLY_PIZZA_API_KEY` for the search API.

Get key: poly.pizza (create account, find API key in settings). Add to `~/.env` as `POLY_PIZZA_API_KEY`.

### Search

```bash
curl "https://api.poly.pizza/v1/models?query=warrior&limit=10" \
  -H "X-Api-Key: $POLY_PIZZA_API_KEY" \
  | python3 -m json.tool | grep -E '"Title"|"ID"|"Download"'

# Response per result:
# "ID": "model-uuid",
# "Title": "Warrior Character",
# "Download": "https://poly.pizza/m/model-uuid/download/glb"
```

### Download GLB

```bash
MODEL_ID="abc-123-def"

curl -L -o "public/assets/$MODEL_ID.glb" \
  -H "X-Api-Key: $POLY_PIZZA_API_KEY" \
  "https://poly.pizza/m/$MODEL_ID/download/glb"
```

Poly.pizza GLBs are low-poly by design — typically 500-5000 triangles. No post-processing needed.

---

## BoxGeometry Placeholder

When all sources fail or no network is available. Always works. Replace with real asset when available.

```javascript
// Drop-in placeholder that matches the API of a loaded model
function createPlaceholderModel(name = 'placeholder') {
  const group = new THREE.Group();
  group.name = name;

  // Body
  const bodyGeo = new THREE.BoxGeometry(0.5, 1, 0.3);
  const bodyMat = new THREE.MeshStandardMaterial({ color: 0x888888 });
  const body = new THREE.Mesh(bodyGeo, bodyMat);
  body.position.y = 0.5;
  group.add(body);

  // Head
  const headGeo = new THREE.BoxGeometry(0.35, 0.35, 0.35);
  const head = new THREE.Mesh(headGeo, bodyMat);
  head.position.y = 1.175;
  group.add(head);

  // Mark as placeholder for easy replacement
  group.userData.isPlaceholder = true;
  group.userData.replacementPrompt = `Generate a 3D model for: ${name}`;

  return group;
}

// Usage — same interface as GLTFLoader callback
const model = createPlaceholderModel('warrior');
scene.add(model);
// Later: replace with real asset by removing placeholder and loading GLB
```

---

## Fallback Chain Implementation

```javascript
async function loadGameAsset(assetName, prompt) {
  const outputPath = `public/assets/${assetName}.glb`;

  // 1. Try Meshy generation (if key available and not already cached)
  if (process.env.MESHY_API_KEY && !fs.existsSync(outputPath)) {
    try {
      await generateWithMeshy(prompt, outputPath);
      return outputPath;
    } catch (e) {
      console.warn('Meshy failed:', e.message);
    }
  }

  // 2. Try Sketchfab search + download
  if (process.env.SKETCHFAB_TOKEN) {
    try {
      const uid = await searchSketchfab(assetName);
      await downloadSketchfabGLB(uid, outputPath);
      return outputPath;
    } catch (e) {
      console.warn('Sketchfab failed:', e.message);
    }
  }

  // 3. Try Poly.pizza
  if (process.env.POLY_PIZZA_API_KEY) {
    try {
      const id = await searchPolyPizza(assetName);
      await downloadPolyPizzaGLB(id, outputPath);
      return outputPath;
    } catch (e) {
      console.warn('Poly.pizza failed:', e.message);
    }
  }

  // 4. BoxGeometry placeholder — always succeeds
  console.warn(`Using placeholder for ${assetName}. Run asset generation when API keys are configured.`);
  return null; // Caller creates placeholder geometry
}
```

---

## License Reference

| Source | License | Attribution Required | Commercial OK |
|--------|---------|---------------------|---------------|
| Sketchfab (CC0) | CC0 | No | Yes |
| Sketchfab (CC-BY) | CC-BY-4.0 | Yes, credit author | Yes |
| Sketchfab (CC-BY-SA) | CC-BY-SA-4.0 | Yes, share-alike | Yes |
| Sketchfab (CC-BY-NC) | CC-BY-NC-4.0 | Yes | **No** |
| Poly Haven | CC0 | No | Yes |
| Poly.pizza | Free for personal/commercial | No | Yes (check per-asset) |

Always check individual asset licenses before shipping in a commercial product.
