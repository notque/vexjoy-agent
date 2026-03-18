"""Shared pytest fixtures for eval harness tests."""

import tempfile
from pathlib import Path
from typing import Generator

import pytest
import yaml


@pytest.fixture
def tmp_work_dir() -> Generator[Path, None, None]:
    """Create a temporary work directory for testing.

    Yields:
        Path to temporary directory that will be cleaned up after test.
    """
    with tempfile.TemporaryDirectory(prefix="eval_test_") as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_task_yaml() -> dict:
    """Sample task configuration for testing.

    Returns:
        Dictionary representing a minimal valid task configuration.
    """
    return {
        "task": {
            "id": "test-task-001",
            "name": "Test Task",
            "description": "A test task for unit testing",
            "category": "testing",
            "type": "capability",
            "input": {
                "prompt": "Test prompt for the agent",
                "context_files": [],
                "setup_commands": [],
            },
            "execution": {
                "agent": None,
                "skill": "do",
                "timeout_seconds": 60,
            },
            "graders": [
                {
                    "type": "string_contains",
                    "config": {
                        "target": "transcript",
                        "patterns": ["test", "success"],
                        "match_all": True,
                    },
                    "weight": 1.0,
                }
            ],
        }
    }


@pytest.fixture
def sample_task_file(tmp_work_dir: Path, sample_task_yaml: dict) -> Path:
    """Create a sample task file in the temp directory.

    Args:
        tmp_work_dir: Temporary directory fixture.
        sample_task_yaml: Sample task configuration fixture.

    Returns:
        Path to the created task YAML file.
    """
    task_file = tmp_work_dir / "test-task.yaml"
    with task_file.open("w") as f:
        yaml.dump(sample_task_yaml, f)
    return task_file


@pytest.fixture
def sample_transcript() -> str:
    """Sample agent output transcript for testing graders.

    Returns:
        String containing sample transcript content.
    """
    return """The agent received the request and began processing.

First, I analyzed the requirements and determined the best approach.
The task was completed successfully with all test cases passing.

Created file: output.py
Function: process_data
Tests: All 5 tests pass with 100% coverage.

The operation completed without errors."""


@pytest.fixture
def sample_transcript_partial() -> str:
    """Sample transcript with partial success for testing partial match scenarios.

    Returns:
        String containing sample transcript with some expected patterns missing.
    """
    return """The agent started processing the request.

Encountered some issues during execution.
Created file: output.py
Function: process_data

Some tests failed. Coverage is at 75%."""


@pytest.fixture
def sample_env(tmp_work_dir: Path) -> dict:
    """Sample environment dictionary for grader testing.

    Args:
        tmp_work_dir: Temporary directory fixture.

    Returns:
        Dictionary with work_dir set to temp directory.
    """
    return {"work_dir": str(tmp_work_dir)}


@pytest.fixture
def sample_yaml_file(tmp_work_dir: Path) -> Path:
    """Create a sample YAML file for yaml_valid grader testing.

    Args:
        tmp_work_dir: Temporary directory fixture.

    Returns:
        Path to the created YAML file.
    """
    yaml_file = tmp_work_dir / "config.yaml"
    content = {
        "name": "test-config",
        "version": "1.0.0",
        "description": "A test configuration",
        "settings": {"debug": True, "timeout": 30},
    }
    with yaml_file.open("w") as f:
        yaml.dump(content, f)
    return yaml_file


@pytest.fixture
def sample_md_with_frontmatter(tmp_work_dir: Path) -> Path:
    """Create a sample markdown file with YAML frontmatter.

    Args:
        tmp_work_dir: Temporary directory fixture.

    Returns:
        Path to the created markdown file.
    """
    md_file = tmp_work_dir / "document.md"
    content = """---
name: test-document
version: 1.0.0
author: Test Author
---

# Test Document

This is the body content of the document.
"""
    md_file.write_text(content)
    return md_file


@pytest.fixture
def calibration_examples_string_contains() -> list[dict]:
    """Sample calibration examples for string_contains grader testing.

    Returns:
        List of calibration example dictionaries.
    """
    return [
        {
            "id": "test-001",
            "description": "All patterns present - should pass",
            "input": {
                "transcript": "Created main.py with process_data function. Tests pass.",
                "config": {
                    "target": "transcript",
                    "patterns": ["main.py", "process_data", "Tests pass"],
                    "match_all": True,
                },
            },
            "expected": {"passed": True, "score": 1.0},
        },
        {
            "id": "test-002",
            "description": "Partial match - should fail with partial score",
            "input": {
                "transcript": "Created main.py. Build completed.",
                "config": {
                    "target": "transcript",
                    "patterns": ["main.py", "process_data", "Tests pass"],
                    "match_all": True,
                },
            },
            "expected": {"passed": False, "score": 0.333},  # 1/3 patterns
        },
    ]


@pytest.fixture
def mock_claude_json_output() -> str:
    """Sample claude CLI JSON output for token extraction testing.

    Returns:
        JSON string mimicking claude CLI output format.
    """
    line1 = '{"type": "assistant", "message": {"content": [{"type": "text", "text": "Processing your request..."}]}}'
    line2 = '{"type": "assistant", "message": {"content": [{"type": "text", "text": "Task completed successfully."}]}}'
    line3 = (
        '{"type": "result", "result": "Task completed successfully.", '
        '"usage": {"input_tokens": 1500, "output_tokens": 500, '
        '"cache_read_input_tokens": 100, "cache_creation_input_tokens": 50}, "total_cost_usd": 0.025}'
    )
    return f"{line1}\n{line2}\n{line3}"


@pytest.fixture
def mock_claude_json_output_array() -> str:
    """Sample claude CLI JSON output as array format.

    Returns:
        JSON array string mimicking claude CLI output format.
    """
    line1 = '{"type": "assistant", "message": {"content": [{"type": "text", "text": "Processing your request..."}]}}'
    line2 = (
        '{"type": "result", "result": "Task completed.", '
        '"usage": {"input_tokens": 1000, "output_tokens": 300}, "total_cost_usd": 0.015}'
    )
    return f"[\n{line1},\n{line2}\n]"
