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
from typing import ClassVar
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


def _query_telemetry(db_env):
    """Read every telemetry_runs row directly (ADR: learning-telemetry-envelope)."""
    sys.path.insert(0, str(LIB_DIR))
    import sqlite3

    import learning_db_v2 as ldb

    ldb.init_db()
    conn = sqlite3.connect(ldb.get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM telemetry_runs").fetchall()]
    finally:
        conn.close()


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

    def test_telemetry_envelope_row_written_on_marked_dispatch(self, db_env, tmp_path, monkeypatch):
        # ADR: learning-telemetry-envelope — a /do-marked dispatch writes ONE
        # envelope row alongside the decision row, with always-derivable fields set.
        a = _load(A_PATH, "rdr_tel_marked")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        sys.path.insert(0, str(LIB_DIR))
        import telemetry_capture as tc

        monkeypatch.setattr(tc, "_STATE_DIR", tmp_path / "telstate")
        event = _agent_event(skill="go-patterns", session="tel-s1")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        rows = _query_telemetry(db_env)
        assert len(rows) == 1
        row = rows[0]
        assert row["topic"] == "routing"
        assert row["key"] == "python-general-engineer:go-patterns"
        assert row["session_id"] == "tel-s1"
        assert row["run_id"]
        assert row["git_sha"]
        assert row["source"] == "hook:routing-decision-recorder"

    def test_no_telemetry_row_when_marker_absent(self, db_env, tmp_path, monkeypatch):
        # No [do-route] marker => no decision row AND no envelope row.
        a = _load(A_PATH, "rdr_tel_nomarker")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        sys.path.insert(0, str(LIB_DIR))
        import telemetry_capture as tc

        monkeypatch.setattr(tc, "_STATE_DIR", tmp_path / "telstate")
        event = _agent_event(marker=False, body="Review this PR, no marker.")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        assert _query_telemetry(db_env) == []


# ---------------------------------------------------------------------------
# B — routing-outcome-recorder
# ---------------------------------------------------------------------------


def _seed_decision(key="python-general-engineer:go-patterns"):
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


class TestOutcomeValidator:
    """B (SubagentStop) NO LONGER scores. It validates the decision row exists
    and keeps the entry PROVISIONAL (revalidated) for the next-turn finalizer;
    late rows are re-queued. Confidence must NOT change at SubagentStop."""

    def test_validated_entry_kept_pending_not_scored(self, db_env, monkeypatch):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        state_dir = db_env["state"]
        monkeypatch.setattr(ros, "_STATE_DIR", state_dir)
        session = "validate-1"
        key = _seed_decision()
        ros.append_pending_outcome(session, key, errors=False)
        before = next(r for r in _query_routing(db_env) if r["key"] == key)

        b = _load(B_PATH, "ror_validate")
        event = {"hook_event_name": "SubagentStop", "session_id": session}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            b.main()

        after = next(r for r in _query_routing(db_env) if r["key"] == key)
        # No scoring at SubagentStop.
        assert after["success_count"] == before["success_count"]
        assert after["failure_count"] == before["failure_count"]
        assert after["confidence"] == before["confidence"]
        # Entry stayed pending (revalidated), attempts NOT advanced.
        still = ros.peek_pending_outcomes(session)
        assert len(still) == 1 and still[0]["key"] == key
        assert still[0]["attempts"] == 0

    def test_missing_row_requeued_with_attempt(self, db_env, monkeypatch):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        session = "validate-late"
        key = "python-general-engineer:no-row-yet"
        ros.append_pending_outcome(session, key, errors=True)

        b = _load(B_PATH, "ror_validate_late")
        event = {"hook_event_name": "SubagentStop", "session_id": session}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            b.main()
        still = ros.peek_pending_outcomes(session)
        assert len(still) == 1
        assert still[0]["attempts"] == 1  # re-queued, not revalidated

    def test_exit_zero_on_empty_and_malformed(self, db_env):
        assert _run_hook(B_PATH, {}).returncode == 0
        assert (
            subprocess.run([sys.executable, str(B_PATH)], input="not json", capture_output=True, text=True).returncode
            == 0
        )
        assert subprocess.run([sys.executable, str(B_PATH)], input="", capture_output=True, text=True).returncode == 0


# ---------------------------------------------------------------------------
# Finalizer (UserPromptSubmit) — next-turn resolution: reaction + error + re-route
# ---------------------------------------------------------------------------

F_PATH = HOOKS_DIR / "routing-outcome-finalizer.py"


def _prompt_event(prompt, session="s1"):
    return {"hook_event_name": "UserPromptSubmit", "session_id": session, "prompt": prompt}


class TestFinalizer:
    def _pend(self, ros, session, key, errors=False):
        ros.append_pending_outcome(session, key, errors=errors)

    def test_acceptance_boosts(self, db_env, monkeypatch):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision()
        self._pend(ros, "fin-acc", key, errors=False)
        before = next(r for r in _query_routing(db_env) if r["key"] == key)["confidence"]

        f = _load(F_PATH, "fin1")
        ev = _prompt_event("looks good, merge it", session="fin-acc")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
            f.main()
        after = next(r for r in _query_routing(db_env) if r["key"] == key)
        assert after["success_count"] == 1
        assert after["confidence"] > before

    def test_neutral_new_topic_boosts(self, db_env, monkeypatch):
        # No complaint = success, matching the old LLM's "user accepted" default.
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision("python-general-engineer:neutral")
        self._pend(ros, "fin-neu", key, errors=False)

        f = _load(F_PATH, "fin2")
        ev = _prompt_event("now add a CHANGELOG entry for the release", session="fin-neu")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
            f.main()
        after = next(r for r in _query_routing(db_env) if r["key"] == key)
        assert after["success_count"] == 1
        assert after["failure_count"] == 0

    def test_rejection_decays(self, db_env, monkeypatch):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision("python-general-engineer:rejected")
        self._pend(ros, "fin-rej", key, errors=False)

        f = _load(F_PATH, "fin3")
        ev = _prompt_event("that's wrong, redo it", session="fin-rej")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
            f.main()
        after = next(r for r in _query_routing(db_env) if r["key"] == key)
        assert after["failure_count"] == 1
        assert after["success_count"] == 0

    def test_reroute_decays(self, db_env, monkeypatch):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision("python-general-engineer:rerouted")
        self._pend(ros, "fin-rr", key, errors=False)

        f = _load(F_PATH, "fin_rr")
        # Re-route now decays ONLY via the complaint-anchored literal "wrong agent"
        # (prose re-route detection was removed); the trailing "use a different
        # agent" no longer matters.
        ev = _prompt_event("wrong agent — use a different agent for this", session="fin-rr")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
            f.main()
        after = next(r for r in _query_routing(db_env) if r["key"] == key)
        assert after["failure_count"] == 1

    def test_tool_error_fails_despite_positive_turn(self, db_env, monkeypatch):
        # errors=True dispatch => failure even when the next turn is praise.
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision("python-general-engineer:errored")
        self._pend(ros, "fin-err", key, errors=True)

        f = _load(F_PATH, "fin4")
        ev = _prompt_event("thanks, looks great!", session="fin-err")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
            f.main()
        after = next(r for r in _query_routing(db_env) if r["key"] == key)
        assert after["failure_count"] == 1
        assert after["success_count"] == 0

    def test_benign_wrong_in_new_request_does_not_decay(self, db_env, monkeypatch):
        # HIGH-PRECISION: a NEW unrelated request that merely contains the word
        # "wrong" must NOT falsely decay the prior dispatch.
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision("python-general-engineer:benign")
        self._pend(ros, "fin-benign", key, errors=False)

        f = _load(F_PATH, "fin5")
        # "wrong" appears, but as part of a new feature request, not a rejection.
        ev = _prompt_event(
            "Add a unit test for the function that detects wrong-format input dates.",
            session="fin-benign",
        )
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
            f.main()
        after = next(r for r in _query_routing(db_env) if r["key"] == key)
        assert after["failure_count"] == 0, "benign 'wrong' falsely decayed the prior dispatch"
        assert after["success_count"] == 1

    def test_idempotent_double_prompt_scores_once(self, db_env, monkeypatch):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision("python-general-engineer:idem")
        self._pend(ros, "fin-idem", key, errors=False)

        ev = _prompt_event("looks good", session="fin-idem")
        for i in range(3):  # re-delivered / duplicate prompts
            f = _load(F_PATH, f"fin_idem_{i}")
            with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
                f.main()
        after = next(r for r in _query_routing(db_env) if r["key"] == key)
        assert after["success_count"] == 1, "double prompt double-scored"

    def test_missing_decision_row_revalidated_not_crashed(self, db_env, monkeypatch):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        session = "fin-norow"
        ros.append_pending_outcome(session, "ghost:skill", errors=False)

        f = _load(F_PATH, "fin6")
        ev = _prompt_event("ok next", session=session)
        with patch("sys.exit") as ex, patch("sys.stdin.read", return_value=json.dumps(ev)):
            f.main()
        ex.assert_called_with(0)
        # Put back (revalidated) for a later resolver, not lost.
        assert ros.peek_pending_outcomes(session)

    def test_malformed_created_entry_does_not_abort_sibling_scoring(self, db_env, monkeypatch):
        # LOW: one pending entry with a non-numeric `created` must be SKIPPED
        # without aborting scoring for the other (valid) entries this turn.
        import json as _json

        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        session = "fin-malformed-created"
        good_key = _seed_decision("python-general-engineer:good-sibling")
        # Append a valid sibling, then inject a malformed-`created` entry directly.
        ros.append_pending_outcome(session, good_key, errors=False)
        path = ros._state_file(session)
        with ros._state_lock(path):
            data = ros._load(path)
            data["pending"].append(
                {"key": "python-general-engineer:bad-sibling", "errors": False, "attempts": 0, "created": "NaN-oops"}
            )
            ros._atomic_write(path, data)

        f = _load(F_PATH, "fin_malformed")
        ev = _prompt_event("now write the docs", session=session)  # neutral => success
        with patch("sys.exit"), patch("sys.stdin.read", return_value=_json.dumps(ev)):
            f.main()
        # The valid sibling still scored (success); the malformed one was skipped.
        after = next(r for r in _query_routing(db_env) if r["key"] == good_key)
        assert after["success_count"] == 1, "malformed sibling aborted scoring of the valid entry"
        assert after["failure_count"] == 0

    def test_exit_zero_on_empty_and_malformed(self, db_env):
        assert _run_hook(F_PATH, {}).returncode == 0
        assert (
            subprocess.run([sys.executable, str(F_PATH)], input="not json", capture_output=True, text=True).returncode
            == 0
        )
        assert subprocess.run([sys.executable, str(F_PATH)], input="", capture_output=True, text=True).returncode == 0

    def test_marker_unit_high_precision(self):
        f = _load(F_PATH, "fin_unit")
        # Clear complaints about the prior work => True. (Prose re-route detection
        # was REMOVED; the only surviving re-route signal is the complaint-anchored
        # literal "wrong agent/skill" — bare "use a different skill" is now benign.)
        for p in [
            "that's wrong",
            "that's worse",
            "revert that",
            "that didn't work",
            "not what I wanted",
            "wrong agent",
            "wrong skill",
        ]:
            assert f.is_rejection(p) is True, p
        # Benign / neutral / acceptance / instructional => False. The STANDALONE
        # rework arms (redo it/that/this, start over, try again) were removed
        # (codex C1): a bare rework imperative is a benign follow-up (new task /
        # apply-elsewhere / parameter change), NOT a complaint about the prior
        # route, so it must score SUCCESS. Genuine complaints carrying these verbs
        # still fire via their complaint clause (covered above + in NAMED_GENUINE).
        for p in [
            "Add a test for wrong-format dates.",
            "looks good, merge it",
            "now write the docs",
            "thanks!",
            "use a different skill",  # bare re-route prose — no complaint anchor
            "redo it",  # bare rework imperative — benign follow-up (C1)
            "start over",  # bare rework imperative — benign follow-up (C1)
            "try again",  # bare rework imperative — benign follow-up (C1)
            "",
            None,
        ]:
            assert f.is_rejection(p) is False, p


# ---------------------------------------------------------------------------
# A + B integration: route-health closes the loop
# ---------------------------------------------------------------------------


class TestEndToEndLoop:
    def test_decision_validate_finalize_closes_loop(self, db_env, monkeypatch):
        # Full path: A writes decision + pending; B validates (no score); the
        # next-turn finalizer (UserPromptSubmit) scores once on user acceptance.
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        a = _load(A_PATH, "rdr_e1")
        b = _load(B_PATH, "ror_e1")
        f = _load(HOOKS_DIR / "routing-outcome-finalizer.py", "fin_e1")
        session = "loop-1"
        event_a = _agent_event(skill="go-patterns", session=session)
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event_a)):
            a.main()
        # SubagentStop validates only — confidence unchanged here.
        event_b = {"hook_event_name": "SubagentStop", "session_id": session}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event_b)):
            b.main()
        mid = next(r for r in _query_routing(db_env) if r["key"] == "python-general-engineer:go-patterns")
        assert mid["success_count"] == 0
        # Next user turn (acceptance) finalizes => success.
        event_f = {"hook_event_name": "UserPromptSubmit", "session_id": session, "prompt": "great, thanks"}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event_f)):
            f.main()
        decision = next(r for r in _query_routing(db_env) if r["key"] == "python-general-engineer:go-patterns")
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
        import routing_outcome_state as ros

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

        # The shared scorer's keyed existence check MUST still find it.
        import routing_outcome_score as score

        assert score.decision_row_exists(target) is True

        # And the finalizer applies the outcome (failure_count increments) —
        # not skipped — even for a beyond-top-1000 decayed target.
        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        ros.append_pending_outcome("beyond1000", target, errors=True)
        before = next(r for r in _query_routing_all(db_env) if r["key"] == target)["failure_count"]
        f = _load(HOOKS_DIR / "routing-outcome-finalizer.py", "fin_keyed")
        event = {"hook_event_name": "UserPromptSubmit", "session_id": "beyond1000", "prompt": "ok next"}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            f.main()
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
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
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

        # Two pending entries in the SAME session: only `bad` carries errors=True.
        session = "attrib"
        ros.append_pending_outcome(session, good, errors=False)
        ros.append_pending_outcome(session, bad, errors=True)

        # Neutral next turn (no rejection): good=success (own flag), bad=failure
        # (own flag). The session-level reaction does NOT broadcast errors.
        f = _load(HOOKS_DIR / "routing-outcome-finalizer.py", "fin_attrib")
        event = {"hook_event_name": "UserPromptSubmit", "session_id": session, "prompt": "ok, next task"}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            f.main()

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
    def test_missing_row_requeued_then_finalized(self, db_env, monkeypatch):
        """B fires before A's decision row is visible => entry re-queued. Once
        the row lands, B revalidates it (still pending) and the next-turn
        finalizer scores it (no data loss)."""
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

        # Entry must be RE-QUEUED (attempts incremented), not dropped or scored.
        still = ros.peek_pending_outcomes(session)
        assert len(still) == 1
        assert still[0]["key"] == key
        assert still[0]["attempts"] == 1

        # Now the decision row lands (action A late).
        import learning_db_v2 as ldb

        ldb.record_learning(
            topic="routing",
            key=key,
            value=f"routing-decision: {key} tool_errors=1",
            category="effectiveness",
            source="test",
        )

        # Next SubagentStop revalidates (row now visible) — still no scoring.
        b2 = _load(B_PATH, "ror_late2")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            b2.main()
        row_mid = next(r for r in _query_routing_all(db_env) if r["key"] == key)
        assert row_mid["failure_count"] == 0

        # Next user turn finalizes: errors=True dispatch => failure.
        f = _load(HOOKS_DIR / "routing-outcome-finalizer.py", "fin_late")
        evf = {"hook_event_name": "UserPromptSubmit", "session_id": session, "prompt": "ok next"}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(evf)):
            f.main()
        row = next(r for r in _query_routing_all(db_env) if r["key"] == key)
        assert row["failure_count"] == 1, "late-landing decision row was not finalized"

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
# Stop fallback — autonomous / no-next-prompt runs resolve via error flag alone
# ---------------------------------------------------------------------------

