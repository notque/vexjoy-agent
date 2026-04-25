# Local Background Removal

No paid APIs. No `remove.bg`, no cloud bg-removal services. Two approaches, both run on the user's machine:

1. **Magenta chroma key** — default. Pure Pillow, no extra deps.
2. **rembg** — opt-in. Uses an ONNX model (~200MB download once) for general bg removal.

The chroma key handles the spritesheet workflow because the skill controls the input (prompts for magenta bg, the canvas template paints magenta). rembg is the opt-in fallback for cases where the backend ignored the magenta-bg instruction.

## Magenta chroma key (two-pass)

The skill prompts the backend to produce magenta (`#FF00FF`) backgrounds, then removes magenta in post.

### Pass 1: direct chroma match

```python
def remove_chroma_pass1(
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

### Pass 2: edge flood fill

```python
def remove_chroma_pass2(
    img: Image.Image,
    chroma: tuple[int, int, int] = (255, 0, 255),
    threshold: int = 60,  # looser than pass 1
) -> Image.Image:
    """Flood-fill from canvas edges, treating chroma-adjacent pixels as background."""
    arr = np.array(img.convert("RGBA"))
    h, w = arr.shape[:2]
    visited = np.zeros((h, w), dtype=bool)

    def is_chroma_adjacent(y, x):
        if visited[y, x] or arr[y, x, 3] == 0:
            return False
        rgb = arr[y, x, :3].astype(int)
        diff = np.abs(rgb - np.array(chroma)).sum()
        return diff <= threshold

    # BFS from every edge pixel
    from collections import deque
    queue = deque()
    for y in (0, h - 1):
        for x in range(w):
            queue.append((y, x))
    for x in (0, w - 1):
        for y in range(h):
            queue.append((y, x))

    while queue:
        y, x = queue.popleft()
        if not (0 <= y < h and 0 <= x < w):
            continue
        if not is_chroma_adjacent(y, x):
            continue
        visited[y, x] = True
        arr[y, x, 3] = 0
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            queue.append((y + dy, x + dx))

    return Image.fromarray(arr, "RGBA")
```

Why two passes:

- Pass 1: tight threshold catches the bulk solid magenta cleanly without bleeding into character pixels.
- Pass 2: flood from edges with looser threshold catches feathered magenta that didn't match pass 1 exactly, but only where it's contiguous with the canvas edge — interior magenta-ish pixels (e.g., a magenta gem in the character's gear) survive.

The combined effect: clean alpha channel, no magenta fringe, character-internal near-magenta colors preserved.

### Tuning

| Parameter | Default | Adjust if |
|-----------|---------|-----------|
| `pass1_threshold` | 30 | Magenta is exactly `#FF00FF` and uncompressed → 15; output has visible halo → increase to 50 |
| `pass2_threshold` | 60 | Pass 2 bites into character → decrease to 40; halo persists → increase to 80 |

`--chroma-threshold` flag controls pass 1; pass 2 is automatically `2 × pass1`.

## rembg (opt-in)

`rembg` is a Python package wrapping a pre-trained ONNX model that segments foreground from background without chroma assumptions. Useful when:

- The backend produced a non-magenta background despite the prompt.
- The character has magenta in their actual design (showman archetype with magenta gear).

Install:

```bash
pip install rembg onnxruntime
```

The first call downloads the U^2-Net or BiRefNet model (~200MB) to `~/.u2net/`. After that, it runs locally.

Usage:

```python
def remove_bg_rembg(input_path: Path, output_path: Path) -> None:
    try:
        from rembg import remove
    except ImportError as e:
        raise RuntimeError(
            "rembg not installed. Run `pip install rembg onnxruntime`, "
            "or use --bg-mode chroma (default)."
        ) from e

    with input_path.open("rb") as i:
        data = i.read()
    output = remove(data)
    output_path.write_bytes(output)
```

The skill exposes `--bg-mode {chroma|rembg|auto}`:

- `chroma` (default) — pure chroma key.
- `rembg` — rembg only.
- `auto` — chroma first; if the resulting alpha mask covers <30% of the canvas, fall back to rembg automatically.

`auto` mode is useful for batch runs where some characters have legitimate magenta in their gear and the chroma key bites too hard.

## Performance

| Mode | Speed (256x256) | Speed (1024x1024) |
|------|-----------------|-------------------|
| Chroma 1-pass | ~30ms | ~500ms |
| Chroma 2-pass | ~80ms | ~1500ms |
| rembg (CPU) | ~1500ms | ~12000ms |
| rembg (GPU via onnxruntime-gpu) | ~200ms | ~1200ms |

For a 16-frame walk cycle (256×256 each), 2-pass chroma takes ~1.3s. rembg takes ~24s on CPU. Default to chroma; opt into rembg only when chroma fails.

## Validation

After bg removal, the dominant corner color should be transparent:

```python
def validate_alpha(img: Image.Image) -> None:
    arr = np.array(img.convert("RGBA"))
    h, w = arr.shape[:2]
    corners = [arr[0, 0], arr[0, w-1], arr[h-1, 0], arr[h-1, w-1]]
    for cy, cx, color in zip([0,0,h-1,h-1], [0,w-1,0,w-1], corners):
        if color[3] != 0:
            warn(f"corner ({cy},{cx}) not transparent: alpha={color[3]}")
```

A non-transparent corner usually means the chroma threshold is too tight or the bg color was something other than magenta.

## Forbidden paths

The skill MUST NOT call any of:

- `remove.bg` API (`api.remove.bg/v1.0/removebg`)
- `removebg` Python package that wraps the above
- `clipdrop.co` API
- Any cloud service that takes an image URL and returns a no-bg image

The grep gate (`grep -rE 'remove\.bg|REMOVEBG|clipdrop' skills/game-sprite-pipeline/`) must return no matches.

<!-- no-pair-required: section header; pair lives in subsection -->
## Anti-pattern

### Anti-pattern: Calling a cloud bg-removal service

**What it looks like:** `requests.post('https://api.remove.bg/v1.0/removebg', files={'image_file': open(path, 'rb')}, headers={'X-Api-Key': KEY})`.

**Why wrong:** Paid API call, requires a key the user did not authorize. Violates the Local-First principle — the user expects free-tier behavior because the skill says "local-first"; their card gets charged.

**Do instead**: Use chroma key (free, fast, deterministic) by default. Use rembg (free, local, slower) as opt-in fallback. Never reach for a cloud service for what is fundamentally a pixel-classification problem.

### Anti-pattern: Single-pass chroma with no edge flood

**What it looks like:** Just `arr[matches_chroma] = transparent` and shipping the output.

**Why wrong:** Anti-aliased edges between magenta and the character produce intermediate pink shades that don't match the chroma threshold exactly. These survive and form a visible halo around the character. Downstream consumers see "magenta-tinted edges" and the character looks dirty.

**Do instead**: Two-pass: pass 1 catches solid magenta; pass 2 flood-fills from edges with looser threshold, picking up feathered fringe without biting into character interior. Pillow + numpy is enough; no extra deps.

## Reference loading hint

Load when:
- Phase B or Phase E (bg removal) is active
- Output has visible magenta halos
- Considering rembg for difficult subjects
- Investigating a paid-API leakage finding (the grep gate flagged something)
