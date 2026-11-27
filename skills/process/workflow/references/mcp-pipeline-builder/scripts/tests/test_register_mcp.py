"""Regression tests for register_mcp.py secret redaction."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "register_mcp.py"


def _run_in(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_dry_run_redacts_env_values_on_stdout(tmp_path: Path) -> None:
    sample_val = "example-value-99887766"
    proc = _run_in(
        tmp_path,
        "--name",
        "demo-mcp",
        "--command",
        "python3",
        "--args",
        "server.py",
        "--env",
        f"SERVICE_TOKEN={sample_val}",
        "--dry-run",
        "--project",
    )
    assert proc.returncode == 0, proc.stderr
    assert sample_val not in proc.stdout
    assert sample_val not in proc.stderr
    assert '"SERVICE_TOKEN": "<REDACTED>"' in proc.stdout


def test_register_writes_env_to_disk_but_redacts_stdout_and_collision_stderr(tmp_path: Path) -> None:
    val_a = "example-first-1122"
    val_b = "example-second-3344"

    first = _run_in(
        tmp_path,
        "--name",
        "demo-mcp",
        "--command",
        "python3",
        "--args",
        "server.py",
        "--env",
        f"API_KEY={val_a}",
        "--project",
    )
    assert first.returncode == 0, first.stderr
    assert val_a not in first.stdout
    assert val_a not in first.stderr
    assert "<REDACTED>" in first.stdout

    cfg = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert cfg["mcpServers"]["demo-mcp"]["env"]["API_KEY"] == val_a

    collision = _run_in(
        tmp_path,
        "--name",
        "demo-mcp",
        "--command",
        "python3",
        "--args",
        "server.py",
        "--env",
        f"API_KEY={val_b}",
        "--project",
    )
    assert collision.returncode == 1
    assert val_a not in collision.stderr
    assert val_b not in collision.stderr
    assert "<REDACTED>" in collision.stderr


def test_malformed_env_does_not_echo_value(tmp_path: Path) -> None:
    leaked = "example-malformed-5566"
    for bad in (f"={leaked}", leaked):
        proc = _run_in(
            tmp_path,
            "--name",
            "demo-mcp",
            "--command",
            "python3",
            "--env",
            bad,
            "--dry-run",
            "--project",
        )
        assert proc.returncode == 1
        assert leaked not in proc.stderr
        assert leaked not in proc.stdout
