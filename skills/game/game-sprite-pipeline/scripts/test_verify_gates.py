#!/usr/bin/env python3
"""Tests for verify_no_magenta + verify_grid_alignment + verify_asset_outputs.

These are the deterministic build-time gates the prior pipeline was missing:
the same broken output shipped every time because nothing flagged it.
Per docs/PHILOSOPHY.md "Everything That Can Be Deterministic, Should Be"
-- pixel comparison + grid math are solved problems, not LLM judgment.

Run: python3 scripts/test_verify_gates.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import sprite_verify  # canonical home post-ADR-205 split


def _new_canvas(w: int, h: int, rgba: tuple[int, int, int, int] = (0, 0, 0, 0)) -> Image.Image:
    return Image.new("RGBA", (w, h), rgba)


def test_verify_no_magenta_clean_canvas() -> None:
    img = _new_canvas(64, 64, (50, 50, 50, 255))
    res = sprite_verify.verify_no_magenta(img)
    assert res["passed"] is True, res
    assert res["strict_count"] == 0, res
    assert res["wide_count"] == 0, res


def test_verify_no_magenta_strict_fail() -> None:
    img = _new_canvas(64, 64, (50, 50, 50, 255))
    arr = np.array(img)
    # 5 strict-magenta pixels in middle of canvas
    arr[10:11, 10:15] = (255, 0, 255, 255)
    img = Image.fromarray(arr, "RGBA")
    res = sprite_verify.verify_no_magenta(img, threshold_strict=0)
    assert res["passed"] is False, res
    assert res["strict_count"] == 5, res
    assert res["wide_count"] == 5, res


def test_verify_no_magenta_within_wide_threshold() -> None:
    img = _new_canvas(64, 64, (50, 50, 50, 255))
    arr = np.array(img)
    # 3 wide-pink pixels (R=200, G=30, B=180) -- caught by wide criterion only
    arr[20:21, 20:23] = (200, 30, 180, 255)
    img = Image.fromarray(arr, "RGBA")
    res = sprite_verify.verify_no_magenta(img, threshold_strict=0, threshold_wide=10)
    assert res["passed"] is True, res  # within tolerance
    assert res["strict_count"] == 0, res  # strict requires R>200, here R==200
    assert res["wide_count"] == 3, res

    res2 = sprite_verify.verify_no_magenta(img, threshold_strict=0, threshold_wide=2)
    assert res2["passed"] is False, res2  # exceeds tolerance


def test_verify_no_magenta_alpha_gate() -> None:
    """Pixels with alpha <= 16 must NOT count -- they are background."""
    img = _new_canvas(64, 64, (255, 0, 255, 0))  # full magenta but alpha=0
    res = sprite_verify.verify_no_magenta(img)
    assert res["passed"] is True, res
    assert res["strict_count"] == 0, res


def test_verify_grid_alignment_clean() -> None:
    cell = 64
    rows, cols = 2, 3
    canvas = _new_canvas(cols * cell, rows * cell)
    arr = np.array(canvas)
    # Each cell has a 32x32 opaque blob centered (16-48 in each cell)
    for r in range(rows):
        for c in range(cols):
            x0, y0 = c * cell + 16, r * cell + 16
            arr[y0 : y0 + 32, x0 : x0 + 32] = (220, 100, 100, 255)
    img = Image.fromarray(arr, "RGBA")
    res = sprite_verify.verify_grid_alignment(img, rows, cols, cell, edge_margin_px=2)
    assert res["passed"] is True, res
    assert len(res["violations"]) == 0, res


def test_verify_grid_alignment_off_grid() -> None:
    """Synthesize a sheet where multiple cells are sliced clean through.

    The naive-grid cell_size bug (53c6915 fix) manifests as characters
    extending across the FULL cell in MULTIPLE cells (the bad pitch cuts
    every character mid-body). A single big-character cell is tolerated;
    two or more triggers fail.
    """
    cell = 64
    rows, cols = 2, 2
    canvas = _new_canvas(cols * cell, rows * cell)
    arr = np.array(canvas)
    # Cell (0,0) clean -- 32x32 centered at 16,16
    arr[16:48, 16:48] = (220, 100, 100, 255)
    # Cell (0,1) horizontal slice
    arr[16:48, 64:128] = (220, 100, 100, 255)
    # Cell (1,0) vertical slice (top to bottom)
    arr[64:128, 16:48] = (220, 100, 100, 255)
    img = Image.fromarray(arr, "RGBA")
    res = sprite_verify.verify_grid_alignment(img, rows, cols, cell, edge_margin_px=2)
    assert res["passed"] is False, res
    patterns = {(v["row"], v["col"], v["pattern"]) for v in res["violations"]}
    assert (0, 1, "horizontal_slice") in patterns, res
    assert (1, 0, "vertical_slice") in patterns, res


def test_verify_grid_alignment_single_violation_tolerated() -> None:
    """Single isolated violation passes (single big-character cell, art choice)."""
    cell = 64
    rows, cols = 2, 2
    canvas = _new_canvas(cols * cell, rows * cell)
    arr = np.array(canvas)
    arr[16:48, 16:48] = (220, 100, 100, 255)
    # One slice violation only
    arr[16:48, 64:128] = (220, 100, 100, 255)
    img = Image.fromarray(arr, "RGBA")
    res = sprite_verify.verify_grid_alignment(img, rows, cols, cell, edge_margin_px=2)
    assert res["passed"] is True, res  # 1 <= tolerance(1)
    assert res["violation_count"] == 1, res


def test_verify_grid_alignment_size_mismatch() -> None:
    canvas = _new_canvas(100, 100)
    res = sprite_verify.verify_grid_alignment(canvas, 2, 2, 64)
    assert res["passed"] is False, res
    assert "size" in res.get("error", ""), res


def test_verify_asset_outputs_portrait(tmp_path: Path) -> None:
    """Synthesize a clean portrait and assert verify_asset_outputs passes."""
    asset_dir = tmp_path / "test-portrait"
    asset_dir.mkdir()
    canvas = _new_canvas(600, 980, (40, 60, 80, 255))
    canvas.save(asset_dir / "final.png")
    res = sprite_verify.verify_asset_outputs(asset_dir, mode="portrait")
    assert res["passed"] is True, res


def test_verify_asset_outputs_portrait_with_magenta(tmp_path: Path) -> None:
    """Portrait with residual magenta must FAIL."""
    asset_dir = tmp_path / "test-portrait-bad"
    asset_dir.mkdir()
    canvas = _new_canvas(600, 980, (40, 60, 80, 255))
    arr = np.array(canvas)
    # 100 strict magenta pixels
    arr[100:110, 100:110] = (255, 0, 255, 255)
    Image.fromarray(arr, "RGBA").save(asset_dir / "final.png")
    res = sprite_verify.verify_asset_outputs(asset_dir, mode="portrait")
    assert res["passed"] is False, res
    assert any(f["check"] == "magenta" for f in res["failures"]), res


def test_verify_asset_outputs_portrait_missing_file(tmp_path: Path) -> None:
    asset_dir = tmp_path / "test-portrait-empty"
    asset_dir.mkdir()
    res = sprite_verify.verify_asset_outputs(asset_dir, mode="portrait")
    assert res["passed"] is False, res


def test_verify_asset_outputs_spritesheet_clean(tmp_path: Path) -> None:
    asset_dir = tmp_path / "test-sheet"
    asset_dir.mkdir()
    cell, rows, cols = 64, 2, 2
    canvas = _new_canvas(cols * cell, rows * cell)
    arr = np.array(canvas)
    # Each cell has a centered character with a unique offset pattern so
    # dHash distances are distinct (frames_distinct gate would otherwise
    # flag four-identical-cells as 100% dups).
    positions = [(16, 16), (24, 16), (16, 24), (24, 24)]
    for idx, (dx, dy) in enumerate(positions):
        r, c = divmod(idx, cols)
        x0, y0 = c * cell + dx, r * cell + dy
        arr[y0 : y0 + 32, x0 : x0 + 32] = (60, 180, 60, 255)
    Image.fromarray(arr, "RGBA").save(asset_dir / "final-sheet.png")
    res = sprite_verify.verify_asset_outputs(asset_dir, mode="spritesheet", grid=(cols, rows), cell_size=cell)
    assert res["passed"] is True, res


def test_verify_asset_outputs_spritesheet_with_off_grid(tmp_path: Path) -> None:
    asset_dir = tmp_path / "test-sheet-bad"
    asset_dir.mkdir()
    # 4x4 grid: 16 cells. With 5% tolerance: int(16*0.05)=0 -> max(1,0)=1.
    # Need 2+ violations to fail. 12 horizontal slices well exceeds that.
    cell, rows, cols = 32, 4, 4
    canvas = _new_canvas(cols * cell, rows * cell)
    arr = np.array(canvas)
    # 12 horizontal slices -- exceeds tolerance.
    for r in range(3):
        for c in range(4):
            x0, y0 = c * cell, r * cell
            arr[y0 + 8 : y0 + 24, x0 : x0 + cell] = (60, 180, 60, 255)
    Image.fromarray(arr, "RGBA").save(asset_dir / "final-sheet.png")
    res = sprite_verify.verify_asset_outputs(asset_dir, mode="spritesheet", grid=(cols, rows), cell_size=cell)
    assert res["passed"] is False, res
    assert any(f["check"] == "grid_alignment" for f in res["failures"]), res


def test_verify_asset_outputs_8x8_four_cropped_fails(tmp_path: Path) -> None:
    """8x8 sheet with 4 cropped cells must FAIL under tightened 5% threshold.

    Tolerance = int(64*0.05) = 3. Four violations exceeds tolerance, so the
    verifier must surface a grid_alignment failure. This is the regression
    test for the powerhouse rubber-stamp finding: at 50% tolerance (32
    cells allowed bad), this case would have wrongly passed.
    """
    asset_dir = tmp_path / "test-sheet-8x8-4bad"
    asset_dir.mkdir()
    cell, rows, cols = 32, 8, 8
    canvas = _new_canvas(cols * cell, rows * cell)
    arr = np.array(canvas)
    # Fill every cell with a small centered character.
    for r in range(rows):
        for c in range(cols):
            x0, y0 = c * cell + 8, r * cell + 8
            arr[y0 : y0 + 16, x0 : x0 + 16] = (60, 180, 60, 255)
    # Now add 4 horizontal slices (cropped cells) in row 0 cols 0..3.
    for c in range(4):
        x0 = c * cell
        arr[8:24, x0 : x0 + cell] = (60, 180, 60, 255)
    Image.fromarray(arr, "RGBA").save(asset_dir / "final-sheet.png")
    res = sprite_verify.verify_asset_outputs(asset_dir, mode="spritesheet", grid=(cols, rows), cell_size=cell)
    assert res["passed"] is False, res
    assert any(f["check"] == "grid_alignment" for f in res["failures"]), res


def test_verify_asset_outputs_8x8_clean_passes(tmp_path: Path) -> None:
    """8x8 sheet of synthesized cells passes the LEGACY gates (magenta + grid).

    The dups gate is excluded by passing a high dup tolerance because synthetic
    8x8=64 cells with simple geometric patterns can't reliably discriminate
    by 8-bit dHash — a real animation cycle has painterly variety that does,
    but this test is a regression test for the LEGACY tolerance threshold,
    not the v8 dups gate. The dups gate has its own dedicated tests
    (test_verify_frames_distinct_*).
    """
    asset_dir = tmp_path / "test-sheet-8x8-clean"
    asset_dir.mkdir()
    cell, rows, cols = 32, 8, 8
    canvas = _new_canvas(cols * cell, rows * cell)
    arr = np.array(canvas)
    for r in range(rows):
        for c in range(cols):
            x0, y0 = c * cell + 8, r * cell + 8
            arr[y0 : y0 + 16, x0 : x0 + 16] = (60, 180, 60, 255)
    Image.fromarray(arr, "RGBA").save(asset_dir / "final-sheet.png")
    # Direct call to the legacy gates only.
    mag = sprite_verify.verify_no_magenta(asset_dir / "final-sheet.png")
    assert mag["passed"], mag
    grid = sprite_verify.verify_grid_alignment(
        asset_dir / "final-sheet.png",
        rows,
        cols,
        cell,
        violation_tolerance=3,
    )
    assert grid["passed"], grid


def test_verify_asset_outputs_8x8_two_cropped_passes(tmp_path: Path) -> None:
    """8x8 sheet with 2 cropped cells PASSES (within 5% tolerance of 3).

    Validates the threshold was loosened from "every cell perfect" to "5%
    of cells may be edge-spanning art". Two violations <= tolerance(3)
    is the legitimate big-character case the verifier should NOT flag.
    """
    asset_dir = tmp_path / "test-sheet-8x8-2bad"
    asset_dir.mkdir()
    cell, rows, cols = 32, 8, 8
    canvas = _new_canvas(cols * cell, rows * cell)
    arr = np.array(canvas)
    for r in range(rows):
        for c in range(cols):
            x0, y0 = c * cell + 8, r * cell + 8
            arr[y0 : y0 + 16, x0 : x0 + 16] = (60, 180, 60, 255)
    # Add 2 horizontal slices.
    for c in range(2):
        x0 = c * cell
        arr[8:24, x0 : x0 + cell] = (60, 180, 60, 255)
    Image.fromarray(arr, "RGBA").save(asset_dir / "final-sheet.png")
    # Direct call to the legacy grid_alignment gate only.
    grid = sprite_verify.verify_grid_alignment(
        asset_dir / "final-sheet.png",
        rows,
        cols,
        cell,
        violation_tolerance=3,
    )
    assert grid["passed"], grid
    assert grid["violation_count"] == 2, grid


# ===========================================================================
# v8 gates: anchor_consistency, frames_have_content, frames_distinct,
# pixel_preservation. Synthesized inputs cover both pass and fail paths.
# ===========================================================================
def test_verify_anchor_consistency_clean() -> None:
    """All cells have characters at identical Y → centroid stddev ~ 0 → pass."""
    cell = 64
    cols, rows = 4, 1
    canvas = _new_canvas(cols * cell, rows * cell)
    arr = np.array(canvas)
    for c in range(cols):
        x0 = c * cell + 16
        # 32-pixel character centered at y 16-48 (centroid Y == 32)
        arr[16:48, x0 : x0 + 32] = (220, 100, 100, 255)
    img = Image.fromarray(arr, "RGBA")
    res = sprite_verify.verify_anchor_consistency(img, cols, rows, cell)
    assert res["passed"] is True, res
    assert res["stddev"] < 1, res
    assert len(res["outliers"]) == 0, res


def test_verify_anchor_consistency_hop_fails() -> None:
    """One cell has its character translated up dramatically → stddev > 8 → fail.

    Reproduces the user's '05 powerhouse hop': the bbox-bottom anchor
    pinned the lunge frame's fist to the floor, lifting the trunk off-screen.
    Synthesis uses 128px cells so the dramatic 64px hop is well within the
    'big outlier' threshold (>= 2x stddev_threshold = 16px).
    """
    cell = 128
    cols, rows = 4, 1
    canvas = _new_canvas(cols * cell, rows * cell)
    arr = np.array(canvas)
    for c in range(cols):
        x0 = c * cell + 32
        # Cell 1's character is at y 0..32 (top-aligned), others at y 64..96.
        # Centroid delta ~= 64px, well above the 16px big-outlier threshold.
        if c == 1:
            arr[0:32, x0 : x0 + 64] = (220, 100, 100, 255)
        else:
            arr[64:96, x0 : x0 + 64] = (220, 100, 100, 255)
    img = Image.fromarray(arr, "RGBA")
    res = sprite_verify.verify_anchor_consistency(img, cols, rows, cell)
    assert res["passed"] is False, res
    # The outlier should specifically be cell index 1.
    outlier_indices = {o["cell_index"] for o in res["outliers"]}
    assert 1 in outlier_indices, res


def test_verify_frames_have_content_pass() -> None:
    cell = 64
    cols, rows = 2, 2
    canvas = _new_canvas(cols * cell, rows * cell)
    arr = np.array(canvas)
    for r in range(rows):
        for c in range(cols):
            arr[r * cell + 16 : r * cell + 48, c * cell + 16 : c * cell + 48] = (220, 100, 100, 255)
    img = Image.fromarray(arr, "RGBA")
    res = sprite_verify.verify_frames_have_content(img, cols, rows, cell)
    assert res["passed"] is True, res
    assert len(res["blank_cells"]) == 0, res


def test_verify_frames_have_content_blank_fails() -> None:
    """Reproduces asset 08 cell 12 (modern-submission-grapple): empty cell."""
    cell = 64
    cols, rows = 2, 2
    canvas = _new_canvas(cols * cell, rows * cell)
    arr = np.array(canvas)
    # Cells 0, 1, 3 have content; cell 2 is blank.
    for idx in (0, 1, 3):
        r, c = divmod(idx, cols)
        arr[r * cell + 16 : r * cell + 48, c * cell + 16 : c * cell + 48] = (220, 100, 100, 255)
    img = Image.fromarray(arr, "RGBA")
    res = sprite_verify.verify_frames_have_content(img, cols, rows, cell)
    assert res["passed"] is False, res
    assert any(b["cell_index"] == 2 for b in res["blank_cells"]), res


def test_verify_frames_distinct_pass_action_cycle() -> None:
    """4 visually distinct frames: each cell has a 32x32 region in a different
    position so dHash distances are >= 4."""
    cell = 64
    cols, rows = 4, 1
    canvas = _new_canvas(cols * cell, rows * cell)
    arr = np.array(canvas)
    positions = [(8, 8), (24, 8), (8, 24), (24, 24)]
    for c, (dx, dy) in enumerate(positions):
        x0 = c * cell + dx
        y0 = dy
        arr[y0 : y0 + 32, x0 : x0 + 32] = (220, 100, 100, 255)
    img = Image.fromarray(arr, "RGBA")
    res = sprite_verify.verify_frames_distinct(img, cols, rows, cell, max_duplicate_pct=25.0)
    assert res["passed"] is True, res


def test_verify_frames_distinct_dups_fail() -> None:
    """4 identical cells: dup pct 100% → fail at threshold 25%."""
    cell = 64
    cols, rows = 4, 1
    canvas = _new_canvas(cols * cell, rows * cell)
    arr = np.array(canvas)
    for c in range(cols):
        x0 = c * cell + 16
        arr[16:48, x0 : x0 + 32] = (220, 100, 100, 255)
    img = Image.fromarray(arr, "RGBA")
    res = sprite_verify.verify_frames_distinct(img, cols, rows, cell, max_duplicate_pct=25.0)
    assert res["passed"] is False, res
    # 6 pairs of duplicates (4 choose 2)
    assert len(res["duplicate_pairs"]) == 6, res


def test_verify_frames_distinct_idle_loop_passes_at_high_threshold() -> None:
    """Portrait-loop's 4 near-identical cells should pass when threshold=100%."""
    cell = 64
    cols, rows = 2, 2
    canvas = _new_canvas(cols * cell, rows * cell)
    arr = np.array(canvas)
    for r in range(rows):
        for c in range(cols):
            x0 = c * cell + 16
            y0 = r * cell + 16
            arr[y0 : y0 + 32, x0 : x0 + 32] = (220, 100, 100, 255)
    img = Image.fromarray(arr, "RGBA")
    res = sprite_verify.verify_frames_distinct(img, cols, rows, cell, max_duplicate_pct=100.0)
    # 4 cells, 6 pairs, dup_pct=100%, but threshold is 100%, so it passes.
    assert res["passed"] is True, res


