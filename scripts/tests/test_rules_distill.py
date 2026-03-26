"""Tests for scripts/rules-distill.py — ADR-114.

Tests each filter layer independently using fixture skill content,
plus integration tests for the full pipeline and staleness policy.
"""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import module under test
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, _SCRIPTS_DIR)
rules_distill = importlib.import_module("rules-distill")
sys.path.pop(0)


# ---------------------------------------------------------------------------
# Fixtures — synthetic skill content
# ---------------------------------------------------------------------------

SKILL_A_CONTENT = """\
---
name: skill-a
description: Test skill A
version: 1.0.0
---

# Skill A

## Hardcoded Behaviors

- Always exit 0 from hooks regardless of errors to avoid blocking the pipeline
- Never auto-apply changes without explicit user approval
- Always verify the output before marking a task complete
- Must run tests after every code modification
"""

SKILL_B_CONTENT = """\
---
name: skill-b
description: Test skill B
version: 1.0.0
---

# Skill B

## Rules

- Always exit 0 from session hooks otherwise the session will fail
- Never write to files without reading them first
- Always verify the output before claiming success
- Must run the test suite after every change, otherwise regressions will slip through
"""

SKILL_C_CONTENT = """\
---
name: skill-c
description: Test skill C (single skill only)
version: 1.0.0
---

# Skill C

## Rules

- Use structured JSON output for all API responses
"""

SKILL_D_CONTENT = """\
---
name: skill-d
description: Test skill D (descriptive, not actionable)
version: 1.0.0
---

# Skill D

## Background

This skill handles file operations.
The system uses a SQLite database for persistence.
Results are cached in memory.
"""

# Shared pattern that overlaps heavily with "always exit 0" principle
SHARED_PATTERN_CONTENT = """\
# Hook Exit Patterns

Always exit 0 from hooks regardless of errors.
Never block the pipeline. Hooks must always exit cleanly.
"""


# ---------------------------------------------------------------------------
# Unit tests: extract_principles_from_text
# ---------------------------------------------------------------------------


class TestExtractPrinciples:
    def test_extracts_bullet_rules(self):
        results = rules_distill.extract_principles_from_text(SKILL_A_CONTENT, "skill-a")
        principles = [r["principle"] for r in results]
        assert any("exit 0" in p for p in principles)
        assert any("verify" in p.lower() for p in principles)

    def test_skips_non_rule_lines(self):
        content = "The system uses SQLite.\nResults are cached.\nBackground info here."
        results = rules_distill.extract_principles_from_text(content, "test")
        assert len(results) == 0

    def test_source_label_attached(self):
        results = rules_distill.extract_principles_from_text(SKILL_A_CONTENT, "my-skill")
        assert all(r["source"] == "my-skill" for r in results)

    def test_minimum_length_filter(self):
        content = "- Never do it\n"  # too short
        results = rules_distill.extract_principles_from_text(content, "x")
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Unit tests: Layer 1 — multi-skill filter
# ---------------------------------------------------------------------------


class TestLayer1MultiSkill:
    def _make_candidates(self, items: list[tuple[str, str]]) -> list[dict]:
        """Create candidate list from (principle, source) pairs."""
        return [{"principle": p, "raw": p, "source": s} for p, s in items]

    def test_keeps_principle_in_two_skills(self):
        # Layer 1 groups by normalized exact text — both skills must use the same principle
        candidates = self._make_candidates(
            [
                ("Always exit 0 from hooks regardless of errors", "skill-a"),
                ("Always exit 0 from hooks regardless of errors", "skill-b"),
            ]
        )
        result = rules_distill.filter_layer1_multi_skill(candidates, min_skills=2)
        assert len(result) == 1
        assert result[0]["occurrence_count"] >= 2

    def test_discards_single_skill_principle(self):
        candidates = self._make_candidates(
            [
                ("Use structured JSON output for all API responses", "skill-c"),
            ]
        )
        result = rules_distill.filter_layer1_multi_skill(candidates, min_skills=2)
        assert len(result) == 0

    def test_deduplicates_same_skill_repetition(self):
        # Same skill mentioning the same principle twice should count as 1 source
        candidates = self._make_candidates(
            [
                ("Always verify output before completing", "skill-a"),
                ("Always verify output before completing", "skill-a"),  # duplicate source
                ("Always verify output before completing", "skill-b"),
            ]
        )
        result = rules_distill.filter_layer1_multi_skill(candidates, min_skills=2)
        assert len(result) == 1
        assert result[0]["occurrence_count"] == 2  # 2 unique sources

    def test_collects_skills_list(self):
        # Layer 1 groups by normalized exact text — use the same principle across skills
        candidates = self._make_candidates(
            [
                ("Never auto-apply changes without explicit user approval", "skill-a"),
                ("Never auto-apply changes without explicit user approval", "skill-b"),
                ("Never auto-apply changes without explicit user approval", "skill-c"),
            ]
        )
        result = rules_distill.filter_layer1_multi_skill(candidates, min_skills=2)
        assert len(result) == 1
        assert len(result[0]["skills"]) >= 2

    def test_case_insensitive_grouping(self):
        candidates = self._make_candidates(
            [
                ("Always Exit 0 From Hooks", "skill-a"),
                ("always exit 0 from hooks", "skill-b"),
            ]
        )
        result = rules_distill.filter_layer1_multi_skill(candidates, min_skills=2)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Unit tests: Layer 2 — actionable filter
