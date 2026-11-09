"""Route-fit self-report: parse the banner, score it, find the agent's reply.

Every /do-dispatched agent is asked (``scripts/build-dispatch.py``
``INJ_ROUTE_FIT``) to close its reply with one line:

    route-fit: ok
    route-fit: wrong-agent | wrong-skill | needs-coordinator | underspecified

Two hooks read it, because the reply arrives at two different events:

- Foreground dispatch: ``PostToolUse:Agent`` carries the reply.
  ``routing-decision-recorder.py`` scores it there.
- Background dispatch: ``PostToolUse:Agent`` fires at launch and carries only
  a launch receipt (``status: async_launched``, no reply). The reply arrives at
  ``SubagentStop``. ``routing-outcome-recorder.py`` scores it there, joined to
  the route key through ``routing_outcome_state.register_async_dispatch``.

Before the second path existed, 304 of 304 sampled /do dispatches were
background launches, so no verdict was ever recorded.
"""

import json
import os
import re

# Anchored to a WHOLE line (^...$, MULTILINE) so the banner spec quoted mid-prose
# is not a verdict; the LAST match wins because the banner is the final line.
_ROUTE_FIT_NEGATIVE = ("wrong-agent", "wrong-skill", "needs-coordinator", "underspecified")
_ROUTE_FIT_RE = re.compile(
    r"^\s*(?:[-*>`\s]*)route-fit:\s*(ok|wrong-agent|wrong-skill|needs-coordinator|underspecified)\s*`?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Bytes read from the end of an agent transcript when the SubagentStop event
# carries no final message. The banner is the reply's last line.
_TRANSCRIPT_TAIL_BYTES = 256 * 1024


def parse_route_fit(output: str) -> str | None:
    """Read the route-fit verdict off the agent's output, or None.

    None means "no verdict": banner absent, or malformed (a value outside the
    enum, or trailing prose on the line). Parse-only and silent, exactly like
    the rightsizing banner — a missing or broken banner must never affect a
    dispatch, and must never be guessed at.
    """
    if not output or "route-fit:" not in output.lower():
        return None
    verdicts = _ROUTE_FIT_RE.findall(output)
    return verdicts[-1].lower() if verdicts else None


def record_route_fit(
    output: str,
    key: str,
    session_id: str | None = None,
    decision_id: str | None = None,
) -> str | None:
    """(D) Score one route-fit verdict for ``key``. Returns the verdict, or None.

    ASYMMETRIC BY DESIGN — the whole point of the signal.

      negative verdict => STRONG evidence: apply_outcome(FAILURE) decays the
        route's confidence, exactly as a tool error or a user rejection does.
      `ok`             => WEAK evidence: apply_outcome(NEUTRAL) is a no-op on
        confidence. It records the basis counter (so the verdict is countable)
        and boosts NOTHING.

    Rationale: the agent grading the fit was handed the wrong domain
    instructions in precisely the case we care about, and an agent that has
    just spent a session on a task will rationalize that it was the right one
    to do it. A self-report is therefore credible when it says "this was not
    mine" and worthless when it says "this was mine". So the signal is wired to
    move only AGAINST the router, never to flatter it. Under the old metric —
    success inferred from the absence of a complaint — a timid general-purpose
    fallback scored identically to a correct specialist; a signal that could
    boost on self-declared `ok` would reproduce that exact failure.

    Caller MUST have written the decision row for ``key`` first (apply_outcome
    is a no-op on a missing row).

    A negative verdict resolves the dispatch: its pending entry is discarded
    (matched by ``decision_id``), so the next-turn finalizer neither decays the
    route a second time nor overwrites the verdict on the decision row.
    """
    verdict = parse_route_fit(output)
    if verdict is None:
        return None

    from routing_outcome_score import FAILURE, NEUTRAL, apply_outcome

    negative = verdict in _ROUTE_FIT_NEGATIVE
    basis = f"route_fit:{verdict}"
    apply_outcome(key, FAILURE if negative else NEUTRAL, basis=basis)

    if negative:
        # Surface the verdict on the decision row so `evidence-route-context`
        # shows WHY a route decayed. NEGATIVES ONLY: this is a second commit
        # (~3ms) and it buys diagnosis of the cases you actually investigate.
        # On the common `ok` path it would cost every dispatch for a row that
        # says nothing happened. Best-effort — the basis counter above is the
        # durable record.
        try:
            from learning_db_v2 import update_evidence_route_outcome

            update_evidence_route_outcome(
                route_key=key,
                session_id=session_id or None,
                outcome="failure",
                outcome_basis=basis,
                decision_id=decision_id or None,
            )
        except Exception:
            pass
        if decision_id:
            try:
                from routing_outcome_state import discard_pending_outcome

                discard_pending_outcome(session_id or "", decision_id)
            except Exception:
                pass
        if session_id:
            # The finalizer's repeat-dispatch weak boost needs "no intervening
            # failure" for this key; a negative verdict is one.
            try:
                from routing_outcome_state import record_outcome_history

                record_outcome_history(session_id, {key: "failure"})
            except Exception:
                pass
    return verdict


def _text_of(content: object) -> str:
    """Flatten message content (a string, or a list of content blocks) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(p for p in parts if isinstance(p, str))
    return ""


def _last_assistant_text(transcript_path: str) -> str:
    """Text of the last assistant message in a JSONL transcript. "" on any error.

    Reads only the final ``_TRANSCRIPT_TAIL_BYTES`` so a long transcript costs
    one bounded read.
    """
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - _TRANSCRIPT_TAIL_BYTES))
            tail = f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    for line in reversed(tail.splitlines()):
        if '"assistant"' not in line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue  # the first line of the tail may be cut mid-record
        if not isinstance(entry, dict) or entry.get("type") != "assistant":
            continue
        message = entry.get("message")
        text = _text_of(message.get("content")) if isinstance(message, dict) else ""
        if text.strip():
            return text
    return ""


def subagent_final_text(event: dict) -> str:
    """The finished subagent's reply, from a SubagentStop event. "" if absent.

    Prefers the event's ``last_assistant_message``. Falls back to the tail of
    ``agent_transcript_path`` for Claude Code versions that omit it. Never reads
    ``transcript_path``: on SubagentStop that is the parent session.
    """
    message = event.get("last_assistant_message")
    text = _text_of(message.get("content") if isinstance(message, dict) else message)
    if text.strip():
        return text
    path = event.get("agent_transcript_path")
    if isinstance(path, str) and path:
        return _last_assistant_text(path)
    return ""
