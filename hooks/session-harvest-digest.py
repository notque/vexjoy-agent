#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SessionStart Hook: Weekly Correction-Harvest Digest — ADR correction-harvest-routine.

Surfaces the user-correction digest (scripts/harvest-corrections.py build_digest)
once per 7 days. Closes the capture->query loop: user-correction-capture.py writes
correction rows all week; this reads them back at session start.

Design Principles:
- SessionStart event. Gated to once per 7 days via a state file.
- Hot path (not-due) is a single file read + one timestamp parse — well under 100ms,
  no DB open, no subprocess.
- Due path imports build_digest (faster than spawning the script).
- Advisory only: informs, never gates a merge or blocks session start.
- Degrades silently on ANY error; always exits 0.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add lib directory to path for hook_utils / learning_db_v2.
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output
from stdin_timeout import read_stdin

EVENT_NAME = "SessionStart"

DIGEST_INTERVAL_DAYS = 7
DIGEST_WINDOW_HOURS = 168  # 7 days, the --since-hours 168 equivalent
MAX_CLUSTERS = 5  # cap surfaced clusters (top-N by count)
STATE_FILENAME = ".harvest-digest-state"

# Lazily bound to harvest-corrections.build_digest on first due run. Module-level
# so tests can monkeypatch it. None until loaded.
build_digest = None


def _load_build_digest():
    """Import build_digest from the hyphenated scripts/harvest-corrections.py.

    Handles repo layout (../scripts) and deployed layout (~/.claude/scripts).
    Caches the resolved callable in the module global `build_digest`.
    """
    global build_digest
    if build_digest is not None:
        return build_digest

    import importlib.util

    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    # learning_db_v2 lives in hooks/lib, already on sys.path; harvest-corrections
    # imports it as a sibling, so the path insert above is sufficient.
    src = scripts_dir / "harvest-corrections.py"
    spec = importlib.util.spec_from_file_location("harvest_corrections", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    build_digest = mod.build_digest
    return build_digest


def _learning_dir() -> Path:
    """Resolve ~/.claude/learning (or CLAUDE_LEARNING_DIR override)."""
    override = os.environ.get("CLAUDE_LEARNING_DIR")
    if override:
        return Path(override)
    return Path.home() / ".claude" / "learning"


def _state_file() -> Path:
    return _learning_dir() / STATE_FILENAME


def _is_due(now: datetime) -> bool:
    """True when >= DIGEST_INTERVAL_DAYS since last_run.

    Missing, empty, or malformed state -> due (fail toward running once; the state
    write then makes the next session not-due).
    """
    path = _state_file()
    try:
        raw = path.read_text(encoding="utf-8")
        last_run = datetime.fromisoformat(json.loads(raw)["last_run"])
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return True
    return (now - last_run) >= timedelta(days=DIGEST_INTERVAL_DAYS)


def _write_state(now: datetime) -> None:
    """Atomically record last_run = now. Best-effort; never raises to caller."""
    path = _state_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps({"last_run": now.isoformat()}), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def _render(digest: dict) -> str:
    """Render the digest as advisory [correction-digest] context lines."""
    total = digest.get("total_corrections", 0)
    if total == 0:
        return f"[correction-digest] No corrections this week (last {DIGEST_WINDOW_HOURS}h)."

    lines = [
        f"[correction-digest] {total} correction(s) in the last {DIGEST_WINDOW_HOURS}h "
        "(advisory — review and apply one-liners by hand):"
    ]
    for c in digest.get("clusters", [])[:MAX_CLUSTERS]:
        domain = c.get("domain", "unattributed")
        count = c.get("count", 0)
        target = c.get("suggested_target") or "no doc target — review manually"
        lines.append(f"[correction-digest] {domain} — {count} correction(s) — target: {target}")
    return "\n".join(lines)


def main() -> None:
    debug = bool(os.environ.get("CLAUDE_HOOKS_DEBUG"))

    # Drain stdin so the parent pipe never blocks (content unused).
    try:
        read_stdin(timeout=2)
    except Exception:
        pass

    now = datetime.now()

    # Hot path: gate first. Not-due -> silent exit, no DB, no import.
    if not _is_due(now):
        empty_output(EVENT_NAME).print_and_exit()

    # Due: build the digest. Import lazily; degrade on any failure.
    try:
        fn = build_digest if build_digest is not None else _load_build_digest()
        digest = fn(since_hours=DIGEST_WINDOW_HOURS)
    except Exception as e:
        if debug:
            print(f"[correction-digest] harvest failed: {type(e).__name__}: {e}", file=sys.stderr)
        # Do NOT write state on failure — retry next session.
        empty_output(EVENT_NAME).print_and_exit()

    # Success: render, record the run, inject.
    block = _render(digest)
    _write_state(now)
    context_output(EVENT_NAME, block).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[correction-digest] Fatal: {type(e).__name__}: {e}", file=sys.stderr)
    finally:
        sys.exit(0)  # ALWAYS exit 0 — non-blocking requirement
