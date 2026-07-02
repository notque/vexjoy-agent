#!/usr/bin/env python3
"""
Tests for scripts/validate-merged-index.py (ADR router-improvement-program, C2).

Each audited defect class gets a seeded fixture the validator must flag:
  D1 — phantom `file` path (CRITICAL when force_route: router PREFERs an unloadable skill)
  D2 — dead `agent=` reference
  D3 — missing `category`
  D4 — missing `description`
  D5 — `not_for` starting "NOT: " (manifest generator prepends it again)
  +  — category outside scripts/category-registry.json (WARN)

Contract under test: advisory default (exit 0 with findings printed);
--strict exits 1 on critical/error findings; deterministic output order.

Run with: python3 -m pytest scripts/tests/test_validate_merged_index.py -v
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "validate-merged-index.py"


# ---------------------------------------------------------------------------
# Fixture builders: a throwaway repo tree + a fake ~/.claude dir.
# ---------------------------------------------------------------------------


def skill_entry(name: str, **overrides) -> dict:
    """A complete, defect-free skill INDEX entry. Overrides seed defects."""
    entry = {
        "file": f"skills/{name}/SKILL.md",
        "description": f"{name} does one thing well.",
        "category": "testing",
        "triggers": [f"{name} trigger"],
    }
    entry.update(overrides)
    return entry


def agent_entry(name: str, **overrides) -> dict:
    """A complete, defect-free agent INDEX entry."""
    entry = {
        "file": f"agents/{name}.md",
        "short_description": f"{name} agent.",
        "category": "testing",
        "triggers": [f"{name} trigger"],
    }
    entry.update(overrides)
    return entry


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def touch(root: Path, relpath: str) -> None:
    """Create an empty file at root/relpath, making parent dirs."""
    p = root / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("stub\n", encoding="utf-8")


def make_repo(
    tmp_path: Path,
    skills: dict,
    agents: dict | None = None,
    local_skills: dict | None = None,
    registry: list[str] | None = None,
) -> tuple[Path, Path]:
    """Build a fixture repo + fake claude dir. Creates backing files for every
    entry whose `file` path starts with the repo tree (callers seed phantoms
    by overriding `file` to a path this never creates)."""
    repo = tmp_path / "repo"
    claude = tmp_path / "claude"
    claude.mkdir(parents=True, exist_ok=True)

    write_json(repo / "skills" / "INDEX.json", {"skills": skills})
    if local_skills is not None:
        write_json(repo / "skills" / "INDEX.local.json", {"skills": local_skills})

    agents = agents if agents is not None else {"real-agent": agent_entry("real-agent")}
    write_json(repo / "agents" / "INDEX.json", {"agents": agents})

    for entries in (skills, local_skills or {}, agents):
        for entry in entries.values():
            file_field = entry.get("file", "")
            if file_field and not file_field.startswith("phantom"):
                touch(repo, file_field)

    if registry is None:
        registry = ["testing"]
    write_json(repo / "scripts" / "category-registry.json", {"comment": "test", "categories": registry})

    return repo, claude


def run(repo: Path, claude: Path, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(repo), "--claude-dir", str(claude), *flags],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Clean baseline
# ---------------------------------------------------------------------------


def test_clean_index_passes(tmp_path):
    repo, claude = make_repo(tmp_path, {"good-skill": skill_entry("good-skill")})
    result = run(repo, claude)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 finding(s)" in result.stdout


def test_clean_index_passes_strict(tmp_path):
    repo, claude = make_repo(tmp_path, {"good-skill": skill_entry("good-skill")})
    result = run(repo, claude, "--strict")
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# D1 — phantom file paths
# ---------------------------------------------------------------------------


def test_d1_phantom_file_flagged(tmp_path):
    skills = {"ghost": skill_entry("ghost", file="phantom/ghost/SKILL.md")}
    repo, claude = make_repo(tmp_path, skills)
    result = run(repo, claude)
    assert "ERROR PHANTOM ghost" in result.stdout
    assert "phantom/ghost/SKILL.md" in result.stdout


def test_d1_force_phantom_is_critical_and_called_out(tmp_path):
    skills = {"ghost-force": skill_entry("ghost-force", file="phantom/gf/SKILL.md", force_route=True)}
    repo, claude = make_repo(tmp_path, skills)
    result = run(repo, claude)
    assert "CRITICAL PHANTOM ghost-force" in result.stdout
    assert "PREFER" in result.stdout  # distinct call-out: router told to PREFER an unloadable skill


def test_d1_missing_file_field_flagged(tmp_path):
    entry = skill_entry("nofile")
    del entry["file"]
    repo, claude = make_repo(tmp_path, {"nofile": entry})
    result = run(repo, claude)
    assert "ERROR PHANTOM nofile" in result.stdout


def test_d1_agent_entry_phantom_file_flagged(tmp_path):
    agents = {"ghost-agent": agent_entry("ghost-agent", file="phantom/ghost-agent.md")}
    repo, claude = make_repo(tmp_path, {"good-skill": skill_entry("good-skill")}, agents=agents)
    result = run(repo, claude)
    assert "ERROR PHANTOM ghost-agent" in result.stdout


def test_d1_deployed_only_skill_resolves_via_claude_dir(tmp_path):
    skills = {"deployed": skill_entry("deployed")}
    repo, claude = make_repo(tmp_path, {"good-skill": skill_entry("good-skill")}, local_skills=skills)
    (repo / "skills" / "deployed").mkdir(parents=True, exist_ok=True)
    # File exists only under the claude dir (deployed flat layout), not the repo.
    (repo / "skills" / "deployed" / "SKILL.md").unlink()
    touch(claude, "skills/deployed/SKILL.md")
    result = run(repo, claude)
    assert "PHANTOM deployed" not in result.stdout
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# D2 — dead agent references
# ---------------------------------------------------------------------------


def test_d2_dead_agent_ref_flagged(tmp_path):
    skills = {"pipeline-skill": skill_entry("pipeline-skill", agent="vanished-agent")}
    repo, claude = make_repo(tmp_path, skills)
    result = run(repo, claude)
    assert "ERROR DEAD-AGENT-REF pipeline-skill" in result.stdout
    assert "vanished-agent" in result.stdout


def test_d2_agent_in_index_accepted(tmp_path):
    skills = {"paired": skill_entry("paired", agent="real-agent")}
    repo, claude = make_repo(tmp_path, skills)
    result = run(repo, claude)
    assert "DEAD-AGENT-REF" not in result.stdout


def test_d2_agent_md_on_disk_accepted(tmp_path):
    # Agent exists as agents/disk-agent.md but is absent from agents/INDEX.json.
    skills = {"paired": skill_entry("paired", agent="disk-agent")}
    repo, claude = make_repo(tmp_path, skills)
    touch(repo, "agents/disk-agent.md")
    result = run(repo, claude)
    assert "DEAD-AGENT-REF" not in result.stdout


def test_d2_builtin_agent_accepted(tmp_path):
    # general-purpose is harness-provided (see validate-do-references.py BUILTIN_AGENTS).
    skills = {"paired": skill_entry("paired", agent="general-purpose")}
    repo, claude = make_repo(tmp_path, skills)
    result = run(repo, claude)
    assert "DEAD-AGENT-REF" not in result.stdout


# ---------------------------------------------------------------------------
# D3 / D4 — missing category / description
# ---------------------------------------------------------------------------


def test_d3_missing_category_flagged(tmp_path):
    entry = skill_entry("nocat")
    del entry["category"]
    repo, claude = make_repo(tmp_path, {"nocat": entry})
    result = run(repo, claude)
    assert "ERROR MISSING-FIELD nocat" in result.stdout
    assert "category" in result.stdout


def test_d4_missing_description_flagged(tmp_path):
    entry = skill_entry("nodesc")
    del entry["description"]
    repo, claude = make_repo(tmp_path, {"nodesc": entry})
    result = run(repo, claude)
    assert "ERROR MISSING-FIELD nodesc" in result.stdout
    assert "description" in result.stdout


def test_d4_short_description_accepted_as_description(tmp_path):
    entry = skill_entry("shortdesc")
    del entry["description"]
    entry["short_description"] = "Short."
    repo, claude = make_repo(tmp_path, {"shortdesc": entry})
    result = run(repo, claude)
    assert "MISSING-FIELD shortdesc" not in result.stdout


# ---------------------------------------------------------------------------
# D5 — "NOT: " prefix doubling
# ---------------------------------------------------------------------------


def test_d5_not_prefix_flagged(tmp_path):
    skills = {"noisy": skill_entry("noisy", not_for="NOT: deep review")}
    repo, claude = make_repo(tmp_path, skills)
    result = run(repo, claude)
    assert "ERROR NOT-PREFIX noisy" in result.stdout


def test_d5_plain_not_for_accepted(tmp_path):
    skills = {"quiet": skill_entry("quiet", not_for="deep review (use full-repo-review)")}
    repo, claude = make_repo(tmp_path, skills)
    result = run(repo, claude)
    assert "NOT-PREFIX" not in result.stdout


# ---------------------------------------------------------------------------
# Category registry
# ---------------------------------------------------------------------------


def test_unknown_category_warns(tmp_path):
    skills = {"offbook": skill_entry("offbook", category="uncharted")}
    repo, claude = make_repo(tmp_path, skills, registry=["testing"])
    result = run(repo, claude)
    assert "WARN UNKNOWN-CATEGORY offbook" in result.stdout
    assert "uncharted" in result.stdout
    assert result.returncode == 0


def test_unknown_category_does_not_gate_strict(tmp_path):
    # Warnings stay advisory even under --strict; only critical/error gate.
    skills = {"offbook": skill_entry("offbook", category="uncharted")}
    repo, claude = make_repo(tmp_path, skills, registry=["testing"])
    result = run(repo, claude, "--strict")
    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_registry_skips_category_check(tmp_path):
    repo, claude = make_repo(tmp_path, {"good-skill": skill_entry("good-skill")})
    (repo / "scripts" / "category-registry.json").unlink()
    result = run(repo, claude)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "UNKNOWN-CATEGORY" not in result.stdout


# ---------------------------------------------------------------------------
# Merged (tracked + local) reads
# ---------------------------------------------------------------------------


def test_defect_in_local_overlay_found(tmp_path):
    # The audit gap: every live defect sat in the local overlay, unvalidated.
    local = {"local-ghost": skill_entry("local-ghost", file="phantom/lg/SKILL.md")}
    repo, claude = make_repo(tmp_path, {"good-skill": skill_entry("good-skill")}, local_skills=local)
    result = run(repo, claude)
    assert "ERROR PHANTOM local-ghost" in result.stdout


def test_local_overlay_absent_tolerated(tmp_path):
    repo, claude = make_repo(tmp_path, {"good-skill": skill_entry("good-skill")})
    assert not (repo / "skills" / "INDEX.local.json").exists()
    result = run(repo, claude)
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# Exit codes, ordering, summary
# ---------------------------------------------------------------------------


def _defect_zoo(tmp_path) -> tuple[Path, Path]:
    """One fixture holding every defect class at once."""
    nocat = skill_entry("nocat")
    del nocat["category"]
    skills = {
        "ghost-force": skill_entry("ghost-force", file="phantom/gf/SKILL.md", force_route=True),
        "ghost": skill_entry("ghost", file="phantom/g/SKILL.md"),
        "dead-ref": skill_entry("dead-ref", agent="vanished-agent"),
        "nocat": nocat,
        "noisy": skill_entry("noisy", not_for="NOT: x"),
        "offbook": skill_entry("offbook", category="uncharted"),
    }
    return make_repo(tmp_path, skills)


def test_advisory_default_exits_zero_with_findings(tmp_path):
    repo, claude = _defect_zoo(tmp_path)
    result = run(repo, claude)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PHANTOM" in result.stdout


def test_strict_exits_one_on_errors(tmp_path):
    repo, claude = _defect_zoo(tmp_path)
    result = run(repo, claude, "--strict")
    assert result.returncode == 1


def test_output_deterministic_and_severity_ordered(tmp_path):
    repo, claude = _defect_zoo(tmp_path)
    first = run(repo, claude).stdout
    second = run(repo, claude).stdout
    assert first == second
    lines = [ln for ln in first.splitlines() if ln[:4] in ("CRIT", "ERRO", "WARN")]
    levels = [ln.split()[0] for ln in lines]
    rank = {"CRITICAL": 0, "ERROR": 1, "WARN": 2}
    assert levels == sorted(levels, key=lambda level: rank[level])
    assert levels[0] == "CRITICAL"


def test_summary_counts(tmp_path):
    repo, claude = _defect_zoo(tmp_path)
    result = run(repo, claude)
    assert "6 finding(s)" in result.stdout
    assert "1 critical" in result.stdout
    assert "4 error" in result.stdout
    assert "1 warn" in result.stdout


def test_missing_tracked_index_exits_one(tmp_path):
    repo, claude = make_repo(tmp_path, {"good-skill": skill_entry("good-skill")})
    (repo / "skills" / "INDEX.json").unlink()
    result = run(repo, claude)
    assert result.returncode == 1
