"""Comprehensive test suite for harness.py.

Tests cover:
1. Grader unit tests (file_exists, string_contains, regex_match, yaml_valid)
2. Integration tests (run_task, run_suite)
3. Calibration tests (load_calibration_examples, run_calibration_example)
4. Token extraction and transcript parsing
"""

# Import harness functions
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from harness import (
    GRADERS,
    cleanup_environment,
    compute_weighted_score,
    extract_token_usage,
    extract_transcript_from_json,
    extract_transcript_metrics,
    grade_file_exists,
    grade_regex_match,
    grade_state_check,
    grade_string_contains,
    grade_tests_pass,
    grade_tool_calls,
    grade_transcript_constraint,
    grade_yaml_valid,
    load_calibration_examples,
    run_calibration_example,
    run_graders,
    run_suite,
    run_task,
    setup_environment,
)

# ============================================================================
# Grader Unit Tests: file_exists
# ============================================================================


class TestGradeFileExists:
    """Tests for the file_exists grader."""

    def test_grade_file_exists_found(self, tmp_work_dir: Path) -> None:
        """Test file_exists grader when file is present."""
        # Create a file in the work directory
        test_file = tmp_work_dir / "output.py"
        test_file.write_text("print('hello')")

        env = {"work_dir": str(tmp_work_dir)}
        config = {"path": "output.py"}

        result = grade_file_exists("", env, config)

        assert result["type"] == "file_exists"
        assert result["passed"] is True
        assert result["score"] == 1.0
        assert "exists" in result["details"]

    def test_grade_file_exists_not_found(self, tmp_work_dir: Path) -> None:
        """Test file_exists grader when file is missing."""
        env = {"work_dir": str(tmp_work_dir)}
        config = {"path": "missing_file.py"}

        result = grade_file_exists("", env, config)

        assert result["type"] == "file_exists"
        assert result["passed"] is False
        assert result["score"] == 0.0
        assert "not found" in result["details"]

    def test_grade_file_exists_nested_path(self, tmp_work_dir: Path) -> None:
        """Test file_exists grader with nested directory path."""
        nested_dir = tmp_work_dir / "src" / "utils"
        nested_dir.mkdir(parents=True)
        test_file = nested_dir / "helpers.py"
        test_file.write_text("def helper(): pass")

        env = {"work_dir": str(tmp_work_dir)}
        config = {"path": "src/utils/helpers.py"}

        result = grade_file_exists("", env, config)

        assert result["passed"] is True
        assert result["score"] == 1.0


# ============================================================================
# Grader Unit Tests: string_contains
# ============================================================================


class TestGradeStringContains:
    """Tests for the string_contains grader."""

    def test_grade_string_contains_all_match(self, sample_transcript: str) -> None:
        """Test string_contains with all patterns matching."""
        env = {"work_dir": "/tmp"}
        config = {
            "target": "transcript",
            "patterns": ["output.py", "process_data", "tests pass"],
            "match_all": True,
        }

        result = grade_string_contains(sample_transcript, env, config)

        assert result["type"] == "string_contains"
        assert result["passed"] is True
        assert result["score"] == 1.0
        assert len(result["matched"]) == 3
        assert len(result["missing"]) == 0

    def test_grade_string_contains_partial(self, sample_transcript_partial: str) -> None:
        """Test string_contains with partial pattern matching."""
        env = {"work_dir": "/tmp"}
        config = {
            "target": "transcript",
            "patterns": ["output.py", "process_data", "tests pass", "100% coverage"],
            "match_all": True,
        }

        result = grade_string_contains(sample_transcript_partial, env, config)

        assert result["type"] == "string_contains"
        assert result["passed"] is False
        assert result["score"] == 0.5  # 2/4 patterns matched
        assert len(result["matched"]) == 2
        assert len(result["missing"]) == 2
        assert "tests pass" in result["missing"]
        assert "100% coverage" in result["missing"]

    def test_grade_string_contains_match_any(self) -> None:
        """Test string_contains with match_all=False (any match passes)."""
        transcript = "The golang-general-engineer processed the request."
        env = {"work_dir": "/tmp"}
        config = {
            "target": "transcript",
            "patterns": ["python-engineer", "golang-general-engineer", "rust-engineer"],
            "match_all": False,
        }

        result = grade_string_contains(transcript, env, config)

        assert result["passed"] is True
        assert result["score"] == 1.0

    def test_grade_string_contains_no_match(self) -> None:
        """Test string_contains with no patterns matching."""
        transcript = "An error occurred during processing."
        env = {"work_dir": "/tmp"}
        config = {
            "target": "transcript",
            "patterns": ["success", "completed", "passed"],
            "match_all": True,
        }

        result = grade_string_contains(transcript, env, config)

        assert result["passed"] is False
        assert result["score"] == 0.0
        assert len(result["missing"]) == 3

    def test_grade_string_contains_from_file(self, tmp_work_dir: Path) -> None:
        """Test string_contains reading content from a file."""
        output_file = tmp_work_dir / "output.txt"
        output_file.write_text("SUCCESS: All operations completed. Tests pass.")

        env = {"work_dir": str(tmp_work_dir)}
        config = {
            "target": "file:output.txt",
            "patterns": ["SUCCESS", "Tests pass"],
            "match_all": True,
        }

        result = grade_string_contains("", env, config)

        assert result["passed"] is True
        assert result["score"] == 1.0

    def test_grade_string_contains_file_not_found(self, tmp_work_dir: Path) -> None:
        """Test string_contains when target file doesn't exist."""
        env = {"work_dir": str(tmp_work_dir)}
        config = {
            "target": "file:missing.txt",
            "patterns": ["anything"],
            "match_all": True,
        }

        result = grade_string_contains("", env, config)

        assert result["passed"] is False
        assert result["score"] == 0.0
        assert "not found" in result["details"]

    def test_grade_string_contains_empty_patterns(self) -> None:
        """Test string_contains with empty pattern list."""
        env = {"work_dir": "/tmp"}
        config = {"target": "transcript", "patterns": [], "match_all": True}

        result = grade_string_contains("Any transcript content", env, config)

        assert result["passed"] is True
        assert result["score"] == 1.0  # No patterns = automatic pass


# ============================================================================
# Grader Unit Tests: regex_match
# ============================================================================