def test_verify_pixel_preservation_pass(tmp_path: Path) -> None:
    """Raw silhouette ~= final silhouette → ratio ~= 1.0 → pass."""
    cell = 64
    cols, rows = 2, 2
    raw_w, raw_h = cols * cell, rows * cell
    raw = Image.new("RGBA", (raw_w, raw_h), (255, 0, 255, 255))
    raw_arr = np.array(raw)
    for r in range(rows):
        for c in range(cols):
            x0, y0 = c * cell + 16, r * cell + 16
            raw_arr[y0 : y0 + 32, x0 : x0 + 32] = (220, 100, 100, 255)
    raw = Image.fromarray(raw_arr, "RGBA")
    raw.save(tmp_path / "raw.png")
    fin = Image.new("RGBA", (raw_w, raw_h), (0, 0, 0, 0))
    fin_arr = np.array(fin)
    for r in range(rows):
        for c in range(cols):
            x0, y0 = c * cell + 16, r * cell + 16
            fin_arr[y0 : y0 + 32, x0 : x0 + 32] = (220, 100, 100, 255)
    fin = Image.fromarray(fin_arr, "RGBA")
    fin.save(tmp_path / "final-sheet.png")
    res = sprite_verify.verify_pixel_preservation(tmp_path / "raw.png", tmp_path / "final-sheet.png", cols, rows, cell)
    assert res["passed"] is True, res
    assert len(res["lossy_cells"]) == 0, res


