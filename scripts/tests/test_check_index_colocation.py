#!/usr/bin/env python3
"""
Tests for scripts/check-index-colocation.py (WARN-ONLY metadata-consistency check).

ADR: agents-index-autosync (Part 2). The check flags when a diff changes an
agent's (or skill's) routing-relevant frontmatter but the regenerated INDEX
entry would differ and was not refreshed alongside it. Default exit is ALWAYS 0;
--strict makes findings exit 1 (escalation flag, wired into no gate).

Run with: python3 -m pytest scripts/tests/test_check_index_colocation.py -v
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "check-index-colocation.py"


# ---------------------------------------------------------------------------
# Git fixture: a throwaway repo with the real generators + an agent file.
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )


def _agent_md(triggers: list[str], description: str = "Test agent.") -> str:
    trig_lines = "\n".join(f"    - {t}" for t in triggers)
    return (
        "---\n"
        "name: demo-agent\n"
        f'description: "{description}"\n'
        "routing:\n"
        "  triggers:\n"
        f"{trig_lines}\n"
        "  complexity: Medium\n"
        "  category: meta\n"
        "---\n\n"
        "Body text for the demo agent.\n"
    )


def _make_repo(tmp_path: Path) -> Path:
    """Build a minimal git repo: scripts/generate-agent-index.py + one agent file."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "lib").mkdir()
    (repo / "agents").mkdir()

    # Copy the real agent index generator so the check can regenerate.
    real_gen = SCRIPT.parent / "generate-agent-index.py"
    (repo / "scripts" / "generate-agent-index.py").write_text(real_gen.read_text(encoding="utf-8"), encoding="utf-8")
    (repo / "scripts" / "check-index-colocation.py").write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")

    # generate-agent-index.py imports the shared frontmatter parser; copy it
    # (and the package marker) so the isolated fixture repo can resolve it.
    lib_dir = SCRIPT.parent / "lib"
    for lib_file in ("__init__.py", "frontmatter.py"):
        (repo / "scripts" / "lib" / lib_file).write_text(
            (lib_dir / lib_file).read_text(encoding="utf-8"), encoding="utf-8"
        )

    (repo / "agents" / "demo-agent.md").write_text(_agent_md(["alpha", "beta"]), encoding="utf-8")

    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/check-index-colocation.py", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=60,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_warn_on_routing_change_without_index_delta(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    # Change triggers in the working tree (INDEX not regenerated/committed).
    (repo / "agents" / "demo-agent.md").write_text(_agent_md(["alpha", "beta", "gamma"]), encoding="utf-8")
    proc = _run(repo)  # working-tree diff vs HEAD
    assert proc.returncode == 0
    assert "WARN" in proc.stdout
    assert "demo-agent" in proc.stdout


def test_silent_on_body_only_edit(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    md = (repo / "agents" / "demo-agent.md").read_text(encoding="utf-8")
    (repo / "agents" / "demo-agent.md").write_text(md + "\nMore body, no routing change.\n", encoding="utf-8")
    proc = _run(repo)
    assert proc.returncode == 0
    assert "WARN" not in proc.stdout


def test_strict_exits_1_on_findings(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "agents" / "demo-agent.md").write_text(_agent_md(["alpha", "beta", "gamma"]), encoding="utf-8")
    proc = _run(repo, "--strict")
    assert proc.returncode == 1  # escalation flag proven
    # Same fixture without --strict exits 0.
    proc0 = _run(repo)
    assert proc0.returncode == 0


def test_json_shape(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "agents" / "demo-agent.md").write_text(_agent_md(["alpha", "beta", "gamma"]), encoding="utf-8")
    proc = _run(repo, "--json")
    assert proc.returncode == 0
    findings = json.loads(proc.stdout)
    assert isinstance(findings, list)
    assert len(findings) == 1
    f = findings[0]
    for key in ("component", "file", "changed_fields", "index_entry_changed"):
        assert key in f
    assert f["component"] == "agents"
    assert "routing.triggers" in f["changed_fields"]


def test_no_changes_exits_zero(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    proc = _run(repo)
    assert proc.returncode == 0
    assert "WARN" not in proc.stdout
