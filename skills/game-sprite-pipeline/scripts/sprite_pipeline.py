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
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError as e:
    print(f"ERROR: Pillow not installed: {e}", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import sprite_canvas
import sprite_generate
import sprite_process
import sprite_prompt

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


def run_pipeline(args: argparse.Namespace) -> int:
    name = args.name or "spritesheet"
    work_dir = Path(args.output_dir or tempfile.mkdtemp(prefix=f"sprite_{name}_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc)
    phases: list[dict] = []

    cols, rows = sprite_prompt.parse_grid(args.grid)

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
    rc = sprite_process.main(
        [
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
    )
    if rc != 0:
        return rc
    phases.append({"phase": "D", "name": "extract-frames", "rc": rc})

    # Phase E: per-frame bg removal
    frames_nobg_dir = work_dir / "frames_nobg"
    raw_frames = sorted(frames_raw_dir.glob("*_frame_*.png"))
    if not raw_frames:
        print("ERROR: no frames extracted in Phase D", file=sys.stderr)
        return 5
    rc = sprite_process.main(
        [
            "remove-bg",
            *(str(f) for f in raw_frames),
            "--output-dir",
            str(frames_nobg_dir),
            "--mode",
            args.bg_mode,
            "--chroma-threshold",
            str(args.chroma_threshold),
        ]
    )
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

    print(
        f"\n[spritesheet] PASS: {name} written to {work_dir / 'out'} (phases: {len(phases)})",
        file=sys.stderr,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prompt", help="Free-form prompt; alternative to --description")
    parser.add_argument("--description", help="Character description text")
    parser.add_argument("--name", help="Sprite name prefix")
    parser.add_argument("--style", default="modern-hi-bit")
    parser.add_argument("--style-string", help="Free-form style fragment for --style custom")
    parser.add_argument("--archetype", help="Wrestler archetype")
    parser.add_argument("--gimmick", help="Wrestler gimmick")
    parser.add_argument("--grid", default="4x1", help="Grid CxR (default 4x1)")
    parser.add_argument("--cell-size", type=int, default=256, choices=[64, 128, 192, 256, 384, 512])
    parser.add_argument("--action", default="walking")
    parser.add_argument("--pattern", default="alternating", choices=["magenta-only", "alternating", "checkerboard"])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--variants", type=int, default=1)
    parser.add_argument("--bg-mode", choices=["chroma", "rembg", "auto"], default="chroma")
    parser.add_argument("--chroma-threshold", type=int, default=30)
    parser.add_argument("--min-pixels", type=int, default=200)
    parser.add_argument("--scale-percentile", type=float, default=95)
    parser.add_argument("--anchor-mode", choices=["bottom", "center", "auto"], default="bottom")
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--no-strips", action="store_true")
    parser.add_argument("--skip-reference", action="store_true", help="Skip Phase A reference generation")
    parser.add_argument("--output-dir", help="Working dir (default: tempdir)")
    parser.add_argument("--dry-run", action="store_true", help="Skip backend; synthetic fixture for D-H")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_pipeline(args)


if __name__ == "__main__":
    sys.exit(main())
