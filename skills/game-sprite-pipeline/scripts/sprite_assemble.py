#!/usr/bin/env python3
"""Output assembly + auto-curation for the game-sprite-pipeline skill.

Owns Phase G (variant ranking) and Phase H (multi-format output: PNG sheet,
animated WebP, animated GIF, Phaser texture-atlas JSON, per-direction
strips). Depends on `sprite_bg` for `matte_composite` (used in GIF
quantization) and on `sprite_anchor` for `find_bottom_anchor` (used in
atlas anchor-Y reporting).

Public surface (re-exported through `sprite_process` for backward compat):
    VariantStats, _compute_variant_stats, cmd_auto_curate,
    cmd_contact_sheet, assemble_outputs, cmd_assemble.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError as e:
    print(f"ERROR: Pillow not installed: {e}", file=sys.stderr)
    print("Install with: pip install pillow", file=sys.stderr)
    sys.exit(1)

from sprite_anchor import find_bottom_anchor
from sprite_bg import DEFAULT_GIF_FPS, matte_composite
from sprite_slicing import _parse_grid


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
        print("ERROR: no images found in any variant dir", file=sys.stderr)
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

    # Animated WebP — preferred output. Full 8-bit alpha, no quantization
    # bleed at silhouette edges. Modern browsers autoplay animated WebP
    # the same way they autoplay GIF.
    webp_path = output_dir / f"{name}.webp"
    duration = int(1000 / max(fps, 1))
    valid_frames = [f for f in frames if f is not None]
    if valid_frames:
        valid_frames[0].save(
            webp_path,
            save_all=True,
            append_images=valid_frames[1:],
            duration=duration,
            loop=0,
            format="WebP",
        )

    # Animated GIF — compatibility fallback. GIF's 1-bit alpha + 256-color
    # adaptive palette can resurrect magenta fringe at silhouette edges
    # even when the RGBA source is clean (the palette quantizer allocates
    # a pink index from anti-aliased boundary pixels). Matte-compositing
    # each frame over a neutral middle-gray BEFORE quantizing prevents
    # this — the palette has no pink reference, anti-aliased edges blend
    # to gray. See bg-removal-local.md "GIF format bleed at silhouette
    # edges" for details.
    gif_path = output_dir / f"{name}.gif"
    if valid_frames:
        gif_imgs = [
            matte_composite(f, matte=(40, 40, 40)).convert("P", palette=Image.Palette.ADAPTIVE) for f in valid_frames
        ]
        gif_imgs[0].save(
            gif_path,
            save_all=True,
            append_images=gif_imgs[1:],
            duration=duration,
            loop=0,
            disposal=2,
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


# Re-export DEFAULT_GIF_FPS so existing CLI argparse defaults referencing
# `sprite_assemble.DEFAULT_GIF_FPS` still resolve. Owned canonically by
# sprite_bg.
__all__ = [
    "DEFAULT_GIF_FPS",
    "VariantStats",
    "_compute_variant_stats",
    "assemble_outputs",
    "cmd_assemble",
    "cmd_auto_curate",
    "cmd_contact_sheet",
]
