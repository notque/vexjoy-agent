#!/usr/bin/env python3
"""Shared TypeSafe/Jev presence check for the /d router.

Answers one question: can `jev-route.py` legitimately call the live Jev
endpoint right now? Two independent conditions must both hold — the API key
is present in the environment, and the typesafe plugin is enabled in the
merged Claude Code settings. Neither condition substitutes for the other: a
present key with the plugin disabled is not available, and an enabled plugin
with no key is not available either.

Underscore filename: importable by name, the same convention
`routing_index_merge.py` uses among the hyphen-named routing scripts (which
run as files, not as a package, and shell out to each other instead).
`jev-route.py` imports this module directly.

Usage:
    python3 scripts/jev_router_common.py --check
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

TYPESAFE_PLUGIN_KEY = "typesafe@typesafe-ai"


def _read_json_object(path: Path) -> dict:
    """Read one settings file as a dict. Any failure -> {} (never raises)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _merged_enabled_plugins() -> dict:
    """Merge `enabledPlugins` from settings.json and settings.local.json.

    Local wins on any key present in both (shallow merge). A missing or
    malformed file resolves to {} for that file and never raises.
    """
    global_settings = _read_json_object(Path.home() / ".claude" / "settings.json")
    local_settings = _read_json_object(Path.home() / ".claude" / "settings.local.json")

    global_plugins = global_settings.get("enabledPlugins")
    local_plugins = local_settings.get("enabledPlugins")

    merged: dict = {}
    if isinstance(global_plugins, dict):
        merged.update(global_plugins)
    if isinstance(local_plugins, dict):
        merged.update(local_plugins)
    return merged


def typesafe_available() -> tuple[bool, str]:
    """Return (available, reason).

    available is True only when BOTH hold:
      1. TYPESAFE_API_KEY is set in the environment and non-empty after
         stripping whitespace. The value itself is never returned or logged.
      2. enabledPlugins["typesafe@typesafe-ai"] == True in the merged
         settings (settings.local.json wins over settings.json on conflict).

    Never raises: any failure while reading settings is swallowed and counts
    against availability, not against the caller.
    """
    try:
        api_key = os.environ.get("TYPESAFE_API_KEY", "")
        has_key = bool(api_key.strip())

        plugins = _merged_enabled_plugins()
        plugin_enabled = plugins.get(TYPESAFE_PLUGIN_KEY) is True

        if has_key and plugin_enabled:
            return True, "TYPESAFE_API_KEY set and typesafe@typesafe-ai enabled"
        if not has_key and not plugin_enabled:
            return False, "TYPESAFE_API_KEY unset and typesafe@typesafe-ai not enabled"
        if not has_key:
            return False, "TYPESAFE_API_KEY unset"
        return False, "typesafe@typesafe-ai not enabled in settings"
    except Exception as exc:
        return False, f"presence check error: {type(exc).__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Presence check for the Jev/TypeSafe routing backend.")
    parser.add_argument(
        "--check",
        action="store_true",
        help='Print {"available": bool, "reason": str} as JSON (also the default with no flags).',
    )
    parser.parse_args()

    available, reason = typesafe_available()
    print(json.dumps({"available": available, "reason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
