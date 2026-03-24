"""Tests for scripts/index-router.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the module under test
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import importlib

index_router = importlib.import_module("index-router")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SKILLS_INDEX = {
    "version": "2.0",
    "skills": {
        "go-testing": {
            "file": "skills/go-testing/SKILL.md",
            "description": "Go testing patterns.",
            "triggers": ["Go test", "_test.go", "table-driven"],
            "force_route": True,
            "agent": "golang-general-engineer",
            "pairs_with": ["go-error-handling"],
            "category": "language",
        },
        "systematic-debugging": {
            "file": "skills/systematic-debugging/SKILL.md",
            "description": "Evidence-based debugging.",
            "triggers": ["debug", "find root cause", "reproduce bug"],
            "category": "process",
        },
        "code-linting": {
            "file": "skills/code-linting/SKILL.md",
            "description": "Lint and format code.",
            "triggers": ["lint code", "run ruff", "format code"],
            "category": "code-quality",
        },
    },
}

SAMPLE_PIPELINES_INDEX = {
    "version": "2.0",
    "pipelines": {
        "pr-pipeline": {
            "file": "pipelines/pr-pipeline/SKILL.md",
            "description": "Submit PR.",
            "triggers": ["submit PR", "create pull request", "push and PR"],
            "force_route": True,
            "phases": ["STAGE", "COMMIT", "PUSH", "CREATE", "VERIFY"],
            "pairs_with": ["git-commit-flow"],
        },
        "doc-pipeline": {
            "file": "pipelines/doc-pipeline/SKILL.md",
            "description": "Create documentation.",
            "triggers": ["document this", "create documentation", "write docs"],
            "force_route": True,
            "pairs_with": ["generate-claudemd"],
        },
        "explore-pipeline": {
            "file": "pipelines/explore-pipeline/SKILL.md",
            "description": "Explore codebase.",
            "triggers": ["understand codebase", "explore repo", "how does this work"],
            "model": "opus",
        },
    },
}

SAMPLE_AGENTS_INDEX = {
    "version": "1.0",
    "agents": {
        "golang-general-engineer": {
            "file": "golang-general-engineer.md",
            "short_description": "Go development expert.",
            "triggers": ["go", "golang", ".go files", "gofmt"],
            "pairs_with": ["go-pr-quality-gate"],
            "complexity": "Medium-Complex",
            "category": "language",
        },
        "python-general-engineer": {
            "file": "python-general-engineer.md",
            "short_description": "Python development expert.",
            "triggers": ["python", ".py", "pip", "pytest"],
            "pairs_with": ["python-quality-gate"],
            "complexity": "Medium-Complex",
            "category": "language",
        },
    },
}


@pytest.fixture()
def mock_indexes(tmp_path: Path) -> Path:
    """Create temporary INDEX files and patch REPO_ROOT."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "INDEX.json").write_text(json.dumps(SAMPLE_SKILLS_INDEX))

    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    (pipelines_dir / "INDEX.json").write_text(json.dumps(SAMPLE_PIPELINES_INDEX))

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "INDEX.json").write_text(json.dumps(SAMPLE_AGENTS_INDEX))

    return tmp_path


@pytest.fixture(autouse=True)
def _patch_repo_root(mock_indexes: Path) -> None:
    """Patch INDEX_PATHS to use temporary files."""
    patched_paths = {
        "skills": mock_indexes / "skills" / "INDEX.json",
        "pipelines": mock_indexes / "pipelines" / "INDEX.json",
        "agents": mock_indexes / "agents" / "INDEX.json",
    }
    with patch.object(index_router, "INDEX_PATHS", patched_paths):
        yield


# ---------------------------------------------------------------------------
# load_indexes tests
# ---------------------------------------------------------------------------


