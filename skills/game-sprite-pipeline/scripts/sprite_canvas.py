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
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError as e:
    print(f"ERROR: Pillow not installed: {e}", file=sys.stderr)
    print("Install with: pip install pillow", file=sys.stderr)
    sys.exit(1)


ALLOWED_CELL_SIZES = {64, 128, 192, 256, 384, 512}
MAX_CANVAS_DIM = 2048
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
    spec = CanvasSpec(
        rows=args.rows,
        cols=args.cols,
        cell_size=args.cell_size,
        pattern=args.pattern,
    )
    try:
        validate_spec(spec)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    img = render_canvas(spec)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")
    print(
        f"[canvas] {output_path} written ({spec.width}x{spec.height}, "
        f"{spec.cols}x{spec.rows} grid, pattern={spec.pattern})",
        file=sys.stderr,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse CLI."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    mk = sub.add_parser("make-template", help="Generate a grid canvas template")
    mk.add_argument("--rows", type=int, required=True, help="Number of rows in the grid")
    mk.add_argument("--cols", type=int, required=True, help="Number of columns in the grid")
    mk.add_argument(
        "--cell-size",
        type=int,
        default=256,
        help="Cell size in px (one of 64,128,192,256,384,512; default 256)",
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
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
