#!/usr/bin/env python3
"""sprite_process — backward-compatibility shim (ADR-205).

The 3,350-LOC implementation that used to live here has been split into
five cohesive modules:

    sprite_bg.py        Chroma-key + despill + bg-removal pixel logic.
    sprite_slicing.py   Grid + content-aware slicers + connected-components.
    sprite_anchor.py    Bbox + ground-line + mass-centroid anchor math.
    sprite_assemble.py  Variant ranking + multi-format output assembly.
    sprite_verify.py    Six deterministic verifier gates + asset runner.

This shim re-exports the public surface of those modules so existing
`from sprite_process import X` (and `sprite_process.X` attribute) callers
keep working. New code should import from the canonical module
(sprite_bg, sprite_slicing, sprite_anchor, sprite_assemble, sprite_verify).

This file also owns the `main()` + `build_parser()` CLI entry points,
because external callers (sprite_pipeline.py, portrait_pipeline.py,
test_pipeline_glue.py) invoke `sprite_process.main([...])` directly.

Subcommands:
    extract-frames      Phase D: connected-components frame detection
    remove-bg           Phase B (portrait) or Phase E (sheet): magenta chroma key
    normalize           Phase C (portrait) or Phase F (sheet): trim/scale/anchor
    validate-portrait   Phase D (portrait): width/height/aspect gate
    contact-sheet       Build a contact-sheet image from variant directories
    auto-curate         Phase G: deterministic ranking of variants
    assemble            Phase H: PNG sheet + GIF + WebP + atlas + strips
    verify-asset        Run every verifier on an asset dir
"""

from __future__ import annotations

import argparse
import sys