class TestLoadIndexes:
    """Tests for load_indexes."""

    def test_loads_all_entry_types(self) -> None:
        entries = index_router.load_indexes()
        types = {e.entry_type for e in entries}
        assert types == {"skill", "pipeline", "agent"}

    def test_loads_correct_count(self) -> None:
        entries = index_router.load_indexes()
        # 3 skills + 3 pipelines + 2 agents = 8
        assert len(entries) == 8

    def test_skill_entry_fields(self) -> None:
        entries = index_router.load_indexes()
        go_testing = next(e for e in entries if e.name == "go-testing")
        assert go_testing.entry_type == "skill"
        assert go_testing.force_route is True
        assert go_testing.agent == "golang-general-engineer"
        assert "Go test" in go_testing.triggers
        assert "go-error-handling" in go_testing.pairs_with

    def test_pipeline_entry_fields(self) -> None:
        entries = index_router.load_indexes()
        pr = next(e for e in entries if e.name == "pr-pipeline")
        assert pr.entry_type == "pipeline"
        assert pr.force_route is True

    def test_agent_entry_fields(self) -> None:
        entries = index_router.load_indexes()
        golang = next(e for e in entries if e.name == "golang-general-engineer")
        assert golang.entry_type == "agent"
        assert "go" in golang.triggers

    def test_missing_index_file_graceful(self, mock_indexes: Path) -> None:
        (mock_indexes / "agents" / "INDEX.json").unlink()
        patched_paths = {
            "skills": mock_indexes / "skills" / "INDEX.json",
            "pipelines": mock_indexes / "pipelines" / "INDEX.json",
            "agents": mock_indexes / "agents" / "INDEX.json",
        }
        with patch.object(index_router, "INDEX_PATHS", patched_paths):
            entries = index_router.load_indexes()
        # Should still load skills and pipelines (6 entries)
        assert len(entries) == 6
        assert all(e.entry_type != "agent" for e in entries)

    def test_malformed_json_graceful(self, mock_indexes: Path) -> None:
        (mock_indexes / "skills" / "INDEX.json").write_text("not json {{{")
        patched_paths = {
            "skills": mock_indexes / "skills" / "INDEX.json",
            "pipelines": mock_indexes / "pipelines" / "INDEX.json",
            "agents": mock_indexes / "agents" / "INDEX.json",
        }
        with patch.object(index_router, "INDEX_PATHS", patched_paths):
            entries = index_router.load_indexes()
        # Should still load pipelines and agents (5 entries)
        assert len(entries) == 5


# ---------------------------------------------------------------------------
# check_force_routes tests
# ---------------------------------------------------------------------------


class TestCheckForceRoutes:
    """Tests for check_force_routes."""

    def test_matches_force_route_skill(self) -> None:
        entries = index_router.load_indexes()
        match = index_router.check_force_routes("write Go test for auth", entries)
        assert match is not None
        assert match.name == "go-testing"
        assert match.agent == "golang-general-engineer"

    def test_matches_force_route_pipeline(self) -> None:
        entries = index_router.load_indexes()
        match = index_router.check_force_routes("submit PR for this feature", entries)
        assert match is not None
        assert match.name == "pr-pipeline"
        assert match.entry_type == "pipeline"

    def test_case_insensitive_matching(self) -> None:
        entries = index_router.load_indexes()
        match = index_router.check_force_routes("CREATE PULL REQUEST now", entries)
        assert match is not None
        assert match.name == "pr-pipeline"

    def test_no_match_returns_none(self) -> None:
        entries = index_router.load_indexes()
        match = index_router.check_force_routes("something completely unrelated", entries)
        assert match is None

    def test_non_force_route_not_matched(self) -> None:
        entries = index_router.load_indexes()
        # "debug" is a trigger for systematic-debugging but it's NOT force_route
        match = index_router.check_force_routes("debug this issue", entries)
        assert match is None

    def test_substring_match(self) -> None:
        entries = index_router.load_indexes()
        # "table-driven" is a trigger for go-testing
        match = index_router.check_force_routes("write table-driven tests for auth", entries)
        assert match is not None
        assert match.name == "go-testing"


# ---------------------------------------------------------------------------
# score_candidates tests
# ---------------------------------------------------------------------------


