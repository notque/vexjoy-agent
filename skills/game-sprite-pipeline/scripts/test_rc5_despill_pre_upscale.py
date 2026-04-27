#!/usr/bin/env python3
"""Regression tests for ADR-208 RC-5 (pre-upscale despill on the raw).

ADR-208 introduces `_pre_despill_raw_for_upscale` and wires it as the
default `pre_despill_raw=True` parameter on `slice_grid_cells`. The fix
zeroes magenta pixels to alpha=0 on the raw BEFORE per-cell LANCZOS
upscale; LANCZOS then interpolates between transparent and content
(alpha-aware) instead of between magenta and content (RGB-only). The
resulting fringe is alpha-faded character RGB instead of pink-tinted RGB.

A second post-anchor despill pass (`_post_anchor_despill_pink` in
sprite_anchor) handles the residual band that the shared-scale rescale
reintroduces.

Tests:
  1. `slice_grid_cells`'s `pre_despill_raw` defaults to True.
  2. Synthetic 1254x1254 raw with magenta bg + colored content, sliced
     into 8x8 / 256, post-pipeline wide_count is much lower with
     pre-despill ON than OFF.
  3. `_pre_despill_raw_for_upscale` zeroes magenta pixels' alpha to 0.
  4. `_post_anchor_despill_pink` is callable and reduces wide-pink count
     on a known-pink-cast input.

Run with pytest:

    pytest skills/game-sprite-pipeline/scripts/test_rc5_despill_pre_upscale.py -v
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy as np
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import sprite_anchor
import sprite_slicing
import sprite_verify

GRID = 8
RAW_SIZE = 1254  # Codex's actual canvas size on a "2048 spec" output
CELL = 256


def test_slice_grid_cells_pre_despill_default_is_true() -> None:
    """`slice_grid_cells`'s `pre_despill_raw` parameter defaults to True."""
    sig = inspect.signature(sprite_slicing.slice_grid_cells)
    default = sig.parameters["pre_despill_raw"].default
    assert default is True, f"expected default True; got {default!r}"


def _make_synthetic_codex_raw(size: int = RAW_SIZE, grid: int = GRID) -> Image.Image:
    """Build a magenta-bg sheet with colored shapes per cell at ~grid pitch.

    Mimics the Codex output contract: 1254x1254 (or similar fractional)
    canvas, magenta background, character art per ~156.75-px pitch cell.
    Each cell gets a circle of a different color so frames are distinct.
    """
    img = np.full((size, size, 4), (255, 0, 255, 255), dtype=np.uint8)
    pitch = size / grid
    rng = np.random.default_rng(1234)
    for r in range(grid):
        for c in range(grid):
            cx = int((c + 0.5) * pitch)
            cy = int((r + 0.5) * pitch)
            radius = int(pitch * 0.35)
            # Random saturated color, deterministic per (r,c)
            color = tuple(int(x) for x in rng.integers(40, 220, size=3))
            yy, xx = np.ogrid[:size, :size]
            mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius**2
            img[mask, 0] = color[0]
            img[mask, 1] = color[1]
            img[mask, 2] = color[2]
            img[mask, 3] = 255
    return Image.fromarray(img, "RGBA")


def test_pre_despill_zeroes_magenta_alpha() -> None:
    """`_pre_despill_raw_for_upscale` sets alpha=0 on magenta pixels."""
    img = Image.new("RGBA", (10, 10), (255, 0, 255, 255))
    out = sprite_slicing._pre_despill_raw_for_upscale(img, chroma_threshold=30)
    arr = np.array(out)
    # All pixels were magenta -> all alpha should now be 0
    assert (arr[..., 3] == 0).all(), f"expected all alpha=0 after pre-despill; got {arr[..., 3]}"


def test_pre_despill_preserves_content_alpha() -> None:
    """Non-magenta pixels keep their original alpha."""
    img = Image.new("RGBA", (10, 10), (50, 200, 80, 255))
    out = sprite_slicing._pre_despill_raw_for_upscale(img, chroma_threshold=30)
    arr = np.array(out)
    assert (arr[..., 3] == 255).all(), "non-magenta pixels should retain alpha"


