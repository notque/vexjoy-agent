#!/usr/bin/env python3
"""
Deterministic cohort gate for retro-knowledge injection A/B test.

Splits sessions into two cohorts based on session ID:
- Odd hash prefix → inject retro knowledge (treatment)
- Even hash prefix → skip injection (control)

Imported by retro-knowledge-injector.py hook. Not run directly.
"""

import sys


def should_inject(session_id: str) -> bool:
    """Determine if this session should receive retro-knowledge injection.

    Uses first 8 hex chars of session_id for deterministic cohort assignment.
    Odd values → inject (treatment group), even values → skip (control group).

    Args:
        session_id: Hex string session identifier.

    Returns:
        True if session should receive retro injection.
    """
    cohort_value = int(session_id[:8], 16)
    inject = cohort_value % 2 != 0
    label = "on" if inject else "off"
    print(f"retro-cohort: {label}", file=sys.stderr)
    return inject
