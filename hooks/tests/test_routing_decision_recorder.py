#!/usr/bin/env python3
"""Tests for the routing-decision-recorder (A) and routing-outcome-recorder (B) hooks.

Covers:
- A records the expected `routing` decision row from a synthetic PostToolUse:Agent event.
- A reads agent + skill from the [do-route] marker; agent-only when skill=-.
- A records ONLY /do-routed dispatches: marker present => recorded; marker
  absent (reviewer sub-agent / nested fan-out) => skipped.
- A records Workflow dispatches (/do Complex): one decision per line-start
  [do-route] marker in tool_input.script; a resubmitted script (workflow
  resume) is a no-op; the Agent path is unchanged.
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
import os
import shutil
import sqlite3
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


@pytest.fixture(scope="module")
def db_template(tmp_path_factory):
    """One freshly initialized learning.db per module.

    A fresh init_db() costs ~0.1s of sqlite fsyncs; copying the finished file
    costs almost nothing. Each test gets its own copy, so isolation holds.
    """
    sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    template = tmp_path_factory.mktemp("learning-template")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("CLAUDE_LEARNING_DIR", str(template))
        mp.setattr(ldb, "_initialized", False, raising=False)
        ldb.init_db()
        with ldb.get_connection() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return template / "learning.db"


@pytest.fixture()
def db_env(tmp_path, monkeypatch, db_template):
    """Point the learning DB and the bridge state dir at a throwaway location."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    shutil.copyfile(db_template, db_dir / "learning.db")
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    sys.path.insert(0, str(LIB_DIR))
    # init_db() against this tmp dir: learning_db_v2 caches _initialized as a
    # module global across in-process tests. On the copied schema it is a
    # cheap no-op pass (migrations already applied).
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


def _workflow_event(script, *, session="wf-s1", output="ok", is_error=False, description=""):
    """Build a synthetic PostToolUse:Workflow event (/do Complex dispatch).

    The Workflow tool's inner agent() calls fire NO PostToolUse:Agent event —
    the harness emits ONE PostToolUse with tool_name "Workflow" whose
    tool_input.script carries every worker prompt, [do-route] markers included.
    """
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Workflow",
        "session_id": session,
        "tool_input": {"description": description, "script": script},
        "tool_result": {"output": output, "is_error": is_error},
    }


# Two workers, two line-start markers, distinct gate inputs per marker line.
_TWO_MARKER_SCRIPT = (
    "results = []\n"
    'prompt_a = """\n'
    "[do-route] agent=python-general-engineer skill=programming complexity=Complex health=-\n"
    "Fix the bug.\n"
    '"""\n'
    'prompt_b = """\n'
    "[do-route] agent=hook-development-engineer skill=pr-workflow complexity=Complex health=0.8 n=6 fail=1 action=keep\n"
    "Open the PR.\n"
    '"""\n'
    'results.append(agent("python-general-engineer", prompt=prompt_a))\n'
    'results.append(agent("hook-development-engineer", prompt=prompt_b))\n'
)


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
        event = _agent_event(skill="testing", body="Write tests.")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        rows = _query_routing(db_env)
        keys = {r["key"] for r in rows}
        assert "python-general-engineer:testing" in keys
        row = next(r for r in rows if r["key"] == "python-general-engineer:testing")
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
            body='Review this PR. Skill("review") load the security skill.',
        )
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        assert _query_routing(db_env) == []

    def test_error_flag_when_result_errored(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_a3")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _agent_event(
            skill="programming",
            output="fatal: permission denied",
            is_error=True,
        )
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        row = next(r for r in _query_routing(db_env) if r["key"] == "python-general-engineer:programming")
        assert "tool_errors=1" in row["value"]

    def test_rightsizing_row_recorded(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_a4")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _agent_event(
            skill="review",
            output="done. rightsizing: tier=3 files=15 packages=4 agents_dispatched=17",
        )
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        keys = {r["key"] for r in _query_routing(db_env)}
        assert "rightsizing:tier3" in keys

    def test_rightsizing_row_recorded_from_live_content_block_shape(self, db_env, monkeypatch):
        # LIVE PAYLOAD REGRESSION: a real Agent (Task) dispatch returns its final
        # message as the Anthropic content-block shape — a LIST of
        # {"type":"text","text":...} blocks — NOT the Bash-style {"output": str}
        # the other tests simulate. The old get_tool_output read only output/stdout
        # string keys, so it returned "" for this shape and the banner was missed
        # (decision + telemetry rows still recorded). This drives the fix.
        a = _load(A_PATH, "rdr_live_blocks")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        banner = (
            "rightsizing: tier=3 files=5 packages=3 agents_dispatched=17 "
            "findings=1C/13H/24M tokens=1984536 wall_clock_s=1667"
        )
        event = _agent_event(skill="review")
        # Replace the Bash-style result with the LIVE content-block list shape
        # under tool_response (the key live Agent dispatches populate).
        event["tool_response"] = [{"type": "text", "text": f"summary...\n{banner}"}]
        event.pop("tool_result", None)
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        row = next(r for r in _query_routing(db_env) if r["key"] == "rightsizing:tier3")
        assert "sum_critical: 1" in row["value"]
        assert "sum_high: 13" in row["value"]
        assert "sum_medium: 24" in row["value"]
        assert "sum_tokens: 1984536" in row["value"]
        assert "sum_wall_clock_s: 1667" in row["value"]

    def test_no_rightsizing_row_when_banner_absent(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_a5")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _agent_event(skill="programming", output="plain output")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        keys = {r["key"] for r in _query_routing(db_env)}
        assert not any(k.startswith("rightsizing:") for k in keys)

    def test_rightsizing_row_records_findings(self, db_env, monkeypatch):
        # ADR review-tier-roi test 1: a banner carrying findings= adds the
        # severity counts to the tier's running sums (one findings-bearing review).
        a = _load(A_PATH, "rdr_findings")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _agent_event(
            skill="review",
            output="done. rightsizing: tier=3 files=15 packages=4 agents_dispatched=17 findings=2C/3H/5M",
        )
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        row = next(r for r in _query_routing(db_env) if r["key"] == "rightsizing:tier3")
        assert "sum_critical: 2" in row["value"]
        assert "sum_high: 3" in row["value"]
        assert "sum_medium: 5" in row["value"]
        assert "n_findings: 1" in row["value"]

    def test_rightsizing_sums_accumulate_a_true_mean(self, db_env, monkeypatch):
        # The fix's core: two findings-bearing reviews at one tier accumulate
        # into running sums (2+5 critical over n_findings=2 => mean 3.5), NOT
        # the last sample. Two banners must not overwrite each other.
        a = _load(A_PATH, "rdr_mean")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        for out, sess in (
            ("rightsizing: tier=3 files=15 packages=4 agents_dispatched=17 findings=2C/1H/0M", "s1"),
            ("rightsizing: tier=3 files=15 packages=4 agents_dispatched=17 findings=5C/3H/4M", "s2"),
        ):
            event = _agent_event(skill="review", output=f"done. {out}", session=sess)
            with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
                a.main()
        row = next(r for r in _query_routing(db_env) if r["key"] == "rightsizing:tier3")
        assert "sum_critical: 7" in row["value"]  # 2 + 5
        assert "sum_high: 4" in row["value"]  # 1 + 3
        assert "n_findings: 2" in row["value"]

    def test_rightsizing_row_records_cost_fields(self, db_env, monkeypatch):
        # ADR review-tier-roi: optional tokens= and wall_clock_s= enter the sums.
        a = _load(A_PATH, "rdr_cost")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _agent_event(
            skill="review",
            output=(
                "done. rightsizing: tier=2 files=8 packages=2 agents_dispatched=12 "
                "findings=0C/1H/2M tokens=52000 wall_clock_s=180"
            ),
        )
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        row = next(r for r in _query_routing(db_env) if r["key"] == "rightsizing:tier2")
        assert "sum_tokens: 52000" in row["value"]
        assert "n_tokens: 1" in row["value"]
        assert "sum_wall_clock_s: 180" in row["value"]

    def test_legacy_rightsizing_banner_still_records(self, db_env, monkeypatch):
        # ADR review-tier-roi test 2: a four-field legacy banner (no findings=)
        # still records the tier row; it bumps `reviews` but no findings sum.
        a = _load(A_PATH, "rdr_legacy")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _agent_event(
            skill="review",
            output="done. rightsizing: tier=1 files=3 packages=1 agents_dispatched=3",
        )
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        row = next(r for r in _query_routing(db_env) if r["key"] == "rightsizing:tier1")
        assert "reviews: 1" in row["value"]
        assert "n_findings: 0" in row["value"]
        assert "sum_critical: 0" in row["value"]
        assert "n_tokens: 0" in row["value"]

    def test_legacy_review_does_not_pollute_findings_mean(self, db_env, monkeypatch):
        # A legacy (no-findings) review at a tier that also has a findings-bearing
        # review must NOT count into the findings denominator: n_findings stays 1
        # while `reviews` is 2. (The old single-row model lost this distinction.)
        a = _load(A_PATH, "rdr_mix")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        for out, sess in (
            ("rightsizing: tier=2 files=8 packages=2 agents_dispatched=12 findings=4C/2H/1M", "s1"),
            ("rightsizing: tier=2 files=8 packages=2 agents_dispatched=12", "s2"),  # legacy
        ):
            event = _agent_event(skill="review", output=f"done. {out}", session=sess)
            with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
                a.main()
        row = next(r for r in _query_routing(db_env) if r["key"] == "rightsizing:tier2")
        assert "reviews: 2" in row["value"]
        assert "n_findings: 1" in row["value"]
        assert "sum_critical: 4" in row["value"]  # only the findings-bearing review

    def test_idempotent_same_dispatch_recorded_once(self, db_env):
        # Use the real bridge state (redirected to tmp) so dedup engages.
        a = _load(A_PATH, "rdr_a6")
        event = _agent_event(skill="programming", session="dup-session")
        for _ in range(3):
            with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
                a.main()
        row = next(r for r in _query_routing(db_env) if r["key"] == "python-general-engineer:programming")
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
        event = _agent_event(skill="programming", session="tel-s1")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        rows = _query_telemetry(db_env)
        assert len(rows) == 1
        row = rows[0]
        assert row["topic"] == "routing"
        assert row["key"] == "python-general-engineer:programming"
        assert row["session_id"] == "tel-s1"
        assert row["run_id"]
        assert row["git_sha"]
        assert row["source"] == "hook:routing-decision-recorder"

    def test_fable_model_marker_is_accepted(self):
        """`fable` is a valid model wherever `opus` is; an unknown name is not."""
        a = _load(A_PATH, "rdr_fable_model")
        marker = "[do-route] agent=python-general-engineer skill=programming complexity=complex model={} effort=high"
        assert a.parse_model(marker.format("fable")) == "fable"
        assert a.parse_model(marker.format("opus")) == "opus"
        assert a.parse_model(marker.format("fabel")) is None

    def test_gpt_56_model_effort_is_persisted_in_route_evidence(self, db_env, monkeypatch):
        """The model-and-effort benchmark point survives the marker round-trip."""
        a = _load(A_PATH, "rdr_gpt_56_model_effort")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _agent_event(skill="programming", session="gpt-56-effort")
        event["tool_input"]["prompt"] = (
            "[do-route] agent=python-general-engineer skill=programming complexity=complex "
            "model=gpt-5.6-sol effort=xhigh health=-\nReview the implementation."
        )
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()

        decisions = [event for event in _read_events(db_env) if event["type"] == "decision"]
        assert decisions[0]["model"] == "gpt-5.6-sol@xhigh"

        sys.path.insert(0, str(LIB_DIR))
        import learning_db_v2 as ldb

        context = ldb.get_evidence_route_context("python-general-engineer:programming")
        assert context["recent"][0]["model"] == "gpt-5.6-sol@xhigh"

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


def _basis_counts(db_env) -> dict[str, int]:
    """Every routing_outcome_basis row as {basis: count}."""
    sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    with ldb.get_connection() as conn:
        rows = conn.execute("SELECT basis, SUM(count) AS n FROM routing_outcome_basis GROUP BY basis").fetchall()
    return {r["basis"]: int(r["n"]) for r in rows}


def _routing_row(db_env, key: str) -> dict:
    return next(r for r in _query_routing(db_env) if r["key"] == key)


class TestRouteFitBanner:
    """(D) The route-fit banner: the router's only signal that a pick was WRONG.

    Weighting is asymmetric on purpose and every test here pins that asymmetry:
    a negative verdict decays the route, `ok` moves confidence by exactly
    nothing. An `ok` that could boost would rebuild the metric this replaces —
    success inferred from the absence of a complaint.
    """

    KEY: ClassVar[str] = "python-general-engineer:programming"

    def _run(self, name, db_env, monkeypatch, output):
        a = _load(A_PATH, name)
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _agent_event(skill="programming", output=output)
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        return _routing_row(db_env, self.KEY)

    @pytest.mark.parametrize("verdict", ["wrong-agent", "wrong-skill", "needs-coordinator", "underspecified"])
    def test_negative_verdict_decays_the_route(self, verdict, db_env, monkeypatch):
        baseline = self._run(f"rf_base_{verdict}", db_env, monkeypatch, "no banner here")["confidence"]
        row = self._run(f"rf_neg_{verdict}", db_env, monkeypatch, f"work done.\nroute-fit: {verdict}")
        assert row["confidence"] < baseline
        assert row["failure_count"] == 1
        assert _basis_counts(db_env)[f"route_fit:{verdict}"] == 1

    def test_ok_never_boosts(self, db_env, monkeypatch):
        """WEAK evidence: recorded, counted, and worth zero confidence."""
        before = self._run("rf_ok_base", db_env, monkeypatch, "no banner here")
        after = self._run("rf_ok", db_env, monkeypatch, "all done.\nroute-fit: ok")
        assert after["confidence"] == before["confidence"]
        assert after["success_count"] == 0
        assert after["failure_count"] == 0
        assert _basis_counts(db_env)["route_fit:ok"] == 1

    def test_banner_absent_is_silent(self, db_env, monkeypatch):
        self._run("rf_absent", db_env, monkeypatch, "plain output, no banner")
        assert not any(b.startswith("route_fit:") for b in _basis_counts(db_env))

    @pytest.mark.parametrize(
        "output",
        [
            "route-fit: maybe",  # value outside the enum
            "route-fit: wrong-agent, but I fixed it anyway",  # trailing prose
            "route-fit:",  # no value
            "the banner format is route-fit: <ok|wrong-agent> mid-sentence",  # quoted spec
            "route-fit wrong-agent",  # missing colon
        ],
    )
    def test_malformed_banner_is_ignored_not_guessed(self, output, db_env, monkeypatch):
        assert self._run(f"rf_bad_{abs(hash(output))}", db_env, monkeypatch, output)["failure_count"] == 0
        assert not any(b.startswith("route_fit:") for b in _basis_counts(db_env))

    def test_last_banner_wins(self, db_env, monkeypatch):
        """The banner is the FINAL line; an earlier mention must not outrank it."""
        a = _load(A_PATH, "rf_last")
        assert a.parse_route_fit("route-fit: ok\nmore work happened\nroute-fit: wrong-skill") == "wrong-skill"

    def test_malformed_banner_never_blocks_the_dispatch(self, db_env):
        """Fail open: the hook still exits 0 and still records the decision."""
        event = _agent_event(skill="programming", output="route-fit: \x00\x00 garbage")
        assert _run_hook(A_PATH, event).returncode == 0

    def test_scoring_failure_never_blocks_the_dispatch(self, db_env, monkeypatch):
        """Even if apply_outcome explodes, the hook exits 0 and keeps its rows."""
        a = _load(A_PATH, "rf_raises")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)

        def _boom(*_a, **_k):
            raise RuntimeError("db on fire")

        monkeypatch.setattr(a, "record_route_fit", _boom)
        event = _agent_event(skill="programming", output="done.\nroute-fit: wrong-agent")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()  # must not raise
        assert _routing_row(db_env, self.KEY)["failure_count"] == 0

    def test_workflow_multi_marker_event_is_not_scored(self, db_env, tmp_path, monkeypatch):
        """One output cannot be attributed across N workers — score nothing."""
        sys.path.insert(0, str(LIB_DIR))
        import telemetry_capture as tc

        monkeypatch.setattr(tc, "_STATE_DIR", tmp_path / "telstate")
        a = _load(A_PATH, "rf_wf")
        event = _workflow_event(_TWO_MARKER_SCRIPT, session="rf-wf", output="done.\nroute-fit: wrong-agent")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        assert not any(b.startswith("route_fit:") for b in _basis_counts(db_env))

    def test_verdict_lands_on_the_evidence_decision_row(self, db_env, monkeypatch):
        self._run("rf_evidence", db_env, monkeypatch, "done.\nroute-fit: wrong-skill")
        sys.path.insert(0, str(LIB_DIR))
        import learning_db_v2 as ldb

        with ldb.get_connection() as conn:
            row = conn.execute(
                "SELECT outcome, outcome_basis FROM evidence_route_decisions WHERE route_key = ? ORDER BY id DESC",
                (self.KEY,),
            ).fetchone()
        assert (row["outcome"], row["outcome_basis"]) == ("failure", "route_fit:wrong-skill")


