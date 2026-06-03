#!/usr/bin/env python3
"""Generate ~/.reasonix/settings.json from a curated allowlist file.

The allowlist format is one entry per line: EVENT:filename [match]
Comments (lines starting with #) and blank lines are ignored.

Unlike the Codex and Gemini generators, this script writes Reasonix's
NATIVE settings shape — a flat array per event, no nested {hooks: [{type, command, ...}]}.
Reasonix's source (src/hooks.ts) reads:

    {
      "hooks": {
        "PreToolUse": [
          { "match": "Bash|Edit", "command": "python3 ...", "description": "...", "timeout": 5000 }
        ],
        "PostToolUse": [...],
        "UserPromptSubmit": [...],
        "Stop": [...]
      }
    }

UserPromptSubmit and Stop have no `match` field. PreToolUse and PostToolUse
take a single anchored regex over the tool name.

Usage:
    python3 scripts/generate-reasonix-settings-hooks.py --allowlist scripts/reasonix-hooks-allowlist.txt
    python3 scripts/generate-reasonix-settings-hooks.py --allowlist scripts/reasonix-hooks-allowlist.txt --dry-run
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Events Reasonix supports. See DeepSeek-Reasonix src/hooks.ts: HOOK_EVENTS.
EVENT_ORDER = ["PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop"]

# Events whose entries MUST carry a match (anchored regex over tool name).
EVENTS_REQUIRING_MATCH = {"PreToolUse", "PostToolUse"}

# Events whose entries MUST NOT carry a match field.
EVENTS_WITHOUT_MATCH = {"UserPromptSubmit", "Stop"}

ALL_KNOWN_EVENTS = set(EVENT_ORDER)

# Per-hook default timeout in ms. Mirrors src/hooks.ts DEFAULT_TIMEOUTS_MS
# (PreToolUse/UserPromptSubmit=5s, PostToolUse/Stop=30s) but the allowlist
# may override per-file.
DEFAULT_TIMEOUTS_MS = {
    "PreToolUse": 5000,
    "PostToolUse": 30000,
    "UserPromptSubmit": 5000,
    "Stop": 30000,
}


def parse_allowlist(text: str) -> list[dict]:
    """Parse allowlist text into a list of entry dicts.

    Args:
        text: Contents of the allowlist file (raw text).

    Returns:
        List of dicts with keys: event, filename, match (str or None).

    Raises:
        ValueError: On malformed lines (line number in message).
    """
    entries: list[dict] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if ":" not in line:
            raise ValueError(f"Line {lineno}: missing ':' separator in {raw!r}. Expected EVENT:filename [match].")

        event_part, rest = line.split(":", 1)
        event = event_part.strip()
        rest_parts = rest.strip().split()

        if not rest_parts:
            raise ValueError(f"Line {lineno}: missing filename after ':' in {raw!r}.")

        filename = rest_parts[0]
        match: str | None = rest_parts[1] if len(rest_parts) > 1 else None

        if event not in ALL_KNOWN_EVENTS:
            known = ", ".join(sorted(ALL_KNOWN_EVENTS))
            raise ValueError(f"Line {lineno}: unknown event {event!r}. Reasonix supports: {known}.")

        if event in EVENTS_REQUIRING_MATCH and not match:
            raise ValueError(
                f"Line {lineno}: {event} requires a match regex (e.g. 'Bash|Edit'). "
                f"Add one after the filename: '{event}:{filename} Bash|Edit'."
            )

        if event in EVENTS_WITHOUT_MATCH and match:
            raise ValueError(f"Line {lineno}: {event} does not accept a match field. Drop the match from this line.")

        entries.append({"event": event, "filename": filename, "match": match})

    return entries


def build_settings(entries: list[dict], reasonix_hooks_dir: str | None = None) -> dict:
    """Build the Reasonix settings.json structure from parsed allowlist entries.

    Args:
        entries: List of entry dicts from parse_allowlist().
        reasonix_hooks_dir: Directory where hooks will reside.
            Defaults to $HOME/.reasonix/hooks.

    Returns:
        Dict representing the full settings.json (the "hooks" key only;
        Reasonix currently only consumes the "hooks" key).
    """
    if reasonix_hooks_dir is None:
        reasonix_hooks_dir = os.path.join(os.environ.get("HOME", "~"), ".reasonix", "hooks")

    # Group by (event, match) so a shared match collapses into one entry.
    # Each group becomes a single Reasonix hook entry whose command runs all filenames.
    groups: dict[tuple[str, str | None], list[str]] = {}
    for entry in entries:
        key = (entry["event"], entry["match"])
        groups.setdefault(key, []).append(entry["filename"])

    if not groups:
        return {"hooks": {}}

    # Reasonix runs hooks sequentially with `&&`-style chaining via the shell;
    # we emit a single `command` string that runs every file in the group.
    # This keeps the same effective behavior as separate hook entries while
    # emitting one entry per match group (matches Reasonix's flat shape).
    hooks_by_event: dict[str, list[dict]] = {}

    for event in EVENT_ORDER:
        event_keys = sorted(
            (k for k in groups if k[0] == event),
            key=lambda k: (k[1] is None, k[1] or ""),
        )
        if not event_keys:
            continue

        event_blocks: list[dict] = []
        for key in event_keys:
            _, match = key
            filenames = groups[key]
            # Chain filenames with `&&` so an early failure short-circuits.
            chained = " && ".join(f'python3 "{reasonix_hooks_dir}/{fn}"' for fn in filenames)

            block: dict = {
                "command": chained,
                "timeout": DEFAULT_TIMEOUTS_MS[event],
            }
            if match is not None:
                block["match"] = match
            event_blocks.append(block)

        hooks_by_event[event] = event_blocks

    return {"hooks": hooks_by_event}


def main() -> None:
    """Parse CLI arguments, read the allowlist, write settings.json.

    Exits with code 0 on success, 1 on any error.
    """
    parser = argparse.ArgumentParser(
        description="Generate ~/.reasonix/settings.json from a curated allowlist file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--allowlist", required=True, help="Path to the allowlist file.")
    parser.add_argument(
        "--output",
        default=os.path.join(os.environ.get("HOME", "~"), ".reasonix", "settings.json"),
        help="Path to settings.json (default: ~/.reasonix/settings.json).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print JSON to stdout instead of writing to disk.",
    )
    parser.add_argument(
        "--reasonix-hooks-dir",
        default=None,
        help="Directory where hooks will live (default: $HOME/.reasonix/hooks).",
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
        result = build_settings(entries, reasonix_hooks_dir=args.reasonix_hooks_dir)
    except Exception as exc:
        print(f"Error building settings: {exc}", file=sys.stderr)
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
        tmp = str(output_path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(output_json)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmp, str(output_path))
    except OSError as exc:
        print(f"Error writing {output_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
