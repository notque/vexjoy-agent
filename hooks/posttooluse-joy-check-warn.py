#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PostToolUse Hook: Joy-Check Framing Validation

After Write or Edit operations on any .md file, scans for prohibition-led
framing violations and warns inline. Advisory hook — always exits 0.

Shift-left companion to the CI gate (PR #634 zero-allowlist policy).
Patterns mirror scripts/validate_positive_instruction_docs.py.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

# Mirror patterns from validate_positive_instruction_docs.py
NEGATIVE_PATTERNS = [
    ("Anti-Pattern", re.compile(r"[Aa]nti-[Pp]atterns?")),
    ("FORBIDDEN", re.compile(r"\bFORBIDDEN\b")),
    ("NEVER", re.compile(r"\bNEVER\b")),
    ("do NOT", re.compile(r"\b[Dd]o NOT\b")),
    ("must NOT", re.compile(r"\bmust NOT\b")),
    ("Don't", re.compile(r"^-?\s*Don't\b")),
    (
        "Avoid",
        re.compile(
            r"^\s*#{1,6}\s+Avoid\b|^\s*#{1,6}.*\bAvoid\s*$|^\s*[-*]?\s*Avoid\b",
            re.IGNORECASE,
        ),
    ),
]


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return (line_no, pattern_label, line_text) for each violation."""
    violations: list[tuple[int, str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return violations

    in_fence = False
    for i, line in enumerate(lines, 1):
        if line.startswith("```"):
            in_fence = not in_fence
        if in_fence or line.lstrip().startswith(">"):
            continue
        for label, rx in NEGATIVE_PATTERNS:
            if rx.search(line):
                violations.append((i, label, line.strip()))
                break
    return violations


def main() -> None:
    try:
        event_data = read_stdin(timeout=2)
        if not event_data.strip():
            return
        event = json.loads(event_data)

        tool_input = event.get("tool_input", {})
        file_path = tool_input.get("file_path", "")

        if not file_path or not file_path.endswith(".md"):
            return

        path = Path(file_path)
        if not path.exists():
            return

        violations = scan_file(path)
        if not violations:
            return

        print(f"[joy-check] Framing violation(s) in {path.name}:")
        for line_no, label, text in violations[:5]:
            print(f"  line {line_no} [{label}]: {text[:80]}")
        if len(violations) > 5:
            print(f"  ... {len(violations) - 5} more")
        print("[joy-check] Run: python3 scripts/validate_positive_instruction_docs.py")
        print("[joy-check] Fix before push — CI gate blocks on violations.")

    except Exception as e:
        print(f"[joy-check] hook error: {e}", file=sys.stderr)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
