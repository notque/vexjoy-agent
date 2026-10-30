"""Offline tests for jev_search: a fake evaluate stands in for Jev (no network)."""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import jev_limits
import jev_search
from jev_search import Escalation, TaskLedger, beam_search, checkpoint_search, progress_questions

# A number line: state is an int, moves are +1, +2, and -1. Target decides "done".


def expand(n: int) -> list[tuple[str, int]]:
    return [(f"add one to {n}", n + 1), (f"add two to {n}", n + 2), (f"subtract one at {n}", n - 1)]


def describe(n: int) -> str:
    return f"counter is {n}"


class FakeJev:
    """Answers progress questions by closeness to ``target``; records every request."""

    def __init__(self, target: int, *, mode: str = "rank", weights: dict[int, float] | None = None) -> None:
        self.target = target
        self.mode = mode
        self.weights = weights or {}
        self.requests: list[tuple[Any, dict[str, Any]]] = []

    def _value(self, text: str) -> int:
        match = re.search(r"counter is (-?\d+)", text)
        assert match, text
        return int(match.group(1))

    def __call__(self, state: Any, questions: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        self.requests.append((state, questions))
        if self.mode == "raise":
            raise RuntimeError("transport down")
        if self.mode == "malformed":
            return {"answers": {"progress": {"choice": "nonsense"}}}
        if self.mode == "missing":
            return {"answers": {}}
        if self.mode == "no_progress":
            labels = list(questions["progress"]["criteria"])
            probs = {k: 0.1 / (len(labels) - 1) for k in labels}
            probs[jev_search.NO_PROGRESS] = 0.9
            return {"answers": {"progress": {"choice": jev_search.NO_PROGRESS, "probabilities": probs}}}
        cands = state["candidates"]
        answers: dict[str, Any] = {}
        for qid, q in questions.items():
            if q["type"] == "choice":
                labels = [k for k in q["criteria"] if k != jev_search.NO_PROGRESS]
                if self.mode == "tie":
                    weights = {k: 1.0 for k in labels}
                elif self.mode == "fixed":
                    weights = {k: self.weights[self._value(cands[k])] for k in labels}
                else:
                    dist = {k: abs(self.target - self._value(cands[k])) for k in labels}
                    nearest = min(dist.values())
                    weights = {k: math.exp(nearest - d) for k, d in dist.items()}
                weights[jev_search.NO_PROGRESS] = 0.0
                total = sum(weights.values())
                probs = {k: w / total for k, w in weights.items()}
                answers[qid] = {
                    "choice": max(probs, key=lambda k: probs[k]),
                    "probabilities": probs,
                    "confidence": max(probs.values()),
                }
            else:
                label = qid.split(":", 1)[1]
                dist = abs(self.target - self._value(cands[label]))
                answers[qid] = {"score": 3.0 * math.exp(-dist / 20), "probabilities": {}, "confidence": 0.9}
        return {"answers": answers}


def test_progress_questions_choice_uses_labels_and_no_progress_option() -> None:
    qs = progress_questions("reach 5", ["add one", "add two"])
    assert list(qs) == ["progress"]
    q = qs["progress"]
    assert q["type"] == "choice"
    assert set(q["criteria"]) == {"add one", "add two", jev_search.NO_PROGRESS}
    assert "reach 5" in q["instructions"]["focus"]


def test_progress_questions_score_above_choice_cutoff() -> None:
    labels = [f"move {i}" for i in range(jev_search.MAX_CHOICE_OPTIONS + 1)]
    qs = progress_questions("reach 5", labels)
    assert len(qs) == len(labels)
    assert all(q["type"] == "score" and q["criteria"] == jev_search.PROGRESS_LEVELS for q in qs.values())


def test_progress_questions_rejects_duplicate_labels() -> None:
    with pytest.raises(ValueError):
        progress_questions("reach 5", ["a", "a"])


def test_happy_path_reaches_subgoal() -> None:
    jev = FakeJev(target=6)
    res = beam_search(0, expand, "reach 6", is_done=lambda n: n == 6, width=1, evaluate=jev, describe=describe)
    assert res.status == "done"
    assert res.state == 6
    assert res.path[-1].startswith("add")
    assert res.calls == len(jev.requests) > 0
    assert res.escalations == 0


def test_done_start_makes_no_call() -> None:
    jev = FakeJev(target=0)
    res = beam_search(0, expand, "stay", is_done=lambda n: n == 0, evaluate=jev)
    assert (res.status, res.calls, res.path) == ("done", 0, [])


def test_beam_keeps_width_branches_and_records_dead_ends() -> None:
    jev = FakeJev(target=100)
    expanded: list[int] = []

    def tracking_expand(n: int) -> list[tuple[str, int]]:
        expanded.append(n)
        return expand(n)

    ledger = TaskLedger(goal="count up")
    res = beam_search(
        0,
        tracking_expand,
        "reach 100",
        is_done=lambda n: n == 100,
        width=2,
        max_steps=2,
        # Step 2 has two branches at value 3 on either side of the cut: a boundary tie.
        escalate=lambda esc: esc.options[0][0],
        evaluate=jev,
        ledger=ledger,
        describe=describe,
    )
    assert res.status == "step_limit"
    assert res.escalations == 1
    # Step 1 expands the start; step 2 expands exactly the two kept branches.
    assert expanded == [0, 2, 1]
    assert any("subtract one at 0" in d for d in ledger.dead_ends)


def test_small_expansion_skips_jev() -> None:
    jev = FakeJev(target=3)
    res = beam_search(
        0, lambda n: [("step", n + 1)], "reach 3", is_done=lambda n: n == 3, width=3, evaluate=jev, describe=describe
    )
    assert res.status == "done"
    assert res.calls == 0


def test_tie_escalates_to_reasoner() -> None:
    jev = FakeJev(target=6, mode="tie")
    seen: list[Escalation] = []

    def reasoner(esc: Escalation) -> str:
        seen.append(esc)
        return next(label for label, _ in esc.options if label.startswith("add two"))

    res = beam_search(
        0,
        expand,
        "reach 6",
        is_done=lambda n: n == 6,
        width=1,
        escalate=reasoner,
        evaluate=jev,
        describe=describe,
    )
    assert res.status == "done"
    assert res.path == ["add two to 0", "add two to 2", "add two to 4"]
    # The third step's candidates include 6, so code ends the search before any call.
    assert res.escalations == len(seen) == 2
    assert seen[0].reason == "tie"
    assert seen[0].ledger["checkpoint"] == "reach 6"


@pytest.mark.parametrize("mode", ["malformed", "missing", "raise"])
def test_bad_answer_escalates_as_invalid(mode: str) -> None:
    jev = FakeJev(target=6, mode=mode)
    seen: list[Escalation] = []

    def reasoner(esc: Escalation) -> str | None:
        seen.append(esc)
        return None

    res = beam_search(
        0, expand, "reach 6", is_done=lambda n: n == 6, width=1, escalate=reasoner, evaluate=jev, describe=describe
    )
    assert res.status == "escalated"
    assert seen[0].reason == "invalid_answer"
    assert seen[0].ranking == []


def test_tie_inside_beam_does_not_escalate() -> None:
    # Values 1 and 2 tie for first; both are kept, and 0 is pruned by a clear gap.
    jev = FakeJev(target=0, mode="fixed", weights={1: 0.4, 2: 0.4, -1: 0.2})
    res = beam_search(
        0, expand, "reach 9", is_done=lambda n: n == 9, width=2, max_steps=1, evaluate=jev, describe=describe
    )
    assert res.status == "step_limit"
    assert res.escalations == 0


def test_tie_at_beam_boundary_escalates() -> None:
    # Clear leader, but the last kept (1) and first pruned (-1) are within margin.
    jev = FakeJev(target=0, mode="fixed", weights={2: 0.6, 1: 0.21, -1: 0.19})
    res = beam_search(
        0, expand, "reach 9", is_done=lambda n: n == 9, width=2, max_steps=1, evaluate=jev, describe=describe
    )
    assert res.status == "escalated"
    assert res.reason.startswith("tie")


def test_width_one_uses_top_two_gap() -> None:
    jev = FakeJev(target=0, mode="fixed", weights={2: 0.45, 1: 0.4, -1: 0.15})
    res = beam_search(
        0, expand, "reach 9", is_done=lambda n: n == 9, width=1, max_steps=1, evaluate=jev, describe=describe
    )
    assert res.status == "escalated"
    assert res.reason.startswith("tie")


def test_no_progress_pick_escalates() -> None:
    jev = FakeJev(target=6, mode="no_progress")
    res = beam_search(0, expand, "reach 6", is_done=lambda n: n == 6, width=1, evaluate=jev, describe=describe)
    assert res.status == "escalated"
    assert res.reason.startswith("no_progress")


def test_no_escalate_returns_escalated_without_guessing() -> None:
    jev = FakeJev(target=6, mode="tie")
    res = beam_search(0, expand, "reach 6", is_done=lambda n: n == 6, width=1, evaluate=jev, describe=describe)
    assert res.status == "escalated"
    assert res.path == []
    assert res.escalations == 1
    assert "no escalate function" in res.reason


def test_unknown_label_from_reasoner_fails() -> None:
    jev = FakeJev(target=6, mode="tie")
    res = beam_search(
        0,
        expand,
        "reach 6",
        is_done=lambda n: n == 6,
        width=1,
        escalate=lambda _e: "bogus",
        evaluate=jev,
        describe=describe,
    )
    assert res.status == "failed"


def test_ledger_truncates_oldest_first_under_budget() -> None:
    ledger = TaskLedger(goal="g", checkpoint="c")
    for i in range(200):
        ledger.add_fact(f"fact {i} " + "x" * 40)
        ledger.add_dead_end(f"dead {i} " + "y" * 40)
    rendered = ledger.render(300)
    assert jev_limits.estimate_tokens(rendered) <= 300
    assert "omitted" in rendered
    assert rendered["facts"][-1].startswith("fact 199")
    assert rendered["dead_ends"][-1].startswith("dead 199")
    assert not any(f.startswith("fact 0 ") for f in rendered["facts"])
    # Source ledger is untouched; only the rendering is bounded.
    assert len(ledger.facts) == 200


def test_ledger_render_without_truncation_has_no_omitted_note() -> None:
    rendered = TaskLedger(goal="g", checkpoint="c", facts=["a"]).render()
    assert "omitted" not in rendered


def test_ledger_budget_too_small_raises() -> None:
    with pytest.raises(ValueError):
        TaskLedger(goal="g" * 400, checkpoint="c" * 300).render(10)


def test_checkpoint_chaining_carries_ledger() -> None:
    jev = FakeJev(target=0)

    def done_for(subgoal: str):
        target = int(subgoal.rsplit(" ", 1)[1])
        jev.target = target
        return lambda n: n == target

    res = checkpoint_search(
        0, ["reach 3", "reach 6"], expand, is_done_for=done_for, width=1, evaluate=jev, describe=describe
    )
    assert res.status == "done"
    assert res.state == 6
    assert res.checkpoints_reached == 2
    assert res.ledger is not None
    assert "reached checkpoint: reach 3" in res.ledger.facts


def test_checkpoint_chaining_stops_on_first_failure() -> None:
    jev = FakeJev(target=3)
    asked: list[str] = []

    def done_for(subgoal: str):
        asked.append(subgoal)
        if subgoal == "reach 3":
            return lambda n: n == 3
        jev.target = 100  # never reached within max_steps
        return lambda _n: False

    res = checkpoint_search(
        0,
        ["reach 3", "never", "unreached"],
        expand,
        is_done_for=done_for,
        width=1,
        max_steps=2,
        evaluate=jev,
        describe=describe,
    )
    assert res.status == "step_limit"
    assert res.checkpoints_reached == 1
    assert asked == ["reach 3", "never"]
    assert "checkpoint 2" in res.reason


def test_many_candidates_split_into_score_requests_under_limit() -> None:
    jev = FakeJev(target=40)

    def wide(n: int) -> list[tuple[str, int]]:
        return [(f"jump {k} at {n}", n + k) for k in range(-20, 21)]

    ledger = TaskLedger(goal="reach 40 " + "z" * 300)
    for i in range(300):
        ledger.add_dead_end(f"old branch {i} " + "q" * 150)
    res = beam_search(
        0,
        wide,
        "reach 40",
        is_done=lambda n: n == 40,
        width=3,
        evaluate=jev,
        ledger=ledger,
        margin=0.0,  # this test checks request size, not ties
        describe=lambda n: f"counter is {n} " + "w" * 400,
    )
    assert res.status == "done"
    assert len(jev.requests) > 1
    assert any(q["type"] == "score" for _, qs in jev.requests for q in qs.values())
    for state, questions in jev.requests:
        assert jev_limits.request_tokens(state, questions)["total"] <= jev_limits.MAX_REQUEST_TOKENS


def test_every_request_under_limit_on_choice_path() -> None:
    jev = FakeJev(target=8)
    ledger = TaskLedger(goal="g", facts=["f" * 500] * 50)
    res = beam_search(
        0, expand, "reach 8", is_done=lambda n: n == 8, width=1, evaluate=jev, ledger=ledger, describe=describe
    )
    assert res.status == "done"
    assert jev.requests
    for state, questions in jev.requests:
        assert jev_limits.request_tokens(state, questions)["total"] <= jev_limits.MAX_REQUEST_TOKENS


def test_import_does_not_load_transport() -> None:
    code = "import sys, jev_search; sys.exit('jev_transport' in sys.modules)"
    proc = subprocess.run([sys.executable, "-c", code], cwd=SCRIPTS, capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr


# ---------------------------------------------------------------------------
# Trace, replay, and fork-from-call-N
# ---------------------------------------------------------------------------


def test_trace_recorder_saves_calls_in_order(tmp_path: Path) -> None:
    jev = FakeJev(target=6)
    rec = jev_search.TraceRecorder(jev)
    res = beam_search(0, expand, "reach 6", is_done=lambda n: n == 6, width=1, evaluate=rec, describe=describe)
    assert res.status == "done"
    assert len(rec.calls) == res.calls > 0
    trace_path = tmp_path / "trace.json"
    rec.save(trace_path)
    loaded = jev_search.load_trace(trace_path)
    assert loaded == rec.calls


def test_load_trace_rejects_a_file_that_is_not_a_trace(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"not": "a trace"}))
    with pytest.raises(ValueError, match="not a jev_search trace"):
        jev_search.load_trace(bad)


