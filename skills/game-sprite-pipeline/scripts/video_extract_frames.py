#!/usr/bin/env python3
"""Video-to-sprite frame extraction via FFmpeg (Phase 5).

Extracts individual PNG frames from a video file at a specified FPS.
Supports clip trimming via --start and --duration.

Subcommands:
    extract     Extract frames from a video file

Usage:
    python3 video_extract_frames.py extract \\
        --input video.mp4 --fps 10 --output-dir frames/

    python3 video_extract_frames.py extract \\
        --input video.mp4 --fps 10 --output-dir frames/ \\
        --start 1.5 --duration 3.0
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("sprite-pipeline.video_extract_frames")


def check_ffmpeg() -> str | None:
    """Return the path to ffmpeg if available, else None."""
    return shutil.which("ffmpeg")


def extract_frames(
    input_path: Path,
    output_dir: Path,
    fps: int = 10,
    start: float | None = None,
    duration: float | None = None,
) -> list[Path]:
    """Extract frames from a video file using FFmpeg.

    Returns sorted list of extracted frame PNG paths.

    Raises:
        FileNotFoundError: If FFmpeg is not available or input doesn't exist.
        subprocess.CalledProcessError: If FFmpeg fails.
    """
    ffmpeg_path = check_ffmpeg()
    if ffmpeg_path is None:
        raise FileNotFoundError("FFmpeg not found on PATH. Install FFmpeg to use video extraction.")

    if not input_path.exists():
        raise FileNotFoundError(f"Input video not found: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = [ffmpeg_path, "-y"]

    if start is not None:
        cmd.extend(["-ss", str(start)])
    if duration is not None:
        cmd.extend(["-t", str(duration)])

    cmd.extend(
        [
            "-i",
            str(input_path),
            "-vf",
            f"fps={fps}",
            "-frame_pts",
            "1",
            str(output_dir / "frame_%04d.png"),
        ]
    )

    logger.info("[video-extract] Running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    frames = sorted(output_dir.glob("frame_*.png"))
    logger.info("[video-extract] Extracted %d frames at %d fps -> %s", len(frames), fps, output_dir)
    return frames


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def cmd_extract(args: argparse.Namespace) -> int:
    """extract subcommand."""
    try:
        frames = extract_frames(
            input_path=Path(args.input),
            output_dir=Path(args.output_dir),
            fps=args.fps,
            start=args.start,
            duration=args.duration,
        )
    except FileNotFoundError as e:
        logger.error("%s", e)
        return 1
    except subprocess.CalledProcessError as e:
        logger.error("FFmpeg failed: %s", e.stderr)
        return 2

    print(f"Extracted {len(frames)} frames to {args.output_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    ext = sub.add_parser("extract", help="Extract frames from a video file")
    ext.add_argument("--input", required=True, help="Input video file path")
    ext.add_argument("--fps", type=int, default=10, help="Frames per second to extract (default 10)")
    ext.add_argument("--output-dir", required=True, help="Output directory for frame PNGs")
    ext.add_argument("--start", type=float, default=None, help="Start time in seconds for clip trimming")
    ext.add_argument("--duration", type=float, default=None, help="Duration in seconds for clip trimming")
    ext.set_defaults(func=cmd_extract)

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
