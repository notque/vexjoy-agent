"""Tests for check-scope-overlap.py.

Tests conflict detection, parallel grouping, readonly handling,
directory parent/child overlap, and CLI output modes.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

# Import the module under test
sys_path_entry = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, sys_path_entry)
cso = importlib.import_module("check-scope-overlap")
sys.path.pop(0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tasks(specs: list[dict]) -> list[cso.Task]:
    """Convert dicts to Task objects."""
    return [cso.Task(id=s["id"], scope=s["scope"], readonly=s.get("readonly", False)) for s in specs]


# ---------------------------------------------------------------------------
# Path conflict detection
# ---------------------------------------------------------------------------


class TestPathsConflict:
    def test_exact_match(self) -> None:
        assert cso._paths_conflict("handlers/auth.go", False, "handlers/auth.go", False) is True

    def test_different_files_same_dir(self) -> None:
        assert cso._paths_conflict("handlers/auth.go", False, "handlers/payment.go", False) is False

    def test_parent_dir_contains_file(self) -> None:
        assert cso._paths_conflict("handlers", True, "handlers/auth.go", False) is True

    def test_file_inside_parent_dir(self) -> None:
        assert cso._paths_conflict("handlers/auth.go", False, "handlers", True) is True

    def test_nested_dir_conflict(self) -> None:
        assert cso._paths_conflict("src", True, "src/handlers/auth.go", False) is True

    def test_sibling_dirs_no_conflict(self) -> None:
        assert cso._paths_conflict("handlers", True, "models", True) is False

    def test_prefix_but_not_parent(self) -> None:
        """handlers-v2/auth.go should NOT conflict with handlers/."""
        assert cso._paths_conflict("handlers", True, "handlers-v2/auth.go", False) is False

    def test_both_dirs_same(self) -> None:
        assert cso._paths_conflict("handlers", True, "handlers", True) is True


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


class TestDetectConflicts:
    def test_adr_example(self) -> None:
        """The exact example from ADR-089."""
        tasks = _make_tasks(
            [
                {"id": "task-1", "scope": ["handlers/auth.go", "middleware/"]},
                {"id": "task-2", "scope": ["handlers/payment.go", "models/"]},
                {"id": "task-3", "scope": ["handlers/auth.go", "tests/"]},
            ]
        )
        conflicts = cso.detect_conflicts(tasks)
        assert len(conflicts) == 1
        assert conflicts[0].tasks == ["task-1", "task-3"]
        assert "handlers/auth.go" in conflicts[0].overlap

    def test_no_conflicts(self) -> None:
        tasks = _make_tasks(
            [
                {"id": "task-1", "scope": ["handlers/"]},
                {"id": "task-2", "scope": ["models/"]},
            ]
        )
        conflicts = cso.detect_conflicts(tasks)
        assert conflicts == []

    def test_readonly_never_conflicts(self) -> None:
        tasks = _make_tasks(
            [
                {"id": "task-1", "scope": ["handlers/auth.go"]},
                {"id": "task-2", "scope": ["handlers/auth.go"], "readonly": True},
            ]
        )
        conflicts = cso.detect_conflicts(tasks)
        assert conflicts == []

    def test_both_readonly_no_conflict(self) -> None:
        tasks = _make_tasks(
            [
                {"id": "task-1", "scope": ["handlers/auth.go"], "readonly": True},
                {"id": "task-2", "scope": ["handlers/auth.go"], "readonly": True},
            ]
        )
        conflicts = cso.detect_conflicts(tasks)
        assert conflicts == []

    def test_multiple_conflicts(self) -> None:
        tasks = _make_tasks(
            [
                {"id": "task-1", "scope": ["a.go", "b.go"]},
                {"id": "task-2", "scope": ["a.go"]},
                {"id": "task-3", "scope": ["b.go"]},
            ]
        )
        conflicts = cso.detect_conflicts(tasks)
        assert len(conflicts) == 2
        conflict_pairs = [(c.tasks[0], c.tasks[1]) for c in conflicts]
        assert ("task-1", "task-2") in conflict_pairs
        assert ("task-1", "task-3") in conflict_pairs

    def test_directory_parent_child(self) -> None:
        tasks = _make_tasks(
            [
                {"id": "task-1", "scope": ["handlers/"]},
                {"id": "task-2", "scope": ["handlers/auth.go"]},
            ]
        )
        conflicts = cso.detect_conflicts(tasks)
        assert len(conflicts) == 1

    def test_overlap_reports_child_path(self) -> None:
        """When a directory conflicts with a file inside it, report the more specific path."""
        tasks = _make_tasks(
            [
                {"id": "task-1", "scope": ["handlers/"]},
                {"id": "task-2", "scope": ["handlers/auth.go"]},
            ]
        )
        conflicts = cso.detect_conflicts(tasks)
        assert conflicts[0].overlap == ["handlers/auth.go"]

    def test_overlap_dedup_no_duplicates(self) -> None:
        """When scopes list both a directory and a file inside it, overlaps should not duplicate."""
        tasks = _make_tasks(
            [
                {"id": "task-1", "scope": ["handlers/", "handlers/auth.go"]},
                {"id": "task-2", "scope": ["handlers/auth.go"]},
            ]
        )
        conflicts = cso.detect_conflicts(tasks)
        assert len(conflicts) == 1
        # No duplicate entries in overlap list
        assert len(conflicts[0].overlap) == len(set(conflicts[0].overlap))


# ---------------------------------------------------------------------------
# Parallel grouping
# ---------------------------------------------------------------------------


class TestComputeParallelGroups:
    def test_adr_example(self) -> None:
        tasks = _make_tasks(
            [
                {"id": "task-1", "scope": ["handlers/auth.go", "middleware/"]},
                {"id": "task-2", "scope": ["handlers/payment.go", "models/"]},
                {"id": "task-3", "scope": ["handlers/auth.go", "tests/"]},
            ]
        )
        conflicts = cso.detect_conflicts(tasks)
        groups = cso.compute_parallel_groups(tasks, conflicts)
        assert len(groups) == 2
        assert "task-1" in groups[0] and "task-2" in groups[0]
        assert groups[1] == ["task-3"]

    def test_no_conflicts_single_group(self) -> None:
        tasks = _make_tasks(
            [
                {"id": "a", "scope": ["x.go"]},
                {"id": "b", "scope": ["y.go"]},
                {"id": "c", "scope": ["z.go"]},
            ]
        )
        conflicts = cso.detect_conflicts(tasks)
        groups = cso.compute_parallel_groups(tasks, conflicts)
        assert len(groups) == 1
        assert sorted(groups[0]) == ["a", "b", "c"]

    def test_all_conflict_serial(self) -> None:
        tasks = _make_tasks(
            [
                {"id": "a", "scope": ["shared.go"]},
                {"id": "b", "scope": ["shared.go"]},
                {"id": "c", "scope": ["shared.go"]},
            ]
        )
        conflicts = cso.detect_conflicts(tasks)
        groups = cso.compute_parallel_groups(tasks, conflicts)
        assert len(groups) == 3


# ---------------------------------------------------------------------------
# Recommendation text
# ---------------------------------------------------------------------------


class TestGenerateRecommendation:
    def test_no_tasks(self) -> None:
        assert cso.generate_recommendation([]) == "No tasks to schedule."

    def test_single_task(self) -> None:
        rec = cso.generate_recommendation([["task-1"]])
        assert "single task" in rec

    def test_all_parallel(self) -> None:
        rec = cso.generate_recommendation([["a", "b", "c"]])
        assert "in parallel" in rec
        assert "No conflicts" in rec

    def test_multiple_groups(self) -> None:
        rec = cso.generate_recommendation([["a", "b"], ["c"]])
        assert "in parallel" in rec
        assert "after group" in rec

    def test_later_group_multi_task(self) -> None:
        """Wave 2 with multiple tasks should use 'Then run ... in parallel'."""
        rec = cso.generate_recommendation([["a"], ["b", "c"]])
        assert "Then run" in rec
        assert "in parallel" in rec


# ---------------------------------------------------------------------------
# Human output formatting
# ---------------------------------------------------------------------------


class TestFormatHuman:
    def test_conflicts_present(self) -> None:
        result = cso.AnalysisResult(
            conflicts=[cso.Conflict(tasks=["t1", "t2"], overlap=["shared.go"])],
            parallel_groups=[["t1"], ["t2"]],
            recommendation="Run t1. Run t2 after group 1 completes.",
        )
        output = cso.format_human(result)
        assert "Conflicts found: 1" in output
        assert "t1 <-> t2" in output
        assert "shared.go" in output
        assert "Group 1:" in output
        assert "Group 2:" in output

    def test_no_conflicts(self) -> None:
        result = cso.AnalysisResult(
            conflicts=[],
            parallel_groups=[["t1", "t2"]],
            recommendation="Run t1 and t2 in parallel.",
        )
        output = cso.format_human(result)
        assert "No conflicts found" in output
        assert "Group 1: t1, t2" in output


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------


class TestParseTasks:
    def test_valid_input(self) -> None:
        tasks = cso.parse_tasks('[{"id": "t1", "scope": ["a.go"]}]')
        assert len(tasks) == 1
        assert tasks[0].id == "t1"
        assert tasks[0].readonly is False

    def test_readonly_flag(self) -> None:
        tasks = cso.parse_tasks('[{"id": "t1", "scope": ["a.go"], "readonly": true}]')
        assert tasks[0].readonly is True

    def test_invalid_json(self) -> None:
        with pytest.raises(ValueError, match="invalid JSON"):
            cso.parse_tasks("not json")

    def test_not_array(self) -> None:
        with pytest.raises(ValueError, match="expected a JSON array"):
            cso.parse_tasks('{"id": "t1"}')

    def test_empty_array(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            cso.parse_tasks("[]")

    def test_missing_id(self) -> None:
        with pytest.raises(ValueError, match="missing or invalid 'id'"):
            cso.parse_tasks('[{"scope": ["a.go"]}]')

    def test_duplicate_id(self) -> None:
        with pytest.raises(ValueError, match="duplicate task id"):
            cso.parse_tasks('[{"id": "t1", "scope": ["a.go"]}, {"id": "t1", "scope": ["b.go"]}]')

    def test_missing_scope(self) -> None:
        with pytest.raises(ValueError, match="missing or invalid 'scope'"):
            cso.parse_tasks('[{"id": "t1"}]')

    def test_invalid_readonly_type(self) -> None:
        with pytest.raises(ValueError, match="must be a boolean"):
            cso.parse_tasks('[{"id": "t1", "scope": ["a.go"], "readonly": "yes"}]')


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCLI:
    def test_json_output(self) -> None:
        """Test main() returns 0 for no-conflict JSON output."""
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch

        buf = io.StringIO()
        with (
            patch(
                "sys.argv",
                ["check-scope-overlap", "--tasks", '[{"id":"a","scope":["x.go"]},{"id":"b","scope":["y.go"]}]'],
            ),
            redirect_stdout(buf),
        ):
            rc = cso.main()
        assert rc == 0
        data = json.loads(buf.getvalue())
        assert data["conflicts"] == []

    def test_check_mode_no_conflicts(self) -> None:
        from unittest.mock import patch

        with patch(
            "sys.argv",
            ["check-scope-overlap", "--tasks", '[{"id":"a","scope":["x.go"]},{"id":"b","scope":["y.go"]}]', "--check"],
        ):
            rc = cso.main()
        assert rc == 0

    def test_check_mode_with_conflicts(self) -> None:
        from unittest.mock import patch

        with patch(
            "sys.argv",
            ["check-scope-overlap", "--tasks", '[{"id":"a","scope":["x.go"]},{"id":"b","scope":["x.go"]}]', "--check"],
        ):
            rc = cso.main()
        assert rc == 1

    def test_invalid_input_returns_2(self) -> None:
        from unittest.mock import patch

        with patch("sys.argv", ["check-scope-overlap", "--tasks", "not-json"]):
            rc = cso.main()
        assert rc == 2

    def test_tasks_file(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        task_file = tmp_path / "tasks.json"
        task_file.write_text('[{"id": "a", "scope": ["x.go"]}]')
        with patch("sys.argv", ["check-scope-overlap", "--tasks-file", str(task_file)]):
            rc = cso.main()
        assert rc == 0

    def test_human_mode(self) -> None:
        """Test --human CLI mode produces human-readable output."""
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch

        buf = io.StringIO()
        with (
            patch(
                "sys.argv",
                [
                    "check-scope-overlap",
                    "--tasks",
                    '[{"id":"a","scope":["x.go"]},{"id":"b","scope":["x.go"]}]',
                    "--human",
                ],
            ),
            redirect_stdout(buf),
        ):
            rc = cso.main()
        assert rc == 0
        output = buf.getvalue()
        assert "Conflicts found: 1" in output
        assert "a <-> b" in output
        assert "Group" in output

    def test_tasks_file_not_found(self) -> None:
        from unittest.mock import patch

        with patch("sys.argv", ["check-scope-overlap", "--tasks-file", "/nonexistent/tasks.json"]):
            rc = cso.main()
        assert rc == 2


# ---------------------------------------------------------------------------
# Input validation edge cases
# ---------------------------------------------------------------------------


class TestParseTasksEdgeCases:
    def test_non_dict_item(self) -> None:
        """Array containing non-object items should fail cleanly."""
        with pytest.raises(ValueError, match="not an object"):
            cso.parse_tasks('["not-a-dict"]')

    def test_whitespace_scope_entry(self) -> None:
        """Whitespace-only scope entries should be rejected."""
        with pytest.raises(ValueError, match="not a non-empty string"):
            cso.parse_tasks('[{"id": "t1", "scope": [" "]}]')

    def test_empty_string_scope_entry(self) -> None:
        with pytest.raises(ValueError, match="not a non-empty string"):
            cso.parse_tasks('[{"id": "t1", "scope": [""]}]')
