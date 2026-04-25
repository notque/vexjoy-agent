# Frame Detection (Connected Components)

Phase D of the spritesheet pipeline. Connected-components clustering replaces naive grid-math cropping. The article's key technical insight: generated frames drift within their cells, so cell-bbox crops capture neighbor pixels and truncate the current sprite.

## The algorithm

```
1. Load the raw spritesheet PNG (RGBA, magenta bg).
2. Build a binary mask: True for non-magenta pixels (chroma threshold T), False otherwise.
3. Run 2-connectivity (4-neighbor) flood fill from each unvisited True pixel.
4. Each flood-fill pass forms one cluster (component).
5. For each component:
   a. Compute its pixel-extent bounding box.
   b. Reject components below MIN_COMPONENT_PIXELS (filter fragments).
6. Sort components by (top, left) — top-to-bottom, left-to-right reading order.
7. Map components to grid cells by their centroid → cell-index lookup.
```

The output is one cropped PNG per component, named by its target grid index (`<name>_frame_00.png`, `_frame_01.png`, ...).

## Why connected components?

Grid math:
```
frame = sheet.crop((c*CELL, r*CELL, (c+1)*CELL, (r+1)*CELL))
```

This breaks because:

1. The model places frames slightly off-cell — drift is typically ±5-15% of cell size.
2. A drifted character's edge falls inside the next cell's bbox, contaminating the neighbor.
3. The current cell's edge crops the character's silhouette mid-pixel.

Connected components find the actual character in pixel space, regardless of its cell-relative position.

## Pseudocode

```python
import numpy as np
from PIL import Image

def extract_frames(
    sheet_path: Path,
    grid_cols: int,
    grid_rows: int,
    chroma_color: tuple[int, int, int] = (255, 0, 255),
    chroma_threshold: int = 30,
    min_component_pixels: int = 200,
) -> list[Image.Image]:
    """Extract frames via connected-components clustering."""
    img = Image.open(sheet_path).convert("RGBA")
    arr = np.array(img)

    # Binary mask: True where pixel is NOT chroma color (within threshold)
    chroma = np.array(chroma_color)
    diff = np.abs(arr[..., :3].astype(int) - chroma).sum(axis=-1)
    mask = diff > chroma_threshold

    # 4-connected component labeling
    labels = label_connected_components(mask)  # custom or scipy.ndimage.label

    components: list[Image.Image] = []
    for label_id in range(1, labels.max() + 1):
        ys, xs = np.where(labels == label_id)
        if len(ys) < min_component_pixels:
            continue  # filter fragments

        top, bot = ys.min(), ys.max() + 1
        left, right = xs.min(), xs.max() + 1
        crop = img.crop((left, top, right, bot))
        components.append(crop)

    # Sort top-to-bottom, left-to-right by bounding-box top-left
    components.sort(key=lambda c: (
        c.getbbox()[1] if c.getbbox() else 0,
        c.getbbox()[0] if c.getbbox() else 0,
    ))

    expected = grid_cols * grid_rows
    if len(components) != expected:
        raise FrameCountMismatchError(
            f"detected {len(components)} components, grid expected {expected}"
        )

    return components
```

`scipy.ndimage.label` is the preferred connected-components implementation. If scipy is not installed, the pure-Python fallback (BFS queue per seed pixel) is ~10x slower but correct.

## Tuning parameters

| Parameter | Default | Adjust if |
|-----------|---------|-----------|
| `chroma_threshold` | 30 (RGB sum-of-abs-diff) | Magenta fringing → increase; legitimate magenta-adjacent pixels lost → decrease |
| `min_component_pixels` | 200 | Detection picks up fragments (eyes, glints) → increase to ~500; small details lost → decrease |
| `connectivity` | 4-neighbor | Components fragment on diagonal-only links → use 8-neighbor (`scipy.ndimage.label(structure=np.ones((3,3)))`) |

The skill exposes these as flags:

```bash
python3 sprite_process.py extract-frames \
    --input sheet.png \
    --grid 4x4 \
    --chroma-threshold 30 \
    --min-pixels 200 \
    --output-dir frames/
```