STOP_PATH = HOOKS_DIR / "session-learning-recorder.py"


class TestStopFallback:
    def test_session_end_resolves_pending_via_error_flag(self, db_env, monkeypatch):
        """No next user prompt: the Stop hook resolves still-pending dispatches
        using each dispatch's own error flag (the deterministic floor)."""
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        ok = _seed_decision("python-general-engineer:auto-ok")
        bad = _seed_decision("python-general-engineer:auto-bad")
        session = "autorun"
        ros.append_pending_outcome(session, ok, errors=False)
        ros.append_pending_outcome(session, bad, errors=True)

        s = _load(STOP_PATH, "stop1")
        event = {"hook_event_name": "Stop", "session_id": session, "session_data": {"files_modified": ["x"]}}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            s.main()

        ok_row = next(r for r in _query_routing_all(db_env) if r["key"] == ok)
        bad_row = next(r for r in _query_routing_all(db_env) if r["key"] == bad)
        assert ok_row["success_count"] == 1  # no error => boost
        assert bad_row["failure_count"] == 1  # error => decay
        # Pending cleared — nothing left to double-resolve.
        assert ros.peek_pending_outcomes(session) == []

    def test_stop_does_not_double_resolve_finalized(self, db_env, monkeypatch):
        """A dispatch already finalized (and cleared) by UserPromptSubmit must
        NOT be scored a second time at Stop."""
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision("python-general-engineer:once")
        session = "once-session"
        ros.append_pending_outcome(session, key, errors=False)

        # UserPromptSubmit finalizes (success) and clears pending.
        f = _load(F_PATH, "fin_once")
        evf = {"hook_event_name": "UserPromptSubmit", "session_id": session, "prompt": "thanks, great"}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(evf)):
            f.main()
        # Stop fallback runs afterwards — pending already empty => no second score.
        s = _load(STOP_PATH, "stop2")
        evs = {"hook_event_name": "Stop", "session_id": session, "session_data": {"files_modified": ["x"]}}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(evs)):
            s.main()
        row = next(r for r in _query_routing_all(db_env) if r["key"] == key)
        assert row["success_count"] == 1, "Stop double-resolved a finalized dispatch"

    def test_stop_exits_zero_on_malformed(self):
        assert _run_hook(STOP_PATH, {}).returncode == 0
        assert (
            subprocess.run(
                [sys.executable, str(STOP_PATH)], input="not json", capture_output=True, text=True
            ).returncode
            == 0
        )


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


