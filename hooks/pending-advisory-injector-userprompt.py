#!/usr/bin/env python3
# hook-version: 1.0.0
"""
UserPromptSubmit Hook: Pending Advisory Injector

Drains advisories that Stop hooks deferred with hook_utils.defer_advisory
and injects them as additionalContext on the user's next prompt. This
replaces async rewakes: same text, delivered when the model is already
generating, at zero extra generation cost.

Reads  ~/.claude/state/pending-advisories/<session_id>.jsonl
Emits  {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
        "additionalContext": "..."}}  or nothing.
Fail-open: any error -> exit 0 with no output. Deletes the file after a
successful read so an advisory is delivered once. Drops rows older than
MAX_AGE_S (a stale drift note from yesterday is noise, not guidance).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PENDING_DIR = Path.home() / ".claude" / "state" / "pending-advisories"
MAX_AGE_S = 6 * 3600
MAX_ROWS = 8
MAX_CHARS = 6000


def _safe_id(v: object) -> str | None:
    if not isinstance(v, str) or not v or "/" in v or "\\" in v or v in (".", ".."):
        return None
    return v


def drain(session_id: str, now: float | None = None) -> str | None:
    path = PENDING_DIR / f"{session_id}.jsonl"
    if not path.exists():
        return None
    now = time.time() if now is None else now
    rows: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and now - float(row.get("ts", 0)) <= MAX_AGE_S:
                rows.append(row)
    finally:
        try:
            path.unlink()
        except OSError:
            pass
    if not rows:
        return None
    rows = rows[-MAX_ROWS:]
    parts = [
        f"[deferred-advisory from {r.get('source', '?')}] {r.get('summary', '')}\n{r.get('message', '')}".rstrip()
        for r in rows
    ]
    text = "\n\n".join(parts)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n[... advisories truncated ...]"
    return (
        "The following advisories were raised by Stop hooks after your last turn and deferred "
        "to this prompt instead of rewaking you. Treat them as context; fix or acknowledge "
        "only where it affects this turn.\n\n" + text
    )


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return
    sid = _safe_id(event.get("session_id")) if isinstance(event, dict) else None
    if not sid:
        return
    try:
        ctx = drain(sid)
    except Exception:
        return
    if ctx:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ctx}}))


if __name__ == "__main__":
    main()
    sys.exit(0)