## Failure modes

### Components merge across cells

**Symptom:** detected count < grid count. Two adjacent characters got connected by a thin chroma-failed pixel bridge.

**Cause:** Magenta fringing too aggressive (low threshold lets near-magenta pixels survive), OR cell separation gap is too small in the canvas template.

**Fix:** Increase `--chroma-threshold` (relaxes the bg mask, drops more fringe). If that fails, regenerate the canvas with larger gutters between cells (edit `sprite_canvas.py`'s `border-width` constant).

### Components fragment within cells

**Symptom:** detected count > grid count. One character split into multiple components (head + body separated, glow aura detected as separate component).

**Cause:** Aggressive chroma-threshold has bitten into the character's color, OR the character has a low-saturation segment that matches magenta.

**Fix:** Decrease `--chroma-threshold` (tighter bg mask), OR increase `--min-pixels` to filter fragments, OR use 8-neighbor connectivity.

### Detected count = expected, but frames are wrong

**Symptom:** count matches, but `frame_03` shows the character that should be in cell 5.

**Cause:** Component sort order does not match grid reading order, OR multiple components per cell got confused.

**Fix:** Inspect the bounding-box centroids of components. The sort key is `(top, left)` — if frames have nearly-equal `top` values, the sort is unstable. Use cell-centroid mapping instead: each component's centroid is mapped to the nearest cell (col, row), and the component is assigned that cell's frame index.

## Centroid-to-cell mapping (alternative sort)

When frame-order matters and frames drift significantly:

```python
def assign_to_cells(components, grid_cols, grid_rows, sheet_w, sheet_h):
    cell_w = sheet_w / grid_cols
    cell_h = sheet_h / grid_rows
    assignments = {}
    for comp in components:
        cy = (comp.bbox.top + comp.bbox.bottom) / 2
        cx = (comp.bbox.left + comp.bbox.right) / 2
        col = min(int(cx / cell_w), grid_cols - 1)
        row = min(int(cy / cell_h), grid_rows - 1)
        idx = row * grid_cols + col
        if idx in assignments:
            # collision: prefer larger component
            if comp.area > assignments[idx].area:
                assignments[idx] = comp
        else:
            assignments[idx] = comp
    return [assignments.get(i) for i in range(grid_cols * grid_rows)]
```

This is the implementation in `sprite_process.py extract-frames` when `--cell-aware` is passed (default for grids ≥ 2x2).

## Output

Each component is saved as `<output-dir>/<name>_frame_NN.png`. The component's PNG dimensions equal its bounding-box size — frames are not yet rescaled to a uniform size; that happens in Phase F (anchor-alignment.md).

A metadata sidecar is written: `<output-dir>/frame_metadata.json`:

```json
{
  "sheet": "sheet.png",
  "grid": [4, 4],
  "components": [
    {"index": 0, "bbox": [12, 8, 240, 252], "area": 23440, "centroid": [126, 130]},
    {"index": 1, "bbox": [268, 12, 510, 256], "area": 22120, "centroid": [389, 134]},
    ...
  ],
  "rejected": 2,
  "warnings": []
}
```

`rejected` counts components below `--min-pixels`. Useful for tuning thresholds.

<!-- no-pair-required: section header; pair lives in subsection -->
## Anti-pattern

### Anti-pattern: Naive grid math for frame extraction

**What it looks like:**
```python
for r in range(rows):
    for c in range(cols):
        frame = sheet.crop((c * cell, r * cell, (c+1) * cell, (r+1) * cell))
```

**Why wrong:** Generated frames drift ±5-15% of cell size. Naive crops capture neighbor pixels and truncate the current sprite. Output frames look ragged at the edges and contain ghosted neighbor silhouettes.

**Do instead**: Connected-components clustering with chroma-key masking. Each component is bounded by the actual character pixel extent, not the cell math. The cell index is recovered post-hoc from component centroid.

## Reference loading hint

Load this file when:
- Spritesheet Phase D (frame extraction) is the active phase
- The pipeline emits a `FrameCountMismatchError`
- Tuning `--chroma-threshold` or `--min-pixels` parameters