# ---------------------------------------------------------------------------
# HIGH-1 — turn-level rejection is attributable only on a SINGLE pending dispatch
# ---------------------------------------------------------------------------


class TestSingleDispatchAttribution:
    """A turn-level reaction ("that's wrong, redo it") can only be pinned to a
    route when exactly ONE dispatch is pending this turn. /do Phase 4 fans out
    multiple agents per turn; broadcasting the reaction across N parallel
    siblings would re-decay correct routes (the sibling-misattribution bug on the
    reaction axis). So with >1 pending, each entry resolves by its OWN errors flag
    and the turn-level reaction is IGNORED."""

    def _seed(self, ldb, key):
        ldb.record_learning(
            topic="routing",
            key=key,
            value=f"routing-decision: {key} tool_errors=0",
            category="effectiveness",
            source="test",
        )

    def test_multi_dispatch_rejection_not_broadcast(self, db_env, monkeypatch):
        # Two CLEAN parallel dispatches + "that's wrong, redo it" => NEITHER
        # sibling is decayed (the reaction is unattributable across siblings).
        sys.path.insert(0, str(LIB_DIR))
        import learning_db_v2 as ldb
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        a = "python-general-engineer:sib-a"
        b = "golang-general-engineer:sib-b"
        for key in (a, b):
            self._seed(ldb, key)
        a_before = next(r for r in _query_routing_all(db_env) if r["key"] == a)["confidence"]
        b_before = next(r for r in _query_routing_all(db_env) if r["key"] == b)["confidence"]

        session = "multi-rej"
        ros.append_pending_outcome(session, a, errors=False)
        ros.append_pending_outcome(session, b, errors=False)

        f = _load(F_PATH, "fin_multi_rej")
        ev = _prompt_event("that's wrong, redo it", session=session)
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
            f.main()

        a_after = next(r for r in _query_routing_all(db_env) if r["key"] == a)
        b_after = next(r for r in _query_routing_all(db_env) if r["key"] == b)
        # Both clean siblings score SUCCESS, neither decayed by the ambiguous turn.
        assert a_after["failure_count"] == 0 and b_after["failure_count"] == 0
        assert a_after["success_count"] == 1 and b_after["success_count"] == 1
        assert a_after["confidence"] > a_before and b_after["confidence"] > b_before

    def test_multi_dispatch_per_entry_error_still_fails(self, db_env, monkeypatch):
        # With >1 pending, the IGNORED turn-reaction does not stop a per-entry
        # tool error from failing its own key (per-entry attribution preserved).
        sys.path.insert(0, str(LIB_DIR))
        import learning_db_v2 as ldb
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        clean = "python-general-engineer:multi-clean"
        errd = "golang-general-engineer:multi-errd"
        for key in (clean, errd):
            self._seed(ldb, key)

        session = "multi-mixed"
        ros.append_pending_outcome(session, clean, errors=False)
        ros.append_pending_outcome(session, errd, errors=True)

        f = _load(F_PATH, "fin_multi_mixed")
        # Even a benign-looking turn: per-entry error decides each key.
        ev = _prompt_event("ok, next task", session=session)
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
            f.main()
        clean_after = next(r for r in _query_routing_all(db_env) if r["key"] == clean)
        errd_after = next(r for r in _query_routing_all(db_env) if r["key"] == errd)
        assert clean_after["success_count"] == 1 and clean_after["failure_count"] == 0
        assert errd_after["failure_count"] == 1 and errd_after["success_count"] == 0

    def test_single_dispatch_rejection_decays(self, db_env, monkeypatch):
        # A SINGLE clean dispatch + "that's wrong" => attributable => decayed.
        sys.path.insert(0, str(LIB_DIR))
        import learning_db_v2 as ldb
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        only = "python-general-engineer:solo"
        self._seed(ldb, only)

        session = "single-rej"
        ros.append_pending_outcome(session, only, errors=False)

        f = _load(F_PATH, "fin_single_rej")
        ev = _prompt_event("that's wrong, redo it", session=session)
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
            f.main()
        after = next(r for r in _query_routing_all(db_env) if r["key"] == only)
        assert after["failure_count"] == 1 and after["success_count"] == 0


