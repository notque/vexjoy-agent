#!/usr/bin/env python3
# hook-version: 1.0.0
"""PostToolUse Hook: Capture index-router.py output deterministically (Phase 0).

When the Bash tool runs a command containing `index-router.py`, this hook
parses the JSON output and records the routing decision to learning.db.

Captures: force_route result, top candidate name + score, request summary.

ADR: adr/router-observability.md — Phase 0 deterministic hook capture.

Design:
- SILENT always (no stdout output to Claude)
- Non-blocking (always exits 0)
- Fast execution (<50ms target, lazy imports)
- Fail-open (any error = silently return)
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

# Regex to extract --request value (double or single quoted)
_REQUEST_PATTERN = re.compile(r"""--request\s+(?:"([^"]+)"|'([^']+)')""")

# Sanitization: strip API keys, tokens, passwords before storing
_SENSITIVE_PATTERN = re.compile(
    r"(sk_live_|sk_test_|ghp_|gho_|AKIA|password=|token=|secret=)[^\s|]+",
    re.IGNORECASE,
)


def _extract_request(command: str) -> str:
    """Extract and sanitize the --request value from the command string."""
    match = _REQUEST_PATTERN.search(command)
    if not match:
        return ""
    # One of the two capture groups will be non-None
    raw = match.group(1) or match.group(2) or ""
    sanitized = _SENSITIVE_PATTERN.sub(r"\1[REDACTED]", raw)
    return sanitized[:200]


def main() -> None:
    """Parse index-router.py output and record Phase 0 routing decision."""
    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            return

        event = json.loads(event_data)

        # Only process Bash tool calls
        if event.get("tool_name") != "Bash":
            return

        tool_input = event.get("tool_input", {})
        command = tool_input.get("command", "")

        # Only process commands that invoke index-router.py
        if "index-router.py" not in command:
            return

        tool_result = event.get("tool_result", {})

        # Skip error results
        if tool_result.get("is_error", False):
            return

        output = tool_result.get("output", "")
        if not output:
            return

        # Parse JSON output from index-router.py
        router_data = json.loads(output)

        # Extract Phase 0 signals
        force_route_raw = router_data.get("force_route")
        candidates = router_data.get("candidates", [])
        top_candidate = candidates[0] if candidates else {}
        top_name = top_candidate.get("name", "none")
        top_score = top_candidate.get("score", 0.0)

        request_summary = _extract_request(command)

        # force_route is a dict {"skill": "X", "agent": "Y"} or None
        if isinstance(force_route_raw, dict):
            force_skill = force_route_raw.get("skill", "unknown")
            key = f"phase0:{force_skill}"
            tags = ["phase0", "force-route"]
            force_str = force_skill
        elif force_route_raw:
            # Fallback for string type (shouldn't happen but defensive)
            key = f"phase0:{force_route_raw}"
            tags = ["phase0", "force-route"]
            force_str = str(force_route_raw)
        else:
            key = f"phase0:{top_name}"
            tags = ["phase0", "scored"]
            force_str = "none"
        value = (
            f"request: {request_summary} | "
            f"phase0_force: {force_str} | "
            f"phase0_top: {top_name} | "
            f"phase0_score: {top_score}"
        )

        # Lazy import — only loaded when we actually need to record
        from learning_db_v2 import record_learning

        record_learning(
            topic="routing",
            key=key,
            value=value,
            category="routing-decision",
            confidence=0.5,
            tags=tags,
            source="hook:record-routing-phase0",
        )

    except Exception:
        pass  # Silent failure — never block the session
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
