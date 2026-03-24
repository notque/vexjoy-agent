#!/usr/bin/env python3
"""Record a routing misroute to learning.db.

Records when /do routed to the wrong agent/skill so the data can be
analyzed later to improve routing tables.

Usage:
    python3 scripts/record-misroute.py \
        --request "original request text" \
        --routed-to "agent:skill that was selected" \
        --should-have-been "correct agent:skill" \
        --reason "brief explanation"
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
LEARNING_DB_SCRIPT = SCRIPTS_DIR / "learning-db.py"


def build_value(request: str, routed_to: str, should_have_been: str, reason: str) -> str:
    """Build the learning value string from misroute details."""
    return f"request: {request} | routed_to: {routed_to} | should_have_been: {should_have_been} | reason: {reason}"


def build_key(routed_to: str, should_have_been: str) -> str:
    """Build a unique key from the routing pair."""
    return f"{routed_to}->should-be-{should_have_been}"


def record_misroute(request: str, routed_to: str, should_have_been: str, reason: str) -> int:
    """Record a misroute via the learning-db.py CLI.

    Returns:
        Exit code from the subprocess call.
    """
    value = build_value(request, routed_to, should_have_been, reason)
    key = build_key(routed_to, should_have_been)

    cmd = [
        sys.executable,
        str(LEARNING_DB_SCRIPT),
        "record",
        "routing",
        key,
        value,
        "--category",
        "misroute",
        "--tags",
        "misroute,routing-feedback",
        "--source",
        "manual:misroute-feedback",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"Recorded misroute: {routed_to} -> should have been {should_have_been}")
    else:
        print(f"Error recording misroute: {result.stderr.strip()}", file=sys.stderr)

    return result.returncode


def main() -> None:
    """Parse arguments and record the misroute."""
    parser = argparse.ArgumentParser(
        description="Record a routing misroute to learning.db",
    )
    parser.add_argument(
        "--request",
        required=True,
        help="The original user request text",
    )
    parser.add_argument(
        "--routed-to",
        required=True,
        help="The agent:skill that was incorrectly selected",
    )
    parser.add_argument(
        "--should-have-been",
        required=True,
        help="The correct agent:skill that should have been selected",
    )
    parser.add_argument(
        "--reason",
        required=True,
        help="Brief explanation of why the route was wrong",
    )

    args = parser.parse_args()
    exit_code = record_misroute(args.request, args.routed_to, args.should_have_been, args.reason)
    sys.exit(exit_code)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(0)
