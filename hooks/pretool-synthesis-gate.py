#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse:Write,Edit Hook: Consultation Synthesis Gate

Blocks feature implementation when an ADR exists but consultation
synthesis is missing or BLOCKED. Forces agents to complete consultation
before writing implementation code.

This is a HARD GATE — exit 2 blocks the Write/Edit tool.

Detection logic:
- Tool is Write or Edit
- .adr-session.json exists (active ADR session)
- Target path is NOT in hooks/, scripts/, adr/, or test files
- No synthesis.md in the ADR consultation directory

Allow-through conditions:
- No .adr-session.json (no active ADR session)
- Target file is in hooks/, scripts/, adr/, commands/ (infrastructure, not implementation)
- Target file is a test file (*_test.go, *_test.py, test_*.py, *.test.ts)
- synthesis.md exists with explicit PROCEED verdict
- SYNTHESIS_GATE_BYPASS=1 env var (for the consultation skill itself)

Block conditions:
- synthesis.md is missing (verdict is None)
- synthesis.md contains explicit BLOCKED verdict
- synthesis.md exists but contains neither PROCEED nor BLOCKED (verdict is UNKNOWN --
  indicates incomplete consultation, truncated write, or merge conflict markers)
"""

import json
import os
import re
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

_BYPASS_ENV = "SYNTHESIS_GATE_BYPASS"

# Paths that ARE implementation code — only these get gated.
# Everything else (docs, config, CI, plans, tests) passes through.
_GATED_PREFIXES = (
    "/agents/",
    "/skills/",
    "/pipelines/",
)

# Source code extensions that are implementation code.
_GATED_EXTENSIONS = frozenset(
    {
        ".py",
        ".go",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".rs",
        ".java",
        ".rb",
        ".c",
        ".cpp",
        ".cs",
    }
)


def _is_gated(file_path: str) -> bool:
    """Return True if this is implementation code that requires consultation."""
    normalised = file_path.replace("\\", "/")
    basename = normalised.rsplit("/", 1)[-1] if "/" in normalised else normalised
    ext = "." + basename.rsplit(".", 1)[-1] if "." in basename else ""

    # Only gate source files in implementation directories
    in_gated_dir = any(prefix in normalised for prefix in _GATED_PREFIXES)
    is_source = ext.lower() in _GATED_EXTENSIONS

    # Gate if it's a source file in an implementation directory
    # OR if it's a SKILL.md or agent .md being created/modified
    if in_gated_dir:
        return True

    # Standalone source files at repo root (rare but possible)
    # are NOT gated — they're scripts or utilities
    return False


def _load_session(base_dir: Path) -> dict | None:
    """Load .adr-session.json from base_dir. Returns None if absent or malformed."""
    session_path = base_dir / ".adr-session.json"
    if not session_path.is_file():
        return None
    try:
        return json.loads(session_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _synthesis_verdict(synthesis_path: Path) -> str | None:
    """
    Return the verdict string from synthesis.md, or None if the file is missing.

    Scans for a line containing 'PROCEED' or 'BLOCKED' (case-insensitive).
    Returns 'PROCEED', 'BLOCKED', or 'UNKNOWN' if neither keyword is found.
    """
    if not synthesis_path.is_file():
        return None
    try:
        text = synthesis_path.read_text(encoding="utf-8").upper()
    except OSError:
        return None

    if "PROCEED" in text:
        return "PROCEED"
    if "BLOCKED" in text:
        return "BLOCKED"
    return "UNKNOWN"


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # tool_name filter removed — matcher "Write|Edit" in settings.json prevents
    # this hook from spawning for non-matching tools.

    # Bypass env var — set by the consultation skill itself.
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print("[synthesis-gate] Bypassed via SYNTHESIS_GATE_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Only gate implementation code (agents/, skills/, pipelines/).
    # Everything else (docs, config, CI, plans, tests, scripts) passes through.
    if not _is_gated(file_path):
        if debug:
            print(f"[synthesis-gate] Not implementation code, allowing: {file_path}", file=sys.stderr)
        sys.exit(0)

    # Resolve project root: prefer event["cwd"], then CLAUDE_PROJECT_DIR, then cwd.
    cwd_str = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", ".")
    base_dir = Path(cwd_str).resolve()

    session = _load_session(base_dir)
    if session is None:
        # No active ADR session — gate is dormant.
        if debug:
            print("[synthesis-gate] No .adr-session.json found — allowing through", file=sys.stderr)
        sys.exit(0)

    domain = session.get("domain", "")
    adr_name = domain or Path(session.get("adr_path", "unknown")).stem

    if debug:
        print(f"[synthesis-gate] Active ADR session: domain={adr_name}", file=sys.stderr)

    # Locate synthesis.md: adr/{domain}/synthesis.md
    synthesis_path = base_dir / "adr" / adr_name / "synthesis.md"
    verdict = _synthesis_verdict(synthesis_path)

    if verdict is None:
        # synthesis.md is missing — block until consultation is run.
        print(
            f"[synthesis-gate] BLOCKED: Consultation required. "
            f"Run /adr-consultation on {adr_name} first.\n"
            f"[synthesis-gate] Expected: {synthesis_path}",
            file=sys.stderr,
        )
        sys.exit(2)

    if verdict == "BLOCKED":
        print(
            f"[synthesis-gate] BLOCKED: Consultation verdict is BLOCKED for {adr_name}.\n"
            f"[synthesis-gate] Review {synthesis_path} and resolve concerns before implementing.",
            file=sys.stderr,
        )
        sys.exit(2)

    if verdict == "UNKNOWN":
        print(
            f"[synthesis-gate] BLOCKED: synthesis.md exists but contains neither PROCEED nor BLOCKED for {adr_name}.\n"
            f"[synthesis-gate] The consultation may be incomplete, truncated, or contain merge conflict markers.\n"
            f"[synthesis-gate] Review {synthesis_path} and ensure it contains an explicit PROCEED or BLOCKED verdict.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Explicit PROCEED — allow through.
    if debug:
        print(f"[synthesis-gate] Verdict=PROCEED for {adr_name} — allowing through", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(2) propagate for blocks
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"[synthesis-gate] Error: {type(e).__name__}: {e}", file=sys.stderr)
        # A crashed hook must fail OPEN — never exit 2 on unexpected errors.
        sys.exit(0)