class TestGradeRegexMatch:
    """Tests for the regex_match grader."""

    def test_grade_regex_match_success(self, sample_transcript: str) -> None:
        """Test regex_match with a matching pattern."""
        env = {"work_dir": "/tmp"}
        config = {"target": "transcript", "pattern": r"output\.py"}

        result = grade_regex_match(sample_transcript, env, config)

        assert result["type"] == "regex_match"
        assert result["passed"] is True
        assert result["score"] == 1.0

    def test_grade_regex_match_fail(self) -> None:
        """Test regex_match with non-matching pattern."""
        transcript = "No special patterns here."
        env = {"work_dir": "/tmp"}
        config = {"target": "transcript", "pattern": r"\d{3}-\d{3}-\d{4}"}

        result = grade_regex_match(transcript, env, config)

        assert result["type"] == "regex_match"
        assert result["passed"] is False
        assert result["score"] == 0.0

    def test_grade_regex_match_complex_pattern(self) -> None:
        """Test regex_match with complex pattern."""
        transcript = "Agent: golang-general-engineer v2.1.0 selected"
        env = {"work_dir": "/tmp"}
        config = {
            "target": "transcript",
            "pattern": r"(golang|python|typescript)-[a-z]+-engineer",
        }

        result = grade_regex_match(transcript, env, config)

        assert result["passed"] is True
        assert result["score"] == 1.0

    def test_grade_regex_match_invalid_regex(self) -> None:
        """Test regex_match with invalid regex pattern."""
        env = {"work_dir": "/tmp"}
        config = {"target": "transcript", "pattern": r"[invalid(regex"}

        result = grade_regex_match("any transcript", env, config)

        assert result["passed"] is False
        assert result["score"] == 0.0
        assert "invalid pattern" in result["details"]

    def test_grade_regex_match_multiline(self) -> None:
        """Test regex_match with multiline content."""
        transcript = """Line 1: Start
Line 2: ERROR: Something went wrong
Line 3: End"""
        env = {"work_dir": "/tmp"}
        config = {"target": "transcript", "pattern": r"^Line 2: ERROR:"}

        result = grade_regex_match(transcript, env, config)

        assert result["passed"] is True

    def test_grade_regex_match_from_file(self, tmp_work_dir: Path) -> None:
        """Test regex_match reading from a file."""
        log_file = tmp_work_dir / "build.log"
        log_file.write_text("Build completed at 2024-01-15 10:30:45 with status SUCCESS")

        env = {"work_dir": str(tmp_work_dir)}
        config = {"target": "file:build.log", "pattern": r"\d{4}-\d{2}-\d{2}.*SUCCESS"}

        result = grade_regex_match("", env, config)

        assert result["passed"] is True


# ============================================================================
# Grader Unit Tests: yaml_valid
# ============================================================================


class TestGradeYamlValid:
    """Tests for the yaml_valid grader."""

    def test_grade_yaml_valid_frontmatter(self, sample_md_with_frontmatter: Path, tmp_work_dir: Path) -> None:
        """Test yaml_valid with markdown file containing valid frontmatter."""
        env = {"work_dir": str(tmp_work_dir)}
        config = {"path": sample_md_with_frontmatter.name, "required_fields": ["name", "version"]}

        result = grade_yaml_valid("", env, config)

        assert result["type"] == "yaml_valid"
        assert result["passed"] is True
        assert result["score"] == 1.0

    def test_grade_yaml_valid_missing_fields(self, sample_md_with_frontmatter: Path, tmp_work_dir: Path) -> None:
        """Test yaml_valid with missing required fields."""
        env = {"work_dir": str(tmp_work_dir)}
        config = {
            "path": sample_md_with_frontmatter.name,
            "required_fields": ["name", "version", "category", "tags"],  # category and tags don't exist
        }

        result = grade_yaml_valid("", env, config)

        assert result["passed"] is False
        assert result["score"] == 0.5  # 2/4 fields present
        assert "Missing required fields" in result["details"]

    def test_grade_yaml_valid_plain_yaml(self, sample_yaml_file: Path, tmp_work_dir: Path) -> None:
        """Test yaml_valid with plain YAML file (not markdown)."""
        env = {"work_dir": str(tmp_work_dir)}
        config = {"path": sample_yaml_file.name, "required_fields": ["name", "version", "settings"]}

        result = grade_yaml_valid("", env, config)

        assert result["passed"] is True
        assert result["score"] == 1.0

    def test_grade_yaml_valid_file_not_found(self, tmp_work_dir: Path) -> None:
        """Test yaml_valid when file doesn't exist."""
        env = {"work_dir": str(tmp_work_dir)}
        config = {"path": "nonexistent.yaml", "required_fields": ["name"]}

        result = grade_yaml_valid("", env, config)

        assert result["passed"] is False
        assert result["score"] == 0.0
        assert "not found" in result["details"]

    def test_grade_yaml_valid_invalid_yaml(self, tmp_work_dir: Path) -> None:
        """Test yaml_valid with invalid YAML content."""
        bad_yaml = tmp_work_dir / "bad.yaml"
        bad_yaml.write_text("invalid: yaml: content: [unclosed")

        env = {"work_dir": str(tmp_work_dir)}
        config = {"path": "bad.yaml", "required_fields": []}

        result = grade_yaml_valid("", env, config)

        assert result["passed"] is False
        assert result["score"] == 0.0
        assert "Invalid YAML" in result["details"]

    def test_grade_yaml_valid_no_frontmatter(self, tmp_work_dir: Path) -> None:
        """Test yaml_valid with markdown file missing frontmatter."""
        md_file = tmp_work_dir / "no_frontmatter.md"
        md_file.write_text("# Just a heading\n\nNo YAML frontmatter here.")

        env = {"work_dir": str(tmp_work_dir)}
        config = {"path": "no_frontmatter.md", "required_fields": ["name"]}

        result = grade_yaml_valid("", env, config)

        assert result["passed"] is False
        assert "No YAML frontmatter found" in result["details"]

    def test_grade_yaml_valid_not_dict(self, tmp_work_dir: Path) -> None:
        """Test yaml_valid when YAML parses to non-dict."""
        list_yaml = tmp_work_dir / "list.yaml"
        list_yaml.write_text("- item1\n- item2\n- item3")

        env = {"work_dir": str(tmp_work_dir)}
        config = {"path": "list.yaml", "required_fields": []}

        result = grade_yaml_valid("", env, config)

        assert result["passed"] is False
        assert result["score"] == 0.5
        assert "not a dictionary" in result["details"]


# ============================================================================
# Score Computation Tests
# ============================================================================


class TestComputeWeightedScore:
    """Tests for compute_weighted_score function."""

    def test_compute_weighted_score_all_pass(self) -> None:
        """Test weighted score with all graders passing."""
        grades = [
            {"score": 1.0, "weight": 1.0},
            {"score": 1.0, "weight": 1.0},
            {"score": 1.0, "weight": 1.0},
        ]
        assert compute_weighted_score(grades) == 1.0

    def test_compute_weighted_score_all_fail(self) -> None:
        """Test weighted score with all graders failing."""
        grades = [
            {"score": 0.0, "weight": 1.0},
            {"score": 0.0, "weight": 1.0},
        ]
        assert compute_weighted_score(grades) == 0.0

    def test_compute_weighted_score_mixed(self) -> None:
        """Test weighted score with mixed results."""
        grades = [
            {"score": 1.0, "weight": 1.0},
            {"score": 0.5, "weight": 1.0},
            {"score": 0.0, "weight": 1.0},
        ]
        assert compute_weighted_score(grades) == 0.5

    def test_compute_weighted_score_different_weights(self) -> None:
        """Test weighted score with different weights."""
        grades = [
            {"score": 1.0, "weight": 2.0},  # 2.0
            {"score": 0.5, "weight": 2.0},  # 1.0
            {"score": 0.0, "weight": 1.0},  # 0.0
        ]
        # Total weight: 5.0, weighted sum: 3.0
        assert compute_weighted_score(grades) == 0.6

    def test_compute_weighted_score_empty(self) -> None:
        """Test weighted score with empty grades list."""
        assert compute_weighted_score([]) == 0.0

    def test_compute_weighted_score_zero_weight(self) -> None:
        """Test weighted score when all weights are zero."""
        grades = [{"score": 1.0, "weight": 0.0}, {"score": 0.5, "weight": 0.0}]
        assert compute_weighted_score(grades) == 0.0

    def test_compute_weighted_score_missing_weight(self) -> None:
        """Test weighted score uses default weight of 1.0."""
        grades = [{"score": 1.0}, {"score": 0.0}]  # No weight specified
        assert compute_weighted_score(grades) == 0.5


