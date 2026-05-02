#!/usr/bin/env python3
"""Process selected video frames into spritesheet row format (Phase 5).

Takes selected frames, removes backgrounds, resizes to cell dimensions,
aligns ground-line anchors, and composites into a horizontal strip.
Optionally generates a preview GIF.

Subcommands:
    process     Process selected frames into a horizontal strip

Usage:
    python3 video_process_frames.py process \\
        --input-dir selected/ --cell-size 256 --output strip.png --bg-mode chroma

    python3 video_process_frames.py process \\
        --input-dir selected/ --cell-size 256 --output strip.png \\
        --bg-mode chroma --preview-gif preview.gif
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger("sprite-pipeline.video_process_frames")

try:
    from PIL import Image
except ImportError as e:
    logger.error("Pillow not installed: %s", e)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import sprite_anchor
import sprite_bg


def process_frames(
    input_dir: Path,
    output_path: Path,
    cell_size: int = 256,
    bg_mode: str = "chroma",
    chroma_threshold: int = sprite_bg.DEFAULT_CHROMA_THRESHOLD,
    preview_gif: Path | None = None,
    fps: int = 10,
) -> dict:
    """Process selected frames into a horizontal strip.

    Args:
        input_dir: Directory of selected frame PNGs.
        output_path: Path for the output strip PNG.
        cell_size: Width and height of each cell in the strip.
        bg_mode: Background removal mode (chroma, gray-tolerance, rembg).
        chroma_threshold: Threshold for chroma key bg removal.
        preview_gif: Optional path to write a preview GIF.
        fps: FPS for preview GIF.

    Returns:
        Dict with output paths and frame count.

    Raises:
        FileNotFoundError: If input_dir doesn't exist or has no frames.
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    frames = sorted(input_dir.glob("selected_*.png"))
    if not frames:
        frames = sorted(input_dir.glob("*.png"))
    if not frames:
        raise FileNotFoundError(f"No PNG frames found in {input_dir}")

    processed: list[Image.Image] = []
    nobg_dir = input_dir / "_nobg"
    nobg_dir.mkdir(exist_ok=True)

    # Phase 1: Background removal
    for frame_path in frames:
        nobg_path = nobg_dir / frame_path.name
        if bg_mode == "chroma":
            sprite_bg.remove_bg_chroma(frame_path, nobg_path, chroma_threshold)
        elif bg_mode == "gray-tolerance":
            sprite_bg.remove_bg_gray_tolerance(frame_path, nobg_path)
        elif bg_mode == "rembg":
            sprite_bg.remove_bg_rembg(frame_path, nobg_path)
        else:
            # Fallback: just copy
            Image.open(frame_path).convert("RGBA").save(nobg_path, format="PNG")

        img = Image.open(nobg_path).convert("RGBA")
        processed.append(img)

    # Phase 2: Shared scale + ground-line anchor
    # Find shared scale height
    target_h = int(cell_size * 0.85)  # 85% of cell for breathing room
    scaled: list[Image.Image] = []
    for img in processed:
        bbox = img.getbbox()
        if bbox is None:
            scaled.append(Image.new("RGBA", (cell_size, cell_size), (0, 0, 0, 0)))
            continue
        trimmed = img.crop(bbox)
        # Scale to fit within cell while maintaining aspect ratio
        w, h = trimmed.size
        if h > 0:
            scale_factor = target_h / h
            new_w = max(1, int(w * scale_factor))
            new_h = max(1, int(h * scale_factor))
            if new_w > cell_size:
                scale_factor = cell_size / w
                new_w = cell_size
                new_h = max(1, int(h * scale_factor))
            trimmed = trimmed.resize((new_w, new_h), Image.Resampling.LANCZOS)
        scaled.append(trimmed)

    # Phase 3: Anchor alignment and compositing
    anchored: list[Image.Image] = []
    for frame in scaled:
        canvas = Image.new("RGBA", (cell_size, cell_size), (0, 0, 0, 0))
        bbox = frame.getbbox()
        if bbox is None:
            anchored.append(canvas)
            continue
        # Center horizontally, anchor bottom with margin
        x_offset = (cell_size - frame.width) // 2
        bottom_margin = int(cell_size * 0.05)
        y_offset = cell_size - frame.height - bottom_margin
        y_offset = max(0, y_offset)
        canvas.paste(frame, (x_offset, y_offset), frame)
        anchored.append(canvas)

    # Phase 4: Composite into horizontal strip
    strip_width = cell_size * len(anchored)
    strip = Image.new("RGBA", (strip_width, cell_size), (0, 0, 0, 0))
    for i, frame in enumerate(anchored):
        strip.paste(frame, (i * cell_size, 0), frame)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    strip.save(output_path, format="PNG")
    logger.info("[video-process] Strip: %d frames @ %dpx -> %s", len(anchored), cell_size, output_path)

    # Optional preview GIF
    result: dict = {
        "strip": str(output_path),
        "frame_count": len(anchored),
        "cell_size": cell_size,
    }

    if preview_gif is not None and anchored:
        preview_gif.parent.mkdir(parents=True, exist_ok=True)
        duration = int(1000 / max(fps, 1))
        gif_frames = [
            sprite_bg.matte_composite(f, matte=(40, 40, 40)).convert("P", palette=Image.Palette.ADAPTIVE)
            for f in anchored
        ]
        gif_frames[0].save(
            preview_gif,
            save_all=True,
            append_images=gif_frames[1:],
            duration=duration,
            loop=0,
            disposal=2,
        )
        result["preview_gif"] = str(preview_gif)
        logger.info("[video-process] Preview GIF -> %s", preview_gif)

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def cmd_process(args: argparse.Namespace) -> int:
    """process subcommand."""
    try:
        result = process_frames(
            input_dir=Path(args.input_dir),
            output_path=Path(args.output),
            cell_size=args.cell_size,
            bg_mode=args.bg_mode,
            chroma_threshold=args.chroma_threshold,
            preview_gif=Path(args.preview_gif) if args.preview_gif else None,
            fps=args.fps,
        )
    except FileNotFoundError as e:
        logger.error("%s", e)
        return 1

    print(f"Processed {result['frame_count']} frames -> {result['strip']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    proc = sub.add_parser("process", help="Process selected frames into strip")
    proc.add_argument("--input-dir", required=True, help="Directory of selected frame PNGs")
    proc.add_argument("--cell-size", type=int, default=256, help="Cell size in pixels (default 256)")
    proc.add_argument("--output", required=True, help="Output strip PNG path")
    proc.add_argument(
        "--bg-mode",
        choices=list(sprite_bg.BG_MODE_CHOICES),
        default="chroma",
        help="Background removal mode",
    )
    proc.add_argument("--chroma-threshold", type=int, default=sprite_bg.DEFAULT_CHROMA_THRESHOLD)
    proc.add_argument("--preview-gif", help="Optional path for preview GIF output")
    proc.add_argument("--fps", type=int, default=10, help="FPS for preview GIF (default 10)")
    proc.set_defaults(func=cmd_process)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(name)s] %(levelname)s: %(message)s",
            stream=sys.stderr,
        )
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
