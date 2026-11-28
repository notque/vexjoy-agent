"""Tests for scripts/validate-references.py — agent reference file integrity.

Covers the path-existence check (``ref_path.exists()`` in ``validate_agent``),
the --agent and --all CLI modes, and negative controls: a reference pointing
at a missing file must exit non-zero.

Every fake agent lives under ``tmp_path``. The CLI tests pass ``--agents-dir``
so nothing is written to the real ``agents/`` directory.

Run with: python3 -m pytest scripts/tests/test_validate_references.py -v
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "validate-references.py"

# Load the hyphenated script as a module.
_spec = importlib.util.spec_from_file_location("validate_references", SCRIPT)
assert _spec is not None and _spec.loader is not None
vr = importlib.util.module_from_spec(_spec)
sys.modules["validate_references"] = vr
_spec.loader.exec_module(vr)

GOOD_REFERENCE = "# Patterns\n\n## Usage\n\nExample:\n\n```python\nprint('ok')\n```\n"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=120,
    )


def _write_agent(agents_dir: Path, name: str, ref: str, *, create_ref: bool) -> Path:
    """Write ``<name>.md`` linking ``references/<ref>``; create the reference file if asked."""
    refs_dir = agents_dir / name / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)
    if create_ref:
        (refs_dir / ref).write_text(GOOD_REFERENCE, encoding="utf-8")
    agent_file = agents_dir / f"{name}.md"
    agent_file.write_text(f"# {name}\n\nLoad [patterns](references/{ref}) on signal.\n", encoding="utf-8")
    return agent_file


# ---------------------------------------------------------------------------
# Negative control: a reference that does not exist must be flagged
# ---------------------------------------------------------------------------


def test_validate_agent_flags_missing_reference(tmp_path: Path) -> None:
    """An agent declaring a reference that does not exist is flagged as MISSING."""
    agent_file = _write_agent(tmp_path, "negtest-phantom-agent", "nonexistent-patterns.md", create_ref=False)

    result = vr.validate_agent(agent_file, check_structure=True)

    expected = str(tmp_path / "negtest-phantom-agent" / "references" / "nonexistent-patterns.md")
    assert result.missing == [expected]
    assert not result.ok, "result should not be ok when references are missing"


def test_validate_agent_passes_when_references_exist(tmp_path: Path) -> None:
    """An agent with all references present and well-formed reports ok=True."""
    agent_file = _write_agent(tmp_path, "negtest-good-agent", "patterns.md", create_ref=True)

    result = vr.validate_agent(agent_file, check_structure=True)

    assert result.declared == [str(tmp_path / "negtest-good-agent" / "references" / "patterns.md")]
    assert result.ok, f"expected ok=True; missing={result.missing}, issues={result.issues}"


# ---------------------------------------------------------------------------
# CLI modes against a tmp agents dir
# ---------------------------------------------------------------------------


def test_agent_mode_exits_nonzero_on_missing_reference(tmp_path: Path) -> None:
    """--agent mode exits 1 and prints MISSING when the agent's reference is absent."""
    _write_agent(tmp_path, "negtest-missing-ref", "does-not-exist-zzzz.md", create_ref=False)

    result = _run("--agents-dir", str(tmp_path), "--agent", "negtest-missing-ref")

    assert result.returncode == 1, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "MISSING: negtest-missing-ref/references/does-not-exist-zzzz.md" in result.stdout, result.stdout


def test_agent_mode_exits_zero_when_references_exist(tmp_path: Path) -> None:
    """--agent mode exits 0 for an agent whose reference exists and is well-formed."""
    _write_agent(tmp_path, "negtest-good-agent", "patterns.md", create_ref=True)

    result = _run("--agents-dir", str(tmp_path), "--agent", "negtest-good-agent")

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "negtest-good-agent: 1/1 references present, 0 issues" in result.stdout, result.stdout


def test_all_mode_reports_missing_reference_and_orphan(tmp_path: Path) -> None:
    """--all mode exits 1, flags the missing reference and the orphan, and passes the good agent."""
    _write_agent(tmp_path, "negtest-good-agent", "patterns.md", create_ref=True)
    _write_agent(tmp_path, "negtest-missing-ref", "does-not-exist-zzzz.md", create_ref=False)
    (tmp_path / "negtest-good-agent" / "references" / "unused.md").write_text(GOOD_REFERENCE, encoding="utf-8")

    result = _run("--agents-dir", str(tmp_path), "--all")

    assert result.returncode == 1, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "negtest-good-agent: 1/1 references present, 0 issues" in result.stdout, result.stdout
    assert "MISSING: negtest-missing-ref/references/does-not-exist-zzzz.md" in result.stdout, result.stdout
    assert "ORPHAN: negtest-good-agent/references/unused.md" in result.stdout, result.stdout