# ============================================================================
# Token Extraction Tests
# ============================================================================


class TestExtractTokenUsage:
    """Tests for extract_token_usage function."""

    def test_extract_token_usage_newline_delimited(self, mock_claude_json_output: str) -> None:
        """Test token extraction from newline-delimited JSON."""
        tokens = extract_token_usage(mock_claude_json_output)

        assert tokens["tokens_input"] == 1500
        assert tokens["tokens_output"] == 500
        assert tokens["tokens_cache_read"] == 100
        assert tokens["tokens_cache_creation"] == 50
        assert tokens["tokens_total"] == 2150
        assert tokens["cost_usd"] == 0.025

    def test_extract_token_usage_array_format(self, mock_claude_json_output_array: str) -> None:
        """Test token extraction from JSON array format."""
        tokens = extract_token_usage(mock_claude_json_output_array)

        assert tokens["tokens_input"] == 1000
        assert tokens["tokens_output"] == 300
        assert tokens["cost_usd"] == 0.015

    def test_extract_token_usage_invalid_json(self) -> None:
        """Test token extraction with invalid JSON returns zeros."""
        tokens = extract_token_usage("not valid json at all")

        assert tokens["tokens_input"] == 0
        assert tokens["tokens_output"] == 0
        assert tokens["tokens_total"] == 0
        assert tokens["cost_usd"] == 0.0

    def test_extract_token_usage_empty(self) -> None:
        """Test token extraction with empty string."""
        tokens = extract_token_usage("")

        assert tokens["tokens_total"] == 0


class TestExtractTranscriptFromJson:
    """Tests for extract_transcript_from_json function."""

    def test_extract_transcript_newline_delimited(self, mock_claude_json_output: str) -> None:
        """Test transcript extraction from newline-delimited JSON."""
        transcript = extract_transcript_from_json(mock_claude_json_output)

        assert "Processing your request" in transcript
        assert "Task completed successfully" in transcript

    def test_extract_transcript_array_format(self, mock_claude_json_output_array: str) -> None:
        """Test transcript extraction from JSON array format."""
        transcript = extract_transcript_from_json(mock_claude_json_output_array)

        assert "Processing your request" in transcript

    def test_extract_transcript_invalid_json(self) -> None:
        """Test transcript extraction with invalid JSON returns empty."""
        transcript = extract_transcript_from_json("invalid json")

        assert transcript == ""


# ============================================================================
# Integration Tests
# ============================================================================


class TestRunTask:
    """Integration tests for run_task function."""

    @patch("harness.execute_agent")
    def test_run_task_basic(self, mock_execute: MagicMock, sample_task_file: Path) -> None:
        """Test basic task execution flow with mocked agent."""
        # Mock the agent execution to return a successful transcript
        mock_execute.return_value = {
            "success": True,
            "transcript": "Task completed with test and success patterns.",
            "raw_json_output": "",
            "stderr": "",
            "elapsed_seconds": 5.0,
            "exit_code": 0,
            "tokens_input": 100,
            "tokens_output": 50,
            "tokens_cache_read": 0,
            "tokens_cache_creation": 0,
            "tokens_total": 150,
            "cost_usd": 0.001,
            # V2 metrics from Anthropic eval article
            "n_turns": 1,
            "n_tool_calls": 0,
            "tool_calls_by_name": {},
            "first_response_time_ms": 100,
            "output_tokens_per_sec": 50.0,
        }

        result = run_task(str(sample_task_file), trial_num=0)

        assert result["task_id"] == "test-task-001"
        assert result["success"] is True
        assert result["score"] == 1.0
        assert result["passed"] is True
        assert len(result["grades"]) == 1
        assert result["grades"][0]["type"] == "string_contains"
        mock_execute.assert_called_once()

    @patch("harness.execute_agent")
    def test_run_task_failed_grading(self, mock_execute: MagicMock, sample_task_file: Path) -> None:
        """Test task execution where grading fails."""
        mock_execute.return_value = {
            "success": True,
            "transcript": "This transcript has neither required pattern.",
            "raw_json_output": "",
            "stderr": "",
            "elapsed_seconds": 3.0,
            "exit_code": 0,
            "tokens_input": 100,
            "tokens_output": 50,
            "tokens_cache_read": 0,
            "tokens_cache_creation": 0,
            "tokens_total": 150,
            "cost_usd": 0.001,
            # V2 metrics
            "n_turns": 1,
            "n_tool_calls": 0,
            "tool_calls_by_name": {},
            "first_response_time_ms": 80,
            "output_tokens_per_sec": 40.0,
        }

        result = run_task(str(sample_task_file), trial_num=0)

        assert result["success"] is True  # Execution succeeded
        assert result["score"] == 0.0  # But grading failed
        assert result["passed"] is False


