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
