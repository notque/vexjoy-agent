#!/usr/bin/env python3
"""Validate that instructional docs avoid prohibition-led framing."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_PATTERNS = [
    "**/*.md",
]
# Directories excluded from scanning: generated/temp content, virtualenvs,
# git internals, worktree copies, caches. Only .md files are scanned.
EXCLUDED_DIRS = (
    ".git",
    ".claude/worktrees",
    ".pytest_cache",
    "node_modules",
    "venv",
    "venv.312.bak",
    "tmp",
)
NEGATIVE_PATTERNS = [
    ("Anti-Pattern", re.compile(r"[Aa]nti-[Pp]atterns?")),
    ("FORBIDDEN", re.compile(r"\bFORBIDDEN\b")),
    ("NEVER", re.compile(r"\bNEVER\b")),
    ("do NOT", re.compile(r"\b[Dd]o NOT\b")),
    ("must NOT", re.compile(r"\bmust NOT\b")),
    ("Don't", re.compile(r"^-?\s*Don't\b")),
    # Heading: "Avoid" as leading verb ("### Avoid X") or terminal verb ("### X to Avoid").
    # Not matched: "### Prefetch Data to Avoid N+1" — "Avoid" embedded in technical phrase.
    ("Avoid", re.compile(r"^\s*#{1,6}\s+Avoid\b|^\s*#{1,6}.*\bAvoid\s*$|^\s*[-*]?\s*Avoid\b", re.IGNORECASE)),
]
# Only .py scripts that contain patterns as source code are exempt.
# Every .md file must pass — no exceptions.
ALLOWLIST: tuple[str, ...] = ()


@dataclass
class Violation:
    file: str
    line: int
    pattern: str
    text: str


def collect_targets() -> list[Path]:
    """Collect all git-tracked .md files, excluding generated/temp directories."""
    import subprocess

    # Use git ls-files to get only tracked .md files
    result = subprocess.run(
        ["git", "ls-files", "--cached", "*.md", "**/*.md"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    targets: list[Path] = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        if any(line.startswith(d + "/") for d in EXCLUDED_DIRS):
            continue
        path = REPO_ROOT / line
        if path.is_file():
            targets.append(path)
    return sorted(targets)


def should_skip(_path: Path) -> bool:
    # No allowlist — every .md file must pass.
    return False


def scan_file(path: Path) -> list[Violation]:
    violations: list[Violation] = []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    in_fence = False
    rel = str(path.relative_to(REPO_ROOT))
    for i, line in enumerate(lines, 1):
        if line.startswith("```"):
            in_fence = not in_fence
        if in_fence or line.lstrip().startswith(">"):
            continue
        for label, rx in NEGATIVE_PATTERNS:
            if rx.search(line):
                violations.append(Violation(rel, i, label, line.strip()))
                break
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate positive instructional framing")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    violations: list[Violation] = []
    for path in collect_targets():
        if should_skip(path):
            continue
        violations.extend(scan_file(path))

    payload = {"violations": [asdict(item) for item in violations], "count": len(violations)}
    if args.json_output:
        print(json.dumps(payload, indent=2))
    else:
        if violations:
            for item in violations[:100]:
                print(f"{item.file}:{item.line} [{item.pattern}] {item.text}")
            if len(violations) > 100:
                print(f"... {len(violations) - 100} more")
        print(f"count: {len(violations)}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
