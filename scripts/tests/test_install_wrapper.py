"""install.sh end to end: a thin wrapper over vexinstall for all five runtimes.

Runs the real checkout's install.sh against a temp HOME. VEXJOY_NO_GIT_HOOKS
and VEXJOY_NO_DEPS keep it off .git/hooks, pip, and npm. Deselected from the
default local run (slow AND integration); CI runs it via ``-m ""``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.slow, pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"
RUNTIMES = ("codex", "factory", "hermes", "reasonix")
TARGETS = ("claude", *RUNTIMES)

if shutil.which("bash") is None:
    pytest.skip("bash not available", allow_module_level=True)


@pytest.fixture
def home(tmp_path: Path) -> Path:
    h = tmp_path / "home"
    for rt in RUNTIMES:
        (h / f".{rt}").mkdir(parents=True)
    return h


def run_install(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith(("VEXINSTALL_", "VEXJOY_"))},
        "HOME": str(home),
        "VEXJOY_NO_GIT_HOOKS": "1",
        "VEXJOY_NO_DEPS": "1",
        "VEXJOY_INSTALL_PROFILE": str(home / "no-profile.yaml"),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "TERM": "dumb",
    }
    return subprocess.run(
        ["bash", str(INSTALL_SH), *args], capture_output=True, text=True, env=env, timeout=600, cwd=home
    )


def ledger(home: Path) -> dict:
    return json.loads((home / ".claude" / "vexjoy" / "ledger.json").read_text())


def tree(root: Path) -> list[tuple[str, str]]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in sorted(dirnames + filenames):
            p = Path(dirpath) / name
            out.append((str(p.relative_to(root)), os.readlink(p) if p.is_symlink() else str(p.lstat().st_size)))
    return sorted(out)


def test_install_all_targets_then_idempotent(home: Path) -> None:
    r = run_install(home)
    assert r.returncode == 0, r.stdout + r.stderr
    targets = {e["target"] for e in ledger(home)["entries"]}
    assert targets == set(TARGETS)
    for t in TARGETS:
        assert (home / f".{t}" / "skills" / "do" / "SKILL.md").is_file(), t
        assert not (home / f".{t}" / "skills" / "meta").exists(), f"{t}: no category dirs"
    assert not (home / ".claude" / "agents").is_symlink()
    assert json.loads((home / ".claude" / "settings.json").read_text())["hooks"]
    hooks = json.loads((home / ".codex" / "hooks.json").read_text())["hooks"]
    assert f"{home}/.codex/hooks/codex-hook-adapter.py" in json.dumps(hooks)
    assert "hooks = true" in (home / ".codex" / "config.toml").read_text()
    factory = json.dumps(json.loads((home / ".factory" / "settings.json").read_text())["hooks"])
    assert "/.factory/hooks/" in factory and "/.claude/hooks/" not in factory
    assert json.loads((home / ".reasonix" / "settings.json").read_text())["hooks"]
    assert oct((home / ".claude").stat().st_mode & 0o777) == "0o700"

    again = run_install(home, "--dry-run")
    assert again.returncode == 0, again.stderr
    for t in TARGETS:
        line = next(ln for ln in again.stdout.splitlines() if ln.startswith(f"{t}: "))
        assert line.startswith(f"{t}: +0 ~0 -0"), line
    assert "would write" not in again.stdout


def test_dry_run_writes_nothing(home: Path) -> None:
    before = tree(home)
    r = run_install(home, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "claude: +" in r.stdout
    assert tree(home) == before


def test_takeover_default_and_opt_out(home: Path) -> None:
    stale = home / ".hermes" / "skills" / "do"
    stale.mkdir(parents=True)
    (stale / "SKILL.md").write_text("---\nname: do\ndescription: stale legacy copy\n---\n")
    kept = run_install(home, "--no-takeover", "--target", "hermes")
    assert kept.returncode == 0, kept.stderr
    assert "stale legacy copy" in (stale / "SKILL.md").read_text()
    taken = run_install(home, "--target", "hermes")
    assert taken.returncode == 0, taken.stderr
    assert "stale legacy copy" not in (stale / "SKILL.md").read_text()


def test_uninstall_then_rollback(home: Path) -> None:
    assert run_install(home, "--copy").returncode == 0
    un = run_install(home, "--uninstall")
    assert un.returncode == 0, un.stderr
    assert not ledger(home)["entries"]
    for t in TARGETS:
        assert not (home / f".{t}" / "skills" / "do").exists(), t
    rb = run_install(home, "--rollback")
    assert rb.returncode == 0, rb.stdout + rb.stderr
    assert "Restoring trash session" in rb.stdout
    assert (home / ".claude" / "skills" / "do" / "SKILL.md").is_file()


def test_deprecated_flags_are_accepted(home: Path) -> None:
    r = run_install(home, "--force", "--no-force", "--per-item", "--sync", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert r.stdout.count("deprecated and ignored") == 4


def test_migrate_overlays_dry_run_and_bad_flags(home: Path) -> None:
    (home / "private-skills").mkdir()
    r = run_install(home, "--migrate-overlays", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "dry-run" in r.stdout and not (home / ".claude" / "vexjoy" / "overlays.json").exists()
    assert run_install(home, "--bogus").returncode == 1
    assert run_install(home, "--help").returncode == 0


def test_home_inside_repo_is_refused_by_the_engine(tmp_path: Path) -> None:
    r = subprocess.run(
        ["bash", str(INSTALL_SH), "--dry-run", "--target", "claude"],
        capture_output=True,
        text=True,
        env={"HOME": str(REPO_ROOT), "PATH": "/usr/local/bin:/usr/bin:/bin", "VEXJOY_NO_DEPS": "1"},
        timeout=120,
        cwd=tmp_path,
    )
    assert r.returncode == 4, r.stdout + r.stderr
    assert "inside" in r.stderr
