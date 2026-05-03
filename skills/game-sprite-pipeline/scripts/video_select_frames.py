#!/usr/bin/env python3
"""Frame selection from extracted video sequences (Phase 5).

Selects N frames from a directory of extracted video frames using either
uniform spacing or manual index selection. Assigns beat labels to selected
frames for animation timing.

Subcommands:
    select      Select N frames from an extracted sequence

Usage:
    python3 video_select_frames.py select \\
        --input-dir frames/ --count 8 --output-dir selected/ --method uniform

    python3 video_select_frames.py select \\
        --input-dir frames/ --count 4 --output-dir selected/ \\
        --method manual --indices 0,5,12,18
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

logger = logging.getLogger("sprite-pipeline.video_select_frames")

# Beat labels for animation timing. Applied cyclically when frame count
# exceeds label count.
BEAT_LABELS = ["anticipation", "contact", "follow-through", "recovery"]


def select_uniform(frames: list[Path], count: int) -> list[int]:
    """Select evenly spaced frame indices from a sequence."""
    n = len(frames)
    if count >= n:
        return list(range(n))
    if count <= 0:
        return []
    if count == 1:
        return [n // 2]

    # Evenly spaced across the sequence
    step = (n - 1) / (count - 1)
    return [round(i * step) for i in range(count)]


def select_manual(frames: list[Path], indices: list[int]) -> list[int]:
    """Select frames by explicit index list, clamped to valid range."""
    n = len(frames)
    return [max(0, min(i, n - 1)) for i in indices]


def assign_beat_labels(count: int) -> list[str]:
    """Assign beat labels to selected frames, cycling through BEAT_LABELS."""
    return [BEAT_LABELS[i % len(BEAT_LABELS)] for i in range(count)]


def select_frames(
    input_dir: Path,
    output_dir: Path,
    count: int,
    method: str = "uniform",
    indices: list[int] | None = None,
) -> dict:
    """Select N frames from an extracted sequence and write selection manifest.

    Args:
        input_dir: Directory of extracted frame PNGs.
        output_dir: Directory to copy selected frames into.
        count: Number of frames to select.
        method: Selection method ("uniform" or "manual").
        indices: Required when method is "manual".

    Returns:
        Selection manifest dict.

    Raises:
        FileNotFoundError: If input_dir doesn't exist or has no frames.
        ValueError: For invalid method or missing indices.
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    frames = sorted(input_dir.glob("frame_*.png"))
    if not frames:
        # Also try other common patterns
        frames = sorted(input_dir.glob("*.png"))
    if not frames:
        raise FileNotFoundError(f"No PNG frames found in {input_dir}")

    if method == "uniform":
        selected_indices = select_uniform(frames, count)
    elif method == "manual":
        if indices is None:
            raise ValueError("--indices required for manual selection method")
        selected_indices = select_manual(frames, indices)
    else:
        raise ValueError(f"Unknown selection method {method!r}. Choose 'uniform' or 'manual'.")

    output_dir.mkdir(parents=True, exist_ok=True)
    beats = assign_beat_labels(len(selected_indices))

    selected_files = []
    for out_idx, (src_idx, beat) in enumerate(zip(selected_indices, beats)):
        src = frames[src_idx]
        dst = output_dir / f"selected_{out_idx:04d}.png"
        shutil.copy2(src, dst)
        selected_files.append(
            {
                "output_index": out_idx,
                "source_index": src_idx,
                "source_file": src.name,
                "output_file": dst.name,
                "beat": beat,
            }
        )

    manifest = {
        "method": method,
        "total_source_frames": len(frames),
        "selected_count": len(selected_indices),
        "frames": selected_files,
    }

    manifest_path = output_dir / "selection.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info(
        "[video-select] Selected %d/%d frames (%s) -> %s",
        len(selected_indices),
        len(frames),
        method,
        output_dir,
    )
    return manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def cmd_select(args: argparse.Namespace) -> int:
    """select subcommand."""
    indices = None
    if args.indices:
        try:
            indices = [int(x.strip()) for x in args.indices.split(",")]
        except ValueError:
            logger.error("--indices must be comma-separated integers, got %r", args.indices)
            return 1

    try:
        manifest = select_frames(
            input_dir=Path(args.input_dir),
            output_dir=Path(args.output_dir),
            count=args.count,
            method=args.method,
            indices=indices,
        )
    except (FileNotFoundError, ValueError) as e:
        logger.error("%s", e)
        return 1

    print(json.dumps(manifest, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sel = sub.add_parser("select", help="Select N frames from extracted sequence")
    sel.add_argument("--input-dir", required=True, help="Directory of extracted frame PNGs")
    sel.add_argument("--count", type=int, required=True, help="Number of frames to select")
    sel.add_argument("--output-dir", required=True, help="Output directory for selected frames")
    sel.add_argument("--method", choices=["uniform", "manual"], default="uniform", help="Selection method")
    sel.add_argument("--indices", help="Comma-separated frame indices (for manual method)")
    sel.set_defaults(func=cmd_select)

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
