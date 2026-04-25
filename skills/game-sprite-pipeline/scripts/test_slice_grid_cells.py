"""Pixel-perfect alignment tests for sprite_process.slice_grid_cells.

The naive-grid extraction bug we are testing: when the raw spritesheet's size
is not a clean multiple of (cols * cell_size), the previous consumer code
resized the whole sheet to the canonical canvas BEFORE slicing. That moves
sprites to fractional cell positions and the grid cuts every character
mid-body.

This test synthesizes a magenta canvas of the exact problem dimensions
(1254x1254 with an 8x8 grid) and asserts each extracted cell's character
centroid lands within ``cell_size/8`` of the expected center.

Run as a standalone script (no pytest dependency required):

    python3 skills/game-sprite-pipeline/scripts/test_slice_grid_cells.py

Exits 0 on success, non-zero on failure with a diagnostic message.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sprite_process

MAGENTA = (255, 0, 255, 255)
MARKER_RGB = (32, 224, 64)  # bright green; far from magenta in chroma space


def _build_synthetic_sheet(raw_w: int, raw_h: int, cols: int, rows: int) -> Image.Image:
    """Build a magenta canvas with a unique green disk placed at each cell center.

    The cell pitch is derived from raw size (raw_w / cols, raw_h / rows). The
    disk radius is small relative to the cell pitch so the disk fits cleanly
    in any reasonable extraction.
    """
    canvas = Image.new("RGBA", (raw_w, raw_h), MAGENTA)
    arr = np.array(canvas)
    pitch_x = raw_w / cols
    pitch_y = raw_h / rows
    radius = int(min(pitch_x, pitch_y) // 6)

    for r in range(rows):
        for c in range(cols):
            # Center of cell (r, c) in raw-pixel coordinates.
            cx = (c + 0.5) * pitch_x
            cy = (r + 0.5) * pitch_y
            # Solid disk of MARKER_RGB at the cell center.
            yy, xx = np.ogrid[:raw_h, :raw_w]
            disk = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius**2
            arr[disk, 0] = MARKER_RGB[0]
            arr[disk, 1] = MARKER_RGB[1]
            arr[disk, 2] = MARKER_RGB[2]
            arr[disk, 3] = 255
    return Image.fromarray(arr, "RGBA")


def _disk_centroid(cell_img: Image.Image) -> tuple[float, float] | None:
    """Return (cx, cy) of the green-marker centroid in cell-local coordinates.

    Returns None if no marker pixels are found (cell is empty / cut wrong).
    """
    arr = np.array(cell_img.convert("RGBA"))
    rgb = arr[..., :3].astype(int)
    # Match green marker: G dominant, R+B low.
    mask = (rgb[..., 1] > 150) & (rgb[..., 0] < 100) & (rgb[..., 2] < 100)
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return float(xs.mean()), float(ys.mean())


def run_case(label: str, raw_w: int, raw_h: int, cols: int, rows: int, cell_size: int) -> int:
    sheet = _build_synthetic_sheet(raw_w, raw_h, cols, rows)
    cells = sprite_process.slice_grid_cells(sheet, cols, rows, cell_size)
    expected = cols * rows
    if len(cells) != expected:
        print(f"FAIL {label}: got {len(cells)} cells, expected {expected}", file=sys.stderr)
        return 1

    # Each extracted cell must be (cell_size, cell_size).
    for i, cell in enumerate(cells):
        if cell.size != (cell_size, cell_size):
            print(
                f"FAIL {label}: cell {i} size {cell.size} != ({cell_size}, {cell_size})",
                file=sys.stderr,
            )
            return 2

    # The disk in cell (r, c) was placed at (raw cell-center) of the source.
    # After per-cell crop + resample to cell_size, the disk's centroid in
    # cell-local coordinates must be near (cell_size/2, cell_size/2).
    tolerance = cell_size / 8.0
    expected_cx = expected_cy = cell_size / 2.0
    failures: list[str] = []
    for i, cell in enumerate(cells):
        centroid = _disk_centroid(cell)
        if centroid is None:
            r, c = divmod(i, cols)
            failures.append(f"cell idx={i} (r={r},c={c}): no marker found in cell")
            continue
        cx, cy = centroid
        dx = abs(cx - expected_cx)
        dy = abs(cy - expected_cy)
        if dx > tolerance or dy > tolerance:
            r, c = divmod(i, cols)
            failures.append(
                f"cell idx={i} (r={r},c={c}): centroid=({cx:.1f},{cy:.1f}) "
                f"expected~=({expected_cx:.1f},{expected_cy:.1f}) tol={tolerance:.1f} "
                f"dx={dx:.1f} dy={dy:.1f}"
            )

    if failures:
        print(f"FAIL {label}: {len(failures)} of {expected} cells off-center:", file=sys.stderr)
        for f in failures[:8]:
            print(f"  {f}", file=sys.stderr)
        if len(failures) > 8:
            print(f"  ... ({len(failures) - 8} more)", file=sys.stderr)
        return 3

    print(f"PASS {label}: {expected} cells extracted, all centroids within {tolerance:.1f}px")
    return 0


def main() -> int:
    cases = [
        # The exact bug from asset 05 (Codex 1254x1254 / 8x8, target 128).
        ("1254x1254/8x8/cell=128 (smoking-gun reproduction)", 1254, 1254, 8, 8, 128),
        # Exact-match canvas (the happy path: should not resample).
        ("1024x1024/8x8/cell=128 (exact match)", 1024, 1024, 8, 8, 128),
        # Integer-divisible non-canonical (pitch=160 -> resample to 128).
        ("1280x1280/8x8/cell=128 (integer pitch)", 1280, 1280, 8, 8, 128),
        # Smaller grids commonly used by portrait-loop & action loops.
        ("1024x1024/2x2/cell=512 (portrait-loop happy path)", 1024, 1024, 2, 2, 512),
        ("1100x1100/2x2/cell=512 (portrait-loop fractional)", 1100, 1100, 2, 2, 512),
        ("1024x1024/4x4/cell=256 (action loop)", 1024, 1024, 4, 4, 256),
        # Pathological fractional sizes also seen in the wild.
        ("1535x1535/4x4/cell=256 (fractional)", 1535, 1535, 4, 4, 256),
    ]
    rc = 0
    for case in cases:
        rc |= run_case(*case)
    if rc == 0:
        print("\nAll cases PASS — slice_grid_cells is pixel-perfect across canvases.")
    else:
        print("\nFAIL: at least one case did not meet the centroid invariant.", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
