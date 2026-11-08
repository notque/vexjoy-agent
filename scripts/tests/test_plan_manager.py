"""Tests for scripts/plan-manager.py task check and uncheck.

A capital ``[X]`` reads as done, so check and uncheck must rewrite it too.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

plan_manager = importlib.import_module("plan-manager")

PLAN = """# Plan: demo

**Created**: 2026-11-01
**Updated**: 2026-11-01

## Requirements

- something

## Implementation Tasks

- [X] first task
- [ ] second task with [x] in its text
- [x] third task
"""


@pytest.fixture
def plan_dir(tmp_path: Path) -> Path:
    root = tmp_path / "plan"
    (root / "active").mkdir(parents=True)
    (root / "active" / "demo.md").write_text(PLAN, encoding="utf-8")
    return root


def _task_lines(plan_dir: Path) -> list[str]:
    text = (plan_dir / "active" / "demo.md").read_text(encoding="utf-8")
    return [line for line in text.splitlines() if line.startswith("- [")]


def test_uncheck_capital_x(plan_dir: Path):
    plan = plan_manager.load_plan(plan_dir, "demo")
    assert plan.tasks[0].completed is True

    result = plan_manager.update_task_status(plan, 1, completed=False)

    assert result.status == "success"
    assert _task_lines(plan_dir)[0] == "- [ ] first task"
    assert plan_manager.load_plan(plan_dir, "demo").tasks[0].completed is False


def test_check_rewrites_only_the_marker(plan_dir: Path):
    plan = plan_manager.load_plan(plan_dir, "demo")

    result = plan_manager.update_task_status(plan, 2, completed=True)

    assert result.status == "success"
    assert _task_lines(plan_dir)[1] == "- [x] second task with [x] in its text"


def test_uncheck_lowercase_x_still_works(plan_dir: Path):
    plan = plan_manager.load_plan(plan_dir, "demo")

    result = plan_manager.update_task_status(plan, 3, completed=False)

    assert result.status == "success"
    assert _task_lines(plan_dir)[2] == "- [ ] third task"
