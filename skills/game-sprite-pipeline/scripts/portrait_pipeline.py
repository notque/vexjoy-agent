#!/usr/bin/env python3
"""
Portrait-mode end-to-end orchestrator (Phases A-E).

Chains:
    A: prompt build + backend dispatch
    B: bg removal (chroma key default; rembg opt-in)
    C: trim and re-canvas with bottom anchor
    D: dimension validation (width 350-850, height 900-1100, aspect 1:1.5-1:2.5)
    E: project-aware deploy (road-to-aew if --target road-to-aew)

Usage:
    python3 portrait_pipeline.py \\
        --display-name "Bangkok Belle Nisa" \\
        --description "kabuki makeup, Thai national colors" \\
        --style slay-the-spire-painted --archetype showman --gimmick heel \\
        --tier act2 --target road-to-aew --regen-manifest --seed 42

--dry-run skips the backend call and uses a synthetic fixture for
post-processing validation. Useful for CI smoke tests.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError as e:
    print(f"ERROR: Pillow not installed: {e}", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import sprite_generate
import sprite_process
import sprite_prompt
from sprite_verify import (
    verify_anchor_consistency,
    verify_frames_distinct,
    verify_frames_have_content,
    verify_no_magenta,
)

# See ADR-199. Distinct from generic pipeline error rc=1 so callers can
# branch on "verifier said no" vs "the pipeline blew up".
VERIFIER_EXIT_CODE = 2


def _detect_backends_available() -> dict[str, bool]:
    """Best-effort backend availability for the verifier failure JSON.

    Cheap shutil/env checks only; we never spawn ``codex --version`` here.
    Mirrors sprite_pipeline._detect_backends_available; duplicated by
    design (per CLAUDE.md "three-line repetition is better than premature
    abstraction") rather than introducing a new module solely for this.
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

    Per ADR-199. JSON shape:

        {passed, gates_run, failures, backends_available, elapsed_seconds}

    Returns ``VERIFIER_EXIT_CODE`` (2) when failures is non-empty; else 0.
    """
    payload = {
        "passed": len(failures) == 0,
        "gates_run": gates_run,
        "failures": failures,
        "backends_available": _detect_backends_available(),
        "elapsed_seconds": round(elapsed_seconds, 3),
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["passed"] else VERIFIER_EXIT_CODE


def _make_fixture_portrait(output: Path) -> None:
    """Synthesize a 600x950 magenta-bg PNG with a simple figure for smoke tests."""
    img = Image.new("RGBA", (600, 950), (255, 0, 255, 255))
    d = ImageDraw.Draw(img)
    # head
    d.ellipse((250, 80, 350, 200), fill=(220, 180, 150, 255), outline=(40, 20, 20, 255), width=4)
    # body
    d.rectangle((220, 200, 380, 600), fill=(180, 40, 40, 255), outline=(40, 20, 20, 255), width=4)
    # legs
    d.rectangle((230, 600, 290, 870), fill=(60, 60, 80, 255), outline=(40, 20, 20, 255), width=4)
    d.rectangle((310, 600, 370, 870), fill=(60, 60, 80, 255), outline=(40, 20, 20, 255), width=4)
    # arms
    d.rectangle((150, 220, 220, 480), fill=(180, 40, 40, 255), outline=(40, 20, 20, 255), width=4)
    d.rectangle((380, 220, 450, 480), fill=(180, 40, 40, 255), outline=(40, 20, 20, 255), width=4)
    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, format="PNG")


def _make_fixture_portrait_loop(output: Path, cell: int = 512) -> None:
    """Synthesize a 1024x1024 2x2 grid of near-identical figures for smoke tests."""
    img = Image.new("RGBA", (cell * 2, cell * 2), (255, 0, 255, 255))
    d = ImageDraw.Draw(img)
    for r in range(2):
        for c in range(2):
            ox, oy = c * cell, r * cell
            # eye state: 0 open, 2 closed (blink), 1+3 open
            blink = (r * 2 + c) == 2
            chest_offset = 0 if (r * 2 + c) == 0 else (-3 if (r * 2 + c) == 1 else 3)
            # head
            d.ellipse(
                (ox + 200, oy + 80, ox + 312, oy + 200),
                fill=(220, 180, 150, 255),
                outline=(40, 20, 20, 255),
                width=4,
            )
            # eyes
            eye_y = oy + 130
            if blink:
                d.line((ox + 225, eye_y, ox + 245, eye_y), fill=(40, 20, 20, 255), width=3)
                d.line((ox + 270, eye_y, ox + 290, eye_y), fill=(40, 20, 20, 255), width=3)
            else:
                d.ellipse((ox + 225, eye_y - 5, ox + 245, eye_y + 5), fill=(40, 20, 20, 255))
                d.ellipse((ox + 270, eye_y - 5, ox + 290, eye_y + 5), fill=(40, 20, 20, 255))
            # body (with chest variation)
            d.rectangle(
                (ox + 180 - chest_offset, oy + 200, ox + 332 + chest_offset, oy + 380),
                fill=(180, 40, 40, 255),
                outline=(40, 20, 20, 255),
                width=4,
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, format="PNG")


def _snake_case(name: str) -> str:
    """Mirror road_to_aew_integration.snake_case for orchestration use."""
    parts = name.strip().split()
    while parts and parts[0].lower() in {"the", "a", "an"}:
        parts.pop(0)
    s = " ".join(parts).lower()
    cleaned = []
    for ch in s:
        if ch.isalnum():
            cleaned.append(ch)
        elif ch.isspace() or ch == "-":
            cleaned.append("_")
    out = "".join(cleaned)
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


def _run_pipeline_body(args: argparse.Namespace, work_dir: Path, name: str) -> int:
    """Portrait pipeline body. ``work_dir`` lifetime is bounded by caller.

    See ADR-200 for the lifecycle contract: ``--output-dir`` set means
    the user owns the directory; unset means the caller wraps this in a
    ``tempfile.TemporaryDirectory`` that reaps on exit.
    """
    work_dir.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc)
    phases: list[dict] = []

    # Phase A: prompt
    prompt_path = work_dir / f"{name}_prompt.txt"
    metadata_path = work_dir / f"{name}_prompt.json"
    prompt_argv = [
        "build-portrait",
        "--style",
        args.style,
        "--description",
        args.description or args.display_name or "",
        "--seed",
        str(args.seed),
        "--output",
        str(prompt_path),
        "--metadata-out",
        str(metadata_path),
    ]
    if args.archetype:
        prompt_argv.extend(["--archetype", args.archetype])
    if args.gimmick:
        prompt_argv.extend(["--gimmick", args.gimmick])
    if args.tier:
        prompt_argv.extend(["--tier", args.tier])
    if args.style_string:
        prompt_argv.extend(["--style-string", args.style_string])
    rc = sprite_prompt.main(prompt_argv)
    if rc != 0:
        return rc
    phases.append({"phase": "A1", "name": "prompt-build", "rc": rc})

    # Phase A: backend dispatch (or fixture in dry-run)
    raw_path = work_dir / f"{name}_raw.png"
    if args.dry_run:
        _make_fixture_portrait(raw_path)
        phases.append({"phase": "A2", "name": "generate", "rc": 0, "dry_run": True})
    else:
        gen_argv = [
            "generate-portrait",
            "--prompt-file",
            str(prompt_path),
            "--output",
            str(raw_path),
            "--seed",
            str(args.seed),
        ]
        rc = sprite_generate.main(gen_argv)
        if rc != 0:
            return rc
        phases.append({"phase": "A2", "name": "generate", "rc": rc})

    # Phase B: bg removal
    nobg_path = work_dir / f"{name}_nobg.png"
    rc = sprite_process.main(
        [
            "remove-bg",
            str(raw_path),
            "--output",
            str(nobg_path),
            "--mode",
            args.bg_mode,
            "--chroma-threshold",
            str(args.chroma_threshold),
        ]
    )
    if rc != 0:
        return rc
    phases.append({"phase": "B", "name": "remove-bg", "rc": rc, "mode": args.bg_mode})

    # Phase C: trim and re-canvas
    trimmed_path = work_dir / f"{name}_trimmed.png"
    rc = sprite_process.main(
        [
            "normalize",
            "--mode",
            "portrait",
            "--input",
            str(nobg_path),
            "--output",
            str(trimmed_path),
            "--target-w",
            str(args.target_w),
            "--target-h",
            str(args.target_h),
        ]
    )
    if rc != 0:
        return rc
    phases.append({"phase": "C", "name": "trim-center", "rc": rc})

    # Phase D: validate dimensions
    validate_argv = ["validate-portrait", str(trimmed_path)]
    if args.force_dimensions:
        validate_argv.append("--force")
    rc = sprite_process.main(validate_argv)
    phases.append({"phase": "D", "name": "validate", "rc": rc, "force": args.force_dimensions})
    if rc != 0:
        return rc

    # Phase E: deploy (or local copy)
    final_path = work_dir / f"{name}.png"
    # Context-managed open ensures the source handle is closed
    # deterministically (ADR-200 file-handle hygiene).
    with Image.open(trimmed_path) as im:
        im.save(final_path, format="PNG")
    if args.target == "road-to-aew":
        deploy_argv = [
            "deploy",
            "--source",
            str(final_path),
            "--display-name",
            args.display_name or name,
        ]
        if args.player:
            deploy_argv.extend(["--player", args.player])
        if args.target_dir:
            deploy_argv.extend(["--target-dir", args.target_dir])
        if args.regen_manifest:
            deploy_argv.append("--regen-manifest")
        if args.dry_run:
            deploy_argv.append("--dry-run")
        from road_to_aew_integration import main as deploy_main

        rc = deploy_main(deploy_argv)
        phases.append({"phase": "E", "name": "deploy", "rc": rc, "target": "road-to-aew"})
        if rc != 0:
            return rc
    else:
        phases.append({"phase": "E", "name": "deploy", "rc": 0, "target": "local", "path": str(final_path)})

    # Metadata sidecar
    sidecar = {
        "name": name,
        "display_name": args.display_name,
        "seed": args.seed,
        "style_preset": args.style,
        "archetype": args.archetype,
        "gimmick": args.gimmick,
        "tier": args.tier,
        "dry_run": args.dry_run,
        "started_at": started.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "phases": phases,
        "output_dir": str(work_dir),
    }
    (work_dir / f"{name}_metadata.json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

    print(
        f"\n[portrait] PASS: {name} written to {work_dir} (phases: {len(phases)})",
        file=sys.stderr,
    )

    # Phase F: verifier gates (ADR-199). Default-on; opt out with --no-verify.
    # Portrait mode runs the subset of gates that apply to a single static
    # image:
    #   - verify_no_magenta: catches residual chroma-key bleed-through.
    #
    # Gates NOT run for portrait mode (and why):
    #   - verify_pixel_preservation: ADR-199 lists it for portraits, but the
    #     function fundamentally takes grid+cell_size and slices both raw and
    #     final into per-cell tiles. A variable-dimension single portrait
    #     does not have a meaningful cell grid; treating the whole image as
    #     one 1x1 cell with raw_size != final_size produces a misleading
    #     area_ratio and false-positive "lossy" verdicts. The dominant
    #     defect surface for portraits is chroma bleed, which verify_no_magenta
    #     covers cleanly. Documented as a deviation from ADR-199's literal
    #     gate list with rationale.
    #   - verify_grid_alignment / _frames_have_content / _frames_distinct /
    #     _anchor_consistency: per-cell gates over a grid sheet. Not
    #     applicable to a single-portrait output.
    if not getattr(args, "verify", True):
        print(
            "WARNING: --no-verify opted out; output not validated",
            file=sys.stderr,
        )
        return 0

    final_path = work_dir / f"{name}.png"
    if not final_path.exists():
        return _emit_verifier_result(
            gates_run=[],
            failures=[{"check": "asset_exists", "file": str(final_path), "details": "missing"}],
            elapsed_seconds=0.0,
        )
    started_verify = time.perf_counter()
    gates_run: list[str] = []
    failures: list[dict] = []
    try:
        gates_run.append("verify_no_magenta")
        result = verify_no_magenta(final_path)
        if not result.get("passed", True):
            failures.append({"check": "verify_no_magenta", "file": str(final_path), "details": result})
    except Exception as e:  # pragma: no cover - defensive
        failures.append({"check": "verify_no_magenta", "file": str(final_path), "details": f"error: {e}"})
    elapsed = time.perf_counter() - started_verify
    return _emit_verifier_result(gates_run=gates_run, failures=failures, elapsed_seconds=elapsed)


def run_pipeline(args: argparse.Namespace) -> int:
    """Portrait pipeline entry point.

    When ``--output-dir`` is set, the directory is preserved (user owns
    its lifecycle). When unset, a ``tempfile.TemporaryDirectory`` is
    created and reaped on exit (ADR-200).
    """
    name = args.name or (_snake_case(args.display_name) if args.display_name else "unnamed_portrait")
    if args.output_dir:
        return _run_pipeline_body(args, Path(args.output_dir), name)
    with tempfile.TemporaryDirectory(prefix=f"portrait_{name}_") as td:
        return _run_pipeline_body(args, Path(td), name)


def _run_portrait_loop_body(args: argparse.Namespace, work_dir: Path, name: str) -> int:
    """Portrait-loop pipeline body. ``work_dir`` lifetime is bounded by caller.

    See ADR-200: when ``--output-dir`` is set the user owns the
    directory; otherwise the caller wraps this in a
    ``tempfile.TemporaryDirectory`` that reaps on exit.
    """
    work_dir.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc)
    phases: list[dict] = []

    cell = args.loop_cell_size  # default 512
    canvas = cell * 2  # 1024 by default

    # Phase A1: prompt
    prompt_path = work_dir / f"{name}_prompt.txt"
    metadata_path = work_dir / f"{name}_prompt.json"
    prompt_argv = [
        "build-portrait-loop",
        "--style",
        args.style,
        "--description",
        args.description or args.display_name or "",
        "--seed",
        str(args.seed),
        "--output",
        str(prompt_path),
        "--metadata-out",
        str(metadata_path),
    ]
    if args.archetype:
        prompt_argv.extend(["--archetype", args.archetype])
    if args.gimmick:
        prompt_argv.extend(["--gimmick", args.gimmick])
    if args.tier:
        prompt_argv.extend(["--tier", args.tier])
    if args.style_string:
        prompt_argv.extend(["--style-string", args.style_string])
    rc = sprite_prompt.main(prompt_argv)
    if rc != 0:
        return rc
    phases.append({"phase": "A1", "name": "prompt-build", "rc": rc})

    # Phase A2: generate (or fixture in dry-run).
    # Portrait-loop produces a 2x2 grid (canvas = cell * 2), which is square by
    # construction. We MUST NOT call `generate-portrait` here -- that subcommand
    # forces aspect_ratio="4:5" which crops the bottom row of the grid. Use
    # `generate-character` instead (aspect_ratio="1:1") so the backend returns
    # a square sheet matching our cell layout.
    raw_path = work_dir / f"{name}_raw.png"
    if args.dry_run:
        _make_fixture_portrait_loop(raw_path, cell=cell)
        phases.append({"phase": "A2", "name": "generate", "rc": 0, "dry_run": True})
    else:
        gen_argv = [
            "generate-character",
            "--prompt-file",
            str(prompt_path),
            "--output",
            str(raw_path),
            "--seed",
            str(args.seed),
        ]
        rc = sprite_generate.main(gen_argv)
        if rc != 0:
            return rc
        phases.append({"phase": "A2", "name": "generate", "rc": rc})

    # Phase D: per-cell extract + bg removal.
    # Use sprite_process.slice_grid_cells: derives cell pitch from the actual
    # raw size (cols * cell_size if exact, raw_size/cols otherwise) instead of
    # assuming the raw is already a clean canonical canvas. Image-gen backends
    # routinely return sizes like 1254x1254 for an 8x8 grid; a whole-image
    # resize before slicing is the bug we are NOT doing here.
    # Context-managed open: close the source PNG handle once we have
    # the in-memory RGBA copy (ADR-200 file-handle hygiene).
    with Image.open(raw_path) as raw_im:
        sheet = raw_im.convert("RGBA")
    raw_frames: list[Image.Image] = [c.convert("RGBA") for c in sprite_process.slice_grid_cells(sheet, 2, 2, cell)]
    phases.append(
        {
            "phase": "D",
            "name": "extract",
            "rc": 0,
            "frames": 4,
            "raw_size": list(sheet.size),
            "canvas_size": canvas,
        }
    )

    # Phase E: bg removal per cell
    nobg_frames: list[Image.Image] = []
    for fr in raw_frames:
        # Use the same despill+fade+dilate chain as the spritesheet pipeline.
        p1 = sprite_process.chroma_pass1(fr, sprite_process.MAGENTA, args.chroma_threshold)
        p2 = sprite_process.chroma_pass2_edge_flood(
            p1,
            sprite_process.MAGENTA,
            sprite_process.DEFAULT_PASS2_THRESHOLD,
            despill_strength=sprite_process.DEFAULT_DESPILL_STRENGTH,
        )
        if sprite_process.HAS_NUMPY:
            import numpy as np  # local import; matched to sprite_process

            arr = np.array(p2.convert("RGBA"))
            arr = sprite_process.alpha_fade_magenta_fringe(arr)
            arr = sprite_process.color_despill_magenta(arr)
            # Interior magenta spill (catches full-opacity pink streaks the
            # generator painted INSIDE the silhouette). Must run BEFORE
            # kill_pink_fringe so neutralized pixels are not re-classified.
            arr = sprite_process.neutralize_interior_magenta_spill(arr)
            arr = sprite_process.dilate_alpha_zero(arr, sprite_process.DEFAULT_ALPHA_DILATE_RADIUS)
            # Final pink-fringe alpha kill at silhouette edges.
            arr = sprite_process.kill_pink_fringe(arr)
            p2 = Image.fromarray(arr, "RGBA")
        nobg_frames.append(p2)
    phases.append({"phase": "E", "name": "remove-bg", "rc": 0})

    # Phase F: ground-line anchor across the 4 frames (drift-free)
    ground_line_y = sprite_process.detect_ground_line(nobg_frames, cell)
    anchored_frames: list[Image.Image] = [
        sprite_process.apply_ground_line_anchor(fr, ground_line_y, cell, cell) for fr in nobg_frames
    ]
    phases.append(
        {
            "phase": "F",
            "name": "anchor",
            "rc": 0,
            "ground_line_y": ground_line_y,
        }
    )

    # Phase H: assemble outputs
    out_dir = work_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    sheet_out = Image.new("RGBA", (cell * 2, cell * 2), (0, 0, 0, 0))
    for i, fr in enumerate(anchored_frames):
        r, c = divmod(i, 2)
        sheet_out.paste(fr, (c * cell, r * cell), fr)
    sheet_out.save(out_dir / f"{name}_sheet.png", format="PNG")

    # Per-frame PNGs
    frames_dir = out_dir / f"{name}_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for i, fr in enumerate(anchored_frames):
        fr.save(frames_dir / f"{name}_frame_{i:02d}.png", format="PNG")

    # Animated WebP (full 8-bit alpha; preferred output). No palette
    # quantization, so silhouettes stay clean.
    webp_path = out_dir / f"{name}.webp"
    anchored_frames[0].save(
        webp_path,
        save_all=True,
        append_images=anchored_frames[1:],
        duration=200,
        loop=0,
        format="WebP",
    )

    # Animated GIF (200ms per frame = 800ms loop) — compatibility fallback.
    # Matte-composite each frame over neutral mid-gray BEFORE quantizing.
    # See sprite_process.matte_composite docstring for the rationale.
    gif_path = out_dir / f"{name}.gif"
    gif_imgs = [
        sprite_process.matte_composite(fr, matte=(40, 40, 40)).convert("P", palette=Image.Palette.ADAPTIVE)
        for fr in anchored_frames
    ]
    gif_imgs[0].save(
        gif_path,
        save_all=True,
        append_images=gif_imgs[1:],
        duration=200,
        loop=0,
        optimize=False,
        disposal=2,
    )
    phases.append({"phase": "H", "name": "assemble", "rc": 0})

    # Metadata sidecar
    sidecar = {
        "name": name,
        "mode": "portrait-loop",
        "display_name": args.display_name,
        "seed": args.seed,
        "style_preset": args.style,
        "archetype": args.archetype,
        "gimmick": args.gimmick,
        "tier": args.tier,
        "frame_count": 4,
        "cell_size": cell,
        "canvas_size": canvas,
        "ground_line_y": ground_line_y,
        "frame_duration_ms": 200,
        "loop_duration_ms": 800,
        "dry_run": args.dry_run,
        "started_at": started.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "phases": phases,
        "output_dir": str(out_dir),
    }
    (work_dir / f"{name}_metadata.json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

    print(
        f"\n[portrait-loop] PASS: {name} written to {out_dir} (4 frames, ground_line_y={ground_line_y})",
        file=sys.stderr,
    )

    # Phase I: verifier gates (ADR-199). Portrait-loop runs the gate subset
    # that applies to animated 2x2 frames:
    #   - verify_no_magenta: residual chroma bleed
    #   - verify_frames_have_content: catches a blank cell (the despill
    #     chain ate one of the four frames)
    #   - verify_frames_distinct: catches the "all four frames identical"
    #     failure (ground-line anchor with zero variation = no animation)
    #   - verify_anchor_consistency: catches drift across the loop
    #
    # verify_grid_alignment is not run because portrait-loop frames are
    # tightly framed faces; the alignment gate's "character touches cell
    # edge" failure pattern doesn't apply when the pose deliberately fills
    # the cell vertically (head + shoulders).
    # verify_pixel_preservation is not run because the raw is upstream of
    # per-cell extraction here -- there is no canonical raw-sheet to
    # final-sheet pair on disk in this pipeline (raw_path is the whole
    # canvas, not a sheet at the same grid pitch as out/{name}_sheet.png).
    if not getattr(args, "verify", True):
        print(
            "WARNING: --no-verify opted out; output not validated",
            file=sys.stderr,
        )
        return 0

    sheet_path = out_dir / f"{name}_sheet.png"
    if not sheet_path.exists():
        return _emit_verifier_result(
            gates_run=[],
            failures=[{"check": "asset_exists", "file": str(sheet_path), "details": "missing"}],
            elapsed_seconds=0.0,
        )
    started_verify = time.perf_counter()
    gates_run: list[str] = []
    failures: list[dict] = []

    def _record(name_: str, result: dict) -> None:
        gates_run.append(name_)
        if not result.get("passed", True):
            failures.append({"check": name_, "file": str(sheet_path), "details": result})

    cols, rows = 2, 2
    try:
        _record("verify_no_magenta", verify_no_magenta(sheet_path))
    except Exception as e:  # pragma: no cover - defensive
        failures.append({"check": "verify_no_magenta", "file": str(sheet_path), "details": f"error: {e}"})
    try:
        _record(
            "verify_frames_have_content",
            verify_frames_have_content(sheet_path, cols, rows, cell),
        )
    except Exception as e:  # pragma: no cover - defensive
        failures.append({"check": "verify_frames_have_content", "file": str(sheet_path), "details": f"error: {e}"})
    try:
        # Portrait-loop frames are intentionally near-identical (subtle
        # breath + blink). Use the same relaxed dup_pct threshold the
        # verify_asset_outputs orchestrator uses for portrait-loop mode
        # (max_duplicate_pct=100.0); the gate then only fires if EVERY
        # cell is byte-identical, which would itself be a pipeline bug.
        _record(
            "verify_frames_distinct",
            verify_frames_distinct(sheet_path, cols, rows, cell, max_duplicate_pct=100.0),
        )
    except Exception as e:  # pragma: no cover - defensive
        failures.append({"check": "verify_frames_distinct", "file": str(sheet_path), "details": f"error: {e}"})
    try:
        # Portrait-loop has a fixed camera, so drift is more obvious; use
        # the tighter 4px stddev threshold from verify_asset_outputs.
        _record(
            "verify_anchor_consistency",
            verify_anchor_consistency(sheet_path, cols, rows, cell, max_centroid_y_stddev_px=4.0),
        )
    except Exception as e:  # pragma: no cover - defensive
        failures.append({"check": "verify_anchor_consistency", "file": str(sheet_path), "details": f"error: {e}"})
    elapsed = time.perf_counter() - started_verify
    return _emit_verifier_result(gates_run=gates_run, failures=failures, elapsed_seconds=elapsed)


def run_portrait_loop(args: argparse.Namespace) -> int:
    """Portrait-loop pipeline entry point.

    Phases:
      A1: prompt build (build-portrait-loop)
      A2: backend dispatch (Codex CLI; or fixture in dry-run) — produces a
          1024x1024 PNG with 2x2 cells (512x512 each)
      D:  per-cell extract + per-cell bg removal
      F:  ground-line anchor across the 4 frames (drift-free)
      H:  PNG sheet + animated GIF + animated WebP + per-frame PNGs

    When ``--output-dir`` is set, the directory is preserved (user owns
    its lifecycle). When unset, a ``tempfile.TemporaryDirectory`` is
    created and reaped on exit (ADR-200).
    """
    name = args.name or (_snake_case(args.display_name) if args.display_name else "portrait_loop")
    if args.output_dir:
        return _run_portrait_loop_body(args, Path(args.output_dir), name)
    with tempfile.TemporaryDirectory(prefix=f"portrait_loop_{name}_") as td:
        return _run_portrait_loop_body(args, Path(td), name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prompt", help="Free-form prompt; alternative to --description")
    parser.add_argument("--description", help="Character description text")
    parser.add_argument("--display-name", help="Character display name (e.g., 'Bangkok Belle Nisa')")
    parser.add_argument("--name", help="Override snake_case ID (default: derived from --display-name)")
    parser.add_argument("--style", default="slay-the-spire-painted")
    parser.add_argument("--style-string", help="Free-form style fragment for --style custom")
    parser.add_argument("--archetype", help="powerhouse, technical, high-flyer, ...")
    parser.add_argument("--gimmick", help="face, heel, manager, referee, ...")
    parser.add_argument("--tier", choices=["act1", "act2", "act3"])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--output-dir",
        help=(
            "Working output directory. When unset, a temporary directory "
            "is created and cleaned up automatically. When set, the "
            "directory is preserved (you own its lifecycle)."
        ),
    )
    parser.add_argument("--target", choices=["road-to-aew", "local"], default="local")
    parser.add_argument("--target-dir", help="Override road-to-aew root (default: ~/road-to-aew)")
    parser.add_argument("--player", choices=["male", "female"], help="Deploy as player sprite")
    parser.add_argument("--regen-manifest", action="store_true", help="Run npm run generate:sprites after deploy")
    parser.add_argument("--bg-mode", choices=["chroma", "rembg", "auto"], default="chroma")
    parser.add_argument("--chroma-threshold", type=int, default=30)
    parser.add_argument("--target-w", type=int, default=600)
    parser.add_argument("--target-h", type=int, default=980)
    parser.add_argument("--force-dimensions", action="store_true")
    parser.add_argument(
        "--dry-run", action="store_true", help="Skip backend; use synthetic fixture for post-processing"
    )
    parser.add_argument(
        "--verify",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Run verifier gates as the last pipeline step (default ON). "
            "Portrait gates: verify_no_magenta. Portrait-loop gates: "
            "verify_no_magenta, verify_frames_have_content, "
            "verify_frames_distinct, verify_anchor_consistency. "
            "On failure, prints structured JSON to stdout and exits with "
            "code 2. Opt out with --no-verify (logs WARNING). "
            "See ADR-199 for the contract."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["portrait", "portrait-loop"],
        default="portrait",
        help=(
            "portrait (default): single static PNG. "
            "portrait-loop: 2x2 = 4-frame subtle idle (breathing + blink); "
            "outputs sheet, GIF, WebP, per-frame PNGs."
        ),
    )
    parser.add_argument(
        "--loop-cell-size",
        type=int,
        default=512,
        help="Cell size for portrait-loop mode (default 512 → 1024x1024 canvas).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.description and args.prompt:
        args.description = args.prompt
    if args.mode == "portrait-loop":
        return run_portrait_loop(args)
    return run_pipeline(args)


if __name__ == "__main__":
    sys.exit(main())