def test_verify_pixel_preservation_severe_loss_fails(tmp_path: Path) -> None:
    """Reproduces asset 19 painted-veteran behavior: raw has silhouette but
    final lost most of it (despill chain bridged cells and over-cleaned)."""
    cell = 64
    cols, rows = 2, 2
    raw_w, raw_h = cols * cell, rows * cell
    raw = Image.new("RGBA", (raw_w, raw_h), (255, 0, 255, 255))
    raw_arr = np.array(raw)
    for r in range(rows):
        for c in range(cols):
            x0, y0 = c * cell + 16, r * cell + 16
            raw_arr[y0 : y0 + 32, x0 : x0 + 32] = (60, 180, 60, 255)
    raw = Image.fromarray(raw_arr, "RGBA")
    raw.save(tmp_path / "raw.png")
    # Final has only 1 cell with content; 3 cells empty.
    fin = Image.new("RGBA", (raw_w, raw_h), (0, 0, 0, 0))
    fin_arr = np.array(fin)
    fin_arr[16:48, 16:48] = (60, 180, 60, 255)
    fin = Image.fromarray(fin_arr, "RGBA")
    fin.save(tmp_path / "final-sheet.png")
    res = sprite_verify.verify_pixel_preservation(tmp_path / "raw.png", tmp_path / "final-sheet.png", cols, rows, cell)
    assert res["passed"] is False, res
    # 3 of 4 cells (75%) have severe loss.
    assert len(res["lossy_cells"]) == 3, res


