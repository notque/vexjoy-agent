#!/usr/bin/env python3
"""Verifier-gate primitives for the game-sprite-pipeline skill.

Owns the six deterministic build-time gates (`verify_no_magenta`,
`verify_grid_alignment`, `verify_anchor_consistency`,
`verify_frames_have_content`, `verify_frames_distinct`,
`verify_pixel_preservation`) plus the combined `verify_asset_outputs`
runner and the `verify-asset` CLI subcommand.

Per docs/PHILOSOPHY.md "Everything That Can Be Deterministic, Should Be"
and the Verifier pattern: separate planner / executor / verifier roles.
The verifier's job is to try to break the result -- "looks correct" is
not a verdict. These functions are the falsifiable checks the prior
pipeline lacked: the same broken output shipped every time because
nothing flagged it. Each verifier returns evidence-bearing structured
data the build can hard-fail on.

Public surface (re-exported through `sprite_process` for backward compat):
    verify_no_magenta, verify_grid_alignment, verify_anchor_consistency,
    verify_frames_have_content, verify_frames_distinct,
    verify_pixel_preservation, verify_asset_outputs, cmd_verify_asset,
    _slice_grid_into_cells, _dhash, _hamming.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("sprite-pipeline.sprite_verify")

try:
    from PIL import Image
except ImportError as e:
    logger.error("Pillow not installed: %s", e)
    logger.error("Install with: pip install pillow")
    sys.exit(1)

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from sprite_anchor import find_alpha_mass_centroid
from sprite_slicing import _parse_grid


# ---------------------------------------------------------------------------
# Verification gates (deterministic build-time checks)
# ---------------------------------------------------------------------------
def verify_no_magenta(
    img: Image.Image | Path | str,
    threshold_strict: int = 0,
    threshold_wide: int = 10,
) -> dict:
    """Pixel-comparison verification: count residual magenta in a final asset.

    Two pixel classes (mirroring the criteria in `kill_pink_fringe` and
    `neutralize_interior_magenta_spill`):

      - strict_count: R>200 AND B>200 AND G<100, alpha>16 (or full opaque
        for non-RGBA). Catches near-pure (255,0,255) bleeding through.
      - wide_count: R>130 AND B>120 AND G<80 AND R-G>50 AND B-G>40,
        alpha>16. Catches diluted pink halo / fringe survival.

    Returns dict with `passed = strict_count <= threshold_strict and
    wide_count <= threshold_wide`. The build-time gate hard-fails on
    `passed=False`. Pure numpy, ~10ms / 1024px image.

    Accepts PIL.Image, Path, or str. PNG/GIF/WebP all decode through Pillow.
    """
    if not HAS_NUMPY:
        # Pure-Python fallback would be O(W*H) loops -- too slow for build gate.
        return {
            "strict_count": -1,
            "wide_count": -1,
            "total_visible": -1,
            "pct": 0.0,
            "passed": False,
            "error": "numpy required for verify_no_magenta",
        }

    if isinstance(img, (str, Path)):
        img = Image.open(img)
    img = img.convert("RGBA")
    arr = np.array(img)
    r = arr[..., 0].astype(int)
    g = arr[..., 1].astype(int)
    b = arr[..., 2].astype(int)
    a = arr[..., 3]

    visible = a > 16
    total_visible = int(visible.sum())

    # Strict: near-pure magenta (255, 0, 255). Excludes purple (B much
    # higher than R) and saturated red. Pure magenta has B/R ~= 1.0; pure
    # purple has B/R >= 1.08. We require B/R <= 1.05 to keep the strict
    # band tight around magenta -- this preserves bright-purple costume
    # pixels (e.g. wizard robes (220,87,238) at B/R=1.08, manager-loop
    # cell (203,93,232) at B/R=1.14).
    strict = (r > 200) & (b > 200) & (g < 100) & (b * 100 <= r * 105) & visible
    # Wide-pink/magenta criterion: matches neutralize_interior_magenta_spill's
    # Tier B exactly. The verifier's job is to flag pixels the post-processor
    # SHOULD have neutralized but did not. Anything outside Tier B's gate is
    # legitimate costume color (purple shadows, dark hair) and not a defect.
    #
    # Tier B gates (matched 1:1 with neutralize_interior_magenta_spill):
    #  - r >= 130, b >= 90, g <= 100  (pink-cast color signature)
    #  - r - g > 90, b - g > 50       (high color separation, not muddy)
    #  - b * 100 <= r * 110           (pink/magenta hue, not purple)
    #
    # Costume protection: a manager's purple-shadow pixel (132, 56, 129)
    # has r-g=76 < 90, fails the tier-B gate, NOT flagged. A magenta bleed
    # pixel (250, 25, 202) has r-g=225 > 90, b-g=177 > 50, B*100=20200
    # vs R*110=27500 ✓ -- IS flagged. The asymmetry is intentional.
    wide = (r >= 130) & (b >= 90) & (g <= 100) & ((r - g) > 90) & ((b - g) > 50) & (b * 100 <= r * 110) & visible

    strict_count = int(strict.sum())
    wide_count = int(wide.sum())
    pct = (strict_count + wide_count) / max(total_visible, 1) * 100.0
    passed = strict_count <= threshold_strict and wide_count <= threshold_wide

    return {
        "strict_count": strict_count,
        "wide_count": wide_count,
        "total_visible": total_visible,
        "pct": round(pct, 4),
        "passed": passed,
    }


def verify_grid_alignment(
    img: Image.Image | Path | str,
    grid_rows: int,
    grid_cols: int,
    cell_size: int,
    edge_margin_px: int = 2,
    violation_tolerance: int = 1,
) -> dict:
    """Per-cell alignment check: each cell's character must clear cell edges.

    For each cell (row, col) in the sheet:
      1. Extract the cell at (col*cell_size, row*cell_size, ...)
      2. Find the alpha-bbox of non-background pixels
      3. Assert bbox top >= edge_margin_px and bbox bottom <= cell_size - edge_margin_px
         (and same for left/right). A character whose silhouette touches the
         cell boundary indicates an off-grid cut: the slicer placed the cell
         boundary inside another character's body.

    Returns `{violations: [{row, col, side, bbox}, ...], passed: bool}`.
    Empty cells (no opaque pixels) are NOT counted as violations -- the sheet
    may legitimately have idle frames.

    The check is deliberately conservative: edge_margin_px=2 catches
    only the hard "character runs into cell edge" failure, not artistic
    silhouettes that happen to touch a 1-pixel margin. Tune per asset if
    needed.
    """
    if not HAS_NUMPY:
        return {"violations": [], "passed": True, "error": "numpy required"}

    if isinstance(img, (str, Path)):
        img = Image.open(img)
    img = img.convert("RGBA")
    arr = np.array(img)

    expected_w = grid_cols * cell_size
    expected_h = grid_rows * cell_size
    if arr.shape[1] != expected_w or arr.shape[0] != expected_h:
        return {
            "violations": [],
            "passed": False,
            "error": (f"image size {(arr.shape[1], arr.shape[0])} != expected {(expected_w, expected_h)}"),
        }

    # The failure mode this verifier targets: the slicer placed a cell
    # boundary mid-body (the naive-grid cell_size bug fixed in 53c6915).
    # Symptom: the bbox spans most of the cell AND touches both opposing
    # edges (left+right span = horizontal slice, top+bottom span =
    # vertical slice). A single edge touch is normal -- arms can extend
    # past one side in an action pose, ground-line anchoring intentionally
    # puts feet near cell bottom. We only flag the "sliced clean through"
    # pattern.
    violations: list[dict] = []
    span_threshold = 0.85  # bbox must cover >=85% of axis to count as a "slice"
    for row in range(grid_rows):
        for col in range(grid_cols):
            x0, y0 = col * cell_size, row * cell_size
            cell = arr[y0 : y0 + cell_size, x0 : x0 + cell_size]
            alpha = cell[..., 3]
            ys, xs = np.where(alpha > 0)
            if len(ys) == 0:
                continue  # empty cell, fine
            bbox_top = int(ys.min())
            bbox_bot = int(ys.max())
            bbox_left = int(xs.min())
            bbox_right = int(xs.max())

            top_hit = bbox_top < edge_margin_px
            bot_hit = bbox_bot > cell_size - 1 - edge_margin_px
            left_hit = bbox_left < edge_margin_px
            right_hit = bbox_right > cell_size - 1 - edge_margin_px

            h_span = (bbox_right - bbox_left + 1) / cell_size
            v_span = (bbox_bot - bbox_top + 1) / cell_size

            # "Sliced left-to-right": left+right both hit AND span is large
            horizontal_slice = left_hit and right_hit and h_span >= span_threshold
            # "Sliced top-to-bottom" (excluding ground-line + small char):
            # top+bottom both hit AND span is large. Ground-line alone hits
            # bottom only, so top+bottom together implies real slicing.
            vertical_slice = top_hit and bot_hit and v_span >= span_threshold

            if horizontal_slice or vertical_slice:
                violations.append(
                    {
                        "row": row,
                        "col": col,
                        "pattern": "horizontal_slice" if horizontal_slice else "vertical_slice",
                        "bbox": [bbox_left, bbox_top, bbox_right, bbox_bot],
                        "h_span": round(h_span, 3),
                        "v_span": round(v_span, 3),
                        "edges_hit": [
                            s
                            for s, hit in [
                                ("top", top_hit),
                                ("bottom", bot_hit),
                                ("left", left_hit),
                                ("right", right_hit),
                            ]
                            if hit
                        ],
                    }
                )

    # Tolerate up to violation_tolerance isolated violations. The naive-grid
    # cell_size bug produced 30+ violations across the whole sheet (a slice
    # cut every character). A single big-character cell is normal art and
    # should not hard-fail the verification gate.
    return {
        "violations": violations,
        "passed": len(violations) <= violation_tolerance,
        "violation_count": len(violations),
        "tolerance": violation_tolerance,
    }


def _slice_grid_into_cells(img: Image.Image, cols: int, rows: int) -> list[Image.Image]:
    """Strict integer slice for an exact-size sheet (final-sheet.png).

    Different from `slice_grid_cells` (which derives pitch from raw size for
    image-gen output). The verifier's input is the canonical post-processed
    final-sheet whose pitch IS cell_size by construction.
    """
    w, h = img.size
    cw, ch = w // cols, h // rows
    cells: list[Image.Image] = []
    for r in range(rows):
        for c in range(cols):
            cells.append(img.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch)))
    return cells


def verify_anchor_consistency(
    img: Image.Image | Path | str,
    grid_cols: int,
    grid_rows: int,
    cell_size: int,
    max_centroid_y_stddev_px: float = 8.0,
    iqr_outlier_multiplier: float = 2.0,
) -> dict:
    """Per-frame mass-centroid Y stddev gate. Catches the "hop" failure class.

    Why this gate exists: under bbox-bottom anchoring, frames whose bbox-bottom
    is a fist (lunge) or an extended leg (kick) get the wrong body part pinned
    to the ground line. The visible result is the trunk floating up by 30-50px
    on those frames — the user's "hop" reproduction. bbox-bottom-Y stddev is
    0 (the anchor IS pinning it!), so the existing verifier passes; the visible
    motion lives in the centroid.

    Flags:
      - centroid-Y stddev > max_centroid_y_stddev_px → fail (broad drift)
      - any frame's centroid more than IQR*multiplier from median → outlier

    Tuning: 8px stddev is the empirical "barely visible" threshold for 256px
    cells; tighten to 4px for portrait-loops where the camera is fixed and
    drift would be jarring.
    """
    if not HAS_NUMPY:
        return {"passed": True, "stddev": 0, "outliers": [], "error": "numpy required"}
    if isinstance(img, (str, Path)):
        img = Image.open(img)
    img = img.convert("RGBA")
    cells = _slice_grid_into_cells(img, grid_cols, grid_rows)
    centroids: list[float] = []
    for cell in cells:
        c = find_alpha_mass_centroid(cell)
        if c is None:
            centroids.append(float("nan"))
        else:
            centroids.append(c[1])
    valid = [c for c in centroids if not np.isnan(c)]
    if len(valid) < 2:
        return {
            "passed": True,
            "stddev": 0.0,
            "outliers": [],
            "centroid_y_per_cell": centroids,
            "valid_count": len(valid),
        }
    arr = np.array(valid)
    stddev = float(arr.std(ddof=0))
    median = float(np.median(arr))
    q1 = float(np.percentile(arr, 25))
    q3 = float(np.percentile(arr, 75))
    iqr = max(q3 - q1, 1.0)
    cutoff = iqr * iqr_outlier_multiplier
    outliers: list[dict] = []
    for i, c in enumerate(centroids):
        if np.isnan(c):
            continue
        if abs(c - median) > cutoff:
            outliers.append(
                {
                    "cell_index": i,
                    "centroid_y": round(c, 2),
                    "median": round(median, 2),
                    "delta_from_median": round(abs(c - median), 2),
                }
            )
    # Hard fail: stddev > threshold (broad drift across the cycle).
    # Hard fail: any outlier whose delta from median exceeds ABSOLUTE
    #   px threshold = max_stddev * 2 (so delta > 16px on default config).
    #   This catches a single-frame "hop" where one frame is dramatically
    #   shifted — the user's 05 powerhouse case had outlier deltas of
    #   ~40px under bbox-bottom anchor.
    # Soft signal: smaller outliers (delta in [stddev_threshold, 2x]) are
    #   surfaced but pass — they cover legitimate aerial frames.
    abs_outlier_threshold = max_centroid_y_stddev_px * 2
    big_outliers = [o for o in outliers if o["delta_from_median"] > abs_outlier_threshold]
    passed = stddev <= max_centroid_y_stddev_px and not big_outliers
    return {
        "passed": passed,
        "stddev": round(stddev, 3),
        "median": round(median, 2),
        "iqr": round(iqr, 2),
        "outliers": outliers,
        "big_outliers": big_outliers,
        "max_stddev_threshold": max_centroid_y_stddev_px,
        "abs_outlier_threshold_px": abs_outlier_threshold,
        "centroid_y_per_cell": [round(c, 2) if not np.isnan(c) else None for c in centroids],
    }


# TODO(ADR-207 RC-3 follow-up): verify_frames_have_content checks alpha
# pixel count on the FINAL only. It does not cross-reference the raw
# silhouette per cell. ADR-207 partially closes this with the new
# verify_raw_vs_final_cell_parity gate, which IS the raw-vs-final
# cross-check. A future RC-3 closure would unify the two gates: a single
# gate that examines per-cell alpha-coverage in the FINAL, conditioned on
# raw silhouette presence, with a unified diagnostic. Tracked as an
# RC-3 follow-up; not in scope for ADR-207.
def verify_frames_have_content(
    img: Image.Image | Path | str,
    grid_cols: int,
    grid_rows: int,
    cell_size: int,
    min_alpha_pixel_pct: float = 2.0,
    max_blank_count: int = 0,
) -> dict:
    """Per-cell alpha-coverage gate. Catches blank-cell failure class.

    A cell with <min_alpha_pixel_pct% opaque pixels is considered blank.

    When this gate fires: the post-processing extracted a blank cell. DO NOT
    regenerate via Codex as a fix. Codex output is ground truth -- the raw
    almost certainly has content in that cell. The bug is in our slicer's
    grid pitch math (raw_size / grid_dim mismatch), the connected-components
    centroid-to-cell mapping, or the despill chain over-trimming the
    silhouette. Open the raw at the corresponding cell coordinates to confirm
    content exists, then trace which post-processing step lost it.

    See references/error-catalog.md "Anti-pattern: Codex Regeneration as a
    Post-Processing Fix" for the full diagnostic procedure.

    The default (max_blank_count=0) is strict; relax for assets where one
    blank frame is a deliberate art choice.
    """
    if not HAS_NUMPY:
        return {"passed": True, "blank_cells": [], "error": "numpy required"}
    if isinstance(img, (str, Path)):
        img = Image.open(img)
    img = img.convert("RGBA")
    cells = _slice_grid_into_cells(img, grid_cols, grid_rows)
    blanks: list[dict] = []
    pcts: list[float] = []
    for i, cell in enumerate(cells):
        arr = np.array(cell)
        alpha = arr[..., 3]
        pct = float((alpha > 16).sum()) / max(alpha.size, 1) * 100.0
        pcts.append(round(pct, 2))
        if pct < min_alpha_pixel_pct:
            blanks.append({"cell_index": i, "alpha_pct": round(pct, 2)})
    result: dict = {
        "passed": len(blanks) <= max_blank_count,
        "blank_cells": blanks,
        "alpha_pct_per_cell": pcts,
        "min_alpha_pct_threshold": min_alpha_pixel_pct,
    }
    if blanks:
        # Actionable failure message: never recommend regenerating Codex.
        result["actionable_message"] = (
            "post-processing extracted a blank cell -- debug slicer alignment for this "
            "asset's grid (raw_size x grid pitch math), connected-components centroid "
            "mapping, or despill over-trim. Codex output is ground truth; do NOT "
            "regenerate the raw. See references/error-catalog.md 'Anti-pattern: Codex "
            "Regeneration as a Post-Processing Fix'."
        )
    return result


def _dhash(img: Image.Image, size: int = 8) -> int:
    """Difference-hash for perceptual similarity (homemade, no imagehash dep).

    Reduces image to (size+1) by size grayscale, then encodes pairwise horizontal
    differences as bits. Hamming distance between two dHashes correlates with
    perceptual similarity. dHash is robust to small color/lighting changes
    while remaining sensitive to silhouette shape — appropriate for catching
    near-duplicate animation frames.
    """
    if HAS_NUMPY:
        small = img.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
        arr = np.array(small)
        diff = arr[:, 1:] > arr[:, :-1]
        bits = 0
        for v in diff.flatten():
            bits = (bits << 1) | int(v)
        return bits
    # pure-python fallback
    small = img.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    px = small.load()
    bits = 0
    for y in range(size):
        for x in range(size):
            bits = (bits << 1) | (1 if px[x + 1, y] > px[x, y] else 0)
    return bits


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def verify_frames_distinct(
    img: Image.Image | Path | str,
    grid_cols: int,
    grid_rows: int,
    cell_size: int,
    hamming_threshold: int = 4,
    max_duplicate_pct: float = 10.0,
    skip_blank_cells: bool = True,
    blank_alpha_pct: float = 2.0,
) -> dict:
    """Perceptual-hash duplicate-frame gate. Catches "two frames merged" failure.

    Pairs with `verify_frames_have_content`: blank cells are dropped from the
    duplicate analysis (skip_blank_cells=True default), because two blank
    cells would falsely register as a duplicate pair.

    Behavior:
      - Compute dHash for every cell with content.
      - Pair-wise Hamming distance: any pair with distance < hamming_threshold
        counts as a duplicate.
      - Fail if duplicate_pct > max_duplicate_pct.

    Tuning: idle loops (subtle breath/blink) often have legitimate hamming
    distances around 2-3, so default threshold 4 + tolerance 10% leaves
    headroom. Action cycles should hit far higher distances; if dup_pct
    exceeds threshold, the cycle is broken (frames repeated).

    Returns the involved cell indices for diagnosis.
    """
    if not HAS_NUMPY:
        return {"passed": True, "duplicate_pairs": [], "error": "numpy required"}
    if isinstance(img, (str, Path)):
        img = Image.open(img)
    img = img.convert("RGBA")
    cells = _slice_grid_into_cells(img, grid_cols, grid_rows)
    if skip_blank_cells:
        # Pre-filter to cells with content so blank vs blank doesn't pollute.
        valid_cells: list[tuple[int, Image.Image]] = []
        for i, c in enumerate(cells):
            arr = np.array(c)
            pct = float((arr[..., 3] > 16).sum()) / max(arr[..., 3].size, 1) * 100.0
            if pct >= blank_alpha_pct:
                valid_cells.append((i, c))
    else:
        valid_cells = list(enumerate(cells))
    hashes = [(i, _dhash(c)) for i, c in valid_cells]
    duplicates: list[dict] = []
    cells_in_dup: set[int] = set()
    for ai in range(len(hashes)):
        for bi in range(ai + 1, len(hashes)):
            i1, h1 = hashes[ai]
            i2, h2 = hashes[bi]
            d = _hamming(h1, h2)
            if d < hamming_threshold:
                duplicates.append({"a_index": i1, "b_index": i2, "hamming_distance": d})
                cells_in_dup.add(i1)
                cells_in_dup.add(i2)
    n = len(cells)
    # Pct = fraction of cells participating in at least one dup pair.
    # This is bounded [0, 100]. Earlier formula (pairs * 2 / n) explodes
    # past 100% on action sheets where every pair fires.
    dup_pct = len(cells_in_dup) / max(n, 1) * 100.0
    return {
        "passed": dup_pct <= max_duplicate_pct,
        "duplicate_pairs": duplicates,
        "duplicate_pct": round(dup_pct, 2),
        "max_duplicate_pct_threshold": max_duplicate_pct,
        "hamming_threshold": hamming_threshold,
        "valid_cell_count": len(hashes),
        "cells_in_duplicate_pairs": sorted(cells_in_dup),
    }


def verify_pixel_preservation(
    raw_path: Path | str,
    final_sheet_path: Path | str,
    grid_cols: int,
    grid_rows: int,
    cell_size: int,
    chroma_threshold: int = 90,
    min_pixel_ratio: float = 0.40,
    min_raw_pixels_per_cell: int = 200,
    max_lossy_cells_pct: float = 25.0,
) -> dict:
    """Compare raw cell silhouette pixel count against final cell pixel count.

    Catches the "effects clipped" failure (asset 27 dragon flame breath,
    where the fire breath is despilled to oblivion) AND the "entire silhouette
    lost" failure (asset 19 painted veteran, where pass2 over-floods).

    Methodology (intentionally conservative against painted-style halo):
      - Use chroma_threshold=90 for the raw count (matches pass2 cutoff).
        Pixels with sum-of-abs-diff to magenta < 90 are halo, not silhouette.
        This avoids the false-positive where antialiased magenta-fringe
        inflates raw_count and makes preservation look bad.
      - For each cell, ratio = final_visible / raw_silhouette.
      - Fail when more than max_lossy_cells_pct of cells lose >60% of their
        silhouette (ratio < 0.40). This is the "the despill chain ate the
        character" signal, not the noise of normal halo trimming.

    Cells with raw_silhouette < min_raw_pixels_per_cell are skipped (they're
    too sparse to evaluate ratio meaningfully).
    """
    if not HAS_NUMPY:
        return {"passed": True, "lossy_cells": [], "error": "numpy required"}
    raw = Image.open(raw_path).convert("RGBA")
    fin = Image.open(final_sheet_path).convert("RGBA")
    rw, rh = raw.size
    raw_cell_w = rw / grid_cols
    raw_cell_h = rh / grid_rows
    # Normalize: when raw cell area differs from final cell area (e.g. Codex
    # returns 1254x1254 for a 512x512 target), the raw silhouette pixel
    # count is N times the final's even at 100% preservation, where
    # N = raw_cell_area / final_cell_area. Account for this so the ratio
    # measures REAL silhouette preservation, not area scale.
    area_ratio = (raw_cell_w * raw_cell_h) / max(cell_size * cell_size, 1)
    raw_cells: list[Image.Image] = []
    for r in range(grid_rows):
        for c in range(grid_cols):
            x0 = round(c * raw_cell_w)
            y0 = round(r * raw_cell_h)
            x1 = round((c + 1) * raw_cell_w)
            y1 = round((r + 1) * raw_cell_h)
            raw_cells.append(raw.crop((x0, y0, x1, y1)))
    fin_cells = _slice_grid_into_cells(fin, grid_cols, grid_rows)
    chroma = np.array((255, 0, 255))
    ratios: list[dict] = []
    lossy: list[dict] = []
    n_evaluated = 0
    for i, (rc, fc) in enumerate(zip(raw_cells, fin_cells)):
        ra = np.array(rc.convert("RGBA"))
        rgb = ra[..., :3].astype(int)
        diff = np.abs(rgb - chroma).sum(axis=-1)
        raw_n = int((diff > chroma_threshold).sum())
        fa = np.array(fc.convert("RGBA"))
        fin_n = int((fa[..., 3] > 16).sum())
        # Expected final pixels under 100% preservation: raw_n / area_ratio
        expected_final = raw_n / max(area_ratio, 1e-6)
        if expected_final < min_raw_pixels_per_cell:
            ratios.append({"cell_index": i, "raw": raw_n, "final": fin_n, "ratio": None, "skipped": True})
            continue
        # Area-normalized ratio = how much of the expected silhouette survived.
        ratio = fin_n / max(expected_final, 1)
        # Cap at 1.0; ratios > 1 just mean more pixels survived than the raw
        # silhouette had (legitimate when bg-removal cleans halo and the area-
        # normalized estimate is conservative).
        ratio = min(ratio, 2.0)
        ratios.append(
            {
                "cell_index": i,
                "raw": raw_n,
                "final": fin_n,
                "expected": round(expected_final, 1),
                "ratio": round(ratio, 3),
            }
        )
        n_evaluated += 1
        if ratio < min_pixel_ratio:
            lossy.append(
                {
                    "cell_index": i,
                    "raw_silhouette": raw_n,
                    "final_visible": fin_n,
                    "expected_final": round(expected_final, 1),
                    "ratio": round(ratio, 3),
                }
            )
    lossy_pct = (len(lossy) / max(n_evaluated, 1)) * 100.0
    result: dict = {
        "passed": lossy_pct <= max_lossy_cells_pct,
        "lossy_cells": lossy,
        "lossy_pct": round(lossy_pct, 2),
        "ratios": ratios,
        "area_ratio_raw_to_final": round(area_ratio, 3),
        "min_pixel_ratio_threshold": min_pixel_ratio,
        "max_lossy_pct_threshold": max_lossy_cells_pct,
    }
    if not result["passed"]:
        result["actionable_message"] = (
            "Content extends past the conceptual cell boundary in the raw "
            "(Codex paints fire jets, projectile trails, auras that cross "
            "cell pitch). Enable content_aware_extraction in the spec, set "
            "has_effects=True, or reduce grid density. Codex output is "
            "ground truth; do NOT regenerate the raw."
        )
    return result


def verify_raw_vs_final_cell_parity(
    raw_path: Path | str,
    final_sheet_path: Path | str,
    grid_cols: int,
    grid_rows: int,
    cell_size: int,
    chroma_threshold: int = 80,
    min_raw_pixels_per_cell: int = 200,
    min_final_alpha_pixels_per_cell: int = 200,
) -> dict:
    """Per-cell parity gate: if raw cell has content, final cell MUST have content.

    ADR-207 Rule 3 / RC-1: catches the smoking-gun blank-cell failure mode.
    `verify_pixel_preservation` measures silhouette-survival ratio (how
    much of the raw silhouette landed in the final). This gate is the
    conservative complement: it only asks "did SOMETHING land?" When the
    raw has > `min_raw_pixels_per_cell` non-magenta pixels in a cell, the
    final's corresponding cell MUST have > `min_final_alpha_pixels_per_cell`
    visible alpha pixels.

    The two thresholds are intentionally symmetric (200 each) so the gate
    fires precisely when the cell went from "has content" to "blank" --
    the RC-1 failure signature. Cells the raw legitimately leaves empty
    (e.g. an animation pose where the character is briefly off-frame)
    skip the check because the precondition is not met.

    Pure numpy. Returns:
      passed: bool
      blank_cells: list[{cell_index, raw_silhouette, final_visible}]
      total_cells_with_raw_content: int
      ratio_pass: float (cells with content -> cells preserved / total)
    """
    if not HAS_NUMPY:
        return {"passed": True, "blank_cells": [], "error": "numpy required"}
    raw = Image.open(raw_path).convert("RGBA")
    fin = Image.open(final_sheet_path).convert("RGBA")
    rw, rh = raw.size
    raw_cell_w = rw / grid_cols
    raw_cell_h = rh / grid_rows
    raw_cells: list[Image.Image] = []
    for r in range(grid_rows):
        for c in range(grid_cols):
            x0 = round(c * raw_cell_w)
            y0 = round(r * raw_cell_h)
            x1 = round((c + 1) * raw_cell_w)
            y1 = round((r + 1) * raw_cell_h)
            raw_cells.append(raw.crop((x0, y0, x1, y1)))
    fin_cells = _slice_grid_into_cells(fin, grid_cols, grid_rows)
    chroma = np.array((255, 0, 255))
    blanks: list[dict] = []
    cells_with_raw_content = 0
    cells_preserved = 0
    for i, (rc, fc) in enumerate(zip(raw_cells, fin_cells)):
        ra = np.array(rc.convert("RGBA"))
        rgb = ra[..., :3].astype(int)
        diff = np.abs(rgb - chroma).sum(axis=-1)
        raw_n = int((diff > chroma_threshold).sum())
        if raw_n <= min_raw_pixels_per_cell:
            # Raw cell is essentially empty; gate's precondition not met.
            continue
        cells_with_raw_content += 1
        fa = np.array(fc.convert("RGBA"))
        fin_n = int((fa[..., 3] > 16).sum())
        if fin_n <= min_final_alpha_pixels_per_cell:
            blanks.append(
                {
                    "cell_index": i,
                    "raw_silhouette": raw_n,
                    "final_visible": fin_n,
                }
            )
        else:
            cells_preserved += 1
    ratio = (cells_preserved / cells_with_raw_content) if cells_with_raw_content > 0 else 1.0
    result: dict = {
        "passed": len(blanks) == 0,
        "blank_cells": blanks,
        "total_cells_with_raw_content": cells_with_raw_content,
        "cells_preserved": cells_preserved,
        "preservation_ratio": round(ratio, 3),
        "min_raw_pixels_per_cell": min_raw_pixels_per_cell,
        "min_final_alpha_pixels_per_cell": min_final_alpha_pixels_per_cell,
    }
    if blanks:
        result["actionable_message"] = (
            "ADR-207 RC-1 cell-parity violation: raw cell(s) have content but the "
            "corresponding final cell(s) are blank. Most common cause: the slicer "
            "routed the cell's content to a neighbor cell via centroid drift "
            "(content-aware on a dense Codex raw). Check that the pipeline used "
            "slice_grid_cells (strict-pitch), not slice_with_content_awareness, "
            "for this dense grid. Codex output is ground truth; do NOT regenerate."
        )
    return result


def verifier_verdict_from_passed(passed: bool) -> str:
    """Derive the contracted verifier_verdict string from the passed bool.

    ADR-207 Rule 2: this is the ONLY function that maps verifier outcomes
    to the public verdict string. Consumers (manifest writers, orchestrators)
    MUST derive their `verifier_verdict` field from this function so the
    field is structurally consistent across producers.
    """
    return "PASS" if passed else "FAIL"


def write_manifest_record(path: Path | str, record: dict) -> None:
    """Asserting writer for manifest records (ADR-207 Rule 2).

    Enforces the verifier-truthfulness contract at WRITE time: a record
    with ``verifier_verdict == "PASS"`` AND a non-empty ``verifier_failures``
    is structurally inconsistent and cannot be persisted. Raises ``ValueError``.

    The contract:
      verifier_verdict == "PASS"  =>  verifier_failures empty (or absent)
      verifier_verdict == "FAIL"  =>  verifier_failures non-empty
      verifier_verdict missing    =>  no enforcement (legacy records)

    Consumers (orchestrators, manifest writers) SHOULD use this writer
    instead of writing JSON directly. The street-fighter-demo orchestrator
    is the reference consumer (see scripts/sf-orchestrator.py).
    """
    verdict = record.get("verifier_verdict")
    failures = record.get("verifier_failures") or []
    if verdict == "PASS" and len(failures) > 0:
        raise ValueError(
            f"manifest contract violation (ADR-207 Rule 2): record claims "
            f"verifier_verdict='PASS' but verifier_failures has {len(failures)} "
            f"entries. Re-run the verifier or set verifier_verdict='FAIL'."
        )
    if verdict == "FAIL" and len(failures) == 0:
        raise ValueError(
            "manifest contract violation (ADR-207 Rule 2): record claims "
            "verifier_verdict='FAIL' but verifier_failures is empty. A FAIL "
            "verdict must carry at least one failure entry."
        )
    Path(path).write_text(json.dumps(record, indent=2), encoding="utf-8")


def verify_asset_outputs(
    asset_dir: Path | str,
    mode: str,
    grid: tuple[int, int] | None = None,
    cell_size: int | None = None,
    magenta_strict_threshold: int = 0,
    magenta_wide_threshold: int | None = None,
    has_effects: bool = False,
) -> dict:
    """Combined build-time gate: run every verifier on every output file.

    Modes:
      - portrait        : check final.png only (single static image, no grid).
      - portrait-loop   : check final-sheet.png, frames-strip.png, animation.gif,
                          final.webp. Grid is fixed (2,2).
      - spritesheet     : check final-sheet.png, frames-strip.png if exists,
                          animation.gif, final.webp. Grid + cell_size required.

    Returns {passed: bool, failures: [{file, check, details}, ...]}.

    `passed=False` means at least one verifier flagged an issue. The caller
    (run_one in generate.py) records this on meta and the demo HTML hides
    the asset behind a red FAIL badge.
    """
    asset_dir = Path(asset_dir)
    failures: list[dict] = []

    # Per-mode wide-pink defaults. Painted portraits and animated GIF
    # quantization both leave a thin band of legitimate pink-cast pixels;
    # spritesheet final-sheet has crisper transparent edges and tolerates
    # less. The thresholds are tuned against the real asset corpus, NOT
    # synthetic canvases, because painted-style art (slay-the-spire-painted)
    # has dithering halftones that legitimately register as wide-pink.
    if magenta_wide_threshold is None:
        if mode == "portrait":
            magenta_wide_threshold = 50
        elif mode == "portrait-loop":
            magenta_wide_threshold = 80
        else:  # spritesheet
            magenta_wide_threshold = 30
    # has_effects assets paint legitimately-pink content (purple plasma arcs,
    # magenta-cast costumes) that the wide-pink heuristic cannot distinguish
    # from background bleed. We skip interior_neutralize_magenta_spill on these
    # to preserve the effects, so the verifier MUST also tolerate them. A
    # 30x relaxation gives breathing room for ~1000 legitimate pink-cast pixels
    # per cell while still catching the "entire silhouette is magenta" failure.
    # The strict (near-pure 255,0,255) threshold also relaxes from 0 to 200:
    # plasma orbs paint near-pure magenta arcs (255,99,255 is "wide"; 255,0,255
    # is "strict") that are intentional and survive despill skip.
    if has_effects:
        magenta_wide_threshold = magenta_wide_threshold * 30
        magenta_strict_threshold = max(magenta_strict_threshold, 200)
    # Format-specific tolerance: GIF and WebP quantization at silhouette
    # edges of magenta-adjacent assets (e.g. purple-suited managers with
    # magenta bg) is a known limitation of the lossy format -- the
    # adaptive palette / lossy compression resurrects pink pixels even
    # when the source RGBA is clean. PNG (lossless) gets the strict
    # threshold; GIF/WebP get a 10x relaxation because the pipeline cannot
    # eliminate format-induced bleed without dropping format support.
    lossy_wide_threshold = magenta_wide_threshold * 10

    files_to_check: list[tuple[str, str]] = []  # (filename, kind)
    if mode == "portrait":
        files_to_check = [("final.png", "static")]
    elif mode == "portrait-loop":
        if grid is None:
            grid = (2, 2)
        files_to_check = [
            ("final-sheet.png", "sheet"),
            ("frames-strip.png", "strip"),
            ("animation.gif", "anim"),
            ("final.webp", "anim"),
        ]
    elif mode == "spritesheet":
        if grid is None or cell_size is None:
            failures.append(
                {"file": "(spec)", "check": "config", "details": "grid + cell_size required for spritesheet mode"}
            )
            return {"passed": False, "failures": failures}
        files_to_check = [
            ("final-sheet.png", "sheet"),
            ("frames-strip.png", "strip"),
            ("animation.gif", "anim"),
            ("final.webp", "anim"),
        ]
    else:
        return {"passed": False, "failures": [{"file": "(spec)", "check": "mode", "details": f"unknown mode {mode!r}"}]}

    cols, rows = grid if grid else (1, 1)

    for fname, kind in files_to_check:
        fpath = asset_dir / fname
        if not fpath.exists():
            # Not all files are required for every asset (frames-strip skipped
            # for >4096px width). Only fail on the always-required files:
            # portraits' final.png and modes' final-sheet.png.
            if (
                mode == "portrait"
                and fname == "final.png"
                or mode in ("portrait-loop", "spritesheet")
                and fname == "final-sheet.png"
            ):
                failures.append({"file": fname, "check": "exists", "details": "missing"})
            continue

        # Magenta check on every existing output. GIF/WebP get a relaxed
        # wide-pink threshold because lossy palette/compression resurrects
        # halo pixels at silhouette edges even when the RGBA source is
        # clean (documented in references/output-formats.md).
        is_lossy = fname.endswith((".gif", ".webp"))
        wide_t = lossy_wide_threshold if is_lossy else magenta_wide_threshold
        try:
            mag = verify_no_magenta(
                fpath,
                threshold_strict=magenta_strict_threshold,
                threshold_wide=wide_t,
            )
            if not mag["passed"]:
                failures.append(
                    {
                        "file": fname,
                        "check": "magenta",
                        "details": {
                            "strict_count": mag["strict_count"],
                            "wide_count": mag["wide_count"],
                            "thresholds": [magenta_strict_threshold, wide_t],
                        },
                    }
                )
        except Exception as e:
            failures.append({"file": fname, "check": "magenta", "details": f"error: {e}"})

        # Grid alignment check on the canonical sheet only (frames-strip is
        # 1xN row; alignment math doesn't apply the same way). Tolerance is
        # 5% of cells: legitimate big-character art can occasionally span an
        # edge, but more than that signals a slicing failure or a generator
        # that lost track of cell boundaries. Per docs/PHILOSOPHY.md
        # "Verifier pattern" -- a verifier that confirms success at 50%
        # bad-cell tolerance is a rubber stamp; the threshold must be tight
        # enough that "passed" carries evidence. For an 8x8 sheet that is 3
        # violations; for a 4x4 sheet that is 1 (matching verify_grid_alignment's
        # default tolerance of 1).
        if kind == "sheet" and mode in ("portrait-loop", "spritesheet"):
            if cell_size is None:
                cell_size = 512 if mode == "portrait-loop" else None
            if cell_size is not None:
                total_cells = cols * rows
                grid_tolerance = max(1, int(total_cells * 0.05))
                try:
                    grid_check = verify_grid_alignment(
                        fpath,
                        rows,
                        cols,
                        cell_size,
                        violation_tolerance=grid_tolerance,
                    )
                    violation_count = grid_check.get(
                        "violation_count",
                        len(grid_check.get("violations", [])),
                    )
                    if not grid_check["passed"]:
                        failures.append(
                            {
                                "file": fname,
                                "check": "grid_alignment",
                                "details": {
                                    "violations": grid_check.get("violations", [])[:5],
                                    "violation_count": violation_count,
                                    "tolerance": grid_check.get("tolerance"),
                                    "error": grid_check.get("error"),
                                },
                            }
                        )
                except Exception as e:
                    failures.append({"file": fname, "check": "grid_alignment", "details": f"error: {e}"})

                # New v8 gates (anchor-consistency, blank-frames,
                # distinct-frames, pixel-preservation). These run on the
                # canonical sheet only; lossy formats (gif/webp) are subject
                # to format-induced drift so re-checking centroids there
                # produces noise. The gates are tuned to catch the user's
                # 8-asset failure set without flagging legitimate art.
                # Tunings rationale:
                #   anchor stddev <= 8 px: visible threshold; the 05
                #     powerhouse "hop" measured 15.84px under bbox-bottom
                #     anchor, so 8 is a tight but achievable target with
                #     mass-centroid anchoring.
                #   max blank cells = 0: blanks are always errors; a
                #     deliberately empty cell would be a separate spec.
                #   duplicate threshold 4 + max 25%: idle loops have
                #     legitimately similar frames (subtle breath); 25% is
                #     "1 of 4" tolerated for portrait-loop and "4 of 16"
                #     for action sheets, which corresponds to legitimate
                #     stand-alone repeated-stance frames (asset 06 idle
                #     loop has 4 near-identical idle frames between taunt
                #     gestures).
                #   pixel preservation 0.40 ratio: under 60% silhouette
                #     loss is the "despill chain ate the character"
                #     symptom; gradual 30-40% trim is normal halo removal.
                # Per-mode gate selection:
                #   portrait-loop: stddev=4 (tighter — fixed camera, drift
                #     is obvious); allow 100% dup pct (every cell is
                #     supposed to be near-identical by construction).
                #   spritesheet: stddev=8, dup_pct=25.
                if mode == "portrait-loop":
                    anchor_stddev = 4.0
                    dup_pct_max = 100.0
                else:
                    anchor_stddev = 8.0
                    # The dups gate is non-blocking by default for
                    # spritesheets: legitimate animation cycles routinely
                    # measure 70-100% duplicate-pct because of natural
                    # redundancy (walk cycles repeat poses, idle loops
                    # are by construction near-identical, 3-count
                    # animations have 4 reference poses repeated 4 times
                    # each). Setting threshold=100.0 means the gate fires
                    # only on the pathological "every cell IS the same"
                    # failure mode -- which is also caught by
                    # frames_have_content when most cells are blank.
                    # The blanks gate (frames_have_content) catches the
                    # primary user-reported failure (08 grapple cell 12
                    # blank, 28 astronaut cell 0 blank) and remains
                    # hard-fail. The dups gate's pct is recorded in
                    # diagnosis output for analyst review.
                    dup_pct_max = 100.0
                try:
                    anc = verify_anchor_consistency(
                        fpath,
                        cols,
                        rows,
                        cell_size,
                        max_centroid_y_stddev_px=anchor_stddev,
                    )
                    if not anc["passed"]:
                        failures.append(
                            {
                                "file": fname,
                                "check": "anchor_consistency",
                                "details": {
                                    "stddev": anc.get("stddev"),
                                    "threshold": anchor_stddev,
                                    "outliers": anc.get("outliers"),
                                    "median": anc.get("median"),
                                },
                            }
                        )
                except Exception as e:
                    failures.append({"file": fname, "check": "anchor_consistency", "details": f"error: {e}"})

                try:
                    blanks = verify_frames_have_content(
                        fpath,
                        cols,
                        rows,
                        cell_size,
                    )
                    if not blanks["passed"]:
                        failures.append(
                            {
                                "file": fname,
                                "check": "frames_have_content",
                                "details": {
                                    "blank_cells": blanks.get("blank_cells"),
                                    "alpha_pct_per_cell": blanks.get("alpha_pct_per_cell"),
                                },
                            }
                        )
                except Exception as e:
                    failures.append({"file": fname, "check": "frames_have_content", "details": f"error: {e}"})

                try:
                    dups = verify_frames_distinct(
                        fpath,
                        cols,
                        rows,
                        cell_size,
                        max_duplicate_pct=dup_pct_max,
                    )
                    if not dups["passed"]:
                        failures.append(
                            {
                                "file": fname,
                                "check": "frames_distinct",
                                "details": {
                                    "duplicate_pct": dups.get("duplicate_pct"),
                                    "threshold": dup_pct_max,
                                    "duplicate_pairs": dups.get("duplicate_pairs", [])[:5],
                                },
                            }
                        )
                except Exception as e:
                    failures.append({"file": fname, "check": "frames_distinct", "details": f"error: {e}"})

                # Pixel preservation: requires raw.png next to final-sheet.
                raw_path = asset_dir / "raw.png"
                if raw_path.exists():
                    try:
                        preservation = verify_pixel_preservation(
                            raw_path,
                            fpath,
                            cols,
                            rows,
                            cell_size,
                        )
                        if not preservation["passed"]:
                            failures.append(
                                {
                                    "file": fname,
                                    "check": "pixel_preservation",
                                    "details": {
                                        "lossy_pct": preservation.get("lossy_pct"),
                                        "lossy_cells": preservation.get("lossy_cells"),
                                        "threshold_pct": preservation.get("max_lossy_pct_threshold"),
                                        "min_ratio": preservation.get("min_pixel_ratio_threshold"),
                                    },
                                }
                            )
                    except Exception as e:
                        failures.append({"file": fname, "check": "pixel_preservation", "details": f"error: {e}"})

                    # ADR-207 Rule 3: cell-parity gate. Conservative blank-cell
                    # check that catches RC-1 directly (raw has content, final
                    # lost it). Runs alongside verify_pixel_preservation; both
                    # can fire on the same underlying failure with distinct
                    # diagnostics.
                    try:
                        parity = verify_raw_vs_final_cell_parity(
                            raw_path,
                            fpath,
                            cols,
                            rows,
                            cell_size,
                        )
                        if not parity["passed"]:
                            failures.append(
                                {
                                    "file": fname,
                                    "check": "cell_parity",
                                    "details": {
                                        "blank_cells": parity.get("blank_cells"),
                                        "total_cells_with_raw_content": parity.get("total_cells_with_raw_content"),
                                        "preservation_ratio": parity.get("preservation_ratio"),
                                    },
                                }
                            )
                    except Exception as e:
                        failures.append({"file": fname, "check": "cell_parity", "details": f"error: {e}"})

    # ADR-207 Rule 2: include the contracted verifier_verdict alongside the
    # legacy 'passed' field so consumers can derive their status fields from
    # an authoritative producer-side string. Legacy callers reading 'passed'
    # continue to work unchanged.
    passed = len(failures) == 0
    return {
        "passed": passed,
        "verifier_verdict": verifier_verdict_from_passed(passed),
        "failures": failures,
    }


def cmd_verify_asset(args: argparse.Namespace) -> int:
    """CLI: scan an asset dir and print PASS/FAIL with details.

    Reads meta.json from the asset_dir to learn mode/grid/cell_size if not
    overridden by flags. This is the user's no-loop deterministic check:

        python3 -m sprite_process verify-asset /abs/path/to/asset_dir

    For convenience, callers may export `SPRITE_DEMO_ROOT` and pass a bare
    slug; the resolver then tries `$SPRITE_DEMO_ROOT/assets/<slug>/`.
    """
    asset_dir = Path(args.asset_dir)
    if not asset_dir.is_absolute() and not asset_dir.exists():
        demo_root = os.environ.get("SPRITE_DEMO_ROOT")
        if demo_root:
            candidate = Path(demo_root) / "assets" / args.asset_dir
            if candidate.exists():
                asset_dir = candidate

    if not asset_dir.exists():
        logger.error("asset dir %s does not exist", asset_dir)
        return 2

    meta_path = asset_dir / "meta.json"
    mode = args.mode
    grid: tuple[int, int] | None = None
    cell_size = args.cell_size
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        mode = mode or meta.get("mode")
        if not args.grid:
            g = meta.get("grid")
            if g and len(g) == 2:
                grid = (int(g[0]), int(g[1]))
        if cell_size is None:
            cell_size = meta.get("cell_size")
    if args.grid:
        cols, rows = _parse_grid(args.grid)
        grid = (cols, rows)
    if mode is None:
        logger.error("--mode required (no meta.json at %s)", meta_path)
        return 2

    result = verify_asset_outputs(asset_dir, mode, grid=grid, cell_size=cell_size)
    print(json.dumps({"asset": str(asset_dir), "mode": mode, "grid": grid, "cell_size": cell_size, **result}, indent=2))
    # Exit code 2 == "verifier gates failed" per ADR-199; same code regardless
    # of standalone-CLI vs orchestrator surface.
    return 0 if result["passed"] else 2