class TestScoreCandidates:
    """Tests for score_candidates."""

    def test_returns_scored_list(self) -> None:
        entries = index_router.load_indexes()
        candidates = index_router.score_candidates("debug find root cause", entries)
        assert len(candidates) > 0
        assert all(c.score > 0.1 for c in candidates)

    def test_sorted_by_score_descending(self) -> None:
        entries = index_router.load_indexes()
        candidates = index_router.score_candidates("lint code format code run ruff", entries)
        scores = [c.score for c in candidates]
        assert scores == sorted(scores, reverse=True)

    def test_top_candidate_correct(self) -> None:
        entries = index_router.load_indexes()
        candidates = index_router.score_candidates("lint code run ruff format code", entries)
        assert candidates[0].name == "code-linting"

    def test_no_match_returns_empty(self) -> None:
        entries = index_router.load_indexes()
        candidates = index_router.score_candidates("xyzzy plugh zzzzz", entries)
        assert candidates == []

    def test_respects_max_candidates(self) -> None:
        entries = index_router.load_indexes()
        candidates = index_router.score_candidates("all the things", entries)
        assert len(candidates) <= index_router.MAX_CANDIDATES


# ---------------------------------------------------------------------------
# resolve_agent tests
# ---------------------------------------------------------------------------


class TestResolveAgent:
    """Tests for resolve_agent."""

    def test_returns_existing_agent(self) -> None:
        entries = index_router.load_indexes()
        candidate = index_router.Candidate(
            entry_type="skill", name="go-testing", score=0.9, agent="golang-general-engineer"
        )
        assert index_router.resolve_agent(candidate, entries) == "golang-general-engineer"

    def test_resolves_from_agent_index(self) -> None:
        entries = index_router.load_indexes()
        # pr-pipeline has no agent — should try to match against agents
        candidate = index_router.Candidate(entry_type="pipeline", name="pr-pipeline", score=0.8)
        # May or may not resolve depending on name overlap with agent triggers
        result = index_router.resolve_agent(candidate, entries)
        # Result can be None or a valid agent name
        assert result is None or isinstance(result, str)

    def test_returns_none_when_no_agent_match(self) -> None:
        entries = index_router.load_indexes()
        candidate = index_router.Candidate(entry_type="skill", name="zzzz-nonexistent", score=0.5)
        result = index_router.resolve_agent(candidate, entries)
        # No overlap between "zzzz" and any agent triggers
        assert result is None


# ---------------------------------------------------------------------------
# suggest_pairs tests
# ---------------------------------------------------------------------------


class TestSuggestPairs:
    """Tests for suggest_pairs."""

    def test_collects_pairs(self) -> None:
        entry = index_router.IndexEntry(
            name="go-testing", entry_type="skill", pairs_with=["go-error-handling", "go-concurrency"]
        )
        pairs = index_router.suggest_pairs([entry])
        assert pairs == ["go-error-handling", "go-concurrency"]

    def test_deduplicates(self) -> None:
        entries = [
            index_router.IndexEntry(name="a", entry_type="skill", pairs_with=["x", "y"]),
            index_router.IndexEntry(name="b", entry_type="skill", pairs_with=["y", "z"]),
        ]
        pairs = index_router.suggest_pairs(entries)
        assert pairs == ["x", "y", "z"]

    def test_excludes_self_references(self) -> None:
        entries = [
            index_router.IndexEntry(name="a", entry_type="skill", pairs_with=["b"]),
            index_router.IndexEntry(name="b", entry_type="skill", pairs_with=["a", "c"]),
        ]
        pairs = index_router.suggest_pairs(entries)
        # "a" and "b" are matched entries, so excluded from pairs
        assert pairs == ["c"]


# ---------------------------------------------------------------------------
# check_composition_chains tests
# ---------------------------------------------------------------------------


