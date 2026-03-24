#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PostToolUse Hook: Review Findings Capture

Captures review findings from subagent (Agent tool) results and records
them to learning.db for cross-session knowledge retention.

Watches for severity-tagged findings (CRITICAL, HIGH, MUST-FIX) and
verdict markers (NEEDS_CHANGES, FAILURES_FOUND, ISSUES_FOUND) in
Agent tool output.

Design Principles:
- SILENT output (records to DB, no context injection)
- Non-blocking (always exits 0)
- Fast execution (<50ms target)
- Only processes Agent tool results
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import empty_output
from learning_db_v2 import record_learning
from stdin_timeout import read_stdin

EVENT_NAME = "PostToolUse"

# Severity header patterns — match lines like "### CRITICAL: some finding"
SEVERITY_HEADER_RE = re.compile(
    r"###\s+(CRITICAL|HIGH|MEDIUM|MUST-FIX|SHOULD-FIX)\s*:\s*(.+)",
    re.IGNORECASE,
)

# Verdict patterns indicating review found issues
VERDICT_PATTERNS = [
    re.compile(r"VERDICT\s*:\s*NEEDS_CHANGES", re.IGNORECASE),
    re.compile(r"VERDICT\s*:\s*FAILURES_FOUND", re.IGNORECASE),
    re.compile(r"VERDICT\s*:\s*ISSUES_FOUND", re.IGNORECASE),
    re.compile(r"\*\*Status\*\*\s*:\s*ISSUES\s+FOUND", re.IGNORECASE),
]


def has_review_findings(text: str) -> bool:
    """Check if text contains any review finding patterns.

    Args:
        text: Agent tool result text to scan.

    Returns:
        True if severity headers or verdict markers are present.
    """
    if SEVERITY_HEADER_RE.search(text):
        return True
    return any(p.search(text) for p in VERDICT_PATTERNS)


def extract_findings(text: str) -> dict[str, int | list[str]]:
    """Extract severity counts and first 3 finding summaries from text.

    Args:
        text: Agent tool result text containing review findings.

    Returns:
        Dict with severity counts and list of finding summaries.
    """
    counts: dict[str, int] = {
        "CRITICAL": 0,
        "HIGH": 0,
        "MEDIUM": 0,
        "MUST-FIX": 0,
        "SHOULD-FIX": 0,
    }
    summaries: list[str] = []

    for match in SEVERITY_HEADER_RE.finditer(text):
        severity = match.group(1).upper()
        summary = match.group(2).strip()

        if severity in counts:
            counts[severity] += 1

        if len(summaries) < 3:
            summaries.append(summary[:200])

    return {
        "critical": counts["CRITICAL"],
        "high": counts["HIGH"],
        "medium": counts["MEDIUM"],
        "must_fix": counts["MUST-FIX"],
        "should_fix": counts["SHOULD-FIX"],
        "summaries": summaries,
    }


def main() -> None:
    """Process PostToolUse events for Agent tool review findings.

    Flow:
    1. Read stdin JSON, check tool_name == "Agent"
    2. Scan tool_result for review finding patterns
    3. Extract severity counts and finding summaries
    4. Record to learning.db
    5. Exit silently (no context injection)
    """
    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            return

        event = json.loads(event_data)

        # Only process Agent tool results
        tool_name = event.get("tool_name", "")
        if tool_name != "Agent":
            return

        # Get tool result text
        tool_result = event.get("tool_result", "")
        if isinstance(tool_result, dict):
            tool_result = tool_result.get("output", "")
        if not isinstance(tool_result, str) or not tool_result:
            return

        # Check for review finding patterns
        if not has_review_findings(tool_result):
            return

        # Extract findings
        findings = extract_findings(tool_result)
        critical_count = findings["critical"]
        high_count = findings["high"]
        medium_count = findings["medium"]
        must_fix_count = findings["must_fix"]
        should_fix_count = findings["should_fix"]
        summaries = findings["summaries"]

        # Build findings summary for DB storage
        summary_parts = []
        if critical_count:
            summary_parts.append(f"{critical_count} CRITICAL")
        if high_count:
            summary_parts.append(f"{high_count} HIGH")
        if medium_count:
            summary_parts.append(f"{medium_count} MEDIUM")
        if must_fix_count:
            summary_parts.append(f"{must_fix_count} MUST-FIX")
        if should_fix_count:
            summary_parts.append(f"{should_fix_count} SHOULD-FIX")

        findings_header = ", ".join(summary_parts) if summary_parts else "issues found"
        findings_detail = "; ".join(summaries) if summaries else "review flagged issues"
        findings_summary = f"{findings_header}: {findings_detail}"

        # Generate dedup key from summary content
        key_hash = hashlib.md5(findings_summary.encode()).hexdigest()[:8]

        # Source detail with counts
        source_detail = f"{critical_count}C/{high_count}H/{medium_count}M findings"

        # Record to learning.db
        record_learning(
            topic="review-findings",
            key=f"review-{key_hash}",
            value=findings_summary,
            category="review",
            source="hook:review-capture",
            source_detail=source_detail,
        )

        # Silent output — learning recorded to DB, not injected into context
        empty_output(EVENT_NAME).print_and_exit()

    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[review-capture] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
