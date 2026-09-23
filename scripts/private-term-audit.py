#!/usr/bin/env python3
"""Audit the tracked tree for private terms. Local only.

Computes the same term set as hooks/pretool-private-name-leak-gate.py
(private leaf component names, derived brand terms, and the optional
~/private-skills/.private-terms list) by importing the hook module. Then
it scans every tracked file's path and contents and prints each hit with
the term redacted.

No-op (exit 0) when ~/private-skills is absent, as in CI and public
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
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE = REPO_ROOT / "hooks" / "pretool-private-name-leak-gate.py"


def load_gate():
    """Import the leak gate as the single source of truth for private terms."""
    sys.path.insert(0, str(GATE.parent / "lib"))
    spec = importlib.util.spec_from_file_location("_private_name_leak_gate", GATE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {GATE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    # git grep exits 1 on "no match"; treat that as empty output.
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip() or f"git {args[0]} failed")
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

    # Cheap fixed-string prefilter, then the exact boundary-aware pattern.
    args = ["grep", "-I", "-i", "-l", "-z", "--fixed-strings"]
    for term in sorted(leaves | strong):
        args += ["-e", term]
    for path in git(repo, *args).split("\0"):
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
