#!/usr/bin/env python3
"""Tests for the routing-decision-recorder (A) and routing-outcome-recorder (B) hooks.

Covers:
- A records the expected `routing` decision row from a synthetic PostToolUse:Agent event.
- A reads agent + skill from the [do-route] marker; agent-only when skill=-.
- A records ONLY /do-routed dispatches: marker present => recorded; marker
  absent (reviewer sub-agent / nested fan-out) => skipped.
- A records a rightsizing row when the banner is present (C), silent otherwise.
- A is idempotent: the same dispatch is recorded once.
- B records success (boost) / failure (decay) from drained pending outcomes.
- B NEVER crashes when the decision record is absent (row-existence pre-check skip).
- The A->B bridge state survives concurrent parallel appends (no lost outcomes).
- Both hooks exit 0 on empty / malformed input.

Uses a throwaway learning.db via CLAUDE_LEARNING_DIR and a per-session bridge
file under tmp_path — never the real DB.

Run with: python3 -m pytest hooks/tests/test_routing_decision_recorder.py -v
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).parent.parent
LIB_DIR = HOOKS_DIR / "lib"
A_PATH = HOOKS_DIR / "routing-decision-recorder.py"
B_PATH = HOOKS_DIR / "routing-outcome-recorder.py"


@pytest.fixture()
def db_env(tmp_path, monkeypatch):
    """Point the learning DB and the bridge state dir at a throwaway location."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    sys.path.insert(0, str(LIB_DIR))
    # Force a fresh DB init against this tmp dir: learning_db_v2 caches
    # _initialized as a module global across in-process tests.
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    # Redirect the bridge state dir away from /tmp into tmp_path.
    import routing_outcome_state as ros

    monkeypatch.setattr(ros, "_STATE_DIR", tmp_path / "state")
    yield {"db_dir": db_dir, "state": tmp_path / "state"}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    with patch("sys.exit"):
        spec.loader.exec_module(mod)
    return mod


def _run_hook(path: Path, event: dict) -> subprocess.CompletedProcess:
    """Run a hook as a subprocess feeding the event on stdin. Returns the result."""
    return subprocess.run(
        [sys.executable, str(path)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )


def _agent_event(
    skill="",
    *,
    marker=True,
    body="do work",
    description="do work",
    output="ok",
    is_error=False,
    session="s1",
):
    """Build a synthetic PostToolUse:Agent event.

    marker=True stamps the [do-route] marker /do prepends to routed prompts
    (the sole signal the recorder uses). marker=False simulates a sub-agent
    fan-out (pr-review reviewer / nested dispatch) that carries no marker.
    """
    if marker:
        prefix = f"[do-route] agent=python-general-engineer skill={skill or '-'} complexity=Medium\n"
    else:
        prefix = ""
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "session_id": session,
        "tool_input": {
            "subagent_type": "python-general-engineer",
            "description": description,
            "prompt": prefix + body,
        },
        "tool_result": {"output": output, "is_error": is_error},
    }


def _query_routing(db_env):
    sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    return ldb.query_learnings(
        topic="routing",
        category="effectiveness",
        exclude_graduated=False,
        exclude_test_sources=False,
        limit=1000,
    )


# ---------------------------------------------------------------------------
# A — routing-decision-recorder
# ---------------------------------------------------------------------------


