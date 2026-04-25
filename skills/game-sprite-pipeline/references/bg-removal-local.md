# Local Background Removal

No paid APIs. No `remove.bg`, no cloud bg-removal services. Three local strategies, all run on the user's machine:

1. **Magenta chroma key** (default; `--bg-mode magenta`) — pure Pillow + numpy. Two-pass despill-aware key plus 1-pixel alpha dilation.
2. **Gray-tolerance** (`--bg-mode gray-tolerance`) — adapted from road-to-aew's production algorithm. Best when the backend paints a gray (#3a3a3a) background instead of honoring the magenta-bg prompt.
3. **rembg** (`--bg-mode rembg`, opt-in) — ONNX U^2-Net model (~200MB). Use only when neither chroma assumption holds.

The chroma key handles the spritesheet workflow because the skill controls the input (prompts for magenta bg, the canvas template paints magenta). The gray-tolerance algorithm is for backends like Gemini Nano Banana that ignore explicit color instructions and paint their own #3a3a3a default. rembg is the fallback for general bg removal when no chroma assumption is reliable.

## Mode selection at a glance

| Backend / scenario | Mode | Why |
|---|---|---|
| Codex CLI image_gen, magenta bg honored | `magenta` (default) | Generator paints true #FF00FF; despill chroma is fastest and cleanest. |
| Codex CLI but the "magenta bg" instruction was ignored | `gray-tolerance` (or `auto`) | Generator picked its own neutral gray; chroma key won't match. |
| Gemini Nano Banana / similar | `gray-tolerance` | road-to-aew has 87 production-clean PNGs with this approach. |
| User-supplied photo / non-game asset | `rembg` | No chroma assumption; ML segmentation handles arbitrary bg. |
| Batch with mixed outputs | `auto` | Tries chroma first; falls through to rembg when alpha coverage <30%. |

CLI selection lives at `sprite_process.py remove-bg` and `sprite_pipeline.py`:

```bash
# default — magenta chroma key with despill + alpha dilation
python3 sprite_process.py remove-bg input.png --output out.png

# gray-tolerance for Gemini-style output
python3 sprite_process.py remove-bg input.png --output out.png --bg-mode gray-tolerance

# tune
python3 sprite_process.py remove-bg input.png --output out.png \
    --bg-mode magenta \
    --chroma-threshold 30 \
    --pass2-threshold 90 \
    --despill-strength 0.5 \
    --alpha-dilate 1
```

## Magenta mode (default)

The skill prompts the backend to produce magenta (`#FF00FF`) backgrounds, then removes magenta in post in three steps: pass 1 tight, pass 2 despill-aware, dilation cleanup.

### Step 1: tight chroma match (pass 1)

```python
def chroma_pass1(
    img: Image.Image,
    chroma: tuple[int, int, int] = (255, 0, 255),
    threshold: int = 30,
) -> Image.Image:
    """Mask pixels within sum-of-abs-diff threshold of chroma."""
    arr = np.array(img.convert("RGBA"))
    rgb = arr[..., :3].astype(int)
    diff = np.abs(rgb - np.array(chroma)).sum(axis=-1)
    mask = diff <= threshold  # True = chroma pixel
    arr[mask, 3] = 0  # set alpha to 0
    return Image.fromarray(arr, "RGBA")
```

This catches solid-magenta backgrounds. It does NOT catch:

- Pixels that are not exactly magenta but are close (faint pink fringing, anti-aliased edges).
- Magenta that has been compressed by JPEG or downsampled.

### Step 2: despill-aware edge flood (pass 2)

