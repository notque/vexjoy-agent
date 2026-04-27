#!/usr/bin/env python3
"""
Phase B (spritesheet mode): generate a Pillow grid template canvas.

Pure deterministic image processing. No LLM, no backend call. Produces a
magenta-background PNG with C x R cells and thin reference borders. Used as
the structural input for spritesheet-mode generation in Phase C.

Subcommands:
    make-template   Generate the canvas template

Usage:
    python3 sprite_canvas.py make-template --rows 4 --cols 4 --cell-size 256 \
        --pattern alternating --output canvas.png

Allowed cell sizes: 64, 128, 192, 256, 384, 512.
Total canvas (cell-size * cols, cell-size * rows) <= 2048 x 2048.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("sprite-pipeline.sprite_canvas")

try:
    from PIL import Image, ImageDraw
except ImportError as e:
    logger.error("Pillow not installed: %s", e)
    logger.error("Install with: pip install pillow")
    sys.exit(1)


ALLOWED_CELL_SIZES = {64, 128, 192, 256, 384, 512}
MAX_CANVAS_DIM = 2048
DEFAULT_MAX_CANVAS = 1024


def compute_max_grid(cell_size: int, max_canvas: int = DEFAULT_MAX_CANVAS) -> tuple[int, int]:
    """Return ``(rows, cols)`` for the largest square grid that fits.

    One Codex CLI imagegen call produces ONE image, so the pipeline should
    pack as many frames as possible into that one image. This helper picks
    the largest square ``rows x cols`` that fits a ``max_canvas`` square at
    the given ``cell_size``.

    >>> compute_max_grid(256, 1024)
    (4, 4)
    >>> compute_max_grid(128, 1024)
    (8, 8)
    >>> compute_max_grid(64, 1024)
    (16, 16)
    >>> compute_max_grid(192, 1024)
    (5, 5)

    Raises ``ValueError`` when the cell does not fit even once.
    """
    if cell_size <= 0:
        raise ValueError(f"cell_size must be positive, got {cell_size}")
    if max_canvas <= 0:
        raise ValueError(f"max_canvas must be positive, got {max_canvas}")
    side = max_canvas // cell_size
    if side < 1:
        raise ValueError(
            f"cell_size {cell_size} is larger than max_canvas {max_canvas}; "
            "no grid fits. Reduce cell-size or raise --max-canvas."
        )
    return side, side


MAGENTA = (255, 0, 255, 255)
BORDER_COLOR = (32, 32, 32, 255)
BORDER_WIDTH = 2
CHECKERBOARD_TINT = (240, 0, 240, 255)  # within chroma threshold of magenta


@dataclass
class CanvasSpec:
    rows: int
    cols: int
    cell_size: int
    pattern: str  # 'magenta-only' | 'alternating' | 'checkerboard'

    @property
    def width(self) -> int:
        return self.cell_size * self.cols

    @property
    def height(self) -> int:
        return self.cell_size * self.rows


def validate_spec(spec: CanvasSpec) -> None:
    """Reject invalid configurations with clear messages."""
    if spec.cell_size not in ALLOWED_CELL_SIZES:
        raise ValueError(f"cell-size {spec.cell_size} not allowed. Choose from {sorted(ALLOWED_CELL_SIZES)}.")
    if spec.rows < 1 or spec.cols < 1:
        raise ValueError(f"grid {spec.cols}x{spec.rows} must have positive rows and cols.")
    if spec.width > MAX_CANVAS_DIM or spec.height > MAX_CANVAS_DIM:
        raise ValueError(
            f"total canvas {spec.width}x{spec.height} exceeds {MAX_CANVAS_DIM}x{MAX_CANVAS_DIM} limit. "
            f"Reduce cell-size or grid."
        )
    if spec.pattern not in {"magenta-only", "alternating", "checkerboard"}:
        raise ValueError(
            f"pattern {spec.pattern!r} not recognized. Choose from: magenta-only, alternating, checkerboard."
        )


def render_canvas(spec: CanvasSpec) -> Image.Image:
    """Build the canvas PIL image per the spec."""
    img = Image.new("RGBA", (spec.width, spec.height), MAGENTA)
    draw = ImageDraw.Draw(img)

    if spec.pattern == "checkerboard":
        for row in range(spec.rows):
            for col in range(spec.cols):
                if (row + col) % 2 == 1:
                    x0 = col * spec.cell_size
                    y0 = row * spec.cell_size
                    x1 = x0 + spec.cell_size
                    y1 = y0 + spec.cell_size
                    draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=CHECKERBOARD_TINT)

    if spec.pattern in {"alternating", "checkerboard"}:
        # vertical lines
        for col in range(spec.cols + 1):
            x = min(col * spec.cell_size, spec.width - 1)
            draw.line(
                [(x, 0), (x, spec.height - 1)],
                fill=BORDER_COLOR,
                width=BORDER_WIDTH,
            )
        # horizontal lines
        for row in range(spec.rows + 1):
            y = min(row * spec.cell_size, spec.height - 1)
            draw.line(
                [(0, y), (spec.width - 1, y)],
                fill=BORDER_COLOR,
                width=BORDER_WIDTH,
            )

    return img


def cmd_make_template(args: argparse.Namespace) -> int:
    """make-template subcommand entry."""
    rows, cols = args.rows, args.cols
    if args.max_frames:
        try:
            r, c = compute_max_grid(args.cell_size, args.max_canvas)
        except ValueError as e:
            logger.error("%s", e)
            return 2
        rows, cols = r, c
        logger.info(
            "[canvas] auto-grid: %dx%d = %d frames @ %dpx on %dx%d canvas",
            cols,
            rows,
            cols * rows,
            args.cell_size,
            args.max_canvas,
            args.max_canvas,
        )
    if rows is None or cols is None:
        logger.error("--rows and --cols are required unless --max-frames is set.")
        return 2

    spec = CanvasSpec(
        rows=rows,
        cols=cols,
        cell_size=args.cell_size,
        pattern=args.pattern,
    )
    try:
        validate_spec(spec)
    except ValueError as e:
        logger.error("%s", e)
        return 2

    img = render_canvas(spec)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")
    logger.info(
        "[canvas] %s written (%dx%d, %dx%d grid, pattern=%s)",
        output_path,
        spec.width,
        spec.height,
        spec.cols,
        spec.rows,
        spec.pattern,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse CLI."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    mk = sub.add_parser("make-template", help="Generate a grid canvas template")
    mk.add_argument("--rows", type=int, default=None, help="Number of rows in the grid (omit with --max-frames)")
    mk.add_argument("--cols", type=int, default=None, help="Number of columns in the grid (omit with --max-frames)")
    mk.add_argument(
        "--cell-size",
        type=int,
        default=256,
        help="Cell size in px (one of 64,128,192,256,384,512; default 256)",
    )
    mk.add_argument(
        "--max-frames",
        action="store_true",
        help=(
            "Auto-fill the canvas: compute the largest square rows x cols that fits "
            "--max-canvas at the given --cell-size, ignoring --rows/--cols."
        ),
    )
    mk.add_argument(
        "--max-canvas",
        type=int,
        default=DEFAULT_MAX_CANVAS,
        help=f"Max canvas side in px when --max-frames is set (default {DEFAULT_MAX_CANVAS})",
    )
    mk.add_argument(
        "--pattern",
        default="alternating",
        choices=["magenta-only", "alternating", "checkerboard"],
        help="Cell rendering pattern (default: alternating)",
    )
    mk.add_argument("--output", required=True, help="Output PNG path")
    mk.set_defaults(func=cmd_make_template)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
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