class TestDecisionRecorder:
    def test_records_decision_row_with_skill(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_a1")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _agent_event(skill="test-driven-development", body="Write tests.")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        rows = _query_routing(db_env)
        keys = {r["key"] for r in rows}
        assert "python-general-engineer:test-driven-development" in keys
        row = next(r for r in rows if r["key"] == "python-general-engineer:test-driven-development")
        assert "tool_errors=0" in row["value"]

    def test_agent_only_key_when_no_skill(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_a2")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        # marker present with skill=- => agent-only key.
        event = _agent_event(skill="", body="Just do the thing, no skill named.")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        keys = {r["key"] for r in _query_routing(db_env)}
        assert "python-general-engineer:" in keys

    def test_skipped_when_marker_absent(self, db_env, monkeypatch):
        # Sub-agent fan-out (pr-review reviewer / nested dispatch) has no marker
        # => not a /do routing decision => recorder records NOTHING.
        a = _load(A_PATH, "rdr_a_nomarker")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        # A reviewer-style prompt that even names a skill the OLD sniffer would catch.
        event = _agent_event(
            marker=False,
            body='Review this PR. Skill("systematic-code-review") load the security-review skill.',
        )
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        assert _query_routing(db_env) == []

    def test_error_flag_when_result_errored(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_a3")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _agent_event(
            skill="go-patterns",
            output="fatal: permission denied",
            is_error=True,
        )
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        row = next(r for r in _query_routing(db_env) if r["key"] == "python-general-engineer:go-patterns")
        assert "tool_errors=1" in row["value"]

    def test_rightsizing_row_recorded(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_a4")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _agent_event(
            skill="systematic-code-review",
            output="done. rightsizing: tier=3 files=15 packages=4 agents_dispatched=17",
        )
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        keys = {r["key"] for r in _query_routing(db_env)}
        assert "rightsizing:tier3" in keys

    def test_no_rightsizing_row_when_banner_absent(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_a5")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _agent_event(skill="go-patterns", output="plain output")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        keys = {r["key"] for r in _query_routing(db_env)}
        assert not any(k.startswith("rightsizing:") for k in keys)

    def test_idempotent_same_dispatch_recorded_once(self, db_env):
        # Use the real bridge state (redirected to tmp) so dedup engages.
        a = _load(A_PATH, "rdr_a6")
        event = _agent_event(skill="go-patterns", session="dup-session")
        for _ in range(3):
            with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
                a.main()
        row = next(r for r in _query_routing(db_env) if r["key"] == "python-general-engineer:go-patterns")
        assert row["observation_count"] == 1

    def test_exit_zero_on_empty_and_malformed(self, db_env):
        assert _run_hook(A_PATH, {}).returncode == 0
        p = subprocess.run([sys.executable, str(A_PATH)], input="not json", capture_output=True, text=True)
        assert p.returncode == 0
        assert subprocess.run([sys.executable, str(A_PATH)], input="", capture_output=True, text=True).returncode == 0

    def test_non_agent_tool_ignored(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_a7")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        assert _query_routing(db_env) == []


# ---------------------------------------------------------------------------
# B — routing-outcome-recorder
# ---------------------------------------------------------------------------


class TestOutcomeRecorder:
    def _seed_decision(self, key="python-general-engineer:go-patterns"):
        sys.path.insert(0, str(LIB_DIR))
        import learning_db_v2 as ldb

        ldb.record_learning(
            topic="routing",
            key=key,
            value=f"routing-decision: {key} tool_errors=0 user_rerouted=0",
            category="effectiveness",
            source="test",
        )
        return key

    def test_success_boosts_confidence(self, db_env, monkeypatch):
        key = self._seed_decision()
        b = _load(B_PATH, "ror_b1")
        monkeypatch.setattr(b, "drain_pending_outcomes", lambda _sid: [{"key": key, "errors": False}])
        before = next(r for r in _query_routing(db_env) if r["key"] == key)["confidence"]
        event = {"hook_event_name": "SubagentStop", "session_id": "s1", "transcript_path": ""}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            b.main()
        after_row = next(r for r in _query_routing(db_env) if r["key"] == key)
        assert after_row["confidence"] > before
        assert after_row["success_count"] == 1

    def test_failure_decays_confidence(self, db_env, monkeypatch):
        key = self._seed_decision("python-general-engineer:debug")
        b = _load(B_PATH, "ror_b2")
        monkeypatch.setattr(b, "drain_pending_outcomes", lambda _sid: [{"key": key, "errors": True}])
        before = next(r for r in _query_routing(db_env) if r["key"] == key)["confidence"]
        event = {"hook_event_name": "SubagentStop", "session_id": "s1", "transcript_path": ""}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            b.main()
        after_row = next(r for r in _query_routing(db_env) if r["key"] == key)
        assert after_row["confidence"] < before
        assert after_row["failure_count"] == 1

    def test_decayed_to_zero_row_is_scored_not_skipped(self, db_env, monkeypatch):
        # LOW 1: a row that legitimately reaches confidence 0.0 must still be
        # scored (failure_count increments) — NOT mistaken for a missing row.
        # The row-existence pre-check sees the row, so it is scored even though
        # boost/decay return 0.0 (which a missing row would also return).
        sys.path.insert(0, str(LIB_DIR))
        import learning_db_v2 as ldb

        key = "python-general-engineer:near-zero"
        ldb.record_learning(
            topic="routing",
            key=key,
            value=f"routing-decision: {key} tool_errors=0",
            category="effectiveness",
            source="test",
        )
        # Drive confidence to exactly 0.0 with a large decay.
        assert ldb.decay_confidence("routing", key, delta=1.0) == 0.0
        before = next(r for r in _query_routing(db_env) if r["key"] == key)["failure_count"]

        b = _load(B_PATH, "ror_zero")
        monkeypatch.setattr(b, "drain_pending_outcomes", lambda _sid: [{"key": key, "errors": True}])
        event = {"hook_event_name": "SubagentStop", "session_id": "s1", "transcript_path": ""}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            b.main()
        after = next(r for r in _query_routing(db_env) if r["key"] == key)
        # Confidence already 0.0; the outcome is still applied => failure_count grows.
        assert after["failure_count"] == before + 1

    def test_never_crashes_when_decision_record_absent(self, db_env, monkeypatch):
        # No decision row seeded — the row-existence pre-check skips cleanly.
        b = _load(B_PATH, "ror_b3")
        monkeypatch.setattr(
            b, "drain_pending_outcomes", lambda _sid: [{"key": "ghost-agent:ghost-skill", "errors": False}]
        )
        event = {"hook_event_name": "SubagentStop", "session_id": "s1", "transcript_path": ""}
        with patch("sys.exit") as ex, patch("sys.stdin.read", return_value=json.dumps(event)):
            b.main()
        # No row created, no exception raised.
        assert all(r["key"] != "ghost-agent:ghost-skill" for r in _query_routing(db_env))
        ex.assert_called_with(0)

    def test_exit_zero_on_empty_and_malformed(self, db_env):
        assert _run_hook(B_PATH, {}).returncode == 0
        assert (
            subprocess.run([sys.executable, str(B_PATH)], input="not json", capture_output=True, text=True).returncode
            == 0
        )
        assert subprocess.run([sys.executable, str(B_PATH)], input="", capture_output=True, text=True).returncode == 0


# ---------------------------------------------------------------------------
# A + B integration: route-health closes the loop
# ---------------------------------------------------------------------------


class TestEndToEndLoop:
    def test_decision_then_outcome_closes_loop(self, db_env):
        # Real bridge (tmp-redirected): A writes decision + pending; B drains and scores.
        a = _load(A_PATH, "rdr_e1")
        b = _load(B_PATH, "ror_e1")
        event_a = _agent_event(skill="go-patterns", session="loop-1")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event_a)):
            a.main()
        event_b = {"hook_event_name": "SubagentStop", "session_id": "loop-1", "transcript_path": ""}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event_b)):
            b.main()
        rows = _query_routing(db_env)
        decision = next(r for r in rows if r["key"] == "python-general-engineer:go-patterns")
        # Decision row exists AND has an outcome (success_count incremented) => loop closed.
        assert decision["success_count"] == 1


