"""pyrun.sh on a hook file that is not deployed exits 1, never 2.

Scenario: settings registered pretool-commit-verification-gate.py before the file reached
~/.claude/hooks. pyrun.sh ran ``python3 <missing file>``, python exited 2, and Claude Code
read that PreToolUse exit as a block on every Bash call, the install included.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

PYRUN = Path(__file__).resolve().parents[1] / "lib" / "pyrun.sh"
HOOK = "pretool-commit-verification-gate.py"


def _run(home: Path, hook: Path) -> subprocess.CompletedProcess[str]:
    env = {"HOME": str(home), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    return subprocess.run(
        ["/bin/sh", str(PYRUN), str(hook)], input="{}", capture_output=True, text=True, env=env, timeout=30
    )


def test_missing_hook_file_exits_non_blocking_and_names_the_fix(tmp_path: Path) -> None:
    home = tmp_path / "home"
    state = home / ".claude" / "vexjoy"
    state.mkdir(parents=True)
    clone = tmp_path / "ledger-clone"
    (state / "ledger.json").write_text(json.dumps({"schema": 1, "source_root": str(clone)}, indent=2))
    missing = home / ".claude" / "hooks" / HOOK

    proc = _run(home, missing)

    assert proc.returncode != 2, "exit 2 blocks every PreToolUse call"
    assert proc.returncode == 1
    lines = proc.stderr.strip().splitlines()
    assert len(lines) == 1, proc.stderr
    assert str(missing) in lines[0]
    assert f"git -C '{clone}' pull --ff-only && '{clone}/install.sh'" in lines[0]


def test_missing_hook_file_without_a_ledger_still_exits_1(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    proc = _run(home, home / ".claude" / "hooks" / HOOK)
    assert proc.returncode == 1
    assert "install.sh" in proc.stderr


def test_missing_hook_message_quotes_a_root_with_spaces(tmp_path: Path) -> None:
    home = tmp_path / "home"
    state = home / ".claude" / "vexjoy"
    state.mkdir(parents=True)
    clone = tmp_path / "my clones" / "vexjoy-agent"
    (state / "ledger.json").write_text(json.dumps({"schema": 1, "source_root": str(clone)}, indent=2))
    proc = _run(home, home / ".claude" / "hooks" / HOOK)
    assert proc.returncode == 1
    assert f"git -C '{clone}' pull --ff-only && '{clone}/install.sh'" in proc.stderr


def test_present_hook_file_still_runs(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    hook = tmp_path / "ok.py"
    hook.write_text("import sys\nprint('ran')\nsys.exit(0)\n")
    proc = _run(home, hook)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ran"
