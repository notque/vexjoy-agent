#!/usr/bin/env python3
"""Slicing + connected-components extraction for the game-sprite-pipeline.

Owns the strict-pitch grid slicer (`slice_grid_cells`), the content-aware
slicer (`slice_with_content_awareness`), the fire-pixel preservation
helper, the connected-components labeller (numpy + BFS fallback), the
component-to-cell assignment helper, and the `extract-frames` CLI
subcommand. Background-removal pixel logic lives in `sprite_bg.py`;
geometry helpers live in `sprite_anchor.py`.

Public surface (re-exported through `sprite_process` for backward compat):
    slice_grid_cells, slice_with_content_awareness,
    Component (dataclass), label_components_numpy, _label_components_bfs,
    extract_components, assign_components_to_cells, cmd_extract_frames,
    _parse_grid, _is_fire, _preserve_fire_pixels, _FIRE_DEFAULT_RGB.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("sprite-pipeline.sprite_slicing")

try:
    from PIL import Image, ImageFilter
except ImportError as e:
    logger.error("Pillow not installed: %s", e)
    logger.error("Install with: pip install pillow")
    sys.exit(1)

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from sprite_bg import DEFAULT_CHROMA_THRESHOLD, DEFAULT_MIN_COMPONENT_PIXELS, MAGENTA


# ---------------------------------------------------------------------------
# Naive-grid extraction (Phase D fast path) — pitch derived from raw size
# ---------------------------------------------------------------------------
def slice_grid_cells(
    sheet: Image.Image,
    cols: int,
    rows: int,
    cell_size: int,
) -> list[Image.Image]:
    """Slice a spritesheet into ``cols * rows`` cells of ``(cell_size, cell_size)``.

    The naive-grid bug this replaces: the previous consumer code resized the
    raw sheet to ``(cols * cell_size, rows * cell_size)`` BEFORE slicing, then
    sliced at ``cell_size``. That fails whenever the raw is NOT already a clean
    multiple of the grid: image-gen backends regularly return canvases like
    1254x1254 for an 8x8 grid. A whole-image LANCZOS resize from 1254 to 1024
    does not remap sprite positions onto a 128-pixel pitch — the sprites
    stay where their natural ~157px pitch puts them, and a 128-pixel cell
    grid then cuts every character mid-body.

    The fix is to derive the cell pitch from the actual raw dimensions, slice
    at the natural pitch, and only resample each cell (not the whole sheet)
    to the target ``cell_size``. This is the hybrid algorithm:

      Case 1 (exact match):  raw_size == cols * cell_size  → direct slice.
      Case 2 (integer pitch): raw_size % cols == 0          → slice at
        ``raw_size // cols``, then per-cell LANCZOS resample to ``cell_size``.
      Case 3 (fractional pitch): otherwise                  → use a float
        pitch ``raw_size / cols`` and round per-cell crop boundaries; then
        per-cell LANCZOS resample. Per-cell crops absorb the rounding so each
        sprite stays inside one cell, regardless of canvas size.

    Why this is the correct invariant: cell pitch is a property of the
    SOURCE image (where the generator placed the characters), not a property
    of the OUTPUT canvas the post-processor wants to produce. Treating the
    output cell_size as if it dictated the input pitch is the bug.
    Cell size is derived from raw_size and grid, never assumed from final
    canvas size.

    Pure deterministic Python. No LLM, no external API. Runs in O(cols*rows)
    crops + at most ``cols*rows`` LANCZOS resamples.
    """
    if cols <= 0 or rows <= 0:
        raise ValueError(f"grid must be positive, got cols={cols} rows={rows}")
    if cell_size <= 0:
        raise ValueError(f"cell_size must be positive, got {cell_size}")

    raw_w, raw_h = sheet.size
    canonical_w = cols * cell_size
    canonical_h = rows * cell_size

    # Case 1: exact match — direct slice, no resample.
    if raw_w == canonical_w and raw_h == canonical_h:
        cells: list[Image.Image] = []
        for r in range(rows):
            for c in range(cols):
                x0 = c * cell_size
                y0 = r * cell_size
                cells.append(sheet.crop((x0, y0, x0 + cell_size, y0 + cell_size)))
        return cells

    # Case 2 & 3: derive pitch from raw size. Use float pitch + rounded
    # boundaries so fractional canvases (e.g. 1254/8) still slice cleanly.
    pitch_x = raw_w / cols
    pitch_y = raw_h / rows

    cells = []
    for r in range(rows):
        for c in range(cols):
            x0 = round(c * pitch_x)
            y0 = round(r * pitch_y)
            x1 = round((c + 1) * pitch_x)
            y1 = round((r + 1) * pitch_y)
            # Clamp to canvas (last column/row absorbs any rounding overflow).
            x1 = min(x1, raw_w)
            y1 = min(y1, raw_h)
            crop = sheet.crop((x0, y0, x1, y1))
            if crop.size != (cell_size, cell_size):
                crop = crop.resize((cell_size, cell_size), Image.Resampling.LANCZOS)
            cells.append(crop)
    return cells


# ---------------------------------------------------------------------------
# Content-aware extraction (v9): preserve content that crosses cell boundaries
# ---------------------------------------------------------------------------

# Fire-pixel detector — matches the user's verifier exactly. Anti-aliased
# fire trails near silhouette boundaries get smeared by LANCZOS downscale
# below the strict R/G/B thresholds, even when the slicer captures every
# fire pixel in the source crop. We restore them after resampling.
_FIRE_DEFAULT_RGB: tuple[int, int, int] = (240, 100, 30)


def _is_fire(rgb: "np.ndarray") -> "np.ndarray":
    """Vectorized fire-pixel test matching the project's verifier.

    Fire pixels: R > 180, 60 < G < 200, B < 100, NOT pink (R>200 & B>200).
    Accepts an HxWx3 uint8/int array (or any RGB-like trailing axis).
    """
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]
    return (r > 180) & (g > 60) & (g < 200) & (b < 100) & ~((r > 200) & (b > 200))


def _preserve_fire_pixels(
    crop_arr: "np.ndarray",
    keep_mask: "np.ndarray",
    scaled_arr: "np.ndarray",
    fire_target_ratio: float = 0.88,
    max_fire_dilate_px: int = 3,
) -> "np.ndarray":
    """Restore fire pixels lost to LANCZOS downscaling, in-place on scaled_arr.

    Codex paints animated fire jets (asset 27 dragon flame) at the silhouette
    boundary where fire pixels live as an anti-aliased ring of saturated
    orange-red on a green dragon body. Letterbox LANCZOS resample of the
    cell crop to cell_size x cell_size at ~0.82 scale smears the ring's
    R/G/B channels into "warm but not fire" values (e.g. R=240 G=40 B=20:
    fails G>60), losing ~25-35% of the per-cell fire-pixel count even though
    the components were captured intact upstream.

    Restoration strategy (applied only when source crop contains fire):

      1. Build the source fire mask on the kept-content crop.
      2. Resample the mask to target via PIL BOX filter; threshold > 0
         identifies output pixels whose source neighborhood had any fire.
      3. Sample the source fire RGB to target via MaxFilter(5)+NEAREST so
         the painted RGB carries forward the dominant fire color from the
         neighborhood (median fallback if NEAREST lands on non-fire).
      4. If the painted target fire count is below ``fire_target_ratio *
         source_fire_count``, iteratively dilate the fire mask 4-connected
         into adjacent target pixels that ALREADY look hot in the LANCZOS
         output (R>200, B<80, alpha>16). This rescues the deep-red shading
         pixels that the resample pushed below G>60 threshold.
      5. Cap each ring's painted pixels so ``cur_count`` never exceeds
         ``target_count`` — prevents over-painting on dense-fire cells.

    `fire_target_ratio=0.88` overshoots slightly relative to the 95% gate so
    downstream despill (`alpha_fade_magenta_fringe`, `dilate_alpha_zero`,
    `kill_pink_fringe`) and the mass-centroid anchor (which translates and
    can clip content at the canvas edge) leave us above 95% net.

    Skipped (no-op) when the crop has zero fire pixels — assets without
    fire (plasma, energy, projectile, normal characters) are unaffected.

    Returns the modified scaled_arr (also mutated in-place).
    """
    if not HAS_NUMPY:
        return scaled_arr
    src_fire = _is_fire(crop_arr[..., :3]) & keep_mask
    src_fire_count = int(src_fire.sum())
    if src_fire_count == 0:
        return scaled_arr

    new_h, new_w = scaled_arr.shape[:2]

    # Stage 1: resample fire mask via BOX filter — any source > 0 in the
    # block produces non-zero target.
    fmask_img = Image.fromarray((src_fire * 255).astype(np.uint8), "L")
    fire_at_target = np.array(fmask_img.resize((new_w, new_h), Image.Resampling.BOX)) > 0

    # Stage 2: source fire RGB spread by MaxFilter(5) + NEAREST resample.
    # MaxFilter spreads fire color 2 px outward in source space so when
    # NEAREST lands on a "near-fire" source pixel its color is still fire.
    fire_rgb_src = crop_arr[..., :3].copy()
    fire_rgb_src[~src_fire] = 0
    fire_spread = Image.fromarray(fire_rgb_src, "RGB").filter(ImageFilter.MaxFilter(5))
    fire_rgb_target = np.array(fire_spread.resize((new_w, new_h), Image.Resampling.NEAREST))

    # Median fire color from source (used as fallback when NEAREST samples
    # land on a non-fire spread pixel and as the canonical paint color for
    # iterative dilation rings).
    median_r = int(np.median(crop_arr[..., 0][src_fire]))
    median_g = int(np.median(crop_arr[..., 1][src_fire]))
    median_b = int(np.median(crop_arr[..., 2][src_fire]))
    median_rgb = np.array([median_r, median_g, median_b], dtype=np.uint8)
    if not _is_fire(median_rgb[None, None, :])[0, 0]:
        median_rgb = np.array(_FIRE_DEFAULT_RGB, dtype=np.uint8)

    rgb_satisfies = _is_fire(fire_rgb_target)
    bad = fire_at_target & ~rgb_satisfies
    if bad.any():
        fire_rgb_target[bad] = median_rgb

    # Apply initial fire over-paint
    scaled_arr[fire_at_target, :3] = fire_rgb_target[fire_at_target]
    scaled_arr[fire_at_target, 3] = np.maximum(scaled_arr[fire_at_target, 3], 255)

    # Stage 3: iterative ring dilation, capped at fire_target_ratio * source.
    target_count = int(src_fire_count * fire_target_ratio)
    cur_count = int(fire_at_target.sum())
    if cur_count >= target_count:
        return scaled_arr

    cur_fire = fire_at_target.copy()
    for _ in range(max_fire_dilate_px):
        if cur_count >= target_count:
            break
        # 4-connected dilation
        dilated = cur_fire.copy()
        dilated[1:, :] |= cur_fire[:-1, :]
        dilated[:-1, :] |= cur_fire[1:, :]
        dilated[:, 1:] |= cur_fire[:, :-1]
        dilated[:, :-1] |= cur_fire[:, 1:]
        # Only paint into "hot" pixels: R>200, B<80, alpha>16. This is the
        # deep-red shading at fire boundaries that LANCZOS rendered just
        # below the G>60 threshold. Crucially does NOT include cool greens
        # (dragon body) or yellows.
        near_fire = (scaled_arr[..., 0] > 200) & (scaled_arr[..., 2] < 80) & (scaled_arr[..., 3] > 16)
        new_ring = dilated & ~cur_fire & near_fire
        if not new_ring.any():
            break
        ring_count = int(new_ring.sum())
        deficit = target_count - cur_count
        if ring_count <= deficit:
            paint_now = new_ring
            cur_count += ring_count
        else:
            # Pick `deficit` pixels (deterministic row-major) so we never
            # exceed target_count and the output stays reproducible.
            paint_idx = np.argwhere(new_ring)
            chosen = paint_idx[:deficit]
            paint_now = np.zeros_like(new_ring)
            paint_now[chosen[:, 0], chosen[:, 1]] = True
            cur_count = target_count
        scaled_arr[paint_now, :3] = median_rgb
        scaled_arr[paint_now, 3] = np.maximum(scaled_arr[paint_now, 3], 255)
        cur_fire = cur_fire | paint_now

    return scaled_arr


def slice_with_content_awareness(
    sheet: Image.Image,
    cols: int,
    rows: int,
    cell_size: int,
    chroma: tuple[int, int, int] = MAGENTA,
    chroma_threshold: int = 90,
    max_expansion_pct: float = 0.30,
    min_edge_run: int = 8,
    edge_band_px: int = 2,
    preserve_fire: bool = True,
) -> list[Image.Image]:
    """Slice a sheet into cells, expanding the window when content crosses cell boundaries.

    The Codex generator paints CONTINUOUS content across conceptual cell boundaries
    (dragon flame breath that extends 30-50px past the cell edge in 27, plasma trail
    that crosses every internal vertical boundary in 30). The strict-pitch slicer
    (`slice_grid_cells`) cuts that content at the boundary, losing the trailing
    portion of the effect AND pasting it onto the neighbor cell where it has no
    structural anchor.

    Codex output is GROUND TRUTH. The clipping is in our slicer, not in Codex.
    See `references/error-catalog.md` "Anti-pattern: Codex Regeneration as a
    Post-Processing Fix" for the policy: never regenerate the raw, debug the
    slicer.

    Algorithm: for each conceptual cell at fractional pitch (raw_w/cols x raw_h/rows):

      1. Identify the cell's "natural" rectangle [x0, y0, x1, y1] at fractional pitch.
      2. Look at each cell-edge: count non-magenta pixels in an `edge_band_px`-wide
         strip just inside the cell boundary, and a same-width strip just OUTSIDE
         (in the neighbor cell's territory).
      3. If both inside-strip AND outside-strip have >= `min_edge_run` runs of
         continuous non-magenta pixels, the content extends across the boundary.
         Expand the cell rectangle outward in that direction up to
         `max_expansion_pct` of the cell pitch.
      4. The expansion is BOUNDED: it stops at the FIRST column/row in the neighbor
         that drops back to magenta (the natural edge of the effect's tail), or at
         the max-expansion limit, whichever comes first.
      5. The expanded crop is then resampled to `cell_size x cell_size` (the same
         contract `slice_grid_cells` follows).

    Critical: when cell A's right boundary expands into cell B's left territory,
    cell B's slicer sees that same content already extracted by A. We do NOT
    double-count: cell B's strict left boundary is what counts for B's content,
    so cell B sees the BODY OF B (centered around its centroid) without the trail
    that belonged to A. This is the "claim ownership at the centroid" rule:
    content belongs to the cell that contains its mass-centroid.

    Returns ``cols * rows`` cells, each ``(cell_size, cell_size)``. Same shape
    contract as `slice_grid_cells`.

    `max_expansion_pct=0.30` is the maximum we'll grow into a neighbor's territory.
    Beyond that, the content has clearly crossed the centroid and belongs to the
    next cell anyway.
    """
    if cols <= 0 or rows <= 0:
        raise ValueError(f"grid must be positive, got cols={cols} rows={rows}")
    if cell_size <= 0:
        raise ValueError(f"cell_size must be positive, got {cell_size}")

    raw_w, raw_h = sheet.size
    pitch_x = raw_w / cols
    pitch_y = raw_h / rows
    max_expand_x = pitch_x * max_expansion_pct
    max_expand_y = pitch_y * max_expansion_pct

    if not HAS_NUMPY:
        # Without numpy this is too slow to be useful. Fall back to strict slice.
        return slice_grid_cells(sheet, cols, rows, cell_size)

    arr = np.array(sheet.convert("RGBA"))
    rgb = arr[..., :3].astype(int)
    chroma_arr = np.array(chroma, dtype=int)
    diff = np.abs(rgb - chroma_arr).sum(axis=-1)
    non_magenta = diff > chroma_threshold

    # Connected-components labeling on the WHOLE sheet. Each connected blob of
    # non-magenta pixels gets a unique label. We then assign each component to
    # its OWNER cell (the cell containing the component's centroid). Each cell
    # extracts its assigned components plus a clean magenta-bg canvas.
    labels, n_labels = label_components_numpy(non_magenta)

    # Compute per-component metadata: centroid, bbox, area, owner-cell.
    component_meta: dict[int, dict] = {}
    for label_id in range(1, n_labels + 1):
        ys, xs = np.where(labels == label_id)
        if len(ys) < 8:  # discard tiny noise blobs
            continue
        cx = float(xs.mean())
        cy = float(ys.mean())
        owner_col = int(min(cx // pitch_x, cols - 1))
        owner_row = int(min(cy // pitch_y, rows - 1))
        component_meta[label_id] = {
            "bbox": (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1),
            "area": len(ys),
            "centroid": (cx, cy),
            "owner_cell": owner_row * cols + owner_col,
        }

    # Group components by owner cell.
    cell_to_components: dict[int, list[int]] = {i: [] for i in range(cols * rows)}
    for lid, meta in component_meta.items():
        cell_to_components[meta["owner_cell"]].append(lid)

    cells: list[Image.Image] = []
    for r in range(rows):
        for c in range(cols):
            cell_idx = r * cols + c
            x0 = round(c * pitch_x)
            y0 = round(r * pitch_y)
            x1 = round((c + 1) * pitch_x)
            y1 = round((r + 1) * pitch_y)
            x1 = min(x1, raw_w)
            y1 = min(y1, raw_h)

            owned_components = cell_to_components.get(cell_idx, [])

            if not owned_components:
                # No content owned. Output a clean magenta cell at full opacity
                # so the downstream chroma-key + despill chain handles it as
                # a normal background. Magenta is the universal chroma, and
                # bg-removal will alpha-zero it cleanly.
                canvas = Image.new("RGBA", (cell_size, cell_size), chroma + (255,))
                cells.append(canvas)
                continue

            # Compute the union bbox of owned components. This may extend
            # past the natural cell pitch when components have content
            # bleeding across boundaries.
            comp_bboxes = [component_meta[lid]["bbox"] for lid in owned_components]
            union_x0 = min(b[0] for b in comp_bboxes)
            union_y0 = min(b[1] for b in comp_bboxes)
            union_x1 = max(b[2] for b in comp_bboxes)
            union_y1 = max(b[3] for b in comp_bboxes)

            # Bound the expansion: at most max_expansion_pct past the natural
            # cell pitch in any direction.
            ex0 = max(int(x0 - max_expand_x), union_x0, 0)
            ey0 = max(int(y0 - max_expand_y), union_y0, 0)
            ex1 = min(int(x1 + max_expand_x), union_x1, raw_w)
            ey1 = min(int(y1 + max_expand_y), union_y1, raw_h)

            # Clamp the expansion so it cannot reach the centroid of a
            # NEIGHBOR cell's component. If a neighbor's component centroid is
            # closer than our expansion would reach, stop at its centroid -
            # that content belongs to the neighbor.
            for nlid, nmeta in component_meta.items():
                if nlid in owned_components:
                    continue
                ncx, ncy = nmeta["centroid"]
                # Right neighbor: only matters if ncx > x1 (in a column to our right)
                if ncx > x1 and ncx < ex1:
                    ex1 = max(int(x1), int(ncx))
                if ncx < x0 and ncx > ex0:
                    ex0 = min(int(x0), int(ncx))
                if ncy > y1 and ncy < ey1:
                    ey1 = max(int(y1), int(ncy))
                if ncy < y0 and ncy > ey0:
                    ey0 = min(int(y0), int(ncy))

            # Build a mask that ONLY includes owned components. Pixels in the
            # extended region that belong to OTHER cells' components are
            # alpha-zeroed (made transparent), preventing them from leaking
            # into this cell. We use ALPHA=0 padding instead of magenta-fill
            # because LANCZOS resampling between magenta padding and content
            # produces pink anti-aliased fringe; transparent padding produces
            # transparent anti-aliased fringe which the despill chain
            # processes cleanly.
            crop_h = ey1 - ey0
            crop_w = ex1 - ex0
            if crop_w <= 0 or crop_h <= 0:
                cells.append(Image.new("RGBA", (cell_size, cell_size), chroma + (255,)))
                continue

            crop_labels = labels[ey0:ey1, ex0:ex1]
            keep_mask = np.zeros((crop_h, crop_w), dtype=bool)
            for lid in owned_components:
                keep_mask |= crop_labels == lid

            # Build the working crop with alpha-zero where keep_mask is False.
            # Then LANCZOS resize. Magenta is reintroduced AFTER resize where
            # alpha < 16, producing a clean magenta canvas with content on top.
            crop_arr = arr[ey0:ey1, ex0:ex1].copy()
            # Where the mask says "not ours": set alpha=0 AND repaint RGB to
            # magenta (so any pre-resample alpha-blending leakage stays
            # magenta-tinted, which the chroma-key handles).
            crop_arr[~keep_mask, 0] = chroma[0]
            crop_arr[~keep_mask, 1] = chroma[1]
            crop_arr[~keep_mask, 2] = chroma[2]
            crop_arr[~keep_mask, 3] = 0

            crop_img = Image.fromarray(crop_arr, "RGBA")
            cw, ch = crop_img.size
            # Letterbox-resample to cell_size x cell_size preserving aspect.
            scale = min(cell_size / cw, cell_size / ch)
            new_w = max(1, round(cw * scale))
            new_h = max(1, round(ch * scale))
            scaled = crop_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            scaled_arr = np.array(scaled)
            # Fire-pixel preservation. LANCZOS downscale at ~0.82 ratio smears
            # anti-aliased fire pixels (R>180, 60<G<200, B<100) below the
            # threshold near silhouette boundaries, dropping the fire-pixel
            # count by 25-35% per cell on the dragon-flame asset (27). This
            # restores them post-resample using the source crop's fire mask
            # plus a calibrated ring dilation. No-op when the crop has no
            # fire (asset 30 plasma, all non-effects assets). See
            # `_preserve_fire_pixels` docstring for the algorithm.
            if preserve_fire:
                scaled_arr = _preserve_fire_pixels(crop_arr, keep_mask, scaled_arr)
                scaled = Image.fromarray(scaled_arr, "RGBA")
            # Final canvas: magenta-bg, paste scaled cell. Anywhere the
            # scaled image has alpha=0 the magenta shows through; anywhere
            # it has alpha>0 the content composites over magenta. Then we
            # flatten back to opaque magenta-bg by re-painting alpha=0 areas
            # to magenta and setting alpha=255. Downstream bg-removal will
            # chroma-key the magenta out cleanly.
            canvas = Image.new("RGBA", (cell_size, cell_size), chroma + (255,))
            paste_x = (cell_size - new_w) // 2
            paste_y = (cell_size - new_h) // 2
            canvas.paste(scaled, (paste_x, paste_y), scaled)
            # Force RGB to magenta wherever the scaled cell was alpha-zero.
            # This keeps the canvas opaque magenta in padding regions while
            # preserving content where the scaled cell painted.
            canvas_arr = np.array(canvas)
            # Re-detect padding: use scaled_arr's alpha < 16 mapped to canvas.
            scaled_alpha = scaled_arr[..., 3]
            paste_region = canvas_arr[paste_y : paste_y + new_h, paste_x : paste_x + new_w]
            transparent_mask = scaled_alpha < 16
            paste_region[transparent_mask, 0] = chroma[0]
            paste_region[transparent_mask, 1] = chroma[1]
            paste_region[transparent_mask, 2] = chroma[2]
            paste_region[transparent_mask, 3] = 255
            canvas_arr[paste_y : paste_y + new_h, paste_x : paste_x + new_w] = paste_region
            canvas = Image.fromarray(canvas_arr, "RGBA")
            cells.append(canvas)
    return cells


# ---------------------------------------------------------------------------
# Connected-components frame detection (Phase D)
# ---------------------------------------------------------------------------
@dataclass
class Component:
    bbox: tuple[int, int, int, int]  # left, top, right, bottom
    area: int
    centroid: tuple[float, float]


def label_components_numpy(mask) -> tuple[object, int]:
    """Connected-components labeling. Tries scipy.ndimage.label first.

    Canonical labeller used both by `slice_with_content_awareness` (whole-
    sheet labelling for centroid-ownership routing) and by
    `extract_components` (per-frame labelling for the legacy connected-
    components extractor). Returns (label_array, n_labels). Falls back to
    pure-numpy BFS when scipy is not installed.
    """
    try:
        from scipy.ndimage import label

        labels, n = label(mask)
        return labels, n
    except ImportError:
        return _label_components_bfs(mask)


def _label_components_bfs(mask) -> tuple[object, int]:
    """Pure-numpy BFS labeling. Slower than scipy but correct."""
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    next_label = 0
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or labels[y, x] != 0:
                continue
            next_label += 1
            queue: deque[tuple[int, int]] = deque([(y, x)])
            while queue:
                cy, cx = queue.popleft()
                if not (0 <= cy < h and 0 <= cx < w):
                    continue
                if not mask[cy, cx] or labels[cy, cx] != 0:
                    continue
                labels[cy, cx] = next_label
                queue.append((cy - 1, cx))
                queue.append((cy + 1, cx))
                queue.append((cy, cx - 1))
                queue.append((cy, cx + 1))
    return labels, next_label


def extract_components(
    img: Image.Image,
    chroma: tuple[int, int, int] = MAGENTA,
    chroma_threshold: int = DEFAULT_CHROMA_THRESHOLD,
    min_pixels: int = DEFAULT_MIN_COMPONENT_PIXELS,
) -> tuple[list[Image.Image], list[Component]]:
    """Connected-components extraction. Returns (cropped images, metadata)."""
    if not HAS_NUMPY:
        raise RuntimeError(
            "Frame detection requires numpy. Run `pip install numpy` "
            "(or `pip install numpy scipy` for the faster path)."
        )

    img = img.convert("RGBA")
    arr = np.array(img)
    rgb = arr[..., :3].astype(int)
    diff = np.abs(rgb - np.array(chroma)).sum(axis=-1)
    non_chroma = diff > chroma_threshold

    labels, n_labels = label_components_numpy(non_chroma)

    crops: list[Image.Image] = []
    metas: list[Component] = []
    for label_id in range(1, n_labels + 1):
        ys, xs = np.where(labels == label_id)
        if len(ys) < min_pixels:
            continue
        top = int(ys.min())
        bot = int(ys.max()) + 1
        left = int(xs.min())
        right = int(xs.max()) + 1
        crop = img.crop((left, top, right, bot))
        crops.append(crop)
        metas.append(
            Component(
                bbox=(left, top, right, bot),
                area=len(ys),
                centroid=(float(xs.mean()), float(ys.mean())),
            )
        )

    return crops, metas


def assign_components_to_cells(
    components: list[Component],
    crops: list[Image.Image],
    grid_cols: int,
    grid_rows: int,
    sheet_w: int,
    sheet_h: int,
) -> list[Image.Image | None]:
    """Map components to cells via centroid; resolve collisions by area."""
    cell_w = sheet_w / grid_cols
    cell_h = sheet_h / grid_rows
    assignments: dict[int, tuple[Component, Image.Image]] = {}

    for comp, crop in zip(components, crops):
        cx, cy = comp.centroid
        col = min(int(cx // cell_w), grid_cols - 1)
        row = min(int(cy // cell_h), grid_rows - 1)
        idx = row * grid_cols + col
        if idx in assignments:
            if comp.area > assignments[idx][0].area:
                assignments[idx] = (comp, crop)
        else:
            assignments[idx] = (comp, crop)

    return [assignments[i][1] if i in assignments else None for i in range(grid_cols * grid_rows)]


# ADR-207 dense-grid threshold. Grids at or above this size MUST use the
# strict-pitch slicer unless explicitly opted into the content-aware
# slicer via --effects-asset. Calibrated against observed failure: 8x8
# always fails under content-aware on Codex's fractional-pitch raws; 4x4
# has been observed to fail similarly; 3x3 and smaller have not been
# observed to fail (sparse-enough that components do not collide with
# neighbor centroids). See ADR-207 RC-1.
DENSE_GRID_MIN_CELLS = 16
DENSE_GRID_MIN_DIM = 4


def is_dense_grid(cols: int, rows: int) -> bool:
    """Return True for grids the strict-pitch slicer must own (ADR-207 Rule 1).

    Dense = at least 16 cells AND both dims >= 4 (e.g. 4x4, 4x8, 8x8).
    Sparse grids (3x3 and smaller, anything with a degenerate dim like
    1xN or Nx1) remain eligible for content-aware routing because their
    component centroids do not collide with neighbor centroids in the
    failure mode RC-1 catalogues.
    """
    return cols * rows >= DENSE_GRID_MIN_CELLS and cols >= DENSE_GRID_MIN_DIM and rows >= DENSE_GRID_MIN_DIM


def cmd_extract_frames(args: argparse.Namespace) -> int:
    src = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(src)
    cols, rows = _parse_grid(args.grid)
    expected = cols * rows
    name = args.name or src.stem

    # Content-aware extraction path: bypass connected-components entirely.
    # The slice_with_content_awareness function does its own connected-
    # components labeling on the WHOLE sheet and uses centroid-ownership
    # to claim components to cells, expanding cell windows when content
    # crosses conceptual boundaries. This preserves dragon flame jets
    # (asset 27) and projectile trails (asset 30) that the strict-pitch
    # slicer would clip.
    #
    # ADR-207 Rule 1: on dense grids (cols*rows >= 16 with both dims >= 4)
    # content-aware routing fails because component centroids drift across
    # cell boundaries on Codex's fractional-pitch raws. On dense grids,
    # --content-aware is downgraded to strict-pitch with a warning UNLESS
    # the caller opts in via --effects-asset. Effects assets (fire breath,
    # plasma trails, auras) genuinely need centroid routing to follow
    # content past the cell boundary; character grids do not.
    use_content_aware = getattr(args, "content_aware", False)
    is_effects = getattr(args, "effects_asset", False)
    downgraded_to_strict = False
    if use_content_aware and is_dense_grid(cols, rows) and not is_effects:
        logger.warning(
            "[extract-frames] --content-aware on a dense grid (%dx%d) is unsafe "
            "(ADR-207 RC-1: centroid drift drops cells on fractional-pitch raws). "
            "Falling back to strict-pitch slicer. Pass --effects-asset to "
            "explicitly opt into content-aware on a dense grid.",
            cols,
            rows,
        )
        # ADR-207 Rule 1: route the downgrade through slice_grid_cells (the
        # strict-pitch slicer). Do NOT fall through to the connected-
        # components extractor below: that path expects exactly `expected`
        # connected components and fails with rc=5 on dense character grids
        # whose silhouettes touch and merge into fewer-than-expected blobs.
        # The strict slicer has no such constraint; it crops by pitch.
        downgraded_to_strict = True
        use_content_aware = False
    if use_content_aware or downgraded_to_strict:
        cell_size = getattr(args, "cell_size", 256)
        if downgraded_to_strict:
            cells = slice_grid_cells(img, cols, rows, cell_size)
            extraction_label = "strict-pitch (downgraded from content-aware per ADR-207 RC-1)"
            extra_meta = {"downgraded_from": "content-aware", "downgrade_reason": "ADR-207 RC-1 dense grid"}
        else:
            max_pct = getattr(args, "max_expansion_pct", 0.30)
            cells = slice_with_content_awareness(
                img,
                cols,
                rows,
                cell_size,
                max_expansion_pct=max_pct,
            )
            extraction_label = "content-aware"
            extra_meta = {"max_expansion_pct": max_pct}
        for i, cell_img in enumerate(cells):
            out = output_dir / f"{name}_frame_{i:02d}.png"
            cell_img.save(out, format="PNG")
        meta = {
            "sheet": str(src),
            "grid": [cols, rows],
            "cell_size": cell_size,
            "extraction": "content-aware" if not downgraded_to_strict else "strict-pitch",
            "frame_count": len(cells),
            "effects_asset": is_effects,
            **extra_meta,
        }
        (output_dir / "frame_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        logger.info("[extract-frames] %s: wrote %d frames to %s", extraction_label, len(cells), output_dir)
        return 0

    try:
        crops, metas = extract_components(
            img,
            chroma_threshold=args.chroma_threshold,
            min_pixels=args.min_pixels,
        )
    except RuntimeError as e:
        logger.error("%s", e)
        return 4

    if args.cell_aware and cols > 1 and rows > 1:
        ordered = assign_components_to_cells(metas, crops, cols, rows, img.width, img.height)
    else:
        # natural top-left sort
        order = sorted(range(len(crops)), key=lambda i: (metas[i].bbox[1], metas[i].bbox[0]))
        ordered = [crops[i] for i in order]

    if not args.allow_count_mismatch:
        # Cell-aware mode always returns a list of length `expected` (with None
        # for missing/colliding cells), so checking len(ordered) != expected
        # would never fire and the count-mismatch guard would be unreachable.
        # Count actual mapped components instead.
        if args.cell_aware:
            non_none = sum(1 for x in ordered if x is not None)
            if non_none != expected:
                logger.error("detected %d components, grid expected %d", non_none, expected)
                return 5
        elif len(ordered) != expected:
            logger.error("detected %d components, grid expected %d", len(ordered), expected)
            return 5

    metadata: dict = {
        "sheet": str(src),
        "grid": [cols, rows],
        "components": [],
        "rejected": 0,
        "warnings": [],
    }

    for i, crop in enumerate(ordered):
        if crop is None:
            metadata["warnings"].append(f"frame {i} missing (no component mapped)")
            continue
        out = output_dir / f"{name}_frame_{i:02d}.png"
        crop.save(out, format="PNG")

    for i, comp in enumerate(metas):
        metadata["components"].append(
            {
                "index": i,
                "bbox": list(comp.bbox),
                "area": comp.area,
                "centroid": list(comp.centroid),
            }
        )
    (output_dir / "frame_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    logger.info("[extract-frames] wrote %d frames to %s", len(metas), output_dir)
    return 0


def _parse_grid(s: str) -> tuple[int, int]:
    parts = s.split("x")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"grid {s!r} malformed. Use CxR like '4x4'.")
    return int(parts[0]), int(parts[1])
