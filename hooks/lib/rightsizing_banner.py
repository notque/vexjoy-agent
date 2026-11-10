"""Right-sizing banner: parse it and add the review to its tier's running sums.

A review closes its reply with one line:

    rightsizing: tier=3 files=15 packages=4 agents_dispatched=17 findings=2C/3H/5M tokens=84000 wall_clock_s=312

Two hooks read it, because the reply arrives at two different events (the same
split as the route-fit banner, ``route_fit.py``):

- Foreground dispatch: ``PostToolUse:Agent`` carries the reply.
  ``routing-decision-recorder.py`` records it there.
- Background dispatch: ``PostToolUse:Agent`` fires at launch and carries only a
  launch receipt. The reply arrives at ``SubagentStop``.
  ``routing-outcome-recorder.py`` records it there, for agents registered
  through ``routing_outcome_state.register_async_dispatch``.
"""

import re

# The first four fields are required; findings= and the cost fields (tokens=,
# wall_clock_s=) are optional, additive extensions (ADR: review-tier-roi).
# Legacy four-field banners still match.
_RIGHTSIZING_RE = re.compile(
    r"rightsizing:\s*tier=(\d+)\s+files=(\d+)\s+packages=(\d+)\s+agents_dispatched=(\d+)"
    r"(?:\s+findings=(\d+)C/(\d+)H/(\d+)M)?"
    r"(?:\s+tokens=(\d+))?"
    r"(?:\s+wall_clock_s=(\d+))?",
    re.IGNORECASE,
)

DEFAULT_SOURCE = "hook:routing-decision-recorder"


def record_rightsizing(output: str, session_id: str | None = None, source: str = DEFAULT_SOURCE) -> bool:
    """(C) Add one rightsizing review to the tier's running sums. Silent when no banner.

    Returns True when a banner was found and recorded.

    Per-review findings and cost are accumulated into running sums in the
    rightsizing:tier{N} row (`accumulate_rightsizing`) so `learning-db.py
    review-roi` reports a TRUE per-tier mean (sum / count), not the last
    review's sample. findings= and the cost fields are optional: a legacy
    banner (no findings=) bumps the review count only; a "-" cost never enters
    its sum (ADR: review-tier-roi).
    """
    if not output or "rightsizing:" not in output.lower():
        return False
    m = _RIGHTSIZING_RE.search(output)
    if not m:
        return False

    def _int_or_none(s: str | None) -> int | None:
        return int(s) if s is not None and s != "" else None

    from learning_db_v2 import accumulate_rightsizing

    accumulate_rightsizing(
        int(m.group(1)),
        critical=_int_or_none(m.group(5)),
        high=_int_or_none(m.group(6)),
        medium=_int_or_none(m.group(7)),
        tokens=_int_or_none(m.group(8)),
        wall_clock_s=_int_or_none(m.group(9)),
        source=source,
        session_id=session_id or None,
    )
    return True