def test_replay_evaluate_reproduces_the_same_path_at_zero_cost(tmp_path: Path) -> None:
    """Record a full search, then replay it: the replay must reach the same
    status and path while never calling the wrapped (recorded) evaluate again."""
    jev = FakeJev(target=6)
    rec = jev_search.TraceRecorder(jev)
    original = beam_search(0, expand, "reach 6", is_done=lambda n: n == 6, width=1, evaluate=rec, describe=describe)
    rec.save(tmp_path / "trace.json")

    calls = jev_search.load_trace(tmp_path / "trace.json")
    replay = jev_search.ReplayEvaluate(calls)
    replayed = beam_search(0, expand, "reach 6", is_done=lambda n: n == 6, width=1, evaluate=replay, describe=describe)

    assert (replayed.status, replayed.path, replayed.state) == (original.status, original.path, original.state)
    assert replay.calls_made == len(calls)  # every recorded call was consumed, none skipped


def test_replay_evaluate_raises_on_a_diverged_request() -> None:
    jev = FakeJev(target=6)
    rec = jev_search.TraceRecorder(jev)
    beam_search(0, expand, "reach 6", is_done=lambda n: n == 6, width=1, evaluate=rec, describe=describe)
    replay = jev_search.ReplayEvaluate(rec.calls)
    recorded_state, recorded_questions = rec.calls[0]["state"], rec.calls[0]["questions"]
    replay(recorded_state, recorded_questions, timeout=1.0)  # consume call 1 to line up with call 2's divergence
    with pytest.raises(jev_search.TraceMismatch, match="call 2 diverged"):
        replay({"different": True}, recorded_questions, timeout=1.0)


