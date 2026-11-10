"""Per-session bridge for next-turn routing-outcome resolution.

The PostToolUse:Agent hook (routing-decision-recorder.py) records the routing
decision row and appends a PROVISIONAL pending outcome (routing key + observed
error flag) here. Resolution happens at a SINGLE point per dispatch, when the
next-turn signal is available:

  - SubagentStop (routing-outcome-recorder.py): validates each pending entry's
    decision row exists; re-queues late rows (bounded) and revalidates healthy
    entries to stay pending. It NO LONGER applies boost/decay.
  - UserPromptSubmit (routing-outcome-finalizer.py): on the next user turn,
    finalizes still-pending entries from tool-errors + user reaction + re-route,
    applying boost/decay ONCE then clearing them (idempotent).
  - Stop (routing-outcome-stop-fallback.py): Stop fires after every turn,
    before the user can react. It resolves only entries no reaction can change
    (errored ones) and entries older than ``STOP_STALE_AGE_SEC``; the rest stay
    pending for the UserPromptSubmit finalizer. On SessionEnd the same hook
    resolves everything left, by the error flag alone.

State lives in a per-session JSON file under /tmp. All writes are atomic
(write-to-temp-then-rename) so an interrupted hook never corrupts the file.
Every function is best-effort and swallows errors — this bridge must never
block a hook.

Concurrency: parallel same-session ``PostToolUse:Agent`` dispatches (the NORMAL
case — /do Phase 4 and pr-review both fan out agents) issue concurrent
read-modify-write cycles against the same state file. Without serialization
those cycles lose updates (two readers see the same ``pending`` list, both
append one entry, the later writer's atomic rename clobbers the earlier one →
B drains fewer outcomes than A wrote → route-health under-counts). To prevent
this, every read-modify-write holds an EXCLUSIVE ``fcntl.flock`` on a sidecar
lock file across the WHOLE load→modify→write, so appends serialize and no
outcome is lost. The lock is advisory and best-effort: if locking is
unavailable the operation still proceeds (degraded, never blocking).

File shape:
    {
      "seen": ["<dispatch-sig>", ...],     # idempotency for the decision hook
      "pending": [{"key": "agent:skill", "errors": false,
                   "attempts": 0, "created": 1735000000.0,
                   "decision_id": "<session>:<dispatch-sig>"}, ...],
      "agents": {"<agent-id>": {"key": "agent:skill", "decision_id": "..."}},
                   # background dispatches awaiting their SubagentStop, where
                   # the agent's final message (route-fit banner) arrives
      "history": {"agent:skill": "neutral", ...}  # last finalized outcome per
                   key this session — the weak-positive signal (C6) reads it to
                   tell a repeat dispatch with no intervening failure
    }

Idempotency (MEDIUM, TOCTOU): the decision hook claims a dispatch signature via
``claim_dispatch`` — an atomic check-and-set under the SAME flock as the write.
The previous split of ``dispatch_seen`` (unlocked read) + ``mark_dispatch_seen``
(locked write) let two concurrent duplicate deliveries both observe "unseen"
and double-record/double-score. ``claim_dispatch`` collapses both into one
locked critical section so exactly one caller wins.

Ordering (HIGH, A-before-B): action A (PostToolUse:Agent) writes the decision
row BEFORE appending the pending bridge entry, and PostToolUse:Agent fires
before SubagentStop — so the decision row is normally present when B drains.
If a B drains a pending key whose decision row is not yet visible (mistiming),
B RE-QUEUES that entry via ``requeue_pending_outcomes`` (bounded by
``MAX_REQUEUE_ATTEMPTS``) instead of discarding it, so a late-arriving decision
row gets scored on a subsequent stop. See adr/learn-step-to-hook.md.
"""

import json
import os
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# Cross-platform exclusive lock on an open fd. POSIX uses fcntl.flock; Windows
# (no fcntl) uses msvcrt.locking on a 1-byte range. Every writer locks the same
# range on the same sidecar lock file, so the read-modify-write cycles serialize
# and no outcome is lost. The previous Windows path was a no-op fcntl shim, which
# left parallel same-session appends racing (lost updates). See
# adr/windows-locking-deploy-warning.md.
try:
    import fcntl  # POSIX

    def _acquire_lock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX)

    def _release_lock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)