class TestRunSuite:
    """Integration tests for run_suite function."""

    @patch("harness.run_task")
    def test_run_suite_single_task(self, mock_run_task: MagicMock, tmp_work_dir: Path) -> None:
        """Test running a suite with a single task."""
        # Create a task file
        task_content = {
            "task": {
                "id": "suite-task-001",
                "name": "Suite Test Task",
                "type": "capability",
                "input": {"prompt": "Test", "context_files": [], "setup_commands": []},
                "execution": {"timeout_seconds": 60},
                "graders": [],
            }
        }
        task_file = tmp_work_dir / "task-001.yaml"
        with task_file.open("w") as f:
            yaml.dump(task_content, f)

        # Mock run_task to return a successful result
        mock_run_task.return_value = {
            "task_id": "suite-task-001",
            "task_name": "Suite Test Task",
            "trial": 0,
            "success": True,
            "score": 0.85,
            "passed": True,
            "grades": [],
            "metrics": {
                "elapsed_seconds": 5.0,
                "exit_code": 0,
                "tokens_input": 100,
                "tokens_output": 50,
                "tokens_cache_read": 0,
                "tokens_cache_creation": 0,
                "tokens_total": 150,
                "cost_usd": 0.001,
                # V2 metrics
                "n_turns": 2,
                "n_tool_calls": 3,
                "tool_calls_by_name": {"Read": 2, "Edit": 1},
                "first_response_time_ms": 150,
                "output_tokens_per_sec": 45.0,
            },
            "transcript_preview": "Test output",
            "timestamp": "2024-01-15T10:00:00",
        }

        result = run_suite(str(tmp_work_dir), num_trials=1)

        assert result["summary"]["total_tasks"] == 1
        assert result["summary"]["passed_any"] == 1
        assert result["summary"]["avg_score"] == 0.85
        mock_run_task.assert_called_once()

    @patch("harness.run_task")
    def test_run_suite_multiple_trials(self, mock_run_task: MagicMock, tmp_work_dir: Path) -> None:
        """Test running a suite with multiple trials per task."""
        task_content = {
            "task": {
                "id": "multi-trial-task",
                "name": "Multi Trial Task",
                "type": "capability",
                "input": {"prompt": "Test", "context_files": [], "setup_commands": []},
                "execution": {"timeout_seconds": 60},
                "graders": [],
            }
        }
        task_file = tmp_work_dir / "task-001.yaml"
        with task_file.open("w") as f:
            yaml.dump(task_content, f)

        # Mock varying results across trials
        # All mocks include V2 metrics fields
        base_metrics = {
            "elapsed_seconds": 5.0,
            "exit_code": 0,
            "tokens_input": 100,
            "tokens_output": 50,
            "tokens_cache_read": 0,
            "tokens_cache_creation": 0,
            "tokens_total": 150,
            "cost_usd": 0.001,
            "n_turns": 1,
            "n_tool_calls": 2,
            "tool_calls_by_name": {"Read": 1, "Edit": 1},
            "first_response_time_ms": 100,
            "output_tokens_per_sec": 50.0,
        }
        mock_run_task.side_effect = [
            {
                "task_id": "multi-trial-task",
                "task_name": "Multi Trial Task",
                "trial": 0,
                "success": True,
                "score": 0.8,
                "passed": True,
                "grades": [],
                "metrics": base_metrics,
                "transcript_preview": "",
                "timestamp": "2024-01-15T10:00:00",
            },
            {
                "task_id": "multi-trial-task",
                "task_name": "Multi Trial Task",
                "trial": 1,
                "success": True,
                "score": 0.6,
                "passed": False,
                "grades": [],
                "metrics": base_metrics,
                "transcript_preview": "",
                "timestamp": "2024-01-15T10:00:01",
            },
            {
                "task_id": "multi-trial-task",
                "task_name": "Multi Trial Task",
                "trial": 2,
                "success": True,
                "score": 0.9,
                "passed": True,
                "grades": [],
                "metrics": base_metrics,
                "transcript_preview": "",
                "timestamp": "2024-01-15T10:00:02",
            },
        ]

        result = run_suite(str(tmp_work_dir), num_trials=3)

        assert result["summary"]["total_tasks"] == 1
        assert result["summary"]["passed_any"] == 1  # pass@k: at least one passed
        assert result["summary"]["passed_all"] == 0  # pass^k: not all passed
        assert result["results"][0]["pass_rate"] == pytest.approx(2 / 3)
        assert mock_run_task.call_count == 3


# ============================================================================
# Calibration Tests
# ============================================================================


class TestCalibration:
    """Tests for grader calibration functionality."""

    def test_load_calibration_examples(self) -> None:
        """Test loading calibration examples from file."""
        # This test assumes calibration data exists
        try:
            examples = load_calibration_examples("string_contains")
            assert isinstance(examples, list)
            assert len(examples) > 0
            assert "id" in examples[0]
            assert "input" in examples[0]
            assert "expected" in examples[0]
        except FileNotFoundError:
            pytest.skip("No calibration data for string_contains")

    def test_load_calibration_examples_not_found(self) -> None:
        """Test loading calibration examples for non-existent grader."""
        with pytest.raises(FileNotFoundError):
            load_calibration_examples("nonexistent_grader_type")

    def test_run_calibration_example(self) -> None:
        """Test running a single calibration example."""
        example = {
            "id": "test-cal-001",
            "description": "All patterns present",
            "input": {
                "transcript": "Created main.py with process_data function.",
                "config": {
                    "target": "transcript",
                    "patterns": ["main.py", "process_data"],
                    "match_all": True,
                },
            },
            "expected": {"passed": True, "score": 1.0},
        }

        result = run_calibration_example("string_contains", example)

        assert result["example_id"] == "test-cal-001"
        assert result["actual"]["passed"] is True
        assert result["actual"]["score"] == 1.0
        assert result["aligned"] is True

    def test_run_calibration_example_misaligned(self) -> None:
        """Test calibration example that doesn't match expected."""
        example = {
            "id": "test-cal-002",
            "description": "Should fail but expects pass",
            "input": {
                "transcript": "No matching patterns here.",
                "config": {
                    "target": "transcript",
                    "patterns": ["main.py", "process_data"],
                    "match_all": True,
                },
            },
            "expected": {"passed": True, "score": 1.0},  # Wrong expectation
        }

        result = run_calibration_example("string_contains", example)

        assert result["actual"]["passed"] is False
        assert result["actual"]["score"] == 0.0
        assert result["aligned"] is False

    def test_run_calibration_example_unknown_grader(self) -> None:
        """Test calibration with unknown grader type."""
        example = {"id": "test", "input": {}, "expected": {}}

        result = run_calibration_example("unknown_grader", example)

        assert result["aligned"] is False
        assert "error" in result

    def test_run_calibration_example_range_scoring(self) -> None:
        """Test calibration with score range (for LLM graders with variance)."""
        example = {
            "id": "test-range-001",
            "description": "Partial match with range expectation",
            "input": {
                "transcript": "Created main.py but no function defined.",
                "config": {
                    "target": "transcript",
                    "patterns": ["main.py", "process_data"],
                    "match_all": True,
                },
            },
            "expected": {
                "passed": False,
                "score_min": 0.4,
                "score_max": 0.6,  # 0.5 is in range
            },
        }

        result = run_calibration_example("string_contains", example)

        assert result["actual"]["score"] == 0.5
        assert result["aligned"] is True
        assert result["score_deviation"] == 0.0


# ============================================================================
# Environment Setup Tests
# ============================================================================


class TestEnvironmentSetup:
    """Tests for environment setup and cleanup."""

    def test_setup_environment_basic(self) -> None:
        """Test basic environment setup creates temp directory."""
        task = {"input": {"setup_commands": [], "context_files": []}}

        env = setup_environment(task)

        try:
            assert "work_dir" in env
            assert Path(env["work_dir"]).exists()
            assert Path(env["work_dir"]).is_dir()
        finally:
            cleanup_environment(env)

    def test_setup_environment_with_setup_commands(self) -> None:
        """Test environment setup runs setup commands."""
        task = {
            "input": {
                "setup_commands": ["mkdir -p src", "touch src/main.py"],
                "context_files": [],
            }
        }

        env = setup_environment(task)

        try:
            work_dir = Path(env["work_dir"])
            assert (work_dir / "src").exists()
            assert (work_dir / "src" / "main.py").exists()
        finally:
            cleanup_environment(env)

    def test_cleanup_environment(self) -> None:
        """Test environment cleanup removes temp directory."""
        task = {"input": {"setup_commands": [], "context_files": []}}

        env = setup_environment(task)
        work_dir = Path(env["work_dir"])
        assert work_dir.exists()

        cleanup_environment(env)

        assert not work_dir.exists()


# ============================================================================
# Run Graders Tests
# ============================================================================


