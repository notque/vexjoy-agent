"""Security tests for smoke-test-hooks target inspection."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "smoke-test-hooks.py"


def _sentinel_writer(sentinel: Path, marker: str) -> str:
    """Python source that writes *marker* to *sentinel* when executed."""
    return "import pathlib\npathlib.Path(" + repr(str(sentinel)) + ").write_text(" + repr(marker) + ")\n"


def test_repo_root_mode_maps_target_commands_to_trusted_hook_basenames(tmp_path: Path) -> None:
    target = tmp_path / "target"
    trusted_hooks = tmp_path / "trusted-hooks"
    malicious_sentinel = tmp_path / "malicious-hook-ran"
    trusted_sentinel = tmp_path / "trusted-hook-ran"
    malicious_hook = target / "hooks" / "probe.py"
    malicious_hook.parent.mkdir(parents=True)
    malicious_hook.write_text(
        _sentinel_writer(malicious_sentinel, "owned"),
        encoding="utf-8",
    )
    trusted_hooks.mkdir()
    (trusted_hooks / "probe.py").write_text(
        _sentinel_writer(trusted_sentinel, "trusted"),
        encoding="utf-8",
    )
    settings = target / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(
        json.dumps(
            {
                "hooks": {
                    "PostToolUse": [
                        {
                            "matcher": "Write",
                            "hooks": [
                                {
                                    "command": f'python3 "{malicious_hook}"',
                                    "timeout": 5000,
                                }
                            ],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--ci",
            "--repo-root",
            str(target),
            "--hooks-dir",
            str(trusted_hooks),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert trusted_sentinel.is_file()
    assert not malicious_sentinel.exists()


def test_safe_mode_strips_target_pytest_execution_context(tmp_path: Path) -> None:
    target = tmp_path / "target"
    trusted_root = tmp_path / "trusted"
    trusted_hooks = trusted_root / "hooks"
    trusted_hooks.mkdir(parents=True)
    sentinel = tmp_path / "target-pytest-plugin-ran"
    record = tmp_path / "trusted-hook-context.json"

    (target / "evil_plugin.py").parent.mkdir(parents=True)
    (target / "evil_plugin.py").write_text(
        _sentinel_writer(sentinel, "owned"),
        encoding="utf-8",
    )
    (target / "conftest.py").write_text(
        _sentinel_writer(sentinel, "owned"),
        encoding="utf-8",
    )
    trusted_hook = trusted_hooks / "trusted-test-runner.py"
    trusted_hook.write_text(
        "import json, os, subprocess, sys\n"
        "from pathlib import Path\n"
        "event = json.load(sys.stdin)\n"
        "context = {'cwd': os.getcwd(), 'project': os.environ.get('CLAUDE_PROJECT_DIR'), "
        "'pythonpath': os.environ.get('PYTHONPATH'), 'pythonhome': os.environ.get('PYTHONHOME'), "
        "'pytest_addopts': os.environ.get('PYTEST_ADDOPTS'), 'pytest_plugins': os.environ.get('PYTEST_PLUGINS'), "
        "'event_cwd': event.get('cwd'), 'file_path': event.get('tool_input', {}).get('file_path')}\n"
        f"Path({str(record)!r}).write_text(json.dumps(context))\n"
        "subprocess.run([sys.executable, '-c', "
        '\'import pytest; raise SystemExit(pytest.main(["--collect-only", "-q"]))\'])\n',
        encoding="utf-8",
    )
    target_hook = target / "hooks" / trusted_hook.name
    target_hook.parent.mkdir()
    target_hook.write_text("raise RuntimeError('target hook executed')\n", encoding="utf-8")
    settings = target / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(
        json.dumps(
            {
                "hooks": {
                    "PostToolUse": [
                        {
                            "hooks": [
                                {
                                    "command": f'python3 "{target_hook}"',
                                    "timeout": 5000,
                                }
                            ]
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "HOME": str(target),
        "CLAUDE_PROJECT_DIR": str(target),
        "PYTHONPATH": str(target),
        "PYTHONHOME": sys.base_prefix,
        "PYTEST_ADDOPTS": "-p evil_plugin",
        "PYTEST_PLUGINS": "evil_plugin",
    }

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--ci",
            "--verbose",
            "--repo-root",
            str(target),
            "--hooks-dir",
            str(trusted_hooks),
        ],
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert not sentinel.exists()
    assert record.is_file(), f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    context = json.loads(record.read_text(encoding="utf-8"))
    assert context == {
        "cwd": str(trusted_root),
        "project": str(trusted_root),
        "pythonpath": None,
        "pythonhome": None,
        "pytest_addopts": None,
        "pytest_plugins": None,
        "event_cwd": str(trusted_root),
        "file_path": str(trusted_root / ".vexjoy-smoke-test.py"),
    }


def _record_env_hook(path: Path, record: Path) -> None:
    path.write_text(
        "import json, os\n"
        f"open({str(record)!r}, 'w').write(json.dumps({{'home': os.environ.get('HOME'), "
        "'sync_disabled': os.environ.get('VEXJOY_SYNC_DISABLED'), 'cwd': os.getcwd()}))\n",
        encoding="utf-8",
    )


def _settings(root: Path, hook: str, event: str = "SessionStart") -> None:
    settings = root / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    cmd = f'python3 "$HOME/.claude/hooks/{hook}"'
    settings.write_text(json.dumps({"hooks": {event: [{"hooks": [{"command": cmd, "timeout": 5000}]}]}}))


def test_safe_mode_home_is_never_the_trusted_repo(tmp_path: Path) -> None:
    """Regression: stop-drift-guard passes --hooks-dir <repo>/hooks, so the trusted
    root is the repo. HOME used to be set to it, and the SessionStart sync hook then
    installed a full ~/.claude tree into repo/.claude."""
    repo = tmp_path / "repo"
    record = tmp_path / "record.json"
    (repo / "hooks").mkdir(parents=True)
    _record_env_hook(repo / "hooks" / "probe.py", record)
    _settings(repo, "probe.py")
    before = sorted(p.name for p in (repo / ".claude").iterdir())

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--ci", "--repo-root", str(repo), "--hooks-dir", str(repo / "hooks")],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    seen = json.loads(record.read_text())
    assert seen["cwd"] == str(repo.resolve())
    assert not Path(seen["home"]).resolve().is_relative_to(repo.resolve()), seen
    assert seen["sync_disabled"] == "1"
    assert not Path(seen["home"]).exists(), "the throwaway HOME is removed after the run"
    assert sorted(p.name for p in (repo / ".claude").iterdir()) == before


def test_default_mode_never_uses_the_real_home(tmp_path: Path) -> None:
    smoke_spec = importlib.util.spec_from_file_location("smoke_default", SCRIPT)
    smoke = importlib.util.module_from_spec(smoke_spec)
    assert smoke_spec.loader is not None
    smoke_spec.loader.exec_module(smoke)
    record = tmp_path / "record.json"
    hook = tmp_path / "probe.py"
    _record_env_hook(hook, record)
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    result = smoke.run_hook(
        {"script": hook, "event": "SessionStart", "matcher": "", "description": "", "timeout_ms": 5000, "command": ""},
        home=fake_home,
    )
    assert result["status"] == "PASS", result
    seen = json.loads(record.read_text())
    assert seen["home"] == str(fake_home) and seen["sync_disabled"] == "1"
    assert seen["home"] != str(Path.home())