```python
def chroma_pass2_edge_flood_despill(
    img: Image.Image,
    chroma: tuple[int, int, int] = (255, 0, 255),
    threshold: int = 90,                  # looser than pass 1
    despill_strength: float = 0.5,
) -> Image.Image:
    """Flood-fill from canvas edges; preserve off-color pixels (despill)."""
    arr = np.array(img.convert("RGBA"))
    h, w = arr.shape[:2]
    visited = np.zeros((h, w), dtype=bool)
    chroma_arr = np.array(chroma)
    despill_cutoff = 20 * despill_strength

    queue = deque()  # all 4 edges seeded
    while queue:
        y, x = queue.popleft()
        if visited[y, x] or not (0 <= y < h and 0 <= x < w):
            continue
        if arr[y, x, 3] == 0:
            visited[y, x] = True
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                queue.append((y + dy, x + dx))
            continue
        rgb = arr[y, x, :3].astype(int)
        diff = int(np.abs(rgb - chroma_arr).sum())
        if diff > threshold:
            continue
        # DESPILL: preserve a near-bg pixel if its RGB is "off-color".
        if despill_strength > 0 and arr[y, x, 3] > 128:
            r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
            color_balance = max(r, g, b) - min(r, g, b)
            if color_balance > despill_cutoff:
                visited[y, x] = True
                continue
        visited[y, x] = True
        arr[y, x, 3] = 0
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            queue.append((y + dy, x + dx))

    return Image.fromarray(arr, "RGBA")
```

#### Why despill?

Anti-aliased edges between magenta and the character produce semi-transparent pixels whose RGB has spilled toward magenta. Naively zeroing those pixels eats the character silhouette; preserving them lets the visible halo persist. Despill checks `max(r,g,b) - min(r,g,b)` — if the channel spread is large, the pixel is a saturated character color that happens to be near the bg threshold (saturated yellows, cyans, greens at the silhouette). Those get preserved. Truly desaturated near-magenta pixels (the fringe) get zeroed.

This lets us safely loosen pass-2 threshold from 60 to 90: the threshold is wider, so we catch more fringe, but despill prevents false positives on character art.

#### Tuning despill

| `despill_strength` | Behavior |
|---|---|
| 0.0 | Despill off. Pure threshold-based pass 2 (legacy behavior). |
| 0.3 | Conservative. Only saturated colors (`color_balance > 6`) protected. |
| **0.5 (default)** | Balanced. Protects most character art (`color_balance > 10`). |
| 1.0 | Aggressive preservation. Protects almost any colored pixel (`color_balance > 20`). |

Increase if pass 2 is biting into character; decrease if halo persists.

### Step 3: alpha-zero dilation

After pass 2, expand the alpha=0 region by 1 pixel (4-connected). This kills the residual halo that survives even pass-2 flood-fill on anti-aliased generator output.

```python
def dilate_alpha_zero(arr: np.ndarray, radius: int = 1) -> np.ndarray:
    alpha = arr[..., 3]
    mask = alpha == 0
    for _ in range(radius):
        shifted = np.zeros_like(mask)
        shifted[1:, :] |= mask[:-1, :]
        shifted[:-1, :] |= mask[1:, :]
        shifted[:, 1:] |= mask[:, :-1]
        shifted[:, :-1] |= mask[:, 1:]
        mask = mask | shifted
    arr[..., 3] = np.where(mask, 0, alpha)
    return arr
```

Pure numpy. No scipy. Radius=1 is enough for almost every case; radius=2 if the halo spans 2+ pixels (unusual; usually means upstream is wrong).

#### Tuning the dilation

| Radius | Use when |
|---|---|
| 0 | Disable. Use when the chroma key is already clean and you want pixel-perfect silhouettes. |
| **1 (default)** | Most generator output. Removes 1-pixel anti-aliased halo. |
| 2+ | Only if you can see a 2+ pixel halo after pass 2. Investigate the generator first. |

### Combined defaults

```bash
python3 sprite_process.py remove-bg input.png --output out.png \
    --chroma-threshold 30 \
    --pass2-threshold 90 \
    --despill-strength 0.5 \
    --alpha-dilate 1
```

These defaults are calibrated against the live demo (8 spritesheets, 200+ frames). Tune `pass2-threshold` first if you see halo or biting; tune `despill-strength` second; tune `alpha-dilate` last.

## Gray-tolerance mode

Adapted from `~/road-to-aew/scripts/generate_enemy_sprite.py` lines 1048-1128 (`remove_watermark` + `make_background_transparent`). The road-to-aew project has produced 87 clean transparent PNGs in production with this algorithm — it's earned its place as our secondary mode.

### The two-step algorithm

