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


_RUNTIME_ENV_KEYS = (
    "JEV_AGENT_MODEL",
    "JEV_AGENT_EFFORT",
    "JEV_AGENT_RUNTIME",
    "VEXJOY_HOOK_RUNTIME",
    "ANTIGRAVITY_AGENT",
    "ANTIGRAVITY_SESSION_ID",
    "AGY_SESSION_ID",
    "ANTIGRAVITY_MODEL",
    "GEMINI_MODEL",
    "ANTIGRAVITY_EFFORT",
    "GEMINI_EFFORT",
    "CODEX_SESSION_ID",
    "CODEX_THREAD_ID",
    "CLAUDE_SESSION_ID",
    "ANTHROPIC_MODEL",
    "CLAUDE_MODEL",
)


def _clear_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _RUNTIME_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_python_310_fallback_reads_codex_agent_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Optional telemetry still works when stdlib tomllib is unavailable."""
    config_dir = tmp_path / ".codex"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        'model = "gpt-test"\nmodel_reasoning_effort = "high"\n',
        encoding="utf-8",
    )
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_SESSION_ID", "session")
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


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 7, -0.5, "0.9", True, None])
def test_non_probability_answer_is_an_error_not_a_clamped_alignment(
    monkeypatch: pytest.MonkeyPatch, bad: object
) -> None:
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-token")
    answers = {key: {"noul": 0.9} for key in align.build_payload("r", "i", _route())["questions"]}
    for key in (
        "intent_is_too_narrow",
        "intent_adds_unrequested_work",
        "route_omits_material_scope",
        "essential_clarification_needed",
    ):
        answers[key] = {"noul": 0.1}
    monkeypatch.setattr(align.jev_transport, "evaluate", lambda *_args, **_kwargs: {"answers": dict(answers)})
    assert align.evaluate_alignment("r", _route(), "i")["alignment"] == "aligned"
    answers["can_proceed_with_proposed_intent"] = {"noul": bad}
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


def test_unavailable_and_error_runs_record_null_booleans_instead_of_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("JEV_TRANSPORT", raising=False)
    recorded: list[dict[str, object]] = []
    monkeypatch.setattr(align, "_record_intent_alignment", lambda **kwargs: recorded.append(kwargs) or True)

    res_unavail = align.evaluate_alignment("fix bug", _route(), "fix bug")
    assert res_unavail["alignment"] == "unavailable"
    assert recorded[-1]["materially_differs"] is None
    assert recorded[-1]["route_mismatch"] is None

    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-token")
    monkeypatch.setattr(align.jev_transport, "evaluate", lambda *_a, **_k: {"answers": {}})
    res_err = align.evaluate_alignment("fix bug", _route(), "fix bug")
    assert res_err["alignment"] == "error"
    assert recorded[-1]["materially_differs"] is None
    assert recorded[-1]["route_mismatch"] is None


def _seed_claude_settings(home: Path) -> None:
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "settings.json").write_text(
        '{"model": "claude-opus-5", "effortLevel": "low"}\n',
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("trigger_env", "trigger_val"),
    [
        ("VEXJOY_HOOK_RUNTIME", "antigravity"),
        ("ANTIGRAVITY_AGENT", "1"),
        ("ANTIGRAVITY_SESSION_ID", "agy-sess-1"),
        ("AGY_SESSION_ID", "agy-sess-2"),
    ],
)
def test_antigravity_profile_detected_even_when_claude_settings_exist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    trigger_env: str,
    trigger_val: str,
) -> None:
    _clear_runtime_env(monkeypatch)
    _seed_claude_settings(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(trigger_env, trigger_val)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-4-argon")
    monkeypatch.setenv("GEMINI_EFFORT", "medium")

    assert align._agent_profile() == ("gemini-4-argon", "medium", "antigravity")

    monkeypatch.setenv("ANTIGRAVITY_MODEL", "gemini-4-argon-high")
    monkeypatch.setenv("ANTIGRAVITY_EFFORT", "high")
    assert align._agent_profile() == ("gemini-4-argon-high", "high", "antigravity")


def test_explicit_jev_agent_env_wins_over_antigravity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clear_runtime_env(monkeypatch)
    _seed_claude_settings(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ANTIGRAVITY_AGENT", "1")
    monkeypatch.setenv("ANTIGRAVITY_MODEL", "gemini-4-argon")
    monkeypatch.setenv("JEV_AGENT_MODEL", "custom-model")
    monkeypatch.setenv("JEV_AGENT_EFFORT", "high")
    monkeypatch.setenv("JEV_AGENT_RUNTIME", "custom")

    assert align._agent_profile() == ("custom-model", "high", "custom")


def test_claude_profile_reads_settings_when_not_antigravity_or_codex(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_runtime_env(monkeypatch)
    _seed_claude_settings(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert align._agent_profile() == ("claude-opus-5", "low", "claude")


def test_codex_profile_reads_config_when_not_antigravity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clear_runtime_env(monkeypatch)
    _seed_claude_settings(tmp_path)
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text(
        'model = "gpt-6-astra"\nmodel_reasoning_effort = "medium"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-1")

    assert align._agent_profile() == ("gpt-6-astra", "medium", "codex")


@pytest.mark.parametrize(
    ("runtime", "effort", "complexity", "file_count", "expected"),
    [
        # claude + medium/complex + low/default/medium effort -> True
        ("claude", None, "medium", 0, True),
        ("claude", "", "complex", 0, True),
        ("claude", "low", "medium", 1, True),
        ("claude", "medium", "complex", 0, True),
        # claude + high/xhigh/max effort -> False regardless of complexity or file_count
        ("claude", "high", "medium", 0, False),
        ("claude", "high", "complex", 5, False),
        ("claude", "xhigh", "complex", 5, False),
        ("claude", "max", "complex", 5, False),
        # claude + trivial/simple with <3 files -> False
        ("claude", "low", "trivial", 0, False),
        ("claude", None, "simple", 2, False),
        # claude + low/default effort + >=3 files -> True even on simple
        ("claude", "low", "simple", 3, True),
        ("claude", None, "simple", 4, True),
        ("claude", "default", "trivial", 3, True),
        ("claude", "medium", "simple", 3, False),
        # non-claude runtimes -> False
        ("codex", "low", "complex", 5, False),
        ("antigravity", "low", "complex", 5, False),
        (None, "low", "complex", 5, False),
    ],
)
def test_should_auto_align_truth_table(
    runtime: str | None,
    effort: str | None,
    complexity: str,
    file_count: int,
    expected: bool,
) -> None:
    assert align.should_auto_align(runtime, effort, complexity, file_count) is expected
