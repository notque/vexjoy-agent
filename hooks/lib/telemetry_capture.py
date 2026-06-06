#!/usr/bin/env python3
"""Best-effort telemetry extraction for the routing envelope.

ADR: learning-telemetry-envelope. Isolates the capture logic so the recorder
hook stays thin and these extractors are unit-testable without a subprocess.

Honesty contract: every extractor returns the real value when the source has it,
else None. None is never coerced to 0. A field that the Claude Code runtime does
not yet supply (token_count, wall_clock_ms, sometimes model_id) returns None now
and lights up automatically the day the payload carries it — no hook edit needed.

All functions are exception-safe: they return None / a fallback rather than raise,
so the recorder hook never fails on capture.
"""

import json
import os
import subprocess
from pathlib import Path

# Per-session SHA cache lives here. Overridable in tests via monkeypatch.
_STATE_DIR = Path.home() / ".claude" / "state" / "telemetry"


def _safe_session_name(session_id: str) -> str:
    """Filesystem-safe per-session filename stem."""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (session_id or "default"))
    return safe[:64] or "default"


def _git_rev_parse_head() -> str | None:
    """git rev-parse HEAD, or None on any failure. ~39 ms when it runs."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception:
        return None
    sha = out.stdout.strip()
    return sha or None


def git_sha_cached(session_id: str = "") -> str | None:
    """Return the repo HEAD SHA, cached per session to stay under the hook budget.

    First call per session: subprocess `git rev-parse HEAD` (~39 ms), written to
    a per-session state file. Every later call reads the cache (no subprocess).
    On any error returns None — capture degrades, the hook never fails.
    """
    state = _STATE_DIR / f"{_safe_session_name(session_id)}.json"
    # Cache hit.
    try:
        if state.exists():
            data = json.loads(state.read_text(encoding="utf-8"))
            cached = data.get("git_sha")
            if cached:
                return cached
    except Exception:
        pass  # corrupt cache => recompute

    sha = _git_rev_parse_head()
    # Cache the result (even None-miss is fine; we just won't have a file).
    if sha:
        try:
            _STATE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = state.with_suffix(".json.tmp")
            tmp.write_text(json.dumps({"git_sha": sha}), encoding="utf-8")
            tmp.replace(state)  # atomic
        except Exception:
            pass  # cache write best-effort
    return sha


def model_id_from(event: dict) -> str | None:
    """Model id from the event, else env, else None.

    Order: event['model'] -> event['tool_input']['model'] -> $ANTHROPIC_MODEL ->
    $CLAUDE_MODEL -> None. The payload did not carry a model id this session, so
    env/None is the realistic path today.
    """
    try:
        if not isinstance(event, dict):
            event = {}
        m = event.get("model")
        if m:
            return str(m)
        ti = event.get("tool_input")
        if isinstance(ti, dict) and ti.get("model"):
            return str(ti["model"])
        return os.environ.get("ANTHROPIC_MODEL") or os.environ.get("CLAUDE_MODEL") or None
    except Exception:
        return None


def token_count_from(event: dict) -> int | None:
    """Total token count if the event ever carries usage, else None.

    Reads event['usage']['total_tokens'] (or ['tokens']). The current
    PostToolUse payload omits usage, so this returns None today and starts
    populating the day the runtime adds it — no hook edit needed.
    """
    try:
        if not isinstance(event, dict):
            return None
        usage = event.get("usage")
        if isinstance(usage, dict):
            for field in ("total_tokens", "tokens", "total"):
                v = usage.get(field)
                if isinstance(v, (int, float)):
                    return int(v)
        return None
    except Exception:
        return None


def wall_clock_ms_from(event: dict) -> int | None:
    """Wall-clock ms if the event carries timestamps, else None.

    Reads event['duration_ms'] directly, or computes end-start from
    event['started_at']/['ended_at'] when both are epoch-millis numbers. The
    current payload omits timing, so this returns None today.
    """
    try:
        if not isinstance(event, dict):
            return None
        d = event.get("duration_ms")
        if isinstance(d, (int, float)):
            return int(d)
        start = event.get("started_at")
        end = event.get("ended_at")
        if isinstance(start, (int, float)) and isinstance(end, (int, float)):
            ms = int(end - start)
            return ms if ms >= 0 else None
        return None
    except Exception:
        return None
