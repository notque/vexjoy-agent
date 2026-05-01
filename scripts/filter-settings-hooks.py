#!/usr/bin/env python3
"""Remove disabled hook entries from a Claude Code settings.json hooks block.

Reads a settings.json file, prunes any hook entry whose ``command`` references
a disabled hook filename (matched against the path component after ``/hooks/``),
and writes the result back. Empty matcher groups are dropped; events with no
remaining groups are removed from ``hooks``.

Usage:
    python3 scripts/filter-settings-hooks.py \\
        --input  ~/.claude/settings.json \\
        --disabled disabled-hooks.txt \\
        --output ~/.claude/settings.json

If --output is omitted, the filtered JSON is written to stdout. The --disabled
file is one filename per line (blank lines and # comments ignored). Pass
/dev/stdin to receive the list via pipe.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


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


def hook_filename_from_command(command: str) -> str | None:
    marker = "/hooks/"
    if marker not in command:
        return None
    tail = command.split(marker, 1)[1]
    return tail.split('"', 1)[0].split("'", 1)[0].split()[0]


def filter_hooks(settings: dict[str, Any], disabled: set[str]) -> dict[str, Any]:
    settings = dict(settings)
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return settings

    filtered_hooks: dict[str, Any] = {}
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            filtered_hooks[event] = groups
            continue
        filtered_groups: list[Any] = []
        for group in groups:
            if not isinstance(group, dict):
                filtered_groups.append(group)
                continue
            entries = group.get("hooks")
            if not isinstance(entries, list):
                filtered_groups.append(group)
                continue
            kept = []
            for entry in entries:
                command = entry.get("command", "") if isinstance(entry, dict) else ""
                filename = hook_filename_from_command(command)
                if filename and filename in disabled:
                    continue
                kept.append(entry)
            if kept:
                next_group = dict(group)
                next_group["hooks"] = kept
                filtered_groups.append(next_group)
        if filtered_groups:
            filtered_hooks[event] = filtered_groups

    settings["hooks"] = filtered_hooks
    return settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--disabled", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None, help="Default: stdout.")
    args = parser.parse_args()

    try:
        settings = json.loads(args.input.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"error: cannot read {args.input}: {exc}", file=sys.stderr)
        return 2

    disabled = read_disabled(args.disabled)
    if not disabled:
        # Nothing to filter — write input unchanged.
        out = settings
    else:
        out = filter_hooks(settings, disabled)

    rendered = json.dumps(out, indent=2) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(rendered, encoding="utf-8")
    os.replace(tmp, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
