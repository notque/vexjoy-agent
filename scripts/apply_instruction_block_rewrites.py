#!/usr/bin/env python3
"""Apply verified block-level rewrites back into repo files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def block_sha(block_text: str) -> str:
    return hashlib.sha256(block_text.encode("utf-8")).hexdigest()


def replace_block(
    path: Path,
    line_start: int,
    line_end: int,
    expected_sha: str,
    replacement: str,
) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = line_start - 1
    end = line_end
    current = "\n".join(lines[start:end]).rstrip()
    if block_sha(current) != expected_sha:
        return False

    replacement_lines = replacement.rstrip().splitlines()
    new_lines = lines[:start] + replacement_lines + lines[end:]
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply verified block-level instruction rewrites")
    parser.add_argument("--input", required=True, help="Path to rewrite result JSON")
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    rewrites = data["rewrites"] if isinstance(data, dict) else data
    applied = 0
    skipped: list[dict[str, object]] = []

    for rewrite in rewrites:
        path = REPO_ROOT / rewrite["file"]
        changed = replace_block(
            path=path,
            line_start=int(rewrite["line_start"]),
            line_end=int(rewrite["line_end"]),
            expected_sha=str(rewrite["block_sha256"]),
            replacement=str(rewrite["replacement"]),
        )
        if changed:
            applied += 1
        else:
            skipped.append(
                {
                    "id": rewrite["id"],
                    "file": rewrite["file"],
                    "line_start": rewrite["line_start"],
                    "reason": "block-hash-mismatch",
                }
            )

    print(json.dumps({"applied": applied, "skipped": skipped}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
