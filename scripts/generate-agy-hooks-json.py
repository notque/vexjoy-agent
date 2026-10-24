#!/usr/bin/env python3
"""Generate Antigravity CLI (agy) hooks.json from scripts/agy-hooks-allowlist.txt.

Antigravity CLI hooks.json schema (agy-customizations/docs/hooks.md):
  - Top-level keys are hook group names (e.g., "vexjoy-agent"), each with `"enabled": true`.
  - SessionStart, PreInvocation, PostInvocation, Stop: FLAT list of handler objects
    `[{"type": "command", "command": "...", "timeout": 10}]` (no matcher wrapper).
  - PreToolUse, PostToolUse: GROUPED list of matcher blocks
    `[{"matcher": "run_command", "hooks": [{"type": "command", "command": "...", "timeout": 10}]}]`.

Usage:
    python3 scripts/generate-agy-hooks-json.py --allowlist scripts/agy-hooks-allowlist.txt --dry-run
    python3 scripts/generate-agy-hooks-json.py --allowlist scripts/agy-hooks-allowlist.txt --output ~/.gemini/config/hooks.json
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

FLAT_EVENTS = ("SessionStart", "PreInvocation", "PostInvocation", "Stop")
GROUPED_EVENTS = ("PreToolUse", "PostToolUse")
EVENT_ORDER = ("SessionStart", "PreInvocation", "PostInvocation", "PreToolUse", "PostToolUse", "Stop")
ALL_KNOWN_EVENTS = frozenset(EVENT_ORDER)
FAILURE_POLICIES = frozenset({"open", "closed"})
HOOK_GROUP_NAME = "vexjoy-agent"
DEFAULT_TIMEOUT = 15


def parse_allowlist(text: str) -> list[dict[str, Any]]:
    """Parse allowlist text into validated entry dicts."""
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str | None]] = set()

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"Line {lineno}: missing ':' separator in {raw!r}.")
        event_part, rest = line.split(":", 1)
        event = event_part.strip()
        rest_parts = rest.strip().split()
        if not rest_parts:
            raise ValueError(f"Line {lineno}: missing filename after ':' in {raw!r}.")
        filename = rest_parts[0]
        if event not in ALL_KNOWN_EVENTS:
            raise ValueError(f"Line {lineno}: unknown Antigravity event {event!r}.")
        if not filename.endswith(".py") or "/" in filename or "\\" in filename:
            raise ValueError(f"Line {lineno}: filename must be a bare .py hook name, got {filename!r}.")

        metadata: dict[str, str] = {}
        for token in rest_parts[1:]:
            if "=" not in token:
                raise ValueError(f"Line {lineno}: metadata token {token!r} must be key=value.")
            k, v = token.split("=", 1)
            if k not in {"matcher", "failure", "force_unique"}:
                raise ValueError(f"Line {lineno}: unknown metadata key {k!r}.")
            if not v:
                raise ValueError(f"Line {lineno}: empty value for {k!r}.")
            metadata[k] = v

        if "failure" not in metadata:
            raise ValueError(f"Line {lineno}: missing required failure=open|closed metadata.")
        failure_policy = metadata["failure"]
        if failure_policy not in FAILURE_POLICIES:
            raise ValueError(f"Line {lineno}: invalid failure policy {failure_policy!r}.")

        matcher = metadata.get("matcher")
        if event in FLAT_EVENTS and matcher is not None:
            raise ValueError(f"Line {lineno}: {event} is a flat event in Antigravity and cannot have matcher=...")
        if event in GROUPED_EVENTS and not matcher:
            raise ValueError(f"Line {lineno}: {event} requires matcher=... in Antigravity.")

        dedup_key = (event, filename, matcher)
        if dedup_key in seen:
            raise ValueError(f"Line {lineno}: duplicate registration {event}:{filename} (matcher={matcher}).")
        seen.add(dedup_key)

        entries.append(
            {
                "event": event,
                "filename": filename,
                "matcher": matcher,
                "failure_policy": failure_policy,
            }
        )
    return entries


def validate_hook_files(entries: list[dict[str, Any]], source_hooks_dir: Path) -> None:
    """Verify agy-hook-adapter.py and every allowlisted hook exist in source_hooks_dir."""
    required = {"agy-hook-adapter.py", *(entry["filename"] for entry in entries)}
    missing = sorted(fname for fname in required if not (source_hooks_dir / fname).is_file())
    if missing:
        raise ValueError(f"Missing Antigravity hook source files in {source_hooks_dir}: {', '.join(missing)}")


def _build_command(
    agy_hooks_dir: str,
    entry: dict[str, Any],
    *,
    drain_deferred: bool = False,
) -> str:
    parts = [
        "python3",
        shlex.quote(f"{agy_hooks_dir}/agy-hook-adapter.py"),
        "--hook",
        shlex.quote(f"{agy_hooks_dir}/{entry['filename']}"),
        "--event",
        shlex.quote(entry["event"]),
        "--failure-policy",
        shlex.quote(entry["failure_policy"]),
    ]
    if entry.get("matcher"):
        parts.extend(["--matcher", shlex.quote(entry["matcher"])])
    if drain_deferred:
        parts.append("--drain-deferred")
    return " ".join(parts)


def build_hooks_json(
    entries: list[dict[str, Any]],
    agy_hooks_dir: str | None = None,
    source_hooks_dir: Path | None = None,
    hook_group_name: str = HOOK_GROUP_NAME,
) -> dict[str, Any]:
    """Build the Antigravity hooks.json structure."""
    if agy_hooks_dir is None:
        agy_hooks_dir = os.path.join(os.environ.get("HOME", "~"), ".gemini", "hooks")
    if source_hooks_dir is None:
        source_hooks_dir = Path(__file__).resolve().parent.parent / "hooks"
    validate_hook_files(entries, source_hooks_dir)

    group_obj: dict[str, Any] = {"enabled": True}

    for event in EVENT_ORDER:
        event_entries = [e for e in entries if e["event"] == event]
        if not event_entries:
            continue

        if event in FLAT_EVENTS:
            flat_handlers: list[dict[str, Any]] = []
            for idx, entry in enumerate(event_entries):
                drain = event == "PreInvocation" and idx == 0
                flat_handlers.append(
                    {
                        "type": "command",
                        "command": _build_command(agy_hooks_dir, entry, drain_deferred=drain),
                        "timeout": DEFAULT_TIMEOUT,
                    }
                )
            group_obj[event] = flat_handlers
        else:
            by_matcher: dict[str, list[dict[str, Any]]] = {}
            for entry in event_entries:
                m = str(entry["matcher"])
                by_matcher.setdefault(m, []).append(entry)
            matcher_blocks: list[dict[str, Any]] = []
            for matcher in sorted(by_matcher):
                hooks_list = [
                    {
                        "type": "command",
                        "command": _build_command(agy_hooks_dir, entry),
                        "timeout": DEFAULT_TIMEOUT,
                    }
                    for entry in by_matcher[matcher]
                ]
                matcher_blocks.append({"matcher": matcher, "hooks": hooks_list})
            group_obj[event] = matcher_blocks

    return {hook_group_name: group_obj}


def merge_hooks_json(existing: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    """Merge generated hook group(s) into existing hooks.json, preserving user groups."""
    merged = dict(existing) if isinstance(existing, dict) else {}
    merged.update(generated)
    return merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Antigravity CLI hooks.json from an allowlist.")
    parser.add_argument(
        "--allowlist",
        default=str(Path(__file__).resolve().parent / "agy-hooks-allowlist.txt"),
        help="Path to the Antigravity hooks allowlist file.",
    )
    parser.add_argument(
        "--output",
        default=os.path.join(os.environ.get("HOME", "~"), ".gemini", "config", "hooks.json"),
        help="Path to write hooks.json (default: ~/.gemini/config/hooks.json).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print JSON to stdout instead of writing to disk.")
    parser.add_argument(
        "--agy-hooks-dir",
        default=None,
        help="Directory where hooks live at runtime (default: $HOME/.gemini/hooks).",
    )
    parser.add_argument(
        "--source-hooks-dir",
        default=str(Path(__file__).resolve().parent.parent / "hooks"),
        help="Source hooks directory used to verify hook files exist.",
    )
    args = parser.parse_args(argv)

    allowlist_path = Path(args.allowlist)
    if not allowlist_path.is_file():
        print(f"Error: allowlist file not found: {allowlist_path}", file=sys.stderr)
        return 1

    try:
        entries = parse_allowlist(allowlist_path.read_text(encoding="utf-8"))
        result = build_hooks_json(
            entries,
            agy_hooks_dir=args.agy_hooks_dir,
            source_hooks_dir=Path(args.source_hooks_dir),
        )
    except Exception as exc:
        print(f"Error generating Antigravity hooks.json: {exc}", file=sys.stderr)
        return 1

    output_json = json.dumps(result, indent=2)
    if args.dry_run:
        print(output_json)
        return 0

    output_path = Path(args.output)
    if output_path.exists():
        try:
            existing_data = json.loads(output_path.read_text(encoding="utf-8"))
            if isinstance(existing_data, dict):
                existing_data.update(result)
                output_json = json.dumps(existing_data, indent=2)
        except Exception:
            pass
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = output_path.with_suffix(f".bak.{timestamp}")
        try:
            backup_path.write_bytes(output_path.read_bytes())
            old_backups = sorted(output_path.parent.glob(f"{output_path.stem}.bak.*"))
            for old in old_backups[:-5]:
                try:
                    old.unlink()
                except OSError:
                    pass
        except OSError:
            pass

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"Error writing {output_path}: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
