#!/usr/bin/env python3
"""
Generate ~/.codex/hooks.json from a curated allowlist file.

The allowlist format is one entry per line: EVENT:filename [matcher]
Comments (lines starting with #) and blank lines are ignored.

Usage:
    python3 scripts/generate-codex-hooks-json.py --allowlist scripts/codex-hooks-allowlist.txt
    python3 scripts/generate-codex-hooks-json.py --allowlist scripts/codex-hooks-allowlist.txt --dry-run
    python3 scripts/generate-codex-hooks-json.py --allowlist scripts/codex-hooks-allowlist.txt --output /tmp/hooks.json
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Events that require a matcher (Codex requires tool name to filter on).
EVENTS_REQUIRING_MATCHER = {"PreToolUse", "PostToolUse"}

# Events where matcher should default to "startup|resume" when omitted.
EVENTS_WITH_DEFAULT_MATCHER = {"SessionStart"}

# Events where matcher field is omitted entirely when not specified.
EVENTS_WITHOUT_MATCHER = {"UserPromptSubmit", "Stop"}

# All known Codex events, in the canonical output order.
EVENT_ORDER = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"]

ALL_KNOWN_EVENTS = set(EVENT_ORDER)


def parse_allowlist(text: str) -> list[dict]:
    """Parse allowlist text into a list of entry dicts.

    Args:
        text: Contents of the allowlist file (not a path; the raw text).

    Returns:
        List of dicts with keys: event, filename, matcher (str or None).

    Raises:
        ValueError: On malformed lines (includes line number in message).
    """
    entries: list[dict] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if ":" not in line:
            raise ValueError(f"Line {lineno}: missing ':' separator in {raw!r}. Expected EVENT:filename [matcher].")

        event_part, rest = line.split(":", 1)
        event = event_part.strip()
        rest_parts = rest.strip().split()

        if not rest_parts:
            raise ValueError(f"Line {lineno}: missing filename after ':' in {raw!r}.")

        filename = rest_parts[0]
        matcher: str | None = rest_parts[1] if len(rest_parts) > 1 else None

        if event not in ALL_KNOWN_EVENTS:
            known = ", ".join(sorted(ALL_KNOWN_EVENTS))
            raise ValueError(f"Line {lineno}: unknown event {event!r}. Known events: {known}.")

        if event in EVENTS_REQUIRING_MATCHER and matcher is None:
            raise ValueError(
                f"Line {lineno}: {event} requires a matcher (e.g. 'Bash') because Codex "
                f"only fires {event} for named tools. Add 'Bash' after the filename: "
                f"'{event}:{filename} Bash'."
            )

        entries.append({"event": event, "filename": filename, "matcher": matcher})

    return entries


def build_hooks_json(entries: list[dict], codex_hooks_dir: str | None = None) -> dict:
    """Build the Codex hooks.json structure from parsed allowlist entries.

    Args:
        entries: List of entry dicts from parse_allowlist().
        codex_hooks_dir: Directory where hooks will reside. Defaults to $HOME/.codex/hooks.

    Returns:
        Dict representing the full hooks.json structure.
    """
    if codex_hooks_dir is None:
        codex_hooks_dir = os.path.join(os.environ.get("HOME", "~"), ".codex", "hooks")

    # Group by (event, effective_matcher) so shared matchers collapse into one block.
    # Key: (event, effective_matcher_or_None)
    groups: dict[tuple[str, str | None], list[str]] = {}

    for entry in entries:
        event = entry["event"]
        raw_matcher = entry["matcher"]
        filename = entry["filename"]

        # Determine the effective matcher for grouping and output.
        if event in EVENTS_WITH_DEFAULT_MATCHER and raw_matcher is None:
            effective_matcher: str | None = "startup|resume"
        elif event in EVENTS_WITHOUT_MATCHER:
            effective_matcher = None  # Omit matcher field entirely.
        else:
            effective_matcher = raw_matcher  # Already validated non-None for requiring events.

        key = (event, effective_matcher)
        groups.setdefault(key, [])
        groups[key].append(filename)

    if not groups:
        return {"hooks": {}}

    # Build output dict with events in canonical order.
    hooks_by_event: dict[str, list[dict]] = {}

    for event in EVENT_ORDER:
        # Collect all matcher groups for this event, sorted by matcher for determinism.
        event_groups = {k: v for k, v in groups.items() if k[0] == event}
        if not event_groups:
            continue

        sorted_keys = sorted(event_groups.keys(), key=lambda k: (k[1] is None, k[1] or ""))
        event_blocks: list[dict] = []

        for key in sorted_keys:
            _, matcher = key
            filenames = event_groups[key]

            hook_entries = [
                {
                    "type": "command",
                    "command": f'python3 "{codex_hooks_dir}/{fname}"',
                    "timeout": 600,
                }
                for fname in filenames
            ]

            block: dict = {}
            if matcher is not None:
                block["matcher"] = matcher
            block["hooks"] = hook_entries

            event_blocks.append(block)

        hooks_by_event[event] = event_blocks

    return {"hooks": hooks_by_event}


def main() -> None:
    """Parse CLI arguments, read the allowlist, and write or print hooks.json.

    Exits with code 0 on success, 1 on any error.
    """
    parser = argparse.ArgumentParser(
        description="Generate ~/.codex/hooks.json from a curated allowlist file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--allowlist", required=True, help="Path to the allowlist file.")
    parser.add_argument(
        "--output",
        default=os.path.join(os.environ.get("HOME", "~"), ".codex", "hooks.json"),
        help="Path to write hooks.json (default: ~/.codex/hooks.json).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print JSON to stdout instead of writing to disk.",
    )
    parser.add_argument(
        "--codex-hooks-dir",
        default=None,
        help="Directory where hooks will live (default: $HOME/.codex/hooks).",
    )

    args = parser.parse_args()

    allowlist_path = Path(args.allowlist)
    if not allowlist_path.exists():
        print(f"Error: allowlist file not found: {allowlist_path}", file=sys.stderr)
        sys.exit(1)

    try:
        text = allowlist_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error reading allowlist: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        entries = parse_allowlist(text)
    except ValueError as exc:
        print(f"Error parsing allowlist: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        result = build_hooks_json(entries, codex_hooks_dir=args.codex_hooks_dir)
    except Exception as exc:
        print(f"Error building hooks JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    output_json = json.dumps(result, indent=2)

    if args.dry_run:
        print(output_json)
        return

    output_path = Path(args.output)

    # Back up existing file before overwriting.
    if output_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = output_path.with_suffix(f".bak.{timestamp}")
        try:
            backup_path.write_bytes(output_path.read_bytes())
        except OSError as exc:
            print(f"Warning: could not create backup {backup_path}: {exc}", file=sys.stderr)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"Error writing {output_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
