#!/usr/bin/env python3
"""
Post-processing for the game-sprite-pipeline skill.

Phases D-H of the spritesheet pipeline + portrait-mode bg removal, trim,
and validation. All operations are local + deterministic. No paid APIs.

Subcommands:
    extract-frames      Phase D: connected-components frame detection
    remove-bg           Phase B (portrait) or Phase E (sheet): magenta chroma key
    normalize           Phase C (portrait) or Phase F (sheet): trim/scale/anchor
    validate-portrait   Phase D (portrait): width/height/aspect gate
    contact-sheet       Build a contact-sheet image from variant directories
    auto-curate         Phase G: deterministic ranking of variants
    assemble            Phase H: PNG sheet + GIF + WebP + atlas + strips
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

try:
    from PIL import Image, ImageDraw
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
MAGENTA = (255, 0, 255)
DEFAULT_CHROMA_THRESHOLD = 30
DEFAULT_MIN_COMPONENT_PIXELS = 200
PORTRAIT_WIDTH_RANGE = (350, 850)
PORTRAIT_HEIGHT_RANGE = (900, 1100)
PORTRAIT_ASPECT_MIN = 1.5  # height / width
PORTRAIT_ASPECT_MAX = 2.5
DEFAULT_BOTTOM_MARGIN = 8
DEFAULT_GIF_FPS = 10


# ---------------------------------------------------------------------------
# Chroma key (portrait Phase B + spritesheet Phase E)
# ---------------------------------------------------------------------------
def chroma_pass1(img: Image.Image, chroma: tuple[int, int, int], threshold: int) -> Image.Image:
    """Mask pixels within sum-of-abs-diff threshold of chroma."""
    img = img.convert("RGBA")
    if HAS_NUMPY:
        arr = np.array(img)
        rgb = arr[..., :3].astype(int)
        diff = np.abs(rgb - np.array(chroma)).sum(axis=-1)
        mask = diff <= threshold
        arr[mask, 3] = 0
        return Image.fromarray(arr, "RGBA")

    # Pure-Python fallback
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if abs(r - chroma[0]) + abs(g - chroma[1]) + abs(b - chroma[2]) <= threshold:
                pixels[x, y] = (r, g, b, 0)
    return img


def chroma_pass2_edge_flood(img: Image.Image, chroma: tuple[int, int, int], threshold: int) -> Image.Image:
    """Flood-fill from canvas edges with looser threshold to catch fringe."""
    img = img.convert("RGBA")
    if not HAS_NUMPY:
        # Without numpy this would be very slow; skip pass 2 in pure-Python mode
        return img

    arr = np.array(img)
    h, w = arr.shape[:2]
    visited = np.zeros((h, w), dtype=bool)
    chroma_arr = np.array(chroma)

    queue: deque[tuple[int, int]] = deque()
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
        if visited[y, x]:
            continue
        if arr[y, x, 3] == 0:
            visited[y, x] = True
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                queue.append((y + dy, x + dx))
            continue
        rgb = arr[y, x, :3].astype(int)
        diff = int(abs(rgb - chroma_arr).sum())
        if diff > threshold:
            continue
        visited[y, x] = True
        arr[y, x, 3] = 0
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            queue.append((y + dy, x + dx))

    return Image.fromarray(arr, "RGBA")


def remove_bg_chroma(input_path: Path, output_path: Path, threshold: int) -> None:
    """Two-pass chroma key: tight pass + edge flood."""
    img = Image.open(input_path)
    pass1 = chroma_pass1(img, MAGENTA, threshold)
    pass2 = chroma_pass2_edge_flood(pass1, MAGENTA, threshold * 2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pass2.save(output_path, format="PNG")


def remove_bg_rembg(input_path: Path, output_path: Path) -> None:
    """rembg fallback for non-magenta backgrounds. Opt-in dep."""
    try:
        from rembg import remove
    except ImportError as e:
        raise RuntimeError(
            "rembg not installed. Run `pip install rembg onnxruntime`, or use --bg-mode chroma (default)."
        ) from e

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(remove(input_path.read_bytes()))


def cmd_remove_bg(args: argparse.Namespace) -> int:
    inputs = [Path(p) for p in args.input]
    output_dir = Path(args.output_dir) if args.output_dir else None
    if len(inputs) > 1 and output_dir is None:
        print("ERROR: --output-dir required when processing multiple inputs", file=sys.stderr)
        return 2

    for src in inputs:
        if output_dir:
            dst = output_dir / src.name
        else:
            dst = Path(args.output) if args.output else src.with_suffix(".nobg.png")

        try:
            if args.mode == "chroma":
                remove_bg_chroma(src, dst, args.chroma_threshold)
            elif args.mode == "rembg":
                remove_bg_rembg(src, dst)
            elif args.mode == "auto":
                # try chroma; if alpha mask is suspiciously small, fall through to rembg
                remove_bg_chroma(src, dst, args.chroma_threshold)
                if _alpha_coverage_too_low(dst):
                    print(
                        f"[remove-bg] auto: chroma low-coverage; falling back to rembg for {src.name}", file=sys.stderr
                    )
                    remove_bg_rembg(src, dst)
            else:
                print(f"ERROR: unknown bg-mode {args.mode!r}", file=sys.stderr)
                return 2
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 4
        print(f"[remove-bg] {src} -> {dst}", file=sys.stderr)
    return 0


def _alpha_coverage_too_low(path: Path) -> bool:
    """Return True if the alpha-mask coverage is below 30% of canvas."""
    img = Image.open(path).convert("RGBA")
    if HAS_NUMPY:
        arr = np.array(img)
        opaque = (arr[..., 3] > 0).sum()
        total = arr.shape[0] * arr.shape[1]
        return (opaque / total) < 0.3
    return False  # without numpy we don't run auto mode anyway


# ---------------------------------------------------------------------------
# Connected-components frame detection (Phase D)
# ---------------------------------------------------------------------------
@dataclass
class Component:
    bbox: tuple[int, int, int, int]  # left, top, right, bottom
    area: int
    centroid: tuple[float, float]


def label_components_numpy(mask) -> tuple[object, int]:
    """Connected-components labeling. Tries scipy.ndimage.label first."""
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


def cmd_extract_frames(args: argparse.Namespace) -> int:
    src = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(src)
    cols, rows = _parse_grid(args.grid)
    expected = cols * rows

    try:
        crops, metas = extract_components(
            img,
            chroma_threshold=args.chroma_threshold,
            min_pixels=args.min_pixels,
        )
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 4

    if args.cell_aware and cols > 1 and rows > 1:
        ordered = assign_components_to_cells(metas, crops, cols, rows, img.width, img.height)
    else:
        # natural top-left sort
        order = sorted(range(len(crops)), key=lambda i: (metas[i].bbox[1], metas[i].bbox[0]))
        ordered = [crops[i] for i in order]

    if not args.allow_count_mismatch and len(ordered) != expected:
        if args.cell_aware:
            non_none = sum(1 for x in ordered if x is not None)
            if non_none != expected:
                print(
                    f"ERROR: detected {non_none} components, grid expected {expected}",
                    file=sys.stderr,
                )
                return 5
        else:
            print(
                f"ERROR: detected {len(ordered)} components, grid expected {expected}",
                file=sys.stderr,
            )
            return 5

    name = args.name or src.stem
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

    print(f"[extract-frames] wrote {len(metas)} frames to {output_dir}", file=sys.stderr)
    return 0


def _parse_grid(s: str) -> tuple[int, int]:
    parts = s.split("x")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"grid {s!r} malformed. Use CxR like '4x4'.")
    return int(parts[0]), int(parts[1])


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
) -> Image.Image:
    """Place frame on transparent canvas with feet at canvas_h - bottom_margin."""
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
    anchor_mode: str = "bottom",
) -> dict:
    """Shared-scale rescale + bottom-anchor for spritesheet frames."""
    output_dir.mkdir(parents=True, exist_ok=True)

    imgs = [Image.open(p).convert("RGBA") for p in frames]
    target_h = shared_scale_height(imgs, scale_percentile)
    target_h = min(target_h, cell_h - 2 * bottom_margin)

    metadata: dict = {
        "scale_percentile": scale_percentile,
        "target_height": target_h,
        "cell_size": [cell_w, cell_h],
        "anchor_mode": anchor_mode,
        "frames": [],
    }

    for src, img in zip(frames, imgs):
        rescaled = rescale_to_height(img, target_h)
        anchored = anchor_to_canvas(
            rescaled,
            cell_w,
            cell_h,
            bottom_margin=bottom_margin,
            anchor_mode=anchor_mode,
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
    meta = normalize_spritesheet(
        frames,
        Path(args.output_dir),
        cell_w=args.cell_size,
        cell_h=args.cell_size,
        scale_percentile=args.scale_percentile,
        anchor_mode=args.anchor_mode,
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


# ---------------------------------------------------------------------------
# Auto-curation (Phase G)
# ---------------------------------------------------------------------------
@dataclass
class VariantStats:
    path: Path
    seed: int
    edge_touch_frames: int = 0
    height_variance: float = 0.0
    frame_count: int = 0


def _compute_variant_stats(frames: list[Path], seed: int) -> VariantStats:
    if not frames:
        return VariantStats(path=Path(), seed=seed)
    heights: list[int] = []
    edge_touches = 0
    for fp in frames:
        img = Image.open(fp).convert("RGBA")
        bbox = img.getbbox()
        if bbox is None:
            continue
        w, h = img.size
        if bbox[0] == 0 or bbox[1] == 0 or bbox[2] == w or bbox[3] == h:
            edge_touches += 1
        heights.append(bbox[3] - bbox[1])
    median = sorted(heights)[len(heights) // 2] if heights else 0
    variance = sum((x - median) ** 2 for x in heights) / max(len(heights), 1)
    return VariantStats(
        path=frames[0].parent,
        seed=seed,
        edge_touch_frames=edge_touches,
        height_variance=variance,
        frame_count=len(frames),
    )


def cmd_auto_curate(args: argparse.Namespace) -> int:
    variants_dir = Path(args.variants_dir)
    variants = sorted([p for p in variants_dir.iterdir() if p.is_dir()])
    if not variants:
        print(f"ERROR: no variant subdirectories in {variants_dir}", file=sys.stderr)
        return 5

    stats: list[VariantStats] = []
    for v in variants:
        seed_match = v.name.split("_")[-1] if "_" in v.name else "0"
        try:
            seed = int(seed_match)
        except ValueError:
            seed = 0
        frames = sorted(v.glob("*_frame_*.png"))
        s = _compute_variant_stats(frames, seed=seed)
        s.path = v
        stats.append(s)

    stats.sort(key=lambda s: (s.edge_touch_frames, s.height_variance, s.seed))
    winner = stats[0]
    print(
        f"[auto-curate] winner: {winner.path.name} "
        f"(edge_touch={winner.edge_touch_frames}, variance={winner.height_variance:.2f}, seed={winner.seed})",
        file=sys.stderr,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "winner": str(winner.path),
                "ranking": [
                    {
                        "path": str(s.path),
                        "edge_touch_frames": s.edge_touch_frames,
                        "height_variance": s.height_variance,
                        "seed": s.seed,
                    }
                    for s in stats
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


# ---------------------------------------------------------------------------
# Contact sheet
# ---------------------------------------------------------------------------
def cmd_contact_sheet(args: argparse.Namespace) -> int:
    variants_dir = Path(args.variants_dir)
    variants = sorted([p for p in variants_dir.iterdir() if p.is_dir()])
    if not variants:
        print(f"ERROR: no variants in {variants_dir}", file=sys.stderr)
        return 5

    thumbs: list[Image.Image] = []
    for v in variants:
        sheet_candidate = next(v.glob("*_sheet.png"), None) or next(v.glob("*.png"), None)
        if sheet_candidate is None:
            continue
        img = Image.open(sheet_candidate).convert("RGBA")
        img.thumbnail((args.thumb_size, args.thumb_size), Image.Resampling.LANCZOS)
        thumbs.append(img)

    if not thumbs:
        print(f"ERROR: no images found in any variant dir", file=sys.stderr)
        return 5

    cols = max(1, args.cols)
    rows = (len(thumbs) + cols - 1) // cols
    cell_w = max(t.width for t in thumbs)
    cell_h = max(t.height for t in thumbs)
    sheet = Image.new("RGBA", (cell_w * cols, cell_h * rows), (32, 32, 32, 255))
    draw = ImageDraw.Draw(sheet)
    for i, thumb in enumerate(thumbs):
        r, c = divmod(i, cols)
        x = c * cell_w + (cell_w - thumb.width) // 2
        y = r * cell_h + (cell_h - thumb.height) // 2
        sheet.paste(thumb, (x, y), thumb)
        draw.text((c * cell_w + 4, r * cell_h + 4), f"#{i}", fill=(255, 255, 255, 255))

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output, format="PNG")
    print(f"[contact-sheet] {args.output} ({len(thumbs)} variants, {cols}x{rows})", file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------
# Final assembly (Phase H)
# ---------------------------------------------------------------------------
def assemble_outputs(
    frames: list[Image.Image],
    output_dir: Path,
    name: str,
    grid_cols: int,
    grid_rows: int,
    cell_w: int,
    cell_h: int,
    fps: int,
    emit_strips: bool,
) -> dict:
    """Phase H: PNG sheet, GIF, WebP, atlas JSON, optional per-direction strips."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # PNG sheet
    sheet = Image.new("RGBA", (cell_w * grid_cols, cell_h * grid_rows), (0, 0, 0, 0))
    for i, frame in enumerate(frames):
        if frame is None:
            continue
        r, c = divmod(i, grid_cols)
        sheet.paste(frame, (c * cell_w, r * cell_h), frame)
    sheet_path = output_dir / f"{name}_sheet.png"
    sheet.save(sheet_path, format="PNG")

    # Animated GIF
    gif_path = output_dir / f"{name}.gif"
    duration = int(1000 / max(fps, 1))
    valid_frames = [f for f in frames if f is not None]
    if valid_frames:
        valid_frames[0].save(
            gif_path,
            save_all=True,
            append_images=valid_frames[1:],
            duration=duration,
            loop=0,
            disposal=2,
            transparency=0,
        )

    # Animated WebP
    webp_path = output_dir / f"{name}.webp"
    if valid_frames:
        valid_frames[0].save(
            webp_path,
            save_all=True,
            append_images=valid_frames[1:],
            duration=duration,
            loop=0,
            format="WebP",
        )

    # Per-frame PNGs
    frames_dir = output_dir / f"{name}_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for i, frame in enumerate(frames):
        if frame is None:
            continue
        frame.save(frames_dir / f"{name}_frame_{i:02d}.png", format="PNG")

    # Phaser atlas JSON
    atlas: dict = {
        "frames": {},
        "meta": {
            "app": "game-sprite-pipeline",
            "version": "1.0.0",
            "image": f"{name}_sheet.png",
            "format": "RGBA8888",
            "size": {"w": sheet.width, "h": sheet.height},
            "scale": "1",
        },
    }
    for i, frame in enumerate(frames):
        if frame is None:
            continue
        r, c = divmod(i, grid_cols)
        anchor_y = find_bottom_anchor(frame)
        atlas["frames"][f"frame_{i:02d}.png"] = {
            "frame": {"x": c * cell_w, "y": r * cell_h, "w": cell_w, "h": cell_h},
            "rotated": False,
            "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": cell_w, "h": cell_h},
            "sourceSize": {"w": cell_w, "h": cell_h},
            "anchor": {"x": 0.5, "y": round(anchor_y / cell_h, 4) if cell_h else 0},
        }
    atlas_path = output_dir / f"{name}.json"
    atlas_path.write_text(json.dumps(atlas, indent=2), encoding="utf-8")

    # Per-direction strips (4xR or 8xR only)
    strips: dict[str, str] = {}
    if emit_strips and grid_cols in (4, 8):
        directions_4 = ["down", "left", "right", "up"]
        directions_8 = ["down", "down-left", "left", "up-left", "up", "up-right", "right", "down-right"]
        directions = directions_4 if grid_cols == 4 else directions_8
        for r in range(grid_rows):
            if r >= len(directions):
                break
            dir_name = directions[r]
            strip = Image.new("RGBA", (cell_w * grid_cols, cell_h), (0, 0, 0, 0))
            for c in range(grid_cols):
                idx = r * grid_cols + c
                if idx < len(frames) and frames[idx] is not None:
                    strip.paste(frames[idx], (c * cell_w, 0), frames[idx])
            strip_path = output_dir / f"{name}_{dir_name}.png"
            strip.save(strip_path, format="PNG")
            strips[dir_name] = str(strip_path)

    return {
        "sheet": str(sheet_path),
        "gif": str(gif_path),
        "webp": str(webp_path),
        "frames_dir": str(frames_dir),
        "atlas": str(atlas_path),
        "strips": strips,
    }