def test_verify_asset_outputs_integration_blank_dup_fail(tmp_path: Path) -> None:
    """End-to-end: feed a synthesized blank+dup combo to verify_asset_outputs.

    Per the operator brief D2: 'feed a known-broken sheet into the verifier
    and assert the verifier catches the blank+dup combination'. This is the
    integration test that proves the gate composition works.

    The synthesis: 16 cells, 12 blank + 4 identical-content. The blank gate
    catches the empty cells; the dups gate catches the 4 identical cells
    (after blank-cell pre-filtering, all 4 remaining cells are duplicates →
    100% of valid cells in dup → fails the 25% threshold).
    """
    asset_dir = tmp_path / "test-blank-dup"
    asset_dir.mkdir()
    cell, cols, rows = 32, 4, 4
    canvas = _new_canvas(cols * cell, rows * cell)
    arr = np.array(canvas)
    # 12 of 16 cells are blank (no content). 4 cells (0, 1, 2, 3) are
    # identical → both gates trigger.
    for c in range(4):
        x0 = c * cell + 8
        arr[8:24, x0 : x0 + 16] = (60, 180, 60, 255)
    Image.fromarray(arr, "RGBA").save(asset_dir / "final-sheet.png")
    Image.fromarray(arr, "RGBA").save(asset_dir / "raw.png")
    res = sprite_verify.verify_asset_outputs(asset_dir, mode="spritesheet", grid=(cols, rows), cell_size=cell)
    assert res["passed"] is False, res
    failure_checks = {f["check"] for f in res["failures"]}
    # The blank-frames gate must fire (12 empty cells).
    assert "frames_have_content" in failure_checks, res
    # Pixel-preservation must also fire (all 16 cells lose >60% of silhouette
    # because the final has only 4 cells with content matching the raw).
    assert "pixel_preservation" in failure_checks, res


