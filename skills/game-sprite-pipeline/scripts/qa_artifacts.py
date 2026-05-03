#!/usr/bin/env python3
"""Visual QA artifact generation for the game-sprite-pipeline (Phase 7).

Produces labeled contact sheets, per-state preview GIFs, and structured
QA reports to accelerate human review of generated spritesheets.

Subcommands:
    make-contact-sheet      Labeled contact sheet from spritesheet
    render-preview-videos   Per-state animated GIFs from spritesheet
    generate-qa-report      JSON QA report with per-row metrics

Usage:
    python3 qa_artifacts.py make-contact-sheet \\
        --input sheet.png --grid 8x9 --cell-size 256 --output qa/contact.png

    python3 qa_artifacts.py render-preview-videos \\
        --input sheet.png --grid 8x9 --cell-size 256 --output-dir qa/previews/ \\
        --preset fighter

    python3 qa_artifacts.py generate-qa-report \\
        --input sheet.png --grid 8x9 --cell-size 256 --output qa/review.json \\
        --preset fighter
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger("sprite-pipeline.qa_artifacts")

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:
    logger.error("Pillow not installed: %s", e)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import sprite_bg
import sprite_prompt


def _load_font(size: int = 14) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a font for text labels, falling back to default."""
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", size)
    except (OSError, IOError):
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf", size)
        except (OSError, IOError):
            return ImageFont.load_default()


def _slice_cells(sheet: Image.Image, cols: int, rows: int, cell_size: int) -> list[list[Image.Image]]:
    """Slice a spritesheet into a 2D grid ``[row][col]`` of cell images."""
    grid: list[list[Image.Image]] = []
    for r in range(rows):
        row: list[Image.Image] = []
        for c in range(cols):
            x = c * cell_size
            y = r * cell_size
            cell = sheet.crop((x, y, x + cell_size, y + cell_size))
            row.append(cell)
        grid.append(row)
    return grid


def _get_state_names(preset_name: str | None, num_rows: int) -> list[str]:
    """Get state names from preset or generate default labels.

    Args:
        preset_name: Optional preset name to look up state names.
        num_rows: Number of rows to generate labels for.

    Returns:
        List of state name strings.
    """
    if preset_name:
        try:
            preset = sprite_prompt.resolve_preset(preset_name)
            return [r["state"] for r in preset["rows"][:num_rows]]
        except ValueError:
            pass
    return [f"row_{i}" for i in range(num_rows)]


