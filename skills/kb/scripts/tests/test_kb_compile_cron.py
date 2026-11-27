"""Regression tests for skills/kb/scripts/kb-compile-cron.sh."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "kb-compile-cron.sh"


def test_script_fixes_repo_dir_and_lockfile_hygiene() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'REPO_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"' in text
    assert 'LOCKFILE="$LOG_DIR/.kb-compile.lock"' in text
    assert 'rm -f "$LOCKFILE"' not in text
    assert "while [[ $# -gt 0 ]]; do" in text


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
@pytest.mark.parametrize("bad_topic", ["../escape", "bad/slash", "bad;cmd", "bad space", "..", "."])
def test_rejects_invalid_topic_names(bad_topic: str) -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--topic", bad_topic],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode != 0
    assert "Invalid topic name" in proc.stderr


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_rejects_missing_topic_value() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--topic"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode != 0
    assert "requires a topic name" in proc.stderr


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_valid_topic_parses_with_while_loop_and_resolves_repo_root(tmp_path: Path) -> None:
    fake_repo = tmp_path / "repo"
    script_copy = fake_repo / "skills" / "kb" / "scripts" / "kb-compile-cron.sh"
    script_copy.parent.mkdir(parents=True)
    shutil.copy2(SCRIPT, script_copy)

    proc = subprocess.run(
        ["bash", str(script_copy), "--topic", "my-valid_topic.1"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 1
    expected_yaml = str(fake_repo / "research" / "my-valid_topic.1" / "kb.yaml")
    assert expected_yaml in proc.stderr
    assert (fake_repo / "cron-logs" / "kb-compile" / ".kb-compile.lock").exists()