except ImportError:  # Windows
    import msvcrt

    # msvcrt.locking with LK_LOCK blocks ~10s then raises OSError; retry so a
    # contended lock waits rather than failing. Bounded so a wedged holder cannot
    # spin forever (degrades to unlocked at the call site, never blocks a hook).
    _LOCK_RETRIES = 60  # ~10 min worst case under heavy contention

    def _acquire_lock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        for attempt in range(_LOCK_RETRIES):
            try:
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                return
            except OSError:
                if attempt == _LOCK_RETRIES - 1:
                    raise

    def _release_lock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)


_STATE_DIR = Path("/tmp")

# Bounded re-queue: how many SubagentStop drains a pending entry may survive
# while its decision row is still not visible (HIGH, A-before-B mistiming).
# After this many attempts the entry is dropped so a permanently-orphaned
# pending key (decision row never written) cannot grow the file unbounded.
MAX_REQUEUE_ATTEMPTS = 5

# Bounded outcome history: last finalized outcome per route key this session
# (the C6 weak-positive signal's memory). A session rarely touches more than a
# few dozen distinct pairs; 200 keys bounds the file while never evicting in
# practice. Eviction drops the OLDEST insertion (dict order round-trips JSON).
MAX_HISTORY_KEYS = 200

# Bounded pending age: a provisional pending entry that is never finalized by
# UserPromptSubmit or Stop (e.g. a crashed session that emits neither a next
# user prompt nor a clean Stop) must not live forever. ``finalize_pending_outcomes``
# drops entries older than this so the per-session state file cannot grow
# unbounded across long-lived or abandoned sessions.
MAX_PENDING_AGE_SEC = 24 * 3600  # 24h

# Stop fires after every turn, before the user's next message. A clean entry
# younger than this stays pending at Stop so the UserPromptSubmit finalizer can
# read the reaction. Older than this, the session has run this long with no
# user turn, so the Stop fallback resolves it by the error flag alone.
# Unmeasured starting value: long enough to outlast one unattended turn.
STOP_STALE_AGE_SEC = 6 * 3600  # 6h

# Bounded map of background dispatches awaiting their SubagentStop.
MAX_ASYNC_AGENTS = 500


def _pending_entry(item: dict[str, Any], attempts: int, created: float) -> dict[str, Any]:
    """Rebuild one pending entry, keeping only known fields.

    ``decision_id`` is optional: entries written before it existed lack it, and
    the outcome writer then falls back to matching by route key.
    """
    entry: dict[str, Any] = {
        "key": item.get("key"),
        "errors": bool(item.get("errors")),
        "attempts": attempts,
        "created": created,
    }
    decision_id = item.get("decision_id")
    if isinstance(decision_id, str) and decision_id:
        entry["decision_id"] = decision_id
    return entry


def _state_dir() -> Path:
    """Resolve the state directory. Honors CLAUDE_ROUTING_STATE_DIR so separate
    processes (real cross-process dispatch, the concurrency test) agree on one
    location; falls back to the module default otherwise."""
    override = os.environ.get("CLAUDE_ROUTING_STATE_DIR")
    return Path(override) if override else _STATE_DIR


def _state_file(session_id: str) -> Path:
    sid = session_id or "nosession"
    # Keep the filename filesystem-safe.
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in sid)[:64]
    return _state_dir() / f"claude-routing-outcomes-{safe}.json"


def _lock_file(path: Path) -> Path:
    """Sidecar lock path for a state file (the state file is rename-replaced,
    so the lock must live on a stable inode that is never replaced)."""
    return path.with_suffix(path.suffix + ".lock")


@contextmanager
def _state_lock(path: Path):
    """Hold an exclusive advisory lock across a read-modify-write cycle.

    Best-effort: if the lock file cannot be opened or locking is unavailable the
    body still runs (degraded to unlocked) so the bridge never blocks a hook. The
    lock lives on a sidecar inode because the state file itself is replaced via
    ``os.replace`` (which swaps inodes and would drop a lock held on the old one).
    The backend is fcntl on POSIX and msvcrt on Windows (see module top)."""
    lock_fd = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(str(_lock_file(path)), os.O_CREAT | os.O_RDWR, 0o600)
        _acquire_lock(lock_fd)
    except OSError:
        if lock_fd is not None:
            try:
                os.close(lock_fd)
            except OSError:
                pass
            lock_fd = None
    try:
        yield
    finally:
        if lock_fd is not None:
            try:
                _release_lock(lock_fd)
            except OSError:
                pass
            try:
                os.close(lock_fd)
            except OSError:
                pass


