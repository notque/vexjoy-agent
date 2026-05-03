#!/usr/bin/env python3
"""Deterministic breathing idle loop from a single static portrait.

Pure Pillow — zero API calls. Splits at body ratio, applies Y-scale + lift.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


def _alpha_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Return the bounding box of non-transparent pixels, or None if empty."""
    return image.getchannel("A").getbbox()


def _split_at_ratio(
    image: Image.Image,
    split_y: int,
) -> tuple[Image.Image, Image.Image]:
    """Split image into upper and lower regions at split_y."""
    top = image.crop((0, 0, image.width, split_y))
    bottom = image.crop((0, split_y, image.width, image.height))
    return top, bottom


def build_breath_frame(
    base: Image.Image,
    scale_y: float,
    lift_px: int,
    body_ratio: float,
) -> Image.Image:
    """Create a single breathing frame by scaling upper body.

    Args:
        base: Source RGBA image.
        scale_y: Vertical scale factor for upper body (e.g. 1.006 = inhale).
        lift_px: Pixels to lift upper body (0 or 1).
        body_ratio: Fraction of alpha-bbox height for the split point
            (0.74 = head+torso vs legs).

    Returns:
        New RGBA image with the breathing transform applied.
    """
    bbox = _alpha_bbox(base)
    if bbox is None:
        return base.copy()

    # Split at ratio within the character's alpha bounding box
    split_y = round(bbox[1] + ((bbox[3] - bbox[1]) * body_ratio))
    top, bottom = _split_at_ratio(base, split_y)
    top_bbox = _alpha_bbox(top)

    canvas = Image.new("RGBA", base.size, (0, 0, 0, 0))
    canvas.alpha_composite(bottom, (0, split_y))

    if top_bbox is None:
        return canvas

    # Scale the upper-body subject region
    top_subject = top.crop(top_bbox)
    scaled_height = max(1, round(top_subject.height * scale_y))
    scaled_top = top_subject.resize(
        (top_subject.width, scaled_height),
        Image.Resampling.BICUBIC,
    )

    # Anchor at the bottom of the upper region (torso stays grounded)
    anchor_bottom = top_bbox[3]
    paste_y = anchor_bottom - scaled_height - lift_px
    canvas.alpha_composite(scaled_top, (top_bbox[0], paste_y))
    return canvas


def generate_idle_frames(
    base: Image.Image,
    body_ratio: float = 0.74,
    num_frames: int = 4,
    inhale_scale_y: float = 1.006,
    exhale_scale_y: float = 0.997,
    inhale_lift_px: int = 1,
    exhale_lift_px: int = 0,
) -> list[Image.Image]:
    """Generate a breathing idle loop from a single static image.

    The breathing pattern is optimized for 4 frames (neutral-inhale-neutral-
    exhale). ``num_frames`` truncates this fixed cycle; values other than 4
    are accepted but produce an incomplete loop. Future versions may
    interpolate additional keyframes.

    Args:
        base: Source RGBA portrait image.
        body_ratio: Head+torso fraction (default 0.74).
        num_frames: Number of frames (default 4, see note above).
        inhale_scale_y: Y scale for inhale frames.
        exhale_scale_y: Y scale for exhale frames.
        inhale_lift_px: Pixel lift for inhale.
        exhale_lift_px: Pixel lift for exhale.

    Returns:
        List of RGBA frames forming a breathing loop.
    """
    if num_frames < 2:
        return [base.copy()]

    # 4-frame loop: neutral -> inhale -> neutral -> exhale
    frames = [
        base.copy(),
        build_breath_frame(base, inhale_scale_y, inhale_lift_px, body_ratio),
        base.copy(),
        build_breath_frame(base, exhale_scale_y, exhale_lift_px, body_ratio),
    ]
    return frames[:num_frames]


def write_strip(frames: list[Image.Image], output: Path) -> None:
    """Write frames as a horizontal strip PNG."""
    if not frames:
        return
    w, h = frames[0].size
    strip = Image.new("RGBA", (w * len(frames), h), (0, 0, 0, 0))
    for i, frame in enumerate(frames):
        strip.alpha_composite(frame, (i * w, 0))
    output.parent.mkdir(parents=True, exist_ok=True)
    strip.save(output, format="PNG")


def write_animation(
    frames: list[Image.Image],
    output: Path,
    fps: int,
) -> None:
    """Write frames as an animated GIF or WebP."""
    if not frames:
        return
    duration_ms = max(1, round(1000 / fps))
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate a deterministic breathing idle loop from a static portrait.",
    )
    parser.add_argument("--input", required=True, help="Path to source portrait PNG")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument(
        "--body-ratio",
        type=float,
        default=0.74,
        help="Split ratio: head+torso fraction (default 0.74)",
    )
    parser.add_argument("--frames", type=int, default=4, help="Number of frames (default 4)")
    parser.add_argument("--fps", type=int, default=5, help="Animation FPS (default 5)")
    parser.add_argument(
        "--inhale-scale-y",
        type=float,
        default=1.006,
        help="Y-scale for inhale (default 1.006)",
    )
    parser.add_argument(
        "--exhale-scale-y",
        type=float,
        default=0.997,
        help="Y-scale for exhale (default 0.997)",
    )
    parser.add_argument("--inhale-lift-px", type=int, default=1, help="Pixel lift for inhale (default 1)")
    parser.add_argument("--exhale-lift-px", type=int, default=0, help="Pixel lift for exhale (default 0)")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"error: input file not found: {input_path}", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    base = Image.open(input_path).convert("RGBA")
    frames = generate_idle_frames(
        base,
        body_ratio=args.body_ratio,
        num_frames=args.frames,
        inhale_scale_y=args.inhale_scale_y,
        exhale_scale_y=args.exhale_scale_y,
        inhale_lift_px=args.inhale_lift_px,
        exhale_lift_px=args.exhale_lift_px,
    )

    # Save individual frames
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for i, frame in enumerate(frames):
        frame.save(frames_dir / f"frame-{i:03d}.png")

    # Save strip, GIF, WebP
    write_strip(frames, output_dir / "idle-strip.png")
    write_animation(frames, output_dir / "animation.gif", args.fps)
    write_animation(frames, output_dir / "animation.webp", args.fps)

    # Metadata
    meta = {
        "source": str(input_path),
        "frames": args.frames,
        "fps": args.fps,
        "body_ratio": args.body_ratio,
        "inhale_scale_y": args.inhale_scale_y,
        "exhale_scale_y": args.exhale_scale_y,
        "inhale_lift_px": args.inhale_lift_px,
        "exhale_lift_px": args.exhale_lift_px,
        "pipeline": "deterministic-breathing-idle",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "outputs": {
            "strip": "idle-strip.png",
            "gif": "animation.gif",
            "webp": "animation.webp",
            "frames": [f"frames/frame-{i:03d}.png" for i in range(len(frames))],
        },
    }
    (output_dir / "idle-meta.json").write_text(
        json.dumps(meta, indent=2),
        encoding="utf-8",
    )

    print(json.dumps({"output_dir": str(output_dir), "frames": len(frames), "fps": args.fps}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
