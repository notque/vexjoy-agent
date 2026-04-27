#!/usr/bin/env python3
"""
Spritesheet-mode end-to-end orchestrator (Phases A-H).

Chains:
    A: reference character generation
    B: canvas template
    C: spritesheet generation
    D: connected-components frame extraction
    E: per-frame bg removal
    F: shared-scale + bottom-anchor normalization
    G: deterministic auto-curation (when --variants > 1)
    H: PNG sheet + GIF + WebP + Phaser atlas + per-direction strips

Usage:
    python3 sprite_pipeline.py \\
        --prompt "wrestler walk cycle, 4 frames" \\
        --grid 4x1 --cell-size 256 --action walking \\
        --style slay-the-spire-painted

--dry-run skips Phase A and C backend calls; uses a synthetic fixture
spritesheet for Phase D-H validation. Useful for CI smoke tests.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("sprite-pipeline.sprite_pipeline")

try:
    from PIL import Image, ImageDraw
except ImportError as e:
    logger.error("Pillow not installed: %s", e)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import sprite_bg
import sprite_canvas
import sprite_generate
import sprite_process
import sprite_prompt
from sprite_verify import (
    verifier_verdict_from_passed,
    verify_anchor_consistency,
    verify_frames_distinct,
    verify_frames_have_content,
    verify_grid_alignment,
    verify_no_magenta,
    verify_pixel_preservation,
    verify_raw_vs_final_cell_parity,
    write_manifest_record,
)

# Exit code emitted by run_pipeline / run_portrait_loop when --verify is on
# and at least one gate fails. Distinct from the generic pipeline-error rc=1
# so road-to-aew CI can branch on "verifier said no" vs "the pipeline blew
# up". Locked by ADR-199 ("Exit code: 0 when passed: true, 2 when any gate
# fails").
VERIFIER_EXIT_CODE = 2

# ADR-207 Rule 4: spritesheet-mode --no-verify returns a distinct non-zero
# exit code so orchestrators cannot silently mask spritesheet failures with
# the same exit status as success. Portrait and portrait-loop modes retain
# --no-verify -> exit 0 because their verifier surface is small enough
# (verify_no_magenta only) that an explicit skip is plausibly intentional.
VERIFIER_SKIPPED_EXIT_CODE = 3

# TODO(ADR-207 RC-4 follow-up): audit every consumer of `--no-verify` for
# spritesheet mode and migrate them to either accept exit code 3 or drop
# `--no-verify` entirely. The street-fighter-demo orchestrator was the
# only known consumer at ship time and is updated in this same wave. Other
# consumers may exist in road-to-aew CI or external scripts; tracked as an
# RC-4 follow-up.

# TODO(ADR-207 RC-5 follow-up): the reverify-after-reprocess pattern is
# implemented as a separate helper script in the street-fighter-demo repo
# (`scripts/reverify_after_reprocess.py`). A toolkit-level helper that any
# consumer can import would centralize the contract. Tracked as an RC-5
# follow-up; not in scope for ADR-207.


def _detect_backends_available() -> dict[str, bool]:
    """Best-effort backend availability for the verifier failure JSON.

    ADR-198 governs the Codex -> Nano Banana fallback chain. The verifier
    surfaces what's available so failure hints can recommend "try the other
    backend" as an actionable fix path. We avoid invoking ``select_backend``
    here because that runs ``codex --version`` and we do not want a
    verifier emission to spawn a subprocess; cheap shutil/env checks are
    enough for the JSON context field.
    """
    nano_script = sprite_generate.find_nano_banana_script()
    return {
        "codex": shutil.which("codex") is not None,
        "nano_banana": nano_script is not None
        and bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
    }


def _emit_verifier_result(
    gates_run: list[str],
    failures: list[dict],
    elapsed_seconds: float,
) -> int:
    """Print the structured verifier JSON to stdout and return the exit code.

    Per ADR-199, verifier output goes to stdout (not stderr, not a logger
    call) so callers can pipe pipeline runs and parse the last JSON block.
    Schema mirrors the ADR contract:

        {
          "passed": bool,
          "gates_run": [gate_name, ...],
          "failures": [{check, file?, details, ...}, ...],
          "backends_available": {"codex": bool, "nano_banana": bool},
          "elapsed_seconds": float,
        }

    Returns ``VERIFIER_EXIT_CODE`` (2) when any gate fails; 0 otherwise.

    ADR-207 Rule 2: ``verifier_verdict`` ("PASS"|"FAIL") is added as the
    consumer-facing contract field. Consumers (orchestrators, manifest
    writers) MUST derive their own status fields from this, not from any
    other heuristic.
    """
    passed = len(failures) == 0
    payload = {
        "passed": passed,
        "verifier_verdict": verifier_verdict_from_passed(passed),
        "gates_run": gates_run,
        "failures": failures,
        "backends_available": _detect_backends_available(),
        "elapsed_seconds": round(elapsed_seconds, 3),
    }
    print(json.dumps(payload, indent=2))
    return 0 if passed else VERIFIER_EXIT_CODE


def _run_spritesheet_verifiers(
    sheet_path: Path,
    raw_path: Path | None,
    cols: int,
    rows: int,
    cell_size: int,
    allow_frame_duplication: bool = False,
) -> tuple[list[str], list[dict]]:
    """Run the spritesheet gate suite against a final sheet PNG.

    Gates (per ADR-199 spritesheet contract):
      - verify_no_magenta
      - verify_grid_alignment
      - verify_anchor_consistency
      - verify_frames_have_content
      - verify_frames_distinct
      - verify_pixel_preservation (only if ``raw_path`` is supplied)

    Each gate is best-effort isolated: a single gate raising or returning
    ``error`` does not prevent the others from running. The caller hard-fails
    on any non-empty failures list.
    """
    gates_run: list[str] = []
    failures: list[dict] = []

    def _record_gate(name: str, result: dict) -> None:
        gates_run.append(name)
        if not result.get("passed", True):
            failures.append({"check": name, "file": str(sheet_path), "details": result})

    try:
        _record_gate("verify_no_magenta", verify_no_magenta(sheet_path))
    except Exception as e:  # pragma: no cover - defensive
        gates_run.append("verify_no_magenta")
        failures.append({"check": "verify_no_magenta", "file": str(sheet_path), "details": f"error: {e}"})

    try:
        _record_gate(
            "verify_grid_alignment",
            verify_grid_alignment(sheet_path, rows, cols, cell_size),
        )
    except Exception as e:  # pragma: no cover - defensive
        gates_run.append("verify_grid_alignment")
        failures.append({"check": "verify_grid_alignment", "file": str(sheet_path), "details": f"error: {e}"})

    try:
        _record_gate(
            "verify_anchor_consistency",
            verify_anchor_consistency(sheet_path, cols, rows, cell_size),
        )
    except Exception as e:  # pragma: no cover - defensive
        gates_run.append("verify_anchor_consistency")
        failures.append({"check": "verify_anchor_consistency", "file": str(sheet_path), "details": f"error: {e}"})

    try:
        _record_gate(
            "verify_frames_have_content",
            verify_frames_have_content(sheet_path, cols, rows, cell_size),
        )
    except Exception as e:  # pragma: no cover - defensive
        gates_run.append("verify_frames_have_content")
        failures.append({"check": "verify_frames_have_content", "file": str(sheet_path), "details": f"error: {e}"})

    try:
        # ADR-208 RC-3: dup_pct_max defaults to 70.0 for spritesheets;
        # opt-out via --allow-frame-duplication relaxes to 100.0 for
        # legitimate idle loops + 8-frame anims tiled across 64 cells.
        dup_pct_max = 100.0 if allow_frame_duplication else 70.0
        _record_gate(
            "verify_frames_distinct",
            verify_frames_distinct(sheet_path, cols, rows, cell_size, max_duplicate_pct=dup_pct_max),
        )
    except Exception as e:  # pragma: no cover - defensive
        gates_run.append("verify_frames_distinct")
        failures.append({"check": "verify_frames_distinct", "file": str(sheet_path), "details": f"error: {e}"})

    if raw_path is not None and raw_path.exists():
        try:
            _record_gate(
                "verify_pixel_preservation",
                verify_pixel_preservation(raw_path, sheet_path, cols, rows, cell_size),
            )
        except Exception as e:  # pragma: no cover - defensive
            gates_run.append("verify_pixel_preservation")
            failures.append({"check": "verify_pixel_preservation", "file": str(sheet_path), "details": f"error: {e}"})

        # ADR-207 Rule 3: cell-parity gate. Conservative blank-cell check
        # that catches RC-1 directly (raw has content, final lost it). Runs
        # alongside verify_pixel_preservation; both can fire on the same
        # underlying failure with distinct diagnostics (parity surfaces the
        # blank-cell symptom; preservation surfaces the silhouette-loss
        # symptom).
        try:
            _record_gate(
                "verify_raw_vs_final_cell_parity",
                verify_raw_vs_final_cell_parity(raw_path, sheet_path, cols, rows, cell_size),
            )
        except Exception as e:  # pragma: no cover - defensive
            gates_run.append("verify_raw_vs_final_cell_parity")
            failures.append(
                {"check": "verify_raw_vs_final_cell_parity", "file": str(sheet_path), "details": f"error: {e}"}
            )

    return gates_run, failures


FIXTURE_COLORS = [
    (220, 60, 60, 255),
    (60, 180, 60, 255),
    (60, 100, 220, 255),
    (220, 180, 40, 255),
    (180, 60, 220, 255),
    (60, 200, 200, 255),
    (240, 140, 60, 255),
    (140, 60, 200, 255),
]


def _make_fixture_sheet(output: Path, cols: int, rows: int, cell: int) -> None:
    """Synthesize a magenta-bg sheet with one colored figure per cell."""
    img = Image.new("RGBA", (cols * cell, rows * cell), (255, 0, 255, 255))
    draw = ImageDraw.Draw(img)
    idx = 0
    for r in range(rows):
        for c in range(cols):
            color = FIXTURE_COLORS[idx % len(FIXTURE_COLORS)]
            cx = c * cell + cell // 2
            cy_top = r * cell + cell // 5
            cy_bot = r * cell + (cell * 4) // 5
            # head
            head_r = cell // 8
            draw.ellipse(
                (cx - head_r, cy_top, cx + head_r, cy_top + 2 * head_r),
                fill=color,
                outline=(20, 20, 20, 255),
                width=3,
            )
            # body
            body_w = cell // 4
            draw.rectangle(
                (cx - body_w // 2, cy_top + 2 * head_r, cx + body_w // 2, cy_bot),
                fill=color,
                outline=(20, 20, 20, 255),
                width=3,
            )
            idx += 1
    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, format="PNG")


def _run_pipeline_body(args: argparse.Namespace, work_dir: Path, name: str) -> int:
    """Pipeline body. ``work_dir`` lifetime is bounded by the caller.

    When ``--output-dir`` is unset the caller wraps this in a
    ``tempfile.TemporaryDirectory`` and the directory is reaped on exit
    (success, exception, or KeyboardInterrupt). When ``--output-dir`` is
    set the user owns the directory and intermediates persist for
    inspection. See ADR-200.
    """
    work_dir.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc)
    phases: list[dict] = []

    if args.max_frames:
        try:
            r, c = sprite_canvas.compute_max_grid(args.cell_size, args.max_canvas)
        except ValueError as e:
            logger.error("%s", e)
            return 2
        cols, rows = c, r
        args.grid = f"{cols}x{rows}"
        logger.info(
            "[pipeline] --max-frames: auto-grid %dx%d = %d frames @ %dpx on %dx%d canvas",
            cols,
            rows,
            cols * rows,
            args.cell_size,
            args.max_canvas,
            args.max_canvas,
        )
    else:
        cols, rows = sprite_prompt.parse_grid(args.grid)

    # Density warning: image-gen models cannot reliably keep characters within
    # cells when the per-cell budget shrinks below ~128px and the grid is
    # dense. See references/frame-detection.md "Grid density limits".
    total_frames = cols * rows
    if total_frames > 64 and not args.confirm_dense_grid:
        logger.warning(
            "grid %dx%d=%d frames is dense; per-cell frame extraction may drift. "
            "Consider 8x8 or smaller. Set --confirm-dense-grid to suppress this warning.",
            cols,
            rows,
            total_frames,
        )

    # Phase A: reference character (skipped in dry-run, optional otherwise)
    char_prompt_path = work_dir / f"{name}_char_prompt.txt"
    char_ref_path = work_dir / f"{name}_reference.png"
    if not args.skip_reference:
        char_argv = [
            "build-character",
            "--style",
            args.style,
            "--description",
            args.description or args.prompt or "",
            "--seed",
            str(args.seed),
            "--output",
            str(char_prompt_path),
        ]
        if args.archetype:
            char_argv.extend(["--archetype", args.archetype])
        if args.gimmick:
            char_argv.extend(["--gimmick", args.gimmick])
        if args.style_string:
            char_argv.extend(["--style-string", args.style_string])
        rc = sprite_prompt.main(char_argv)
        if rc != 0:
            return rc
        if not args.dry_run:
            rc = sprite_generate.main(
                [
                    "generate-character",
                    "--prompt-file",
                    str(char_prompt_path),
                    "--output",
                    str(char_ref_path),
                    "--seed",
                    str(args.seed),
                ]
            )
            if rc != 0:
                return rc
        phases.append({"phase": "A", "name": "reference-character", "rc": 0, "dry_run": args.dry_run})

    # Phase B: canvas template
    canvas_path = work_dir / f"{name}_canvas.png"
    rc = sprite_canvas.main(
        [
            "make-template",
            "--rows",
            str(rows),
            "--cols",
            str(cols),
            "--cell-size",
            str(args.cell_size),
            "--pattern",
            args.pattern,
            "--output",
            str(canvas_path),
        ]
    )
    if rc != 0:
        return rc
    phases.append({"phase": "B", "name": "canvas", "rc": rc})

    # Phase C: spritesheet generation
    sheet_prompt_path = work_dir / f"{name}_sheet_prompt.txt"
    sheet_raw_path = work_dir / f"{name}_sheet_raw.png"
    sheet_argv = [
        "build-spritesheet",
        "--style",
        args.style,
        "--description",
        args.description or args.prompt or "",
        "--grid",
        args.grid,
        "--action",
        args.action,
        "--seed",
        str(args.seed),
        "--output",
        str(sheet_prompt_path),
    ]
    if args.archetype:
        sheet_argv.extend(["--archetype", args.archetype])
    if args.gimmick:
        sheet_argv.extend(["--gimmick", args.gimmick])
    if args.style_string:
        sheet_argv.extend(["--style-string", args.style_string])
    rc = sprite_prompt.main(sheet_argv)
    if rc != 0:
        return rc

    if args.dry_run:
        _make_fixture_sheet(sheet_raw_path, cols, rows, args.cell_size)
        phases.append({"phase": "C", "name": "generate-sheet", "rc": 0, "dry_run": True})
    else:
        rc = sprite_generate.main(
            [
                "generate-spritesheet",
                "--prompt-file",
                str(sheet_prompt_path),
                "--output",
                str(sheet_raw_path),
                "--canvas",
                str(canvas_path),
                "--reference",
                str(char_ref_path) if char_ref_path.exists() else str(canvas_path),
                "--seed",
                str(args.seed),
            ]
        )
        if rc != 0:
            return rc
        phases.append({"phase": "C", "name": "generate-sheet", "rc": rc})

    # Phase D: extract frames
    frames_raw_dir = work_dir / "frames_raw"
    extract_args = [
        "extract-frames",
        "--input",
        str(sheet_raw_path),
        "--grid",
        args.grid,
        "--output-dir",
        str(frames_raw_dir),
        "--name",
        name,
        "--chroma-threshold",
        str(args.chroma_threshold),
        "--min-pixels",
        str(args.min_pixels),
    ]
    # ADR-207 Rule 1: dense grids (>= 4x4 with >= 16 cells) ALWAYS use the
    # slicer dispatch path, never the legacy connected-components extractor.
    # The dispatch routes to strict-pitch by default; --effects-asset opts
    # into content-aware (correct only for sparse-but-cross-boundary content
    # like fire breath / plasma trails / auras). The deprecation warning
    # below fires when the user explicitly passed --content-aware-extraction
    # for a dense grid -- the flag is silently downgraded to strict-pitch
    # at the sprite_process layer; this log explains WHY.
    from sprite_slicing import is_dense_grid

    grid_is_dense = is_dense_grid(cols, rows)
    use_effects_asset = getattr(args, "effects_asset", False)
    legacy_content_aware = getattr(args, "content_aware_extraction", False)
    if grid_is_dense:
        # Dispatch through the slicer surface always.
        extract_args.append("--content-aware")
        if use_effects_asset:
            extract_args.append("--effects-asset")
        if legacy_content_aware and not use_effects_asset:
            logger.warning(
                "[pipeline] --content-aware-extraction on dense grid %dx%d is "
                "deprecated per ADR-207 RC-1; the slicer dispatch will downgrade "
                "to strict-pitch. Pass --effects-asset to explicitly opt into "
                "content-aware (correct only for sparse-but-cross-boundary "
                "content like fire breath / plasma trails / auras).",
                cols,
                rows,
            )
    elif legacy_content_aware:
        # Sparse grid: content-aware is fine; pass through.
        extract_args.append("--content-aware")
        if use_effects_asset:
            extract_args.append("--effects-asset")
    rc = sprite_process.main(extract_args)
    if rc != 0:
        return rc
    phases.append({"phase": "D", "name": "extract-frames", "rc": rc})

    # Phase E: per-frame bg removal
    frames_nobg_dir = work_dir / "frames_nobg"
    raw_frames = sorted(frames_raw_dir.glob("*_frame_*.png"))
    if not raw_frames:
        logger.error("no frames extracted in Phase D")
        return 5
    # ADR-204: pass through pipeline-level --bg-mode to sprite_process's
    # canonical --bg-mode flag. Both surfaces share BG_MODE_CHOICES so the
    # value passes through unchanged.
    rb_argv: list[str] = [
        "remove-bg",
        *(str(f) for f in raw_frames),
        "--output-dir",
        str(frames_nobg_dir),
        "--bg-mode",
        args.bg_mode,
        "--chroma-threshold",
        str(args.chroma_threshold),
    ]
    rc = sprite_process.main(rb_argv)
    if rc != 0:
        return rc
    phases.append({"phase": "E", "name": "remove-bg", "rc": rc, "mode": args.bg_mode})

    # Phase F: normalize
    frames_norm_dir = work_dir / "frames_normalized"
    rc = sprite_process.main(
        [
            "normalize",
            "--mode",
            "spritesheet",
            "--input-dir",
            str(frames_nobg_dir),
            "--output-dir",
            str(frames_norm_dir),
            "--cell-size",
            str(args.cell_size),
            "--scale-percentile",
            str(args.scale_percentile),
            "--anchor-mode",
            args.anchor_mode,
        ]
    )
    if rc != 0:
        return rc
    phases.append({"phase": "F", "name": "normalize", "rc": rc})

    # Phase G: skipped when variants == 1
    if args.variants > 1:
        phases.append({"phase": "G", "name": "auto-curate", "rc": 0, "note": "variants > 1 not yet wired in dry-run"})

    # Phase H: assembly
    assemble_argv = [
        "assemble",
        "--frames-dir",
        str(frames_norm_dir),
        "--grid",
        args.grid,
        "--cell-size",
        str(args.cell_size),
        "--output-dir",
        str(work_dir / "out"),
        "--name",
        name,
        "--fps",
        str(args.fps),
    ]
    if args.no_strips:
        assemble_argv.append("--no-strips")
    rc = sprite_process.main(assemble_argv)
    if rc != 0:
        return rc
    phases.append({"phase": "H", "name": "assemble", "rc": rc})

    # Metadata
    sidecar = {
        "name": name,
        "grid": [cols, rows],
        "cell_size": args.cell_size,
        "action": args.action,
        "style_preset": args.style,
        "archetype": args.archetype,
        "seed": args.seed,
        "dry_run": args.dry_run,
        "started_at": started.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "phases": phases,
        "output_dir": str(work_dir / "out"),
    }
    (work_dir / f"{name}_metadata.json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

    logger.info(
        "[spritesheet] PASS: %s written to %s (phases: %d)",
        name,
        work_dir / "out",
        len(phases),
    )

    # Phase I: verifier gates (ADR-199). Default-on; opt out with --no-verify.
    # Gates run on the assembled sheet at work_dir/out/{name}_sheet.png while
    # the work dir is still in scope (ADR-200 requires gates to fire INSIDE
    # the TemporaryDirectory context so the asset is still on disk).
    #
    # ADR-207 Rule 4: spritesheet --no-verify returns VERIFIER_SKIPPED_EXIT_CODE
    # (3) instead of 0. Orchestrators that explicitly want to skip verification
    # must explicitly accept exit code 3 -- no silent masking with the same
    # exit status as success.
    if not getattr(args, "verify", True):
        logger.warning(
            "--no-verify opted out; spritesheet output not validated. "
            "Returning exit code %d (ADR-207 Rule 4: distinct from success).",
            VERIFIER_SKIPPED_EXIT_CODE,
        )
        return VERIFIER_SKIPPED_EXIT_CODE

    sheet_path = work_dir / "out" / f"{name}_sheet.png"
    if not sheet_path.exists():
        # Pipeline shipped without a sheet -- treat as a verifier failure so
        # callers don't silently green-light empty output. (Defensive: Phase H
        # error path returns nonzero before we get here, but handle it anyway.)
        return _emit_verifier_result(
            gates_run=[],
            failures=[{"check": "asset_exists", "file": str(sheet_path), "details": "missing"}],
            elapsed_seconds=0.0,
        )

    # Pixel-preservation needs the raw alongside the final. Phase C wrote the
    # raw to {name}_sheet_raw.png; pass it when present so the gate runs.
    raw_path = work_dir / f"{name}_sheet_raw.png"
    started_verify = time.perf_counter()
    gates_run, failures = _run_spritesheet_verifiers(
        sheet_path=sheet_path,
        raw_path=raw_path if raw_path.exists() else None,
        cols=cols,
        rows=rows,
        cell_size=args.cell_size,
        allow_frame_duplication=getattr(args, "allow_frame_duplication", False),
    )
    elapsed = time.perf_counter() - started_verify

    # ADR-207 Rule 2: rewrite the metadata sidecar to include the
    # contracted verifier_verdict + verifier_failures. Use the asserting
    # writer so consumers cannot read a sidecar that claims PASS while
    # listing failures.
    sidecar_path = work_dir / f"{name}_metadata.json"
    if sidecar_path.exists():
        try:
            sidecar_data = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:  # pragma: no cover - defensive
            sidecar_data = {}
        sidecar_data["verifier_verdict"] = verifier_verdict_from_passed(len(failures) == 0)
        sidecar_data["verifier_failures"] = failures
        sidecar_data["verifier_gates_run"] = gates_run
        sidecar_data["verifier_elapsed_seconds"] = round(elapsed, 3)
        # write_manifest_record raises ValueError if PASS+failures contradict.
        write_manifest_record(sidecar_path, sidecar_data)

    return _emit_verifier_result(gates_run=gates_run, failures=failures, elapsed_seconds=elapsed)


def run_pipeline(args: argparse.Namespace) -> int:
    """Spritesheet pipeline entry point.

    When ``--output-dir`` is set, the directory is preserved (user owns
    its lifecycle). When unset, a ``tempfile.TemporaryDirectory`` is
    created and reaped on exit (ADR-200).
    """
    name = args.name or "spritesheet"
    if args.output_dir:
        return _run_pipeline_body(args, Path(args.output_dir), name)
    with tempfile.TemporaryDirectory(prefix=f"sprite_{name}_") as td:
        return _run_pipeline_body(args, Path(td), name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prompt", help="Free-form prompt; alternative to --description")
    parser.add_argument("--description", help="Character description text")
    parser.add_argument("--name", help="Sprite name prefix")
    parser.add_argument("--style", default="modern-hi-bit")
    parser.add_argument("--style-string", help="Free-form style fragment for --style custom")
    parser.add_argument("--archetype", help="Wrestler archetype")
    parser.add_argument("--gimmick", help="Wrestler gimmick")
    parser.add_argument("--grid", default="4x1", help="Grid CxR (default 4x1; ignored with --max-frames)")
    parser.add_argument("--cell-size", type=int, default=256, choices=[64, 128, 192, 256, 384, 512])
    parser.add_argument(
        "--max-frames",
        action="store_true",
        help=(
            "Auto-fill the canvas: pack the largest square grid that fits "
            "--max-canvas at --cell-size. Overrides --grid."
        ),
    )
    parser.add_argument(
        "--max-canvas",
        type=int,
        default=sprite_canvas.DEFAULT_MAX_CANVAS,
        help=f"Max canvas side in px when --max-frames is set (default {sprite_canvas.DEFAULT_MAX_CANVAS})",
    )
    parser.add_argument("--action", default="walking")
    parser.add_argument("--pattern", default="alternating", choices=["magenta-only", "alternating", "checkerboard"])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--variants", type=int, default=1)
    parser.add_argument(
        "--bg-mode",
        choices=list(sprite_bg.BG_MODE_CHOICES),
        default="chroma",
        help=(
            "Background removal (ADR-204 unified vocabulary): "
            "chroma=two-pass magenta despill (default), "
            "gray-tolerance=road-to-aew #3a3a3a algorithm, "
            "rembg=opt-in ML, auto=chroma with rembg fallback."
        ),
    )
    parser.add_argument("--chroma-threshold", type=int, default=30)
    parser.add_argument(
        "--confirm-dense-grid",
        action="store_true",
        help=(
            "Suppress the dense-grid warning when rows*cols > 64. "
            "Image-gen models drop sprite quality at high density; "
            "see references/frame-detection.md."
        ),
    )
    parser.add_argument("--min-pixels", type=int, default=200)
    parser.add_argument("--scale-percentile", type=float, default=95)
    parser.add_argument(
        "--anchor-mode",
        choices=["bottom", "center", "auto", "ground-line", "per-frame-bottom", "mass-centroid"],
        default="mass-centroid",
        help=(
            "Anchor strategy. mass-centroid (ADR-208 RC-4 default): each "
            "frame's alpha-mass-centroid lands at a globally-stable Y; "
            "drift-free even on extended-limb frames (lunge, kick). "
            "ground-line: legacy global bbox-bottom anchor (correct for "
            "portrait-loop / fixed-camera modes; wobbles on action sheets "
            "where bbox-bottom is sometimes a fist or kicking leg). "
            "per-frame-bottom / bottom: per-frame bbox anchor (drifts). "
            "See references/anchor-alignment.md and ADR-208."
        ),
    )
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--no-strips", action="store_true")
    parser.add_argument("--skip-reference", action="store_true", help="Skip Phase A reference generation")
    parser.add_argument(
        "--output-dir",
        help=(
            "Working directory. When unset, a temporary directory is "
            "created and cleaned up automatically. When set, the "
            "directory is preserved (you own its lifecycle)."
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="Skip backend; synthetic fixture for D-H")
    parser.add_argument(
        "--verify",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Run verifier gates as the last pipeline step (default ON). "
            "Spritesheet gates: verify_no_magenta, verify_grid_alignment, "
            "verify_anchor_consistency, verify_frames_have_content, "
            "verify_frames_distinct, verify_pixel_preservation. "
            "On failure, prints structured JSON to stdout and exits with "
            "code 2. Opt out with --no-verify (logs WARNING). "
            "See ADR-199 for the contract."
        ),
    )
    parser.add_argument(
        "--content-aware-extraction",
        action="store_true",
        help=(
            "Use slice_with_content_awareness (connected-components + centroid "
            "ownership) instead of strict-pitch slicing. ADR-207 Rule 1: on dense "
            "grids (>= 4x4 with >= 16 cells) this flag is unsafe and is downgraded "
            "to strict-pitch with a warning unless --effects-asset is also passed. "
            "Use --effects-asset for legitimate sparse-but-cross-boundary content "
            "(fire breath, plasma trails, projectile auras). Codex output is "
            "ground truth; clipping happens in our slicer. See ADR-207 RC-1 and "
            "references/error-catalog.md 'Anti-pattern: Codex Regeneration as a "
            "Post-Processing Fix'."
        ),
    )
    parser.add_argument(
        "--effects-asset",
        action="store_true",
        help=(
            "Opt INTO content-aware routing on a DENSE grid (>= 4x4 with >= 16 cells). "
            "Use ONLY for sparse-but-cross-boundary content: fire breath, plasma "
            "trails, projectile auras. Do NOT use for character grids — content-aware "
            "on dense character grids drops cells via centroid drift (ADR-207 RC-1)."
        ),
    )
    parser.add_argument(
        "--allow-frame-duplication",
        action="store_true",
        help=(
            "Opt OUT of the frames-distinct gate's tightened threshold (ADR-208 RC-3). "
            "Use for spec-known sheets with legitimate frame repetition: idle loops "
            "where 8 frames repeat to fill 64 cells, taunt poses where the character "
            "holds a stance for most of the cycle, or any animation where >70% "
            "duplicate-pct is the artist's intent. Without this flag the gate fires "
            "at 70% to catch the layout-drift signature where centroid mis-routing "
            "lands most cells on a few near-identical poses (ADR-208 RC-3)."
        ),
    )
    # Logging level controls (ADR-202). Mutually exclusive; default INFO.
    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress INFO log records; only emit WARNING and above on stderr.",
    )
    log_group.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Emit DEBUG-level diagnostic log records on stderr.",
    )
    return parser


def configure_logging(quiet: bool, verbose: bool) -> None:
    """Configure the root logger for sprite-pipeline scripts (ADR-202).

    --quiet → WARNING, --verbose → DEBUG, default → INFO. Records are
    formatted as ``[<logger-name>] LEVEL: message`` and written to stderr
    so structured stdout (verifier JSON, generated paths) stays clean.
    """
    level = logging.WARNING if quiet else (logging.DEBUG if verbose else logging.INFO)
    logging.basicConfig(
        level=level,
        format="[%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(quiet=args.quiet, verbose=args.verbose)
    # portrait-loop mode delegates to portrait_pipeline.run_portrait_loop
    if getattr(args, "mode", None) == "portrait-loop":
        import portrait_pipeline as pp

        return pp.run_portrait_loop(args)
    return run_pipeline(args)


if __name__ == "__main__":
    sys.exit(main())
