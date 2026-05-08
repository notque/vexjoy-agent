"""Tests for hooks/pipeline-phase-gate.py.

Covers:
- Existing do-perspectives gates (regression)
- quality-loop phase gates
- feature-lifecycle phase gates
- Bypass env var
- No sentinel fallthrough
- Unknown pipeline fallthrough
- JSON sentinel format
- Legacy integer sentinel format
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parents[2] / "hooks" / "pipeline-phase-gate.py"


def _run_hook(
    tool_input: dict,
    cwd: str | None = None,
    env_overrides: dict[str, str] | None = None,
    timeout: int = 10,
) -> subprocess.CompletedProcess:
    """Run the hook as a subprocess, passing event JSON on stdin."""
    event = {
        "tool_name": "Write",
        "tool_input": tool_input,
    }
    if cwd:
        event["cwd"] = cwd

    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(Path.home()),
        "PYTHONPATH": "",
    }
    if env_overrides:
        env.update(env_overrides)

    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


# ---------------------------------------------------------------------------
# Regression: do-perspectives gates still work
# ---------------------------------------------------------------------------


class TestDoPerspecivesGates:
    """Existing do-perspectives prerequisite and sentinel gates."""

    def test_writing_synthesis_without_prerequisite_blocks(self, tmp_path: Path) -> None:
        """Writing synthesis.md without perspectives-analysis.md -> exit 2."""
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "synthesis.md")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2
        assert "BLOCKED" in result.stderr
        assert "perspectives-analysis.md" in result.stderr

    def test_writing_synthesis_with_prerequisite_allows(self, tmp_path: Path) -> None:
        """Writing synthesis.md with perspectives-analysis.md present -> exit 0."""
        (tmp_path / "perspectives-analysis.md").write_text("analysis content")
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "synthesis.md")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_sentinel_phase3_without_artifact_blocks(self, tmp_path: Path) -> None:
        """Sentinel phase=3 for do-perspectives without perspectives-analysis.md -> exit 2."""
        (tmp_path / ".pipeline-phase").write_text('{"pipeline": "do-perspectives", "phase": 3}')
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "some-output.md")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2
        assert "perspectives-analysis.md" in result.stderr

    def test_sentinel_phase4_with_artifact_allows(self, tmp_path: Path) -> None:
        """Sentinel phase=4 for do-perspectives with synthesis.md -> exit 0."""
        (tmp_path / ".pipeline-phase").write_text('{"pipeline": "do-perspectives", "phase": 4}')
        (tmp_path / "synthesis.md").write_text("synthesis content")
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "final-output.md")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# quality-loop phase gates
# ---------------------------------------------------------------------------


class TestQualityLoopGates:
    """quality-loop: PLAN -> IMPLEMENT -> TEST -> REVIEW gates."""

    def test_phase2_implement_without_task_plan_blocks(self, tmp_path: Path) -> None:
        """Phase 2 (IMPLEMENT) write without task_plan.md -> exit 2."""
        (tmp_path / ".pipeline-phase").write_text('{"pipeline": "quality-loop", "phase": 2}')
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "src/main.py")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2
        assert "BLOCKED" in result.stderr
        assert "task_plan.md" in result.stderr

    def test_phase2_implement_with_task_plan_allows(self, tmp_path: Path) -> None:
        """Phase 2 (IMPLEMENT) write with task_plan.md present -> exit 0."""
        (tmp_path / ".pipeline-phase").write_text('{"pipeline": "quality-loop", "phase": 2}')
        (tmp_path / "task_plan.md").write_text("## Plan\n- acceptance criteria here")
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "src/main.py")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_phase3_test_without_state_blocks(self, tmp_path: Path) -> None:
        """Phase 3 (TEST) without quality-loop-state.md -> exit 2."""
        (tmp_path / ".pipeline-phase").write_text('{"pipeline": "quality-loop", "phase": 3}')
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "test_output.txt")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2
        assert "quality-loop-state.md" in result.stderr

    def test_phase3_test_with_state_allows(self, tmp_path: Path) -> None:
        """Phase 3 (TEST) with quality-loop-state.md present -> exit 0."""
        (tmp_path / ".pipeline-phase").write_text('{"pipeline": "quality-loop", "phase": 3}')
        (tmp_path / "quality-loop-state.md").write_text("agent: python\nskill: quality-gate")
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "test_output.txt")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_phase7_fix_without_state_blocks(self, tmp_path: Path) -> None:
        """Phase 7 (FIX) without quality-loop-state.md -> exit 2."""
        (tmp_path / ".pipeline-phase").write_text('{"pipeline": "quality-loop", "phase": 7}')
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "src/fix.py")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2

    def test_phase9_pr_with_state_allows(self, tmp_path: Path) -> None:
        """Phase 9 (PR) with quality-loop-state.md -> exit 0."""
        (tmp_path / ".pipeline-phase").write_text('{"pipeline": "quality-loop", "phase": 9}')
        (tmp_path / "quality-loop-state.md").write_text("agent: go\nskill: go-patterns")
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "pr_body.md")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# feature-lifecycle phase gates
# ---------------------------------------------------------------------------


class TestFeatureLifecycleGates:
    """feature-lifecycle: DESIGN -> PLAN -> IMPLEMENT -> VALIDATE -> RELEASE gates."""

    def test_phase2_plan_without_feature_dir_blocks(self, tmp_path: Path) -> None:
        """Phase 2 (PLAN) without .feature/ directory -> exit 2."""
        (tmp_path / ".pipeline-phase").write_text('{"pipeline": "feature-lifecycle", "phase": 2}')
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "plan.md")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2
        assert "BLOCKED" in result.stderr
        assert ".feature/" in result.stderr

    def test_phase2_plan_with_feature_dir_allows(self, tmp_path: Path) -> None:
        """Phase 2 (PLAN) with .feature/ directory present -> exit 0."""
        (tmp_path / ".pipeline-phase").write_text('{"pipeline": "feature-lifecycle", "phase": 2}')
        (tmp_path / ".feature").mkdir()
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "plan.md")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_phase4_validate_without_feature_dir_blocks(self, tmp_path: Path) -> None:
        """Phase 4 (VALIDATE) without .feature/ -> exit 2."""
        (tmp_path / ".pipeline-phase").write_text('{"pipeline": "feature-lifecycle", "phase": 4}')
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "report.md")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2

    def test_phase5_release_with_feature_dir_allows(self, tmp_path: Path) -> None:
        """Phase 5 (RELEASE) with .feature/ -> exit 0."""
        (tmp_path / ".pipeline-phase").write_text('{"pipeline": "feature-lifecycle", "phase": 5}')
        (tmp_path / ".feature").mkdir()
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "release-notes.md")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# pr-workflow (empty registry — falls through)
# ---------------------------------------------------------------------------


class TestPrWorkflowGates:
    """pr-workflow: currently no file-artifact gates, should fall through."""

    def test_pr_workflow_no_gates_allows(self, tmp_path: Path) -> None:
        """pr-workflow has no phase entries, so all writes fall through -> exit 0."""
        (tmp_path / ".pipeline-phase").write_text('{"pipeline": "pr-workflow", "phase": 2}')
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "some-file.py")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Bypass and fallthrough
# ---------------------------------------------------------------------------


class TestBypassAndFallthrough:
    """Bypass env var, no sentinel, unknown pipeline."""

    def test_bypass_env_allows_regardless(self, tmp_path: Path) -> None:
        """PIPELINE_PHASE_GATE_BYPASS=1 allows even when artifact is missing."""
        (tmp_path / ".pipeline-phase").write_text('{"pipeline": "quality-loop", "phase": 2}')
        # No task_plan.md — would normally block
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "src/main.py")},
            cwd=str(tmp_path),
            env_overrides={"PIPELINE_PHASE_GATE_BYPASS": "1"},
        )
        assert result.returncode == 0

    def test_no_sentinel_falls_through(self, tmp_path: Path) -> None:
        """No .pipeline-phase sentinel file -> exit 0 (no active pipeline)."""
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "any-file.py")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_unknown_pipeline_falls_through(self, tmp_path: Path) -> None:
        """Unknown pipeline ID in sentinel -> exit 0 (don't break unknown pipelines)."""
        (tmp_path / ".pipeline-phase").write_text('{"pipeline": "some-future-skill", "phase": 5}')
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "output.md")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_empty_stdin_allows(self, tmp_path: Path) -> None:
        """Empty stdin (broken pipe) -> exit 0."""
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
            env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home())},
        )
        assert result.returncode == 0

    def test_no_file_path_allows(self, tmp_path: Path) -> None:
        """tool_input without file_path -> exit 0."""
        result = _run_hook(
            tool_input={"content": "some content"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Sentinel format tests
# ---------------------------------------------------------------------------


class TestSentinelFormats:
    """Test JSON and legacy integer sentinel formats."""

    def test_legacy_integer_sentinel_with_env_pipeline(self, tmp_path: Path) -> None:
        """Legacy integer sentinel + PIPELINE_ID env -> gates correctly."""
        (tmp_path / ".pipeline-phase").write_text("3")
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "output.md")},
            cwd=str(tmp_path),
            env_overrides={"PIPELINE_ID": "do-perspectives"},
        )
        # Phase 3 requires perspectives-analysis.md which is absent
        assert result.returncode == 2

    def test_json_sentinel_with_pipeline(self, tmp_path: Path) -> None:
        """JSON sentinel carries pipeline ID — no env needed."""
        (tmp_path / ".pipeline-phase").write_text('{"pipeline": "quality-loop", "phase": 2}')
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "something.py")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2
        assert "task_plan.md" in result.stderr

    def test_malformed_sentinel_falls_through(self, tmp_path: Path) -> None:
        """Malformed sentinel content -> exit 0 (fail open)."""
        (tmp_path / ".pipeline-phase").write_text("not-a-number-or-json")
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "file.py")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_empty_sentinel_falls_through(self, tmp_path: Path) -> None:
        """Empty sentinel file -> exit 0."""
        (tmp_path / ".pipeline-phase").write_text("")
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "file.py")},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_env_phase_overrides_sentinel(self, tmp_path: Path) -> None:
        """PIPELINE_CURRENT_PHASE env overrides sentinel file phase."""
        # Sentinel says phase 2 (would need task_plan.md for quality-loop)
        (tmp_path / ".pipeline-phase").write_text('{"pipeline": "quality-loop", "phase": 2}')
        # But env says phase 1 (no gate for quality-loop phase 1)
        result = _run_hook(
            tool_input={"file_path": str(tmp_path / "something.py")},
            cwd=str(tmp_path),
            env_overrides={"PIPELINE_CURRENT_PHASE": "1"},
        )
        # Phase 1 has no gate entry for quality-loop -> falls through
        # But pipeline detection still needs to find "quality-loop" — check env override takes priority
        assert result.returncode == 0