class TestRunGraders:
    """Tests for run_graders function."""

    def test_run_graders_single_grader(self, tmp_work_dir: Path) -> None:
        """Test running a single grader."""
        task = {
            "graders": [
                {
                    "type": "string_contains",
                    "config": {"target": "transcript", "patterns": ["success"], "match_all": True},
                    "weight": 1.0,
                }
            ]
        }
        env = {"work_dir": str(tmp_work_dir)}
        transcript = "Operation completed with success."

        results = run_graders(task, transcript, env)

        assert len(results) == 1
        assert results[0]["type"] == "string_contains"
        assert results[0]["passed"] is True
        assert results[0]["weight"] == 1.0

    def test_run_graders_multiple_graders(self, tmp_work_dir: Path) -> None:
        """Test running multiple graders."""
        # Create a file for file_exists grader
        (tmp_work_dir / "output.txt").write_text("test")

        task = {
            "graders": [
                {
                    "type": "string_contains",
                    "config": {"target": "transcript", "patterns": ["completed"], "match_all": True},
                    "weight": 0.5,
                },
                {
                    "type": "file_exists",
                    "config": {"path": "output.txt"},
                    "weight": 0.5,
                },
            ]
        }
        env = {"work_dir": str(tmp_work_dir)}
        transcript = "Task completed."

        results = run_graders(task, transcript, env)

        assert len(results) == 2
        assert all(r["passed"] for r in results)
        assert compute_weighted_score(results) == 1.0

    def test_run_graders_unknown_type(self, tmp_work_dir: Path) -> None:
        """Test handling of unknown grader type."""
        task = {
            "graders": [
                {
                    "type": "unknown_grader_type",
                    "config": {},
                    "weight": 1.0,
                }
            ]
        }
        env = {"work_dir": str(tmp_work_dir)}

        results = run_graders(task, "any transcript", env)

        assert len(results) == 1
        assert results[0]["passed"] is False
        assert "Unknown grader type" in results[0]["details"]


# ============================================================================
# GRADERS Registry Tests
# ============================================================================


class TestGradersRegistry:
    """Tests for the GRADERS registry."""

    def test_graders_registry_contains_expected(self) -> None:
        """Test that GRADERS registry contains expected grader types."""
        expected_graders = [
            "file_exists",
            "string_contains",
            "regex_match",
            "tests_pass",
            "yaml_valid",
            "llm_rubric",
            "agent_evaluator",
        ]

        for grader in expected_graders:
            assert grader in GRADERS, f"Missing grader: {grader}"

    def test_graders_are_callable(self) -> None:
        """Test that all registered graders are callable."""
        for name, grader_fn in GRADERS.items():
            assert callable(grader_fn), f"Grader {name} is not callable"

    def test_v2_graders_in_registry(self) -> None:
        """Test that V2 graders from Anthropic eval article are registered."""
        v2_graders = [
            "tool_calls",
            "state_check",
            "transcript_constraint",
        ]
        for grader in v2_graders:
            assert grader in GRADERS, f"Missing V2 grader: {grader}"


# ============================================================================
# V2 Grader Tests: tool_calls
# ============================================================================


class TestGradeToolCalls:
    """Tests for the tool_calls grader (V2 - Anthropic eval article)."""

    def test_tool_calls_required_present(self, tmp_work_dir: Path) -> None:
        """Test tool_calls grader when required tools are present."""

        # Simulate raw JSON with tool calls
        raw_json = """
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "/test.py"}},
            {"type": "tool_use", "name": "Edit", "input": {"file_path": "/test.py", "old_string": "a", "new_string": "b"}}
        ]}}
        """
        env = {"work_dir": str(tmp_work_dir), "raw_json_output": raw_json}
        config = {"required_tools": ["Read", "Edit"]}

        result = grade_tool_calls("", env, config)

        assert result["type"] == "tool_calls"
        assert result["passed"] is True
        assert result["score"] == 1.0
        assert "Read" in result["tool_calls_found"]
        assert "Edit" in result["tool_calls_found"]
        assert result["num_calls"] == 2

    def test_tool_calls_required_missing(self, tmp_work_dir: Path) -> None:
        """Test tool_calls grader when required tools are missing."""

        raw_json = """
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "/test.py"}}
        ]}}
        """
        env = {"work_dir": str(tmp_work_dir), "raw_json_output": raw_json}
        config = {"required_tools": ["Read", "Edit", "Bash"]}

        result = grade_tool_calls("", env, config)

        assert result["passed"] is False
        assert result["score"] < 1.0
        assert "Missing required tools" in result["details"]

    def test_tool_calls_forbidden_used(self, tmp_work_dir: Path) -> None:
        """Test tool_calls grader when forbidden tools are used."""

        raw_json = """
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": "rm -rf /"}}
        ]}}
        """
        env = {"work_dir": str(tmp_work_dir), "raw_json_output": raw_json}
        config = {"forbidden_tools": ["Bash"]}

        result = grade_tool_calls("", env, config)

        assert result["passed"] is False
        assert "Called forbidden tools" in result["details"]

    def test_tool_calls_count_bounds(self, tmp_work_dir: Path) -> None:
        """Test tool_calls grader with min/max bounds."""

        raw_json = """
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {}}
        ]}}
        """
        env = {"work_dir": str(tmp_work_dir), "raw_json_output": raw_json}
        config = {"min_tool_calls": 3}

        result = grade_tool_calls("", env, config)

        assert result["passed"] is False
        assert "Too few tool calls" in result["details"]

    def test_tool_calls_empty_transcript(self, tmp_work_dir: Path) -> None:
        """Test tool_calls grader with no tool calls."""

        env = {"work_dir": str(tmp_work_dir), "raw_json_output": ""}
        config = {"required_tools": []}

        result = grade_tool_calls("No tools used", env, config)

        assert result["passed"] is True
        assert result["num_calls"] == 0


# ============================================================================
# V2 Grader Tests: state_check
# ============================================================================


class TestGradeStateCheck:
    """Tests for the state_check grader (V2 - Anthropic eval article)."""

    def test_state_check_files_exist(self, tmp_work_dir: Path) -> None:
        """Test state_check grader verifies file existence."""

        # Create expected files
        (tmp_work_dir / "output.py").write_text("print('hello')")
        (tmp_work_dir / "tests").mkdir()
        (tmp_work_dir / "tests" / "test_output.py").write_text("def test_x(): pass")

        env = {"work_dir": str(tmp_work_dir)}
        config = {"files_exist": ["output.py", "tests/test_output.py"]}

        result = grade_state_check("", env, config)

        assert result["type"] == "state_check"
        assert result["passed"] is True
        assert result["score"] == 1.0
        assert result["checks_passed"] == 2
        assert result["total_checks"] == 2

    def test_state_check_files_not_exist(self, tmp_work_dir: Path) -> None:
        """Test state_check grader verifies files don't exist."""

        # Create a file that should NOT exist
        (tmp_work_dir / "temp.py").write_text("temporary")

        env = {"work_dir": str(tmp_work_dir)}
        config = {"files_not_exist": ["temp.py", "cache.json"]}

        result = grade_state_check("", env, config)

        assert result["passed"] is False
        assert "File should not exist: temp.py" in result["issues"]
        assert result["checks_passed"] == 1  # cache.json doesn't exist (correct)
        assert result["total_checks"] == 2

    def test_state_check_file_contains(self, tmp_work_dir: Path) -> None:
        """Test state_check grader verifies file contents."""

        (tmp_work_dir / "main.py").write_text("""
def main():
    print("Hello World")

if __name__ == "__main__":
    main()
""")

        env = {"work_dir": str(tmp_work_dir)}
        config = {
            "file_contains": {
                "main.py": [
                    r"def main\(\)",
                    r"__name__.*__main__",
                ]
            }
        }

        result = grade_state_check("", env, config)

        assert result["passed"] is True
        assert result["score"] == 1.0

    def test_state_check_file_not_contains(self, tmp_work_dir: Path) -> None:
        """Test state_check grader verifies forbidden content."""

        (tmp_work_dir / "secure.py").write_text("password = 'secret123'")

        env = {"work_dir": str(tmp_work_dir)}
        config = {"file_not_contains": {"secure.py": ["password.*=", "secret"]}}

        result = grade_state_check("", env, config)

        assert result["passed"] is False
        assert any("Forbidden pattern found" in issue for issue in result["issues"])

    def test_state_check_no_config(self, tmp_work_dir: Path) -> None:
        """Test state_check grader with empty config passes."""

        env = {"work_dir": str(tmp_work_dir)}
        config = {}

        result = grade_state_check("", env, config)

        assert result["passed"] is True
        assert result["score"] == 1.0


