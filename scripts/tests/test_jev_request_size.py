"""Request-size guard: too much context is the most common Jev failure via Vercel."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jev_limits
import jev_transport
import jev_vercel

SMALL_Q = {"type": "boolean", "instructions": "ok?"}


def _huge_state() -> dict[str, str]:
    return {"text": "x" * (jev_limits.MAX_REQUEST_TOKENS * 5)}


def test_pack_questions_keeps_every_request_under_target_with_full_state() -> None:
    state = {"text": "y" * 4000}
    questions = {f"q{i}": {"type": "boolean", "instructions": "z" * 1200} for i in range(12)}

    groups = jev_limits.pack_questions(state, questions)

    assert len(groups) > 1
    assert [k for g in groups for k in g] == list(questions)
    assert all(jev_limits.request_tokens(state, g)["total"] <= jev_limits.TARGET_REQUEST_TOKENS for g in groups)


def test_pack_questions_honors_max_questions() -> None:
    groups = jev_limits.pack_questions({}, {f"q{i}": SMALL_Q for i in range(7)}, max_questions=3)
    assert [len(g) for g in groups] == [3, 3, 1]


def test_pack_questions_refuses_state_too_large_for_one_question() -> None:
    with pytest.raises(jev_limits.RequestTooLarge):
        jev_limits.pack_questions(_huge_state(), {"q": SMALL_Q})


def _many_questions(n: int) -> dict[str, dict[str, str]]:
    return {f"q{i}": {"type": "boolean", "instructions": "z" * 1200} for i in range(n)}


def test_vercel_splits_oversized_request_into_as_many_as_it_takes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bridge = tmp_path / "gateway.mjs"
    bridge.write_text("// bridge")
    monkeypatch.setattr(jev_vercel, "_BRIDGE", bridge)
    sent: list[dict] = []

    def fake_one(state, questions, **_kw):
        assert jev_limits.request_tokens(state, questions)["total"] <= jev_limits.TARGET_REQUEST_TOKENS
        sent.append(questions)
        return {"answers": {k: {"noul": 0.7} for k in questions}, "_meta": {"retry": {"attempts": 1, "retries": 0}}}

    monkeypatch.setattr(jev_vercel, "_evaluate_one", fake_one)
    state = {"text": "y" * 4000}
    questions = _many_questions(120)  # ~37k tokens: needs 15+ requests

    result = jev_vercel.evaluate(state, questions, timeout=1)

    assert set(result["answers"]) == set(questions)
    assert len(sent) == result["_meta"]["split"]["requests"] >= 15
    assert result["_meta"]["retry"]["attempts"] == len(sent)


def test_vercel_sends_one_request_when_it_fits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bridge = tmp_path / "gateway.mjs"
    bridge.write_text("// bridge")
    monkeypatch.setattr(jev_vercel, "_BRIDGE", bridge)
    one = Mock(return_value={"answers": {"q": {"noul": 0.5}}})
    monkeypatch.setattr(jev_vercel, "_evaluate_one", one)

    result = jev_vercel.evaluate({"text": "small"}, {"q": SMALL_Q}, timeout=1)

    assert one.call_count == 1
    assert "split" not in result.get("_meta", {})


def test_vercel_refuses_only_a_state_too_large_for_one_question(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bridge = tmp_path / "gateway.mjs"
    bridge.write_text("// bridge")
    monkeypatch.setattr(jev_vercel, "_BRIDGE", bridge)
    run = Mock()
    monkeypatch.setattr(jev_vercel.subprocess, "run", run)
    with pytest.raises(jev_vercel.JevRequestTooLarge):
        jev_vercel.evaluate(_huge_state(), {"q": SMALL_Q}, timeout=1)
    run.assert_not_called()


def test_split_failure_raises_instead_of_partial_answers() -> None:
    calls = {"n": 0}

    def send_one(state, questions):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("gateway down")
        return {"answers": {k: {"noul": 0.5} for k in questions}}

    with pytest.raises(RuntimeError):
        jev_limits.split_and_run({"text": "y" * 4000}, _many_questions(12), send_one)


def test_transport_direct_splits_too(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    monkeypatch.setenv("TYPESAFE_API_KEY", "direct")
    monkeypatch.setenv("JEV_TRANSPORT", "direct")
    sent: list[dict] = []

    def call(payload, *_a, **_kw):
        sent.append(payload["questions"])
        return {"answers": {k: {"noul": 0.6} for k in payload["questions"]}}, 0

    monkeypatch.setattr(jev_transport.jev_router_common, "call_jev", call)
    questions = _many_questions(12)
    result = jev_transport.evaluate({"text": "y" * 4000}, questions, timeout=1)

    assert set(result["answers"]) == set(questions)
    assert len(sent) > 1


def test_transport_refuses_state_too_large_as_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    monkeypatch.setenv("TYPESAFE_API_KEY", "direct")
    monkeypatch.setenv("JEV_TRANSPORT", "direct")
    call = Mock()
    monkeypatch.setattr(jev_transport.jev_router_common, "call_jev", call)
    with pytest.raises(jev_transport.JevTransportError) as error:
        jev_transport.evaluate(_huge_state(), {"q": SMALL_Q}, timeout=1)
    assert error.value.source == jev_transport.REQUEST_TOO_LARGE
    call.assert_not_called()


def test_evaluate_packed_splits_and_merges(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "gateway")
    monkeypatch.setenv("JEV_TRANSPORT", "vercel")
    sent: list[dict] = []

    def fake(state, questions, *, timeout, max_request_tokens):
        return jev_limits.split_and_run(
            state,
            questions,
            lambda _s, q: sent.append(q) or {"answers": {k: {"noul": 0.8} for k in q}},
            limit=max_request_tokens,
        )

    monkeypatch.setattr(jev_transport.jev_vercel, "evaluate", fake)
    questions = _many_questions(12)

    result = jev_transport.evaluate_packed({"text": "y" * 4000}, questions, timeout=1)

    assert set(result["answers"]) == set(questions)
    assert len(sent) == result["_meta"]["split"]["requests"] > 1


def test_default_attempts_cover_rate_limit_retries() -> None:
    assert jev_vercel.DEFAULT_MAX_ATTEMPTS >= 4
    assert {429, 503, 529} <= jev_vercel.TRANSIENT_STATUSES
