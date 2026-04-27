# Grid Shapes

Allowed grid configurations for spritesheet mode. Loaded when `--grid CxR` is set or the user asks about cell sizes.

## Cell size table

| Cell size | Use case | Notes |
|-----------|----------|-------|
| `64` | Tile-aligned tiny sprites (Game Boy era) | Frame detection difficult; use only with `gameboy-4color` style |
| `128` | Compact 2D action games | Standard for top-down RPGs |
| `192` | Detailed mid-resolution | Good balance of detail and grid space |
| `256` | **Default** for character sheets | Slay-the-Spire-tier detail fits |
| `384` | Large character portraits | Reduces grid count; use for hero sheets |
| `512` | Full painterly portraits | Limits total frames per sheet |

Cell-size validation rejects values not in this set. Powers of 16 only — non-power-of-16 values produce subpixel alignment issues during frame extraction.

## Grid shape conventions

`--grid CxR` is read as `Columns x Rows`. Total canvas:

```
canvas_width  = cell_size * C
canvas_height = cell_size * R
```

Total canvas must be ≤ 2048 × 2048. Backends silently downsample anything larger, destroying frame quality.

| Grid | Total | Use case |
|------|-------|----------|
| `4x1` | 4 frames | Single-direction walk cycle |
| `8x1` | 8 frames | Long single-direction walk or attack sequence |
| `4x4` | 16 frames | 4-direction walk cycle (one row per direction) |
| `4x2` | 8 frames | 4-direction idle + 4-direction walk |
| `8x4` | 32 frames | 4-direction walk + attack + hit + death |
| `8x8` | 64 frames | Full character with all states (cap at 256px cell-size to fit canvas) |
| `1x4` | 4 frames | Vertical sequence (charge → release → hit) |

The `4xR` and `8xR` patterns trigger per-direction strip output in Phase H — each row is exported as a separate horizontal strip PNG (`<name>_<dir>.png`). See `output-formats.md`.

## Direction-to-row convention

When `--grid 4xR` is used as a 4-direction sheet, rows map to:

| Row | Direction | Meaning |
|-----|-----------|---------|
| 0 | down | Character facing camera |
| 1 | left | Character facing left (mirror for right via CSS or runtime flip) |
| 2 | right | Character facing right |
| 3 | up | Character facing away from camera |

Why no separate "right" generation by default: most game runtimes flip the left strip horizontally (`scaleX(-1)` in DOM, `setFlipX(true)` in Phaser), saving 25% of generation cost. Pass `--no-flip-right` to generate explicit right-facing frames if your art demands asymmetric details (sword on left hip, etc.).

For `--grid 8xR` (8-directional games), rows map to:

| Row | Direction |
|-----|-----------|
| 0 | down |
| 1 | down-left |
| 2 | left |
| 3 | up-left |
| 4 | up |
| 5 | up-right |
| 6 | right |
| 7 | down-right |

8-direction sheets cost roughly 2x generation budget vs 4-direction.

## Maximum frames per generation

One Codex CLI imagegen call produces ONE image. Callers who want N frames
in a single Codex run should pack as many cells as possible into that one
image rather than firing N calls.

`--max-frames` (on both `sprite_canvas.py make-template` and
`sprite_pipeline.py`) auto-fills the canvas: it computes the largest
square `rows x cols` grid that fits a `--max-canvas` (default 1024x1024)
square at the given `--cell-size`. The math is just integer division:

```python
side = max_canvas // cell_size
rows, cols = side, side  # square grid; symmetry helps the model
```

### Cell-size to max-grid table

For the **default** `--max-canvas 1024`:

| `--cell-size` | side = 1024 // cell-size | grid | total frames |
|---------------|--------------------------|------|--------------|
| `512` | 2 | 2x2 | 4 |
| `384` | 2 | 2x2 | 4 |
| `256` | 4 | 4x4 | **16** |
| `192` | 5 | 5x5 | **25** |
| `128` | 8 | 8x8 | **64** |
| `64`  | 16 | 16x16 | **256** |

For `--max-canvas 1536`:

| `--cell-size` | side | grid | total frames |
|---------------|------|------|--------------|
| `512` | 3 | 3x3 | 9 |
| `384` | 4 | 4x4 | 16 |
| `256` | 6 | 6x6 | 36 |
| `192` | 8 | 8x8 | 64 |
| `128` | 12 | 12x12 | 144 |
| `64`  | 24 | 24x24 | 576 |