# ---------------------------------------------------------------------------
# HIGH 1 / MEDIUM 2 — A->B bridge concurrency: no lost outcomes under parallel append
# ---------------------------------------------------------------------------

# Source for a child process that appends ONE pending outcome under the shared
# state dir (set via CLAUDE_ROUTING_STATE_DIR). Models a real parallel dispatch
# writing through routing_outcome_state from a separate process.
_PROC_APPEND_SRC = """
import sys
sys.path.insert(0, {lib!r})
from routing_outcome_state import append_pending_outcome
append_pending_outcome({session!r}, "agent:skill-" + sys.argv[1], False)
"""


class TestBridgeConcurrency:
    def _drain(self, session, state_dir):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        # Point the module at the same dir the appenders used.
        old = getattr(ros, "_STATE_DIR", None)
        ros._STATE_DIR = Path(state_dir)
        try:
            return ros.drain_pending_outcomes(session)
        finally:
            if old is not None:
                ros._STATE_DIR = old

    def test_parallel_thread_appends_no_lost_outcomes(self, tmp_path, monkeypatch):
        """N threads append concurrently to one session; the drain must see all N.

        Without locking the read-modify-write races and the file ends up with
        far fewer than N entries (lost-update). The flock serialization fixes it.
        """
        import threading

        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        state_dir = tmp_path / "state"
        monkeypatch.setattr(ros, "_STATE_DIR", state_dir)
        session = "concurrent-threads"
        n = 60

        barrier = threading.Barrier(n)

        def worker(i):
            barrier.wait()  # maximize overlap of the read-modify-write windows
            ros.append_pending_outcome(session, f"agent:skill-{i}", False)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        drained = ros.drain_pending_outcomes(session)
        assert len(drained) == n, f"lost outcomes: drained {len(drained)} of {n}"
        assert {d["key"] for d in drained} == {f"agent:skill-{i}" for i in range(n)}

    def test_parallel_process_appends_no_lost_outcomes(self, tmp_path):
        """N separate PROCESSES append concurrently; the drain must see all N.

        Threads share the GIL; only multi-process exercises the cross-process
        flock. Each child writes through routing_outcome_state independently.
        """
        import os as _os

        state_dir = tmp_path / "state-proc"
        state_dir.mkdir()
        session = "concurrent-procs"
        n = 25

        env = dict(_os.environ)
        env["CLAUDE_ROUTING_STATE_DIR"] = str(state_dir)
        src = _PROC_APPEND_SRC.format(lib=str(LIB_DIR), session=session)

        procs = [subprocess.Popen([sys.executable, "-c", src, str(i)], env=env) for i in range(n)]
        for p in procs:
            assert p.wait() == 0

        drained = self._drain(session, state_dir)
        assert len(drained) == n, f"lost outcomes: drained {len(drained)} of {n}"
        assert {d["key"] for d in drained} == {f"agent:skill-{i}" for i in range(n)}


