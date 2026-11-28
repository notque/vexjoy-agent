#!/usr/bin/env python3
"""Composable prompt constraint presets for /do, /d, /prompt, and build-dispatch.

Presets are short standalone flags (for example ``--strict-scope`` or
``--local-only``) that inject deterministic constraint rules into a dispatch
Task Specification and surface an explicit banner line in the dispatch header.

Stdlib only. Cross-platform safe.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

PRESETS: dict[str, dict[str, Any]] = {
    "strict-scope": {
        "name": "strict-scope",
        "flag": "--strict-scope",
        "summary": "Restrict edits strictly to the stated outcome",
        "constraint": (
            "Touch only the files and symbols required for the stated outcome; "
            "make zero opportunistic refactors or unrelated edits."
        ),
    },
    "spike": {
        "name": "spike",
        "flag": "--spike",
        "summary": "Time-boxed prototype or investigation with disposable changes",
        "constraint": (
            "Time-boxed prototype or investigation; prioritize answering the question "
            "with evidence and keep changes disposable/unmerged."
        ),
    },
    "review-only": {
        "name": "review-only",
        "flag": "--review-only",
        "summary": "Read-only inspection with file:line evidence",
        "constraint": (
            "Read-only inspection and findings with file:line evidence; "
            "make zero file edits, commits, or mutating commands."
        ),
    },
    "ship": {
        "name": "ship",
        "flag": "--ship",
        "summary": "Deliver end-to-end through tests, PR, and green CI",
        "constraint": (
            "Deliver end-to-end: implement, run full relevant tests and linters, "
            "verify exit codes, open/update PR, and wait for green CI before merging."
        ),
    },
    "local-only": {
        "name": "local-only",
        "flag": "--local-only",
        "summary": "Keep all changes local with zero remote mutations",
        "constraint": ("Keep all changes local: make zero git pushes, PR creations, merges, or remote mutations."),
    },
}

_PRESET_NAMES_ALT = "|".join(re.escape(name) for name in PRESETS)
# Match standalone --<preset> flags bounded by string edges or whitespace.
# Does not match inside words/paths (foo--ship, path/--ship/x) or longer flags (--shipping, --ship=1).
_FLAG_RE = re.compile(rf"(?:(?<=^)|(?<=\s))--({_PRESET_NAMES_ALT})(?=$|\s)", re.IGNORECASE)


def extract_presets(text: str) -> tuple[list[str], str]:
    """Extract standalone preset flags from *text* and return ``(names, cleaned_text)``.

    Flags are matched case-insensitively, normalized to lowercase preset names,
    and deduplicated in first-seen order. Non-standalone occurrences (substrings,
    file paths, longer flags such as ``--shipping`` or ``foo--ship``) stay untouched.
    """
    if not text:
        return [], text

    found: list[str] = []
    seen: set[str] = set()
    for match in _FLAG_RE.finditer(text):
        name = match.group(1).lower()
        if name not in seen:
            seen.add(name)
            found.append(name)

    if not found:
        return [], text

    cleaned_lines: list[str] = []
    for line in text.splitlines():
        if _FLAG_RE.search(line):
            updated = _FLAG_RE.sub("", line)
            updated = re.sub(r"[ \t]{2,}", " ", updated).strip()
            if updated:
                cleaned_lines.append(updated)
        else:
            cleaned_lines.append(line)

    return found, "\n".join(cleaned_lines)


def _normalize_preset_name(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValueError(f"preset name must be a string, got {type(raw).__name__}")
    name = raw.strip().lower()
    if name.startswith("--"):
        name = name[2:]
    if name not in PRESETS:
        valid = ", ".join(PRESETS)
        raise ValueError(f"unknown prompt preset {raw!r}; valid presets: {valid}")
    return name


def resolve_presets(names: list[str] | None = None, text: str = "") -> list[dict[str, str]]:
    """Validate explicit *names*, merge with flags extracted from *text*, and deduplicate.

    Explicit names appear before extracted flags; first occurrence wins for order.
    Raises ``ValueError`` on any unknown preset name or invalid *names* container.
    """
    ordered: list[str] = []
    seen: set[str] = set()

    if names is not None:
        if isinstance(names, (str, bytes)) or not isinstance(names, (list, tuple)):
            raise ValueError("preset names must be a list of strings")
        for raw in names:
            name = _normalize_preset_name(raw)
            if name not in seen:
                seen.add(name)
                ordered.append(name)

    if text:
        extracted, _cleaned = extract_presets(text)
        for name in extracted:
            if name not in seen:
                seen.add(name)
                ordered.append(name)

    return [
        {
            "name": str(PRESETS[name]["name"]),
            "flag": str(PRESETS[name]["flag"]),
            "summary": str(PRESETS[name]["summary"]),
            "constraint": str(PRESETS[name]["constraint"]),
        }
        for name in ordered
    ]


def format_preset_constraints(presets: list[dict[str, str]]) -> str:
    """Format resolved presets as a compact constraint string for Task Specification."""
    if not presets:
        return ""
    return " ".join(f"[{preset['name']}] {preset['constraint']}" for preset in presets)


def format_preset_banner(presets: list[dict[str, str]]) -> str:
    """Format resolved presets as a visible dispatch header line."""
    if not presets:
        return ""
    flags = ", ".join(preset["flag"] for preset in presets)
    return f"Prompt presets: {flags}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect and extract composable prompt constraint presets.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List all available prompt presets")
    group.add_argument("--extract", metavar="TEXT", help="Extract preset flags from a prompt string")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    args = parser.parse_args(argv)

    if args.list:
        items = resolve_presets(list(PRESETS))
        if args.json_output:
            sys.stdout.write(json.dumps({"presets": items}, indent=2) + "\n")
        else:
            for item in items:
                sys.stdout.write(f"{item['flag']}: {item['constraint']}\n")
        return 0

    names, cleaned = extract_presets(args.extract)
    resolved = resolve_presets(names)
    payload = {
        "presets": names,
        "cleaned_text": cleaned,
        "banner": format_preset_banner(resolved),
        "constraints": format_preset_constraints(resolved),
        "resolved": resolved,
    }
    if args.json_output:
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    else:
        if payload["banner"]:
            sys.stdout.write(payload["banner"] + "\n")
            sys.stdout.write(f"Constraints: {payload['constraints']}\n")
        else:
            sys.stdout.write("Prompt presets: none\n")
        sys.stdout.write(f"Cleaned text: {cleaned}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