# ============================================================================
# V2 Grader Tests: transcript_constraint
# ============================================================================


class TestGradeTranscriptConstraint:
    """Tests for the transcript_constraint grader (V2 - Anthropic eval article)."""

    def test_transcript_constraint_max_turns(self, tmp_work_dir: Path) -> None:
        """Test transcript_constraint grader enforces max turns."""

        env = {
            "work_dir": str(tmp_work_dir),
            "n_turns": 10,
            "n_tool_calls": 5,
            "tokens_total": 1000,
            "elapsed_seconds": 30,
        }
        config = {"max_turns": 5}

        result = grade_transcript_constraint("", env, config)

        assert result["type"] == "transcript_constraint"
        assert result["passed"] is False
        assert "Too many turns: 10 > 5" in result["details"]

    def test_transcript_constraint_max_tool_calls(self, tmp_work_dir: Path) -> None:
        """Test transcript_constraint grader enforces max tool calls."""

        env = {
            "work_dir": str(tmp_work_dir),
            "n_turns": 2,
            "n_tool_calls": 50,
            "tokens_total": 5000,
            "elapsed_seconds": 60,
        }
        config = {"max_tool_calls": 20}

        result = grade_transcript_constraint("", env, config)

        assert result["passed"] is False
        assert "Too many tool calls: 50 > 20" in result["details"]

    def test_transcript_constraint_forbidden_patterns(self, tmp_work_dir: Path) -> None:
        """Test transcript_constraint grader detects forbidden patterns."""

        transcript = "I don't know how to do that. Let me try something else."
        env = {
            "work_dir": str(tmp_work_dir),
            "n_turns": 1,
            "n_tool_calls": 1,
            "tokens_total": 100,
            "elapsed_seconds": 5,
        }
        config = {"forbidden_patterns": ["I don't know", "I cannot"]}

        result = grade_transcript_constraint(transcript, env, config)

        assert result["passed"] is False
        assert any("Forbidden pattern found" in issue for issue in result["issues"])

    def test_transcript_constraint_required_patterns(self, tmp_work_dir: Path) -> None:
        """Test transcript_constraint grader verifies required patterns."""

        transcript = "Task started. Working on it..."
        env = {
            "work_dir": str(tmp_work_dir),
            "n_turns": 1,
            "n_tool_calls": 1,
            "tokens_total": 100,
            "elapsed_seconds": 5,
        }
        config = {"required_patterns": ["completed successfully", "Task finished"]}

        result = grade_transcript_constraint(transcript, env, config)

        assert result["passed"] is False
        assert any("Required pattern missing" in issue for issue in result["issues"])

    def test_transcript_constraint_all_pass(self, tmp_work_dir: Path) -> None:
        """Test transcript_constraint grader when all constraints pass."""

        transcript = "Task completed successfully!"
        env = {
            "work_dir": str(tmp_work_dir),
            "n_turns": 2,
            "n_tool_calls": 5,
            "tokens_total": 500,
            "elapsed_seconds": 10,
        }
        config = {
            "max_turns": 5,
            "max_tool_calls": 10,
            "max_tokens": 1000,
            "required_patterns": ["completed successfully"],
        }

        result = grade_transcript_constraint(transcript, env, config)

        assert result["passed"] is True
        assert result["score"] == 1.0


# ============================================================================
# V2 Metrics Tests: extract_transcript_metrics
# ============================================================================


class TestExtractTranscriptMetrics:
    """Tests for extract_transcript_metrics function (V2 - Anthropic eval article)."""

    def test_extract_transcript_metrics_basic(self) -> None:
        """Test basic transcript metrics extraction."""

        json_output = """
{"type": "user", "timestamp": "2024-01-01T10:00:00Z"}
{"type": "assistant", "timestamp": "2024-01-01T10:00:01Z", "message": {"content": [{"type": "text", "text": "Hello"}]}}
{"type": "user", "timestamp": "2024-01-01T10:00:02Z"}
{"type": "assistant", "timestamp": "2024-01-01T10:00:03Z", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {}}]}}
{"type": "result", "usage": {"output_tokens": 100}, "duration_ms": 2000}
"""
        metrics = extract_transcript_metrics(json_output)

        assert metrics["n_turns"] == 2
        assert metrics["n_user_messages"] == 2
        assert metrics["n_assistant_messages"] == 2
        assert metrics["n_tool_calls"] == 1
        assert metrics["tool_calls_by_name"]["Read"] == 1
        assert metrics["output_tokens_per_sec"] == 50.0  # 100 tokens / 2 seconds

    def test_extract_transcript_metrics_multiple_tools(self) -> None:
        """Test transcript metrics with multiple tool calls."""
        # NDJSON format: one JSON object per line
        json_output = '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {}}, {"type": "tool_use", "name": "Read", "input": {}}, {"type": "tool_use", "name": "Edit", "input": {}}]}}\n{"type": "result", "usage": {"output_tokens": 500}}'

        metrics = extract_transcript_metrics(json_output)

        assert metrics["n_tool_calls"] == 3
        assert metrics["tool_calls_by_name"]["Read"] == 2
        assert metrics["tool_calls_by_name"]["Edit"] == 1

    def test_extract_transcript_metrics_empty(self) -> None:
        """Test transcript metrics with empty input."""

        metrics = extract_transcript_metrics("")

        assert metrics["n_turns"] == 0
        assert metrics["n_tool_calls"] == 0

    def test_extract_transcript_metrics_invalid_json(self) -> None:
        """Test transcript metrics with invalid JSON."""

        metrics = extract_transcript_metrics("not valid json")

        assert metrics["n_turns"] == 0
        assert metrics["n_tool_calls"] == 0


# ============================================================================
# Grader Unit Tests: tests_pass
# ============================================================================


