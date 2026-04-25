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

import sprite_generate
import sprite_process
import sprite_prompt


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


def run_pipeline(args: argparse.Namespace) -> int:
    name = args.name or (_snake_case(args.display_name) if args.display_name else "unnamed_portrait")
    work_dir = Path(args.output_dir or tempfile.mkdtemp(prefix=f"portrait_{name}_"))
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
    Image.open(trimmed_path).save(final_path, format="PNG")
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
    return 0


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
    parser.add_argument("--output-dir", help="Working output dir (default: tempdir)")
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.description and args.prompt:
        args.description = args.prompt
    return run_pipeline(args)


if __name__ == "__main__":
    sys.exit(main())
