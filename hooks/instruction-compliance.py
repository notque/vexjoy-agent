#!/usr/bin/env python3
# hook-version: 1.0.0
"""PostToolUse Hook: Instruction Compliance Measurement

Fires after Agent tool dispatches to check whether MANDATORY instructions
(M01-M09 from ADR instruction-skip-rate-measurement) were followed.

Records compliance observations to learning.db for skip-rate dashboard.

Design Principles:
- Informational only (always exits 0, never blocks)
- Lightweight string-presence checks (<50ms)
- Multiple signal patterns per instruction for reduced false negatives
"""

import json
import os
import re
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import empty_output, get_session_id, get_tool_output, get_tool_result
from learning_db_v2 import record_instruction_compliance_batch
from stdin_timeout import read_stdin

EVENT_NAME = "PostToolUse"

# ─── Instruction Definitions ─────────────────────────────────────

INSTRUCTIONS: dict[str, dict[str, str | list[re.Pattern[str]]]] = {
    "M01": {
        "name": "Phase Banners",
        "patterns": [
            re.compile(r"##\s*Phase\s+\d", re.IGNORECASE),
            re.compile(r"Phase\s+\d\s*:", re.IGNORECASE),
        ],
    },
    "M03": {
        "name": "Routing Decision",
        "patterns": [
            re.compile(r"^={3,}\s*$", re.MULTILINE),
            re.compile(r"(?:^|\s)ROUTING\s*:", re.IGNORECASE | re.MULTILINE),
            re.compile(r"Selected\s*:", re.IGNORECASE),
        ],
    },
    "M04": {
        "name": "Reference Loading",
        "patterns": [
            re.compile(r"Reference\s+Loading", re.IGNORECASE),
            re.compile(r"reference.*table", re.IGNORECASE),
            re.compile(r"Before\s+starting\s+work", re.IGNORECASE),
            re.compile(r"Load\s+EVERY\s+reference\s+file", re.IGNORECASE),
        ],
    },
    "M05": {
        "name": "Completeness",
        "patterns": [
            re.compile(r"deliver\s+the\s+finished\s+product", re.IGNORECASE),
            re.compile(r"ship\s+the\s+complete\s+thing", re.IGNORECASE),
            re.compile(r"Ship\s+the\s+complete", re.IGNORECASE),
            re.compile(r"Deliver\s+the\s+finished", re.IGNORECASE),
        ],
    },
    "M06": {
        "name": "Density Standard",
        "patterns": [
            re.compile(r"write\s+dense", re.IGNORECASE),
            re.compile(r"high\s+fidelity,?\s+minimum\s+words", re.IGNORECASE),
        ],
    },
}


def check_compliance(text: str) -> dict[str, bool]:
    """Check agent output against all instrumented instructions.

    Args:
        text: Combined agent prompt and output text to scan.

    Returns:
        Dict mapping instruction ID to compliance boolean.
    """
    results: dict[str, bool] = {}
    for instr_id, instr in INSTRUCTIONS.items():
        patterns: list[re.Pattern[str]] = instr["patterns"]  # type: ignore[assignment]
        compliant = any(p.search(text) for p in patterns)
        results[instr_id] = compliant
    return results


def record_compliance_batch(
    results: dict[str, bool],
    session_id: str,
) -> None:
    """Record all instruction compliance observations in one transaction.

    Args:
        results: Dict mapping instruction ID to compliance boolean.
        session_id: Current session identifier.
    """
    records = [(instr_id, compliant, session_id) for instr_id, compliant in results.items()]
    record_instruction_compliance_batch(records)


def main() -> None:
    """Process PostToolUse events for Agent instruction compliance.

    Flow:
    1. Read stdin JSON
    2. Extract agent output text
    3. Check each instruction for compliance signals
    4. Record observations to learning.db
    5. Exit silently (informational, never blocks)
    """
    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            empty_output(EVENT_NAME).print_and_exit()

        event = json.loads(event_data)
        session_id = event.get("session_id") or get_session_id()

        # Extract agent output text
        tool_result = get_tool_result(event)
        if isinstance(tool_result, dict):
            output_text = get_tool_output(tool_result)
        elif isinstance(tool_result, str):
            output_text = tool_result
        else:
            output_text = ""

        # Also check tool_input (agent prompt) for M04/M05/M06
        tool_input = event.get("tool_input", event.get("input", ""))
        if isinstance(tool_input, dict):
            tool_input = json.dumps(tool_input)
        elif not isinstance(tool_input, str):
            tool_input = ""

        combined_text = f"{tool_input}\n{output_text}"

        if not combined_text.strip():
            empty_output(EVENT_NAME).print_and_exit()

        # Check and record compliance for all instructions in one transaction
        results = check_compliance(combined_text)
        record_compliance_batch(results, session_id)

        empty_output(EVENT_NAME).print_and_exit()

    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[instruction-compliance] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
