"""Regression tests for the registered-hook smoke harness fixtures."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "smoke-test-hooks.py"


def _load_smoke_module():
    spec = importlib.util.spec_from_file_location("smoke_test_hooks", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("hook_name", ["posttool-rename-sweep.py"])
def test_posttool_fixture_does_not_create_caught_hook_errors(
    hook_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    smoke = _load_smoke_module()
    error_log = tmp_path / "hook-errors.jsonl"
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(error_log))
    payload = dict(smoke.MOCK_INPUTS["PostToolUse"])
    if hook_name == "posttool-rename-sweep.py":
        payload["tool_name"] = "Bash"
        payload["tool_input"] = {"command": "printf runtime-probe"}
    monkeypatch.setitem(smoke.MOCK_INPUTS, "PostToolUse", payload)

    result = smoke.run_hook(
        {
            "script": ROOT / "hooks" / hook_name,
            "event": "PostToolUse",
            "matcher": "Write|Edit",
            "description": "runtime fixture regression",
            "timeout_s": 5,
            "command": f"python3 hooks/{hook_name}",
        }
    )

    assert result["status"] == "PASS", result
    assert not error_log.exists() or not error_log.read_text(encoding="utf-8").strip(), result


def _hook(script: Path, timeout_s: float = 5) -> dict:
    return {
        "script": script,
        "event": "PostToolUse",
        "matcher": "Write",
        "description": "",
        "timeout_s": timeout_s,
        "command": "",
    }


def test_a_crashing_hook_fails_instead_of_warning(tmp_path: Path) -> None:
    """Exit 1 is how an uncaught exception ends a hook, and a crashed gate lets the tool call through."""
    smoke = _load_smoke_module()
    crash = tmp_path / "crash.py"
    crash.write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()

    result = smoke.run_hook(_hook(crash), home=home)

    assert result["status"] == "FAIL", result
    assert result["exit_code"] == 1


def test_ci_exits_one_when_a_registered_hook_crashes(tmp_path: Path) -> None:
    trusted = tmp_path / "trusted-hooks"
    trusted.mkdir()
    (trusted / "crash.py").write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    target = tmp_path / "target"
    (target / ".claude").mkdir(parents=True)
    settings = {"hooks": {"PostToolUse": [{"hooks": [{"command": 'python3 "$HOME/.claude/hooks/crash.py"'}]}]}}
    (target / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--ci", "--repo-root", str(target), "--hooks-dir", str(trusted)],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "crash.py" in result.stdout and "FAIL (exit 3)" in result.stdout


def test_registered_timeout_is_read_in_seconds(tmp_path: Path) -> None:
    """Claude Code reads a hook timeout in seconds; the smoke test used to divide it by 1000."""
    smoke = _load_smoke_module()
    slow = tmp_path / "slow.py"
    slow.write_text("import time\ntime.sleep(0.7)\n", encoding="utf-8")
    settings = tmp_path / "settings.json"
    entry = {"command": f'python3 "{slow}"', "timeout": 2}
    settings.write_text(json.dumps({"hooks": {"PostToolUse": [{"hooks": [entry]}]}}), encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()

    hooks = smoke.load_registered_hooks(settings_path=settings)

    assert [h["timeout_s"] for h in hooks] == [2]
    assert smoke.run_hook(hooks[0], home=home)["status"] == "PASS"
