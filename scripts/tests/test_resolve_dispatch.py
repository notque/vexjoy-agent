"""Tests for scripts/resolve-dispatch.py.

Covers:
- Valid agent and valid skill exit 0 with no stderr.
- Invalid agent with close match exits 2 with a "closest matches" message.
- Invalid skill with no close match exits 2 and still reports.
- Both arguments empty exits 2 with an explanatory stderr line.
- Repo-local ``.claude/agents/<name>.md`` overrides a missing toolkit entry.
- Repo-local ``.claude/skills/<name>/SKILL.md`` overrides a missing toolkit entry.
- Levenshtein ranking returns the expected close matches.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the hyphen-named module via importlib
# ---------------------------------------------------------------------------

_SCRIPT_PATH = Path(__file__).parent.parent / "resolve-dispatch.py"
_spec = importlib.util.spec_from_file_location("resolve_dispatch", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
sys.modules["resolve_dispatch"] = _mod

levenshtein = _mod.levenshtein
closest_matches = _mod.closest_matches


# ---------------------------------------------------------------------------
# Fixtures: build a fake ~/.toolkit tree so tests never touch real files
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_toolkit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a fake ~/.toolkit with INDEX.json and skills glob targets.

    Contains three agents (golang-general-engineer, python-general-engineer,
    code-reviewer) and three skills (go-patterns, pr-workflow, systematic-debugging).
    """
    toolkit = tmp_path / "toolkit"
    agents_dir = toolkit / "agents"
    skills_dir = toolkit / "skills"
    agents_dir.mkdir(parents=True)
    skills_dir.mkdir(parents=True)

    # Agent markdown files.
    for name in ("golang-general-engineer", "python-general-engineer", "code-reviewer"):
        (agents_dir / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")

    # INDEX.json recording the canonical agent set.
    index_payload = {
        "version": "1.0",
        "agents": {
            "golang-general-engineer": {
                "file": "agents/golang-general-engineer.md",
                "short_description": "Go",
                "triggers": ["go", "golang"],
            },
            "python-general-engineer": {
                "file": "agents/python-general-engineer.md",
                "short_description": "Python",
                "triggers": ["python"],
            },
            "code-reviewer": {
                "file": "agents/code-reviewer.md",
                "short_description": "Review",
                "triggers": ["review"],
            },
        },
    }
    (agents_dir / "INDEX.json").write_text(json.dumps(index_payload), encoding="utf-8")

    # Skill directories, each with a SKILL.md.
    for skill_name in ("go-patterns", "pr-workflow", "systematic-debugging"):
        sdir = skills_dir / skill_name
        sdir.mkdir()
        (sdir / "SKILL.md").write_text(f"# {skill_name}\n", encoding="utf-8")

    # Redirect Path.home() at the module level so the resolver reads our fake tree.
    monkeypatch.setattr(_mod, "TOOLKIT_DIR", toolkit)
    monkeypatch.setattr(_mod, "AGENTS_DIR", toolkit / "agents")
    monkeypatch.setattr(_mod, "SKILLS_DIR", toolkit / "skills")
    monkeypatch.setattr(_mod, "AGENTS_INDEX", toolkit / "agents" / "INDEX.json")

    return toolkit


@pytest.fixture
def isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Change into a scratch directory so repo-local .claude/* lookups start empty."""
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


# ---------------------------------------------------------------------------
# levenshtein + closest_matches
# ---------------------------------------------------------------------------


def test_levenshtein_identical_is_zero() -> None:
    assert levenshtein("abc", "abc") == 0


def test_levenshtein_one_char_edit() -> None:
    assert levenshtein("cat", "cut") == 1
    assert levenshtein("benchmark", "benchmarks") == 1


def test_levenshtein_handles_empty() -> None:
    assert levenshtein("", "abc") == 3
    assert levenshtein("abc", "") == 3
    assert levenshtein("", "") == 0


def test_closest_matches_ranks_by_distance() -> None:
    haystack = {"golang-general-engineer", "python-general-engineer", "code-reviewer"}
    matches = closest_matches("golang-gen-engineer", haystack, limit=3)
    # Closest match must be the golang agent.
    assert matches[0] == "golang-general-engineer"
    assert len(matches) == 3


def test_closest_matches_empty_haystack() -> None:
    assert closest_matches("anything", set()) == []


# ---------------------------------------------------------------------------
# main() — direct function call (fast, no subprocess)
# ---------------------------------------------------------------------------


def test_valid_agent_and_skill_exit_zero(fake_toolkit: Path, isolated_cwd: Path, capsys: pytest.CaptureFixture) -> None:
    rc = _mod.main(["--agent", "golang-general-engineer", "--skill", "go-patterns"])
    out = capsys.readouterr()
    assert rc == 0
    assert out.err == ""


def test_valid_agent_only(fake_toolkit: Path, isolated_cwd: Path, capsys: pytest.CaptureFixture) -> None:
    rc = _mod.main(["--agent", "python-general-engineer", "--skill", ""])
    out = capsys.readouterr()
    assert rc == 0
    assert out.err == ""


def test_valid_skill_only(fake_toolkit: Path, isolated_cwd: Path, capsys: pytest.CaptureFixture) -> None:
    rc = _mod.main(["--agent", "", "--skill", "pr-workflow"])
    out = capsys.readouterr()
    assert rc == 0
    assert out.err == ""


def test_invalid_agent_with_close_match(fake_toolkit: Path, isolated_cwd: Path, capsys: pytest.CaptureFixture) -> None:
    # "benchmark" does not exist; the real fake agents are far away but
    # closest_matches still returns a ranked list of three names.
    rc = _mod.main(["--agent", "benchmark", "--skill", ""])
    out = capsys.readouterr()
    assert rc == 2
    assert "router picked invalid agent: benchmark" in out.err
    assert "closest matches:" in out.err


def test_invalid_agent_typo_suggests_real_agent(
    fake_toolkit: Path, isolated_cwd: Path, capsys: pytest.CaptureFixture
) -> None:
    # Typo of "python-general-engineer".
    rc = _mod.main(["--agent", "python-general-enginer", "--skill", ""])
    out = capsys.readouterr()
    assert rc == 2
    assert "python-general-engineer" in out.err


def test_invalid_skill_still_reports(fake_toolkit: Path, isolated_cwd: Path, capsys: pytest.CaptureFixture) -> None:
    rc = _mod.main(["--agent", "", "--skill", "totally-made-up-skill"])
    out = capsys.readouterr()
    assert rc == 2
    assert "router picked invalid skill: totally-made-up-skill" in out.err
    # Three skills in the fake toolkit, so we always get a ranked list.
    assert "closest matches:" in out.err


def test_both_empty_is_error(fake_toolkit: Path, isolated_cwd: Path, capsys: pytest.CaptureFixture) -> None:
    rc = _mod.main(["--agent", "", "--skill", ""])
    out = capsys.readouterr()
    assert rc == 2
    assert "at least one of --agent or --skill must be non-empty" in out.err


def test_both_invalid_reports_both(fake_toolkit: Path, isolated_cwd: Path, capsys: pytest.CaptureFixture) -> None:
    rc = _mod.main(["--agent", "not-an-agent", "--skill", "not-a-skill"])
    out = capsys.readouterr()
    assert rc == 2
    assert "router picked invalid agent: not-an-agent" in out.err
    assert "router picked invalid skill: not-a-skill" in out.err


# ---------------------------------------------------------------------------
# Repo-local overrides
# ---------------------------------------------------------------------------


def test_repo_local_agent_override_wins(fake_toolkit: Path, isolated_cwd: Path, capsys: pytest.CaptureFixture) -> None:
    """A repo-local .claude/agents/<name>.md adds an agent not in the toolkit."""
    local_agents = isolated_cwd / ".claude" / "agents"
    local_agents.mkdir(parents=True)
    (local_agents / "local-only-agent.md").write_text("# local-only-agent\n", encoding="utf-8")

    rc = _mod.main(["--agent", "local-only-agent", "--skill", ""])
    out = capsys.readouterr()
    assert rc == 0
    assert out.err == ""


def test_repo_local_skill_override_wins(fake_toolkit: Path, isolated_cwd: Path, capsys: pytest.CaptureFixture) -> None:
    """A repo-local .claude/skills/<name>/SKILL.md adds a skill not in the toolkit."""
    local_skill_dir = isolated_cwd / ".claude" / "skills" / "local-only-skill"
    local_skill_dir.mkdir(parents=True)
    (local_skill_dir / "SKILL.md").write_text("# local-only-skill\n", encoding="utf-8")

    rc = _mod.main(["--agent", "", "--skill", "local-only-skill"])
    out = capsys.readouterr()
    assert rc == 0
    assert out.err == ""


# ---------------------------------------------------------------------------
# End-to-end: run the real script as a subprocess to exercise argparse + exit
# ---------------------------------------------------------------------------


def test_script_subprocess_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Invoke the script directly to confirm the CLI wiring and exit codes."""
    # Build a fake toolkit the subprocess will see via HOME.
    home = tmp_path / "home"
    home.mkdir()
    agents_dir = home / ".toolkit" / "agents"
    skills_dir = home / ".toolkit" / "skills"
    agents_dir.mkdir(parents=True)
    skills_dir.mkdir(parents=True)
    (agents_dir / "only-agent.md").write_text("# only-agent\n", encoding="utf-8")
    (agents_dir / "INDEX.json").write_text(
        json.dumps({"agents": {"only-agent": {"file": "agents/only-agent.md"}}}),
        encoding="utf-8",
    )
    (skills_dir / "only-skill").mkdir()
    (skills_dir / "only-skill" / "SKILL.md").write_text("# only-skill\n", encoding="utf-8")

    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    work = tmp_path / "cwd"
    work.mkdir()

    # Valid invocation -> exit 0.
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), "--agent", "only-agent", "--skill", "only-skill"],
        env=env,
        cwd=str(work),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""

    # Invalid invocation -> exit 2 with stderr.
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), "--agent", "not-real", "--skill", ""],
        env=env,
        cwd=str(work),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "router picked invalid agent: not-real" in result.stderr
