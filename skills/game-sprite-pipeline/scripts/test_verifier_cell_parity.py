#!/usr/bin/env python3
"""Regression tests for ADR-207 Rule 3 (verify_raw_vs_final_cell_parity).

The new cell-parity gate fires when a raw cell has > 200 non-magenta pixels
but the corresponding final cell has <= 200 visible alpha pixels. This is
the conservative blank-cell check that catches ADR-207 RC-1 directly: raw
has content, final lost it.

These tests exercise:

  1. Negative case: raw + final both have content; gate passes.
  2. Positive case: raw has content in cells, final has them all blank;
     gate fires with detailed per-cell diagnostic.
  3. Mixed case: raw cell IS empty; final cell IS empty; gate's
     precondition not met for that cell (no false positive on legitimately
     empty cells).
  4. Actionable message references ADR-207 RC-1.

Run with pytest:

    pytest skills/game-sprite-pipeline/scripts/test_verifier_cell_parity.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import sprite_verify

MAGENTA = (255, 0, 255, 255)
CHAR_RGB = (32, 224, 64)


def _make_raw_with_content_per_cell(cols: int, rows: int, cell_size: int, populated_cells: set[int]) -> Image.Image:
    """Build a raw sheet at exact pitch with a solid disk in each populated cell."""
    w = cols * cell_size
    h = rows * cell_size
    img = Image.new("RGBA", (w, h), MAGENTA)
    arr = np.array(img)
    radius = cell_size // 5
    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            if idx not in populated_cells:
                continue
            cx = c * cell_size + cell_size // 2
            cy = r * cell_size + cell_size // 2
            yy, xx = np.ogrid[:h, :w]
            disk = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius**2
            arr[disk, 0] = CHAR_RGB[0]
            arr[disk, 1] = CHAR_RGB[1]
            arr[disk, 2] = CHAR_RGB[2]
            arr[disk, 3] = 255
    return Image.fromarray(arr, "RGBA")


def _make_final_with_alpha_per_cell(cols: int, rows: int, cell_size: int, populated_cells: set[int]) -> Image.Image:
    """Build a final sheet with visible alpha-content in each populated cell."""
    w = cols * cell_size
    h = rows * cell_size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))  # fully transparent
    arr = np.array(img)
    radius = cell_size // 5
    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            if idx not in populated_cells:
                continue
            cx = c * cell_size + cell_size // 2
            cy = r * cell_size + cell_size // 2
            yy, xx = np.ogrid[:h, :w]
            disk = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius**2
            arr[disk, 0] = CHAR_RGB[0]
            arr[disk, 1] = CHAR_RGB[1]
            arr[disk, 2] = CHAR_RGB[2]
            arr[disk, 3] = 255
    return Image.fromarray(arr, "RGBA")


# ---------------------------------------------------------------------------
# Test 1: negative case (full preservation)
# ---------------------------------------------------------------------------
def test_cell_parity_passes_when_all_raw_content_preserved(tmp_path: Path) -> None:
    """All 16 raw cells have content; all 16 final cells preserve it."""
    cells = set(range(16))
    raw = _make_raw_with_content_per_cell(4, 4, 256, cells)
    final = _make_final_with_alpha_per_cell(4, 4, 256, cells)
    raw_path = tmp_path / "raw_full.png"
    final_path = tmp_path / "final_full.png"
    raw.save(raw_path)
    final.save(final_path)

    result = sprite_verify.verify_raw_vs_final_cell_parity(raw_path, final_path, 4, 4, 256)
    assert result["passed"] is True, f"expected pass; got {result}"
    assert result["blank_cells"] == [], result
    assert result["total_cells_with_raw_content"] == 16, result
    assert result["cells_preserved"] == 16, result


# ---------------------------------------------------------------------------
# Test 2: positive case (raw has content, final blank — RC-1 signature)
# ---------------------------------------------------------------------------
def test_cell_parity_fires_when_raw_has_content_but_final_blank(tmp_path: Path) -> None:
    """All 16 raw cells have content; final has them ALL blank. Gate must fire."""
    cells = set(range(16))
    raw = _make_raw_with_content_per_cell(4, 4, 256, cells)
    # Final has zero populated cells -> entirely transparent
    final = _make_final_with_alpha_per_cell(4, 4, 256, set())
    raw_path = tmp_path / "raw_full2.png"
    final_path = tmp_path / "final_blank.png"
    raw.save(raw_path)
    final.save(final_path)

    result = sprite_verify.verify_raw_vs_final_cell_parity(raw_path, final_path, 4, 4, 256)
    assert result["passed"] is False, f"gate should fire on full-blank final; got {result}"
    assert len(result["blank_cells"]) == 16, f"expected 16 blank cells flagged; got {len(result['blank_cells'])}"
    # Each blank cell entry must include diagnostic detail.
    for blank in result["blank_cells"]:
        assert "cell_index" in blank, blank
        assert "raw_silhouette" in blank, blank
        assert "final_visible" in blank, blank
        assert blank["raw_silhouette"] > 200, blank  # precondition met
        assert blank["final_visible"] <= 200, blank  # final IS blank
    # Actionable message must point at ADR-207 RC-1.
    assert "ADR-207" in result.get("actionable_message", ""), result.get("actionable_message")
    assert "RC-1" in result.get("actionable_message", ""), result.get("actionable_message")


# ---------------------------------------------------------------------------
# Test 3: mixed case (some raw cells legitimately empty)
# ---------------------------------------------------------------------------
def test_cell_parity_skips_legitimately_empty_raw_cells(tmp_path: Path) -> None:
    """If raw cell IS empty, gate's precondition does not apply -> no false positive.

    Build a raw with only cells {0, 5, 10, 15} populated. Final has the
    same 4 cells populated. The other 12 cells: raw is magenta, final is
    transparent. Gate must NOT flag those 12 cells (precondition not met)
    AND must report total_cells_with_raw_content == 4.
    """
    populated = {0, 5, 10, 15}
    raw = _make_raw_with_content_per_cell(4, 4, 256, populated)
    final = _make_final_with_alpha_per_cell(4, 4, 256, populated)
    raw_path = tmp_path / "raw_partial.png"
    final_path = tmp_path / "final_partial.png"
    raw.save(raw_path)
    final.save(final_path)

    result = sprite_verify.verify_raw_vs_final_cell_parity(raw_path, final_path, 4, 4, 256)
    assert result["passed"] is True, f"all populated cells preserved; should pass: {result}"
    assert result["total_cells_with_raw_content"] == 4, (
        f"expected 4 cells with content (precondition met); got {result['total_cells_with_raw_content']}"
    )
    assert result["cells_preserved"] == 4, result
    assert result["blank_cells"] == [], result


# ---------------------------------------------------------------------------
# Test 4: partial loss (raw populated, only some final cells preserved)
# ---------------------------------------------------------------------------
def test_cell_parity_diagnoses_partial_loss(tmp_path: Path) -> None:
    """Raw has 16 cells with content; final preserves 12, drops 4. Gate flags 4."""
    raw = _make_raw_with_content_per_cell(4, 4, 256, set(range(16)))
    final = _make_final_with_alpha_per_cell(4, 4, 256, set(range(12)))  # last 4 dropped
    raw_path = tmp_path / "raw_loss.png"
    final_path = tmp_path / "final_loss.png"
    raw.save(raw_path)
    final.save(final_path)

    result = sprite_verify.verify_raw_vs_final_cell_parity(raw_path, final_path, 4, 4, 256)
    assert result["passed"] is False, result
    assert len(result["blank_cells"]) == 4, f"expected 4 dropped cells; got {len(result['blank_cells'])}"
    flagged_indexes = sorted(b["cell_index"] for b in result["blank_cells"])
    assert flagged_indexes == [12, 13, 14, 15], flagged_indexes
    assert result["total_cells_with_raw_content"] == 16, result
    assert result["cells_preserved"] == 12, result


# ---------------------------------------------------------------------------
# Standalone runner (works without pytest)
# ---------------------------------------------------------------------------
def main() -> int:
    import tempfile

    tests = [
        test_cell_parity_passes_when_all_raw_content_preserved,
        test_cell_parity_fires_when_raw_has_content_but_final_blank,
        test_cell_parity_skips_legitimately_empty_raw_cells,
        test_cell_parity_diagnoses_partial_loss,
    ]
    failures: list[tuple[str, str]] = []
    for t in tests:
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
    print(f"\nAll {len(tests)} tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
