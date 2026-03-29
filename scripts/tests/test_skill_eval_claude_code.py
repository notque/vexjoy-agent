from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_improve_description_uses_claude_code_and_shortens(monkeypatch, tmp_path):
    from scripts.skill_eval import improve_description as mod

    calls: list[list[str]] = []

    def fake_run(cmd, capture_output, text, cwd, env, timeout):
        calls.append(cmd)
        if len(calls) == 1:
            text_out = "<new_description>" + ("a" * 1030) + "</new_description>"
        else:
            text_out = "<new_description>short and valid</new_description>"
        payload = [
            {"type": "assistant", "message": {"content": [{"type": "text", "text": text_out}]}},
            {"type": "result", "result": "raw result"},
        ]
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    description = mod.improve_description(
        skill_name="skill-eval",
        skill_content="# Skill",
        current_description="old",
        eval_results={
            "results": [
                {"query": "improve this skill", "should_trigger": True, "pass": False, "triggers": 0, "runs": 1}
            ],
            "summary": {"passed": 0, "failed": 1, "total": 1},
        },
        history=[],
        model=None,
        log_dir=tmp_path,
        iteration=1,
    )

    assert description == "short and valid"
    assert calls
    assert calls[0][:2] == ["claude", "-p"]
    transcript = json.loads((tmp_path / "improve_iter_1.json").read_text())
    assert transcript["raw_result_text"] == "raw result"
    assert transcript["rewrite_raw_result_text"] == "raw result"
