#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PostToolUse Hook: Record routing gaps when /do finds no matching agent.

Parses "GAP DETECTED: No match for [domain]" banners from tool output
and persists them to learning.db. On repeated gaps for the same domain,
observation_count increments via record_learning() upsert behavior.

Design Principles:
- Silent when no gap detected (no noise)
- Non-blocking (always exits 0)
- Fast execution (<50ms target)
- Lazy imports to minimize startup cost
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

_GAP_PATTERN = re.compile(r"GAP DETECTED:\s*No match for\s+\[?([^\]\n]+)\]?")


def main():
    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            return

        event = json.loads(event_data)

        # Only process PostToolUse events
        event_type = event.get("hook_event_name") or event.get("type", "")
        if event_type != "PostToolUse":
            return

        # Check tool output for GAP DETECTED banner
        tool_result = event.get("tool_result", {})
        output = tool_result.get("output", "")
        if not isinstance(output, str) or "GAP DETECTED" not in output:
            return

        match = _GAP_PATTERN.search(output)
        if not match:
            return

        domain = match.group(1).strip()
        if not domain:
            return

        # Lazy import
        sys.path.insert(0, str(Path(__file__).parent / "lib"))
        from learning_db_v2 import record_learning

        result = record_learning(
            topic="routing-gap",
            key=domain,
            value=f"No agent matched domain: {domain}",
            category="effectiveness",
            confidence=0.4,
            tags=["routing", "gap", domain],
            source="hook:routing-gap-recorder",
        )

        if result.get("is_new"):
            print(f"[routing-gap] New gap recorded: {domain}")
        else:
            print(f"[routing-gap] Gap repeated: {domain} (x{result.get('observation_count', '?')})")

    except Exception:
        pass  # Silent failure
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
