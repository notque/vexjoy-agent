#!/usr/bin/env python3
"""Deterministic prefilter and safe bulk fixer for instruction-mode joy-check issues.

This script intentionally handles only exact, allowlisted rewrites that are
mechanical enough to trust repo-wide. Everything else is reported as backlog for
manual or LLM-assisted reframing.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_PATTERNS = [
    "agents/**/*.md",
    "agents/**/references/*.md",
    "skills/**/SKILL.md",
    "skills/**/references/*.md",
    "CLAUDE.md",
]
SAFE_REWRITES = {
    "## Anti-Patterns": "## Patterns to Detect and Fix",
    "## Common Anti-Patterns": "## Common Patterns to Detect and Fix",
    "## Anti-Pattern Catalog": "## Pattern Catalog",
    "## Operational Anti-Patterns": "## Operational Patterns to Detect and Fix",
    "### FORBIDDEN Patterns (HARD GATE)": "### Hard Gate Patterns",
    "### Anti-Pattern Checklist: What NOT To Do": "### Pattern Checklist: What to Detect and Fix",
}
PRIMARY_PATTERNS = [
    ("NEVER", re.compile(r"\bNEVER\b")),
    ("do NOT", re.compile(r"\b[Dd]o NOT\b")),
    ("must NOT", re.compile(r"\bmust NOT\b")),
    ("FORBIDDEN", re.compile(r"\bFORBIDDEN\b")),
    ("Don't", re.compile(r"^\s*[-*]?\s*Don't\b")),
    ("Avoid", re.compile(r"^\s*#{1,6}.*Avoid|^\s*[-*]?\s*Avoid\b", re.IGNORECASE)),
    ("Anti-Pattern", re.compile(r"^\s*#{1,6}.*[Aa]nti-[Pp]attern")),
    ("What NOT To Do", re.compile(r"What NOT To Do")),
]


@dataclass
class Finding:
    file: str
    line: int
    pattern: str
    text: str
    safe_fix: str | None = None


def iter_targets() -> list[Path]:
    seen: set[Path] = set()
    targets: list[Path] = []
    for pattern in SCAN_PATTERNS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if path.is_file() and path not in seen:
                seen.add(path)
                targets.append(path)
    return targets


def scan_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    in_fence = False
    for i, line in enumerate(lines, 1):
        if line.startswith("```"):
            in_fence = not in_fence
        if in_fence or line.lstrip().startswith(">"):
            continue
        safe_fix = SAFE_REWRITES.get(line.strip())
        for label, rx in PRIMARY_PATTERNS:
            if rx.search(line):
                try:
                    rel = str(path.relative_to(REPO_ROOT))
                except ValueError:
                    rel = str(path)
                findings.append(Finding(rel, i, label, line.strip(), safe_fix))
                break
    return findings


def apply_safe_rewrites(path: Path) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    changed = 0
    in_fence = False
    for idx, line in enumerate(lines):
        if line.startswith("```"):
            in_fence = not in_fence
        if in_fence:
            continue
        stripped = line.strip()
        replacement = SAFE_REWRITES.get(stripped)
        if replacement and stripped != replacement:
            prefix = line[: len(line) - len(line.lstrip())]
            lines[idx] = prefix + replacement
            changed += 1
    if changed:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan and apply safe instruction-mode joy-check rewrites")
    parser.add_argument("--apply-safe-fixes", action="store_true", help="Rewrite exact allowlisted headings in place")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Emit JSON report")
    parser.add_argument("--output", metavar="PATH", help="Write JSON report to file")
    args = parser.parse_args()

    all_findings: list[Finding] = []
    applied_files = 0
    applied_rewrites = 0
    targets = iter_targets()
    if args.apply_safe_fixes:
        for target in targets:
            changed = apply_safe_rewrites(target)
            if changed:
                applied_files += 1
                applied_rewrites += changed
    for target in targets:
        all_findings.extend(scan_file(target))

    safe_fixable = sum(1 for finding in all_findings if finding.safe_fix)
    payload = {
        "total": len(all_findings),
        "safe_fixable": safe_fixable,
        "applied_files": applied_files,
        "applied_rewrites": applied_rewrites,
        "findings": [asdict(finding) for finding in all_findings],
        "safe_rewrites": SAFE_REWRITES,
    }
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if args.json_output:
        print(json.dumps(payload, indent=2))
    elif not args.output:
        print(f"total findings: {len(all_findings)}")
        print(f"safe-fixable findings: {safe_fixable}")
        print(f"applied files: {applied_files}")
        print(f"applied rewrites: {applied_rewrites}")
        for finding in all_findings[:50]:
            suffix = f" -> {finding.safe_fix}" if finding.safe_fix else ""
            print(f"{finding.file}:{finding.line} [{finding.pattern}] {finding.text}{suffix}")
        if len(all_findings) > 50:
            print(f"... {len(all_findings) - 50} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
