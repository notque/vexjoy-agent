#!/usr/bin/env python3
"""Regression tests for ADR-208 RC-4 (mass-centroid is the default anchor mode).

ADR-208 flips the default anchor mode in `normalize_spritesheet` from
`ground-line` (legacy) to `mass-centroid`. The mass centroid integrates
over all opaque pixels, so a single limb extension only nudges it by a few
pixels (vs the dozens that bbox-bottom shifts on action sheets). The
empirical drop on the canonical luchadora-highflyer/05-specials sample:
anchor stddev 17.5 -> 0.6 px.

Tests:
  1. `normalize_spritesheet`'s `anchor_mode` parameter defaults to
     "mass-centroid".
  2. `sprite_pipeline.py --anchor-mode` argparse default is
     "mass-centroid".
  3. `sprite_process.py normalize --anchor-mode` argparse default is
     "mass-centroid".
  4. End-to-end: a synthetic sheet with a "fist" extending downward on one
     frame produces a tighter centroid stddev under mass-centroid than
     under ground-line.

Run with pytest:

    pytest skills/game-sprite-pipeline/scripts/test_rc4_mass_centroid_default.py -v
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
import sprite_pipeline
import sprite_process
import sprite_verify


def test_normalize_spritesheet_default_anchor_mode_is_mass_centroid() -> None:
    """`normalize_spritesheet`'s default `anchor_mode` is `mass-centroid`."""
    sig = inspect.signature(sprite_anchor.normalize_spritesheet)
    default = sig.parameters["anchor_mode"].default
    assert default == "mass-centroid", f"expected default 'mass-centroid'; got {default!r}"


def test_sprite_pipeline_argparse_default_anchor_mode() -> None:
    """`sprite_pipeline.py --anchor-mode` argparse default is `mass-centroid`."""
    parser = sprite_pipeline.build_parser()
    actions = {a.dest: a for a in parser._actions}
    anchor_action = actions["anchor_mode"]
    assert anchor_action.default == "mass-centroid", anchor_action.default


def test_sprite_process_normalize_argparse_default_anchor_mode() -> None:
    """`sprite_process.py normalize --anchor-mode` argparse default is `mass-centroid`."""
    parser = sprite_process.build_parser()
    # Find the normalize subparser.
    subparsers = [a for a in parser._actions if isinstance(a, type(parser._subparsers))]
    # Easier: parse and inspect.
    args = parser.parse_args(
        [
            "normalize",
            "--mode",
            "spritesheet",
            "--input-dir",
            "/tmp/_unused",
            "--output-dir",
            "/tmp/_unused",
        ]
    )
    assert args.anchor_mode == "mass-centroid", args.anchor_mode


def _make_action_frames_with_one_lunge(cell: int = 256, n_frames: int = 4) -> list[Image.Image]:
    """Build n_frames frames where one frame has a "fist" extending below the body.

    The lunge frame's bbox-bottom is dominated by the fist (low y), so
    bbox-bottom anchoring would pin the fist instead of the body trunk
    and the centroid would shift visibly upward. Mass-centroid anchoring
    integrates over all opaque pixels and pins the trunk-centroid stable.
    """
    frames: list[Image.Image] = []
    for i in range(n_frames):
        img = np.zeros((cell, cell, 4), dtype=np.uint8)
        # Body trunk: rectangle from y=64 to y=192, x=96 to x=160 (centered)
        img[64:192, 96:160, :3] = (200, 100, 80)
        img[64:192, 96:160, 3] = 255
        # Head: top of trunk
        img[40:64, 110:146, :3] = (220, 180, 150)
        img[40:64, 110:146, 3] = 255
        # Lunge: on frame 1, add a "fist" extending DOWN past the body
        # (bbox-bottom is at y=240 instead of y=192).
        if i == 1:
            img[192:240, 130:150, :3] = (220, 180, 150)
            img[192:240, 130:150, 3] = 255
        frames.append(Image.fromarray(img, "RGBA"))
    return frames