def test_replay_evaluate_non_strict_ignores_a_diverged_request() -> None:
    jev = FakeJev(target=6)
    rec = jev_search.TraceRecorder(jev)
    beam_search(0, expand, "reach 6", is_done=lambda n: n == 6, width=1, evaluate=rec, describe=describe)
    replay = jev_search.ReplayEvaluate(rec.calls, strict=False)
    out = replay({"different": True}, {"different": True}, timeout=1.0)
    assert out == rec.calls[0]["response"]


def test_replay_evaluate_exhausted_past_the_last_recorded_call() -> None:
    jev = FakeJev(target=6)
    rec = jev_search.TraceRecorder(jev)
    beam_search(0, expand, "reach 6", is_done=lambda n: n == 6, width=1, evaluate=rec, describe=describe)
    replay = jev_search.ReplayEvaluate(rec.calls, strict=False)
    for call in rec.calls:
        replay(call["state"], call["questions"], timeout=1.0)
    with pytest.raises(jev_search.TraceExhausted, match=f"only {len(rec.calls)} recorded"):
        replay({}, {}, timeout=1.0)


def test_fork_evaluate_rejects_a_negative_fork_at() -> None:
    with pytest.raises(ValueError, match="fork_at must be >= 0"):
        jev_search.fork_evaluate([], -1, lambda *_a, **_kw: {})