# Re-export numpy availability flag so callers can branch on it. Read from
# any of the new modules; all five compute it identically.
from sprite_anchor import (
    DEFAULT_BOTTOM_MARGIN,
    PORTRAIT_ASPECT_MAX,
    PORTRAIT_ASPECT_MIN,
    PORTRAIT_HEIGHT_RANGE,
    PORTRAIT_WIDTH_RANGE,
    anchor_to_canvas,
    apply_ground_line_anchor,
    apply_mass_centroid_anchor,
    cmd_normalize,
    cmd_validate_portrait,
    detect_centroid_y_target,
    detect_ground_line,
    find_alpha_bbox,
    find_alpha_mass_centroid,
    find_bottom_anchor,
    normalize_portrait,
    normalize_spritesheet,
    rescale_to_height,
    shared_scale_height,
    trim_to_bbox,
)
from sprite_assemble import (
    VariantStats,
    _compute_variant_stats,
    assemble_outputs,
    cmd_assemble,
    cmd_auto_curate,
    cmd_contact_sheet,
)
from sprite_bg import (
    BG_MODE_CHOICES,
    DEFAULT_ALPHA_DILATE_RADIUS,
    DEFAULT_CHROMA_THRESHOLD,
    DEFAULT_DESPILL_STRENGTH,
    DEFAULT_GIF_FPS,
    DEFAULT_MIN_COMPONENT_PIXELS,
    DEFAULT_PASS2_THRESHOLD,
    GRAY_BG_DEFAULT,
    GRAY_BG_TOLERANCE_DEFAULT,
    HAS_NUMPY,
    MAGENTA,
    WATERMARK_BRIGHTNESS_THRESHOLD,
    WATERMARK_MARGIN_DEFAULT,
    _alpha_coverage_too_low,
    _bg_mode_from_legacy,
    alpha_fade_magenta_fringe,
    chroma_pass1,
    chroma_pass2_edge_flood,
    cmd_remove_bg,
    color_despill_magenta,
    dilate_alpha_zero,
    gray_tolerance_to_alpha,
    kill_pink_fringe,
    matte_composite,
    neutralize_interior_magenta_spill,
    remove_bg_chroma,
    remove_bg_gray_tolerance,
    remove_bg_rembg,
    remove_watermark_corners,
)
from sprite_slicing import (
    _FIRE_DEFAULT_RGB,
    Component,
    _is_fire,
    _label_components_bfs,
    _parse_grid,
    _preserve_fire_pixels,
    assign_components_to_cells,
    cmd_extract_frames,
    extract_components,
    label_components_numpy,
    slice_grid_cells,
    slice_with_content_awareness,
)
from sprite_verify import (
    _dhash,
    _hamming,
    _slice_grid_into_cells,
    cmd_verify_asset,
    verify_anchor_consistency,
    verify_asset_outputs,
    verify_frames_distinct,
    verify_frames_have_content,
    verify_grid_alignment,
    verify_no_magenta,
    verify_pixel_preservation,
)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    rb = sub.add_parser("remove-bg", help="Remove background (magenta chroma key default)")
    rb.add_argument("input", nargs="+", help="Input PNG path(s)")
    rb.add_argument("--output", help="Output path (single input)")
    rb.add_argument("--output-dir", help="Output directory (multi-input)")
    # Legacy --mode kept for backward compat with the pipeline orchestrator.
    rb.add_argument("--mode", choices=["chroma", "rembg", "auto"], default="chroma")
    # New canonical flag. magenta = the default two-pass despill chroma key.
    # gray-tolerance = road-to-aew's algorithm for backends that paint #3a3a3a.
    rb.add_argument(
        "--bg-mode",
        choices=list(BG_MODE_CHOICES),
        default=None,
        help="Background removal strategy. magenta=despill chroma; gray-tolerance=road-to-aew #3a3a3a algorithm.",
    )
    rb.add_argument("--chroma-threshold", type=int, default=DEFAULT_CHROMA_THRESHOLD)
    rb.add_argument(
        "--pass2-threshold",
        type=int,
        default=DEFAULT_PASS2_THRESHOLD,
        help="Pass-2 edge-flood threshold (default 90; despill protects character pixels).",
    )
    rb.add_argument(
        "--despill-strength",
        type=float,
        default=DEFAULT_DESPILL_STRENGTH,
        help="Despill strength for pass 2 (0=off; 1.0=aggressive preserve).",
    )
    rb.add_argument(
        "--alpha-dilate",
        type=int,
        default=DEFAULT_ALPHA_DILATE_RADIUS,
        help="Pixel radius for alpha-zero dilation after chroma key (kills 1-px halo).",
    )
    rb.add_argument(
        "--gray-bg",
        type=int,
        nargs=3,
        default=list(GRAY_BG_DEFAULT),
        metavar=("R", "G", "B"),
        help="Background RGB for --bg-mode gray-tolerance (default 58 58 58).",
    )
    rb.add_argument(
        "--gray-tolerance",
        type=int,
        default=GRAY_BG_TOLERANCE_DEFAULT,
        help="Per-channel tolerance for gray-tolerance mode (default 30).",
    )
    rb.add_argument(
        "--watermark-margin",
        type=int,
        default=WATERMARK_MARGIN_DEFAULT,
        help="Corner box size (px) cleaned of bright pixels before gray-tolerance masking.",
    )
    rb.set_defaults(func=cmd_remove_bg)

    ef = sub.add_parser("extract-frames", help="Phase D: connected-components frame detection")
    ef.add_argument("--input", required=True, help="Spritesheet PNG path")
    ef.add_argument("--grid", required=True, help="Expected grid CxR (e.g., 4x4)")
    ef.add_argument("--output-dir", required=True, help="Where to write frame PNGs")
    ef.add_argument("--name", help="Frame name prefix (default: input stem)")
    ef.add_argument("--chroma-threshold", type=int, default=DEFAULT_CHROMA_THRESHOLD)
    ef.add_argument("--min-pixels", type=int, default=DEFAULT_MIN_COMPONENT_PIXELS)
    ef.add_argument("--cell-aware", action="store_true", default=True, help="Map components to cells via centroid")
    ef.add_argument("--allow-count-mismatch", action="store_true", help="Tolerate component count != grid")
    ef.add_argument(
        "--content-aware",
        action="store_true",
        help=(
            "Use slice_with_content_awareness instead of connected-components. "
            "Required for assets with effects (fire, projectiles) where content "
            "crosses conceptual cell boundaries. Codex is ground truth; clipping "
            "is a post-processing bug. See references/error-catalog.md."
        ),
    )
    ef.add_argument("--cell-size", type=int, default=256, help="Output cell size when --content-aware (default 256)")
    ef.add_argument(
        "--max-expansion-pct",
        type=float,
        default=0.30,
        help="Max content-aware expansion past cell pitch as a fraction (default 0.30 = 30%%).",
    )
    ef.set_defaults(func=cmd_extract_frames)

    nz = sub.add_parser("normalize", help="Trim/scale/anchor")
    nz.add_argument("--mode", choices=["portrait", "spritesheet"], required=True)
    nz.add_argument("--input", help="Input image (portrait mode)")
    nz.add_argument("--input-dir", help="Input directory of frames (spritesheet mode)")
    nz.add_argument("--output", help="Output path (portrait)")
    nz.add_argument("--output-dir", help="Output directory (spritesheet)")
    nz.add_argument("--target-w", type=int, default=600)
    nz.add_argument("--target-h", type=int, default=980)
    nz.add_argument("--cell-size", type=int, default=256)
    nz.add_argument("--scale-percentile", type=float, default=95)
    nz.add_argument(
        "--anchor-mode",
        choices=["bottom", "center", "auto", "ground-line", "per-frame-bottom"],
        default="ground-line",
        help=(
            "Anchor strategy. ground-line (default): each frame's "
            "alpha-bbox-bottom lands at a globally-stable ground-Y; "
            "drift-free across mixed grounded/aerial poses. "
            "per-frame-bottom (alias: bottom): legacy per-frame anchor "
            "(drifts when bbox heights vary). center: vertical center. "
            "auto: heuristic legacy fallback."
        ),
    )
    nz.set_defaults(func=cmd_normalize)

    vp = sub.add_parser("validate-portrait", help="Phase D portrait dimension gate")
    vp.add_argument("input", help="Portrait PNG path")
    vp.add_argument("--force", action="store_true", dest="force", help="Skip the gate (logs warning)")
    vp.set_defaults(func=cmd_validate_portrait)

    cs = sub.add_parser("contact-sheet", help="Build a variant contact sheet image")
    cs.add_argument("--variants-dir", required=True, help="Directory containing variant_NNN/ subdirs")
    cs.add_argument("--output", required=True, help="Output contact sheet PNG")
    cs.add_argument("--cols", type=int, default=4)
    cs.add_argument("--thumb-size", type=int, default=256)
    cs.set_defaults(func=cmd_contact_sheet)

    ac = sub.add_parser("auto-curate", help="Phase G: deterministic ranking of variants")
    ac.add_argument("--variants-dir", required=True)
    ac.add_argument("--output", required=True, help="Where to write ranking JSON")
    ac.set_defaults(func=cmd_auto_curate)

    va = sub.add_parser(
        "verify-asset",
        help="Verify an asset dir's outputs (deterministic build-time gate).",
    )
    va.add_argument("asset_dir", help="Path to asset dir (or slug under /tmp/sprite-demo/assets/)")
    va.add_argument("--mode", choices=["portrait", "portrait-loop", "spritesheet"])
    va.add_argument("--grid", help="Grid CxR (overrides meta.json)")
    va.add_argument("--cell-size", type=int, help="Cell size in px (overrides meta.json)")
    va.set_defaults(func=cmd_verify_asset)

    ab = sub.add_parser("assemble", help="Phase H: PNG sheet + GIF + WebP + atlas + strips")
    ab.add_argument("--frames-dir", required=True)
    ab.add_argument("--grid", required=True)
    ab.add_argument("--cell-size", type=int, default=256)
    ab.add_argument("--output-dir", required=True)
    ab.add_argument("--name")
    ab.add_argument("--fps", type=int, default=DEFAULT_GIF_FPS)
    ab.add_argument("--no-strips", action="store_true", help="Skip per-direction strips")
    ab.set_defaults(func=cmd_assemble)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