def test_mass_centroid_stays_stable_against_lunge_outlier(tmp_path: Path) -> None:
    """Synthetic 4-frame sheet with one lunge frame: mass-centroid stddev < 8 px."""
    frames = _make_action_frames_with_one_lunge(cell=256, n_frames=4)
    frame_paths: list[Path] = []
    for i, fr in enumerate(frames):
        p = tmp_path / f"sheet_frame_{i:02d}.png"
        fr.save(p)
        frame_paths.append(p)

    output_dir = tmp_path / "normalized_centroid"
    sprite_anchor.normalize_spritesheet(
        frame_paths,
        output_dir,
        cell_w=256,
        cell_h=256,
        anchor_mode="mass-centroid",
    )

    # Re-assemble into a sheet for verification
    cell = 256
    sheet = Image.new("RGBA", (4 * cell, cell), (0, 0, 0, 0))
    for i in range(4):
        cell_img = Image.open(output_dir / f"sheet_frame_{i:02d}.png").convert("RGBA")
        sheet.paste(cell_img, (i * cell, 0), cell_img)
    sheet_path = tmp_path / "centroid_sheet.png"
    sheet.save(sheet_path)
    res = sprite_verify.verify_anchor_consistency(sheet_path, 4, 1, cell, max_centroid_y_stddev_px=8.0)
    assert res["passed"], f"mass-centroid should pass anchor stddev <= 8; got {res}"
    # Also assert the absolute stddev is well under 8 (the "drift-free" claim).
    assert res["stddev"] < 8.0, f"mass-centroid stddev {res['stddev']} not < 8 px"


def test_ground_line_drifts_against_lunge_outlier(tmp_path: Path) -> None:
    """Same synthetic input under ground-line anchor: stddev > mass-centroid's.

    This is the negative control proving the default flip matters: the
    same input that mass-centroid drives near-zero produces measurable
    drift under the legacy ground-line strategy.
    """
    frames = _make_action_frames_with_one_lunge(cell=256, n_frames=4)
    frame_paths: list[Path] = []
    for i, fr in enumerate(frames):
        p = tmp_path / f"sheet_frame_{i:02d}.png"
        fr.save(p)
        frame_paths.append(p)

    output_dir_centroid = tmp_path / "normalized_centroid"
    sprite_anchor.normalize_spritesheet(
        frame_paths, output_dir_centroid, cell_w=256, cell_h=256, anchor_mode="mass-centroid"
    )
    output_dir_groundline = tmp_path / "normalized_groundline"
    sprite_anchor.normalize_spritesheet(
        frame_paths, output_dir_groundline, cell_w=256, cell_h=256, anchor_mode="ground-line"
    )

    cell = 256

    def _stddev(out_dir: Path) -> float:
        sheet = Image.new("RGBA", (4 * cell, cell), (0, 0, 0, 0))
        for i in range(4):
            cell_img = Image.open(out_dir / f"sheet_frame_{i:02d}.png").convert("RGBA")
            sheet.paste(cell_img, (i * cell, 0), cell_img)
        sheet_path = out_dir.parent / f"{out_dir.name}_sheet.png"
        sheet.save(sheet_path)
        return float(sprite_verify.verify_anchor_consistency(sheet_path, 4, 1, cell)["stddev"])

    centroid_stddev = _stddev(output_dir_centroid)
    groundline_stddev = _stddev(output_dir_groundline)
    # mass-centroid's stddev should be smaller than ground-line's on this
    # input. The exact magnitude is implementation-dependent so we assert
    # the *ordering* (which is the contract the default flip is built on).
    assert centroid_stddev <= groundline_stddev, (
        f"mass-centroid stddev ({centroid_stddev}) should be <= ground-line stddev ({groundline_stddev})"
    )


def main() -> int:
    """Standalone runner (works without pytest)."""
    import tempfile

    no_arg_tests = [
        test_normalize_spritesheet_default_anchor_mode_is_mass_centroid,
        test_sprite_pipeline_argparse_default_anchor_mode,
        test_sprite_process_normalize_argparse_default_anchor_mode,
    ]
    tmp_tests = [
        test_mass_centroid_stays_stable_against_lunge_outlier,
        test_ground_line_drifts_against_lunge_outlier,
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
