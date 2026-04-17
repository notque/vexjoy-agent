#!/usr/bin/env python3
"""Validate that instructional docs avoid prohibition-led framing."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_PATTERNS = [
    "AGENT_TEMPLATE_V2.md",
    "docs/*.md",
    "agents/**/*.md",
    "agents/**/references/*.md",
    "skills/**/SKILL.md",
    "skills/**/references/*.md",
]
NEGATIVE_PATTERNS = [
    ("Anti-Pattern", re.compile(r"^\s*#{1,6}.*[Aa]nti-[Pp]attern")),
    ("FORBIDDEN", re.compile(r"\bFORBIDDEN\b")),
    ("do NOT", re.compile(r"\b[Dd]o NOT\b")),
    ("must NOT", re.compile(r"\bmust NOT\b")),
    ("Avoid", re.compile(r"^\s*#{1,6}.*Avoid|^\s*[-*]?\s*Avoid\b", re.IGNORECASE)),
]
ALLOWLIST = (
    "anti-ai-editor",
    "instruction-rubric.md",
    "detect_negative_instruction_blocks.py",
    "extract_negative_instruction_blocks.py",
    "validate_positive_instruction_docs.py",
    "bulk_fix_instruction_joy.py",
)


@dataclass
class Violation:
    file: str
    line: int
    pattern: str
    text: str


def collect_targets() -> list[Path]:
    seen: set[Path] = set()
    targets: list[Path] = []
    for pattern in SCAN_PATTERNS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if path.is_file() and path not in seen:
                seen.add(path)
                targets.append(path)
    return targets


def should_skip(path: Path) -> bool:
    rel = str(path.relative_to(REPO_ROOT))
    return any(token in rel for token in ALLOWLIST)


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