class TestFallbackReasonRecording:
    """`fallback=<slug>` on the marker becomes a countable row (Task 2)."""

    def _run(self, name, db_env, monkeypatch, marker_line):
        a = _load(A_PATH, name)
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _agent_event(skill="quick")
        event["tool_input"]["prompt"] = f"{marker_line}\nDo the thing."
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        return {r["key"] for r in _query_routing(db_env)}

    def test_reason_recorded_as_its_own_row(self, db_env, monkeypatch):
        keys = self._run(
            "fb_reason",
            db_env,
            monkeypatch,
            "[do-route] agent=general-purpose skill=quick complexity=medium model=opus "
            "health=- fallback=no-specialist-match",
        )
        assert "fallback-reason:no-specialist-match" in keys
        assert "general-purpose:quick" in keys

    def test_no_reason_row_without_the_token(self, db_env, monkeypatch):
        keys = self._run(
            "fb_none",
            db_env,
            monkeypatch,
            "[do-route] agent=python-general-engineer skill=quick complexity=medium model=opus health=-",
        )
        assert not any(k.startswith("fallback-reason:") for k in keys)

    def test_reason_is_read_from_the_marker_line_only(self, db_env, monkeypatch):
        """Task prose saying `fallback=...` must never be read as the router's reason."""
        a = _load(A_PATH, "fb_scope")
        assert (
            a.parse_fallback_reason(
                "[do-route] agent=python-general-engineer skill=quick complexity=medium\nuse fallback=whatever in the body"
            )
            is None
        )


class TestWorkflowDecisionRecorder:
    """A also sees Workflow dispatches (/do Complex): one decision per
    line-start [do-route] marker in tool_input.script, idempotent per marker
    line so a workflow resume that resubmits the script records nothing new.
    The Agent path stays byte-identical (regression test at the end)."""

    def test_two_markers_record_two_decisions(self, db_env, tmp_path, monkeypatch):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros
        import telemetry_capture as tc

        monkeypatch.setattr(tc, "_STATE_DIR", tmp_path / "telstate")
        a = _load(A_PATH, "rdr_wf_two")
        event = _workflow_event(_TWO_MARKER_SCRIPT, session="wf-two")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()

        # Two decision rows, one per marker.
        keys = {r["key"] for r in _query_routing(db_env)}
        assert "python-general-engineer:programming" in keys
        assert "hook-development-engineer:pr-workflow" in keys

        # Two DECISION events with per-marker complexity + gate inputs.
        decisions = [e for e in _read_events(db_env) if e["type"] == "decision"]
        assert len(decisions) == 2
        by_agent = {d["agent"]: d for d in decisions}
        assert by_agent["python-general-engineer"]["skill"] == "programming"
        assert by_agent["hook-development-engineer"]["skill"] == "pr-workflow"
        # complexity is normalized to the lowercase enum at record time.
        assert all(d["complexity"] == "complex" for d in decisions)
        # marker A: health=- => no weight row but instrumented.
        da = by_agent["python-general-engineer"]
        assert da["health_at_decision"] is None and da["gate_inputs_present"] is True
        # marker B: full numeric gate inputs, read from ITS line only.
        db = by_agent["hook-development-engineer"]
        assert db["health_at_decision"] == 0.8
        assert db["n"] == 6 and db["failure"] == 1 and db["action"] == "keep"

        # One telemetry envelope row per marker.
        tel_keys = {r["key"] for r in _query_telemetry(db_env)}
        assert tel_keys == {"python-general-engineer:programming", "hook-development-engineer:pr-workflow"}

        # One pending outcome per marker for the finalizer / Stop fallback
        # (Workflow inner agents fire no SubagentStop; none is needed).
        pending_keys = {p["key"] for p in ros.peek_pending_outcomes("wf-two")}
        assert pending_keys == {"python-general-engineer:programming", "hook-development-engineer:pr-workflow"}

    def test_resubmitted_script_is_noop(self, db_env, monkeypatch):
        # Workflow resume resubmits the SAME script: the per-marker-line
        # signatures re-claim nothing => zero new rows/events/pendings.
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        a = _load(A_PATH, "rdr_wf_resume")
        event = _workflow_event(_TWO_MARKER_SCRIPT, session="wf-resume")
        for _ in range(3):
            with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
                a.main()
        decisions = [e for e in _read_events(db_env) if e["type"] == "decision"]
        assert len(decisions) == 2
        assert all(r["observation_count"] == 1 for r in _query_routing(db_env))
        assert len(ros.peek_pending_outcomes("wf-resume")) == 2

    def test_identical_duplicate_marker_lines_are_two_decisions(self, db_env):
        # Two workers with byte-identical marker lines = two real dispatches:
        # the occurrence index keeps their signatures distinct — while a
        # resubmit of the same script still re-claims both (no-op).
        line = "[do-route] agent=python-general-engineer skill=programming complexity=Medium\n"
        script = f'a = """\n{line}task one\n"""\nb = """\n{line}task two\n"""\n'
        a = _load(A_PATH, "rdr_wf_dup")
        event = _workflow_event(script, session="wf-dup")
        for _ in range(2):  # second run = resume no-op
            with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
                a.main()
        decisions = [e for e in _read_events(db_env) if e["type"] == "decision"]
        assert len(decisions) == 2

    def test_mid_line_marker_not_recorded(self, db_env):
        # Line-start anchor semantics carry over to the script path: a marker
        # quoted mid-line is prose, not a routing decision.
        script = 'x = "see the [do-route] agent=python-general-engineer skill=programming line"\n'
        a = _load(A_PATH, "rdr_wf_midline")
        event = _workflow_event(script, session="wf-mid")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        assert _query_routing(db_env) == []
        assert _read_events(db_env) == []

    def test_workflow_rightsizing_accumulates_once_per_event(self, db_env):
        # The banner lives in the ONE Workflow tool result: accumulate it once
        # per event (not per marker), and never again on a resubmit.
        a = _load(A_PATH, "rdr_wf_rs")
        event = _workflow_event(
            _TWO_MARKER_SCRIPT,
            session="wf-rs",
            output="done. rightsizing: tier=3 files=15 packages=4 agents_dispatched=17",
        )
        for _ in range(2):  # second run = resume no-op
            with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
                a.main()
        row = next(r for r in _query_routing(db_env) if r["key"] == "rightsizing:tier3")
        assert "reviews: 1" in row["value"]

    def test_agent_payload_regression(self, db_env):
        # The Agent path must behave exactly as before the Workflow change:
        # one row, one decision event, snippet from description, prompt-scoped
        # complexity, one pending outcome.
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        a = _load(A_PATH, "rdr_wf_agent_reg")
        event = _agent_event(skill="programming", description="do work", session="wf-agent-reg")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        rows = _query_routing(db_env)
        assert len(rows) == 1
        assert rows[0]["key"] == "python-general-engineer:programming"
        assert "tool_errors=0" in rows[0]["value"]
        decisions = [e for e in _read_events(db_env) if e["type"] == "decision"]
        assert len(decisions) == 1
        assert decisions[0]["request_snippet"] == "do work"
        assert decisions[0]["complexity"] == "medium"  # normalized enum value
        assert [p["key"] for p in ros.peek_pending_outcomes("wf-agent-reg")] == ["python-general-engineer:programming"]


# ---------------------------------------------------------------------------
# B — routing-outcome-recorder
# ---------------------------------------------------------------------------


def _seed_decision(key="python-general-engineer:programming"):
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


