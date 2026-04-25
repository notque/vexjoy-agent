#!/usr/bin/env python3
"""
Backend dispatcher for the game-sprite-pipeline skill.

Codex CLI imagegen is the SOLE backend. The skill fails LOUDLY when Codex is
unavailable rather than silently falling back to paid APIs (no Gemini, no
Nano Banana, no OpenAI direct). This is intentional per the Local-First
principle (PHILOSOPHY.md).

Codex CLI does not have a `codex image generate` subcommand. Image
generation happens through `codex exec`: the Codex agent has access to an
internal imagegen tool, and we invoke it by prompting the agent to "generate
an image of <subject> and save it to <absolute-path>". Codex first writes
the file under ``$CODEX_HOME/generated_images/<session-id>/ig_*.png`` and
then the agent copies/moves it to the requested path inside its workspace.

Subcommands:
    generate-portrait       Single portrait image
    generate-character      Phase A: 1024x1024 reference character (spritesheet mode)
    generate-spritesheet    Phase C: full spritesheet generation

Usage:
    python3 sprite_generate.py generate-portrait \\
        --prompt-file prompt.txt --output portrait.png --seed 42

Detection logic on every call:
    1. ``codex`` in PATH and ``codex --version`` exits 0 -> use Codex CLI.
    2. Else -> raise BackendUnavailableError with explicit fix instructions.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Default Codex exec wall-clock cap per generation (seconds).
# A typical imagegen run takes ~20-60s; allow a comfortable margin.
DEFAULT_CODEX_TIMEOUT_S = 240


class BackendUnavailableError(RuntimeError):
    """Raised when the Codex CLI backend is not available."""


@dataclass
class BackendChoice:
    backend: str  # always 'codex' in this Codex-only build
    detected_via: str


def select_backend() -> BackendChoice:
    """Detect Codex CLI availability. Fail loudly if unavailable.

    Codex is the only supported backend. No fallback. If Codex is missing or
    unauthenticated, the skill raises rather than silently calling a paid
    alternative.
    """
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
            raise BackendUnavailableError(
                "Codex CLI is on PATH but the auth/version check failed: "
                f"{e}.\n\n"
                "Run `codex login` to authenticate, then retry. This skill\n"
                "does not fall back to paid APIs (no Gemini, no Nano Banana,\n"
                "no OpenAI direct) by design -- absence of the free backend\n"
                "must be visible, not silently monetized."
            ) from e

    raise BackendUnavailableError(
        "Codex CLI is not available.\n\n"
        "Install Codex CLI and run `codex login`, then retry.\n\n"
        "This skill uses Codex CLI imagegen as its sole backend. There is\n"
        "no fallback to paid APIs (no Gemini, no Nano Banana, no OpenAI\n"
        "direct). The skill fails loud rather than silently charging your\n"
        "card on a backend you did not opt into."
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
def _build_codex_prompt(
    user_prompt: str,
    output: Path,
    reference: Path | None,
) -> str:
    """Wrap the user's prompt with explicit imagegen + save instructions.

    Codex CLI's image generation is invoked by *asking the agent* to use its
    imagegen tool and to save the result at a specific path. The wrapper
    below forces both behaviors and asks for a final ``ls -la`` so the call
    fails loudly if the file is missing.
    """
    ref_clause = ""
    if reference is not None:
        ref_clause = f"\nReference image to follow for character identity: {reference}\n"

    return (
        "Use your image_gen tool to create the following image. Then save\n"
        f"the resulting PNG file to this absolute path: {output}\n"
        "After saving, run `ls -la <path>` to verify the file exists.\n"
        f"{ref_clause}\n"
        "Image specification:\n"
        f"{user_prompt}\n"
    )


def generate_via_codex(
    prompt: str,
    output: Path,
    reference: Path | None = None,
    seed: int = 0,
    timeout_s: int = DEFAULT_CODEX_TIMEOUT_S,
    log_file: Path | None = None,
) -> int:
    """Run Codex CLI imagegen via subprocess. Returns exit code.

    The Codex CLI exec sandbox blocks file writes through bubblewrap on
    machines without proper bwrap setup; we use
    ``--dangerously-bypass-approvals-and-sandbox`` because this skill is
    intentionally invoked from controlled, user-initiated automation only.
    Reference images are passed via the ``-i`` flag (Codex 0.125+).

    The ``seed`` argument is not piped to Codex (no public seed flag) but is
    embedded in the prompt body for the model's awareness; reproducibility
    is best-effort here.
    """
    output.parent.mkdir(parents=True, exist_ok=True)

    wrapped = _build_codex_prompt(prompt, output, reference)
    if seed:
        wrapped = f"# seed={seed}\n{wrapped}"

    cmd: list[str] = [
        "codex",
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "--skip-git-repo-check",
    ]
    if reference is not None:
        cmd.extend(["-i", str(reference)])
    cmd.append(wrapped)

    print(f"[backend:codex] generating -> {output} (timeout {timeout_s}s)", file=sys.stderr)
    try:
        if log_file is not None:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with log_file.open("w", encoding="utf-8") as fp:
                proc = subprocess.run(
                    cmd,
                    check=False,
                    stdout=fp,
                    stderr=subprocess.STDOUT,
                    timeout=timeout_s,
                )
        else:
            proc = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                timeout=timeout_s,
            )

        if proc.returncode != 0:
            print(f"[backend:codex] non-zero exit {proc.returncode}", file=sys.stderr)
            if log_file is None and proc.stderr:
                print(proc.stderr.decode(errors="replace"), file=sys.stderr)
            return proc.returncode

        if not output.exists() or output.stat().st_size == 0:
            print(
                f"[backend:codex] codex exec exited 0 but {output} is missing/empty.\n"
                "  Common causes: prompt did not invoke imagegen tool, sandbox\n"
                "  blocked file save, or model declined the request. Inspect the\n"
                f"  Codex log at {log_file if log_file else 'stderr'} for details.",
                file=sys.stderr,
            )
            return 5
        return 0
    except subprocess.TimeoutExpired:
        print(f"[backend:codex] timed out after {timeout_s}s", file=sys.stderr)
        return 124


# ---------------------------------------------------------------------------
# Subcommand wrappers
# ---------------------------------------------------------------------------
def _run_generate(
    args: argparse.Namespace,
    *,
    aspect_hint: str,
    use_reference: bool,
) -> int:
    """Shared dispatch path for portrait, character, and spritesheet modes.

    aspect_hint is informational only -- Codex CLI does not expose a public
    aspect-ratio flag, so we encode the desired aspect in the prompt body.
    """
    if args.dry_run:
        print(f"[backend] DRY-RUN: skipping Codex call ({aspect_hint})", file=sys.stderr)
        return 0

    try:
        choice = select_backend()
    except BackendUnavailableError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3
    print(f"[backend] selected={choice.backend} ({choice.detected_via})", file=sys.stderr)

    prompt = read_prompt(args.prompt, Path(args.prompt_file) if args.prompt_file else None)
    output = Path(args.output)

    aspect_line = f"\nAspect ratio target: {aspect_hint}.\n"
    full_prompt = prompt + aspect_line

    reference: Path | None = None
    if use_reference:
        canvas = getattr(args, "canvas", None)
        ref = getattr(args, "reference", None)
        # spritesheet generation prefers the canvas template as structural ref;
        # fall back to character reference when canvas is missing.
        if canvas:
            reference = Path(canvas)
        elif ref:
            reference = Path(ref)

    log_file = Path(args.log_file) if args.log_file else None
    return generate_via_codex(
        full_prompt,
        output,
        reference=reference,
        seed=args.seed,
        timeout_s=args.timeout,
        log_file=log_file,
    )


def cmd_generate_portrait(args: argparse.Namespace) -> int:
    return _run_generate(args, aspect_hint="4:5 portrait", use_reference=False)


def cmd_generate_character(args: argparse.Namespace) -> int:
    return _run_generate(args, aspect_hint="1:1 square (1024x1024)", use_reference=False)


def cmd_generate_spritesheet(args: argparse.Namespace) -> int:
    return _run_generate(args, aspect_hint="1:1 square (1024x1024)", use_reference=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _add_common_args(parser: argparse.ArgumentParser) -> None:
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--prompt", help="Prompt text")
    grp.add_argument("--prompt-file", help="Path to a file containing the prompt")
    parser.add_argument("--output", required=True, help="Output PNG path")
    parser.add_argument("--seed", type=int, default=0, help="Reproducibility seed (best-effort)")
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_CODEX_TIMEOUT_S,
        help=f"Wall-clock cap for the Codex run (default {DEFAULT_CODEX_TIMEOUT_S}s)",
    )
    parser.add_argument("--log-file", help="Optional path to capture Codex stdout/stderr")
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
    gs.add_argument("--canvas", help="Phase B grid canvas template path (used as -i reference)")
    gs.add_argument("--reference", help="Reference character path (Phase A output)")
    gs.set_defaults(func=cmd_generate_spritesheet)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
