#!/usr/bin/env python3
"""Pathspec-scoped git commit helper for multi-agent worktrees.

Stages and commits only the listed paths, so one agent never commits
another agent's changes. Rebuilt in Python from the `committer` bash
helper in steipete/agent-scripts (evidence only, no code copied).

Usage:
    python3 scripts/scoped-commit.py [--force-lock] "message" path [path ...]

Guards:
    - Paths that resolve to the repo root or cwd (".", "./", absolute repo
      path) and pathspec magic prefixes (":/", ":(glob)") are rejected.
    - A message that matches an existing path is rejected (argument-order slip).
    - A stale .git/index.lock is removed only with --force-lock, then one retry.

Exit codes: 0 = committed, 1 = error, 2 = usage error
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

INDEX_LOCK_RE = re.compile(r"Unable to create '([^']*index\.lock)'")


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a git command, capturing output."""
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False)


def _fail(message: str) -> int:
    print(f"Error: {message}", file=sys.stderr)
    return 1


def _path_known_to_git(path: str) -> bool:
    """True if the path is in the index or in HEAD (supports staging deletions)."""
    if _git(["ls-files", "--error-unmatch", "--", path]).returncode == 0:
        return True
    return _git(["cat-file", "-e", f"HEAD:{path}"]).returncode == 0


def _commit(message: str, paths: list[str]) -> subprocess.CompletedProcess[str]:
    return _git(["commit", "-m", message, "--", *paths])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Commit only the listed paths.")
    parser.add_argument("--force-lock", action="store_true", help="remove a stale .git/index.lock and retry once")
    parser.add_argument("message", help="commit message")
    parser.add_argument("paths", nargs="+", help="specific paths to stage and commit")
    args = parser.parse_args(argv)

    if not args.message.strip():
        return _fail("commit message must not be empty")
    if Path(args.message).exists():
        return _fail(f'first argument looks like a path ("{args.message}"); pass the commit message first')
    toplevel = _git(["rev-parse", "--show-toplevel"])
    if toplevel.returncode != 0:
        return _fail(f"not a git repository: {toplevel.stderr.strip()}")
    repo_root = Path(toplevel.stdout.strip()).resolve()
    for path in args.paths:
        if path.startswith(":"):
            return _fail(f'pathspec magic prefixes are not allowed: "{path}"')
        if Path(path).resolve() in (Path.cwd().resolve(), repo_root):
            return _fail(f'"{path}" stages the whole repository; list specific paths instead')

    for path in args.paths:
        if not Path(path).exists() and not _path_known_to_git(path):
            return _fail(f"path not found: {path}")

    unstage = _git(["restore", "--staged", ":/"])
    if unstage.returncode != 0:
        return _fail(f"could not reset index: {unstage.stderr.strip()}")
    add = _git(["add", "-A", "--", *args.paths])
    if add.returncode != 0:
        return _fail(f"git add failed: {add.stderr.strip()}")
    if _git(["diff", "--staged", "--quiet"]).returncode == 0:
        return _fail(f"no staged changes for: {' '.join(args.paths)}")

    result = _commit(args.message, args.paths)
    if result.returncode != 0 and args.force_lock:
        match = INDEX_LOCK_RE.search(result.stderr)
        if match and Path(match.group(1)).exists():
            Path(match.group(1)).unlink()
            print(f"Removed stale git lock: {match.group(1)}", file=sys.stderr)
            result = _commit(args.message, args.paths)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return 1

    print(f'Committed "{args.message}" with {len(args.paths)} path(s)')
    return 0


if __name__ == "__main__":
    sys.exit(main())