For `--max-canvas 2048` (the absolute hardware ceiling — backends silently
downsample anything larger):

| `--cell-size` | side | grid | total frames |
|---------------|------|------|--------------|
| `512` | 4 | 4x4 | 16 |
| `384` | 5 | 5x5 | 25 |
| `256` | 8 | 8x8 | 64 |
| `192` | 10 | 10x10 | 100 |
| `128` | 16 | 16x16 | 256 |
| `64`  | 32 | 32x32 | 1024 |

In practice, **64-256 frames** at **128-256px** cells is the sweet spot:
big enough that detail survives, dense enough that one call covers a full
4-direction walk + idle + attack + hit + death cycle.

### Usage

```bash
# Phase B canvas: max-fill 1024x1024 with 256px cells -> 4x4 = 16 frames
python3 sprite_canvas.py make-template \
    --cell-size 256 --max-frames \
    --output canvas.png

# Pipeline: same flag flows through Phase B + C
python3 sprite_pipeline.py \
    --description "pixel knight, 4-direction walk cycle" \
    --style snes-16bit-jrpg \
    --cell-size 256 --max-frames \
    --action walking
```

When `--max-frames` is set, `--rows`/`--cols`/`--grid` are overridden and a
notice is printed to stderr:

```
[canvas] auto-grid: 4x4 = 16 frames @ 256px on 1024x1024 canvas
```

## Validator behavior

`sprite_canvas.py make-template` validates inputs and rejects with clear errors:

```
ERROR: cell-size 200 not allowed. Choose from {64, 128, 192, 256, 384, 512}.
ERROR: total canvas 2560x1024 exceeds 2048x2048 limit. Reduce cell-size or grid.
ERROR: grid '4_4' malformed. Use CxR format like '4x4'.
```

The same validation runs at `sprite_pipeline.py` entry, before any backend call — failing fast saves backend costs.

## Generated canvas layout

The Phase B canvas template is:

- background: solid magenta (`#FF00FF`) RGB
- cell borders: 2px lines in dark grey (`#202020`) at every cell boundary
- alternating cell tint (optional via `--pattern checkerboard`): subtle 5% darken on alternating cells, helps the model distinguish frame slots without affecting bg removal

```
+-----+-----+-----+-----+
|     |     |     |     |
|  0  |  1  |  2  |  3  |
|     |     |     |     |
+-----+-----+-----+-----+
|     |     |     |     |
|  4  |  5  |  6  |  7  |
|     |     |     |     |
+-----+-----+-----+-----+
```

The borders disappear in Phase E (chroma-key removes everything that is not the character). They exist purely to guide the model during Phase C generation.

## Pattern modes

| Pattern | Effect |
|---------|--------|
| `magenta-only` | Solid magenta, no grid lines (relies entirely on prompt for layout) |
| `alternating` | Magenta with thin grid lines (default; balance of structure and chroma simplicity) |
| `checkerboard` | Alternating tint per cell (highest structure; some backends respect cells better with this) |

`checkerboard` adds a tinted variant of magenta that is still chroma-key-compatible (within `--chroma-threshold 30`). Do not use truly different colors — they survive the chroma key and pollute the alpha channel.

<!-- no-pair-required: section header; pair lives in subsection -->
## Anti-pattern

### Anti-pattern: Skipping the canvas template and prompting "make a 4x4 grid"

**What it looks like:** Single-prompt request "generate a 4x4 walk-cycle spritesheet of a wrestler" without supplying a structural canvas reference.

**Why wrong:** Both Codex CLI and Nano Banana do not natively understand sprite-grid layouts from prose alone. Output drifts: cells overlap, frames stack diagonally, character scales differ across cells, gutters disappear. Frame detection then has no reliable cell anchors.

**Do instead**: Always generate the Phase B canvas first (Pillow, no LLM), then pass it to Phase C as a reference image with the instruction "place the character in each cell". The grid lines and magenta background give the model concrete structural anchors. Frame detection in Phase D uses the actual character pixels (connected components), not the cell math, but the canvas still helps the model produce one character per cell.

## Reference loading hint

Load when sizing decisions are active: `--grid` or `--cell-size` flags, or user asks about sheet dimensions / direction conventions.
