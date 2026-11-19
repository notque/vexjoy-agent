"""Negative-control tests for scripts/check-routing-drift.py.

Proves the drift checker rejects missing-from-manifest and unresolvable
skills, and accepts a clean setup. Uses a self-contained temp tree with
stub INDEX.json and routing-manifest.py.

Run with: python3 -m pytest scripts/tests/test_check_routing_drift.py -v
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "check-routing-drift.py"


def _setup_repo(
    tmp_path: Path,
    skills: dict[str, dict],
    manifest_skills: list[str] | None = None,
    manifest_extra: str = "",
    agents_section: list[str] | None = None,
) -> Path:
    """Build a minimal repo tree with skills/INDEX.json, a stub
    routing-manifest.py, and a file for each indexed skill.
    manifest_skills controls which names the stub manifest emits as entry
    lines (default: every indexed name). manifest_extra is appended to the
    SKILLS section verbatim. agents_section, when given, renders a retired
    AGENTS: section first."""
    repo = tmp_path / "repo"
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir(parents=True)

    # Copy the real script and its helper so REPO_ROOT resolves to repo/
    shutil.copy2(SCRIPT, scripts_dir / "check-routing-drift.py")
    (scripts_dir / "lib").mkdir(exist_ok=True)
    shutil.copy2(SCRIPT.parent / "lib" / "index_freshness.py", scripts_dir / "lib" / "index_freshness.py")

    index_dir = repo / "skills"
    index_dir.mkdir(parents=True)
    (index_dir / "INDEX.json").write_text(json.dumps({"skills": skills}), encoding="utf-8")
    for entry in skills.values():
        file_field = entry.get("file", "")
        if file_field:
            p = repo / file_field
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# Stub\n", encoding="utf-8")

    if manifest_skills is None:
        manifest_skills = list(skills.keys())
    lines: list[str] = []
    if agents_section is not None:
        lines += ["AGENTS:", *[f"  {name} — does things" for name in agents_section], ""]
    lines += ["SKILLS:", *[f"  {name} (meta) — does things" for name in manifest_skills]]
    if manifest_extra:
        lines.append(manifest_extra)
    lines += ["", "PIPELINES:"]
    manifest_script = scripts_dir / "routing-manifest.py"
    manifest_script.write_text(
        f"#!/usr/bin/env python3\nprint({chr(10).join(lines)!r})\n",
        encoding="utf-8",
    )

    return repo


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    script = repo / "scripts" / "check-routing-drift.py"
    return subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(repo),
    )


# ---------------------------------------------------------------------------
# Positive: all indexed skills appear in manifest -> exit 0
# ---------------------------------------------------------------------------


def test_clean_setup_passes(tmp_path: Path) -> None:
    skills = {
        "deploy": {"file": "skills/infrastructure/deploy/SKILL.md", "description": "deploy"},
        "review": {"file": "skills/review/review/SKILL.md", "description": "review"},
    }
    repo = _setup_repo(tmp_path, skills)
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# NEGATIVE: skill absent from routing manifest -> exit 1
# ---------------------------------------------------------------------------


def test_missing_from_manifest_exits_one(tmp_path: Path) -> None:
    skills = {
        "visible": {"file": "skills/visible/SKILL.md", "description": "ok"},
        "invisible": {"file": "skills/invisible/SKILL.md", "description": "missing"},
    }
    repo = _setup_repo(tmp_path, skills, manifest_skills=["visible"])
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "invisible" in result.stdout, result.stdout


# ---------------------------------------------------------------------------
# NEGATIVE: indexed skill's SKILL.md does not exist on disk -> exit 1
# ---------------------------------------------------------------------------


def test_unresolvable_skill_exits_one(tmp_path: Path) -> None:
    skills = {
        "good": {"file": "skills/good/SKILL.md", "description": "ok"},
        "ghost": {"file": "skills/ghost/SKILL.md", "description": "phantom"},
    }
    repo = _setup_repo(tmp_path, skills, manifest_skills=["good", "ghost"])
    # Remove the SKILL.md that _setup_repo created for ghost
    ghost_file = repo / "skills" / "ghost" / "SKILL.md"
    ghost_file.unlink()
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "ghost" in (result.stdout + result.stderr), result.stdout + result.stderr


# ---------------------------------------------------------------------------
# Agents are retired (plans/009): no agents index needed, no AGENTS: section allowed
# ---------------------------------------------------------------------------

_SKILLS = {"deploy": {"file": "skills/infrastructure/deploy/SKILL.md", "description": "deploy"}}


def test_no_agents_index_is_needed(tmp_path: Path) -> None:
    repo = _setup_repo(tmp_path, _SKILLS)
    assert not (repo / "agents").exists()
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_rendered_agents_section_fails(tmp_path: Path) -> None:
    repo = _setup_repo(tmp_path, _SKILLS, agents_section=["golang-general-engineer"])
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "AGENTS:" in result.stdout, result.stdout


def test_skill_named_only_in_another_entry_is_missing(tmp_path: Path) -> None:
    """A name inside another entry's text is not a manifest entry."""
    skills = {**_SKILLS, "lost": {"file": "skills/lost/SKILL.md", "description": "lost"}}
    repo = _setup_repo(
        tmp_path,
        skills,
        manifest_skills=["deploy"],
        manifest_extra="  other — x NOT: lost work (use lost)\nlost wrapped text",
    )
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "lost" in result.stdout, result.stdout


def test_missing_skills_index_without_generator_exits_one(tmp_path: Path) -> None:
    repo = _setup_repo(tmp_path, _SKILLS)
    (repo / "skills" / "INDEX.json").unlink()
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "cannot be generated" in result.stderr, result.stderr


def test_stale_skills_index_is_regenerated_before_the_check(tmp_path: Path) -> None:
    """An index older than a SKILL.md is rebuilt, so the check reads current data."""
    repo = _setup_repo(tmp_path, _SKILLS, manifest_skills=["deploy"])
    index = repo / "skills" / "INDEX.json"
    fresh = {"skills": {**_SKILLS, "added": {"file": "skills/added/SKILL.md", "description": "new"}}}
    (repo / "scripts" / "generate-skill-index.py").write_text(
        f"from pathlib import Path\nPath('skills/INDEX.json').write_text({json.dumps(fresh)!r})\n",
        encoding="utf-8",
    )
    (repo / "skills" / "added").mkdir()
    (repo / "skills" / "added" / "SKILL.md").write_text("# Stub\n", encoding="utf-8")
    os.utime(index, (1_000_000_000, 1_000_000_000))

    result = _run(repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "added" in result.stdout, result.stdout
    assert "added" in json.loads(index.read_text(encoding="utf-8"))["skills"]