class TestGradeTestsPass:
    """Tests for the tests_pass grader."""

    def test_tests_pass_success(self, tmp_work_dir: Path) -> None:
        """Test tests_pass grader with successful command."""
        env = {"work_dir": str(tmp_work_dir)}
        config = {"command": "echo 'tests passed'"}

        result = grade_tests_pass("", env, config)

        assert result["type"] == "tests_pass"
        assert result["passed"] is True
        assert result["score"] == 1.0
        assert "Exit code: 0" in result["details"]
        assert "tests passed" in result["stdout"]

    def test_tests_pass_failure(self, tmp_work_dir: Path) -> None:
        """Test tests_pass grader with failing command."""
        env = {"work_dir": str(tmp_work_dir)}
        config = {"command": "exit 1"}

        result = grade_tests_pass("", env, config)

        assert result["type"] == "tests_pass"
        assert result["passed"] is False
        assert result["score"] == 0.0
        assert "Exit code: 1" in result["details"]

    def test_tests_pass_timeout(self, tmp_work_dir: Path) -> None:
        """Test tests_pass grader with timeout."""
        env = {"work_dir": str(tmp_work_dir)}
        config = {"command": "sleep 10", "timeout": 1}

        result = grade_tests_pass("", env, config)

        assert result["passed"] is False
        assert result["score"] == 0.0
        assert "timed out" in result["details"]

    def test_tests_pass_working_dir(self, tmp_work_dir: Path) -> None:
        """Test tests_pass grader with custom working directory."""
        subdir = tmp_work_dir / "subdir"
        subdir.mkdir()
        (subdir / "test.txt").write_text("content")

        env = {"work_dir": str(tmp_work_dir)}
        config = {"command": "ls test.txt", "working_dir": "subdir"}

        result = grade_tests_pass("", env, config)

        assert result["passed"] is True
        assert "test.txt" in result["stdout"]

    def test_tests_pass_path_traversal(self, tmp_work_dir: Path) -> None:
        """Test tests_pass grader rejects path traversal in working_dir."""
        env = {"work_dir": str(tmp_work_dir)}
        config = {"command": "ls", "working_dir": "../../../etc"}

        result = grade_tests_pass("", env, config)

        assert result["passed"] is False
        assert "Invalid working_dir" in result["details"]


# ============================================================================
# V2 Grader Tests: tool_calls with tool_params
# ============================================================================


class TestGradeToolCallsParams:
    """Tests for the tool_calls grader tool_params config option."""

    def test_tool_params_match(self, tmp_work_dir: Path) -> None:
        """Test tool_calls grader with matching tool parameters."""
        raw_json = """
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Edit", "input": {"file_path": "/src/main.py", "old_string": "x", "new_string": "y"}}
        ]}}
        """
        env = {"work_dir": str(tmp_work_dir), "raw_json_output": raw_json}
        config = {
            "required_tools": ["Edit"],
            "tool_params": {"Edit": {"file_path": r".*\.py$"}},
        }

        result = grade_tool_calls("", env, config)

        assert result["passed"] is True
        assert result["score"] == 1.0

    def test_tool_params_no_match(self, tmp_work_dir: Path) -> None:
        """Test tool_calls grader with non-matching tool parameters."""
        raw_json = """
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Edit", "input": {"file_path": "/data/config.json"}}
        ]}}
        """
        env = {"work_dir": str(tmp_work_dir), "raw_json_output": raw_json}
        config = {
            "tool_params": {"Edit": {"file_path": r".*\.py$"}},
        }

        result = grade_tool_calls("", env, config)

        assert result["passed"] is False
        assert "doesn't match pattern" in result["details"]

    def test_tool_calls_json_array_format(self, tmp_work_dir: Path) -> None:
        """Test tool_calls grader with JSON array format input."""
        raw_json = """[
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/test.py"}},
                {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}
            ]}}
        ]"""
        env = {"work_dir": str(tmp_work_dir), "raw_json_output": raw_json}
        config = {"required_tools": ["Read", "Bash"]}

        result = grade_tool_calls("", env, config)

        assert result["passed"] is True
        assert result["num_calls"] == 2

    def test_tool_calls_max_tool_calls(self, tmp_work_dir: Path) -> None:
        """Test tool_calls grader with max_tool_calls constraint."""
        raw_json = """
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {}},
            {"type": "tool_use", "name": "Read", "input": {}},
            {"type": "tool_use", "name": "Read", "input": {}},
            {"type": "tool_use", "name": "Read", "input": {}},
            {"type": "tool_use", "name": "Read", "input": {}}
        ]}}
        """
        env = {"work_dir": str(tmp_work_dir), "raw_json_output": raw_json}
        config = {"max_tool_calls": 3}

        result = grade_tool_calls("", env, config)

        assert result["passed"] is False
        assert "Too many tool calls: 5 > 3" in result["details"]


# ============================================================================
# V2 Grader Tests: state_check with git_status
# ============================================================================


class TestGradeStateCheckGit:
    """Tests for the state_check grader git_status config option."""

    def test_git_status_pattern_match(self, tmp_work_dir: Path) -> None:
        """Test state_check grader with git status patterns."""
        # Initialize git repo for test
        import subprocess

        subprocess.run(["git", "init"], cwd=tmp_work_dir, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_work_dir,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_work_dir,
            capture_output=True,
        )

        # Create an untracked file
        (tmp_work_dir / "new_file.py").write_text("print('hello')")

        env = {"work_dir": str(tmp_work_dir)}
        config = {
            "git_status": {
                "patterns": [r"\?\? new_file\.py"],  # Untracked file pattern
            }
        }

        result = grade_state_check("", env, config)

        assert result["passed"] is True
        assert result["score"] == 1.0

    def test_git_status_not_a_repo(self, tmp_work_dir: Path) -> None:
        """Test state_check grader when directory is not a git repo."""
        env = {"work_dir": str(tmp_work_dir)}
        config = {
            "git_status": {
                "patterns": ["some pattern"],
            }
        }

        result = grade_state_check("", env, config)

        # Should fail because git status won't work in non-repo
        assert result["passed"] is False
        assert "Git status pattern not found" in str(result["issues"])


# ============================================================================
# Path Traversal Security Tests
# ============================================================================


class TestPathTraversalSecurity:
    """Tests for path traversal prevention in graders."""

    def test_file_exists_path_traversal(self, tmp_work_dir: Path) -> None:
        """Test file_exists grader blocks path traversal."""
        env = {"work_dir": str(tmp_work_dir)}
        config = {"path": "../../../etc/passwd"}

        result = grade_file_exists("", env, config)

        assert result["passed"] is False
        assert "Invalid path" in result["details"]

    def test_string_contains_file_path_traversal(self, tmp_work_dir: Path) -> None:
        """Test string_contains grader blocks path traversal in file target."""
        env = {"work_dir": str(tmp_work_dir)}
        config = {
            "target": "file:../../../etc/passwd",
            "patterns": ["root"],
        }

        result = grade_string_contains("", env, config)

        assert result["passed"] is False
        assert "Invalid path" in result["details"]

    def test_regex_match_file_path_traversal(self, tmp_work_dir: Path) -> None:
        """Test regex_match grader blocks path traversal."""
        env = {"work_dir": str(tmp_work_dir)}
        config = {"target": "file:../../etc/passwd", "pattern": ".*"}

        result = grade_regex_match("", env, config)

        assert result["passed"] is False
        assert "Invalid path" in result["details"]

    def test_yaml_valid_path_traversal(self, tmp_work_dir: Path) -> None:
        """Test yaml_valid grader blocks path traversal."""
        env = {"work_dir": str(tmp_work_dir)}
        config = {"path": "../../../etc/passwd", "required_fields": []}

        result = grade_yaml_valid("", env, config)

        assert result["passed"] is False
        assert "Invalid path" in result["details"]


# ============================================================================
# File Contains Edge Cases
# ============================================================================