def _load(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                data.setdefault("seen", [])
                data.setdefault("pending", [])
                data.setdefault("history", {})
                if not isinstance(data.get("agents"), dict):
                    data["agents"] = {}
                return data
    except (json.JSONDecodeError, OSError, ValueError) as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[routing-outcome-state] _load: {type(e).__name__}: {e}", file=sys.stderr)
    return {"seen": [], "pending": [], "history": {}, "agents": {}}


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f)
            os.replace(tmp, str(path))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as e:
        # Best-effort: at worst we lose one bridge record.
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[routing-outcome-state] _atomic_write: {type(e).__name__}: {e}", file=sys.stderr)


def claim_dispatch(session_id: str, signature: str) -> bool:
    """Atomic check-and-set: claim a dispatch signature for recording.

    Returns True iff THIS caller is the first to claim ``signature`` (the row
    should be recorded). Returns False if it was already seen (skip — a
    duplicate delivery). The check and the mark happen under ONE flock, so N
    concurrent duplicate deliveries see exactly one True (MEDIUM, TOCTOU fix:
    replaces the split dispatch_seen-read + mark_dispatch_seen-write that let
    two racers both observe "unseen").

    Best-effort: if state I/O fails entirely it returns True (record rather than
    silently drop a real dispatch); the DB upsert on (topic, key) is itself
    idempotent, so a rare double-claim under total I/O failure is bounded.
    """
    try:
        path = _state_file(session_id)
        with _state_lock(path):
            data = _load(path)
            if signature in data["seen"]:
                return False
            data["seen"].append(signature)
            # Bound the seen list so a long session can't grow it unbounded.
            data["seen"] = data["seen"][-500:]
            _atomic_write(path, data)
            return True
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[routing-outcome-state] claim_dispatch: {type(e).__name__}: {e}", file=sys.stderr)
        return True


# NIT (removed): the split ``dispatch_seen`` (unlocked read) + ``mark_dispatch_seen``
# (locked write) pair was superseded by the atomic ``claim_dispatch`` check-and-set
# above. They were dead (no caller) and their split read/write protocol is exactly
# the TOCTOU race ``claim_dispatch`` closes — deleted so it cannot be re-introduced.


def append_pending_outcome(session_id: str, key: str, errors: bool, decision_id: str | None = None) -> None:
    """Append a PROVISIONAL pending outcome.

    The entry carries this dispatch's own observed ``errors`` flag and is left
    pending (not scored) until a resolver finalizes it: UserPromptSubmit on the
    next user turn (reaction + error + re-route) or Stop at session end (error
    flag alone). ``created`` bounds its lifetime; ``attempts`` bounds re-queues
    while the decision row is still not visible at SubagentStop.
    ``decision_id`` names this dispatch's evidence row, so the resolver updates
    that row and not another dispatch of the same key.
    """
    try:
        path = _state_file(session_id)
        with _state_lock(path):
            data = _load(path)
            data["pending"].append(
                _pending_entry({"key": key, "errors": errors, "decision_id": decision_id}, 0, time.time())
            )
            data["pending"] = data["pending"][-500:]
            _atomic_write(path, data)
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[routing-outcome-state] append_pending_outcome: {type(e).__name__}: {e}", file=sys.stderr)


def peek_pending_outcomes(session_id: str) -> list[dict[str, Any]]:
    """Return a copy of the still-pending outcomes WITHOUT clearing them.

    Read-only helper for diagnostics / the SubagentStop validator, which must
    inspect pending entries but leave them in place for a later finalizer.
    """
    try:
        return list(_load(_state_file(session_id)).get("pending", []))
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[routing-outcome-state] peek_pending_outcomes: {type(e).__name__}: {e}", file=sys.stderr)
        return []


def finalize_pending_outcomes(session_id: str) -> list[dict[str, Any]]:
    """Atomically read-AND-clear all still-pending outcomes for resolution.

    Used by the single resolution point on each turn (UserPromptSubmit) and by
    the session-end fallback (SessionEnd). Returns the pending entries; the caller is
    responsible for applying boost/decay exactly once. Entries older than
    ``MAX_PENDING_AGE_SEC`` are dropped (returned but the caller skips scoring
    via the age check) — handled here by simply clearing them so abandoned
    sessions cannot grow state unbounded.

    Clearing here makes finalization idempotent across re-delivered events: a
    second UserPromptSubmit for the same prompt finds an empty pending list and
    applies nothing (no double boost/decay).
    """
    try:
        path = _state_file(session_id)
        with _state_lock(path):
            data = _load(path)
            pending = data.get("pending", [])
            if pending:
                data["pending"] = []
                _atomic_write(path, data)
        return pending
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[routing-outcome-state] finalize_pending_outcomes: {type(e).__name__}: {e}", file=sys.stderr)
        return []


