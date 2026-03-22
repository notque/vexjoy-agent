#!/usr/bin/env python3
"""Incremental upgrade detection — identify components changed since last upgrade.

Reads ~/.claude/state.json for the last recorded upgrade SHA, then diffs against
HEAD to find which agents, skills, hooks, and scripts have changed. Supports
full-scan mode (--full) and state recording (--record).

Usage:
    python3 scripts/upgrade-diff.py              # Incremental diff since last upgrade
    python3 scripts/upgrade-diff.py --full       # List all components (skip diff)
    python3 scripts/upgrade-diff.py --record     # Record current HEAD as last upgrade SHA

Exit codes:
    0 = success
    1 = error (git failure, state write failure)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATE_FILE = Path.home() / ".claude" / "state.json"
COMPONENT_DIRS = ("agents/", "skills/", "hooks/", "scripts/")
CATEGORY_MAP = {
    "agents": "agents/",
    "skills": "skills/",
    "hooks": "hooks/",
    "scripts": "scripts/",
}


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git(*args: str) -> str:
    """Run a git command and return stripped stdout. Raises on failure."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _get_head_sha() -> str:
    """Return the full SHA of HEAD."""
    return _git("rev-parse", "HEAD")


def _sha_exists(sha: str) -> bool:
    """Check whether a commit SHA exists in the local repo."""
    try:
        _git("cat-file", "-t", sha)
        return True
    except subprocess.CalledProcessError:
        return False


def _diff_names(base_sha: str, head_sha: str) -> list[str]:
    """Return file paths changed between two SHAs, limited to component dirs."""
    args = ["diff", "--name-status", f"{base_sha}..{head_sha}", "--"]
    args.extend(COMPONENT_DIRS)
    raw = _git(*args)
    return raw.splitlines() if raw else []


def _list_all_components() -> list[str]:
    """Return all tracked files under component directories."""
    args = ["ls-files", "--"]
    args.extend(COMPONENT_DIRS)
    raw = _git(*args)
    return raw.splitlines() if raw else []


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def _read_state() -> dict:
    """Read state.json, returning empty dict on missing/corrupt file."""
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _write_state(state: dict) -> None:
    """Write state.json, creating parent directory if needed."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Categorisation
# ---------------------------------------------------------------------------


def _categorise(path: str) -> str | None:
    """Return the category name for a file path, or None if not a component."""
    for category, prefix in CATEGORY_MAP.items():
        if path.startswith(prefix):
            return category
    return None


def _parse_diff_lines(lines: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    """Parse git diff --name-status output into changed and deleted buckets.

    Returns (changed_by_category, deleted_paths).
    Renames (R###) are treated as delete + add.
    """
    changed: dict[str, list[str]] = {k: [] for k in CATEGORY_MAP}
    deleted: list[str] = []

    for line in lines:
        parts = line.split("\t")
        if len(parts) < 2:
            continue

        status = parts[0]
        path = parts[-1]  # For renames, last element is the new path

        if status.startswith("R"):
            # Rename: old path deleted, new path added
            old_path = parts[1]
            new_path = parts[2] if len(parts) > 2 else parts[1]

            old_cat = _categorise(old_path)
            if old_cat is not None:
                deleted.append(old_path)

            new_cat = _categorise(new_path)
            if new_cat is not None:
                changed[new_cat].append(new_path)
        elif status.startswith("D"):
            cat = _categorise(path)
            if cat is not None:
                deleted.append(path)
        else:
            # A (added), M (modified), C (copied), T (type change)
            cat = _categorise(path)
            if cat is not None:
                changed[cat].append(path)

    # Sort for deterministic output
    for cat in changed:
        changed[cat].sort()
    deleted.sort()

    return changed, deleted


def _build_full_output(head_sha: str) -> dict:
    """Build output for full mode (all components)."""
    all_files = _list_all_components()
    changed: dict[str, list[str]] = {k: [] for k in CATEGORY_MAP}

    for path in all_files:
        cat = _categorise(path)
        if cat is not None:
            changed[cat].append(path)

    for cat in changed:
        changed[cat].sort()

    total = sum(len(v) for v in changed.values())

    return {
        "mode": "full",
        "base_sha": None,
        "head_sha": head_sha,
        "changed": changed,
        "deleted": [],
        "total_changed": total,
    }


def _build_incremental_output(base_sha: str, head_sha: str) -> dict:
    """Build output for incremental mode (diff since last upgrade)."""
    diff_lines = _diff_names(base_sha, head_sha)
    changed, deleted = _parse_diff_lines(diff_lines)
    total = sum(len(v) for v in changed.values())

    return {
        "mode": "incremental",
        "base_sha": base_sha,
        "head_sha": head_sha,
        "changed": changed,
        "deleted": deleted,
        "total_changed": total,
    }


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_diff(full: bool) -> int:
    """Main diff command: output changed components as JSON."""
    try:
        head_sha = _get_head_sha()
    except subprocess.CalledProcessError as exc:
        print(f"error: failed to get HEAD SHA: {exc}", file=sys.stderr)
        return 1

    if full:
        output = _build_full_output(head_sha)
    else:
        state = _read_state()
        base_sha = state.get("last_upgrade_sha")

        if not base_sha or not _sha_exists(base_sha):
            # First run or stale SHA — fall back to full mode
            output = _build_full_output(head_sha)
        elif base_sha == head_sha:
            # No changes since last upgrade
            output = {
                "mode": "incremental",
                "base_sha": base_sha,
                "head_sha": head_sha,
                "changed": {k: [] for k in CATEGORY_MAP},
                "deleted": [],
                "total_changed": 0,
            }
        else:
            output = _build_incremental_output(base_sha, head_sha)

    print(json.dumps(output, indent=2))
    return 0


def cmd_record() -> int:
    """Record current HEAD SHA and timestamp in state.json."""
    try:
        head_sha = _get_head_sha()
    except subprocess.CalledProcessError as exc:
        print(f"error: failed to get HEAD SHA: {exc}", file=sys.stderr)
        return 1

    state = _read_state()
    state["last_upgrade_sha"] = head_sha
    state["last_upgrade_timestamp"] = datetime.now(timezone.utc).isoformat()

    try:
        _write_state(state)
    except OSError as exc:
        print(f"error: failed to write state: {exc}", file=sys.stderr)
        return 1

    output = {
        "recorded": True,
        "sha": head_sha,
        "timestamp": state["last_upgrade_timestamp"],
        "state_file": str(STATE_FILE),
    }
    print(json.dumps(output, indent=2))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect components changed since last system upgrade.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="List all components instead of diffing against last upgrade SHA.",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Record current HEAD SHA as the last upgrade point in ~/.claude/state.json.",
    )
    args = parser.parse_args()

    if args.record:
        return cmd_record()
    return cmd_diff(full=args.full)


if __name__ == "__main__":
    sys.exit(main())
