#!/usr/bin/env python3
"""Filter scripts/codex-hooks-allowlist.txt by removing disabled hook filenames.

Reads an allowlist file in the format used by codex-hooks-allowlist.txt:

    # comment
    EVENT:filename [matcher]

and writes a copy to stdout (or --output) with any line whose filename appears
in the disabled list removed. Comments and blank lines are preserved.

Usage:
    python3 scripts/filter-codex-allowlist.py \\
        --input  scripts/codex-hooks-allowlist.txt \\
        --disabled disabled-hooks.txt \\
        --output filtered-allowlist.txt

The --disabled file is one filename per line (blank lines and # comments
ignored). May be /dev/stdin to receive the list via pipe.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def read_disabled(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line)
    return out


def filter_allowlist(text: str, disabled: set[str]) -> str:
    kept: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            kept.append(raw)
            continue
        # Format: EVENT:filename [matcher]
        if ":" not in stripped:
            kept.append(raw)
            continue
        rest = stripped.split(":", 1)[1].strip()
        filename = rest.split()[0] if rest else ""
        if filename in disabled:
            continue
        kept.append(raw)
    # Preserve trailing newline if input had one.
    suffix = "\n" if text.endswith("\n") else ""
    return "\n".join(kept) + suffix


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--disabled", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None, help="Default: stdout.")
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    disabled = read_disabled(args.disabled)
    filtered = filter_allowlist(args.input.read_text(encoding="utf-8"), disabled)

    if args.output is None:
        sys.stdout.write(filtered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(filtered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