# ---------------------------------------------------------------------------
# HIGH-2 — clause-scoped, acceptance-precedence false-failure precision
# ---------------------------------------------------------------------------


class TestRejectionPrecision:
    """is_rejection() must be high-precision: benign prompts that merely contain
    a rework verb in a LATER clause (new work, not a complaint) score SUCCESS;
    only the user's IMMEDIATE reaction (first clause) is tested. Acceptance in
    the first clause takes precedence over a later rework-shaped clause."""

    BENIGN: ClassVar = [
        "thanks, that worked. redo it for the other file",
        "great, now start over on the README",
        "the workflow should roll back on failure; document that",
        "looks good. now refactor the parser",
        "perfect, switch to a different file and add the same test",
    ]
    GENUINE: ClassVar = [
        "that's wrong, redo it",
        "wrong agent, use a different agent",
        # "that's not what I wanted" is a self-contained first-clause complaint.
        "that's not what I wanted",
        "that didn't work, try again",
        "revert that change",
        # Dead-pattern fix: a leading bare "no"/"nope" reaction + a `that's`
        # complaint is now caught on the RAW prompt (not the comma-severed first
        # clause). The old `\b(no,? that's…)\b` pattern could never match because
        # the clause splitter severed "no" from "that's" first.
        "no, that's not what I asked for",
        "nope, that's wrong",
    ]

    # The EXACT phrases the confirmation review named as false-positives. Prose
    # re-route / spec / conditional / docs prompts that must ALL classify SUCCESS.
    # Listed verbatim — these are the regression guards for HIGH-2.
    NAMED_BENIGN: ClassVar = [
        "the migration should roll back the change on failure",
        "explain when to use a different approach for caching",
        "we should have used a cache here, and document the skill matrix",
        "can you use a different approach here",
        "try a different approach to memoization",
        "undo the change only if the checksum fails",
        "document when to use a different agent",
        "we should have used a different skill for this",
        "thanks, that worked. redo it for the other file",
        "great, now start over on the README",
        # Leading-"no"/"undo" benign guards: a bare "no"/"undo"/"rollback" token
        # that is NOT the absolute-start reaction + complaint must stay SUCCESS.
        # These guard the dead-pattern fix's `^\s*(no|nope)\b` anchor against
        # over-firing on the word "no"/"undo" mid-sentence.
        "there is no cache here, document it",
        "undo is hard here; explain how to revert a squashed merge",
        "the rollback procedure didn't work in staging, document it",
        # codex C1: BARE rework imperatives are benign follow-ups, not complaints
        # about the just-completed route (apply-elsewhere / new task / parameter
        # change). The standalone redo/start-over/try-again arms were removed, so
        # these must classify SUCCESS — decaying them violates "never worse than
        # the proxy" in the common single-dispatch path.
        "redo it for the other file",
        "start over on the README",
        "try again with a smaller batch size",
        "redo the diagram so it matches",
        "start over with a cleaner schema",
    ]
    # Genuine complaints the review named as must-still-FAIL.
    NAMED_GENUINE: ClassVar = [
        "that's wrong, redo it",
        "that didn't work",
        "revert that, you broke the build",
        "that's worse than before",
        # Dead-pattern fix: leading "no"/"nope" reaction + `that's` complaint.
        "no, that's not what I asked for",
        "nope, that's wrong",
    ]

    def test_benign_first_clause_not_rejection(self):
        f = _load(F_PATH, "fin_precision_benign")
        for p in self.BENIGN:
            assert f.is_rejection(p) is False, f"benign prompt falsely flagged: {p!r}"

    def test_genuine_rejection_is_rejection(self):
        f = _load(F_PATH, "fin_precision_genuine")
        for p in self.GENUINE:
            assert f.is_rejection(p) is True, f"genuine rejection missed: {p!r}"

    def test_named_benign_phrases_classify_success(self):
        # The exact review-named false-positives must NOT be rejections.
        f = _load(F_PATH, "fin_named_benign")
        for p in self.NAMED_BENIGN:
            assert f.is_rejection(p) is False, f"review-named benign falsely flagged: {p!r}"

    def test_named_genuine_phrases_classify_failure(self):
        # The exact review-named genuine complaints must remain rejections.
        f = _load(F_PATH, "fin_named_genuine")
        for p in self.NAMED_GENUINE:
            assert f.is_rejection(p) is True, f"review-named genuine missed: {p!r}"

    def test_benign_prompt_scores_success_end_to_end(self, db_env, monkeypatch):
        # A single dispatch + a benign "redo it in a later clause" prompt => the
        # reaction is acceptance/neutral in the first clause => SUCCESS, no decay.
        sys.path.insert(0, str(LIB_DIR))
        import learning_db_v2 as ldb
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        for i, prompt in enumerate(self.BENIGN):
            key = f"python-general-engineer:benign-{i}"
            ldb.record_learning(
                topic="routing",
                key=key,
                value=f"routing-decision: {key} tool_errors=0",
                category="effectiveness",
                source="test",
            )
            session = f"benign-e2e-{i}"
            ros.append_pending_outcome(session, key, errors=False)
            f = _load(F_PATH, f"fin_benign_e2e_{i}")
            ev = _prompt_event(prompt, session=session)
            with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
                f.main()
            after = next(r for r in _query_routing_all(db_env) if r["key"] == key)
            assert after["failure_count"] == 0, f"benign prompt decayed route: {prompt!r}"
            assert after["success_count"] == 1

    def test_named_rollback_phrase_scores_success_end_to_end(self, db_env, monkeypatch):
        # Spec-required E2E: a single clean dispatch + the review's roll-back spec
        # phrase => SUCCESS (success_count=1, failure_count=0), no decay.
        sys.path.insert(0, str(LIB_DIR))
        import learning_db_v2 as ldb
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = "python-general-engineer:rollback-spec"
        ldb.record_learning(
            topic="routing",
            key=key,
            value=f"routing-decision: {key} tool_errors=0",
            category="effectiveness",
            source="test",
        )
        session = "named-rollback-e2e"
        ros.append_pending_outcome(session, key, errors=False)
        f = _load(F_PATH, "fin_named_rollback_e2e")
        ev = _prompt_event("the migration should roll back the change on failure", session=session)
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
            f.main()
        after = next(r for r in _query_routing_all(db_env) if r["key"] == key)
        assert after["success_count"] == 1, "named roll-back spec phrase failed to score success"
        assert after["failure_count"] == 0, "named roll-back spec phrase falsely decayed route"