def take_resolvable_pending_outcomes(session_id: str, min_age_sec: float) -> list[dict[str, Any]]:
    """Remove and return only the pending entries a Stop may resolve.

    Stop fires after every turn, before the user's next message. Draining all
    entries there scored every dispatch as silence and left the UserPromptSubmit
    finalizer nothing to read. This takes an entry only when no later reaction
    can change its outcome, or when no reaction is coming:

      - ``errors`` is set: a tool error scores failure whatever the user says.
      - older than ``min_age_sec``: the session ran that long with no user turn.
      - ``created`` is malformed: the entry can never be aged, so drop it here.

    Every other entry stays pending, in order. Atomic under the state lock, so
    a concurrent append is never lost.
    """
    try:
        now = time.time()
        path = _state_file(session_id)
        with _state_lock(path):
            data = _load(path)
            taken: list[dict[str, Any]] = []
            kept: list[dict[str, Any]] = []
            for item in data.get("pending", []):
                try:
                    age = now - float(item.get("created", now))
                except (TypeError, ValueError, AttributeError):
                    taken.append(item)
                    continue
                if item.get("errors") or age > min_age_sec:
                    taken.append(item)
                else:
                    kept.append(item)
            if taken:
                data["pending"] = kept
                _atomic_write(path, data)
        return taken
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[routing-outcome-state] take_resolvable_pending_outcomes: {type(e).__name__}: {e}", file=sys.stderr)
        return []


def discard_pending_outcome(session_id: str, decision_id: str) -> bool:
    """Drop the pending entry for one dispatch. True iff an entry was removed.

    Used when a signal resolves the dispatch before the next user turn (a
    negative route-fit verdict), so no later resolver scores it a second time.
    Matches on ``decision_id`` only: a key can have several live dispatches.
    """
    if not decision_id:
        return False
    try:
        path = _state_file(session_id)
        with _state_lock(path):
            data = _load(path)
            pending = data.get("pending", [])
            kept = [it for it in pending if not (isinstance(it, dict) and it.get("decision_id") == decision_id)]
            if len(kept) == len(pending):
                return False
            data["pending"] = kept
            _atomic_write(path, data)
        return True
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[routing-outcome-state] discard_pending_outcome: {type(e).__name__}: {e}", file=sys.stderr)
        return False


def register_async_dispatch(session_id: str, agent_id: str, key: str, decision_id: str | None = None) -> None:
    """Remember a background dispatch until its SubagentStop.

    A background Agent call returns a launch receipt at PostToolUse, not the
    agent's reply. The reply arrives at SubagentStop, which carries the agent id
    but no route key. This map joins the two. Bounded: oldest entry evicted.
    """
    if not agent_id or not key:
        return
    try:
        path = _state_file(session_id)
        with _state_lock(path):
            data = _load(path)
            agents = data["agents"]
            agents.pop(agent_id, None)
            agents[agent_id] = {"key": key, "decision_id": decision_id or ""}
            while len(agents) > MAX_ASYNC_AGENTS:
                agents.pop(next(iter(agents)))
            _atomic_write(path, data)
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[routing-outcome-state] register_async_dispatch: {type(e).__name__}: {e}", file=sys.stderr)