class TestApplyOutcomeThreeWay:
    """T4: apply_outcome is three-way — success boosts, failure decays, neutral
    is a pure no-op (no boost, no decay, no count change)."""

    def test_neutral_is_pure_noop(self, db_env):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_score as ros_score

        key = _seed_decision("python-general-engineer:noop")
        before = next(r for r in _query_routing(db_env) if r["key"] == key)
        ros_score.apply_outcome(key, "neutral")
        after = next(r for r in _query_routing(db_env) if r["key"] == key)
        assert after["success_count"] == before["success_count"]
        assert after["failure_count"] == before["failure_count"]
        assert after["confidence"] == before["confidence"]
        assert after["observation_count"] == before["observation_count"]

    def test_success_boosts_failure_decays(self, db_env):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_score as ros_score

        sk = _seed_decision("python-general-engineer:succ")
        fk = _seed_decision("python-general-engineer:fail")
        ros_score.apply_outcome(sk, "success")
        ros_score.apply_outcome(fk, "failure")
        sr = next(r for r in _query_routing(db_env) if r["key"] == sk)
        fr = next(r for r in _query_routing(db_env) if r["key"] == fk)
        assert sr["success_count"] == 1 and sr["failure_count"] == 0
        assert fr["failure_count"] == 1 and fr["success_count"] == 0

    def test_legacy_bool_still_supported(self, db_env):
        # Back-compat: True=>failure, False=>success.
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_score as ros_score

        tk = _seed_decision("python-general-engineer:legacy-true")
        fk = _seed_decision("python-general-engineer:legacy-false")
        ros_score.apply_outcome(tk, True)
        ros_score.apply_outcome(fk, False)
        assert next(r for r in _query_routing(db_env) if r["key"] == tk)["failure_count"] == 1
        assert next(r for r in _query_routing(db_env) if r["key"] == fk)["success_count"] == 1


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

    def test_neutral_new_topic_is_noop(self, db_env, monkeypatch):
        # T4 three-way: an unrelated / new-topic next prompt carries NO acceptance
        # and NO complaint => NEUTRAL no-op. No boost, no decay, no count change.
        # (Previously this boosted — the inflation T4 removes.)
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision("python-general-engineer:neutral")
        self._pend(ros, "fin-neu", key, errors=False)
        before = next(r for r in _query_routing(db_env) if r["key"] == key)

        f = _load(F_PATH, "fin2")
        ev = _prompt_event("now add a CHANGELOG entry for the release", session="fin-neu")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
            f.main()
        after = next(r for r in _query_routing(db_env) if r["key"] == key)
        assert after["success_count"] == before["success_count"]  # no boost
        assert after["failure_count"] == before["failure_count"]  # no decay
        assert after["confidence"] == before["confidence"]  # unchanged
        # Pending cleared (resolved once, idempotent) even though it was a no-op.
        assert ros.peek_pending_outcomes("fin-neu") == []

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
        # T4: a benign new request is neutral (no acceptance marker) — no boost.
        assert after["success_count"] == 0

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
        ev = _prompt_event("thanks, now write the docs", session=session)  # acceptance => success
        with patch("sys.exit"), patch("sys.stdin.read", return_value=_json.dumps(ev)):
            f.main()
        # The valid sibling still scored; the malformed one was skipped. With one
        # live entry the turn acceptance is attributable => success.
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

    def test_acceptance_marker_unit(self):
        # T4: is_acceptance decides boost-vs-neutral. Explicit affirmation in the
        # FIRST clause => True; an unrelated/new-topic prompt => False (=> neutral).
        f = _load(F_PATH, "fin_acc_unit")
        for p in [
            "thanks!",
            "looks good, merge it",
            "perfect, ship it",
            "lgtm",
            "great work",
            "that worked, now do the next file",
        ]:
            assert f.is_acceptance(p) is True, p
        for p in [
            "now add a CHANGELOG entry for the release",
            "write the docs",
            "that's wrong",
            "Add a test for wrong-format dates.",
            "",
            None,
        ]:
            assert f.is_acceptance(p) is False, p


# ---------------------------------------------------------------------------
# T3 — per-dispatch route event log (JSONL)
# ---------------------------------------------------------------------------

EVENTS_NAME = "route-events.jsonl"


def _read_events(db_env):
    """Read every event line from the throwaway route-events.jsonl, or []."""
    path = db_env["db_dir"] / EVENTS_NAME
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class TestRouteEventLog:
    """T3: the decision hook appends one DECISION event per recorded dispatch;
    the finalizer appends one OUTCOME event per finalized dispatch. Append-only,
    failure-safe — a write error must never break the hook."""

    def test_decision_event_appended_on_record(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_evt1")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _agent_event(skill="programming", body="Refactor the parser.", session="evt-s1")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        events = _read_events(db_env)
        decisions = [e for e in events if e["type"] == "decision"]
        assert len(decisions) == 1
        d = decisions[0]
        assert d["agent"] == "python-general-engineer"
        assert d["skill"] == "programming"
        assert d["session"] == "evt-s1"
        assert d["complexity"].lower() == "medium"
        assert "request_snippet" in d and "health_at_decision" in d

    def test_no_decision_event_when_marker_absent(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_evt2")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _agent_event(marker=False, body="Review this PR.")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        assert _read_events(db_env) == []

    def test_outcome_event_appended_on_finalize(self, db_env, monkeypatch):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision("python-general-engineer:evt-fin")
        ros.append_pending_outcome("evt-fin", key, errors=False)

        f = _load(F_PATH, "fin_evt1")
        ev = _prompt_event("looks good, merge it", session="evt-fin")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
            f.main()
        outcomes = [e for e in _read_events(db_env) if e["type"] == "outcome"]
        assert len(outcomes) == 1
        assert outcomes[0]["key"] == key
        assert outcomes[0]["outcome"] in {"success", "failure", "neutral"}
        assert outcomes[0]["session"] == "evt-fin"

    def test_outcome_event_records_failure(self, db_env, monkeypatch):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision("python-general-engineer:evt-fail")
        ros.append_pending_outcome("evt-fail", key, errors=True)

        f = _load(F_PATH, "fin_evt_fail")
        ev = _prompt_event("ok next", session="evt-fail")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
            f.main()
        outcomes = [e for e in _read_events(db_env) if e["type"] == "outcome"]
        assert outcomes and outcomes[0]["outcome"] == "failure"

    def test_log_is_append_only_across_dispatches(self, db_env, monkeypatch):
        # Two recorded dispatches => two decision lines, none overwritten.
        a = _load(A_PATH, "rdr_evt_append")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        for i, skill in enumerate(("programming", "testing")):
            ev = _agent_event(skill=skill, body=f"task {i}", session=f"append-{i}")
            with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
                a.main()
        decisions = [e for e in _read_events(db_env) if e["type"] == "decision"]
        assert {d["skill"] for d in decisions} == {"programming", "testing"}
        assert len(decisions) == 2

    def test_decision_event_write_error_does_not_break_hook(self, db_env, monkeypatch):
        # A failing event append must NOT prevent the aggregate row being written
        # and must NOT raise — the hook stays non-blocking.
        a = _load(A_PATH, "rdr_evt_safe")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        import route_events

        monkeypatch.setattr(
            route_events,
            "_append",
            lambda *_a, **_k: (_ for _ in ()).throw(OSError("disk full")),
        )
        event = _agent_event(skill="programming", session="evt-safe")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()  # must not raise
        # Aggregate row still recorded despite the event-log failure.
        keys = {r["key"] for r in _query_routing(db_env)}
        assert "python-general-engineer:programming" in keys

    def test_malformed_events_dir_does_not_crash_recorder(self, db_env, monkeypatch):
        # CLAUDE_LEARNING_DIR pointing at a non-creatable path => event append
        # fails silently; the hook still exits 0 (subprocess end-to-end).
        bad = db_env["db_dir"] / "notadir"
        bad.write_text("i am a file, not a directory")
        env = dict(os.environ)
        env["CLAUDE_LEARNING_DIR"] = str(bad)  # base path is a file => mkdir fails
        event = _agent_event(skill="programming", session="evt-baddir")
        p = subprocess.run(
            [sys.executable, str(A_PATH)],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=env,
        )
        assert p.returncode == 0


class TestOutcomeEventReasonAndRelevance:
    """record_outcome_event writes reason + routing_relevant only when supplied,
    and the finalizer always stamps both so a decay is queryable from the JSONL
    alone (no per-key basis table needed)."""

    def test_reason_written_when_given(self, db_env):
        sys.path.insert(0, str(LIB_DIR))
        import route_events

        route_events.record_outcome_event(session="s", key="a:b", outcome="failure", reason="tool-errors")
        ev = next(e for e in _read_events(db_env) if e["type"] == "outcome")
        assert ev["reason"] == "tool-errors"

    def test_routing_relevant_written_when_given(self, db_env):
        sys.path.insert(0, str(LIB_DIR))
        import route_events

        route_events.record_outcome_event(session="s", key="a:b", outcome="failure", routing_relevant=True)
        ev = next(e for e in _read_events(db_env) if e["type"] == "outcome")
        assert ev["routing_relevant"] is True

    def test_routing_relevant_absent_when_none(self, db_env):
        sys.path.insert(0, str(LIB_DIR))
        import route_events

        # Default None => field omitted, so old callers stay byte-compatible.
        route_events.record_outcome_event(session="s", key="a:b", outcome="neutral")
        ev = next(e for e in _read_events(db_env) if e["type"] == "outcome")
        assert "routing_relevant" not in ev
        assert "reason" not in ev

    def test_finalizer_writes_reason_and_routing_relevant(self, db_env, monkeypatch):
        # End-to-end: a rejection decay must carry reason + routing_relevant in
        # the JSONL OUTCOME event so the demotion cause is queryable.
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision("python-general-engineer:evt-reason")
        ros.append_pending_outcome("evt-reason", key, errors=False)

        f = _load(F_PATH, "fin_reason")
        ev = _prompt_event("that's wrong, redo it", session="evt-reason")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
            f.main()
        outcome = next(e for e in _read_events(db_env) if e["type"] == "outcome")
        assert outcome["outcome"] == "failure"
        assert outcome["reason"] == "rejection"
        assert outcome["routing_relevant"] is True


# ---------------------------------------------------------------------------
# Step 1.5 — health gate inputs carried on the [do-route] marker
# ---------------------------------------------------------------------------


def _health_event(marker_body, *, session="hs1", description="do work"):
    """PostToolUse:Agent event whose prompt is the supplied marker line verbatim."""
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "session_id": session,
        "tool_input": {
            "subagent_type": "python-general-engineer",
            "description": description,
            "prompt": marker_body + "\ndo the work",
        },
        "tool_result": {"output": "ok", "is_error": False},
    }


class TestHealthMarkerParse:
    """Step 1.5: the recorder reads {health, n, fail, action, alts} off the marker
    and writes them to the DECISION event. `health=-` writes null health.

    Three-state instrumentation contract (decommission clock validity):
      (a) numeric  health=<float>  => health_at_decision float, gate_inputs_present True
      (b) no-row   health=-        => health_at_decision null,  gate_inputs_present True
      (c) legacy   no health= token => health_at_decision null,  gate_inputs_present False
    States (a)+(b) are instrumented (marker carried the gate input); only (c)
    counts against the 95% rate. `gate_inputs_present` is the validity signal,
    not non-null health — most live picks are state (b) (pair has no weight row)."""

    def test_health_fields_written_to_decision_event(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_health1")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        marker = (
            "[do-route] agent=python-general-engineer skill=programming "
            "complexity=Medium health=0.20 n=6 fail=4 action=demote alts=direct:pr-workflow,explore:codebase-overview"
        )
        event = _health_event(marker, session="hs-demote")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        d = next(e for e in _read_events(db_env) if e["type"] == "decision")
        assert d["health_at_decision"] == 0.20
        assert d["n"] == 6
        assert d["failure"] == 4
        assert d["action"] == "demote"
        assert d["alternates"] == ["direct:pr-workflow", "explore:codebase-overview"]
        # State (a): marker carried gate inputs.
        assert d["gate_inputs_present"] is True

    def test_health_dash_writes_null(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_health2")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        marker = "[do-route] agent=python-general-engineer skill=programming complexity=Medium health=-"
        event = _health_event(marker, session="hs-null")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        d = next(e for e in _read_events(db_env) if e["type"] == "decision")
        assert d["health_at_decision"] is None
        assert d["n"] is None
        assert d["failure"] is None
        assert d["action"] is None
        assert d["alternates"] is None
        # State (b): marker said no-row (`-`). The pick has no weight row — valid,
        # expected data — so it is INSTRUMENTED, not missing. This is the fix: the
        # gate must read this as instrumented, distinguishable from state (c).
        assert d["gate_inputs_present"] is True

    def test_absent_health_field_writes_null(self, db_env, monkeypatch):
        # State (c): a legacy marker with no health= token => null health, all
        # fields null, gate_inputs_present False (no marker gate input at all).
        a = _load(A_PATH, "rdr_health3")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        marker = "[do-route] agent=python-general-engineer skill=programming complexity=Medium"
        event = _health_event(marker, session="hs-legacy")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        d = next(e for e in _read_events(db_env) if e["type"] == "decision")
        assert d["health_at_decision"] is None
        assert d["action"] is None
        assert d["gate_inputs_present"] is False


class TestHealthMarkerLineScoping:
    """Findings 70/15/97 regression guards.

    70: gate inputs are read from the marker LINE only — a task body mentioning
        `health=`/`fail=` must NOT poison gate_inputs_present or the clock.
    15: a malformed `health=1.2.3` reads as field-absent (state c), and the
        decision event is STILL recorded — never silently dropped.
    """

    def test_health_in_body_is_ignored(self, db_env, monkeypatch):
        # Marker line carries NO gate input (state c); the BODY mentions
        # health=/fail= — those must not be read. Expect state (c): null health,
        # gate_inputs_present False.
        a = _load(A_PATH, "rdr_body_ignored")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Agent",
            "session_id": "body-health",
            "tool_input": {
                "subagent_type": "python-general-engineer",
                "description": "do work",
                "prompt": (
                    "[do-route] agent=python-general-engineer skill=programming complexity=Medium\n"
                    "Fix the gate: when health=0.9 and fail=3 the action=demote path is wrong."
                ),
            },
            "tool_result": {"output": "ok", "is_error": False},
        }
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        d = next(e for e in _read_events(db_env) if e["type"] == "decision")
        assert d["health_at_decision"] is None  # body health=0.9 NOT read
        assert d["failure"] is None  # body fail=3 NOT read
        assert d["action"] is None  # body action=demote NOT read
        assert d["gate_inputs_present"] is False  # state (c): clean of body poison

    def test_health_on_marker_line_is_parsed(self, db_env, monkeypatch):
        # Same body health= bait, but the marker line ALSO carries health=0.20.
        # The marker-line value must win; body values are never read.
        a = _load(A_PATH, "rdr_line_parsed")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Agent",
            "session_id": "line-health",
            "tool_input": {
                "subagent_type": "python-general-engineer",
                "description": "do work",
                "prompt": (
                    "[do-route] agent=python-general-engineer skill=programming "
                    "complexity=Medium health=0.20 fail=4 action=demote\n"
                    "Body text that says health=0.99 and fail=9 must be ignored."
                ),
            },
            "tool_result": {"output": "ok", "is_error": False},
        }
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        d = next(e for e in _read_events(db_env) if e["type"] == "decision")
        assert d["health_at_decision"] == 0.20  # marker line, not body 0.99
        assert d["failure"] == 4  # marker line, not body 9
        assert d["action"] == "demote"
        assert d["gate_inputs_present"] is True

    def test_malformed_health_is_field_absent_but_event_recorded(self, db_env, monkeypatch):
        # health=1.2.3 is malformed: it must read as field-absent (state c) and
        # the decision event MUST still be recorded — never dropped by a raised
        # float(). gate_inputs_present False, decision + routing rows still land.
        a = _load(A_PATH, "rdr_malformed_health")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        marker = "[do-route] agent=python-general-engineer skill=programming complexity=Medium health=1.2.3"
        event = _health_event(marker, session="hs-malformed")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        d = next(e for e in _read_events(db_env) if e["type"] == "decision")
        assert d["health_at_decision"] is None  # malformed => field absent
        assert d["gate_inputs_present"] is False  # state (c), honest "not instrumented"
        # The event is still recorded — the malformed value did NOT drop it.
        keys = {r["key"] for r in _query_routing(db_env)}
        assert "python-general-engineer:programming" in keys

    def test_valid_health_dash_still_state_b(self, db_env, monkeypatch):
        # Regression: the tightened regex must still accept `health=-` => state b
        # (null health, gate_inputs_present True).
        a = _load(A_PATH, "rdr_dash_stateb")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        marker = "[do-route] agent=python-general-engineer skill=programming complexity=Medium health=-"
        event = _health_event(marker, session="hs-dash-b")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        d = next(e for e in _read_events(db_env) if e["type"] == "decision")
        assert d["health_at_decision"] is None
        assert d["gate_inputs_present"] is True

    def test_recorder_failure_writes_stderr_line(self, db_env, monkeypatch, capsys):
        # Finding 97: an uncaught recorder error must surface ONE short stderr
        # line (class: msg) even WITHOUT CLAUDE_HOOKS_DEBUG, and still exit 0.
        # Force a failure inside main() (claim_dispatch raises) and assert the
        # outer handler wrote the line and exit(0) was called.
        monkeypatch.delenv("CLAUDE_HOOKS_DEBUG", raising=False)  # prove no-debug logging
        a = _load(A_PATH, "rdr_stderr_fail")

        def _boom(*_a, **_k):
            raise RuntimeError("forced failure")

        monkeypatch.setattr(a, "claim_dispatch", _boom)
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        event = _agent_event(skill="programming", session="stderr-fail")
        with patch("sys.exit") as ex, patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        ex.assert_called_with(0)  # still non-blocking
        err = capsys.readouterr().err
        assert "[routing-decision-recorder] HOOK-ERROR: RuntimeError: forced failure" in err