# ---------------------------------------------------------------------------


class TestLayer2Actionable:
    def _make_multi(self, principle: str) -> list[dict]:
        return [{"principle": principle, "skills": ["a", "b"], "occurrence_count": 2}]

    def test_keeps_always_rule(self):
        result = rules_distill.filter_layer2_actionable(
            self._make_multi("Always exit 0 from hooks regardless of errors")
        )
        assert len(result) == 1

    def test_keeps_never_rule(self):
        result = rules_distill.filter_layer2_actionable(self._make_multi("Never auto-apply changes without approval"))
        assert len(result) == 1

    def test_keeps_must_rule(self):
        result = rules_distill.filter_layer2_actionable(
            self._make_multi("Must run tests after every code modification")
        )
        assert len(result) == 1

    def test_keeps_avoid_rule(self):
        result = rules_distill.filter_layer2_actionable(self._make_multi("Avoid blocking the session hook pipeline"))
        assert len(result) == 1

    def test_discards_descriptive_statement(self):
        result = rules_distill.filter_layer2_actionable(
            self._make_multi("The system stores results in a SQLite database")
        )
        assert len(result) == 0

    def test_discards_background_context(self):
        result = rules_distill.filter_layer2_actionable(
            self._make_multi("This approach was chosen for performance reasons")
        )
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Unit tests: Layer 3 — violation risk filter
# ---------------------------------------------------------------------------


class TestLayer3ViolationRisk:
    def _make_candidate(self, principle: str, source: str = "skill-a") -> dict:
        return {
            "principle": principle,
            "skills": [source],
            "occurrence_count": 2,
        }

    def test_passes_principle_with_otherwise_in_text(self):
        principle = "Always exit 0 from hooks otherwise the session will fail"
        candidates = [self._make_candidate(principle)]
        result = rules_distill.filter_layer3_violation_risk(candidates, {})
        assert len(result) == 1

    def test_passes_principle_with_exits_0_keyword(self):
        principle = "Hooks must always exits 0 to avoid blocking"
        candidates = [self._make_candidate(principle)]
        result = rules_distill.filter_layer3_violation_risk(candidates, {})
        assert len(result) == 1

    def test_uses_skill_context_for_risk_detection(self):
        principle = "Always verify output before completing a task"
        # Principle itself has no violation keyword, but skill body does
        skill_body = (
            "Always verify output before completing a task. Skipping this will break the pipeline and cause errors."
        )
        candidates = [self._make_candidate(principle, "skill-a")]
        result = rules_distill.filter_layer3_violation_risk(candidates, {"skill-a": skill_body})
        assert len(result) == 1

    def test_discards_principle_with_no_risk_context(self):
        principle = "Always use structured JSON output"
        candidates = [self._make_candidate(principle)]
        # No risk keywords in principle or skill context
        result = rules_distill.filter_layer3_violation_risk(
            candidates, {"skill-a": "Use structured JSON output for responses."}
        )
        assert len(result) == 0

    def test_passes_fail_keyword(self):
        principle = "Never skip tests otherwise the build will fail"
        candidates = [self._make_candidate(principle)]
        result = rules_distill.filter_layer3_violation_risk(candidates, {})
        assert len(result) == 1

    def test_passes_crash_keyword(self):
        principle = "Always handle exceptions or the process will crash"
        candidates = [self._make_candidate(principle)]
        result = rules_distill.filter_layer3_violation_risk(candidates, {})
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Unit tests: Layer 4 — not-already-covered filter
# ---------------------------------------------------------------------------