def claim_async_dispatch(session_id: str, agent_id: str) -> dict[str, str] | None:
    """Remove and return the route for a finished background agent, or None.

    Check-and-remove under one lock: a re-delivered SubagentStop finds nothing
    and scores nothing.
    """
    if not agent_id:
        return None
    try:
        path = _state_file(session_id)
        with _state_lock(path):
            data = _load(path)
            entry = data["agents"].pop(agent_id, None)
            if entry is None:
                return None
            _atomic_write(path, data)
        if isinstance(entry, dict) and entry.get("key"):
            return {"key": str(entry["key"]), "decision_id": str(entry.get("decision_id") or "")}
        return None
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[routing-outcome-state] claim_async_dispatch: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def revalidate_pending_outcomes(session_id: str, items: list[dict[str, Any]]) -> None:
    """Re-queue VALIDATED provisional entries that are not yet finalizable.

    SubagentStop confirms each pending entry's decision row exists, then puts
    the still-unresolved entries BACK (so a later UserPromptSubmit/Stop can
    finalize them) WITHOUT advancing the re-queue attempt counter — these are
    healthy entries awaiting a next-turn signal, not late-row mistimings. Stale
    entries (older than ``MAX_PENDING_AGE_SEC``) are dropped here too.
    """
    if not items:
        return
    try:
        now = time.time()
        path = _state_file(session_id)
        with _state_lock(path):
            data = _load(path)
            for item in items:
                if not item.get("key"):
                    continue
                created = float(item.get("created", now))
                if now - created > MAX_PENDING_AGE_SEC:
                    continue  # drop abandoned provisional entry
                data["pending"].append(_pending_entry(item, int(item.get("attempts", 0)), created))
            data["pending"] = data["pending"][-500:]
            _atomic_write(path, data)
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[routing-outcome-state] revalidate_pending_outcomes: {type(e).__name__}: {e}", file=sys.stderr)


def drain_pending_outcomes(session_id: str) -> list[dict[str, Any]]:
    """Return and clear all pending outcomes for this session.

    Returns a list of {"key": str, "errors": bool}. Clears the pending list
    (keeps the seen list) so each pending outcome is applied at most once.
    """
    try:
        path = _state_file(session_id)
        with _state_lock(path):
            data = _load(path)
            pending = data.get("pending", [])
            if pending:
                data["pending"] = []
                _atomic_write(path, data)
        return pending
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[routing-outcome-state] drain_pending_outcomes: {type(e).__name__}: {e}", file=sys.stderr)
        return []


def get_outcome_history(session_id: str) -> dict[str, str]:
    """Last finalized outcome per route key this session. {} on any error.

    Read-only. The weak-positive signal (C6) reads it in the UserPromptSubmit
    finalizer: a pending key whose PREVIOUS finalization this session was not a
    failure is a repeat dispatch with no intervening failure.
    """
    try:
        history = _load(_state_file(session_id)).get("history", {})
        return dict(history) if isinstance(history, dict) else {}
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[routing-outcome-state] get_outcome_history: {type(e).__name__}: {e}", file=sys.stderr)
        return {}


def record_outcome_history(session_id: str, updates: dict[str, str]) -> None:
    """Merge finalized outcomes into the per-key session history. Best-effort.

    Latest write wins per key (the finalizer applies failure precedence within
    one turn BEFORE calling). Bounded to ``MAX_HISTORY_KEYS`` — oldest insertion
    evicted first — so a long session cannot grow the file unbounded.
    """
    if not updates:
        return
    try:
        path = _state_file(session_id)
        with _state_lock(path):
            data = _load(path)
            history = data.get("history", {})
            if not isinstance(history, dict):
                history = {}
            for key, outcome in updates.items():
                if not key or not isinstance(outcome, str):
                    continue
                history.pop(key, None)  # re-insert => freshest position
                history[key] = outcome
            while len(history) > MAX_HISTORY_KEYS:
                history.pop(next(iter(history)))
            data["history"] = history
            _atomic_write(path, data)
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[routing-outcome-state] record_outcome_history: {type(e).__name__}: {e}", file=sys.stderr)


def requeue_pending_outcomes(session_id: str, items: list[dict[str, Any]]) -> None:
    """Re-queue pending outcomes whose decision row was not yet visible at drain.

    HIGH (A-before-B mistiming): when B drains a key before A's decision row is
    visible, the entry is put BACK so a later SubagentStop can score it once the
    row lands — instead of being silently dropped. Each re-queue increments the
    entry's ``attempts``; entries that exceed ``MAX_REQUEUE_ATTEMPTS`` are
    dropped (the decision row was likely never written — e.g. A errored) so the
    pending list cannot grow unbounded.
    """
    if not items:
        return
    try:
        path = _state_file(session_id)
        with _state_lock(path):
            data = _load(path)
            for item in items:
                attempts = int(item.get("attempts", 0)) + 1
                if attempts > MAX_REQUEUE_ATTEMPTS:
                    continue  # give up on a permanently-orphaned pending key
                data["pending"].append(_pending_entry(item, attempts, float(item.get("created", time.time()))))
            data["pending"] = data["pending"][-500:]
            _atomic_write(path, data)
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[routing-outcome-state] requeue_pending_outcomes: {type(e).__name__}: {e}", file=sys.stderr)