class TestFileContainsEdgeCases:
    """Tests for file_contains edge cases in state_check grader."""

    def test_file_contains_missing_file(self, tmp_work_dir: Path) -> None:
        """Test state_check file_contains with missing file."""
        env = {"work_dir": str(tmp_work_dir)}
        config = {
            "file_contains": {
                "nonexistent.py": ["pattern1", "pattern2"],
            }
        }

        result = grade_state_check("", env, config)

        assert result["passed"] is False
        assert any("Cannot check pattern in missing file" in issue for issue in result["issues"])
        # Should track both patterns as failed checks
        assert result["total_checks"] == 2


# ============================================================================
# LLM Rubric Grader Tests
# ============================================================================


class TestGradeLlmRubric:
    """Tests for the llm_rubric grader with mocked subprocess."""

    def test_llm_rubric_successful_evaluation(self, tmp_work_dir: Path) -> None:
        """Test llm_rubric with successful LLM response."""
        from harness import grade_llm_rubric

        env = {"work_dir": str(tmp_work_dir)}
        config = {
            "assertions": ["Code includes error handling", "Function has docstring"],
        }
        transcript = "def example():\n    '''Docstring'''\n    try:\n        pass\n    except:\n        pass"

        mock_response = {
            "overall_pass": True,
            "score": 0.9,
            "summary": "Good code quality",
            "assertions": [
                {"assertion": "Code includes error handling", "passed": True, "reasoning": "Has try/except"},
                {"assertion": "Function has docstring", "passed": True, "reasoning": "Has docstring"},
            ],
        }

        with patch("harness.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_response), stderr="")

            result = grade_llm_rubric(transcript, env, config)

            assert result["type"] == "llm_rubric"
            assert result["passed"] is True
            assert result["score"] == 0.9
            assert "Good code quality" in result["details"]
            assert len(result["assertions"]) == 2

    def test_llm_rubric_failed_evaluation(self, tmp_work_dir: Path) -> None:
        """Test llm_rubric with failing LLM response."""
        from harness import grade_llm_rubric

        env = {"work_dir": str(tmp_work_dir)}
        config = {"assertions": ["Has unit tests"]}
        transcript = "def example(): pass"

        mock_response = {
            "overall_pass": False,
            "score": 0.0,
            "summary": "Missing unit tests",
            "assertions": [
                {"assertion": "Has unit tests", "passed": False, "reasoning": "No tests found"},
            ],
        }

        with patch("harness.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_response), stderr="")

            result = grade_llm_rubric(transcript, env, config)

            assert result["passed"] is False
            assert result["score"] == 0.0

    def test_llm_rubric_cli_failure(self, tmp_work_dir: Path) -> None:
        """Test llm_rubric when claude CLI fails."""
        from harness import grade_llm_rubric

        env = {"work_dir": str(tmp_work_dir)}
        config = {"assertions": ["test"]}

        with patch("harness.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="CLI error")

            result = grade_llm_rubric("transcript", env, config)

            assert result["passed"] is False
            assert "LLM grading failed" in result["details"]

    def test_llm_rubric_timeout(self, tmp_work_dir: Path) -> None:
        """Test llm_rubric timeout handling."""
        import subprocess

        from harness import grade_llm_rubric

        env = {"work_dir": str(tmp_work_dir)}
        config = {"assertions": ["test"]}

        with patch("harness.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("claude", 120)

            result = grade_llm_rubric("transcript", env, config)

            assert result["passed"] is False
            assert "timed out" in result["details"]

    def test_llm_rubric_invalid_json(self, tmp_work_dir: Path) -> None:
        """Test llm_rubric with invalid JSON response."""
        from harness import grade_llm_rubric

        env = {"work_dir": str(tmp_work_dir)}
        config = {"assertions": ["test"]}

        with patch("harness.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="not valid json {{{", stderr="")

            result = grade_llm_rubric("transcript", env, config)

            assert result["passed"] is False
            assert "Failed to parse" in result["details"]

    def test_llm_rubric_json_in_markdown_block(self, tmp_work_dir: Path) -> None:
        """Test llm_rubric extracts JSON from markdown code block."""
        from harness import grade_llm_rubric

        env = {"work_dir": str(tmp_work_dir)}
        config = {"assertions": ["test"]}

        mock_response = {"overall_pass": True, "score": 1.0, "summary": "Pass"}
        response_with_markdown = f"```json\n{json.dumps(mock_response)}\n```"

        with patch("harness.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=response_with_markdown, stderr="")

            result = grade_llm_rubric("transcript", env, config)

            assert result["passed"] is True
            assert result["score"] == 1.0


# ============================================================================
# Agent Evaluator Grader Tests
# ============================================================================


class TestGradeAgentEvaluator:
    """Tests for the agent_evaluator grader."""

    def test_agent_evaluator_reads_output_file(self, tmp_work_dir: Path) -> None:
        """Test agent_evaluator reads results from output file."""
        from harness import grade_agent_evaluator

        # Create the eval_grade.json file that the agent would write
        eval_result = {
            "overall_pass": True,
            "score": 0.85,
            "summary": "Good implementation",
            "assertions": [
                {"assertion": "test1", "passed": True, "reasoning": "OK"},
            ],
        }
        output_file = tmp_work_dir / "eval_grade.json"
        output_file.write_text(json.dumps(eval_result))

        env = {"work_dir": str(tmp_work_dir)}
        config = {
            "rubric": "Test rubric",
            "assertions": ["test1"],
        }

        result = grade_agent_evaluator("transcript", env, config)

        assert result["type"] == "agent_evaluator"
        assert result["passed"] is True
        assert result["score"] == 0.85
        assert "Good implementation" in result["details"]

    def test_agent_evaluator_no_output_file(self, tmp_work_dir: Path) -> None:
        """Test agent_evaluator returns fallback when no output file exists."""
        from harness import grade_agent_evaluator

        env = {"work_dir": str(tmp_work_dir)}
        config = {"assertions": ["test1"]}

        result = grade_agent_evaluator("transcript", env, config)

        assert result["passed"] is False
        assert "CLI mode" in result["details"]

    def test_agent_evaluator_invalid_json_in_file(self, tmp_work_dir: Path) -> None:
        """Test agent_evaluator handles malformed JSON in output file."""
        from harness import grade_agent_evaluator

        output_file = tmp_work_dir / "eval_grade.json"
        output_file.write_text("not valid json {{{")

        env = {"work_dir": str(tmp_work_dir)}
        config = {"assertions": ["test1"]}

        result = grade_agent_evaluator("transcript", env, config)

        assert result["passed"] is False
        assert "Failed to parse" in result["details"]

    def test_agent_evaluator_failed_assertion(self, tmp_work_dir: Path) -> None:
        """Test agent_evaluator with failed assertion."""
        from harness import grade_agent_evaluator

        eval_result = {
            "overall_pass": False,
            "score": 0.3,
            "summary": "Missing error handling",
            "assertions": [
                {"assertion": "Has error handling", "passed": False, "reasoning": "No try/except found"},
            ],
        }
        output_file = tmp_work_dir / "eval_grade.json"
        output_file.write_text(json.dumps(eval_result))

        env = {"work_dir": str(tmp_work_dir)}
        config = {"assertions": ["Has error handling"]}

        result = grade_agent_evaluator("transcript", env, config)

        assert result["passed"] is False
        assert result["score"] == 0.3
