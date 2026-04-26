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
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("sprite-pipeline.sprite_generate")

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
            logger.warning(
                "[backend] codex CLI present but auth check failed (%s); trying Nano Banana",
                e,
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
    reference: Path | list[Path] | None = None,
    seed: int = 0,
    model: str = "image-1",
) -> int:
    """Run Codex CLI imagegen via subprocess. Returns exit code.

    Codex CLI 0.125+ does not expose --output-image / --aspect-ratio /
    --reference / --seed flags directly. Image generation happens through
    the agent's internal image_gen tool: we PROMPT codex exec to use that
    tool and save to an absolute path, then verify the file exists. The
    aspect_ratio / reference / seed values are encoded into the prompt
    itself rather than as CLI flags. This mirrors the working invocation
    pattern in /tmp/sprite-demo/generate.py:codex_generate.
    """
    output.parent.mkdir(parents=True, exist_ok=True)

    extras: list[str] = []
    if aspect_ratio:
        extras.append(f"Aspect ratio target: {aspect_ratio}.")
    if seed:
        extras.append(f"Seed (encode in image_gen call when supported): {seed}.")

    ref_count = len(reference) if isinstance(reference, list) else (1 if reference else 0)
    if ref_count > 1:
        ref_note = (
            "\nReference images attached: image 1 is the magenta GRID CANVAS "
            "TEMPLATE — use it to locate cell boundaries and place exactly "
            "one frame per cell. Image 2 is the CHARACTER REFERENCE — "
            "preserve this character's identity (face, hair, costume, "
            "colors, body type) in every cell.\n"
        )
    elif ref_count == 1:
        ref_note = (
            "\nReference image attached: use it as the structural / identity reference for the generated image.\n"
        )
    else:
        ref_note = ""

    wrapped = (
        "Use your image_gen tool to create the following image. Then save the "
        f"resulting PNG to this absolute path: {output}\n"
        "After saving, run `ls -la <path>` to verify the file exists.\n"
        f"{ref_note}\n"
        f"Image specification:\n{prompt}\n"
    )
    if extras:
        wrapped += "\n" + "\n".join(extras) + "\n"

    cmd: list[str] = [
        "codex",
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "--skip-git-repo-check",
    ]
    if reference:
        # -i / --image takes nargs=*; must be followed by `--` to terminate
        # before the positional prompt argument, otherwise the prompt is
        # consumed as another image filename. `reference` may be a single
        # Path or a list of Paths (canvas template + character portrait).
        ref_list = reference if isinstance(reference, list) else [reference]
        cmd.append("-i")
        cmd.extend(str(p) for p in ref_list)
        cmd.append("--")
    cmd.append(wrapped)

    logger.info("[backend:codex] $ codex exec ... (output=%s)", output)
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, timeout=420)
        if proc.returncode != 0:
            logger.error("[backend:codex] failed exit %d", proc.returncode)
            if proc.stderr:
                logger.error("%s", proc.stderr.decode(errors="replace")[-1000:])
            return proc.returncode
        if not output.exists() or output.stat().st_size == 0:
            logger.error("[backend:codex] codex exit 0 but %s missing/empty", output)
            if proc.stdout:
                logger.error("%s", proc.stdout.decode(errors="replace")[-1000:])
            return 5
        return 0
    except subprocess.TimeoutExpired:
        logger.error("[backend:codex] timed out after 420s")
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
        logger.error("[backend:nano-banana] nano-banana-generate.py not found at expected paths")
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

    logger.info(
        "[backend:nano-banana] $ %s (%s)",
        script.name,
        "with-reference" if reference else "generate",
    )
    try:
        subprocess.run(cmd, check=True, timeout=300)
        return 0
    except subprocess.CalledProcessError as e:
        logger.error("[backend:nano-banana] failed exit %d", e.returncode)
        return e.returncode
    except subprocess.TimeoutExpired:
        logger.error("[backend:nano-banana] timed out after 300s")
        return 124


# ---------------------------------------------------------------------------
# Subcommand wrappers
# ---------------------------------------------------------------------------
def cmd_generate_portrait(args: argparse.Namespace) -> int:
    if args.dry_run:
        logger.info("[backend] DRY-RUN: skipping backend call (portrait)")
        return 0
    try:
        choice = select_backend()
    except BackendUnavailableError as e:
        logger.error("%s", e)
        return 3
    logger.info("[backend] selected=%s (%s)", choice.backend, choice.detected_via)

    prompt = read_prompt(args.prompt, Path(args.prompt_file) if args.prompt_file else None)
    output = Path(args.output)

    if choice.backend == "codex":
        return generate_via_codex(prompt, output, aspect_ratio="4:5", seed=args.seed)
    return generate_via_nano_banana(prompt, output, aspect_ratio="4:5", seed=args.seed)


def cmd_generate_character(args: argparse.Namespace) -> int:
    if args.dry_run:
        logger.info("[backend] DRY-RUN: skipping backend call (character reference)")
        return 0
    try:
        choice = select_backend()
    except BackendUnavailableError as e:
        logger.error("%s", e)
        return 3
    logger.info("[backend] selected=%s (%s)", choice.backend, choice.detected_via)

    prompt = read_prompt(args.prompt, Path(args.prompt_file) if args.prompt_file else None)
    output = Path(args.output)

    if choice.backend == "codex":
        return generate_via_codex(prompt, output, aspect_ratio="1:1", seed=args.seed)
    return generate_via_nano_banana(prompt, output, aspect_ratio="1:1", seed=args.seed)


def cmd_generate_spritesheet(args: argparse.Namespace) -> int:
    if args.dry_run:
        logger.info("[backend] DRY-RUN: skipping backend call (spritesheet)")
        return 0
    try:
        choice = select_backend()
    except BackendUnavailableError as e:
        logger.error("%s", e)
        return 3
    logger.info("[backend] selected=%s (%s)", choice.backend, choice.detected_via)

    prompt = read_prompt(args.prompt, Path(args.prompt_file) if args.prompt_file else None)
    output = Path(args.output)
    canvas = Path(args.canvas) if args.canvas else None
    reference = Path(args.reference) if args.reference else None

    # Codex backend: pass BOTH images when both exist (canvas template +
    # character portrait). Codex `-i` accepts nargs=*; the model uses the
    # canvas for structural cell layout and the portrait for character
    # identity. Nano Banana single-ref API falls back to canvas-only.
    if choice.backend == "codex":
        refs: list[Path] = [p for p in (canvas, reference) if p]
        ref_arg: Path | list[Path] | None = refs if len(refs) > 1 else (refs[0] if refs else None)
        return generate_via_codex(prompt, output, reference=ref_arg, seed=args.seed)
    structural_ref = canvas or reference
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
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(name)s] %(levelname)s: %(message)s",
            stream=sys.stderr,
        )
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