# ---------------------------------------------------------------------------
# Scoped modes that CI already uses
# ---------------------------------------------------------------------------


def _make_synthetic_repo(tmp_path: Path) -> Path:
    """Create a minimal repo copy hosting scripts/validate-references.py."""
    repo = tmp_path / "repo"
    (repo / "scripts" / "lib").mkdir(parents=True)
    shutil.copy2(SCRIPT, repo / "scripts" / "validate-references.py")
    for lib_file in ("__init__.py", "frontmatter.py", "index_freshness.py"):
        src = REPO_ROOT / "scripts" / "lib" / lib_file
        if src.is_file():
            shutil.copy2(src, repo / "scripts" / "lib" / lib_file)
    merge_src = REPO_ROOT / "scripts" / "routing_index_merge.py"
    if merge_src.is_file():
        shutil.copy2(merge_src, repo / "scripts" / "routing_index_merge.py")
    (repo / "agents").mkdir(exist_ok=True)
    (repo / "skills").mkdir(exist_ok=True)
    (repo / "commands").mkdir(exist_ok=True)
    return repo


def _run_in_repo(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    script = repo / "scripts" / "validate-references.py"
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        cwd=str(repo),
        timeout=60,
    )


def test_check_do_framing_exits_nonzero_on_unpaired_antipattern(tmp_path: Path) -> None:
    """--check-do-framing exits 1 when an anti-pattern heading lacks a positive counterpart."""
    repo = _make_synthetic_repo(tmp_path)
    skill = repo / "skills" / "demo" / "bad-framing" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# Demo\n\n## Anti-patterns\n\nNever write bare except clauses.\n", encoding="utf-8")

    result = _run_in_repo(repo, "--check-do-framing")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "DO-FRAMING" in result.stdout
    assert "bad-framing" in result.stdout


def test_check_placeholders_exits_nonzero_on_generic_signal(tmp_path: Path) -> None:
    """--check-placeholders exits 1 when a loading table uses a banned placeholder signal."""
    repo = _make_synthetic_repo(tmp_path)
    skill = repo / "skills" / "demo" / "bad-table" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "# Demo\n\n| Signal | Reference |\n| --- | --- |\n| implementation patterns | references/p.md |\n",
        encoding="utf-8",
    )

    result = _run_in_repo(repo, "--check-placeholders")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "PLACEHOLDER_SIGNAL" in result.stdout
    assert "implementation patterns" in result.stdout


def test_check_size_exits_nonzero_on_oversized_reference(tmp_path: Path) -> None:
    """--check-size exits 1 when an unregistered skill reference exceeds 500 lines."""
    repo = _make_synthetic_repo(tmp_path)
    skill_dir = repo / "skills" / "demo" / "huge-ref"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Huge Ref\n", encoding="utf-8")
    (skill_dir / "references" / "oversized.md").write_text("line\n" * 510, encoding="utf-8")

    result = _run_in_repo(repo, "--check-size")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "demo/huge-ref/references/oversized.md" in result.stdout
    assert "exceeds 500" in result.stdout


def test_check_skill_calls_exits_nonzero_on_unknown_skill_and_missing_tool(tmp_path: Path) -> None:
    """--check-skill-calls exits 1 when a command calls a nonexistent skill without Skill permission."""
    repo = _make_synthetic_repo(tmp_path)
    (repo / "skills" / "INDEX.json").write_text(json.dumps({"skills": {"known-skill": {}}}), encoding="utf-8")
    (repo / "agents" / "INDEX.json").write_text(json.dumps({"agents": {}}), encoding="utf-8")
    pipeline_idx = repo / "skills" / "process" / "workflow" / "references" / "pipeline-index.json"
    pipeline_idx.parent.mkdir(parents=True)
    pipeline_idx.write_text(json.dumps({"pipelines": {}}), encoding="utf-8")
    (repo / "commands" / "broken.md").write_text(
        "---\ndescription: broken\nallowed-tools: [Read]\n---\n\nCall the Skill tool with `phantom-skill`.\n",
        encoding="utf-8",
    )

    result = _run_in_repo(repo, "--check-skill-calls")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "allowed-tools lacks Skill" in result.stdout
    assert "phantom-skill" in result.stdout


def test_validate_reference_file_outside_repo_falls_back_cleanly(tmp_path: Path) -> None:
    """validate_reference_file must not raise ValueError for paths outside agents_dir and REPO_ROOT."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("validate_references_mod", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    ext = tmp_path / "external_ref.md"
    ext.write_text("No headings here.\n", encoding="utf-8")
    issues = mod.validate_reference_file(ext)
    assert len(issues) == 1
    assert issues[0].kind == "no-headings"
    assert issues[0].path == str(ext)