# ---------------------------------------------------------------------------
# Complexity enum normalization + optional stack= token on the marker
# ---------------------------------------------------------------------------


class TestComplexityNormalization:
    """The recorder lowercases the marker's complexity and validates it against
    the router enum {trivial, simple, medium, complex}. Valid => normalized
    value stored. Invalid (production carried `Low`) => complexity "" and the
    raw value kept in complexity_invalid — recorded, never dropped. Read from
    the marker LINE only (same scoping as the health gate inputs)."""

    def _record(self, a, marker, session):
        event = _health_event(marker, session=session)
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()

    def test_valid_complexity_case_normalized(self, db_env, monkeypatch):
        # Production case-split: `Medium` and `medium` must land as ONE value.
        a = _load(A_PATH, "rdr_cx_case")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        self._record(a, "[do-route] agent=python-general-engineer skill=programming complexity=Medium", "cx-case")
        d = next(e for e in _read_events(db_env) if e["type"] == "decision")
        assert d["complexity"] == "medium"
        assert "complexity_invalid" not in d

    def test_invalid_complexity_recorded_not_dropped(self, db_env, monkeypatch):
        # Production invalid value `Low`: normalized field stays "", the raw
        # value lands in complexity_invalid, and the decision event + routing
        # row are STILL recorded.
        a = _load(A_PATH, "rdr_cx_invalid")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        self._record(a, "[do-route] agent=python-general-engineer skill=programming complexity=Low", "cx-invalid")
        d = next(e for e in _read_events(db_env) if e["type"] == "decision")
        assert d["complexity"] == ""
        assert d["complexity_invalid"] == "Low"
        keys = {r["key"] for r in _query_routing(db_env)}
        assert "python-general-engineer:programming" in keys  # event not dropped

    def test_absent_complexity_is_empty_without_invalid_field(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_cx_absent")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        self._record(a, "[do-route] agent=python-general-engineer skill=programming", "cx-absent")
        d = next(e for e in _read_events(db_env) if e["type"] == "decision")
        assert d["complexity"] == ""
        assert "complexity_invalid" not in d

    def test_body_complexity_not_read(self, db_env, monkeypatch):
        # Marker-line scoping: a body mentioning complexity= must not be read
        # (same rationale as the health gate inputs, Finding 70).
        a = _load(A_PATH, "rdr_cx_body")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _health_event("[do-route] agent=python-general-engineer skill=programming", session="cx-body")
        event["tool_input"]["prompt"] += "\nThe old complexity=Weird value must be ignored."
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        d = next(e for e in _read_events(db_env) if e["type"] == "decision")
        assert d["complexity"] == ""
        assert "complexity_invalid" not in d


class TestStackTokenParse:
    """Optional ` stack={s1,s2}` marker token => decision event `stack` list.
    Absent (or empty) token => NO field, so stack-free markers write unchanged
    events. Instrumentation only — the router emits the token in a later PR."""

    def _decision(self, db_env, monkeypatch, marker, session, body_suffix=""):
        a = _load(A_PATH, f"rdr_stack_{session}")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _health_event(marker, session=session)
        if body_suffix:
            event["tool_input"]["prompt"] += body_suffix
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()
        return next(e for e in _read_events(db_env) if e["type"] == "decision")

    def test_stack_token_parsed_to_list(self, db_env, monkeypatch):
        d = self._decision(
            db_env,
            monkeypatch,
            "[do-route] agent=python-general-engineer skill=programming complexity=Medium stack={testing,pr-workflow}",
            "yes",
        )
        assert d["stack"] == ["testing", "pr-workflow"]
        assert d["complexity"] == "medium"  # sibling tokens still parse

    def test_absent_stack_token_writes_no_field(self, db_env, monkeypatch):
        d = self._decision(
            db_env,
            monkeypatch,
            "[do-route] agent=python-general-engineer skill=programming complexity=Medium",
            "no",
        )
        assert "stack" not in d

    def test_empty_stack_braces_write_no_field(self, db_env, monkeypatch):
        d = self._decision(
            db_env,
            monkeypatch,
            "[do-route] agent=python-general-engineer skill=programming stack={}",
            "empty",
        )
        assert "stack" not in d

    def test_stack_in_body_ignored(self, db_env, monkeypatch):
        # Marker-line scoping: a body mentioning stack={...} is prose, not a
        # router token.
        d = self._decision(
            db_env,
            monkeypatch,
            "[do-route] agent=python-general-engineer skill=programming",
            "body",
            body_suffix="\nDiscuss the stack={a,b} syntax in the docs.",
        )
        assert "stack" not in d


class TestStackUsageRecording:
    """The recorder also bumps a stack-usage DB row per enhancement skill
    (topic="routing", category="effectiveness", key "stack-usage:{skill}"),
    queried by `learning-db.py stack-usage`. Instrumentation only — reuses
    record_learning's upsert, no parallel store."""

    def _record(self, a, marker, session):
        event = _health_event(marker, session=session)
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()

    def test_stack_skills_recorded_as_rows(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_su1")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        self._record(
            a,
            "[do-route] agent=python-general-engineer skill=programming stack={testing,testing}",
            "su-1",
        )
        rows = {r["key"]: r for r in _query_routing(db_env)}
        assert "stack-usage:testing" in rows
        assert "stack-usage:testing" in rows
        assert rows["stack-usage:testing"]["observation_count"] == 1

    def test_repeat_stacking_bumps_observation_count(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_su2")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        for i in range(3):
            self._record(a, "[do-route] agent=python-general-engineer skill=programming stack={joy-check}", f"su-r{i}")
        rows = {r["key"]: r for r in _query_routing(db_env)}
        assert rows["stack-usage:joy-check"]["observation_count"] == 3

    def test_duplicate_skill_in_one_marker_counts_once(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_su3")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        self._record(
            a, "[do-route] agent=python-general-engineer skill=programming stack={joy-check,joy-check}", "su-dup"
        )
        rows = {r["key"]: r for r in _query_routing(db_env)}
        assert rows["stack-usage:joy-check"]["observation_count"] == 1

    def test_absent_stack_token_records_no_stack_usage_rows(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_su4")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        self._record(a, "[do-route] agent=python-general-engineer skill=programming", "su-none")
        keys = {r["key"] for r in _query_routing(db_env)}
        assert not any(k.startswith("stack-usage:") for k in keys)

    def test_empty_stack_braces_record_no_stack_usage_rows(self, db_env, monkeypatch):
        a = _load(A_PATH, "rdr_su5")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        self._record(a, "[do-route] agent=python-general-engineer skill=programming stack={}", "su-empty")
        keys = {r["key"] for r in _query_routing(db_env)}
        assert not any(k.startswith("stack-usage:") for k in keys)


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
        event_a = _agent_event(skill="programming", session=session)
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event_a)):
            a.main()
        # SubagentStop validates only — confidence unchanged here.
        event_b = {"hook_event_name": "SubagentStop", "session_id": session}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event_b)):
            b.main()
        mid = next(r for r in _query_routing(db_env) if r["key"] == "python-general-engineer:programming")
        assert mid["success_count"] == 0
        # Next user turn (acceptance) finalizes => success.
        event_f = {"hook_event_name": "UserPromptSubmit", "session_id": session, "prompt": "great, thanks"}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event_f)):
            f.main()
        decision = next(r for r in _query_routing(db_env) if r["key"] == "python-general-engineer:programming")
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
        # Seeded in one transaction: 1100 record_learning() calls cost ~5s of
        # per-row commits and the fillers are setup, not behavior under test.
        now = "2026-01-01T00:00:00"
        with sqlite3.connect(ldb.get_db_path()) as conn:
            conn.executemany(
                "INSERT INTO learnings (topic, key, value, category, confidence, source, first_seen, last_seen)"
                " VALUES ('routing', ?, ?, 'effectiveness', 0.95, 'test', ?, ?)",
                [
                    (f"filler-agent:skill-{i}", f"routing-decision: filler {i} tool_errors=0", now, now)
                    for i in range(1100)
                ],
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

        # Neutral next turn (no acceptance, no rejection) with >1 pending: the
        # turn reaction is NOT attributable. Each entry resolves on its OWN flag —
        # good=neutral (T4: clean, no acceptance => no-op), bad=failure (own
        # error). The sibling's error does NOT broadcast a decay onto good.
        f = _load(HOOKS_DIR / "routing-outcome-finalizer.py", "fin_attrib")
        event = {"hook_event_name": "UserPromptSubmit", "session_id": session, "prompt": "ok, next task"}
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            f.main()

        good_after = next(r for r in _query_routing_all(db_env) if r["key"] == good)
        bad_after = next(r for r in _query_routing_all(db_env) if r["key"] == bad)
        # Clean key is NEUTRAL (no boost, no decay) — NOT decayed by the sibling.
        assert good_after["success_count"] == 0
        assert good_after["failure_count"] == 0
        assert good_after["confidence"] == good_before
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

STOP_PATH = HOOKS_DIR / "routing-outcome-stop-fallback.py"


def _age_pending(db_env, session: str, seconds: float) -> None:
    """Backdate every pending entry of one session by `seconds`."""
    import routing_outcome_state as ros

    path = ros._state_file(session)
    data = json.loads(path.read_text(encoding="utf-8"))
    for item in data["pending"]:
        item["created"] = float(item["created"]) - seconds
    path.write_text(json.dumps(data), encoding="utf-8")


def _seed_evidence(key: str, session: str, decision_id: str) -> None:
    """One evidence_route_decisions row (NULL outcome) for an `agent:skill` key."""
    import learning_db_v2 as ldb

    agent, skill = key.split(":", 1)
    ldb.record_evidence_route_decision(
        session_id=session, agent=agent, skill=skill, complexity="medium", decision_id=decision_id
    )


def _evidence_outcomes(key: str) -> dict[str, tuple]:
    """decision_id -> (outcome, outcome_basis) for one route key."""
    import learning_db_v2 as ldb

    with ldb.get_connection() as conn:
        rows = conn.execute(
            "SELECT decision_id, outcome, outcome_basis FROM evidence_route_decisions WHERE route_key = ?", (key,)
        ).fetchall()
    return {r["decision_id"]: (r["outcome"], r["outcome_basis"]) for r in rows}


def _fire(path: Path, name: str, event: dict):
    mod = _load(path, name)
    with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
        mod.main()
    return mod


class TestStopFallback:
    """Stop fires after every turn, before the user's next prompt. It resolves
    only what the finalizer can never score better: errored and stale entries.
    SessionEnd resolves everything."""

    def test_stop_resolves_errors_and_keeps_clean_pending(self, db_env, monkeypatch):
        """Stop: an errored dispatch fails at once; a fresh clean one stays
        pending for the UserPromptSubmit finalizer."""
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        ok = _seed_decision("python-general-engineer:auto-ok")
        bad = _seed_decision("python-general-engineer:auto-bad")
        session = "autorun"
        ros.append_pending_outcome(session, ok, errors=False)
        ros.append_pending_outcome(session, bad, errors=True)
        ok_before = next(r for r in _query_routing_all(db_env) if r["key"] == ok)

        event = {"hook_event_name": "Stop", "session_id": session, "session_data": {"files_modified": ["x"]}}
        _fire(STOP_PATH, "stop1", event)

        ok_row = next(r for r in _query_routing_all(db_env) if r["key"] == ok)
        bad_row = next(r for r in _query_routing_all(db_env) if r["key"] == bad)
        assert ok_row["success_count"] == ok_before["success_count"]
        assert ok_row["failure_count"] == 0
        assert ok_row["confidence"] == ok_before["confidence"]
        assert bad_row["failure_count"] == 1  # error => decay
        assert [p["key"] for p in ros.peek_pending_outcomes(session)] == [ok]
        # The clean entry was not scored: no default_no_complaint row.
        assert _basis_counts(db_env) == {"tool_errors_only": 1}

    def test_stop_then_next_prompt_scores_the_reaction(self, db_env, monkeypatch):
        """The regression this fixes: Stop used to drain every entry, so the
        finalizer never saw one and every outcome was default_no_complaint."""
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision("python-general-engineer:turn-loop")
        session = "turn-loop"
        ros.append_pending_outcome(session, key, errors=False)

        _fire(STOP_PATH, "stop_loop", {"hook_event_name": "Stop", "session_id": session})
        _fire(F_PATH, "fin_loop", _prompt_event("thanks, that worked", session=session))

        row = next(r for r in _query_routing_all(db_env) if r["key"] == key)
        assert row["success_count"] == 1
        assert _basis_counts(db_env) == {"acceptance_detected": 1}
        assert ros.peek_pending_outcomes(session) == []

    def test_stop_resolves_stale_entry_as_neutral(self, db_env, monkeypatch):
        """No user turn for STOP_STALE_AGE_SEC: the clean entry resolves to
        NEUTRAL (no boost) with basis default_no_complaint."""
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision("python-general-engineer:stale")
        session = "stale-run"
        ros.append_pending_outcome(session, key, errors=False)
        before = next(r for r in _query_routing_all(db_env) if r["key"] == key)

        _age_pending(db_env, session, ros.STOP_STALE_AGE_SEC - 60)
        _fire(STOP_PATH, "stop_not_stale", {"hook_event_name": "Stop", "session_id": session})
        assert len(ros.peek_pending_outcomes(session)) == 1  # just under the line: kept

        _age_pending(db_env, session, 120)
        _fire(STOP_PATH, "stop_stale", {"hook_event_name": "Stop", "session_id": session})

        after = next(r for r in _query_routing_all(db_env) if r["key"] == key)
        assert after["success_count"] == before["success_count"]
        assert after["failure_count"] == before["failure_count"]
        assert after["confidence"] == before["confidence"]
        assert ros.peek_pending_outcomes(session) == []
        assert _basis_counts(db_env) == {"default_no_complaint": 1}

    def test_stop_drops_abandoned_entry_unscored(self, db_env, monkeypatch):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision("python-general-engineer:abandoned")
        session = "abandoned"
        ros.append_pending_outcome(session, key, errors=True)
        _age_pending(db_env, session, ros.MAX_PENDING_AGE_SEC + 60)

        _fire(STOP_PATH, "stop_abandoned", {"hook_event_name": "Stop", "session_id": session})

        row = next(r for r in _query_routing_all(db_env) if r["key"] == key)
        assert row["failure_count"] == 0
        assert ros.peek_pending_outcomes(session) == []
        assert _basis_counts(db_env) == {}

    def test_stop_writes_the_outcome_on_the_evidence_row(self, db_env, monkeypatch):
        """The fallback used to call apply_outcome only, leaving the decision
        rows it resolved with a NULL outcome."""
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision("python-general-engineer:evidence")
        session = "evidence-run"
        for decision_id, errors in (("d-1", True), ("d-2", False)):
            _seed_evidence(key, session, decision_id)
            ros.append_pending_outcome(session, key, errors, decision_id)

        _fire(STOP_PATH, "stop_evidence", {"hook_event_name": "Stop", "session_id": session})
        assert _evidence_outcomes(key) == {"d-1": ("failure", "tool_errors_only"), "d-2": (None, None)}

        _fire(STOP_PATH, "end_evidence", {"hook_event_name": "SessionEnd", "session_id": session})
        assert _evidence_outcomes(key) == {
            "d-1": ("failure", "tool_errors_only"),
            "d-2": ("neutral", "default_no_complaint"),
        }
        events = [e for e in _read_events(db_env) if e.get("type") == "outcome"]
        assert [(e["outcome"], e["reason"]) for e in events] == [
            ("failure", "tool-errors"),
            ("neutral", "session-end-no-reaction"),
        ]

    def test_session_end_resolves_every_pending_entry(self, db_env, monkeypatch, capsys):
        """SessionEnd is the true end: no next prompt can come, so a fresh
        clean entry resolves too. SessionEnd takes no hook output."""
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        ok = _seed_decision("python-general-engineer:end-ok")
        bad = _seed_decision("python-general-engineer:end-bad")
        session = "session-end"
        ros.append_pending_outcome(session, ok, errors=False)
        ros.append_pending_outcome(session, bad, errors=True)
        ok_before = next(r for r in _query_routing_all(db_env) if r["key"] == ok)
        capsys.readouterr()

        _fire(STOP_PATH, "end1", {"hook_event_name": "SessionEnd", "session_id": session, "reason": "exit"})

        assert capsys.readouterr().out == ""
        ok_row = next(r for r in _query_routing_all(db_env) if r["key"] == ok)
        bad_row = next(r for r in _query_routing_all(db_env) if r["key"] == bad)
        assert ok_row["confidence"] == ok_before["confidence"] and ok_row["success_count"] == 0
        assert bad_row["failure_count"] == 1
        assert ros.peek_pending_outcomes(session) == []
        assert _basis_counts(db_env) == {"default_no_complaint": 1, "tool_errors_only": 1}

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

    def test_stop_skips_a_non_dict_entry_and_scores_the_rest(self, db_env, monkeypatch):
        """The state helper hands back malformed entries so they leave state.
        One of them must not abort the loop and lose the entries after it."""
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision("python-general-engineer:after-junk")
        session = "junk-entry"
        ros.append_pending_outcome(session, key, errors=True)
        path = ros._state_file(session)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["pending"].insert(0, "not-a-dict")
        path.write_text(json.dumps(data), encoding="utf-8")

        _fire(STOP_PATH, "stop_junk", {"hook_event_name": "Stop", "session_id": session})

        row = next(r for r in _query_routing_all(db_env) if r["key"] == key)
        assert row["failure_count"] == 1
        assert ros.peek_pending_outcomes(session) == []

    def test_stop_resolved_failure_blocks_the_next_repeat_weak_boost(self, db_env, monkeypatch):
        """Neutral, then a tool-error failure resolved at Stop, then a clean
        repeat: the repeat has an intervening failure, so it stays neutral."""
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        key = _seed_decision("python-general-engineer:repeat-after-stop-failure")
        session = "repeat-stop"

        ros.append_pending_outcome(session, key, errors=False)
        _fire(F_PATH, "rs_fin1", _prompt_event("now refactor the parser module", session=session))
        assert ros.get_outcome_history(session)[key] == "neutral"

        ros.append_pending_outcome(session, key, errors=True)
        _fire(STOP_PATH, "rs_stop", {"hook_event_name": "Stop", "session_id": session})
        assert ros.get_outcome_history(session)[key] == "failure"
        failed = next(r for r in _query_routing_all(db_env) if r["key"] == key)
        assert failed["failure_count"] == 1

        ros.append_pending_outcome(session, key, errors=False)
        _fire(F_PATH, "rs_fin2", _prompt_event("sort the report output by date", session=session))

        after = next(r for r in _query_routing_all(db_env) if r["key"] == key)
        assert after["success_count"] == 0, "weak boost despite a Stop-resolved failure"
        assert after["confidence"] == failed["confidence"]
        assert "repeat_dispatch_weak" not in _basis_counts(db_env)

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
        # CORE GUARD: neither sibling is DECAYED by the unattributable turn. Under
        # T4 a clean unattributable sibling is NEUTRAL (no boost either), not the
        # old auto-success — but the misattribution guard (no false decay) holds.
        assert a_after["failure_count"] == 0 and b_after["failure_count"] == 0
        assert a_after["success_count"] == 0 and b_after["success_count"] == 0
        assert a_after["confidence"] == a_before and b_after["confidence"] == b_before

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
        # T4: clean sibling is NEUTRAL (no acceptance, unattributable turn) — no
        # boost, no decay. The errored sibling still fails on its own flag.
        assert clean_after["success_count"] == 0 and clean_after["failure_count"] == 0
        assert errd_after["failure_count"] == 1 and errd_after["success_count"] == 0


class TestKeyLevelAttribution:
    """v1.2.0: a reaction names a route when every live pending dispatch shares
    one route key, and it scores ONE entry. Mixed keys: rejection is ignored,
    acceptance is a bounded weak boost per key."""

    def _pend(self, monkeypatch, db_env, session, keys):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "_STATE_DIR", db_env["state"])
        for key in dict.fromkeys(keys):
            _seed_decision(key)
        for i, key in enumerate(keys):
            _seed_evidence(key, session, f"{session}:{i}")
            ros.append_pending_outcome(session, key, False, f"{session}:{i}")
        return ros

    def _row(self, db_env, key):
        return next(r for r in _query_routing_all(db_env) if r["key"] == key)

    def test_same_key_fanout_acceptance_boosts_once(self, db_env, monkeypatch):
        key = "python-general-engineer:fan"
        ros = self._pend(monkeypatch, db_env, "fan-acc", [key, key, key])

        _fire(F_PATH, "fin_fan_acc", _prompt_event("looks great", session="fan-acc"))

        row = self._row(db_env, key)
        assert row["success_count"] == 1, "one reaction must be one boost, not one per sibling"
        assert _basis_counts(db_env) == {"acceptance_detected": 1, "default_no_complaint": 2}
        assert _evidence_outcomes(key) == {
            "fan-acc:0": ("success", "acceptance_detected"),
            "fan-acc:1": ("neutral", "default_no_complaint"),
            "fan-acc:2": ("neutral", "default_no_complaint"),
        }
        assert ros.peek_pending_outcomes("fan-acc") == []

    def test_same_key_fanout_rejection_decays_once(self, db_env, monkeypatch):
        key = "python-general-engineer:fan-rej"
        self._pend(monkeypatch, db_env, "fan-rej", [key, key])

        _fire(F_PATH, "fin_fan_rej", _prompt_event("okay that's wrong", session="fan-rej"))

        row = self._row(db_env, key)
        assert row["failure_count"] == 1 and row["success_count"] == 0
        assert _basis_counts(db_env) == {"rejection_detected": 1, "default_no_complaint": 1}

    def test_reaction_skips_an_errored_sibling(self, db_env, monkeypatch):
        """The errored entry fails on its own flag; the acceptance scores the
        first CLEAN entry."""
        key = "python-general-engineer:fan-err"
        ros = self._pend(monkeypatch, db_env, "fan-err", [])
        _seed_decision(key)
        ros.append_pending_outcome("fan-err", key, True, "e-0")
        ros.append_pending_outcome("fan-err", key, False, "e-1")

        _fire(F_PATH, "fin_fan_err", _prompt_event("thanks", session="fan-err"))

        row = self._row(db_env, key)
        assert row["failure_count"] == 1 and row["success_count"] == 1
        assert _basis_counts(db_env) == {"tool_errors_only": 1, "acceptance_detected": 1}

    def test_mixed_keys_acceptance_is_a_bounded_weak_boost_per_key(self, db_env, monkeypatch):
        sys.path.insert(0, str(LIB_DIR))
        import routing_outcome_score as score

        a = "python-general-engineer:mix-a"
        b = "golang-general-engineer:mix-b"
        self._pend(monkeypatch, db_env, "mix-acc", [a, b, a])
        before = {k: self._row(db_env, k)["confidence"] for k in (a, b)}

        _fire(F_PATH, "fin_mix_acc", _prompt_event("thanks, that worked", session="mix-acc"))

        for key in (a, b):
            row = self._row(db_env, key)
            assert row["failure_count"] == 0
            assert row["success_count"] == 1, "one weak boost per key, not per entry"
            gain = row["confidence"] - before[key]
            assert 0 <= gain <= score.WEAK_BOOST_DELTA + 1e-9
            assert row["confidence"] <= max(before[key], score.WEAK_CONFIDENCE_CAP) + 1e-9
        assert _basis_counts(db_env) == {"acceptance_shared": 2, "default_no_complaint": 1}
        events = [e for e in _read_events(db_env) if e.get("type") == "outcome"]
        assert [e["reason"] for e in events].count("acceptance-shared-multi-dispatch") == 2

    def test_mixed_keys_rejection_is_ignored(self, db_env, monkeypatch):
        a = "python-general-engineer:mixr-a"
        b = "golang-general-engineer:mixr-b"
        self._pend(monkeypatch, db_env, "mix-rej", [a, b])

        _fire(F_PATH, "fin_mix_rej", _prompt_event("that's wrong", session="mix-rej"))

        for key in (a, b):
            row = self._row(db_env, key)
            assert row["failure_count"] == 0 and row["success_count"] == 0
        assert _basis_counts(db_env) == {"default_no_complaint": 2}