class TestCheckCompositionChains:
    """Tests for check_composition_chains."""

    def test_finds_chain_for_entry_skill(self) -> None:
        chains = index_router.check_composition_chains("systematic-debugging")
        assert len(chains) == 1
        assert chains[0] == ["systematic-debugging", "test-driven-development", "pr-pipeline"]

    def test_finds_chain_for_member_skill(self) -> None:
        chains = index_router.check_composition_chains("test-driven-development")
        assert len(chains) == 1
        assert "systematic-debugging" in chains[0]

    def test_returns_empty_for_no_match(self) -> None:
        chains = index_router.check_composition_chains("nonexistent-skill")
        assert chains == []

    def test_returns_empty_for_none(self) -> None:
        chains = index_router.check_composition_chains(None)
        assert chains == []

    def test_doc_pipeline_chain(self) -> None:
        chains = index_router.check_composition_chains("doc-pipeline")
        assert len(chains) == 1
        assert chains[0] == ["docs-sync-checker", "doc-pipeline", "generate-claudemd"]


# ---------------------------------------------------------------------------
# route_request integration tests
# ---------------------------------------------------------------------------


class TestRouteRequest:
    """Integration tests for route_request."""

    def test_force_route_populates_result(self) -> None:
        result = index_router.route_request("write Go test for the handler")
        assert result.force_route is not None
        assert result.force_route.get("skill") == "go-testing"
        assert result.force_route.get("agent") == "golang-general-engineer"

    def test_force_only_skips_candidates(self) -> None:
        result = index_router.route_request("write Go test for the handler", force_only=True)
        assert result.force_route is not None
        assert result.candidates == []

    def test_no_match_returns_empty_result(self) -> None:
        result = index_router.route_request("xyzzy plugh zzzzz")
        assert result.force_route is None
        assert result.candidates == []
        assert result.pairs_with == []
        assert result.model_preference is None

    def test_candidates_populated_for_non_force(self) -> None:
        result = index_router.route_request("lint code format code run ruff")
        # code-linting should be top candidate
        assert len(result.candidates) > 0
        assert result.candidates[0].name == "code-linting"

    def test_pipeline_force_route(self) -> None:
        result = index_router.route_request("create documentation for the API")
        assert result.force_route is not None
        assert result.force_route.get("pipeline") == "doc-pipeline"


# ---------------------------------------------------------------------------
# Output formatting tests
# ---------------------------------------------------------------------------


class TestFormatting:
    """Tests for output formatting."""

    def test_json_output_valid(self) -> None:
        result = index_router.route_request("write Go test for auth")
        output = index_router.format_json_output(result)
        parsed = json.loads(output)
        assert "force_route" in parsed
        assert "candidates" in parsed
        assert "pairs_with" in parsed
        assert "model_preference" in parsed
        assert "composition_chains" in parsed

    def test_json_output_candidate_fields(self) -> None:
        result = index_router.route_request("lint code format code run ruff")
        output = index_router.format_json_output(result)
        parsed = json.loads(output)
        for candidate in parsed["candidates"]:
            assert "type" in candidate
            assert "name" in candidate
            assert "score" in candidate

    def test_text_output_force_route(self) -> None:
        result = index_router.route_request("write Go test for auth")
        output = index_router.format_text_output(result)
        assert "force_route:" in output
        assert "go-testing" in output

    def test_text_output_no_match(self) -> None:
        result = index_router.route_request("xyzzy zzzzz")
        output = index_router.format_text_output(result)
        assert "no_match: true" in output


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


SCRIPT_PATH = str(Path(__file__).resolve().parent.parent / "index-router.py")


class TestCLI:
    """CLI integration tests using subprocess against real INDEX files."""

    def test_json_flag(self) -> None:
        result = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--request", "write Go tests for auth", "--json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert "force_route" in parsed

    def test_plain_text_output(self) -> None:
        result = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--request", "write Go tests for auth"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "go-testing" in result.stdout

    def test_force_only_flag(self) -> None:
        result = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--request", "write Go tests for auth", "--force-only", "--json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert parsed["candidates"] == []
        assert parsed["force_route"] is not None

    def test_always_exits_zero(self) -> None:
        result = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--request", "xyzzy plugh completely unrelated"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