def make_contact_sheet(
    input_path: Path,
    output_path: Path,
    cols: int,
    rows: int,
    cell_size: int,
    preset_name: str | None = None,
) -> Path:
    """Produce a labeled contact sheet PNG from a spritesheet.

    Args:
        input_path: Path to the spritesheet PNG.
        output_path: Path for the contact sheet output.
        cols: Number of columns in the spritesheet grid.
        rows: Number of rows in the spritesheet grid.
        cell_size: Cell size in pixels.
        preset_name: Optional preset for state name labels.

    Returns:
        Path to the generated contact sheet.
    """
    sheet = Image.open(input_path).convert("RGBA")
    grid = _slice_cells(sheet, cols, rows, cell_size)
    state_names = _get_state_names(preset_name, rows)

    # Layout: label column + cell thumbnails
    thumb_size = min(cell_size, 128)
    label_width = 140
    padding = 4
    header_height = 24

    out_w = label_width + cols * (thumb_size + padding) + padding
    out_h = header_height + rows * (thumb_size + padding) + padding

    canvas = Image.new("RGBA", (out_w, out_h), (32, 32, 32, 255))
    draw = ImageDraw.Draw(canvas)
    font = _load_font(12)
    header_font = _load_font(11)

    # Column headers
    for c in range(cols):
        x = label_width + c * (thumb_size + padding) + padding
        draw.text((x + 2, 4), f"F{c}", fill=(180, 180, 180, 255), font=header_font)

    # Rows
    for r in range(rows):
        y = header_height + r * (thumb_size + padding) + padding
        # Row label
        label = state_names[r] if r < len(state_names) else f"row_{r}"
        draw.text((4, y + thumb_size // 2 - 6), label, fill=(220, 220, 220, 255), font=font)

        for c in range(cols):
            x = label_width + c * (thumb_size + padding) + padding
            cell = grid[r][c].copy()
            cell.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)

            # Composite cell over dark background for visibility
            bg = Image.new("RGBA", (thumb_size, thumb_size), (48, 48, 48, 255))
            bg.paste(cell, ((thumb_size - cell.width) // 2, (thumb_size - cell.height) // 2), cell)
            canvas.paste(bg, (x, y))

            # Frame number overlay
            draw.text((x + 2, y + 2), str(c), fill=(255, 255, 100, 200), font=header_font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG")
    logger.info("[qa] Contact sheet: %dx%d -> %s", cols, rows, output_path)
    return output_path


def render_preview_videos(
    input_path: Path,
    output_dir: Path,
    cols: int,
    rows: int,
    cell_size: int,
    preset_name: str | None = None,
    fps: int = 10,
) -> list[Path]:
    """Produce one animated GIF per animation state row.

    Args:
        input_path: Path to the spritesheet PNG.
        output_dir: Directory for preview GIF outputs.
        cols: Number of columns in the spritesheet grid.
        rows: Number of rows in the spritesheet grid.
        cell_size: Cell size in pixels.
        preset_name: Optional preset for state names and timing.
        fps: Default FPS when preset timing is unavailable.

    Returns:
        List of paths to generated GIFs.
    """
    sheet = Image.open(input_path).convert("RGBA")
    grid = _slice_cells(sheet, cols, rows, cell_size)
    state_names = _get_state_names(preset_name, rows)

    # Load timing from preset if available
    timing: dict[str, list[int]] = {}
    if preset_name:
        try:
            preset = sprite_prompt.resolve_preset(preset_name)
            for row_def in preset["rows"]:
                if "timing" in row_def:
                    timing[row_def["state"]] = row_def["timing"]
        except ValueError:
            pass

    output_dir.mkdir(parents=True, exist_ok=True)
    default_duration = int(1000 / max(fps, 1))
    gif_paths: list[Path] = []

    for r in range(rows):
        state = state_names[r] if r < len(state_names) else f"row_{r}"
        row_frames = grid[r]

        # Filter out empty cells (all transparent)
        valid_frames: list[Image.Image] = []
        for cell in row_frames:
            bbox = cell.getbbox()
            if bbox is not None:
                valid_frames.append(cell)

        if not valid_frames:
            continue

        # Per-frame durations from preset timing
        state_timing = timing.get(state)
        if state_timing and len(state_timing) >= len(valid_frames):
            durations = state_timing[: len(valid_frames)]
        else:
            durations = [default_duration] * len(valid_frames)

        # Matte composite for GIF
        gif_frames = [
            sprite_bg.matte_composite(f, matte=(40, 40, 40)).convert("P", palette=Image.Palette.ADAPTIVE)
            for f in valid_frames
        ]

        gif_path = output_dir / f"{state}.gif"
        gif_frames[0].save(
            gif_path,
            save_all=True,
            append_images=gif_frames[1:],
            duration=durations,
            loop=0,
            disposal=2,
        )
        gif_paths.append(gif_path)
        logger.info("[qa] Preview GIF: %s (%d frames) -> %s", state, len(valid_frames), gif_path)

    return gif_paths


def generate_qa_report(
    input_path: Path,
    output_path: Path,
    cols: int,
    rows: int,
    cell_size: int,
    preset_name: str | None = None,
) -> dict:
    """Produce a QA report JSON with per-row metrics.

    Args:
        input_path: Path to the spritesheet PNG.
        output_path: Path for the QA report JSON.
        cols: Number of columns in the spritesheet grid.
        rows: Number of rows in the spritesheet grid.
        cell_size: Cell size in pixels.
        preset_name: Optional preset for expected frame counts.

    Returns:
        QA report dict.
    """
    sheet = Image.open(input_path).convert("RGBA")
    grid = _slice_cells(sheet, cols, rows, cell_size)
    state_names = _get_state_names(preset_name, rows)

    # Get expected frame counts from preset
    expected_frames: dict[str, int] = {}
    if preset_name:
        try:
            preset = sprite_prompt.resolve_preset(preset_name)
            for row_def in preset["rows"]:
                expected_frames[row_def["state"]] = row_def["frames"]
        except ValueError:
            pass

    row_reports = []
    for r in range(rows):
        state = state_names[r] if r < len(state_names) else f"row_{r}"
        row_frames = grid[r]

        # Count non-empty frames
        actual_count = 0
        for cell in row_frames:
            if cell.getbbox() is not None:
                actual_count += 1

        expected = expected_frames.get(state, cols)
        frame_match = actual_count == expected

        row_reports.append(
            {
                "row_index": r,
                "state": state,
                "frame_count": {
                    "actual": actual_count,
                    "expected": expected,
                    "match": frame_match,
                },
                "identity_consistency": "visual inspection required",
                "effects_compliance": "visual inspection required",
                "overall_status": "pass" if frame_match else "review",
            }
        )

    overall_pass = all(rr["overall_status"] == "pass" for rr in row_reports)
    report = {
        "spritesheet": str(input_path),
        "grid": f"{cols}x{rows}",
        "cell_size": cell_size,
        "preset": preset_name,
        "overall_status": "pass" if overall_pass else "review",
        "rows": row_reports,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("[qa] Report: %s -> %s", "PASS" if overall_pass else "REVIEW", output_path)
    return report


# ---------------------------------------------------------------------------
# CLI subcommands
# ---------------------------------------------------------------------------
def _parse_grid(grid: str) -> tuple[int, int]:
    """Parse grid spec 'CxR' into (cols, rows)."""
    parts = grid.split("x")
    if len(parts) != 2:
        raise ValueError(f"Invalid grid format {grid!r}. Use CxR like '8x9'.")
    return int(parts[0]), int(parts[1])


def cmd_make_contact_sheet(args: argparse.Namespace) -> int:
    """make-contact-sheet subcommand."""
    cols, rows = _parse_grid(args.grid)
    result = make_contact_sheet(
        input_path=Path(args.input),
        output_path=Path(args.output),
        cols=cols,
        rows=rows,
        cell_size=args.cell_size,
        preset_name=args.preset,
    )
    print(f"Contact sheet -> {result}")
    return 0


def cmd_render_preview_videos(args: argparse.Namespace) -> int:
    """render-preview-videos subcommand."""
    cols, rows = _parse_grid(args.grid)
    paths = render_preview_videos(
        input_path=Path(args.input),
        output_dir=Path(args.output_dir),
        cols=cols,
        rows=rows,
        cell_size=args.cell_size,
        preset_name=args.preset,
        fps=args.fps,
    )
    print(f"Generated {len(paths)} preview GIFs")
    return 0


def cmd_generate_qa_report(args: argparse.Namespace) -> int:
    """generate-qa-report subcommand."""
    cols, rows = _parse_grid(args.grid)
    report = generate_qa_report(
        input_path=Path(args.input),
        output_path=Path(args.output),
        cols=cols,
        rows=rows,
        cell_size=args.cell_size,
        preset_name=args.preset,
    )
    print(json.dumps(report, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    cs = sub.add_parser("make-contact-sheet", help="Labeled contact sheet from spritesheet")
    cs.add_argument("--input", required=True, help="Spritesheet PNG path")
    cs.add_argument("--grid", required=True, help="Grid CxR (e.g., 8x9)")
    cs.add_argument("--cell-size", type=int, default=256)
    cs.add_argument("--output", required=True, help="Output contact sheet PNG path")
    cs.add_argument("--preset", help="Preset name for state labels")
    cs.set_defaults(func=cmd_make_contact_sheet)

    pv = sub.add_parser("render-preview-videos", help="Per-state animated GIFs")
    pv.add_argument("--input", required=True, help="Spritesheet PNG path")
    pv.add_argument("--grid", required=True, help="Grid CxR (e.g., 8x9)")
    pv.add_argument("--cell-size", type=int, default=256)
    pv.add_argument("--output-dir", required=True, help="Output directory for GIFs")
    pv.add_argument("--preset", help="Preset name for state names and timing")
    pv.add_argument("--fps", type=int, default=10, help="Default FPS (overridden by preset timing)")
    pv.set_defaults(func=cmd_render_preview_videos)

    qr = sub.add_parser("generate-qa-report", help="JSON QA report")
    qr.add_argument("--input", required=True, help="Spritesheet PNG path")
    qr.add_argument("--grid", required=True, help="Grid CxR (e.g., 8x9)")
    qr.add_argument("--cell-size", type=int, default=256)
    qr.add_argument("--output", required=True, help="Output review.json path")
    qr.add_argument("--preset", help="Preset name for expected frame counts")
    qr.set_defaults(func=cmd_generate_qa_report)

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