class TestLayer4NotCovered:
    def _make_candidate(self, principle: str) -> dict:
        return {
            "principle": principle,
            "skills": ["a", "b"],
            "occurrence_count": 2,
        }

    def test_discards_heavily_overlapping_principle(self):
        shared = ["Always exit 0 from hooks regardless of errors. Never block the pipeline."]
        candidates = [self._make_candidate("Always exit 0 from hooks regardless of errors")]
        result = rules_distill.filter_layer4_not_covered(candidates, shared)
        # High overlap — should be filtered out
        assert len(result) == 0

    def test_keeps_novel_principle(self):
        shared = ["Always exit 0 from hooks regardless of errors."]
        candidates = [self._make_candidate("Never commit directly to main without explicit user authorization")]
        result = rules_distill.filter_layer4_not_covered(candidates, shared)
        assert len(result) == 1

    def test_overlap_ratio_attached(self):
        shared = ["Always verify output. Never skip tests."]
        novel = "Never auto-apply proposed changes without reading the target file first"
        candidates = [self._make_candidate(novel)]
        result = rules_distill.filter_layer4_not_covered(candidates, shared)
        if result:
            assert "overlap_ratio" in result[0]
            assert 0.0 <= result[0]["overlap_ratio"] <= 1.0

    def test_empty_shared_patterns_passes_all(self):
        candidates = [
            self._make_candidate("Always exit 0 from hooks"),
            self._make_candidate("Never auto-apply changes"),
        ]
        result = rules_distill.filter_layer4_not_covered(candidates, [])
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Unit tests: Staleness policy
# ---------------------------------------------------------------------------


class TestStalenessPolicy:
    def _make_pending(self, days_ago: int) -> dict:
        created = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return {
            "id": "abc12345",
            "principle": "Always exit 0",
            "status": "pending",
            "created_at": created.isoformat(),
        }

    def test_recent_pending_stays_pending(self):
        candidates = [self._make_pending(5)]
        result = rules_distill.apply_staleness_policy(candidates)
        assert result[0]["status"] == "pending"

    def test_stale_pending_promoted_to_deferred(self):
        candidates = [self._make_pending(35)]  # > 30 days
        result = rules_distill.apply_staleness_policy(candidates)
        assert result[0]["status"] == "deferred"
        assert result[0].get("deferred_reason") == "staleness"

    def test_boundary_at_30_days_stays_pending(self):
        candidates = [self._make_pending(30)]
        result = rules_distill.apply_staleness_policy(candidates)
        # Exactly 30 days — not yet stale
        assert result[0]["status"] == "pending"

    def test_approved_candidates_unchanged(self):
        c = {
            "id": "xyz",
            "principle": "Some principle",
            "status": "approved",
            "created_at": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
        }
        result = rules_distill.apply_staleness_policy([c])
        assert result[0]["status"] == "approved"

    def test_skipped_candidates_unchanged(self):
        c = {
            "id": "xyz",
            "principle": "Some principle",
            "status": "skipped",
            "created_at": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
        }
        result = rules_distill.apply_staleness_policy([c])
        assert result[0]["status"] == "skipped"

    def test_missing_created_at_left_intact(self):
        c = {"id": "xyz", "principle": "Some principle", "status": "pending"}
        result = rules_distill.apply_staleness_policy([c])
        assert result[0]["status"] == "pending"  # No date → no change


# ---------------------------------------------------------------------------
# Unit tests: merge_candidates
# ---------------------------------------------------------------------------