class TestEvidenceRowTargeting:
    """update_evidence_route_outcome must fill the row of the dispatch it
    scores. It used to update the newest row per key and session, so repeat
    dispatches of one key left the older rows NULL."""

    KEY: ClassVar[str] = "python-general-engineer:rows"

    def test_decision_id_targets_the_exact_row(self, db_env):
        import learning_db_v2 as ldb

        for i in range(3):
            _seed_evidence(self.KEY, "rows", f"r-{i}")
        ldb.update_evidence_route_outcome(
            route_key=self.KEY,
            session_id="rows",
            outcome="failure",
            outcome_basis="tool_errors_only",
            decision_id="r-1",
        )
        assert _evidence_outcomes(self.KEY) == {
            "r-0": (None, None),
            "r-1": ("failure", "tool_errors_only"),
            "r-2": (None, None),
        }

    def test_without_decision_id_fills_the_oldest_unscored_row_first(self, db_env):
        import learning_db_v2 as ldb

        for i in range(2):
            _seed_evidence(self.KEY, "rows", f"r-{i}")
        for outcome in ("neutral", "success"):
            ldb.update_evidence_route_outcome(route_key=self.KEY, session_id="rows", outcome=outcome, outcome_basis="b")
        assert _evidence_outcomes(self.KEY) == {"r-0": ("neutral", "b"), "r-1": ("success", "b")}

    def test_without_a_session_the_newest_row_is_scored_not_an_old_open_one(self, db_env):
        import learning_db_v2 as ldb

        _seed_evidence(self.KEY, "old-session", "r-old")
        _seed_evidence(self.KEY, "rows", "r-new")
        ldb.update_evidence_route_outcome(route_key=self.KEY, session_id="", outcome="success", outcome_basis="b")
        assert _evidence_outcomes(self.KEY) == {"r-old": (None, None), "r-new": ("success", "b")}

    def test_unknown_decision_id_falls_back_to_the_key(self, db_env):
        import learning_db_v2 as ldb

        _seed_evidence(self.KEY, "rows", "r-0")
        ldb.update_evidence_route_outcome(
            route_key=self.KEY, session_id="rows", outcome="neutral", outcome_basis="b", decision_id="gone"
        )
        assert _evidence_outcomes(self.KEY) == {"r-0": ("neutral", "b")}