# ---------------------------------------------------------------------------
# CRITICAL — decision_row_exists keyed lookup survives a >1000-row table
# ---------------------------------------------------------------------------


class TestDecisionRowExistsBeyondTop1000:
    """A decayed target row beyond a confidence-DESC top-1000 window must still
    be found by the KEYED existence check, so its outcome is still scored.

    The old top-1000 query_learnings scan ordered confidence DESC; once the
    routing/effectiveness table exceeded 1000 rows, a low-confidence target
    fell out of the window => decision_row_exists False => outcome silently
    skipped (data loss). The keyed SELECT has no row cap.
    """

    def test_decayed_target_beyond_1000_rows_is_scored(self, db_env, monkeypatch):
        sys.path.insert(0, str(LIB_DIR))
        import learning_db_v2 as ldb

        target = "python-general-engineer:rare-route"
        # Seed the target FIRST and decay it to a low confidence so it sorts
        # LAST under confidence DESC.
        ldb.record_learning(
            topic="routing",
            key=target,
            value=f"routing-decision: {target} tool_errors=0",
            category="effectiveness",
            source="test",
        )
        ldb.decay_confidence("routing", target, delta=0.45)  # -> ~0.05, near floor

        # Now flood the table with >1000 HIGH-confidence routing rows so the
        # target is pushed past any top-1000 confidence-DESC window.
        for i in range(1100):
            ldb.record_learning(
                topic="routing",
                key=f"filler-agent:skill-{i}",
                value=f"routing-decision: filler {i} tool_errors=0",
                category="effectiveness",
                confidence=0.95,
                source="test",
            )

        # Sanity: the OLD top-1000 confidence-DESC scan would NOT see the target.
        top1000 = ldb.query_learnings(
            topic="routing",
            category="effectiveness",
            exclude_graduated=False,
            exclude_test_sources=False,
            limit=1000,
        )
        assert target not in {r["key"] for r in top1000}, "test premise broken: target still in top-1000"

        # The hook's keyed existence check MUST still find it.
        b = _load(B_PATH, "ror_keyed")
        assert b.decision_row_exists(target) is True

        # And the outcome is applied (failure_count increments) — not skipped.
        before = next(r for r in _query_routing_all(db_env) if r["key"] == target)["failure_count"]
        monkeypatch.setattr(b, "drain_pending_outcomes", lambda _sid: [{"key": target, "errors": True}])
        event = {"hook_event_name": "SubagentStop", "session_id": "s1"}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            b.main()
        after = next(r for r in _query_routing_all(db_env) if r["key"] == target)["failure_count"]
        assert after == before + 1, "decayed beyond-top-1000 target was not scored"


