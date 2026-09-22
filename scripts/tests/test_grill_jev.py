from __future__ import annotations

import importlib.util
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
    battery.write_text('{"questions":{"artifact_has_tests":{"type":"noul"}}}', encoding="utf-8")

    assert grill._load_questions(str(battery)) == {"artifact_has_tests": {"type": "noul"}}