def _async_agent_event(agent_id="agent-abc", session="bg1", skill="programming"):
    """PostToolUse:Agent for a BACKGROUND dispatch: a launch receipt, no reply."""
    event = _agent_event(skill=skill, session=session)
    event["tool_result"] = {
        "isAsync": True,
        "status": "async_launched",
        "agentId": agent_id,
        "description": "do work",
        "prompt": "do work",
        "outputFile": "/nonexistent/agent.output",
    }
    return event


def _subagent_stop(agent_id="agent-abc", session="bg1", **extra):
    return {"hook_event_name": "SubagentStop", "session_id": session, "agent_id": agent_id, **extra}


class TestBackgroundRouteFit:
    """A background dispatch returns a launch receipt at PostToolUse:Agent, so
    its route-fit banner is scored at SubagentStop. 304 of 304 sampled /do
    dispatches were background launches: no verdict was ever recorded."""

    KEY: ClassVar[str] = "python-general-engineer:programming"

    def _launch(self, db_env, name, **kw):
        _fire(A_PATH, name, _async_agent_event(**kw))

    def test_launch_receipt_registers_the_agent_and_scores_nothing(self, db_env):
        import routing_outcome_state as ros

        self._launch(db_env, "bg_launch")

        assert not any(b.startswith("route_fit:") for b in _basis_counts(db_env))
        pending = ros.peek_pending_outcomes("bg1")
        assert [p["key"] for p in pending] == [self.KEY]
        route = ros.claim_async_dispatch("bg1", "agent-abc")
        assert route == {"key": self.KEY, "decision_id": pending[0]["decision_id"]}

    def test_foreground_reply_is_not_registered(self, db_env):
        import routing_outcome_state as ros

        _fire(A_PATH, "fg_launch", _agent_event(skill="programming", session="fg1", output="done.\nroute-fit: ok"))

        assert _basis_counts(db_env)["route_fit:ok"] == 1
        assert json.loads(ros._state_file("fg1").read_text(encoding="utf-8")).get("agents") in ({}, None)

    def test_negative_verdict_at_subagent_stop_decays_and_resolves(self, db_env):
        import routing_outcome_state as ros

        self._launch(db_env, "bg_neg_a")
        baseline = _routing_row(db_env, self.KEY)["confidence"]
        decision_id = ros.peek_pending_outcomes("bg1")[0]["decision_id"]

        stop = _subagent_stop(last_assistant_message="Work done.\n\nroute-fit: wrong-agent")
        _fire(B_PATH, "bg_neg_b", stop)

        row = _routing_row(db_env, self.KEY)
        assert row["confidence"] < baseline and row["failure_count"] == 1
        assert _basis_counts(db_env) == {"route_fit:wrong-agent": 1}
        assert _evidence_outcomes(self.KEY)[decision_id] == ("failure", "route_fit:wrong-agent")
        # Resolved: the pending entry is gone, so the next prompt cannot decay
        # the route again or overwrite the verdict.
        assert ros.peek_pending_outcomes("bg1") == []
        # An intervening failure for the finalizer's repeat-dispatch check.
        assert ros.get_outcome_history("bg1")[self.KEY] == "failure"
        _fire(F_PATH, "bg_neg_f", _prompt_event("that's wrong", session="bg1"))
        assert _routing_row(db_env, self.KEY)["failure_count"] == 1

    def test_redelivered_subagent_stop_scores_once(self, db_env):
        self._launch(db_env, "bg_dup_a")
        stop = _subagent_stop(last_assistant_message="route-fit: wrong-skill")
        _fire(B_PATH, "bg_dup_b1", stop)
        _fire(B_PATH, "bg_dup_b2", stop)

        assert _routing_row(db_env, self.KEY)["failure_count"] == 1
        assert _basis_counts(db_env) == {"route_fit:wrong-skill": 1}

    def test_ok_verdict_boosts_nothing_and_leaves_the_entry_pending(self, db_env):
        import routing_outcome_state as ros

        self._launch(db_env, "bg_ok_a")
        baseline = _routing_row(db_env, self.KEY)

        _fire(B_PATH, "bg_ok_b", _subagent_stop(last_assistant_message="All done.\nroute-fit: ok"))

        row = _routing_row(db_env, self.KEY)
        assert row["confidence"] == baseline["confidence"]
        assert row["success_count"] == 0 and row["failure_count"] == 0
        assert _basis_counts(db_env) == {"route_fit:ok": 1}
        # `ok` is weak evidence: the user's next prompt still decides.
        assert [p["key"] for p in ros.peek_pending_outcomes("bg1")] == [self.KEY]

    def test_reply_is_read_from_the_agent_transcript_when_the_event_omits_it(self, db_env, tmp_path):
        self._launch(db_env, "bg_tr_a")
        transcript = tmp_path / "agent.jsonl"
        lines = [
            {"type": "user", "message": {"role": "user", "content": "do work"}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "route-fit: ok"}]}},
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {}}]}},
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "Finished.\nroute-fit: needs-coordinator"}]},
            },
        ]
        transcript.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")

        _fire(B_PATH, "bg_tr_b", _subagent_stop(agent_transcript_path=str(transcript)))

        assert _basis_counts(db_env) == {"route_fit:needs-coordinator": 1}

    @pytest.mark.parametrize(
        "extra",
        [
            {},  # no reply and no transcript
            {"last_assistant_message": "done, no banner"},
            {"last_assistant_message": "route-fit: maybe"},  # outside the enum
            {"agent_transcript_path": "/nonexistent/agent.jsonl"},
        ],
    )
    def test_missing_or_malformed_banner_records_nothing(self, extra, db_env):
        self._launch(db_env, "bg_none_a")
        _fire(B_PATH, "bg_none_b", _subagent_stop(**extra))

        assert _basis_counts(db_env) == {}
        assert _routing_row(db_env, self.KEY)["failure_count"] == 0

    def test_unregistered_agent_is_ignored(self, db_env):
        """A reviewer sub-agent or nested fan-out was never a /do dispatch."""
        self._launch(db_env, "bg_other_a")
        stop = _subagent_stop(agent_id="some-other-agent", last_assistant_message="route-fit: wrong-agent")
        _fire(B_PATH, "bg_other_b", stop)

        assert _basis_counts(db_env) == {}

    def test_subagent_stop_exits_zero_with_a_banner(self, db_env, monkeypatch):
        # Subprocess: point its bridge state at tmp_path, not the real /tmp.
        monkeypatch.setenv("CLAUDE_ROUTING_STATE_DIR", str(db_env["state"]))
        stop = _subagent_stop(last_assistant_message="route-fit: wrong-agent")
        assert _run_hook(B_PATH, stop).returncode == 0


