#!/usr/bin/env python3
"""Audit the tracked tree for private terms. Local only.

Computes the same term set as hooks/pretool-private-name-leak-gate.py
(private leaf component names, derived brand terms, and the optional
~/private-skills/.private-terms list) by importing the hook module. Then
it scans every tracked file's path and contents and prints each hit with
the term redacted.

No-op (exit 0) when neither ~/private-skills nor ~/pgh/private-skills exists, as in CI and public
installs: the term set exists only on the owner's machine.

Usage:
    python3 scripts/private-term-audit.py [--repo PATH]

Exit codes:
    0 -- no private term found, or no private tree on this machine
    1 -- at least one tracked path or file contains a private term
    2 -- the repo or the gate module could not be loaded
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE = REPO_ROOT / "hooks" / "pretool-private-name-leak-gate.py"
_GIT_ENV_SCRUB = frozenset({"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"})
_GIT_TIMEOUT_S = 60.0


def load_gate():
    """Import the leak gate as the single source of truth for private terms."""
    sys.path.insert(0, str(GATE.parent / "lib"))
    spec = importlib.util.spec_from_file_location("_private_name_leak_gate", GATE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {GATE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(
    repo: Path,
    *args: str,
    input_text: str | None = None,
    allow_no_match: bool = False,
    timeout: float = _GIT_TIMEOUT_S,
) -> str:
    env = {k: v for k, v in os.environ.items() if k not in _GIT_ENV_SCRUB}
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            env=env,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"git {args[0]} timed out after {timeout}s") from exc
    # Only git grep exits 1 on "no match"; other commands (e.g. ls-files) must exit 0.
    allowed = (0, 1) if allow_no_match else (0,)
    if result.returncode not in allowed:
        raise RuntimeError(result.stderr.strip() or f"git {args[0]} failed (exit {result.returncode})")
    return result.stdout


def audit(repo: Path, gate) -> list[str]:
    """Return redacted report lines, one per offending path."""
    leaves, strong = gate.private_terms(repo)
    pattern = gate.term_pattern(leaves, strong)
    if pattern is None:
        return []

    def redact(text: str) -> str:
        return pattern.sub(lambda m: gate._redact(m.group(0)), text)

    hits: dict[str, set[str]] = {}
    for path in git(repo, "ls-files", "-z").split("\0"):
        if path and pattern.search(path):
            hits.setdefault(path, set()).add("path")

    # Cheap fixed-string prefilter via stdin (-f - avoids argv length limits),
    # then the exact boundary-aware pattern.
    terms = sorted(t for t in (leaves | strong) if t)
    grep_out = ""
    if terms:
        grep_out = git(
            repo,
            "grep",
            "-I",
            "-i",
            "-l",
            "-z",
            "--fixed-strings",
            "-f",
            "-",
            input_text="\n".join(terms) + "\n",
            allow_no_match=True,
        )
    for path in grep_out.split("\0"):
        if not path:
            continue
        try:
            text = (repo / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if pattern.search(text):
            hits.setdefault(path, set()).add("content")

    return [f"{redact(path)}  [{', '.join(sorted(kinds))}]" for path, kinds in sorted(hits.items())]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--repo", type=Path, default=REPO_ROOT, help="repo root to scan (default: this checkout)")
    args = parser.parse_args()

    try:
        gate = load_gate()
    except Exception as exc:
        print(f"private-term-audit: cannot load gate: {exc}", file=sys.stderr)
        return 2
    if not gate._PRIVATE_DIR.is_dir():
        print("private-term-audit: no private tree on this machine, nothing to check")
        return 0

    repo = args.repo.resolve()
    try:
        lines = audit(repo, gate)
    except RuntimeError as exc:
        print(f"private-term-audit: {exc}", file=sys.stderr)
        return 2
    if not lines:
        print("private-term-audit: clean, no private term in tracked paths or files")
        return 0
    print(f"private-term-audit: {len(lines)} tracked path(s) contain a private term (redacted):")
    for line in lines:
        print(f"  {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
