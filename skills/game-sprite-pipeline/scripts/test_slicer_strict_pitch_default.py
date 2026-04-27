#!/usr/bin/env python3
"""Regression tests for ADR-207 Rule 1 (RC-1).

The smoking-gun failure: ``slice_with_content_awareness`` on a dense Codex
raw (1254x1254 / 8x8 / cell_size=256) drops cells via centroid drift.
ADR-207 makes the strict-pitch slicer the only allowed dispatch on dense
grids, downgrading content-aware to strict with a warning unless
``--effects-asset`` is also passed.

These tests exercise that contract:

  1. The strict-pitch slicer produces 0 blank cells on the synthetic
     dense-grid sheet.
  2. ``cmd_extract_frames`` with ``--content-aware`` on a dense grid
     downgrades to strict (logs a warning, falls back) and produces the
     same 0-blank result.
  3. ``cmd_extract_frames`` with ``--content-aware --effects-asset`` on a
     dense grid honors the explicit opt-in (no downgrade).
  4. ``is_dense_grid`` predicate matches the calibrated cutpoint.

Run with pytest:

    pytest skills/game-sprite-pipeline/scripts/test_slicer_strict_pitch_default.py -v
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import sprite_slicing

MAGENTA_RGB = (255, 0, 255)
CHAR_RGB = (32, 224, 64)


def _build_dense_synthetic_sheet(raw_w: int, raw_h: int, cols: int, rows: int) -> Image.Image:
    """Build a magenta canvas with one solid disk per cell at the cell center.

    Mirrors the Codex 1254x1254 / 8x8 case where disk centroids land at
    fractional pitch positions. Strict slicing with per-cell crop + resample
    recovers each disk; content-aware centroid routing drifts.
    """
    canvas = Image.new("RGBA", (raw_w, raw_h), MAGENTA_RGB + (255,))
    arr = np.array(canvas)
    pitch_x = raw_w / cols
    pitch_y = raw_h / rows
    radius = int(min(pitch_x, pitch_y) // 5)
    for r in range(rows):
        for c in range(cols):
            cx = (c + 0.5) * pitch_x
            cy = (r + 0.5) * pitch_y
            yy, xx = np.ogrid[:raw_h, :raw_w]
            disk = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius**2
            arr[disk, 0] = CHAR_RGB[0]
            arr[disk, 1] = CHAR_RGB[1]
            arr[disk, 2] = CHAR_RGB[2]
            arr[disk, 3] = 255
    return Image.fromarray(arr, "RGBA")


def _count_blank_cells(cells: list[Image.Image], chroma_threshold: int = 80, min_pixels: int = 200) -> int:
    """Count cells that are essentially pure magenta (no character disk survived)."""
    blank = 0
    for cell in cells:
        arr = np.array(cell.convert("RGB")).astype(int)
        diff = np.abs(arr - np.array(MAGENTA_RGB)).sum(axis=-1)
        if (diff > chroma_threshold).sum() < min_pixels:
            blank += 1
    return blank


# ---------------------------------------------------------------------------
# Test 1: strict slicer baseline on the smoking-gun shape
# ---------------------------------------------------------------------------
def test_strict_pitch_slicer_zero_blanks_on_dense_codex_raw() -> None:
    """slice_grid_cells produces 0 blank cells on 1254x1254/8x8/cell=256."""
    sheet = _build_dense_synthetic_sheet(1254, 1254, 8, 8)
    cells = sprite_slicing.slice_grid_cells(sheet, 8, 8, 256)
    assert len(cells) == 64, f"expected 64 cells, got {len(cells)}"
    blanks = _count_blank_cells(cells)
    assert blanks == 0, (
        f"strict-pitch slicer dropped {blanks}/64 cells on synthetic Codex-shape "
        f"raw. ADR-207 RC-1 reproduction asserts strict yields 0/64 blanks."
    )


# ---------------------------------------------------------------------------
# Test 2: dense-grid dispatch downgrades content-aware -> strict
# ---------------------------------------------------------------------------
def test_content_aware_on_dense_grid_downgrades_to_strict(
    tmp_path: Path,
    caplog: object,
) -> None:
    """cmd_extract_frames with --content-aware on 8x8 dense grid downgrades to strict.

    Asserts (a) the warning is logged with the ADR-207 RC-1 reference,
    (b) the resulting frames are 0-blank (proving strict was used).
    """
    sheet = _build_dense_synthetic_sheet(1254, 1254, 8, 8)
    sheet_path = tmp_path / "raw_dense.png"
    sheet.save(sheet_path)
    out_dir = tmp_path / "frames"

    args = argparse.Namespace(
        input=str(sheet_path),
        output_dir=str(out_dir),
        grid="8x8",
        name="dense",
        chroma_threshold=80,
        min_pixels=200,
        cell_aware=True,
        allow_count_mismatch=False,
        content_aware=True,  # the deprecated path on dense grids
        effects_asset=False,  # NO opt-in
        cell_size=256,
        max_expansion_pct=0.30,
    )

    with caplog.at_level(logging.WARNING, logger="sprite-pipeline.sprite_slicing"):
        rc = sprite_slicing.cmd_extract_frames(args)
    assert rc == 0, f"extract-frames returned rc={rc} on dense downgrade path"

    # The downgrade warning must reference ADR-207 RC-1.
    warning_messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    adr207_warnings = [m for m in warning_messages if "ADR-207" in m]
    assert adr207_warnings, f"expected an ADR-207 RC-1 downgrade warning, got: {warning_messages}"

    # Frames written should be 0-blank because strict-pitch produced them.
    frame_paths = sorted(out_dir.glob("dense_frame_*.png"))
    assert len(frame_paths) == 64, f"expected 64 frame files, got {len(frame_paths)}"
    cells = [Image.open(p) for p in frame_paths]
    blanks = _count_blank_cells(cells)
    assert blanks == 0, (
        f"content-aware on dense grid SHOULD have downgraded to strict (0 blanks); "
        f"got {blanks}/64 blanks instead, suggesting the downgrade did not happen."
    )


# ---------------------------------------------------------------------------
# Test 3: --effects-asset honors content-aware on dense grid
# ---------------------------------------------------------------------------
def test_effects_asset_opt_in_keeps_content_aware_on_dense_grid(
    tmp_path: Path,
    caplog: object,
) -> None:
    """--content-aware --effects-asset on dense grid does NOT downgrade.

    The point of --effects-asset is to opt INTO content-aware on a dense
    grid (legitimate for sparse-but-cross-boundary content like fire breath).
    Asserts the downgrade warning is NOT emitted and the frame_metadata.json
    records extraction='content-aware' with effects_asset=True.
    """
    import json

    sheet = _build_dense_synthetic_sheet(1254, 1254, 8, 8)
    sheet_path = tmp_path / "raw_dense_fx.png"
    sheet.save(sheet_path)
    out_dir = tmp_path / "frames_fx"

    args = argparse.Namespace(
        input=str(sheet_path),
        output_dir=str(out_dir),
        grid="8x8",
        name="dense_fx",
        chroma_threshold=80,
        min_pixels=200,
        cell_aware=True,
        allow_count_mismatch=False,
        content_aware=True,
        effects_asset=True,  # explicit opt-in
        cell_size=256,
        max_expansion_pct=0.30,
    )

    with caplog.at_level(logging.WARNING, logger="sprite-pipeline.sprite_slicing"):
        rc = sprite_slicing.cmd_extract_frames(args)
    assert rc == 0, f"extract-frames returned rc={rc} on effects-asset opt-in"

    # The downgrade warning must NOT fire when --effects-asset is set.
    adr207_warnings = [
        r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING and "ADR-207" in r.getMessage()
    ]
    assert not adr207_warnings, (
        f"--effects-asset should opt INTO content-aware (no downgrade warning); got: {adr207_warnings}"
    )

    # Metadata must record the chosen extraction path.
    meta_path = out_dir / "frame_metadata.json"
    assert meta_path.exists(), "frame_metadata.json missing on content-aware path"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta.get("extraction") == "content-aware", meta
    assert meta.get("effects_asset") is True, meta


# ---------------------------------------------------------------------------
# Test 4: is_dense_grid predicate calibration
# ---------------------------------------------------------------------------
def test_is_dense_grid_predicate_calibration() -> None:
    """ADR-207 calibration: dense = >= 16 cells AND both dims >= 4."""
    # Dense (should fire)
    assert sprite_slicing.is_dense_grid(4, 4) is True  # exactly the cutpoint
    assert sprite_slicing.is_dense_grid(8, 8) is True  # the live failure case
    assert sprite_slicing.is_dense_grid(4, 8) is True  # asymmetric dense
    assert sprite_slicing.is_dense_grid(16, 4) is True  # tall dense

    # Sparse (should NOT fire)
    assert sprite_slicing.is_dense_grid(3, 3) is False  # below cell count
    assert sprite_slicing.is_dense_grid(2, 8) is False  # one dim too narrow
    assert sprite_slicing.is_dense_grid(1, 64) is False  # degenerate
    assert sprite_slicing.is_dense_grid(2, 2) is False  # smallest sparse
    assert sprite_slicing.is_dense_grid(4, 3) is False  # one dim too narrow
    assert sprite_slicing.is_dense_grid(3, 4) is False  # one dim too narrow


# ---------------------------------------------------------------------------
# Standalone runner (works without pytest)
# ---------------------------------------------------------------------------
class _CapLog:
    """Minimal caplog substitute for standalone runs."""

    def __init__(self) -> None:
        self.records: list[logging.LogRecord] = []
        self._handler = logging.Handler()
        self._handler.emit = self.records.append  # type: ignore[method-assign]

    def at_level(self, level: int, logger: str = "") -> "_CapLog":
        log = logging.getLogger(logger)
        log.setLevel(level)
        log.addHandler(self._handler)
        return self

    def __enter__(self) -> "_CapLog":
        return self

    def __exit__(self, *args: object) -> None:
        pass


def main() -> int:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="[%(name)s] %(levelname)s: %(message)s", stream=sys.stderr)
    import tempfile

    failures: list[tuple[str, str]] = []

    try:
        test_strict_pitch_slicer_zero_blanks_on_dense_codex_raw()
        print("PASS test_strict_pitch_slicer_zero_blanks_on_dense_codex_raw")
    except AssertionError as e:
        print(f"FAIL test_strict_pitch_slicer_zero_blanks_on_dense_codex_raw: {e}")
        failures.append(("test_strict_pitch_slicer_zero_blanks_on_dense_codex_raw", str(e)))

    with tempfile.TemporaryDirectory() as td:
        try:
            test_content_aware_on_dense_grid_downgrades_to_strict(Path(td), _CapLog())
            print("PASS test_content_aware_on_dense_grid_downgrades_to_strict")
        except AssertionError as e:
            print(f"FAIL test_content_aware_on_dense_grid_downgrades_to_strict: {e}")
            failures.append(("test_content_aware_on_dense_grid_downgrades_to_strict", str(e)))

    with tempfile.TemporaryDirectory() as td:
        try:
            test_effects_asset_opt_in_keeps_content_aware_on_dense_grid(Path(td), _CapLog())
            print("PASS test_effects_asset_opt_in_keeps_content_aware_on_dense_grid")
        except AssertionError as e:
            print(f"FAIL test_effects_asset_opt_in_keeps_content_aware_on_dense_grid: {e}")
            failures.append(("test_effects_asset_opt_in_keeps_content_aware_on_dense_grid", str(e)))

    try:
        test_is_dense_grid_predicate_calibration()
        print("PASS test_is_dense_grid_predicate_calibration")
    except AssertionError as e:
        print(f"FAIL test_is_dense_grid_predicate_calibration: {e}")
        failures.append(("test_is_dense_grid_predicate_calibration", str(e)))

    if failures:
        print(f"\n{len(failures)} FAIL")
        return 1
    print("\nAll tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