class TestOutcomeStateTakeAndClaim:
    """Bridge-state primitives behind the Stop fallback and background route-fit."""

    def test_take_resolvable_keeps_fresh_clean_entries_in_order(self, db_env):
        import routing_outcome_state as ros

        for key, errors in (("a:1", False), ("b:2", True), ("c:3", False)):
            ros.append_pending_outcome("take", key, errors, f"d-{key}")
        path = ros._state_file("take")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["pending"].append({"key": "d:4", "errors": False, "attempts": 0, "created": "not-a-number"})
        path.write_text(json.dumps(data), encoding="utf-8")

        taken = ros.take_resolvable_pending_outcomes("take", ros.STOP_STALE_AGE_SEC)

        assert [t["key"] for t in taken] == ["b:2", "d:4"]  # errored, malformed
        kept = ros.peek_pending_outcomes("take")
        assert [k["key"] for k in kept] == ["a:1", "c:3"]
        assert [k["decision_id"] for k in kept] == ["d-a:1", "d-c:3"]
        assert ros.take_resolvable_pending_outcomes("take", ros.STOP_STALE_AGE_SEC) == []

    def test_requeue_and_revalidate_keep_the_decision_id(self, db_env):
        import routing_outcome_state as ros

        ros.append_pending_outcome("rq", "a:1", False, "d-1")
        ros.requeue_pending_outcomes("rq", ros.drain_pending_outcomes("rq"))
        ros.revalidate_pending_outcomes("rq", ros.drain_pending_outcomes("rq"))

        assert [p["decision_id"] for p in ros.peek_pending_outcomes("rq")] == ["d-1"]

    def test_discard_matches_one_dispatch_of_a_repeated_key(self, db_env):
        import routing_outcome_state as ros

        ros.append_pending_outcome("disc", "a:1", False, "d-1")
        ros.append_pending_outcome("disc", "a:1", False, "d-2")

        assert ros.discard_pending_outcome("disc", "d-1") is True
        assert ros.discard_pending_outcome("disc", "d-1") is False
        assert ros.discard_pending_outcome("disc", "") is False
        assert [p["decision_id"] for p in ros.peek_pending_outcomes("disc")] == ["d-2"]

    def test_async_registry_is_claimed_once_and_bounded(self, db_env, monkeypatch):
        import routing_outcome_state as ros

        monkeypatch.setattr(ros, "MAX_ASYNC_AGENTS", 3)
        for i in range(5):
            ros.register_async_dispatch("reg", f"agent-{i}", f"k:{i}", f"d-{i}")

        assert ros.claim_async_dispatch("reg", "agent-0") is None  # evicted, oldest first
        assert ros.claim_async_dispatch("reg", "agent-4") == {"key": "k:4", "decision_id": "d-4"}
        assert ros.claim_async_dispatch("reg", "agent-4") is None
        assert ros.claim_async_dispatch("reg", "") is None
        # Pending and the registry share one file and do not disturb each other.
        ros.append_pending_outcome("reg", "k:9", False)
        assert ros.claim_async_dispatch("reg", "agent-3") == {"key": "k:3", "decision_id": "d-3"}
        assert [p["key"] for p in ros.peek_pending_outcomes("reg")] == ["k:9"]


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

    def test_benign_prompt_never_decays_end_to_end(self, db_env, monkeypatch):
        # CORE GUARD: a benign prompt (rework verb only in a LATER clause, or a
        # spec/instructional first clause) must NEVER DECAY the route. Under T4 the
        # outcome is SUCCESS only when the first clause carries an acceptance
        # marker; an instructional/spec first clause is NEUTRAL (no boost). Either
        # way failure_count stays 0 — the precision guard this test exists for.
        sys.path.insert(0, str(LIB_DIR))
        import learning_db_v2 as ldb
        import routing_outcome_state as ros

        f_unit = _load(F_PATH, "fin_benign_unit")
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
            # acceptance first clause => success; instructional/spec => neutral.
            expected = 1 if f_unit.is_acceptance(prompt) else 0
            assert after["success_count"] == expected, prompt

    def test_named_rollback_phrase_does_not_decay_end_to_end(self, db_env, monkeypatch):
        # Spec-required E2E false-positive guard: a single clean dispatch + the
        # review's roll-back SPEC phrase must NOT decay the route. T4: it carries
        # no acceptance marker (instructional/conditional clause) => NEUTRAL
        # (failure_count=0, success_count=0). The guard is "no false decay".
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
        before = next(r for r in _query_routing_all(db_env) if r["key"] == key)["confidence"]
        session = "named-rollback-e2e"
        ros.append_pending_outcome(session, key, errors=False)
        f = _load(F_PATH, "fin_named_rollback_e2e")
        ev = _prompt_event("the migration should roll back the change on failure", session=session)
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(ev)):
            f.main()
        after = next(r for r in _query_routing_all(db_env) if r["key"] == key)
        assert after["failure_count"] == 0, "spec phrase falsely decayed the route"
        assert after["success_count"] == 0, "spec phrase is neutral, not success (T4)"
        assert after["confidence"] == before
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


# ---------------------------------------------------------------------------
# Handoff-completeness telemetry: spec_score / spec_missing / prompt_chars
# ---------------------------------------------------------------------------

BUILD_DISPATCH_PATH = HOOKS_DIR.parent / "scripts" / "build-dispatch.py"
SPEC_LABELS_ALL = (
    "Request (verbatim),Intent,Acceptance criteria,Relevant file locations,Decisions,Prior results,## Repo state"
)
SPEC_COLUMNS = ("spec_score", "spec_missing", "prompt_chars")


def _build_preamble_full() -> str:
    """build_preamble() with every task_spec field filled and the repo-state block on."""
    mod = _load(BUILD_DISPATCH_PATH, "build_dispatch_for_spec_score")
    return mod.build_preamble(
        {
            "agent": "python-general-engineer",
            "skill": "testing",
            "complexity": "medium",
            "model": "opus",
            "task_spec": {
                "request_verbatim": "score handoff completeness",
                "intent": "Add telemetry.",
                "constraints": "No commits.",
                "acceptance": "Tests pass.",
                "files": "hooks/routing-decision-recorder.py",
                "decisions": "Score only [do-route] dispatches.",
                "prior_results": "pre-route fallthrough.",
                "gaps": "none",
                "operator_context": "personal profile",
            },
        },
        repo_root=HOOKS_DIR.parent,
    )


def _spec_row(db_env) -> dict:
    """The three spec fields of the newest evidence_route_decisions row."""
    import sqlite3

    import learning_db_v2 as ldb

    conn = sqlite3.connect(ldb.get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT spec_score, spec_missing, prompt_chars FROM evidence_route_decisions ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "no evidence_route_decisions row recorded"
    return dict(row)


def _run_recorder_prompt(monkeypatch, prompt: str, name: str) -> None:
    """Run recorder main() in-process on an Agent event whose prompt is exactly `prompt`."""
    a = _load(A_PATH, f"rdr_spec_{name}")
    monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
    monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
    event = _agent_event(marker=False, body=prompt)
    with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
        a.main()


@pytest.mark.usefixtures("use_public_index")
class TestSpecScore:
    def test_full_preamble_scores_seven(self, db_env, monkeypatch):
        # (a) every task_spec field filled: all seven labels present.
        prompt = _build_preamble_full()
        _run_recorder_prompt(monkeypatch, prompt, "full")
        assert _spec_row(db_env) == {"spec_score": 7, "spec_missing": "", "prompt_chars": len(prompt)}

    def test_marker_only_scores_zero(self, db_env, monkeypatch):
        # (b) marker alone: every label absent, listed in fixed order.
        prompt = "[do-route] agent=python-general-engineer skill=testing complexity=medium\n"
        _run_recorder_prompt(monkeypatch, prompt, "marker_only")
        assert _spec_row(db_env) == {"spec_score": 0, "spec_missing": SPEC_LABELS_ALL, "prompt_chars": len(prompt)}

    def test_no_marker_leaves_fields_null(self, db_env, monkeypatch):
        # (c) no marker: the recorder skips the event, so the only row is the
        # seeded one and its fields stay NULL.
        import learning_db_v2 as ldb

        ldb.record_evidence_route_decision(session_id="s1", agent="python-general-engineer", skill="x")
        _run_recorder_prompt(monkeypatch, "**Intent:** x\n## Repo state\n", "no_marker")
        assert _spec_row(db_env) == {"spec_score": None, "spec_missing": None, "prompt_chars": None}
        import sqlite3

        conn = sqlite3.connect(ldb.get_db_path())
        try:
            assert conn.execute("SELECT COUNT(*) FROM evidence_route_decisions").fetchone()[0] == 1
        finally:
            conn.close()

    def test_disable_env_var_leaves_fields_null(self, db_env, monkeypatch):
        # (d) VEXJOY_SPEC_SCORE_DISABLE=1 with a full preamble.
        monkeypatch.setenv("VEXJOY_SPEC_SCORE_DISABLE", "1")
        _run_recorder_prompt(monkeypatch, _build_preamble_full(), "disabled")
        assert _spec_row(db_env) == {"spec_score": None, "spec_missing": None, "prompt_chars": None}

    def test_pre_migration_db_degrades_to_decision_row(self, db_env, monkeypatch):
        # A DB without the spec columns: the decision row is still written and
        # the hook does not raise.
        import sqlite3

        import learning_db_v2 as ldb

        conn = sqlite3.connect(ldb.get_db_path())
        for col in SPEC_COLUMNS:
            conn.execute(f"ALTER TABLE evidence_route_decisions DROP COLUMN {col}")
        conn.commit()
        conn.close()
        prompt = "[do-route] agent=python-general-engineer skill=- complexity=medium\n**Intent:** x\n"
        _run_recorder_prompt(monkeypatch, prompt, "pre_migration")
        conn = sqlite3.connect(ldb.get_db_path())
        try:
            assert conn.execute("SELECT COUNT(*) FROM evidence_route_decisions").fetchone()[0] == 1
        finally:
            conn.close()


class TestSpecScoreMigration:
    def test_pre_migration_db_gains_columns_once(self, tmp_path, monkeypatch):
        # (e) a DB at user_version 9 without the columns; migrate twice; each
        # column exists exactly once and the migration row is recorded once.
        import sqlite3

        sys.path.insert(0, str(LIB_DIR))
        import learning_db_v2 as ldb

        db_dir = tmp_path / "learning"
        db_dir.mkdir()
        monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
        monkeypatch.setattr(ldb, "_initialized", False, raising=False)

        db_path = db_dir / "learning.db"
        conn = sqlite3.connect(db_path)
        conn.executescript(ldb._SCHEMA)
        for col in SPEC_COLUMNS:
            conn.execute(f"ALTER TABLE evidence_route_decisions DROP COLUMN {col}")
        conn.execute("PRAGMA user_version = 9")
        conn.commit()
        conn.close()

        def columns():
            c = sqlite3.connect(db_path)
            try:
                return [r[1] for r in c.execute("PRAGMA table_info(evidence_route_decisions)")]
            finally:
                c.close()

        assert not set(SPEC_COLUMNS) & set(columns())

        ldb.init_db()
        monkeypatch.setattr(ldb, "_initialized", False, raising=False)
        ldb.init_db()

        after = columns()
        for col in SPEC_COLUMNS:
            assert after.count(col) == 1, (col, after)

        c = sqlite3.connect(db_path)
        try:
            assert c.execute("PRAGMA user_version").fetchone()[0] == ldb._CURRENT_SCHEMA_VERSION
            assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
            rows = c.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 10").fetchone()[0]
        finally:
            c.close()
        assert rows == 1


# ---------------------------------------------------------------------------
# Evidence route decision — recording and error-logging
# ---------------------------------------------------------------------------


class TestEvidenceRouteDecisionRecording:
    """Verify that evidence_route_decisions rows are written for every
    /do-routed dispatch and that failures are now logged instead of
    silently swallowed."""

    def test_decision_row_written_on_marker_dispatch(self, db_env, monkeypatch):
        """A standard [do-route] Agent dispatch writes an evidence_route_decisions row."""
        a = _load(A_PATH, "rdr_evidence_row")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)
        event = _agent_event(skill="testing", body="Write tests.", session="ev-s1")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()

        import sqlite3

        import learning_db_v2 as ldb

        conn = sqlite3.connect(ldb.get_db_path())
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM evidence_route_decisions WHERE session_id = 'ev-s1'").fetchall()
        finally:
            conn.close()
        assert len(rows) == 1, f"expected 1 evidence_route_decisions row, got {len(rows)}"
        assert rows[0]["agent"] == "python-general-engineer"
        assert rows[0]["skill"] == "testing"
        assert rows[0]["route_key"] == "python-general-engineer:testing"

    def test_evidence_failure_is_logged_not_swallowed(self, db_env, monkeypatch):
        """When record_evidence_route_decision raises, the error is logged
        via hook_error instead of silently swallowed by a bare pass."""
        a = _load(A_PATH, "rdr_evidence_err_logged")
        monkeypatch.setattr(a, "append_pending_outcome", lambda *_a, **_k: None)
        monkeypatch.setattr(a, "claim_dispatch", lambda *_a, **_k: True)

        # Patch record_evidence_route_decision to raise
        import learning_db_v2 as ldb

        original = ldb.record_evidence_route_decision
        calls = []

        def failing_record(**kwargs):
            calls.append(kwargs)
            raise RuntimeError("simulated DB failure")

        monkeypatch.setattr(ldb, "record_evidence_route_decision", failing_record)

        # Capture hook_error calls
        errors_logged = []
        original_hook_error = a.hook_error

        def capturing_hook_error(name, exc):
            errors_logged.append((name, str(exc)))
            # call original so it writes to debug log
            original_hook_error(name, exc)

        monkeypatch.setattr(a, "hook_error", capturing_hook_error)

        event = _agent_event(skill="testing", body="Write tests.", session="ev-err-s1")
        with patch("sys.exit"), patch("sys.stdin.read", return_value=json.dumps(event)):
            a.main()

        # The decision was attempted
        assert len(calls) == 1
        # The error was logged (not silently swallowed)
        assert any("routing-decision-recorder:evidence" in name for name, _ in errors_logged)
        # The learnings row was still written (failure of evidence row doesn't
        # block the learnings row)
        routing_rows = _query_routing(db_env)
        assert any(r["key"] == "python-general-engineer:testing" for r in routing_rows)


