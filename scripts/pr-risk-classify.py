#!/usr/bin/env python3
"""PR risk classification — deterministic path + size signals.

Maps a diff's file list and line counts to a risk level (low/medium/high)
and a size tier (small/medium/large). Emits a split recommendation when the
change exceeds 800 lines.

Policy: skills/process/pr-workflow/references/pr-risk-policy.md
Sizing:  scripts/right-size-review.py (tier data reused, not duplicated)

Usage:
    python3 scripts/pr-risk-classify.py --base main
    python3 scripts/pr-risk-classify.py --base main --head HEAD
    echo "10 5 hooks/pre-check.py" | python3 scripts/pr-risk-classify.py --stdin

Output: JSON {risk, size_tier, total_lines, file_count, recommend_split,
              reasons, high_risk_files, review_lane}.
Exit 0 always (warn-only per PHILOSOPHY.md Warn-Only Gates).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

# --- Path risk patterns ------------------------------------------------------

# HIGH: infrastructure, safety hooks, install, sync, settings, root policy.
_HIGH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^hooks/"),
    re.compile(r"^\.github/"),
    re.compile(r"^install\.sh$"),
    re.compile(r"^scripts/sync-"),
    re.compile(r"^\.claude/settings\.json$"),
    re.compile(r"^\.claude/settings\.local\.json$"),
    re.compile(r"^CLAUDE\.md$"),
]

# LOW: docs, ADRs, non-root markdown (excluding SKILL.md), INDEX.json,
# skill reference markdown.
_LOW_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^docs/"),
    re.compile(r"^adr/"),
    re.compile(r"^.+/INDEX\.json$"),
    re.compile(r"^INDEX\.json$"),
    re.compile(r"^skills/.+/references/.*\.md$"),
    re.compile(r"^agents/.+/references/.*\.md$"),
]


# --- Size thresholds ---------------------------------------------------------

_SIZE_SMALL = 200
_SIZE_LARGE = 800  # Tier 3+ from right-size-review; triggers recommend_split.


def classify_path(path: str) -> str:
    """Return 'high', 'low', or 'medium' for a single file path."""
    for pat in _HIGH_PATTERNS:
        if pat.search(path):
            return "high"
    for pat in _LOW_PATTERNS:
        if pat.search(path):
            return "low"
    return "medium"


def size_tier(total_lines: int) -> str:
    """Map total changed lines to a size label."""
    if total_lines <= _SIZE_SMALL:
        return "small"
    if total_lines <= _SIZE_LARGE:
        return "medium"
    return "large"


def classify(
    files: list[tuple[str, int]],
) -> dict:
    """Classify risk from a list of (path, added+deleted lines) tuples.

    Returns the full result dict ready for JSON serialization.
    """
    if not files:
        return {
            "risk": "low",
            "size_tier": "small",
            "total_lines": 0,
            "file_count": 0,
            "recommend_split": False,
            "reasons": ["empty diff"],
            "high_risk_files": [],
            "review_lane": "quick-single",
        }

    total_lines = sum(lines for _, lines in files)
    file_count = len(files)
    st = size_tier(total_lines)

    high_files: list[str] = []
    path_risks: list[str] = []
    for path, _ in files:
        pr = classify_path(path)
        path_risks.append(pr)
        if pr == "high":
            high_files.append(path)

    has_high = len(high_files) > 0
    all_low = all(r == "low" for r in path_risks)

    reasons: list[str] = []

    # Risk resolution (policy rules 1-6).
    if has_high:
        risk = "high"
        reasons.append(f"high-risk paths: {', '.join(high_files[:5])}")
        if len(high_files) > 5:
            reasons.append(f"...and {len(high_files) - 5} more high-risk files")
    elif all_low:
        if st == "small":
            risk = "low"
            reasons.append(f"{file_count} files changed, all in low-risk paths")
        elif st == "medium":
            risk = "medium"
            reasons.append("all low-risk paths but size escalates to medium")
        else:
            risk = "high"
            reasons.append("all low-risk paths but size escalates to high (801+ lines)")
    else:
        risk = "medium"
        reasons.append(f"{file_count} files changed across medium-risk paths")

    recommend_split = total_lines > _SIZE_LARGE
    if recommend_split:
        reasons.append(f"{total_lines} lines changed exceeds 800-line ceiling; consider splitting")

    # Review lane.
    lane_map = {
        "low": "quick-single",
        "medium": "full-roster",
        "high": "full-roster-plus-sign-off",
    }

    return {
        "risk": risk,
        "size_tier": st,
        "total_lines": total_lines,
        "file_count": file_count,
        "recommend_split": recommend_split,
        "reasons": reasons,
        "high_risk_files": high_files,
        "review_lane": lane_map[risk],
    }


# --- Git integration ---------------------------------------------------------


def _git_numstat(base: str | None, head: str) -> list[tuple[str, int]]:
    """Parse git diff --numstat into (path, added+deleted) tuples."""
    if base:
        cmd = ["git", "diff", "--numstat", f"{base}...{head}"]
    else:
        cmd = ["git", "diff", "--numstat", head]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return _parse_numstat(out)


def _parse_numstat(raw: str) -> list[tuple[str, int]]:
    """Parse raw numstat output into (path, total_changed_lines) tuples.

    Binary files show as '-\t-\tpath'; count those as 0 lines.
    """
    result: list[tuple[str, int]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 2)
        if len(parts) < 3:
            continue
        added_s, deleted_s, path = parts
        try:
            added = int(added_s)
            deleted = int(deleted_s)
        except ValueError:
            # Binary file: '-' for added/deleted.
            added, deleted = 0, 0
        result.append((path, added + deleted))
    return result


def _parse_stdin() -> list[tuple[str, int]]:
    """Read numstat-format lines from stdin."""
    return _parse_numstat(sys.stdin.read())


# --- CLI ---------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="PR risk classification.")
    parser.add_argument("--base", help="git base ref (e.g. main)")
    parser.add_argument("--head", default="HEAD", help="git head ref (default: HEAD)")
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="read numstat-format lines from stdin instead of running git",
    )
    args = parser.parse_args()

    if args.stdin:
        files = _parse_stdin()
    else:
        if args.base is None:
            print(
                "warning: no --base given; diffing against the working tree, not a branch",
                file=sys.stderr,
            )
        files = _git_numstat(args.base, args.head)

    result = classify(files)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
