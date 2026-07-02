"""Runtime mirror gating tests for install.sh.

install.sh syncs an optional runtime mirror (codex, factory, hermes,
reasonix) only when the runtime's command is on PATH or its home dir
already exists. A clean HOME gains no runtime dirs for absent runtimes;
a pre-existing runtime dir keeps syncing even without the command.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"

RUNTIMES = ("codex", "factory", "hermes", "reasonix")

if shutil.which("bash") is None:
    pytest.skip("bash not available on this platform", allow_module_level=True)


def _run_install(fake_home: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(fake_home), "TERM": "dumb"}
    return subprocess.run(
        ["bash", str(INSTALL_SH), "--copy", "--force"],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    return home


def test_clean_home_skips_absent_runtimes(fake_home: Path) -> None:
    """No runtime dir is created for a runtime with no command and no dir."""
    absent = [r for r in RUNTIMES if shutil.which(r) is None]
    if not absent:
        pytest.skip("every runtime command is on PATH; nothing to verify")

    result = _run_install(fake_home)
    assert result.returncode == 0, result.stderr[-2000:]

    for runtime in absent:
        runtime_dir = fake_home / f".{runtime}"
        assert not runtime_dir.exists(), (
            f"~/.{runtime} was created although the {runtime} command is absent.\nSTDOUT:\n{result.stdout[-2000:]}"
        )


def test_existing_dir_syncs_without_command(fake_home: Path) -> None:
    """A pre-existing runtime dir keeps syncing even without the command."""
    candidates = [r for r in RUNTIMES if shutil.which(r) is None]
    if not candidates:
        pytest.skip("every runtime command is on PATH; nothing to verify")

    runtime = candidates[0]
    runtime_dir = fake_home / f".{runtime}"
    runtime_dir.mkdir()

    result = _run_install(fake_home)
    assert result.returncode == 0, result.stderr[-2000:]

    skills_dir = runtime_dir / "skills"
    assert skills_dir.exists() and any(skills_dir.iterdir()), (
        f"pre-existing ~/.{runtime} was not synced (skills missing/empty).\nSTDOUT:\n{result.stdout[-2000:]}"
    )