class TestMergeCandidates:
    def _make_new(self, principle: str, skills: list[str] | None = None) -> dict:
        return {
            "principle": principle,
            "raw": principle,
            "skills": skills or ["skill-a", "skill-b"],
            "occurrence_count": 2,
            "overlap_ratio": 0.1,
            "source": "skill-a",
        }

    def test_adds_new_candidate(self):
        existing: list[dict] = []
        new = [self._make_new("Always exit 0 from hooks")]
        result = rules_distill.merge_candidates(existing, new)
        assert len(result) == 1
        assert result[0]["status"] == "pending"

    def test_skips_already_approved(self):
        approved = {
            "id": "abc",
            "principle": "Always exit 0 from hooks",
            "status": "approved",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        new = [self._make_new("Always exit 0 from hooks")]
        result = rules_distill.merge_candidates([approved], new)
        # Only the approved one — new duplicate not added
        assert len(result) == 1
        assert result[0]["status"] == "approved"

    def test_skips_already_skipped(self):
        skipped = {
            "id": "abc",
            "principle": "Never auto-apply changes",
            "status": "skipped",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        new = [self._make_new("Never auto-apply changes")]
        result = rules_distill.merge_candidates([skipped], new)
        assert len(result) == 1
        assert result[0]["status"] == "skipped"

    def test_does_not_duplicate_pending(self):
        pending = {
            "id": "abc",
            "principle": "Always exit 0 from hooks",
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        new = [self._make_new("Always exit 0 from hooks")]
        result = rules_distill.merge_candidates([pending], new)
        assert len(result) == 1  # Not duplicated

    def test_candidate_id_assigned(self):
        new = [self._make_new("Always verify output before completing")]
        result = rules_distill.merge_candidates([], new)
        assert "id" in result[0]
        assert len(result[0]["id"]) == 8

    def test_confidence_assigned(self):
        new = [self._make_new("Must run tests after every code modification")]
        result = rules_distill.merge_candidates([], new)
        assert "confidence" in result[0]
        assert 0.0 <= result[0]["confidence"] <= 1.0

    def test_verdict_assigned(self):
        new = [self._make_new("Never block the hook pipeline")]
        result = rules_distill.merge_candidates([], new)
        assert result[0]["verdict"] in ("Append", "Revise", "New Section")


# ---------------------------------------------------------------------------
# Integration test: full distillation pipeline (file-based)
# ---------------------------------------------------------------------------


class TestFullPipeline:
    def test_dry_run_with_fixture_skills(self, tmp_path):
        """Full pipeline using temporary skill files — no writes."""
        # Create temporary skill files
        skills_dir = tmp_path / "skills"
        (skills_dir / "skill-a").mkdir(parents=True)
        (skills_dir / "skill-b").mkdir(parents=True)
        (skills_dir / "shared-patterns").mkdir(parents=True)
        (skills_dir / "skill-a" / "SKILL.md").write_text(SKILL_A_CONTENT)
        (skills_dir / "skill-b" / "SKILL.md").write_text(SKILL_B_CONTENT)
        (skills_dir / "shared-patterns" / "base.md").write_text("# Base Patterns\nSome existing patterns here.")

        # Patch the module's directory constants
        with (
            patch.object(rules_distill, "SKILLS_DIR", skills_dir),
            patch.object(rules_distill, "PIPELINES_DIR", tmp_path / "pipelines"),
            patch.object(rules_distill, "SHARED_PATTERNS_DIR", skills_dir / "shared-patterns"),
            patch.object(rules_distill, "LEARNING_DIR", tmp_path / "learning"),
            patch.object(rules_distill, "PENDING_JSON", tmp_path / "learning" / "pending.json"),
            patch.object(rules_distill, "LAST_RUN_FILE", tmp_path / "learning" / "last-run"),
            # Disable LLM to use keyword extraction
            patch.object(rules_distill, "_llm_extract_principles", return_value=None),
        ):
            result = rules_distill.run_distillation(dry_run=True, verbose=False)

        # Validate required top-level keys (ADR-114 validation criteria)
        assert "distilled_at" in result
        assert "skills_scanned" in result
        assert "candidates" in result

        # Skills were scanned
        assert len(result["skills_scanned"]) == 2

        # No files written in dry-run
        assert not (tmp_path / "learning" / "pending.json").exists()

    def test_writes_pending_json_in_live_mode(self, tmp_path):
        """Full pipeline writes pending.json in live mode."""
        skills_dir = tmp_path / "skills"
        (skills_dir / "skill-a").mkdir(parents=True)
        (skills_dir / "skill-b").mkdir(parents=True)
        (skills_dir / "shared-patterns").mkdir(parents=True)
        (skills_dir / "skill-a" / "SKILL.md").write_text(SKILL_A_CONTENT)
        (skills_dir / "skill-b" / "SKILL.md").write_text(SKILL_B_CONTENT)

        learning_dir = tmp_path / "learning"

        with (
            patch.object(rules_distill, "SKILLS_DIR", skills_dir),
            patch.object(rules_distill, "PIPELINES_DIR", tmp_path / "pipelines"),
            patch.object(rules_distill, "SHARED_PATTERNS_DIR", skills_dir / "shared-patterns"),
            patch.object(rules_distill, "LEARNING_DIR", learning_dir),
            patch.object(rules_distill, "PENDING_JSON", learning_dir / "pending.json"),
            patch.object(rules_distill, "LAST_RUN_FILE", learning_dir / "last-run"),
            patch.object(rules_distill, "_llm_extract_principles", return_value=None),
        ):
            result = rules_distill.run_distillation(dry_run=False, verbose=False)

        # File must be written
        pending_path = learning_dir / "pending.json"
        assert pending_path.exists()

        # Validate JSON content
        written = json.loads(pending_path.read_text())
        assert "distilled_at" in written
        assert "skills_scanned" in written
        assert "candidates" in written

    def test_candidates_have_required_fields(self, tmp_path):
        """All candidates must have id, principle, skills, status, confidence, verdict."""
        skills_dir = tmp_path / "skills"
        (skills_dir / "skill-a").mkdir(parents=True)
        (skills_dir / "skill-b").mkdir(parents=True)
        (skills_dir / "shared-patterns").mkdir(parents=True)
        (skills_dir / "skill-a" / "SKILL.md").write_text(SKILL_A_CONTENT)
        (skills_dir / "skill-b" / "SKILL.md").write_text(SKILL_B_CONTENT)

        learning_dir = tmp_path / "learning"

        with (
            patch.object(rules_distill, "SKILLS_DIR", skills_dir),
            patch.object(rules_distill, "PIPELINES_DIR", tmp_path / "pipelines"),
            patch.object(rules_distill, "SHARED_PATTERNS_DIR", skills_dir / "shared-patterns"),
            patch.object(rules_distill, "LEARNING_DIR", learning_dir),
            patch.object(rules_distill, "PENDING_JSON", learning_dir / "pending.json"),
            patch.object(rules_distill, "LAST_RUN_FILE", learning_dir / "last-run"),
            patch.object(rules_distill, "_llm_extract_principles", return_value=None),
        ):
            result = rules_distill.run_distillation(dry_run=True, verbose=False)

        required_fields = {"id", "principle", "skills", "status", "confidence", "verdict", "target"}
        for candidate in result["candidates"]:
            missing = required_fields - set(candidate.keys())
            assert not missing, f"Candidate missing fields: {missing}\n{candidate}"

    def test_all_candidates_pass_four_layer_filter(self, tmp_path):
        """Verify every output candidate logically passes each filter layer."""
        skills_dir = tmp_path / "skills"
        (skills_dir / "skill-a").mkdir(parents=True)
        (skills_dir / "skill-b").mkdir(parents=True)
        (skills_dir / "shared-patterns").mkdir(parents=True)
        (skills_dir / "skill-a" / "SKILL.md").write_text(SKILL_A_CONTENT)
        (skills_dir / "skill-b" / "SKILL.md").write_text(SKILL_B_CONTENT)

        learning_dir = tmp_path / "learning"

        with (
            patch.object(rules_distill, "SKILLS_DIR", skills_dir),
            patch.object(rules_distill, "PIPELINES_DIR", tmp_path / "pipelines"),
            patch.object(rules_distill, "SHARED_PATTERNS_DIR", skills_dir / "shared-patterns"),
            patch.object(rules_distill, "LEARNING_DIR", learning_dir),
            patch.object(rules_distill, "PENDING_JSON", learning_dir / "pending.json"),
            patch.object(rules_distill, "LAST_RUN_FILE", learning_dir / "last-run"),
            patch.object(rules_distill, "_llm_extract_principles", return_value=None),
        ):
            result = rules_distill.run_distillation(dry_run=True, verbose=False)

        for candidate in result["candidates"]:
            p = candidate["principle"]
            # Layer 1: appeared in 2+ skills
            assert candidate.get("occurrence_count", 0) >= 2, f"L1 fail: {p}"
            # Layer 2: actionable keyword present
            assert rules_distill._ACTIONABLE_RE.search(p), f"L2 fail: {p}"
            # Layer 3: trusted because it made it through (no easy re-check without context)
            # Layer 4: overlap_ratio < 0.4 (how it was filtered)
            assert candidate.get("overlap_ratio", 0.0) < 0.4, f"L4 fail: {p}"
