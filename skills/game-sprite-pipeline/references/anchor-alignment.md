# Anchor Alignment

Phase F of the spritesheet pipeline. Per-frame normalization: shared-scale rescale + bottom-anchor alignment. Without this, walk-cycle frames have wildly different character heights and the character's feet bounce vertically as the animation plays.

## The two operations

### 1. Shared-scale rescale

After Phase D, each frame is cropped to its own bounding box. Bounding-box heights vary because the character's silhouette differs per pose (arms up = taller, crouched = shorter). Walk cycles need consistent character height across frames.

**Algorithm:**

```python
import statistics

def shared_scale(frames: list[Image.Image], target_percentile: float = 95) -> int:
    heights = [f.height for f in frames]
    target_height = int(statistics.quantiles(heights, n=100)[int(target_percentile) - 1])
    return target_height

def rescale_to_height(frame: Image.Image, target_height: int) -> Image.Image:
    aspect = frame.width / frame.height
    new_width = int(target_height * aspect)
    return frame.resize((new_width, target_height), Image.LANCZOS)
```

Why the 95th percentile (not the median or max):

- Median: a single tall frame (jumping pose) skews short; arms-up frames get scaled down and look small.
- Max: a single accidental tall component (artifact glow) inflates everything else.
- 95th: robust to a single outlier, captures "near-tallest legitimate frame" as the canonical height.

`--scale-percentile` flag exposes this; default is 95.

### 2. Bottom-anchor alignment

After rescale, frames have varying widths and heights. Walk cycles need the character's feet at the same canvas-Y coordinate so playback does not bounce.

**Algorithm:**

```python
def find_bottom_anchor(frame: Image.Image) -> int:
    """Y-coordinate of lowest non-transparent pixel."""
    arr = np.array(frame)
    alpha = arr[..., 3]
    # find rows that have any non-transparent pixel
    has_pixel = alpha.max(axis=1) > 0
    nonzero_rows = np.where(has_pixel)[0]
    if len(nonzero_rows) == 0:
        return frame.height  # all-transparent: anchor at canvas bottom
    return int(nonzero_rows.max())  # bottom-most row with a pixel
```

```python
def anchor_to_canvas(
    frame: Image.Image,
    canvas_w: int,
    canvas_h: int,
    bottom_margin: int = 8,
) -> Image.Image:
    """Place frame on transparent canvas with feet at canvas_h - bottom_margin."""
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    bottom = find_bottom_anchor(frame)
    target_y = canvas_h - bottom_margin - bottom  # subtracting because frame top will be placed here
    # actually: we want frame's bottom-anchor at canvas_h - bottom_margin
    # frame's top-y in canvas coords = (canvas_h - bottom_margin) - bottom
    paste_y = (canvas_h - bottom_margin) - bottom

    # Horizontal: center the frame's bbox on canvas
    paste_x = (canvas_w - frame.width) // 2

    canvas.paste(frame, (paste_x, paste_y), frame)
    return canvas
```

The result: every output frame is the same canvas size (`cell_size × cell_size` typically), with the character's lowest pixel at `canvas_h - bottom_margin`.

## Frame-relative anchor data

The metadata JSON written by Phase F includes per-frame anchor coordinates:

```json
{
  "frame_00": {"bbox": [12, 8, 240, 252], "anchor_y": 250, "scaled_to": [228, 244]},
  "frame_01": {"bbox": [268, 12, 510, 256], "anchor_y": 252, "scaled_to": [242, 236]}
}
```

Phaser texture-atlas JSON consumes the `anchor_y` for `setOrigin(0.5, anchor_y/cell_h)` calls in game code.

## Special cases

### Lying-down or aerial character

`find_bottom_anchor` finds the lowest pixel. For a character lying flat (death frame, slam impact), this is the head or back, not the feet. Anchor alignment will place the wrong body part at the bottom.