```python
BG_COLOR = (58, 58, 58)        # #3a3a3a — Gemini Nano Banana default bg
BG_TOLERANCE = 30              # per-channel abs-diff
WATERMARK_MARGIN = 40          # corner box size in pixels
WATERMARK_BRIGHTNESS = 180     # mean(R,G,B) > this = "bright" pixel

def remove_watermark_corners(img, bg_color, margin, brightness=180):
    """Step 1: paint bright corner pixels back to bg_color."""
    # The four corner boxes (margin x margin each) get scanned.
    # Any pixel with mean(R,G,B) > brightness gets repainted to bg_color.
    # This kills Gemini's "made by..." watermark BEFORE step 2 sees it.

def gray_tolerance_to_alpha(img, bg_color, tolerance):
    """Step 2: any pixel within ±tolerance of bg_color (per-channel) gets alpha=0."""
    arr = np.array(img.convert("RGBA"))
    rgb = arr[..., :3].astype(int)
    bg = np.array(bg_color, dtype=int)
    within = np.all(np.abs(rgb - bg) <= tolerance, axis=-1)
    arr[within, 3] = 0
    return Image.fromarray(arr, "RGBA")
```

Step 1 (watermark cleanup) only matters when the backend paints a watermark in a corner. For backends that don't, it's a cheap no-op.

Step 2 is a per-channel tolerance check. It's looser than chroma sum-of-abs-diff because Gemini's gray bg has more channel variance (compression / dithering). Per-channel `±30` is the sweet spot road-to-aew settled on after iteration.

The same alpha dilation step (radius=1) runs after step 2.

### Tuning gray-tolerance

| Parameter | Default | Adjust if |
|---|---|---|
| `--gray-bg R G B` | `58 58 58` | Backend paints a different gray (e.g. `64 64 64`). |
| `--gray-tolerance` | 30 | Halo persists → 40; biting into character → 20. |
| `--watermark-margin` | 40 | Watermark in larger corner area → 60. Set to 0 to skip step 1. |
| `--alpha-dilate` | 1 | Same tuning as magenta mode. |

### When to use which mode

```
Did the backend paint magenta as instructed?
├── YES → --bg-mode magenta (default)
├── NO, painted gray → --bg-mode gray-tolerance
└── NO, painted white/photo → --bg-mode rembg
```

The skill's `auto` mode handles the first uncertainty: chroma first, fall through to rembg if alpha coverage <30%. But auto does NOT try gray-tolerance — that's a deliberate user choice based on the backend.

## rembg (opt-in)

`rembg` is a Python package wrapping a pre-trained ONNX model that segments foreground from background without chroma assumptions. Useful when:

- The backend produced a non-magenta, non-gray background.
- The character has magenta in their actual design (showman archetype with magenta gear) AND the bg isn't gray either.
- General-purpose cleanup of arbitrary user-supplied images.

Install:

```bash
pip install rembg onnxruntime
```

The first call downloads the U^2-Net or BiRefNet model (~200MB) to `~/.u2net/`. After that, it runs locally.

Usage is gated by import — the skill never installs rembg silently.

## Performance

| Mode | 256x256 | 1024x1024 |
|------|---------|-----------|
| Magenta pass-1 only | ~30ms | ~500ms |
| Magenta pass-1+2 (despill) | ~80ms | ~1500ms |
| Magenta full (+ dilate) | ~85ms | ~1550ms |
| Gray-tolerance (numpy) | ~25ms | ~450ms |
| Gray-tolerance + dilate | ~30ms | ~500ms |
| rembg (CPU) | ~1500ms | ~12000ms |
| rembg (GPU via onnxruntime-gpu) | ~200ms | ~1200ms |

For a 16-frame walk cycle (256×256 each), magenta full takes ~1.4s; gray-tolerance ~0.5s; rembg ~24s on CPU. Default to chroma; opt into rembg only when chroma fails.

## Validation

After bg removal, the dominant corner color should be transparent:

```python
def validate_alpha(img: Image.Image) -> None:
    arr = np.array(img.convert("RGBA"))
    h, w = arr.shape[:2]
    corners = [arr[0, 0], arr[0, w-1], arr[h-1, 0], arr[h-1, w-1]]
    for color in corners:
        if color[3] != 0:
            warn(f"corner not transparent: alpha={color[3]}")
```

