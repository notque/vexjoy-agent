"""Tests for the two scoped alt-model modes added to `jev_transport.py` (owner, 2026-10-30).

Mode 1, `evaluate_with_fallback`: Jev first, the named alt model only on
`JevTransportError`, result tagged `is_jev`. Mode 2, `evaluate_second_opinion`:
both answers side by side, never merged. Neither mode is a generic
provider-plugin architecture -- both call the single hardcoded
`jev_alt_model.answer`, never a registry or discovered provider.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import jev_alt_model
import jev_transport

STATE = {"request": "test"}
QUESTIONS = {"ok": {"type": "noul", "instructions": "Is this a test?"}}
JEV_ANSWER = {"answers": {"ok": {"type": "noul", "noul": 0.9}}, "_meta": {"transport": "vercel-ai-gateway"}}
ALT_ANSWER = {
    "answers": {"ok": {"type": "noul", "noul": 0.2}},
    "model": "claude-sonnet-4-6",
    "_meta": {"is_jev": False, "source": "alt-model", "backend": "claude-cli"},
}


def _fails(*_args, **_kwargs):
    raise jev_transport.JevTransportError("boom", source="unavailable")


def _returns_alt(*_args, **_kwargs):
    return dict(ALT_ANSWER, _meta=dict(ALT_ANSWER["_meta"]))


def _alt_fails(*_args, **_kwargs):
    raise jev_alt_model.AltModelError("claude-cli-missing")


# ---------------------------------------------------------------------------
# evaluate_with_fallback
# ---------------------------------------------------------------------------


def test_fallback_uses_jev_when_it_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        jev_transport, "evaluate_packed", lambda *_a, **_k: dict(JEV_ANSWER, _meta=dict(JEV_ANSWER["_meta"]))
    )
    called = []
    monkeypatch.setattr(jev_transport.jev_alt_model, "answer", lambda *_a, **_k: called.append(1) or ALT_ANSWER)

    result = jev_transport.evaluate_with_fallback(STATE, QUESTIONS, timeout=5)
    assert result["answers"] == JEV_ANSWER["answers"]
    assert result["_meta"]["is_jev"] is True
    assert called == []  # the alt model is never called when Jev succeeds


def test_fallback_calls_alt_model_only_after_jev_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_transport, "evaluate_packed", _fails)
    seen = {}

    def fake_alt(state, questions, *, timeout):
        seen.update(state=state, questions=questions, timeout=timeout)
        return _returns_alt()

    monkeypatch.setattr(jev_transport.jev_alt_model, "answer", fake_alt)

    result = jev_transport.evaluate_with_fallback(STATE, QUESTIONS, timeout=5)
    assert seen["state"] == STATE
    assert seen["questions"] == QUESTIONS
    assert result["answers"] == ALT_ANSWER["answers"]
    assert result["_meta"]["is_jev"] is False
    assert "unavailable" in result["_meta"]["fallback_reason"]


def test_fallback_raises_when_both_jev_and_alt_model_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_transport, "evaluate_packed", _fails)
    monkeypatch.setattr(jev_transport.jev_alt_model, "answer", _alt_fails)

    with pytest.raises(jev_transport.JevTransportError) as exc_info:
        jev_transport.evaluate_with_fallback(STATE, QUESTIONS, timeout=5)
    assert exc_info.value.source == jev_transport.FALLBACK_FAILED
    assert "claude-cli-missing" in str(exc_info.value)


def test_fallback_refuses_images_without_calling_alt_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_transport, "evaluate_packed", _fails)
    called = []
    monkeypatch.setattr(jev_transport.jev_alt_model, "answer", lambda *_a, **_k: called.append(1))
    monkeypatch.setattr(jev_transport.jev_images, "contains_images", lambda *_a, **_k: True)

    with pytest.raises(jev_transport.JevTransportError) as exc_info:
        jev_transport.evaluate_with_fallback(STATE, QUESTIONS, timeout=5)
    assert exc_info.value.source == jev_transport.IMAGES_UNSUPPORTED
    assert called == []


# ---------------------------------------------------------------------------
# evaluate_second_opinion
# ---------------------------------------------------------------------------


def test_second_opinion_returns_both_answers_unmerged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        jev_transport, "evaluate_packed", lambda *_a, **_k: dict(JEV_ANSWER, _meta=dict(JEV_ANSWER["_meta"]))
    )
    monkeypatch.setattr(jev_transport.jev_alt_model, "answer", lambda *_a, **_k: _returns_alt())

    result = jev_transport.evaluate_second_opinion(STATE, QUESTIONS, timeout=5)
    assert result["_meta"] == {"mode": "second_opinion"}
    assert result["jev"]["answers"]["ok"]["noul"] == 0.9
    assert result["alt_model"]["answers"]["ok"]["noul"] == 0.2
    assert result["jev"]["_meta"]["is_jev"] is True
    assert result["alt_model"]["_meta"]["is_jev"] is False
    # Never averaged or merged into one number.
    assert result["jev"]["answers"]["ok"]["noul"] != result["alt_model"]["answers"]["ok"]["noul"]


def test_second_opinion_reports_jev_failure_but_keeps_alt_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_transport, "evaluate_packed", _fails)
    monkeypatch.setattr(jev_transport.jev_alt_model, "answer", lambda *_a, **_k: _returns_alt())

    result = jev_transport.evaluate_second_opinion(STATE, QUESTIONS, timeout=5)
    assert result["jev"]["source"] == "unavailable"
    assert "boom" in result["jev"]["error"]
    assert result["alt_model"]["answers"]["ok"]["noul"] == 0.2


def test_second_opinion_reports_alt_failure_but_keeps_jev_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        jev_transport, "evaluate_packed", lambda *_a, **_k: dict(JEV_ANSWER, _meta=dict(JEV_ANSWER["_meta"]))
    )
    monkeypatch.setattr(jev_transport.jev_alt_model, "answer", _alt_fails)

    result = jev_transport.evaluate_second_opinion(STATE, QUESTIONS, timeout=5)
    assert result["jev"]["answers"]["ok"]["noul"] == 0.9
    assert result["alt_model"]["source"] == jev_alt_model.SOURCE
    assert "claude-cli-missing" in result["alt_model"]["error"]


def test_second_opinion_refuses_images_before_calling_either(monkeypatch: pytest.MonkeyPatch) -> None:
    jev_called = []
    alt_called = []
    monkeypatch.setattr(jev_transport, "evaluate_packed", lambda *_a, **_k: jev_called.append(1))
    monkeypatch.setattr(jev_transport.jev_alt_model, "answer", lambda *_a, **_k: alt_called.append(1))
    monkeypatch.setattr(jev_transport.jev_images, "contains_images", lambda *_a, **_k: True)

    with pytest.raises(jev_transport.JevTransportError) as exc_info:
        jev_transport.evaluate_second_opinion(STATE, QUESTIONS, timeout=5)
    assert exc_info.value.source == jev_transport.IMAGES_UNSUPPORTED
    assert jev_called == [] and alt_called == []
