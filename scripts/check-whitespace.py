#!/usr/bin/env python3
"""Check agent and skill markdown files for blank lines and trailing spaces that inflate token counts."""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")

REPO_ROOT = Path(__file__).parent.parent

_DEFAULT_PATTERNS = [
    "agents/**/*.md",
    "skills/**/*.md",
]


@dataclass
class Violation:
    path: str
    line_no: int
    kind: str
    detail: str


def check_file(path: Path) -> list[Violation]:
    """Return all whitespace violations in a single file. Pure check, no side effects."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    try:
        rel = str(path.relative_to(REPO_ROOT))
    except ValueError:
        rel = str(path)

    violations: list[Violation] = []
    lines = content.splitlines(keepends=False)

    i = 0
    in_fence = False
    while i < len(lines):
        # Track code fence state — skip structural checks inside fences
        if _FENCE_RE.match(lines[i]):
            in_fence = not in_fence
            i += 1
            continue

        # Consecutive blank lines: count run of empty lines (skip inside fences)
        if lines[i] == "" and not in_fence:
            run = 0
            j = i
            while j < len(lines) and lines[j] == "":
                run += 1
                j += 1
            if run >= 2:
                violations.append(
                    Violation(
                        path=rel,
                        line_no=i + 1,
                        kind="consecutive_blank_lines",
                        detail=f"{run} consecutive blank lines",
                    )
                )
            i = j
            continue

        # Trailing whitespace
        stripped = lines[i].rstrip(" \t")
        if len(stripped) < len(lines[i]):
            trailing = len(lines[i]) - len(stripped)
            violations.append(
                Violation(
                    path=rel,
                    line_no=i + 1,
                    kind="trailing_whitespace",
                    detail=f"{trailing} trailing char(s)",
                )
            )

        i += 1

    return violations


def fix_file(path: Path) -> int:
    """Fix trailing whitespace and consecutive blank lines in place.

    Returns the count of fixes applied. Does NOT fix indented headers.
    """
    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0

    lines = original.splitlines(keepends=False)
    fixed_lines: list[str] = []
    fixes = 0

    i = 0
    in_fence = False
    while i < len(lines):
        line = lines[i]

        # Track code fence state — preserve blank lines inside fences
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            fixed_lines.append(line)
            i += 1
            continue

        # Collapse runs of 2+ blank lines into a single blank line (outside fences only)
        if line == "" and not in_fence:
            run = 0
            j = i
            while j < len(lines) and lines[j] == "":
                run += 1
                j += 1
            fixed_lines.append("")
            if run >= 2:
                fixes += run - 1
            i = j
            continue

        # Strip trailing whitespace
        stripped = line.rstrip(" \t")
        if len(stripped) < len(line):
            fixes += 1
            line = stripped

        fixed_lines.append(line)
        i += 1

    result = "\n".join(fixed_lines)

    # Preserve original trailing newline behaviour
    if original.endswith("\n"):
        result += "\n"

    if result != original:
        path.write_text(result, encoding="utf-8")

    return fixes


def _collect_paths(path_args: list[str]) -> list[Path]:
    """Resolve CLI path arguments to a list of Path objects."""
    paths: list[Path] = []
    seen: set[Path] = set()
    for arg in path_args:
        p = Path(arg)
        if p.is_file():
            if p not in seen:
                seen.add(p)
                paths.append(p)
        elif p.is_dir():
            for candidate in sorted(p.rglob("*.md")):
                if candidate not in seen:
                    seen.add(candidate)
                    paths.append(candidate)
        else:
            print(f"WARNING: path not found: {arg}", file=sys.stderr)
    return paths


def _collect_default_paths() -> list[Path]:
    """Collect all agent and skill markdown files from repo root."""
    seen: set[Path] = set()
    paths: list[Path] = []
    for pattern in _DEFAULT_PATTERNS:
        for p in sorted(REPO_ROOT.glob(pattern)):
            if p.is_file() and p not in seen:
                seen.add(p)
                paths.append(p)
    return paths


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Check agent/skill markdown files for blank lines and trailing spaces that inflate Opus token counts.",
        epilog="Exit codes: 0=clean, 1=violations found, 2=usage error. --fix auto-corrects violations in place.",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix trailing whitespace and consecutive blank lines in place",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        metavar="PATH",
        help="Files or directories to scan (default: agents/**/*.md and skills/**/*.md)",
    )
    args = parser.parse_args()

    if args.paths:
        targets = _collect_paths(args.paths)
    else:
        targets = _collect_default_paths()

    if not targets:
        print("No files to scan.", file=sys.stderr)
        sys.exit(2)

    if args.fix:
        total_fixes = 0
        for target in targets:
            n = fix_file(target)
            if n:
                print(f"fixed {target}: {n} fix(es) applied")
                total_fixes += n
        if total_fixes:
            print(f"\nTotal fixes applied: {total_fixes}")
        else:
            print("No fixes needed.")
        sys.exit(0)

    all_violations: list[Violation] = []
    for target in targets:
        all_violations.extend(check_file(target))

    if all_violations:
        for v in all_violations:
            print(f"{v.path}:{v.line_no}: {v.kind} ({v.detail})")
        print(f"\n{len(all_violations)} violation(s) found in {len(targets)} file(s) scanned.")
        sys.exit(1)
    else:
        print(f"clean — {len(targets)} file(s) scanned, no violations.")
        sys.exit(0)


if __name__ == "__main__":
    main()
