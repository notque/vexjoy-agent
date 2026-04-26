#!/usr/bin/env python3
"""Geometry primitives for the game-sprite-pipeline skill.

Owns alpha-bbox + ground-line + mass-centroid anchor math, the height
percentile + rescale helpers, the canvas-paste anchor router, and the
portrait/spritesheet normalize CLI subcommands. No bg-removal logic —
those primitives live in `sprite_bg.py`. No slicer logic — that lives
in `sprite_slicing.py`.

Public surface (re-exported through `sprite_process` for backward compat):
    Constants:
        PORTRAIT_WIDTH_RANGE, PORTRAIT_HEIGHT_RANGE, PORTRAIT_ASPECT_MIN,
        PORTRAIT_ASPECT_MAX, DEFAULT_BOTTOM_MARGIN.
    Bbox / centroid:
        find_bottom_anchor, find_alpha_bbox, find_alpha_mass_centroid,
        trim_to_bbox.
    Anchor application:
        apply_mass_centroid_anchor, apply_ground_line_anchor,
        anchor_to_canvas.
    Anchor detection (batch):
        detect_centroid_y_target, detect_ground_line, shared_scale_height.
    Resampling helpers:
        rescale_to_height.
    Pipeline functions:
        normalize_portrait, normalize_spritesheet.
    CLI:
        cmd_normalize, cmd_validate_portrait.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError as e:
    print(f"ERROR: Pillow not installed: {e}", file=sys.stderr)
    print("Install with: pip install pillow", file=sys.stderr)
    sys.exit(1)

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORTRAIT_WIDTH_RANGE = (350, 850)
PORTRAIT_HEIGHT_RANGE = (900, 1100)
PORTRAIT_ASPECT_MIN = 1.5  # height / width
PORTRAIT_ASPECT_MAX = 2.5
DEFAULT_BOTTOM_MARGIN = 8


# ---------------------------------------------------------------------------
# Normalization (portrait Phase C / spritesheet Phase F)
# ---------------------------------------------------------------------------
def find_bottom_anchor(img: Image.Image) -> int:
    """Return y-coordinate of lowest non-transparent pixel."""
    if HAS_NUMPY:
        arr = np.array(img.convert("RGBA"))
        alpha = arr[..., 3]
        has_pixel = alpha.max(axis=1) > 0
        nonzero = np.where(has_pixel)[0]
        if len(nonzero) == 0:
            return img.height
        return int(nonzero.max())

    pixels = img.convert("RGBA").load()
    w, h = img.size
    for y in range(h - 1, -1, -1):
        for x in range(w):
            if pixels[x, y][3] > 0:
                return y
    return img.height


def find_alpha_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    """Return (top, bot, left, right) bbox of all non-transparent pixels.

    Differs from PIL's getbbox in that it walks alpha explicitly (not all
    color channels), which is important after bg-removal when low-alpha
    fringe pixels survive.
    """
    if HAS_NUMPY:
        arr = np.array(img.convert("RGBA"))
        alpha = arr[..., 3]
        ys, xs = np.where(alpha > 0)
        if len(ys) == 0:
            return None
        return int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    bbox = img.convert("RGBA").getbbox()
    if bbox is None:
        return None
    left, top, right, bot = bbox
    return top, bot - 1, left, right - 1


def find_alpha_mass_centroid(img: Image.Image) -> tuple[float, float] | None:
    """Return (cx, cy) of alpha-mass centroid (alpha-weighted X and Y means).

    Why this is the load-bearing primitive for anchor v8: bbox-bottom is
    dominated by extended-limb pixels (mic, raised arm, kicking leg).
    The mass centroid integrates over ALL opaque pixels, so a single limb
    extension only shifts it by a few pixels, not 30+. Empirically (live
    demo 05 powerhouse): bbox-bottom-Y stddev=0px (we already pin it),
    centroid-Y stddev=15.84px under bbox-bottom anchor — that 15.84px is
    the visible "hop" the user reported. Pinning the centroid instead
    drops centroid-Y stddev to <2px because the centroid IS the quantity
    being held constant.

    Returns None when there is no opaque content (alpha sum < 1.0).
    """
    if not HAS_NUMPY:
        return None
    arr = np.array(img.convert("RGBA"))
    alpha = arr[..., 3].astype(float)
    if alpha.sum() < 1.0:
        return None
    h, w = alpha.shape
    ys = np.arange(h).reshape(-1, 1).astype(float)
    xs = np.arange(w).reshape(1, -1).astype(float)
    cy = float((alpha * ys).sum() / alpha.sum())
    cx = float((alpha * xs).sum() / alpha.sum())
    return cx, cy


def apply_mass_centroid_anchor(
    frame: Image.Image,
    centroid_y_target: int,
    cell_w: int,
    cell_h: int,
) -> Image.Image:
    """Translate `frame` so its alpha-mass-centroid Y lands at `centroid_y_target`.

    Counterpart to apply_ground_line_anchor but uses the mass centroid as the
    quantity held constant across the batch. Frames where the bbox-bottom is
    a fist or an extended leg still anchor cleanly because the mass centroid
    represents the "body trunk" — limb extensions only nudge it by a few
    pixels, not the dozens that bbox-bottom shifts. Result: the trunk stays
    planted; limb extensions look like motion against a stable body.

    Horizontal: center the mass centroid X on the cell's vertical axis.
    """
    out = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
    centroid = find_alpha_mass_centroid(frame)
    if centroid is None:
        return out
    cx, cy = centroid
    paste_x = (cell_w / 2) - cx
    paste_y = centroid_y_target - cy

    # Fit-to-cell: if frame larger than cell, scale down (preserve aspect).
    bbox = find_alpha_bbox(frame)
    if bbox is not None:
        top, bot, left, right = bbox
        bbox_h = bot - top + 1
        bbox_w = right - left + 1
        scale = 1.0
        if bbox_h > cell_h or bbox_w > cell_w:
            scale = min(cell_h / max(bbox_h, 1), cell_w / max(bbox_w, 1))
        if scale < 1.0:
            new_w = max(1, int(frame.width * scale))
            new_h = max(1, int(frame.height * scale))
            frame = frame.resize((new_w, new_h), Image.Resampling.LANCZOS)
            centroid = find_alpha_mass_centroid(frame)
            if centroid is None:
                return out
            cx, cy = centroid
            paste_x = (cell_w / 2) - cx
            paste_y = centroid_y_target - cy

    out.paste(frame, (round(paste_x), round(paste_y)), frame)
    return out


def detect_centroid_y_target(
    frames: list[Image.Image],
    cell_h: int,
    fallback_pct: float = 0.55,
) -> int:
    """Return the Y at which mass centroids should sit for drift-free anchoring.

    Uses the median centroid Y across all frames with content (not just
    grounded ones). For walk cycles + idle loops the centroid stays in a
    tight band; for action cycles the median is the "rest pose" centroid
    and outlier frames (e.g. a leap) get translated relative to that
    stable Y.

    Falls back to `cell_h * fallback_pct` when there is no opaque content.
    """
    cys: list[float] = []
    for fr in frames:
        c = find_alpha_mass_centroid(fr)
        if c is not None:
            cys.append(c[1])
    if not cys:
        return int(cell_h * fallback_pct)
    cys.sort()
    return int(cys[len(cys) // 2])


def detect_ground_line(
    frames: list[Image.Image],
    cell_h: int,
    bottom_zone_pct: float = 0.30,
    fallback_percentile: float = 75.0,
) -> int:
    """Detect a globally-stable ground line across all frames.

    Algorithm:

    1. For each frame, find its largest connected component (alpha > 0).
       (Using the bbox-bottom of all non-transparent pixels is a good-enough
       proxy when frames have already been bg-removed and contain only one
       character per cell.)
    2. Among the frames whose bbox-bottom falls within the lower
       `bottom_zone_pct` of the cell (default lower 30%), take the median
       bbox-bottom-Y. These are the "feet-on-ground" frames; the median is
       robust to a handful of outliers (a frame where the model drew the
       character one pixel higher than the rest).
    3. Fallback: if NO frame's bbox-bottom is in the lower zone (rare —
       implies every frame is aerial), return the `fallback_percentile`-th
       percentile of all bbox-bottom-Ys.

    Returns the Y coordinate (in cell-canvas space) at which the character's
    lowest grounded pixel typically sits. Each frame is later translated so
    its bbox-bottom lands AT this Y, which keeps the visual ground steady
    across the animation cycle.

    See `references/anchor-alignment.md` for the per-frame vs global trade-off.
    """
    if not frames:
        return cell_h - DEFAULT_BOTTOM_MARGIN

    bottoms: list[int] = []
    for fr in frames:
        bbox = find_alpha_bbox(fr)
        if bbox is None:
            continue
        bottoms.append(bbox[1])

    if not bottoms:
        return cell_h - DEFAULT_BOTTOM_MARGIN

    # Frames whose bbox-bottom is in the lower 30% of the cell are the
    # feet-on-ground reference frames.
    threshold_y = int(cell_h * (1 - bottom_zone_pct))
    grounded_bottoms = [b for b in bottoms if b >= threshold_y]

    if grounded_bottoms:
        # Median: robust to a single-frame outlier where one feet pixel is
        # shifted by ±1 due to AA / chroma fringe artifact.
        sorted_b = sorted(grounded_bottoms)
        return sorted_b[len(sorted_b) // 2]

    # Pure-aerial sequence (every frame's bbox-bottom is high in the cell).
    # Use the 75th percentile of all bbox-bottoms — pins the lowest reach
    # consistently across the animation.
    sorted_all = sorted(bottoms)
    idx = min(len(sorted_all) - 1, int(len(sorted_all) * fallback_percentile / 100.0))
    return sorted_all[idx]


def apply_ground_line_anchor(
    frame: Image.Image,
    ground_line_y: int,
    cell_w: int,
    cell_h: int,
    horizontal_mode: str = "centroid",
) -> Image.Image:
    """Translate `frame` so its alpha-bbox-bottom lands at `ground_line_y`.

    Unlike per-frame bottom-anchor (which moves the FRAME bottom to the cell
    bottom — and thus the character moves with bbox-height), this places the
    CHARACTER'S OWN bottom-most pixel at a fixed, globally-stable Y. Result:
    feet stay planted; head bounces only when the actual silhouette changes.

    `horizontal_mode`:
      - `centroid` (default): center the alpha-mass centroid horizontally.
        Preferred for full-body characters where the center of mass should
        sit on the cell's vertical axis.
      - `bbox`: center the alpha-bbox horizontally (legacy behavior).
        Reasonable for symmetric stances; can drift on lunge frames where
        the bbox extends right but the center of mass is still in the middle.
    """
    out = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
    bbox = find_alpha_bbox(frame)
    if bbox is None:
        return out
    top, bot, left, right = bbox
    bbox_h = bot - top + 1
    bbox_w = right - left + 1

    # Vertical: translate so bbox bottom lands at ground_line_y.
    paste_y = ground_line_y - bot

    # Horizontal: center the bbox or centroid in the cell.
    if horizontal_mode == "centroid" and HAS_NUMPY:
        arr = np.array(frame.convert("RGBA"))
        alpha = arr[..., 3]
        ys, xs = np.where(alpha > 0)
        if len(xs) > 0:
            cx = int(xs.mean())
            paste_x = (cell_w // 2) - cx
        else:
            paste_x = (cell_w - frame.width) // 2
    else:
        # bbox-center horizontal
        bbox_cx = (left + right) // 2
        paste_x = (cell_w // 2) - bbox_cx

    # Fit-to-cell: if the frame's bbox is taller or wider than the cell after
    # translation, scale it down (preserve aspect) so it still fits. Rare but
    # possible when an aerial-leap frame extends way beyond the cell.
    scale = 1.0
    if bbox_h > cell_h or bbox_w > cell_w:
        scale = min(cell_h / max(bbox_h, 1), cell_w / max(bbox_w, 1))

    if scale < 1.0:
        new_w = max(1, int(frame.width * scale))
        new_h = max(1, int(frame.height * scale))
        frame = frame.resize((new_w, new_h), Image.Resampling.LANCZOS)
        # Recompute bbox in the scaled frame
        rescaled_bbox = find_alpha_bbox(frame)
        if rescaled_bbox is None:
            return out
        top, bot, left, right = rescaled_bbox
        paste_y = ground_line_y - bot
        if horizontal_mode == "centroid" and HAS_NUMPY:
            arr = np.array(frame.convert("RGBA"))
            alpha = arr[..., 3]
            ys, xs = np.where(alpha > 0)
            if len(xs) > 0:
                cx = int(xs.mean())
                paste_x = (cell_w // 2) - cx
            else:
                paste_x = (cell_w - frame.width) // 2
        else:
            bbox_cx = (left + right) // 2
            paste_x = (cell_w // 2) - bbox_cx

    out.paste(frame, (paste_x, paste_y), frame)
    return out


def trim_to_bbox(img: Image.Image) -> Image.Image:
    """Crop to non-transparent bounding box."""
    bbox = img.convert("RGBA").getbbox()
    if bbox is None:
        return img
    return img.crop(bbox)


def shared_scale_height(frames: list[Image.Image], percentile: float = 95) -> int:
    """Return target height = Nth percentile of frame heights."""
    heights = sorted(f.height for f in frames)
    if not heights:
        return 0
    idx = int(len(heights) * (percentile / 100.0))
    idx = min(max(idx, 0), len(heights) - 1)
    return heights[idx]


def rescale_to_height(img: Image.Image, target_h: int) -> Image.Image:
    aspect = img.width / max(img.height, 1)
    new_w = max(1, int(target_h * aspect))
    return img.resize((new_w, target_h), Image.Resampling.LANCZOS)


def anchor_to_canvas(
    frame: Image.Image,
    canvas_w: int,
    canvas_h: int,
    bottom_margin: int = DEFAULT_BOTTOM_MARGIN,
    anchor_mode: str = "bottom",
    ground_line_y: int | None = None,
) -> Image.Image:
    """Place frame on transparent canvas with anchor controlled by `anchor_mode`.

    Modes:
      - `bottom` (legacy per-frame): place this frame's lowest pixel at
        `canvas_h - bottom_margin`. Frames with different alpha-bottom Y
        produce visible bouncing — see `apply_ground_line_anchor` for the
        global alternative.
      - `center`: vertically center the frame on the canvas. Use for
        sequences where the character is genuinely off-ground throughout
        (jump-loop, fly).
      - `ground-line`: translate so the frame's alpha-bbox-bottom lands at
        `ground_line_y`. Caller must pre-compute `ground_line_y` via
        `detect_ground_line(frames, canvas_h)` once for the whole batch.
        Provides drift-free animation across mixed grounded/aerial poses.
      - `auto`: pick `bottom` for upright frames (height/width > 1.2),
        `center` otherwise. Legacy behavior; superseded by `ground-line`.
    """
    if anchor_mode == "ground-line":
        if ground_line_y is None:
            ground_line_y = canvas_h - bottom_margin
        return apply_ground_line_anchor(frame, ground_line_y, canvas_w, canvas_h)

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    if anchor_mode == "center":
        paste_y = (canvas_h - frame.height) // 2
    else:
        bottom = find_bottom_anchor(frame)
        paste_y = (canvas_h - bottom_margin) - bottom
    paste_x = (canvas_w - frame.width) // 2
    canvas.paste(frame, (paste_x, paste_y), frame)
    return canvas


def normalize_portrait(
    src: Path,
    dst: Path,
    target_w: int = 600,
    target_h: int = 980,
    padding_pct: float = 0.05,
) -> dict:
    """Trim, re-canvas with padding, bottom-anchor a portrait."""
    img = Image.open(src).convert("RGBA")
    trimmed = trim_to_bbox(img)
    if trimmed.width == 0 or trimmed.height == 0:
        raise RuntimeError("trimmed image is empty (alpha mask removed all content)")

    # Scale to fit within (target_w, target_h) with padding
    avail_w = int(target_w * (1 - 2 * padding_pct))
    avail_h = int(target_h * (1 - 2 * padding_pct))
    scale = min(avail_w / trimmed.width, avail_h / trimmed.height)
    new_w = max(1, int(trimmed.width * scale))
    new_h = max(1, int(trimmed.height * scale))
    scaled = trimmed.resize((new_w, new_h), Image.Resampling.LANCZOS)

    bottom_margin = int(target_h * padding_pct)
    anchored = anchor_to_canvas(scaled, target_w, target_h, bottom_margin=bottom_margin)
    dst.parent.mkdir(parents=True, exist_ok=True)
    anchored.save(dst, format="PNG")
    return {
        "input_size": [img.width, img.height],
        "trimmed_size": [trimmed.width, trimmed.height],
        "scaled_size": [new_w, new_h],
        "output_size": [target_w, target_h],
        "scale_factor": float(scale),
    }


def normalize_spritesheet(
    frames: list[Path],
    output_dir: Path,
    cell_w: int,
    cell_h: int,
    scale_percentile: float = 95,
    bottom_margin: int = DEFAULT_BOTTOM_MARGIN,
    anchor_mode: str = "ground-line",
) -> dict:
    """Shared-scale rescale + anchor alignment for spritesheet frames.

    `anchor_mode` defaults to `ground-line` (the global, drift-free anchor).
    Pass `bottom` for the legacy per-frame behavior (kept for backward compat
    on single-pose action loops where bbox-bottom genuinely tracks the feet).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    imgs = [Image.open(p).convert("RGBA") for p in frames]
    target_h = shared_scale_height(imgs, scale_percentile)
    target_h = min(target_h, cell_h - 2 * bottom_margin)

    rescaled_imgs = [rescale_to_height(img, target_h) for img in imgs]

    # Compute the global ground line ONCE across all rescaled frames so each
    # frame's translation puts its alpha-bbox-bottom at the same Y. This is
    # the drift fix: per-frame bottom-anchor moves with bbox-height, but the
    # global ground line is invariant across the batch.
    ground_line_y: int | None = None
    if anchor_mode == "ground-line":
        # Frames are not yet on the cell canvas; we need to compute ground
        # line in the post-translation coordinate system. We assume that
        # most frames (the grounded ones) will end up with their bottom at
        # `cell_h - bottom_margin`, so use that as the ground line.
        ground_line_y = cell_h - bottom_margin

    metadata: dict = {
        "scale_percentile": scale_percentile,
        "target_height": target_h,
        "cell_size": [cell_w, cell_h],
        "anchor_mode": anchor_mode,
        "ground_line_y": ground_line_y,
        "frames": [],
    }

    for src, img, rescaled in zip(frames, imgs, rescaled_imgs):
        anchored = anchor_to_canvas(
            rescaled,
            cell_w,
            cell_h,
            bottom_margin=bottom_margin,
            anchor_mode=anchor_mode,
            ground_line_y=ground_line_y,
        )
        out = output_dir / src.name
        anchored.save(out, format="PNG")
        anchor_y = find_bottom_anchor(anchored)
        metadata["frames"].append(
            {
                "name": src.name,
                "input_size": [img.width, img.height],
                "scaled_to": [rescaled.width, rescaled.height],
                "anchor_y": anchor_y,
            }
        )

    (output_dir / "anchor_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def cmd_normalize(args: argparse.Namespace) -> int:
    if args.mode == "portrait":
        try:
            meta = normalize_portrait(
                Path(args.input),
                Path(args.output),
                target_w=args.target_w,
                target_h=args.target_h,
            )
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 4
        print(f"[normalize] portrait {args.input} -> {args.output} ({meta['output_size']})", file=sys.stderr)
        return 0

    # spritesheet
    frames = sorted(Path(args.input_dir).glob("*_frame_*.png"))
    if not frames:
        print(f"ERROR: no *_frame_*.png files in {args.input_dir}", file=sys.stderr)
        return 2
    # Map per-frame-bottom alias to the legacy `bottom` mode so internal
    # branching stays simple. ground-line is the new default.
    anchor_mode = "bottom" if args.anchor_mode == "per-frame-bottom" else args.anchor_mode
    meta = normalize_spritesheet(
        frames,
        Path(args.output_dir),
        cell_w=args.cell_size,
        cell_h=args.cell_size,
        scale_percentile=args.scale_percentile,
        anchor_mode=anchor_mode,
    )
    print(
        f"[normalize] spritesheet {len(frames)} frames -> {args.output_dir} (scaled to h={meta['target_height']})",
        file=sys.stderr,
    )
    return 0


# ---------------------------------------------------------------------------
# Portrait dimension validator (Phase D)
# ---------------------------------------------------------------------------
def cmd_validate_portrait(args: argparse.Namespace) -> int:
    img = Image.open(args.input)
    w, h = img.size
    aspect = h / w if w > 0 else 0

    errors: list[str] = []
    if not (PORTRAIT_WIDTH_RANGE[0] <= w <= PORTRAIT_WIDTH_RANGE[1]):
        errors.append(f"width {w} outside {PORTRAIT_WIDTH_RANGE}")
    if not (PORTRAIT_HEIGHT_RANGE[0] <= h <= PORTRAIT_HEIGHT_RANGE[1]):
        errors.append(f"height {h} outside {PORTRAIT_HEIGHT_RANGE}")
    if not (PORTRAIT_ASPECT_MIN <= aspect <= PORTRAIT_ASPECT_MAX):
        errors.append(f"aspect 1:{aspect:.2f} outside [1:{PORTRAIT_ASPECT_MIN}, 1:{PORTRAIT_ASPECT_MAX}]")

    if errors:
        if args.force:
            print(
                f"WARNING: --force-dimensions used; output bypasses gate ({'; '.join(errors)})",
                file=sys.stderr,
            )
            return 0
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 6

    print(
        f"[validate-portrait] PASS ({w}x{h}, aspect 1:{aspect:.2f})",
        file=sys.stderr,
    )
    return 0