def cmd_assemble(args: argparse.Namespace) -> int:
    cols, rows = _parse_grid(args.grid)
    frame_paths = sorted(Path(args.frames_dir).glob("*_frame_*.png"))
    expected = cols * rows
    frames: list[Image.Image | None] = []
    by_idx: dict[int, Image.Image] = {}
    for p in frame_paths:
        idx_str = p.stem.split("_frame_")[-1]
        try:
            idx = int(idx_str)
        except ValueError:
            continue
        by_idx[idx] = Image.open(p).convert("RGBA")
    for i in range(expected):
        frames.append(by_idx.get(i))

    name = args.name or Path(args.frames_dir).name
    emit_strips = cols in (4, 8) and not args.no_strips
    result = assemble_outputs(
        frames=frames,
        output_dir=Path(args.output_dir),
        name=name,
        grid_cols=cols,
        grid_rows=rows,
        cell_w=args.cell_size,
        cell_h=args.cell_size,
        fps=args.fps,
        emit_strips=emit_strips,
    )
    print(
        f"[assemble] {name}: sheet+gif+webp+atlas+frames written to {args.output_dir}",
        file=sys.stderr,
    )
    if result["strips"]:
        print(f"[assemble] strips: {', '.join(result['strips'].keys())}", file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    rb = sub.add_parser("remove-bg", help="Remove background (chroma key default)")
    rb.add_argument("input", nargs="+", help="Input PNG path(s)")
    rb.add_argument("--output", help="Output path (single input)")
    rb.add_argument("--output-dir", help="Output directory (multi-input)")
    rb.add_argument("--mode", choices=["chroma", "rembg", "auto"], default="chroma")
    rb.add_argument("--chroma-threshold", type=int, default=DEFAULT_CHROMA_THRESHOLD)
    rb.set_defaults(func=cmd_remove_bg)

    ef = sub.add_parser("extract-frames", help="Phase D: connected-components frame detection")
    ef.add_argument("--input", required=True, help="Spritesheet PNG path")
    ef.add_argument("--grid", required=True, help="Expected grid CxR (e.g., 4x4)")
    ef.add_argument("--output-dir", required=True, help="Where to write frame PNGs")
    ef.add_argument("--name", help="Frame name prefix (default: input stem)")
    ef.add_argument("--chroma-threshold", type=int, default=DEFAULT_CHROMA_THRESHOLD)
    ef.add_argument("--min-pixels", type=int, default=DEFAULT_MIN_COMPONENT_PIXELS)
    ef.add_argument("--cell-aware", action="store_true", default=True, help="Map components to cells via centroid")
    ef.add_argument("--allow-count-mismatch", action="store_true", help="Tolerate component count != grid")
    ef.set_defaults(func=cmd_extract_frames)

    nz = sub.add_parser("normalize", help="Trim/scale/anchor")
    nz.add_argument("--mode", choices=["portrait", "spritesheet"], required=True)
    nz.add_argument("--input", help="Input image (portrait mode)")
    nz.add_argument("--input-dir", help="Input directory of frames (spritesheet mode)")
    nz.add_argument("--output", help="Output path (portrait)")
    nz.add_argument("--output-dir", help="Output directory (spritesheet)")
    nz.add_argument("--target-w", type=int, default=600)
    nz.add_argument("--target-h", type=int, default=980)
    nz.add_argument("--cell-size", type=int, default=256)
    nz.add_argument("--scale-percentile", type=float, default=95)
    nz.add_argument("--anchor-mode", choices=["bottom", "center", "auto"], default="bottom")
    nz.set_defaults(func=cmd_normalize)

    vp = sub.add_parser("validate-portrait", help="Phase D portrait dimension gate")
    vp.add_argument("input", help="Portrait PNG path")
    vp.add_argument("--force", action="store_true", dest="force", help="Skip the gate (logs warning)")
    vp.set_defaults(func=cmd_validate_portrait)

    cs = sub.add_parser("contact-sheet", help="Build a variant contact sheet image")
    cs.add_argument("--variants-dir", required=True, help="Directory containing variant_NNN/ subdirs")
    cs.add_argument("--output", required=True, help="Output contact sheet PNG")
    cs.add_argument("--cols", type=int, default=4)
    cs.add_argument("--thumb-size", type=int, default=256)
    cs.set_defaults(func=cmd_contact_sheet)

    ac = sub.add_parser("auto-curate", help="Phase G: deterministic ranking of variants")
    ac.add_argument("--variants-dir", required=True)
    ac.add_argument("--output", required=True, help="Where to write ranking JSON")
    ac.set_defaults(func=cmd_auto_curate)

    ab = sub.add_parser("assemble", help="Phase H: PNG sheet + GIF + WebP + atlas + strips")
    ab.add_argument("--frames-dir", required=True)
    ab.add_argument("--grid", required=True)
    ab.add_argument("--cell-size", type=int, default=256)
    ab.add_argument("--output-dir", required=True)
    ab.add_argument("--name")
    ab.add_argument("--fps", type=int, default=DEFAULT_GIF_FPS)
    ab.add_argument("--no-strips", action="store_true", help="Skip per-direction strips")
    ab.set_defaults(func=cmd_assemble)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
