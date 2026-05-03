#!/usr/bin/env python3
"""
Phase B (spritesheet mode): generate a Pillow grid template canvas.

Pure deterministic image processing. No LLM, no backend call. Produces a
magenta-background PNG with C x R cells and thin reference borders. Used as
the structural input for spritesheet-mode generation in Phase C.

Subcommands:
    make-template       Generate the canvas template
    make-layout-guide   Generate per-row layout reference PNG (Phase 2)

Usage:
    python3 sprite_canvas.py make-template --rows 4 --cols 4 --cell-size 256 \
        --pattern alternating --output canvas.png

    python3 sprite_canvas.py make-layout-guide --state idle --frames 6 \
        --cell-size 256 --output guide.png

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
    from PIL import Image, ImageDraw, ImageFont
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

# Layout guide colors (Phase 2)
GUIDE_BORDER_COLOR = (180, 180, 180, 255)  # light gray
GUIDE_BORDER_WIDTH = 2
GUIDE_TEXT_COLOR = (160, 160, 160, 255)  # lighter gray for cell numbers


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


def render_layout_guide(frames: int, cell_size: int, state: str = "") -> Image.Image:
    """Generate a per-row layout guide PNG (Phase 2).

    Produces a horizontal strip with frame boundaries drawn as light gray
    borders on a transparent background. Each cell has a centered frame
    number. Passed as --reference to the backend to ground frame placement.

    Args:
        frames: Number of frames (cells) in the strip.
        cell_size: Width and height of each cell in pixels.
        state: Optional animation state label drawn at left edge.

    Returns:
        RGBA Image with transparent background and gray cell guides.
    """
    width = frames * cell_size
    height = cell_size
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Try to load a font; fall back to default if unavailable
    font = None
    font_small = None
    try:
        font_size = max(cell_size // 4, 16)
        font_small_size = max(cell_size // 8, 10)
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_small_size)
    except (OSError, IOError):
        font = ImageFont.load_default()
        font_small = font

    for i in range(frames):
        x0 = i * cell_size
        y0 = 0
        x1 = x0 + cell_size - 1
        y1 = cell_size - 1

        # Cell border
        draw.rectangle((x0, y0, x1, y1), outline=GUIDE_BORDER_COLOR, width=GUIDE_BORDER_WIDTH)

        # Frame number centered in cell
        label = str(i)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = x0 + (cell_size - tw) // 2
        ty = y0 + (cell_size - th) // 2
        draw.text((tx, ty), label, fill=GUIDE_TEXT_COLOR, font=font)

    # State label at top-left if provided
    if state and font_small:
        draw.text((4, 4), state, fill=GUIDE_BORDER_COLOR, font=font_small)

    logger.info(
        "[canvas] layout guide: %d frames @ %dpx, state=%s, size=%dx%d",
        frames,
        cell_size,
        state or "(none)",
        width,
        height,
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


def cmd_make_layout_guide(args: argparse.Namespace) -> int:
    """make-layout-guide subcommand entry (Phase 2)."""
    cell_size = args.cell_size
    if cell_size not in ALLOWED_CELL_SIZES:
        logger.error("cell-size %d not allowed. Choose from %s.", cell_size, sorted(ALLOWED_CELL_SIZES))
        return 2
    if args.frames < 1:
        logger.error("--frames must be >= 1, got %d", args.frames)
        return 2

    img = render_layout_guide(
        frames=args.frames,
        cell_size=cell_size,
        state=args.state or "",
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")
    logger.info("[canvas] layout guide written: %s (%dx%d)", output_path, img.width, img.height)
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

    lg = sub.add_parser(
        "make-layout-guide",
        help="Generate per-row layout reference PNG (Phase 2)",
    )
    lg.add_argument("--state", default="", help="Animation state name (e.g., idle, dash-right)")
    lg.add_argument("--frames", type=int, required=True, help="Number of frames in the row")
    lg.add_argument(
        "--cell-size",
        type=int,
        default=256,
        help="Cell size in px (one of 64,128,192,256,384,512; default 256)",
    )
    lg.add_argument("--output", required=True, help="Output PNG path")
    lg.set_defaults(func=cmd_make_layout_guide)

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
