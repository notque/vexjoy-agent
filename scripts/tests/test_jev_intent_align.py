from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import jev_intent_align as align


@pytest.fixture(autouse=True)
def _disable_real_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(align, "_record_intent_alignment", None)


def _route() -> dict:
    return {
        "agent": "frontend",
        "skill": "testing",
        "pipeline": None,
        "complexity": "medium",
        "source": "jev",
        "reasoning": "fit",
    }


def test_payload_batches_all_independent_questions() -> None:
    payload = align.build_payload("Fix the audit", "Fix the audit without changing scope.", _route())
    assert payload["state"]["user_request"] == "Fix the audit"
    assert len(payload["questions"]) == 9
    assert all(question["type"] == "noul" for question in payload["questions"].values())
    assert "selected_route" in payload["state"]
    assert all(isinstance(question["instructions"], dict) for question in payload["questions"].values())


def test_default_intent_preserves_verbatim_request() -> None:
    request = "  Audit every GM-mode surface; do not fix product UI yet.  "
    assert request in align.proposed_intent(request, _route())
    assert align.build_payload(request, " intent ", _route())["state"]["user_request"] == request


def test_python_310_fallback_reads_codex_agent_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Optional telemetry still works when stdlib tomllib is unavailable."""
    config_dir = tmp_path / ".codex"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        'model = "gpt-test"\nmodel_reasoning_effort = "high"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_SESSION_ID", "session")
    monkeypatch.delenv("JEV_AGENT_MODEL", raising=False)
    monkeypatch.delenv("JEV_AGENT_EFFORT", raising=False)
    monkeypatch.delenv("JEV_AGENT_RUNTIME", raising=False)
    monkeypatch.setattr(align, "tomllib", None)

    assert align._agent_profile() == ("gpt-test", "high", "codex")


def test_alignment_reports_scope_loss(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-token")
    answers = {key: {"noul": 0.9} for key in align.build_payload("r", "i", _route())["questions"]}
    answers["intent_is_too_narrow"] = {"noul": 0.95}
    monkeypatch.setattr(
        align.jev_transport,
        "evaluate",
        lambda *_args, **_kwargs: {"answers": answers, "_meta": {"retry": {"attempts": 1}}},
    )
    result = align.evaluate_alignment("r", _route(), "i")
    assert result["alignment"] == "review"
    assert result["aligned"] is False
    assert "proposed intent drops material scope" in result["issues"]


def test_alignment_requires_clarification_only_when_jev_says_essential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-token")
    answers = {key: {"noul": 0.9} for key in align.build_payload("r", "i", _route())["questions"]}
    answers.update(
        {
            "intent_is_too_narrow": {"noul": 0.1},
            "intent_adds_unrequested_work": {"noul": 0.1},
            "route_omits_material_scope": {"noul": 0.1},
            "essential_clarification_needed": {"noul": 0.95},
        }
    )
    monkeypatch.setattr(align.jev_transport, "evaluate", lambda *_args, **_kwargs: {"answers": answers})
    result = align.evaluate_alignment("r", _route(), "i")
    assert result["clarification_needed"] is True
    assert result["alignment"] == "review"


def test_alignment_surfaces_core_route_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-token")
    answers = {key: {"noul": 0.9} for key in align.build_payload("r", "i", _route())["questions"]}
    answers.update(
        {
            "route_supports_requested_outcome": {"noul": 0.1},
            "intent_is_too_narrow": {"noul": 0.1},
            "intent_adds_unrequested_work": {"noul": 0.1},
            "route_omits_material_scope": {"noul": 0.1},
            "essential_clarification_needed": {"noul": 0.1},
        }
    )
    monkeypatch.setattr(align.jev_transport, "evaluate", lambda *_args, **_kwargs: {"answers": answers})
    result = align.evaluate_alignment("r", _route(), "i")
    assert result["alignment"] == "review"
    assert "selected route conflicts with the requested outcome" in result["issues"]


def test_incomplete_answers_fail_open_instead_of_false_alignment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-token")
    monkeypatch.setattr(align.jev_transport, "evaluate", lambda *_args, **_kwargs: {"answers": {}})
    result = align.evaluate_alignment("r", _route(), "i")
    assert result["alignment"] == "error"
    assert result["aligned"] is False


def test_unavailable_gateway_is_a_receipt_not_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("JEV_TRANSPORT", raising=False)
    result = align.evaluate_alignment("fix it", _route(), None)
    assert result["alignment"] == "unavailable"
    assert result["available"] is False


@pytest.mark.parametrize("mode", ["unavailable", "oversized", "transport_error", "incomplete"])
def test_all_failure_receipts_have_uniform_schema(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    if mode == "unavailable":
        monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
        result = align.evaluate_alignment("r", _route(), "i")
    elif mode == "oversized":
        monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-token")
        result = align.evaluate_alignment("r" * (align.MAX_ALIGNMENT_STATE_CHARS + 1), _route(), "i")
    elif mode == "transport_error":
        monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-token")
        monkeypatch.setattr(
            align.jev_transport,
            "evaluate",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                align.jev_transport.JevTransportError("boom", source=align.jev_transport.VERCEL)
            ),
        )
        result = align.evaluate_alignment("r", _route(), "i")
    else:
        monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-token")
        monkeypatch.setattr(align.jev_transport, "evaluate", lambda *_args, **_kwargs: {"answers": {}})
        result = align.evaluate_alignment("r", _route(), "i")

    assert set(result) >= {
        "available",
        "source",
        "model",
        "proposed_intent",
        "alignment",
        "aligned",
        "clarification_needed",
        "issues",
        "scores",
        "questions_version",
        "latency_ms",
        "usage",
        "transport_retry",
        "reason",
    }
    assert result["aligned"] is False
    assert isinstance(result["issues"], list)
    assert isinstance(result["scores"], dict)


def test_proposed_alignment_records_model_and_material_difference(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-token")
    monkeypatch.setenv("JEV_AGENT_MODEL", "claude-opus-5")
    monkeypatch.setenv("JEV_AGENT_EFFORT", "high")
    monkeypatch.setenv("JEV_AGENT_RUNTIME", "claude")
    answers = {key: {"noul": 0.9} for key in align.build_payload("r", "i", _route())["questions"]}
    answers.update(
        {
            "intent_is_too_narrow": {"noul": 0.95},
            "intent_adds_unrequested_work": {"noul": 0.1},
            "route_omits_material_scope": {"noul": 0.1},
            "essential_clarification_needed": {"noul": 0.1},
        }
    )
    monkeypatch.setattr(
        align.jev_transport,
        "evaluate",
        lambda *_args, **_kwargs: {"model": "typesafe-ai/jev-1.13", "answers": answers},
    )
    recorded: dict[str, object] = {}
    monkeypatch.setattr(align, "_record_intent_alignment", lambda **kwargs: recorded.update(kwargs) or True)
    result = align.evaluate_alignment("r", _route(), "i")
    assert result["model"] == "typesafe-ai/jev-1.13"
    assert recorded["phase"] == "proposed"
    assert recorded["model"] == "typesafe-ai/jev-1.13"
    assert recorded["agent_model"] == "claude-opus-5"
    assert recorded["agent_effort"] == "high"
    assert recorded["agent_runtime"] == "claude"
    assert recorded["materially_differs"] is True
    assert recorded["route_mismatch"] is False
    assert "request_hash" in recorded and "proposed_intent_hash" in recorded


def test_unrequested_work_is_corrected_without_false_clarification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-token")
    answers = {key: {"noul": 0.9} for key in align.build_payload("r", "i", _route())["questions"]}
    answers.update(
        {
            "intent_preserves_requested_outcome": {"noul": 0.09},
            "intent_preserves_explicit_constraints": {"noul": 0.08},
            "intent_adds_unrequested_work": {"noul": 0.97},
            "intent_is_too_narrow": {"noul": 0.1},
            "route_omits_material_scope": {"noul": 0.1},
            "essential_clarification_needed": {"noul": 0.81},
            "can_proceed_with_proposed_intent": {"noul": 0.25},
        }
    )
    monkeypatch.setattr(align.jev_transport, "evaluate", lambda *_args, **_kwargs: {"answers": answers})

    result = align.evaluate_alignment("Update README.", _route(), "Update README and deploy production.")

    assert result["alignment"] == "review"
    assert result["clarification_needed"] is False
    assert "proposed intent adds unrequested work" in result["issues"]
    assert "essential clarification is needed" not in result["issues"]