A non-transparent corner usually means the chroma threshold is too tight or the bg color was something other than magenta. With gray-tolerance mode, a non-transparent corner means the bg color guess (`#3a3a3a`) was wrong — try `--gray-bg 64 64 64` or measure the corner pixel directly.

## Forbidden paths

The skill MUST NOT call any of:

- `remove.bg` API (`api.remove.bg/v1.0/removebg`)
- `removebg` Python package that wraps the above
- `clipdrop.co` API
- Any cloud service that takes an image URL and returns a no-bg image

The grep gate (`grep -rE 'remove\.bg|REMOVEBG|clipdrop' skills/game-sprite-pipeline/`) must return no matches.

## Acknowledgement

The gray-tolerance algorithm and watermark-corner cleanup are adapted from `~/road-to-aew/scripts/generate_enemy_sprite.py` (Andy Nemmity, 2025). That project produces 87 clean transparent enemy PNGs in production. The despill addition to pass 2 is original to this skill, calibrated against the live demo's anti-aliased Codex output.

<!-- no-pair-required: section header; pair lives in subsection -->
## Anti-pattern

### Anti-pattern: Calling a cloud bg-removal service

**What it looks like:** `requests.post('https://api.remove.bg/v1.0/removebg', files={'image_file': open(path, 'rb')}, headers={'X-Api-Key': KEY})`.

**Why wrong:** Paid API call, requires a key the user did not authorize. Violates the Local-First principle — the user expects free-tier behavior because the skill says "local-first"; their card gets charged.

**Do instead**: Use chroma key (free, fast, deterministic) by default. Use rembg (free, local, slower) as opt-in fallback. Never reach for a cloud service for what is fundamentally a pixel-classification problem.

### Anti-pattern: Single-pass chroma with no edge flood

**What it looks like:** Just `arr[matches_chroma] = transparent` and shipping the output.

**Why wrong:** Anti-aliased edges between magenta and the character produce intermediate pink shades that don't match the chroma threshold exactly. These survive and form a visible halo around the character. Downstream consumers see "magenta-tinted edges" and the character looks dirty.

**Do instead**: Two-pass with despill: pass 1 catches solid magenta; pass 2 flood-fills from edges with looser threshold and despill (preserving off-color pixels at the fringe); 1-pixel alpha dilation kills the residual halo. Pillow + numpy is enough; no extra deps.

### Anti-pattern: Skipping despill on pass 2

**What it looks like:** Bumping pass-2 threshold above 60 without despill; output looks "eaten" — character silhouette has chunks missing where saturated colors lived.

**Why wrong:** Loose pass 2 catches everything within the wider band, including fully-opaque saturated character pixels that happen to have a magenta-ish hue (a luchador's pink tights, a deep-purple cape near magenta).

**Do instead**: Keep despill at 0.5 minimum when pass-2 threshold > 60. Despill checks `max(rgb) - min(rgb)` — saturated character pixels have high spread (yellow has spread 255; off-magenta gray fringe has spread <20) and stay visible.

### Anti-pattern: Skipping alpha dilation on a "clean" output

**What it looks like:** Trusting a clean-looking pass 2 result and shipping; downstream consumers report a faint 1-pixel halo at the silhouette.

**Why wrong:** The chroma key thresholds are calibrated against direct color, but anti-aliased pixels with low alpha can still be visible against light backgrounds. A 1-pixel dilation of the alpha=0 region effectively strips those translucent pixels. Cost: invisible (~5ms / 1024px image).

**Do instead**: Ship `--alpha-dilate 1` by default. Only set to 0 when you specifically need pixel-perfect silhouettes for tooling that does its own anti-aliasing.

## Reference loading hint

Load when:
- Phase B or Phase E (bg removal) is active
- Output has visible magenta halos
- Choosing between `--bg-mode magenta` and `--bg-mode gray-tolerance`
- Considering rembg for difficult subjects
- Investigating a paid-API leakage finding (the grep gate flagged something)