**Mitigation:** `--anchor center` flag uses the bbox vertical center as the anchor reference instead of the bottom. For mixed sequences (walk + death + idle), the user can pass `--anchor-mode auto`, which uses `bottom` for upright frames (height/width > 1.2) and `center` for everything else.

### All-transparent frame

A frame with no non-transparent pixels (rare; usually a Phase D failure). Returns `frame.height` as the anchor — places nothing at the bottom margin. Surfaced as a warning:

```
WARNING: frame_03 has no non-transparent pixels; check frame extraction
```

The pipeline does not abort — the output sheet has an empty cell, but downstream consumers handle it.

### Wide character (boss / giant)

`giant` archetype has a 1.2x scale modifier. After Phase F, its bbox is wider than other frames. Horizontal centering still works; downstream renderers should not assume uniform width. The atlas JSON records per-frame width.

## Tuning parameters

| Parameter | Default | Adjust if |
|-----------|---------|-----------|
| `--scale-percentile` | 95 | Median (50) for groups of similar-pose frames; Max (100) for single-pose sheets |
| `--bottom-margin` | 8 px | Larger if feet should sit higher in the cell; 0 for feet-at-edge |
| `--anchor-mode` | `bottom` | `center` for non-upright sequences; `auto` for mixed |

## Output

Per-frame normalized PNGs at `<output-dir>/<name>_frame_NN.png`. Each is exactly `cell_w × cell_h` pixels. Plus a metadata JSON with per-frame bbox, anchor, and scale info.

## Validation

After Phase F:

```python
def validate_normalization(frames: list[Image.Image], cell_w: int, cell_h: int):
    for i, f in enumerate(frames):
        if (f.width, f.height) != (cell_w, cell_h):
            raise NormalizationError(f"frame {i} is {f.size}, expected ({cell_w}, {cell_h})")
        anchor = find_bottom_anchor(f)
        if anchor < cell_h * 0.5:
            warn(f"frame {i} anchor at y={anchor} (canvas height {cell_h}) — sprite floats high")
```

The skill emits warnings for frames whose anchor is in the upper half (sprite "floating") because this often indicates a Phase D extraction error rather than a legitimate aerial pose.

## Why bottom-anchor (not center)

Walk-cycle and idle animations have the character's feet planted on the ground. If frames are center-anchored, the head bobs up and down as the bbox height varies (taller arms-up frame → center moves up → head moves up). Bottom-anchor pins the feet, so motion looks grounded.

For animations where the character is genuinely off-ground (jumping, flying, falling), `--anchor center` produces the right look. The default is `bottom` because most game animations are ground-based.

<!-- no-pair-required: section header; pair lives in subsection -->
## Anti-pattern

### Anti-pattern: Center-anchoring all frames regardless of action

**What it looks like:** Always centering frames vertically, regardless of whether the character is grounded or aerial.

**Why wrong:** Walk-cycle feet bounce because center-anchored frames with different bbox heights produce different ground-Y. Animation looks broken even if individual frames are well-rendered.

**Do instead**: Bottom-anchor by default. Use `--anchor center` only when the character is genuinely off-ground for the entire sequence (jump-loop, falling-loop). For mixed sequences, `--anchor-mode auto` picks per-frame based on bbox aspect.

### Anti-pattern: Skipping shared-scale and trusting per-frame bbox sizes

**What it looks like:** Outputting frames at their natural bbox dimensions without rescaling to a shared height.

**Why wrong:** Walk-cycle frames have arms in different positions; their bboxes have different heights. Without shared-scale, the character's apparent height changes frame-to-frame even though the actual character is the same size.

**Do instead**: Compute the 95th-percentile height across all frames and rescale every frame's height to that target, preserving per-frame aspect. Width varies (arms out vs arms in), but height stays constant.

## Reference loading hint

Load when:
- Spritesheet Phase F (normalization) is active
- Output frames have inconsistent character size or bouncing feet
- Phaser atlas integration needs anchor data