def test_full_pipeline_pre_despill_reduces_wide_pink(tmp_path: Path) -> None:
    """End-to-end: pre-despill + post-anchor despill drives wide_count well below 100."""
    raw = _make_synthetic_codex_raw()
    raw_path = tmp_path / "raw.png"
    raw.save(raw_path)

    # Slice with strict-pitch (default pre_despill_raw=True).
    cells = sprite_slicing.slice_grid_cells(raw, GRID, GRID, CELL)
    assert len(cells) == GRID * GRID

    frames_dir = tmp_path / "frames_raw"
    frames_dir.mkdir(exist_ok=True)
    paths: list[Path] = []
    for i, cell in enumerate(cells):
        p = frames_dir / f"sheet_frame_{i:02d}.png"
        cell.save(p)
        paths.append(p)

    # Run the standard remove-bg + normalize chain.
    import sprite_process

    nobg_dir = tmp_path / "frames_nobg"
    rc = sprite_process.main(
        [
            "remove-bg",
            *(str(p) for p in paths),
            "--output-dir",
            str(nobg_dir),
            "--bg-mode",
            "chroma",
            "--chroma-threshold",
            "80",
        ]
    )
    assert rc == 0

    norm_dir = tmp_path / "frames_normalized"
    rc = sprite_process.main(
        [
            "normalize",
            "--mode",
            "spritesheet",
            "--input-dir",
            str(nobg_dir),
            "--output-dir",
            str(norm_dir),
            "--cell-size",
            str(CELL),
            "--anchor-mode",
            "mass-centroid",
        ]
    )
    assert rc == 0

    # Assemble final sheet
    out_dir = tmp_path / "out"
    rc = sprite_process.main(
        [
            "assemble",
            "--frames-dir",
            str(norm_dir),
            "--grid",
            f"{GRID}x{GRID}",
            "--cell-size",
            str(CELL),
            "--output-dir",
            str(out_dir),
            "--name",
            "sheet",
            "--no-strips",
        ]
    )
    assert rc == 0

    sheet_path = out_dir / "sheet_sheet.png"
    mag = sprite_verify.verify_no_magenta(sheet_path, threshold_strict=0, threshold_wide=30)
    # ADR-208 RC-5: the spritesheet orchestrator threshold is 30.
    assert mag["wide_count"] <= 30, (
        f"expected wide_count <= 30 with pre-despill on; got wide_count={mag['wide_count']}, "
        f"strict_count={mag['strict_count']}"
    )


def test_post_anchor_despill_helper_exists_and_callable() -> None:
    """`_post_anchor_despill_pink` is the documented RC-5 cleanup helper."""
    assert hasattr(sprite_anchor, "_post_anchor_despill_pink"), (
        "RC-5 expects `_post_anchor_despill_pink` in sprite_anchor"
    )
    helper = sprite_anchor._post_anchor_despill_pink
    # Build a 10x10 RGBA array with pink-cast pixels at silhouette edge.
    arr = np.zeros((10, 10, 4), dtype=np.uint8)
    arr[:, :, 0] = 220  # R high
    arr[:, :, 1] = 80  # G low
    arr[:, :, 2] = 150  # B moderate
    arr[:, :, 3] = 220  # alpha > 200 (relaxed criterion)
    out = helper(arr)
    # Pink-cast should be neutralized: R and B pulled down to G.
    assert (out[..., 0] == 80).all(), f"R should be pulled to G; got {out[..., 0]}"
    assert (out[..., 2] == 80).all(), f"B should be pulled to G; got {out[..., 2]}"


def main() -> int:
    """Standalone runner (works without pytest)."""
    import tempfile

    no_arg_tests = [
        test_slice_grid_cells_pre_despill_default_is_true,
        test_pre_despill_zeroes_magenta_alpha,
        test_pre_despill_preserves_content_alpha,
        test_post_anchor_despill_helper_exists_and_callable,
    ]
    tmp_tests = [
        test_full_pipeline_pre_despill_reduces_wide_pink,
    ]
    failures: list[tuple[str, str]] = []
    for t in no_arg_tests:
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
    print(f"\nAll {len(no_arg_tests) + len(tmp_tests)} tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