# ---------------------------------------------------------------------------
# MEDIUM-1 — orphan (no decision row) is attempt-bounded at the finalizer too
# ---------------------------------------------------------------------------


class TestFinalizerOrphanBounded:
    """A pending entry whose decision row was NEVER written must be routed
    through the attempt-bounded requeue at UserPromptSubmit (increments attempts,
    dropped at MAX_REQUEUE_ATTEMPTS) — not the attempt-preserving revalidate that
    lets a never-written-row orphan linger up to 24h."""

    def test_orphan_dropped_after_max_requeue_passes(self, db_env, monkeypatch):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        session = "fin-orphan"
        key = "ghost-agent:ghost-skill"
        ros.append_pending_outcome(session, key, errors=False)

        # Each finalizer pass finds no decision row => requeue (attempts+1).
        # After MAX_REQUEUE_ATTEMPTS passes the orphan is dropped.
        for i in range(ros.MAX_REQUEUE_ATTEMPTS + 1):
            f = _load(F_PATH, f"fin_orphan_{i}")
            ev = _prompt_event("ok next", session=session)
            with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
                f.main()

        remaining = ros.peek_pending_outcomes(session)
        assert remaining == [], f"orphan not dropped by finalizer after cap: {remaining}"

    def test_orphan_attempts_increment_each_pass(self, db_env, monkeypatch):
        # Distinguishes requeue (increments) from revalidate (preserves): after
        # one finalizer pass the orphan's attempts must be 1, not 0.
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        session = "fin-orphan-attempt"
        key = "ghost-agent:ghost-skill"
        ros.append_pending_outcome(session, key, errors=False)

        f = _load(F_PATH, "fin_orphan_attempt")
        ev = _prompt_event("ok next", session=session)
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
            f.main()
        still = ros.peek_pending_outcomes(session)
        assert len(still) == 1 and still[0]["attempts"] == 1, still