def test_recorder_fails_soft_when_scripts_lib_is_missing(tmp_path):
    """An install with hooks but no scripts/ must not crash the hook on every Agent dispatch.

    route_types lives in scripts/lib. The CI hook-health job used to deploy hooks/
    alone, and the recorder then exited 1 at import. It records the ImportError
    through hook_error and exits 0 instead.
    """
    hooks = tmp_path / "home" / ".claude" / "hooks"
    shutil.copytree(LIB_DIR, hooks / "lib", ignore=shutil.ignore_patterns("__pycache__", "tests"))
    shutil.copy2(A_PATH, hooks / A_PATH.name)
    errors = Path(os.environ["CLAUDE_HOOK_ERRORS_PATH"])  # isolated per test by conftest

    result = _run_hook(hooks / A_PATH.name, _agent_event(skill="programming"))

    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    entries = [json.loads(line) for line in errors.read_text(encoding="utf-8").splitlines()]
    assert [e["hook"] for e in entries] == ["routing-decision-recorder"]
    assert entries[0]["type"] in {"ImportError", "ModuleNotFoundError"}
    assert "route_types" in entries[0]["msg"]


def _inject_pending(session: str, entries: list, *, first: bool = True) -> None:
    """Write raw entries into one session's pending list, before or after the real ones."""
    import routing_outcome_state as ros

    path = ros._state_file(session)
    with ros._state_lock(path):
        data = ros._load(path)
        data["pending"] = [*entries, *data["pending"]] if first else [*data["pending"], *entries]
        ros._atomic_write(path, data)


# Shapes a corrupt or hand-edited state file can hold. Each resolver clears the
# pending list BEFORE its loop, so a crash on one of these loses every entry.
_MALFORMED_PENDING = [
    "a-string",
    None,
    7,
    ["a", "list"],
    {"key": ["unhashable"], "errors": True, "attempts": 0, "created": 1.0},
    {"key": {"a": 1}, "errors": True, "attempts": 0},
    {"key": 12, "errors": True, "attempts": 0},
    {"errors": True},
]


class TestMalformedPendingEntries:
    """A malformed pending entry is dropped alone; its valid siblings still resolve."""

    def test_stop_fallback_scores_the_valid_sibling_and_writes_history(self, db_env):
        import routing_outcome_state as ros

        key = _seed_decision("python-general-engineer:stop-sibling")
        session = "stop-malformed"
        ros.append_pending_outcome(session, key, errors=True)
        _inject_pending(session, _MALFORMED_PENDING)

        _fire(STOP_PATH, "stop_malformed", {"hook_event_name": "SessionEnd", "session_id": session})

        assert _routing_row(db_env, key)["failure_count"] == 1
        assert _basis_counts(db_env) == {"tool_errors_only": 1}
        assert ros.get_outcome_history(session) == {key: "failure"}
        assert ros.peek_pending_outcomes(session) == []

    def test_stop_fallback_counts_only_scored_entries(self, db_env):
        import routing_outcome_state as ros

        key = _seed_decision("python-general-engineer:stop-count")
        session = "stop-count"
        ros.append_pending_outcome(session, key, errors=True)
        _inject_pending(session, _MALFORMED_PENDING, first=False)

        stop = _load(STOP_PATH, "stop_count")

        assert stop.finalize_routing_outcomes(session, session_end=True) == 1

    def test_stop_fallback_failure_reaches_history_when_a_later_entry_raises(self, db_env, monkeypatch):
        """A failure resolved before a crash must still block the next weak boost."""
        import routing_outcome_score as score
        import routing_outcome_state as ros

        first = _seed_decision("python-general-engineer:stop-first")
        second = _seed_decision("python-general-engineer:stop-second")
        third = _seed_decision("python-general-engineer:stop-third")
        session = "stop-raise"
        for key in (first, second, third):
            ros.append_pending_outcome(session, key, errors=True)
        real = score.record_resolved_outcome

        def flaky(**kwargs):
            if kwargs["key"] == second:
                raise RuntimeError("db busy")
            return real(**kwargs)

        monkeypatch.setattr(score, "record_resolved_outcome", flaky)
        stop = _load(STOP_PATH, "stop_raise")

        assert stop.finalize_routing_outcomes(session, session_end=True) == 2
        # The entry that raised is not in history; the ones around it are.
        assert ros.get_outcome_history(session) == {first: "failure", third: "failure"}
        assert _routing_row(db_env, third)["failure_count"] == 1

    def test_stop_fallback_writes_history_when_the_loop_itself_dies(self, db_env, monkeypatch):
        import routing_outcome_score as score
        import routing_outcome_state as ros

        first = _seed_decision("python-general-engineer:stop-die-first")
        second = _seed_decision("python-general-engineer:stop-die-second")
        session = "stop-die"
        for key in (first, second):
            ros.append_pending_outcome(session, key, errors=True)
        real = score.record_resolved_outcome

        def dies(**kwargs):
            if kwargs["key"] == second:
                raise KeyboardInterrupt  # not an Exception: skips the per-entry guard
            return real(**kwargs)

        monkeypatch.setattr(score, "record_resolved_outcome", dies)
        stop = _load(STOP_PATH, "stop_die")

        with pytest.raises(KeyboardInterrupt):
            stop.finalize_routing_outcomes(session, session_end=True)
        assert ros.get_outcome_history(session) == {first: "failure"}

    def test_finalizer_scores_the_valid_sibling(self, db_env):
        import routing_outcome_state as ros

        key = _seed_decision("python-general-engineer:fin-sibling")
        session = "fin-malformed-shapes"
        ros.append_pending_outcome(session, key, errors=False)
        _inject_pending(session, _MALFORMED_PENDING)

        _fire(F_PATH, "fin_shapes", _prompt_event("thanks, that worked", session=session))

        # One live route key: the acceptance is attributable and boosts it.
        assert _routing_row(db_env, key)["success_count"] == 1
        assert _basis_counts(db_env) == {"acceptance_detected": 1}
        assert ros.get_outcome_history(session) == {key: "success"}

    def test_subagent_stop_keeps_the_valid_sibling_pending(self, db_env):
        import routing_outcome_state as ros

        key = _seed_decision("python-general-engineer:rec-sibling")
        session = "rec-malformed"
        ros.append_pending_outcome(session, key, errors=False)
        _inject_pending(session, _MALFORMED_PENDING)

        _fire(B_PATH, "rec_malformed", {"hook_event_name": "SubagentStop", "session_id": session})

        assert [p["key"] for p in ros.peek_pending_outcomes(session)] == [key]


def _rightsizing_rows(db_env) -> dict[str, int]:
    """rightsizing key -> observation_count."""
    return {
        r["key"]: int(r["observation_count"]) for r in _query_routing(db_env) if r["key"].startswith("rightsizing:")
    }


class TestBackgroundRightsizing:
    """A background review returns a launch receipt at PostToolUse:Agent, so its
    rightsizing banner is first readable at SubagentStop."""

    BANNER: ClassVar[str] = (
        "rightsizing: tier=3 files=15 packages=4 agents_dispatched=17 findings=2C/3H/5M tokens=84000 wall_clock_s=312"
    )

    def test_launch_receipt_records_no_rightsizing(self, db_env):
        _fire(A_PATH, "bgr_launch", _async_agent_event(skill="review"))

        assert _rightsizing_rows(db_env) == {}

    def test_banner_at_subagent_stop_is_recorded_with_its_fields(self, db_env):
        _fire(A_PATH, "bgr_a", _async_agent_event(skill="review"))

        _fire(B_PATH, "bgr_b", _subagent_stop(last_assistant_message=f"Review done.\n{self.BANNER}\nroute-fit: ok"))

        assert _rightsizing_rows(db_env) == {"rightsizing:tier3": 1}
        row = _routing_row(db_env, "rightsizing:tier3")
        assert "sum_critical: 2" in row["value"] and "sum_tokens: 84000" in row["value"]
        assert row["source"] == "hook:routing-outcome-recorder"
        assert _basis_counts(db_env) == {"route_fit:ok": 1}

    def test_banner_without_route_fit_is_still_recorded(self, db_env):
        _fire(A_PATH, "bgr_only_a", _async_agent_event(skill="review"))

        _fire(B_PATH, "bgr_only_b", _subagent_stop(last_assistant_message=f"done. {self.BANNER}"))

        assert _rightsizing_rows(db_env) == {"rightsizing:tier3": 1}
        assert _basis_counts(db_env) == {}

    def test_banner_is_read_from_the_agent_transcript(self, db_env, tmp_path):
        _fire(A_PATH, "bgr_tr_a", _async_agent_event(skill="review"))
        transcript = tmp_path / "agent.jsonl"
        line = {"type": "assistant", "message": {"content": [{"type": "text", "text": self.BANNER}]}}
        transcript.write_text(json.dumps(line) + "\n", encoding="utf-8")

        _fire(B_PATH, "bgr_tr_b", _subagent_stop(agent_transcript_path=str(transcript)))

        assert _rightsizing_rows(db_env) == {"rightsizing:tier3": 1}

    def test_redelivered_subagent_stop_records_once(self, db_env):
        _fire(A_PATH, "bgr_dup_a", _async_agent_event(skill="review"))
        stop = _subagent_stop(last_assistant_message=self.BANNER)

        _fire(B_PATH, "bgr_dup_b1", stop)
        _fire(B_PATH, "bgr_dup_b2", stop)

        assert _rightsizing_rows(db_env) == {"rightsizing:tier3": 1}

    def test_foreground_review_is_not_recorded_again_at_subagent_stop(self, db_env):
        _fire(A_PATH, "bgr_fg_a", _agent_event(skill="review", session="bg1", output=f"done. {self.BANNER}"))

        _fire(B_PATH, "bgr_fg_b", _subagent_stop(last_assistant_message=f"done. {self.BANNER}"))

        assert _rightsizing_rows(db_env) == {"rightsizing:tier3": 1}

    def test_unregistered_agent_records_nothing(self, db_env):
        _fire(A_PATH, "bgr_other_a", _async_agent_event(skill="review"))

        _fire(B_PATH, "bgr_other_b", _subagent_stop(agent_id="someone-else", last_assistant_message=self.BANNER))

        assert _rightsizing_rows(db_env) == {}

    def test_rightsizing_failure_does_not_cost_the_route_fit_verdict(self, db_env, monkeypatch):
        import rightsizing_banner

        def _boom(*_a, **_k):
            raise RuntimeError("db busy")

        monkeypatch.setattr(rightsizing_banner, "record_rightsizing", _boom)
        _fire(A_PATH, "bgr_boom_a", _async_agent_event(skill="review"))

        _fire(B_PATH, "bgr_boom_b", _subagent_stop(last_assistant_message=f"{self.BANNER}\nroute-fit: wrong-skill"))

        assert _basis_counts(db_env) == {"route_fit:wrong-skill": 1}
