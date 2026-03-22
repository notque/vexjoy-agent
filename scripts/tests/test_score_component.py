"""Tests for scripts/score-component.py deterministic scoring."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "score-component.py"


def run_script(*args: str, expect_rc: int = 0) -> subprocess.CompletedProcess[str]:
    """Run score-component.py with given arguments."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == expect_rc, (
        f"Expected rc={expect_rc}, got {result.returncode}\nstderr: {result.stderr}\nstdout: {result.stdout}"
    )
    return result


class TestSingleComponent:
    """Test scoring individual component files."""

    def test_score_agent(self) -> None:
        result = run_script("agents/golang-general-engineer.md")
        assert "Component Health Score" in result.stdout
        assert "Type: agent" in result.stdout
        assert "TOTAL:" in result.stdout

    def test_score_skill(self) -> None:
        result = run_script("skills/do/SKILL.md")
        assert "Component Health Score" in result.stdout
        assert "Type: skill" in result.stdout

    def test_grade_in_output(self) -> None:
        result = run_script("agents/golang-general-engineer.md")
        # Must contain one of the valid grades
        assert any(f"({g})" in result.stdout for g in ("A", "B", "C", "D", "F"))


class TestBatchMode:
    """Test --all-agents and --all-skills flags."""

    def test_all_agents_runs(self) -> None:
        # Exit code 1 is expected when some agents grade below B
        result = run_script("--all-agents", "--json", expect_rc=1)
        data = json.loads(result.stdout)
        assert data["summary"]["total_components"] > 0
        assert "results" in data

    def test_all_skills_runs(self) -> None:
        # Exit code 1 is expected when some skills grade below B
        result = run_script("--all-skills", "--json", expect_rc=1)
        data = json.loads(result.stdout)
        assert data["summary"]["total_components"] > 0

    def test_summary_table_shown_for_multiple(self) -> None:
        result = run_script(
            "agents/golang-general-engineer.md",
            "agents/python-general-engineer.md",
        )
        assert "Summary" in result.stdout
        assert "Average:" in result.stdout


class TestJsonOutput:
    """Test --json flag produces valid, structured JSON."""

    def test_json_structure(self) -> None:
        result = run_script("agents/golang-general-engineer.md", "--json")
        data = json.loads(result.stdout)
        assert "results" in data
        assert "summary" in data
        assert len(data["results"]) == 1

        entry = data["results"][0]
        assert entry["type"] == "agent"
        assert "total" in entry
        assert "max_total" in entry
        assert "grade" in entry
        assert "checks" in entry
        assert isinstance(entry["checks"], list)

    def test_json_check_fields(self) -> None:
        result = run_script("skills/do/SKILL.md", "--json")
        data = json.loads(result.stdout)
        check = data["results"][0]["checks"][0]
        assert "name" in check
        assert "status" in check
        assert "earned" in check
        assert "max" in check
        assert check["status"] in ("PASS", "FAIL", "PART")


class TestSecretDetection:
    """Test --check-secrets flag."""

    def test_no_secrets_in_agents(self) -> None:
        result = run_script("agents/golang-general-engineer.md", "--check-secrets", "--json")
        data = json.loads(result.stdout)
        entry = data["results"][0]
        assert entry["secret_penalty"] == 0
        assert entry["secrets_found"] == []


class TestErrorHandling:
    """Test error cases return correct exit codes."""

    def test_missing_file(self) -> None:
        run_script("nonexistent.md", expect_rc=2)

    def test_no_arguments(self) -> None:
        run_script(expect_rc=2)

    def test_non_component_file(self) -> None:
        run_script("scripts/score-component.py", expect_rc=2)


class TestCheckLogic:
    """Test individual check functions via subprocess with specific inputs."""

    def test_frontmatter_pass(self) -> None:
        """Valid frontmatter detected via a real agent with known good frontmatter."""
        result = run_script("agents/golang-general-engineer.md", "--json")
        data = json.loads(result.stdout)
        checks = {c["name"]: c for c in data["results"][0]["checks"]}
        assert checks["Valid YAML frontmatter"]["status"] == "PASS"
        assert checks["Valid YAML frontmatter"]["earned"] == 10

    def test_operator_context_check(self) -> None:
        """Operator Context check detects subsections in /do skill."""
        result = run_script("skills/do/SKILL.md", "--json")
        data = json.loads(result.stdout)
        checks = {c["name"]: c for c in data["results"][0]["checks"]}
        assert checks["Operator Context"]["status"] == "PASS"

    def test_secret_detection_clean_agent(self) -> None:
        """No secrets in a standard agent."""
        result = run_script("agents/golang-general-engineer.md", "--check-secrets", "--json")
        data = json.loads(result.stdout)
        entry = data["results"][0]
        assert entry["secret_penalty"] == 0
        assert entry["secrets_found"] == []

    def test_routing_registration_check(self) -> None:
        """Registered agent passes routing check."""
        result = run_script("agents/golang-general-engineer.md", "--json")
        data = json.loads(result.stdout)
        checks = {c["name"]: c for c in data["results"][0]["checks"]}
        assert checks["Registered in routing"]["status"] == "PASS"
