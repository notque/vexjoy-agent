from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "grill-jev.py"
    spec = importlib.util.spec_from_file_location("grill_jev", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_noul_reports_only_the_configured_negative_outcome() -> None:
    grill = _load_module()
    question = {"type": "noul", "report_when": "false"}

    assert not grill._is_high_signal(question, {"noul": 0.9}, 0.7)
    assert grill._is_high_signal(question, {"noul": 0.1}, 0.7)


def test_choice_reports_only_configured_concerning_choices() -> None:
    grill = _load_module()
    question = {"type": "choice", "report_choices": ["high", "critical"]}

    assert not grill._is_high_signal(question, {"choice": "low", "confidence": 0.95}, 0.7)
    assert grill._is_high_signal(question, {"choice": "high", "confidence": 0.95}, 0.7)


def test_load_questions_uses_a_runner_authored_battery(tmp_path: Path) -> None:
    grill = _load_module()
    battery = tmp_path / "questions.json"
    q = {"type": "noul", "report_when": "false", "instructions": {"question": "Are there tests?"}}
    battery.write_text(json.dumps({"questions": {"artifact_has_tests": q}}), encoding="utf-8")

    assert grill._load_questions(str(battery)) == {"artifact_has_tests": q}


def test_load_questions_rejects_score_levels_given_as_a_dict(tmp_path: Path) -> None:
    import pytest

    grill = _load_module()
    battery = tmp_path / "questions.json"
    bad = {"type": "score", "instructions": {"question": "How good?"}, "criteria": {"0": {"summary": "bad"}}}
    battery.write_text(json.dumps({"overall": bad}), encoding="utf-8")
    with pytest.raises(ValueError, match="overall: score criteria must be a list"):
        grill._load_questions(str(battery))


def _noul(text: str) -> dict:
    return {"type": "noul", "report_when": "true", "instructions": {"question": text}}


def test_run_battery_isolates_a_failing_question_and_keeps_the_rest(monkeypatch) -> None:
    grill = _load_module()
    calls: list[list[str]] = []

    def fake(_state, questions, **_kw):
        calls.append(list(questions))
        if "bad" in questions:
            raise grill.jev_transport.JevTransportError("Gateway 400", source="vercel")
        return {"answers": {qid: {"noul": 0.1} for qid in questions}}

    monkeypatch.setattr(grill.jev_transport, "evaluate", fake)
    questions = {"a": _noul("a?"), "bad": _noul("b?"), "c": _noul("c?"), "d": _noul("d?")}
    answers = grill._run_battery({"artifact": "x"}, questions, timeout=1)

    assert {k: v.get("noul") for k, v in answers.items() if "error" not in v} == {"a": 0.1, "c": 0.1, "d": 0.1}
    assert "Gateway 400" in answers["bad"]["error"]
    assert ["probe"] in calls  # a probe told a bad question apart from an outage


def test_run_battery_raises_when_jev_is_down(monkeypatch) -> None:
    import pytest

    grill = _load_module()

    def down(_state, _questions, **_kw):
        raise grill.jev_transport.JevTransportError("Gateway 503", source="vercel")

    monkeypatch.setattr(grill.jev_transport, "evaluate", down)
    with pytest.raises(grill.jev_transport.JevTransportError):
        grill._run_battery({"artifact": "x"}, {"a": _noul("a?"), "b": _noul("b?")}, timeout=1)


def test_report_exits_2_and_lists_unanswered_questions(capsys) -> None:
    grill = _load_module()
    questions = {"a": _noul("a?"), "bad": _noul("b?")}
    answers = {"a": {"noul": 0.1}, "bad": {"type": "noul", "error": "Gateway 400"}}

    assert grill._print_report(answers, questions, "general", 0.7, True) == 2
    assert "UNANSWERED (1; unknown, not a pass)" in capsys.readouterr().out


def test_battery_batches_are_packed_by_tokens_not_count() -> None:
    grill = _load_module()
    state = {"artifact": "a" * 6000}  # ~1.5k tokens, resent with every batch
    questions = {f"risk_{i}": {"type": "noul", "instructions": "q" * 600} for i in range(30)}

    batches = grill._pack_batches(state, questions)

    assert [qid for batch in batches for qid in batch] == list(questions)
    for batch in batches:
        assert len(batch) <= grill.BATCH_SIZE
        assert grill._estimate_tokens(state, {q: questions[q] for q in batch}) <= grill.TARGET_REQUEST_TOKENS


def test_battery_refuses_artifact_too_large_for_one_question() -> None:
    import pytest

    grill = _load_module()
    state = {"artifact": "a" * (grill.TARGET_REQUEST_TOKENS * 4)}
    with pytest.raises(grill.RequestTooLarge):
        grill._pack_batches(state, {"risk_1": {"type": "noul", "instructions": "ok?"}})


def test_run_battery_sends_nothing_when_artifact_too_large(monkeypatch) -> None:
    import pytest

    grill = _load_module()
    sent: list[dict] = []
    monkeypatch.setattr(grill.jev_transport, "evaluate", lambda _s, q, **_kw: sent.append(q) or {"answers": {}})
    state = {"artifact": "a" * (grill.TARGET_REQUEST_TOKENS * 4)}
    with pytest.raises(grill.RequestTooLarge):
        grill._run_battery(state, {"risk_1": {"type": "noul", "instructions": "ok?"}}, timeout=1)
    assert sent == []