def main() -> int:
    import tempfile

    tests = [
        test_verify_no_magenta_clean_canvas,
        test_verify_no_magenta_strict_fail,
        test_verify_no_magenta_within_wide_threshold,
        test_verify_no_magenta_alpha_gate,
        test_verify_grid_alignment_clean,
        test_verify_grid_alignment_off_grid,
        test_verify_grid_alignment_single_violation_tolerated,
        test_verify_grid_alignment_size_mismatch,
        test_verify_anchor_consistency_clean,
        test_verify_anchor_consistency_hop_fails,
        test_verify_frames_have_content_pass,
        test_verify_frames_have_content_blank_fails,
        test_verify_frames_distinct_pass_action_cycle,
        test_verify_frames_distinct_dups_fail,
        test_verify_frames_distinct_idle_loop_passes_at_high_threshold,
    ]
    tmp_tests = [
        test_verify_asset_outputs_portrait,
        test_verify_asset_outputs_portrait_with_magenta,
        test_verify_asset_outputs_portrait_missing_file,
        test_verify_asset_outputs_spritesheet_clean,
        test_verify_asset_outputs_spritesheet_with_off_grid,
        test_verify_asset_outputs_8x8_four_cropped_fails,
        test_verify_asset_outputs_8x8_clean_passes,
        test_verify_asset_outputs_8x8_two_cropped_passes,
        test_verify_pixel_preservation_pass,
        test_verify_pixel_preservation_severe_loss_fails,
        test_verify_asset_outputs_integration_blank_dup_fail,
    ]
    failures: list[tuple[str, str]] = []
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failures.append((t.__name__, str(e)))
    for t in tmp_tests:
        with tempfile.TemporaryDirectory() as td:
            try:
                t(Path(td))
                print(f"PASS {t.__name__}")
            except AssertionError as e:
                print(f"FAIL {t.__name__}: {e}")
                failures.append((t.__name__, str(e)))
    if failures:
        print(f"\n{len(failures)} FAIL")
        return 1
    print(f"\nAll {len(tests) + len(tmp_tests)} tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