def test_fork_evaluate_replays_then_resumes_live_calls() -> None:
    """Record a 2-call search, then fork at call 1: call 1 must come from the
    trace (the original FakeJev is never touched again) and call 2 must reach
    a fresh, live evaluate, landing on the same answer."""
    recorded_jev = FakeJev(target=6)
    rec = jev_search.TraceRecorder(recorded_jev)
    original = beam_search(0, expand, "reach 6", is_done=lambda n: n == 6, width=1, evaluate=rec, describe=describe)
    assert len(rec.calls) == 2  # fixture of this test: exactly one call to fork after

    live_jev = FakeJev(target=6)
    fork = jev_search.fork_evaluate(rec.calls, 1, live_jev)
    forked = beam_search(0, expand, "reach 6", is_done=lambda n: n == 6, width=1, evaluate=fork, describe=describe)

    assert (forked.status, forked.path, forked.state) == (original.status, original.path, original.state)
    assert len(live_jev.requests) == 1  # only the call past fork_at reached the live evaluate


def test_fork_evaluate_at_zero_never_touches_the_recording() -> None:
    """fork_at=0 is a pure live run: the replay side must never be consulted,
    so a trace with a mismatched (even malformed) call 1 is never read."""
    bad_calls = [{"state": {"wrong": True}, "questions": {}, "response": {}}]
    live_jev = FakeJev(target=6)
    fork = jev_search.fork_evaluate(bad_calls, 0, live_jev)
    res = beam_search(0, expand, "reach 6", is_done=lambda n: n == 6, width=1, evaluate=fork, describe=describe)
    assert res.status == "done"
    assert len(live_jev.requests) == 2
