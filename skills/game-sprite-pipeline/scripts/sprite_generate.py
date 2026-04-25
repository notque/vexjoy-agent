#!/usr/bin/env python3
"""
Backend dispatcher for the game-sprite-pipeline skill.

Selects between Codex CLI imagegen (primary) and Gemini Nano Banana
(fallback). Fails loudly when neither backend is available -- the skill
does NOT call paid APIs directly.

Subcommands:
    generate-portrait       Single portrait image
    generate-character      Phase A: 1024x1024 reference character (spritesheet mode)
    generate-spritesheet    Phase C: full spritesheet generation

Usage:
    python3 sprite_generate.py generate-portrait \\
        --prompt-file prompt.txt --output portrait.png --seed 42

The script never touches paid endpoints. Detection logic:
    1. `codex` in PATH and `codex --version` exits 0 -> Codex CLI.
    2. GEMINI_API_KEY (or GOOGLE_API_KEY) set -> Nano Banana.
    3. Else: BackendUnavailableError with explicit fix instructions.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Resolve nano-banana script paths. Prefer ~/.claude/scripts/ (deployed),
# fall back to repo path when running in a dev checkout.
NANO_BANANA_GENERATE_CANDIDATES = [
    Path.home() / ".claude" / "scripts" / "nano-banana-generate.py",
    Path("/home/feedgen/.claude/scripts/nano-banana-generate.py"),
]


def find_nano_banana_script() -> Path | None:
    """Return the first existing nano-banana-generate.py path."""
    for candidate in NANO_BANANA_GENERATE_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


class BackendUnavailableError(RuntimeError):
    """Raised when no image-generation backend is available."""


@dataclass
class BackendChoice:
    backend: str  # 'codex' | 'nano-banana'
    detected_via: str


def select_backend() -> BackendChoice:
    """Detect which backend to use. Fail loudly if none available."""
    if shutil.which("codex"):
        try:
            subprocess.run(
                ["codex", "--version"],
                check=True,
                capture_output=True,
                timeout=10,
            )
            return BackendChoice(backend="codex", detected_via="codex --version exit 0")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
            print(
                f"[backend] codex CLI present but auth check failed ({e}); trying Nano Banana",
                file=sys.stderr,
            )

    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return BackendChoice(backend="nano-banana", detected_via="GEMINI_API_KEY env set")

    raise BackendUnavailableError(
        "No image-generation backend available.\n\n"
        "Tried in order:\n"
        "  1. Codex CLI (`codex` not in PATH or auth failed)\n"
        "  2. Gemini Nano Banana (GEMINI_API_KEY not set)\n\n"
        "This skill does not call paid APIs directly. To proceed:\n"
        "  - Install Codex CLI and run `codex auth`, OR\n"
        "  - Set GEMINI_API_KEY: export GEMINI_API_KEY=<your-key>\n\n"
        "Never set OPENAI_API_KEY for this skill -- paid fallbacks are\n"
        "intentionally prohibited per the Local-First principle."
    )


def read_prompt(prompt: str | None, prompt_file: Path | None) -> str:
    """Resolve the prompt from --prompt or --prompt-file."""
    if prompt and prompt_file:
        raise ValueError("Pass either --prompt OR --prompt-file, not both.")
    if prompt:
        return prompt
    if prompt_file:
        return prompt_file.read_text(encoding="utf-8")
    raise ValueError("Must pass --prompt or --prompt-file.")


# ---------------------------------------------------------------------------
# Codex CLI dispatch
# ---------------------------------------------------------------------------
def generate_via_codex(
    prompt: str,
    output: Path,
    aspect_ratio: str | None = None,
    reference: Path | None = None,
    seed: int = 0,
    model: str = "image-1",
) -> int:
    """Run Codex CLI imagegen via subprocess. Returns exit code."""
    output.parent.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = ["codex", "exec", prompt, "--output-image", str(output), "--model", model]
    if aspect_ratio:
        cmd.extend(["--aspect-ratio", aspect_ratio])
    if reference:
        cmd.extend(["--reference", str(reference)])
    if seed:
        cmd.extend(["--seed", str(seed)])

    print(f"[backend:codex] $ {' '.join(cmd[:3])} ...", file=sys.stderr)
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
        return 0
    except subprocess.CalledProcessError as e:
        print(f"[backend:codex] failed exit {e.returncode}", file=sys.stderr)
        if e.stderr:
            print(e.stderr.decode(errors="replace"), file=sys.stderr)
        return e.returncode
    except subprocess.TimeoutExpired:
        print("[backend:codex] timed out after 180s", file=sys.stderr)
        return 124


# ---------------------------------------------------------------------------
# Nano Banana dispatch
# ---------------------------------------------------------------------------
def generate_via_nano_banana(
    prompt: str,
    output: Path,
    aspect_ratio: str = "1:1",
    reference: Path | None = None,
    seed: int = 0,
    model: str = "pro",
) -> int:
    """Shell out to nano-banana-generate.py. Returns exit code."""
    script = find_nano_banana_script()
    if script is None:
        print(
            "[backend:nano-banana] nano-banana-generate.py not found at expected paths",
            file=sys.stderr,
        )
        return 127

    output.parent.mkdir(parents=True, exist_ok=True)

    if reference:
        cmd = [
            sys.executable,
            str(script),
            "with-reference",
            "--prompt",
            prompt,
            "--reference",
            str(reference),
            "--output",
            str(output),
            "--model",
            model,
            "--aspect-ratio",
            aspect_ratio,
        ]
    else:
        cmd = [
            sys.executable,
            str(script),
            "generate",
            "--prompt",
            prompt,
            "--output",
            str(output),
            "--model",
            model,
            "--aspect-ratio",
            aspect_ratio,
        ]

    print(f"[backend:nano-banana] $ {script.name} ({'with-reference' if reference else 'generate'})", file=sys.stderr)
    try:
        subprocess.run(cmd, check=True, timeout=300)
        return 0
    except subprocess.CalledProcessError as e:
        print(f"[backend:nano-banana] failed exit {e.returncode}", file=sys.stderr)
        return e.returncode
    except subprocess.TimeoutExpired:
        print("[backend:nano-banana] timed out after 300s", file=sys.stderr)
        return 124


# ---------------------------------------------------------------------------
# Subcommand wrappers
# ---------------------------------------------------------------------------
def cmd_generate_portrait(args: argparse.Namespace) -> int:
    if args.dry_run:
        print("[backend] DRY-RUN: skipping backend call (portrait)", file=sys.stderr)
        return 0
    try:
        choice = select_backend()
    except BackendUnavailableError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3
    print(f"[backend] selected={choice.backend} ({choice.detected_via})", file=sys.stderr)

    prompt = read_prompt(args.prompt, Path(args.prompt_file) if args.prompt_file else None)
    output = Path(args.output)

    if choice.backend == "codex":
        return generate_via_codex(prompt, output, aspect_ratio="4:5", seed=args.seed)
    return generate_via_nano_banana(prompt, output, aspect_ratio="4:5", seed=args.seed)


def cmd_generate_character(args: argparse.Namespace) -> int:
    if args.dry_run:
        print("[backend] DRY-RUN: skipping backend call (character reference)", file=sys.stderr)
        return 0
    try:
        choice = select_backend()
    except BackendUnavailableError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3
    print(f"[backend] selected={choice.backend} ({choice.detected_via})", file=sys.stderr)

    prompt = read_prompt(args.prompt, Path(args.prompt_file) if args.prompt_file else None)
    output = Path(args.output)

    if choice.backend == "codex":
        return generate_via_codex(prompt, output, aspect_ratio="1:1", seed=args.seed)
    return generate_via_nano_banana(prompt, output, aspect_ratio="1:1", seed=args.seed)


def cmd_generate_spritesheet(args: argparse.Namespace) -> int:
    if args.dry_run:
        print("[backend] DRY-RUN: skipping backend call (spritesheet)", file=sys.stderr)
        return 0
    try:
        choice = select_backend()
    except BackendUnavailableError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3
    print(f"[backend] selected={choice.backend} ({choice.detected_via})", file=sys.stderr)

    prompt = read_prompt(args.prompt, Path(args.prompt_file) if args.prompt_file else None)
    output = Path(args.output)
    canvas = Path(args.canvas) if args.canvas else None
    reference = Path(args.reference) if args.reference else None

    # spritesheet generation prefers a structural reference (canvas template)
    structural_ref = canvas or reference

    if choice.backend == "codex":
        return generate_via_codex(prompt, output, reference=structural_ref, seed=args.seed)
    return generate_via_nano_banana(prompt, output, reference=structural_ref, seed=args.seed)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _add_common_args(parser: argparse.ArgumentParser) -> None:
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--prompt", help="Prompt text")
    grp.add_argument("--prompt-file", help="Path to a file containing the prompt")
    parser.add_argument("--output", required=True, help="Output PNG path")
    parser.add_argument("--seed", type=int, default=0, help="Reproducibility seed")
    parser.add_argument("--dry-run", action="store_true", help="Skip backend call (smoke testing)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    gp = sub.add_parser("generate-portrait", help="Single portrait image (Phase A portrait)")
    _add_common_args(gp)
    gp.set_defaults(func=cmd_generate_portrait)

    gc = sub.add_parser("generate-character", help="Phase A: reference character (spritesheet mode)")
    _add_common_args(gc)
    gc.set_defaults(func=cmd_generate_character)

    gs = sub.add_parser("generate-spritesheet", help="Phase C: spritesheet generation")
    _add_common_args(gs)
    gs.add_argument("--canvas", help="Phase B grid canvas template path")
    gs.add_argument("--reference", help="Reference character path (Phase A output)")
    gs.set_defaults(func=cmd_generate_spritesheet)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