def _query_routing_all(db_env):
    """Keyed-safe routing fetch for assertions: read every routing row directly
    (no confidence-DESC top-N cap) so a decayed target is always visible."""
    sys.path.insert(0, str(LIB_DIR))
    import sqlite3

    import learning_db_v2 as ldb

    ldb.init_db()
    conn = sqlite3.connect(ldb.get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM learnings WHERE topic = 'routing'").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# HIGH-2 — per-agent attribution: one key's error must NOT decay a sibling
# ---------------------------------------------------------------------------


class TestPerAgentAttribution:
    """Each pending entry is scored by its OWN errors flag. A failing agent in
    the same session/transcript must not broadcast failure onto a clean
    sibling key (the dropped whole-transcript substring scan used to do this).
    """

    def test_sibling_key_not_decayed_by_other_agents_error(self, db_env, monkeypatch):
        sys.path.insert(0, str(LIB_DIR))
        import learning_db_v2 as ldb

        good = "python-general-engineer:clean"
        bad = "golang-general-engineer:broken"
        for key in (good, bad):
            ldb.record_learning(
                topic="routing",
                key=key,
                value=f"routing-decision: {key} tool_errors=0",
                category="effectiveness",
                source="test",
            )
        good_before = next(r for r in _query_routing_all(db_env) if r["key"] == good)["confidence"]

        b = _load(B_PATH, "ror_attrib")
        # Two pending entries drained together: only `bad` carries errors=True.
        monkeypatch.setattr(
            b,
            "drain_pending_outcomes",
            lambda _sid: [{"key": good, "errors": False}, {"key": bad, "errors": True}],
        )
        # A transcript full of error prose must NOT influence the clean key.
        event = {"hook_event_name": "SubagentStop", "session_id": "s1"}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            b.main()

        good_after = next(r for r in _query_routing_all(db_env) if r["key"] == good)
        bad_after = next(r for r in _query_routing_all(db_env) if r["key"] == bad)
        # Clean key boosted (success), NOT decayed by the sibling's error.
        assert good_after["success_count"] == 1
        assert good_after["failure_count"] == 0
        assert good_after["confidence"] > good_before
        # Failing key decayed on its own flag.
        assert bad_after["failure_count"] == 1


# ---------------------------------------------------------------------------
# HIGH-3 — late decision row is re-queued (bounded), not dropped
# ---------------------------------------------------------------------------


class TestLateDecisionRowRequeue:
    def test_missing_row_requeued_then_scored_on_next_stop(self, db_env, monkeypatch):
        """B fires before A's decision row is visible => entry re-queued; once
        the row lands, a subsequent SubagentStop scores it (no data loss)."""
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        state_dir = db_env["state"]
        monkeypatch.setattr(ros, "_STATE_DIR", state_dir)
        session = "late-row"
        key = "python-general-engineer:late"

        # Pending exists but NO decision row yet.
        ros.append_pending_outcome(session, key, errors=True)

        b = _load(B_PATH, "ror_late1")
        event = {"hook_event_name": "SubagentStop", "session_id": session}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            b.main()

        # Entry must be RE-QUEUED (attempts incremented), not dropped.
        requeued = ros.drain_pending_outcomes(session)
        assert len(requeued) == 1
        assert requeued[0]["key"] == key
        assert requeued[0]["attempts"] == 1
        # Put it back for the next stop.
        ros.requeue_pending_outcomes(session, [{"key": key, "errors": True, "attempts": 0}])

        # Now the decision row lands (action A late).
        import learning_db_v2 as ldb

        ldb.record_learning(
            topic="routing",
            key=key,
            value=f"routing-decision: {key} tool_errors=1",
            category="effectiveness",
            source="test",
        )

        b2 = _load(B_PATH, "ror_late2")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            b2.main()
        row = next(r for r in _query_routing_all(db_env) if r["key"] == key)
        assert row["failure_count"] == 1, "late-landing decision row was not scored"

    def test_requeue_is_bounded_and_drops_orphan(self, db_env, monkeypatch):
        """A pending key whose decision row never lands is dropped after
        MAX_REQUEUE_ATTEMPTS so the pending list cannot grow unbounded."""
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        state_dir = db_env["state"]
        monkeypatch.setattr(ros, "_STATE_DIR", state_dir)
        session = "orphan"
        key = "ghost-agent:ghost-skill"
        ros.append_pending_outcome(session, key, errors=False)

        event = {"hook_event_name": "SubagentStop", "session_id": session}
        # Drain repeatedly; the decision row never exists. Each stop re-queues
        # with attempts+1 until the cap is exceeded, then the entry is dropped.
        for i in range(ros.MAX_REQUEUE_ATTEMPTS + 2):
            b = _load(B_PATH, f"ror_orphan_{i}")
            with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
                b.main()

        # After exceeding the cap, the orphan is gone from pending.
        remaining = ros.drain_pending_outcomes(session)
        assert remaining == [], f"orphan pending not dropped after cap: {remaining}"


# ---------------------------------------------------------------------------
# MEDIUM — claim_dispatch atomicity: N concurrent identical deliveries -> once
# ---------------------------------------------------------------------------

_PROC_CLAIM_SRC = """
import sys
sys.path.insert(0, {lib!r})
from routing_outcome_state import claim_dispatch
won = claim_dispatch({session!r}, {sig!r})
sys.exit(0 if won else 3)  # exit 0 == this proc claimed (won)
"""


class TestClaimDispatchAtomicity:
    def test_concurrent_identical_claims_record_once(self, tmp_path):
        """N separate processes claim the SAME signature concurrently; exactly
        one must win (return True). The old split read+write let several win =>
        double-record/double-score. claim_dispatch is one locked check-and-set.
        """
        import os as _os

        state_dir = tmp_path / "state-claim"
        state_dir.mkdir()
        session = "claim-session"
        sig = "deadbeefcafef00d"
        n = 30

        env = dict(_os.environ)
        env["CLAUDE_ROUTING_STATE_DIR"] = str(state_dir)
        src = _PROC_CLAIM_SRC.format(lib=str(LIB_DIR), session=session, sig=sig)

        procs = [subprocess.Popen([sys.executable, "-c", src], env=env) for _ in range(n)]
        winners = sum(1 for p in procs if p.wait() == 0)
        assert winners == 1, f"expected exactly one claimer, got {winners}"

    def test_claim_then_reclaim_same_signature_is_false(self, tmp_path, monkeypatch):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", tmp_path / "state")
        assert ros.claim_dispatch("s", "sig-1") is True
        assert ros.claim_dispatch("s", "sig-1") is False
