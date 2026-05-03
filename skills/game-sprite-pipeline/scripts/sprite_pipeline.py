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

Per-row mode (--per-row, typically with --preset):
    A: canonical base character generation (identity lock)
    For each row in preset:
        B': layout guide generation
        C': per-row strip generation with identity lock + VFX containment
        D': per-strip slice (pitch = strip_width / expected_frames)
        E': per-frame bg removal on individually sliced frames
    F: normalize all frames together (consistent anchoring)
    H: assemble into final sheet with correct row/col mapping

Usage:
    python3 sprite_pipeline.py \\
        --prompt "wrestler walk cycle, 4 frames" \\
        --grid 4x1 --cell-size 256 --action walking \\
        --style slay-the-spire-painted

    python3 sprite_pipeline.py \\
        --preset fighter --per-row --dry-run --output-dir /tmp/test

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

import qa_artifacts
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


def _detect_backends_available() -> dict[str, bool]:
    """Best-effort backend availability for the verifier failure JSON."""
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
    """Print the structured verifier JSON to stdout and return the exit code."""
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
    expected_empty_cells: list[tuple[int, int]] | None = None,
) -> tuple[list[str], list[dict]]:
    """Run the spritesheet gate suite against a final sheet PNG.

    Args:
        expected_empty_cells: List of (row, col) tuples for cells that are
            intentionally empty (per-row mode padding). Forwarded to
            verify_frames_have_content and verify_frames_distinct so they
            skip these cells instead of flagging them.
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
            verify_frames_have_content(
                sheet_path,
                cols,
                rows,
                cell_size,
                expected_empty_cells=expected_empty_cells,
            ),
        )
    except Exception as e:  # pragma: no cover - defensive
        gates_run.append("verify_frames_have_content")
        failures.append({"check": "verify_frames_have_content", "file": str(sheet_path), "details": f"error: {e}"})

    try:
        dup_pct_max = 100.0 if allow_frame_duplication else 70.0
        _record_gate(
            "verify_frames_distinct",
            verify_frames_distinct(
                sheet_path,
                cols,
                rows,
                cell_size,
                max_duplicate_pct=dup_pct_max,
                expected_empty_cells=expected_empty_cells,
            ),
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


def _make_fixture_strip(output: Path, frames: int, cell: int, row_idx: int) -> None:
    """Synthesize a magenta-bg horizontal strip fixture for dry-run per-row mode.

    Each frame gets a distinct color and slightly varied figure proportions
    to give downstream verifiers something to differentiate.
    """
    img = Image.new("RGBA", (frames * cell, cell), (255, 0, 255, 255))
    draw = ImageDraw.Draw(img)
    for f in range(frames):
        color = FIXTURE_COLORS[(row_idx * frames + f) % len(FIXTURE_COLORS)]
        cx = f * cell + cell // 2
        # Vary proportions per frame so verify_frames_distinct sees differences
        head_r = cell // 8 + (f % 3) * 2
        cy_top = cell // 5 + (f % 4) * 3
        cy_bot = (cell * 4) // 5 - (f % 3) * 2
        draw.ellipse(
            (cx - head_r, cy_top, cx + head_r, cy_top + 2 * head_r),
            fill=color,
            outline=(20, 20, 20, 255),
            width=3,
        )
        body_w = cell // 4 + (f % 3) * 4
        draw.rectangle(
            (cx - body_w // 2, cy_top + 2 * head_r, cx + body_w // 2, cy_bot),
            fill=color,
            outline=(20, 20, 20, 255),
            width=3,
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, format="PNG")


def _make_fixture_canonical_base(output: Path, cell: int) -> None:
    """Synthesize a canonical base image fixture for dry-run mode."""
    img = Image.new("RGBA", (cell * 2, cell * 2), (255, 0, 255, 255))
    draw = ImageDraw.Draw(img)
    color = (100, 140, 220, 255)
    cx, cy_top, cy_bot = cell, cell // 3, cell * 2 - cell // 3
    head_r = cell // 4
    draw.ellipse(
        (cx - head_r, cy_top, cx + head_r, cy_top + 2 * head_r),
        fill=color,
        outline=(20, 20, 20, 255),
        width=4,
    )
    body_w = cell // 2
    draw.rectangle(
        (cx - body_w // 2, cy_top + 2 * head_r, cx + body_w // 2, cy_bot),
        fill=color,
        outline=(20, 20, 20, 255),
        width=4,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, format="PNG")


def _composite_strips(strip_paths: list[Path], output: Path, cell_size: int) -> None:
    """Composite row strip images into a single spritesheet.

    Each strip is a horizontal image of (frames_in_row * cell_size) x cell_size.
    The output is the widest strip width x (num_strips * cell_size), with
    narrower strips left-aligned and remaining space filled with magenta.
    """
    strips = [Image.open(p).convert("RGBA") for p in strip_paths]
    max_width = max(s.width for s in strips)
    total_height = sum(s.height for s in strips)

    sheet = Image.new("RGBA", (max_width, total_height), (255, 0, 255, 255))
    y_offset = 0
    for strip in strips:
        sheet.paste(strip, (0, y_offset))
        y_offset += strip.height

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG")
    logger.info("[composite] %s written (%dx%d, %d strips)", output, max_width, total_height, len(strips))


def _process_row_strip(
    strip_path: Path,
    row_index: int,
    state: str,
    name: str,
    expected_frames: int,
    cell_size: int,
    work_dir: Path,
    bg_mode: str,
    chroma_threshold: int,
) -> list[Path]:
    """Slice a single row strip into individual frames and remove backgrounds.

    Per-row mode knows the exact frame count from the preset. We slice at
    simple pitch (strip_width / expected_frames) rather than using
    connected-components or the dense-grid slicer, which fragment characters
    when Codex-generated strips don't align to cell boundaries.

    Steps:
        1. Pre-despill magenta to alpha=0 (avoids LANCZOS pink fringe on resize)
        2. Resize strip to (expected_frames * cell_size) x cell_size if needed
        3. Slice into expected_frames cells at exact cell_size pitch
        4. Run bg removal on each frame
        5. Return list of processed frame paths

    Args:
        strip_path: Path to the row strip PNG.
        row_index: Zero-based row index (for naming).
        state: Animation state name (e.g. "idle", "dash-right").
        name: Sprite name prefix.
        expected_frames: Number of frames this row should contain.
        cell_size: Target cell size in pixels.
        work_dir: Working directory for intermediate files.
        bg_mode: Background removal mode (chroma, gray-tolerance, etc.).
        chroma_threshold: Chroma-key threshold for bg removal.

    Returns:
        List of paths to bg-removed frame PNGs, ordered by frame index.
    """
    from sprite_slicing import _pre_despill_raw_for_upscale

    strip_img = Image.open(strip_path).convert("RGBA")

    # Pre-despill: convert magenta to alpha=0 before any resize to avoid
    # LANCZOS interpolating between magenta and content (produces pink fringe).
    strip_img = _pre_despill_raw_for_upscale(strip_img, chroma_threshold=chroma_threshold)

    # Target dimensions
    target_w = expected_frames * cell_size
    target_h = cell_size

    # Resize if dimensions don't match expected
    if strip_img.size != (target_w, target_h):
        logger.info(
            "[per-row] row %d (%s): resizing strip %dx%d -> %dx%d",
            row_index,
            state,
            strip_img.width,
            strip_img.height,
            target_w,
            target_h,
        )
        strip_img = strip_img.resize((target_w, target_h), Image.Resampling.LANCZOS)

    # Slice at exact pitch — no connected-components needed
    row_frames_dir = work_dir / f"row_{row_index:02d}_{state}" / "frames"
    row_frames_dir.mkdir(parents=True, exist_ok=True)

    frame_paths: list[Path] = []
    for f_idx in range(expected_frames):
        x0 = f_idx * cell_size
        frame_img = strip_img.crop((x0, 0, x0 + cell_size, cell_size))
        frame_path = row_frames_dir / f"{name}_row{row_index:02d}_{state}_frame_{f_idx:02d}.png"
        frame_img.save(frame_path, format="PNG")
        frame_paths.append(frame_path)

    # Per-frame background removal
    nobg_dir = work_dir / f"row_{row_index:02d}_{state}" / "frames_nobg"
    nobg_dir.mkdir(parents=True, exist_ok=True)

    processed_paths: list[Path] = []
    for fp in frame_paths:
        dst = nobg_dir / fp.name
        if bg_mode == "chroma":
            sprite_bg.remove_bg_chroma(fp, dst, chroma_threshold)
        elif bg_mode == "gray-tolerance":
            sprite_bg.remove_bg_gray_tolerance(fp, dst)
        elif bg_mode == "rembg":
            sprite_bg.remove_bg_rembg(fp, dst)
        elif bg_mode == "auto":
            sprite_bg.remove_bg_chroma(fp, dst, chroma_threshold)
            if sprite_bg._alpha_coverage_too_low(dst):
                logger.warning("[per-row] auto: chroma low-coverage on %s; falling back to rembg", fp.name)
                sprite_bg.remove_bg_rembg(fp, dst)
        else:
            # Fallback to chroma
            sprite_bg.remove_bg_chroma(fp, dst, chroma_threshold)
        processed_paths.append(dst)

    logger.info(
        "[per-row] row %d (%s): sliced %d frames, bg removed",
        row_index,
        state,
        len(processed_paths),
    )
    return processed_paths


def _run_per_row_pipeline(args: argparse.Namespace, work_dir: Path, name: str) -> int:
    """Per-row pipeline body (Phase 1 + Phase 2 + Phase 3).

    Generates each animation row as a separate strip, then composites into
    a final sheet and runs the standard D-H pipeline on it.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    phases: list[dict] = []

    # Resolve preset
    try:
        preset = sprite_prompt.resolve_preset(args.preset)
    except ValueError as e:
        logger.error("%s", e)
        return 1
    row_defs = preset["rows"]

    # Phase A: canonical base generation (Phase 3 identity lock)
    canonical_base_path = work_dir / f"{name}_canonical_base.png"
    char_prompt_path = work_dir / f"{name}_char_prompt.txt"

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

    if args.dry_run:
        _make_fixture_canonical_base(canonical_base_path, args.cell_size)
    else:
        rc = sprite_generate.main(
            [
                "generate-character",
                "--prompt-file",
                str(char_prompt_path),
                "--output",
                str(canonical_base_path),
                "--seed",
                str(args.seed),
            ]
        )
        if rc != 0:
            return rc
    phases.append({"phase": "A", "name": "canonical-base", "rc": 0, "dry_run": args.dry_run})
    logger.info("[per-row] Phase A: canonical base at %s", canonical_base_path)

    # Per-row generation loop
    strip_paths: list[Path] = []
    max_frames = max(r["frames"] for r in row_defs)

    for row_idx, row_def in enumerate(row_defs):
        state = row_def["state"]
        frames = row_def["frames"]
        action = row_def["action"]

        row_dir = work_dir / f"row_{row_idx:02d}_{state}"
        row_dir.mkdir(parents=True, exist_ok=True)

        # Phase 2: layout guide
        guide_path = row_dir / "layout_guide.png"
        rc = sprite_canvas.main(
            [
                "make-layout-guide",
                "--state",
                state,
                "--frames",
                str(frames),
                "--cell-size",
                str(args.cell_size),
                "--output",
                str(guide_path),
            ]
        )
        if rc != 0:
            return rc

        # Row-strip prompt (Phase 1 + Phase 9 VFX containment)
        row_prompt_path = row_dir / "row_prompt.txt"
        prompt_argv = [
            "build-row-strip",
            "--style",
            args.style,
            "--description",
            args.description or args.prompt or "",
            "--seed",
            str(args.seed),
            "--output",
            str(row_prompt_path),
            "--state",
            state,
            "--frames",
            str(frames),
            "--action",
            action,
            "--canonical-base",
            str(canonical_base_path),
        ]
        if args.archetype:
            prompt_argv.extend(["--archetype", args.archetype])
        if args.gimmick:
            prompt_argv.extend(["--gimmick", args.gimmick])
        if args.style_string:
            prompt_argv.extend(["--style-string", args.style_string])
        rc = sprite_prompt.main(prompt_argv)
        if rc != 0:
            return rc

        # Generate strip
        strip_path = row_dir / f"{name}_row_{row_idx:02d}_{state}.png"
        if args.dry_run:
            _make_fixture_strip(strip_path, frames, args.cell_size, row_idx)
        else:
            # Pass both layout guide and canonical base as references
            rc = sprite_generate.main(
                [
                    "generate-spritesheet",
                    "--prompt-file",
                    str(row_prompt_path),
                    "--output",
                    str(strip_path),
                    "--canvas",
                    str(guide_path),
                    "--reference",
                    str(canonical_base_path),
                    "--seed",
                    str(args.seed + row_idx),
                ]
            )
            if rc != 0:
                return rc

        strip_paths.append(strip_path)
        phases.append(
            {
                "phase": f"C-row-{row_idx}",
                "name": f"row-strip-{state}",
                "rc": 0,
                "dry_run": args.dry_run,
                "frames": frames,
            }
        )
        logger.info("[per-row] row %d/%d (%s, %d frames) done", row_idx + 1, len(row_defs), state, frames)

    # Composite strips into raw sheet (reference only — slicing is per-strip)
    sheet_raw_path = work_dir / f"{name}_sheet_raw.png"
    _composite_strips(strip_paths, sheet_raw_path, args.cell_size)
    phases.append({"phase": "composite", "name": "composite-strips", "rc": 0})

    # Compute effective grid for downstream phases
    total_rows = len(row_defs)
    effective_cols = max_frames

    # Per-strip processing: slice each row strip individually and run bg
    # removal per frame. This avoids the dense-grid slicer which fragments
    # characters when Codex-generated strips don't align to cell boundaries.
    frames_nobg_dir = work_dir / "frames_nobg"
    frames_nobg_dir.mkdir(parents=True, exist_ok=True)

    # Track global frame index so normalize/assemble can map frames to
    # the correct row/col position in the final sheet.
    global_frame_idx = 0
    for row_idx, row_def in enumerate(row_defs):
        row_frame_paths = _process_row_strip(
            strip_path=strip_paths[row_idx],
            row_index=row_idx,
            state=row_def["state"],
            name=name,
            expected_frames=row_def["frames"],
            cell_size=args.cell_size,
            work_dir=work_dir,
            bg_mode=args.bg_mode,
            chroma_threshold=args.chroma_threshold,
        )
        # Copy/rename frames to the shared nobg dir with sequential global
        # indices so the normalize and assemble phases see them as a flat
        # list in the correct order (row-major: row0 frames, row1 frames, …).
        for fp in row_frame_paths:
            dst = frames_nobg_dir / f"{name}_frame_{global_frame_idx:02d}.png"
            # Use shutil.copy2 to avoid cross-device link issues
            shutil.copy2(fp, dst)
            global_frame_idx += 1
        # Pad shorter rows with None-sentinel empty cells up to effective_cols
        for _ in range(row_def["frames"], effective_cols):
            global_frame_idx += 1

    phases.append({"phase": "D+E", "name": "per-strip-slice-and-bg-removal", "rc": 0, "mode": args.bg_mode})

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

    # Phase H: assembly with per-frame timing (Phase 8)
    # Extract timing from preset for assembly
    timing_dict: dict[str, list[int]] = {}
    state_name_list: list[str] = []
    for rd in row_defs:
        state_name_list.append(rd["state"])
        if "timing" in rd:
            timing_dict[rd["state"]] = rd["timing"]

    # Write timing JSON for assembly to consume
    timing_json_path: Path | None = None
    if timing_dict:
        timing_json_path = work_dir / f"{name}_timing_input.json"
        timing_json_path.write_text(json.dumps(timing_dict, indent=2), encoding="utf-8")

    # Also accept --timing-json override
    if getattr(args, "timing_json", None):
        timing_json_path = Path(args.timing_json)

    # Use direct assembly call instead of CLI to pass timing
    from sprite_assemble import assemble_outputs

    frame_paths = sorted((frames_norm_dir).glob("*_frame_*.png"))
    expected = effective_cols * total_rows
    by_idx: dict[int, Image.Image] = {}
    for p in frame_paths:
        idx_str = p.stem.split("_frame_")[-1]
        try:
            idx = int(idx_str)
        except ValueError:
            continue
        by_idx[idx] = Image.open(p).convert("RGBA")
    assembly_frames: list[Image.Image | None] = [by_idx.get(i) for i in range(expected)]

    emit_strips = effective_cols in (4, 8) and not args.no_strips
    assemble_outputs(
        frames=assembly_frames,
        output_dir=work_dir / "out",
        name=name,
        grid_cols=effective_cols,
        grid_rows=total_rows,
        cell_w=args.cell_size,
        cell_h=args.cell_size,
        fps=args.fps,
        emit_strips=emit_strips,
        timing=timing_dict if timing_dict else None,
        state_names=state_name_list if state_name_list else None,
    )
    phases.append({"phase": "H", "name": "assemble", "rc": 0})

    # Phase 7: QA artifacts (when --qa-artifacts is set)
    if getattr(args, "qa_artifacts", False):
        sheet_for_qa = work_dir / "out" / f"{name}_sheet.png"
        if sheet_for_qa.exists():
            qa_dir = work_dir / "qa"
            qa_dir.mkdir(parents=True, exist_ok=True)
            qa_artifacts.make_contact_sheet(
                input_path=sheet_for_qa,
                output_path=qa_dir / "contact_sheet.png",
                cols=effective_cols,
                rows=total_rows,
                cell_size=args.cell_size,
                preset_name=args.preset,
            )
            qa_artifacts.render_preview_videos(
                input_path=sheet_for_qa,
                output_dir=qa_dir / "previews",
                cols=effective_cols,
                rows=total_rows,
                cell_size=args.cell_size,
                preset_name=args.preset,
                fps=args.fps,
            )
            qa_artifacts.generate_qa_report(
                input_path=sheet_for_qa,
                output_path=qa_dir / "review.json",
                cols=effective_cols,
                rows=total_rows,
                cell_size=args.cell_size,
                preset_name=args.preset,
            )
            phases.append({"phase": "QA", "name": "qa-artifacts", "rc": 0})
            logger.info("[per-row] QA artifacts written to %s", qa_dir)

    # Metadata
    sidecar = {
        "name": name,
        "mode": "per-row",
        "preset": args.preset,
        "grid": [effective_cols, total_rows],
        "cell_size": args.cell_size,
        "rows": [{"state": r["state"], "frames": r["frames"], "action": r["action"]} for r in row_defs],
        "style_preset": args.style,
        "archetype": args.archetype,
        "seed": args.seed,
        "dry_run": args.dry_run,
        "started_at": started.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "phases": phases,
        "output_dir": str(work_dir / "out"),
        "canonical_base": str(canonical_base_path),
    }
    (work_dir / f"{name}_metadata.json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

    logger.info(
        "[per-row] PASS: %s written to %s (%d rows, %d phases)",
        name,
        work_dir / "out",
        len(row_defs),
        len(phases),
    )

    # Verifier gates
    if not getattr(args, "verify", True):
        logger.warning(
            "--no-verify opted out; per-row output not validated. Returning exit code %d (ADR-207 Rule 4).",
            VERIFIER_SKIPPED_EXIT_CODE,
        )
        return VERIFIER_SKIPPED_EXIT_CODE

    sheet_path = work_dir / "out" / f"{name}_sheet.png"
    if not sheet_path.exists():
        return _emit_verifier_result(
            gates_run=[],
            failures=[{"check": "asset_exists", "file": str(sheet_path), "details": "missing"}],
            elapsed_seconds=0.0,
        )

    # Compute expected-empty cells: per-row mode pads shorter rows to
    # max_frames columns. Cells beyond a row's frame count are intentionally
    # blank and must not trigger verify_frames_have_content or
    # verify_frames_distinct failures.
    expected_empty_cells: list[tuple[int, int]] = []
    for row_idx, row_def in enumerate(row_defs):
        for col in range(row_def["frames"], effective_cols):
            expected_empty_cells.append((row_idx, col))

    # Per-row mode: do NOT pass raw_path to the verifier. The composite
    # raw sheet is a reference artifact, not the slicer input. The
    # verify_pixel_preservation and verify_raw_vs_final_cell_parity gates
    # compare raw-vs-final cell content; in per-row mode the final sheet
    # was assembled from per-strip slicing, so the composite raw has
    # different cell alignment and the parity check would false-positive.
    started_verify = time.perf_counter()
    gates_run, failures = _run_spritesheet_verifiers(
        sheet_path=sheet_path,
        raw_path=None,
        cols=effective_cols,
        rows=total_rows,
        cell_size=args.cell_size,
        allow_frame_duplication=getattr(args, "allow_frame_duplication", False),
        expected_empty_cells=expected_empty_cells,
    )
    elapsed = time.perf_counter() - started_verify

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
        write_manifest_record(sidecar_path, sidecar_data)

    return _emit_verifier_result(gates_run=gates_run, failures=failures, elapsed_seconds=elapsed)


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
    from sprite_slicing import is_dense_grid

    grid_is_dense = is_dense_grid(cols, rows)
    use_effects_asset = getattr(args, "effects_asset", False)
    legacy_content_aware = getattr(args, "content_aware_extraction", False)
    if grid_is_dense:
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

    # Phase H: assembly (with timing support from --timing-json)
    timing_dict: dict[str, list[int]] | None = None
    state_name_list: list[str] | None = None
    timing_json_arg = getattr(args, "timing_json", None)
    if timing_json_arg:
        tjp = Path(timing_json_arg)
        if tjp.exists():
            timing_dict = json.loads(tjp.read_text(encoding="utf-8"))
            state_name_list = list(timing_dict.keys()) if timing_dict else None

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

    # Phase 7: QA artifacts (when --qa-artifacts is set)
    if getattr(args, "qa_artifacts", False):
        sheet_for_qa = work_dir / "out" / f"{name}_sheet.png"
        if sheet_for_qa.exists():
            qa_dir = work_dir / "qa"
            qa_dir.mkdir(parents=True, exist_ok=True)
            qa_artifacts.make_contact_sheet(
                input_path=sheet_for_qa,
                output_path=qa_dir / "contact_sheet.png",
                cols=cols,
                rows=rows,
                cell_size=args.cell_size,
            )
            qa_artifacts.render_preview_videos(
                input_path=sheet_for_qa,
                output_dir=qa_dir / "previews",
                cols=cols,
                rows=rows,
                cell_size=args.cell_size,
                fps=args.fps,
            )
            qa_artifacts.generate_qa_report(
                input_path=sheet_for_qa,
                output_path=qa_dir / "review.json",
                cols=cols,
                rows=rows,
                cell_size=args.cell_size,
            )
            phases.append({"phase": "QA", "name": "qa-artifacts", "rc": 0})
            logger.info("[spritesheet] QA artifacts written to %s", qa_dir)

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

    # Phase I: verifier gates (ADR-199).
    if not getattr(args, "verify", True):
        logger.warning(
            "--no-verify opted out; spritesheet output not validated. "
            "Returning exit code %d (ADR-207 Rule 4: distinct from success).",
            VERIFIER_SKIPPED_EXIT_CODE,
        )
        return VERIFIER_SKIPPED_EXIT_CODE

    sheet_path = work_dir / "out" / f"{name}_sheet.png"
    if not sheet_path.exists():
        return _emit_verifier_result(
            gates_run=[],
            failures=[{"check": "asset_exists", "file": str(sheet_path), "details": "missing"}],
            elapsed_seconds=0.0,
        )

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
        write_manifest_record(sidecar_path, sidecar_data)

    return _emit_verifier_result(gates_run=gates_run, failures=failures, elapsed_seconds=elapsed)


def run_pipeline(args: argparse.Namespace) -> int:
    """Spritesheet pipeline entry point.

    Routes to per-row mode when --per-row is set; otherwise classic monolithic.
    When ``--output-dir`` is set, the directory is preserved. When unset, a
    ``tempfile.TemporaryDirectory`` is created and reaped on exit (ADR-200).
    """
    name = args.name or "spritesheet"

    # Route to per-row pipeline when --per-row is set
    if getattr(args, "per_row", False):
        if not getattr(args, "preset", None):
            logger.error("--per-row requires --preset (e.g., --preset fighter)")
            return 1
        if args.output_dir:
            return _run_per_row_pipeline(args, Path(args.output_dir), name)
        with tempfile.TemporaryDirectory(prefix=f"sprite_{name}_") as td:
            return _run_per_row_pipeline(args, Path(td), name)

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
    parser.add_argument("--grid", default="4x1", help="Grid CxR (default 4x1; ignored with --max-frames or --preset)")
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
        help=("Run verifier gates as the last pipeline step (default ON). See ADR-199 for the contract."),
    )
    parser.add_argument(
        "--content-aware-extraction",
        action="store_true",
        help=(
            "Use slice_with_content_awareness instead of strict-pitch slicing. "
            "ADR-207 Rule 1: on dense grids this flag is downgraded. "
            "See ADR-207 RC-1."
        ),
    )
    parser.add_argument(
        "--effects-asset",
        action="store_true",
        help=("Opt INTO content-aware routing on a DENSE grid. Use ONLY for sparse-but-cross-boundary content."),
    )
    parser.add_argument(
        "--allow-frame-duplication",
        action="store_true",
        help=(
            "Opt OUT of the frames-distinct gate's tightened threshold (ADR-208 RC-3). "
            "Use for spec-known sheets with legitimate frame repetition."
        ),
    )
    # Per-row mode flags (Phase 1 + Phase 6)
    parser.add_argument(
        "--per-row",
        action="store_true",
        help=(
            "Generate each animation row as a separate strip, then composite. "
            "Requires --preset. Eliminates cross-row contamination."
        ),
    )
    parser.add_argument(
        "--preset",
        choices=["fighter", "rpg-character", "platformer", "pet", "custom"],
        help=(
            "Named animation preset defining rows, frame counts, and timing. "
            "Use with --per-row for row-strip generation mode."
        ),
    )
    # Phase 5: Video source per row
    parser.add_argument(
        "--video-rows",
        help=(
            "Video source per row: comma-separated 'row_idx:state:path' entries. "
            "Example: '0:idle:/path/to/idle.mp4,4:jump:/path/to/jump.mp4'. "
            "Rows with video sources use the video extraction pipeline."
        ),
    )
    # Phase 7: QA artifacts
    parser.add_argument(
        "--qa-artifacts",
        action="store_true",
        help=("Generate QA artifacts (contact sheet, preview GIFs, review JSON) after verifier gates. Default OFF."),
    )
    # Phase 8: Custom timing
    parser.add_argument(
        "--timing-json",
        help=(
            "Path to JSON file with per-state timing overrides. Format: "
            '{"state_name": [ms_per_frame, ...]}. Overrides preset timing.'
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
    """Configure the root logger for sprite-pipeline scripts (ADR-202)."""
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
