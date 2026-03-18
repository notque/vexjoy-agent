#!/usr/bin/env python3
"""
Testing Skill Integration for Eval Harness.

Bridges the testing-agents-with-subagents skill with the eval harness,
enabling the skill to run eval tasks from YAML files and collect metrics.

Usage from skill context:
    from evals.integrations.testing_skill import run_agent_eval, EvalResult

    result = run_agent_eval("python-general-engineer", trials=3)
    print(f"Pass rate: {result.pass_rate:.1%}")
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

# Add parent directory to path to import harness
EVALS_DIR = Path(__file__).parent.parent
if str(EVALS_DIR) not in sys.path:
    sys.path.insert(0, str(EVALS_DIR))

import yaml

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass
class TrialResult:
    """Result of a single trial."""

    task_id: str
    trial_num: int
    passed: bool
    score: float
    elapsed_seconds: float
    tokens_total: int
    cost_usd: float
    transcript_preview: str = ""
    grades: list[dict] = field(default_factory=list)


@dataclass
class TaskResult:
    """Aggregated result for a task across multiple trials."""

    task_id: str
    task_name: str
    trials: list[TrialResult]
    pass_at_k: bool  # At least one trial passed
    pass_power_k: bool  # All trials passed
    pass_rate: float
    avg_score: float
    tokens_total: int
    cost_usd: float


@dataclass
class EvalResult:
    """Full evaluation result for an agent."""

    agent_name: str
    num_trials: int
    timestamp: str
    tasks: list[TaskResult]
    # Aggregate metrics
    total_tasks: int
    passed_any: int  # Tasks with at least one passing trial
    passed_all: int  # Tasks with all trials passing
    pass_rate: float  # Percentage of tasks with at least one pass
    avg_score: float
    tokens_total: int
    cost_usd: float


def find_tasks_for_agent(agent_name: str, tasks_dir: Path | None = None) -> list[Path]:
    """
    Find all eval tasks tagged for a specific agent.

    Looks for tasks where execution.agent matches the agent name.

    Args:
        agent_name: The agent name to find tasks for (e.g., 'python-general-engineer')
        tasks_dir: Directory containing task YAML files (defaults to evals/tasks/)

    Returns:
        List of paths to matching task files
    """
    if tasks_dir is None:
        tasks_dir = EVALS_DIR / "tasks"

    matching_tasks: list[Path] = []

    # Walk through all task directories
    for task_file in tasks_dir.rglob("*.yaml"):
        # Skip schema file
        if task_file.name == "task_schema.yaml":
            continue

        try:
            with open(task_file) as f:
                data = yaml.safe_load(f)

            task = data.get("task", data)
            task_agent = task.get("execution", {}).get("agent")

            if task_agent == agent_name:
                matching_tasks.append(task_file)

        except (yaml.YAMLError, OSError, KeyError):
            # Skip malformed files
            continue

    return sorted(matching_tasks)


def list_available_agents(tasks_dir: Path | None = None) -> dict[str, int]:
    """
    List all agents that have eval tasks available.

    Args:
        tasks_dir: Directory containing task YAML files

    Returns:
        Dict mapping agent names to task counts
    """
    if tasks_dir is None:
        tasks_dir = EVALS_DIR / "tasks"

    agents: dict[str, int] = {}

    for task_file in tasks_dir.rglob("*.yaml"):
        if task_file.name == "task_schema.yaml":
            continue

        try:
            with open(task_file) as f:
                data = yaml.safe_load(f)

            task = data.get("task", data)
            agent = task.get("execution", {}).get("agent")

            if agent:
                agents[agent] = agents.get(agent, 0) + 1

        except (yaml.YAMLError, OSError, KeyError):
            continue

    return agents


def run_single_task(task_path: Path, trial_num: int = 0) -> TrialResult:
    """
    Run a single eval task and return the result.

    Args:
        task_path: Path to the task YAML file
        trial_num: Trial number (for multi-trial runs)

    Returns:
        TrialResult with pass/fail, score, and metrics
    """
    # Import harness functions
    from harness import run_task

    result = run_task(str(task_path), trial_num)

    return TrialResult(
        task_id=result["task_id"],
        trial_num=trial_num,
        passed=result["passed"],
        score=result["score"],
        elapsed_seconds=result["metrics"]["elapsed_seconds"],
        tokens_total=result["metrics"]["tokens_total"],
        cost_usd=result["metrics"]["cost_usd"],
        transcript_preview=result.get("transcript_preview", "")[:200],
        grades=result.get("grades", []),
    )


def run_task_with_trials(task_path: Path, num_trials: int = 3) -> TaskResult:
    """
    Run a task multiple times and aggregate results.

    Args:
        task_path: Path to the task YAML file
        num_trials: Number of trials to run

    Returns:
        TaskResult with aggregated metrics and pass@k statistics
    """
    # Load task to get metadata
    with open(task_path) as f:
        data = yaml.safe_load(f)

    task = data.get("task", data)
    task_id = task.get("id", task_path.stem)
    task_name = task.get("name", "")

    # Run trials
    trials: list[TrialResult] = []
    for i in range(num_trials):
        result = run_single_task(task_path, i)
        trials.append(result)

    # Calculate aggregates
    passes = sum(1 for t in trials if t.passed)
    pass_at_k = passes > 0
    pass_power_k = passes == num_trials
    pass_rate = passes / num_trials if num_trials > 0 else 0.0
    avg_score = sum(t.score for t in trials) / num_trials if num_trials > 0 else 0.0
    tokens_total = sum(t.tokens_total for t in trials)
    cost_usd = sum(t.cost_usd for t in trials)

    return TaskResult(
        task_id=task_id,
        task_name=task_name,
        trials=trials,
        pass_at_k=pass_at_k,
        pass_power_k=pass_power_k,
        pass_rate=pass_rate,
        avg_score=avg_score,
        tokens_total=tokens_total,
        cost_usd=cost_usd,
    )


def run_agent_eval(
    agent_name: str,
    num_trials: int = 3,
    tasks_dir: Path | None = None,
    verbose: bool = True,
) -> EvalResult:
    """
    Run all eval tasks for an agent and aggregate results.

    This is the main entry point for the testing skill integration.

    Args:
        agent_name: The agent to test (e.g., 'python-general-engineer')
        num_trials: Number of trials per task (default: 3)
        tasks_dir: Directory containing task files
        verbose: Whether to print progress

    Returns:
        EvalResult with full metrics and pass@k statistics
    """
    # Find tasks for this agent
    task_files = find_tasks_for_agent(agent_name, tasks_dir)

    if not task_files:
        return EvalResult(
            agent_name=agent_name,
            num_trials=num_trials,
            timestamp=datetime.now().isoformat(),
            tasks=[],
            total_tasks=0,
            passed_any=0,
            passed_all=0,
            pass_rate=0.0,
            avg_score=0.0,
            tokens_total=0,
            cost_usd=0.0,
        )

    if verbose:
        print(f"Found {len(task_files)} eval tasks for {agent_name}")
        print(f"Running {num_trials} trials per task...")
        print("-" * 60)

    # Run all tasks
    task_results: list[TaskResult] = []
    for task_file in task_files:
        if verbose:
            print(f"Running: {task_file.name}")

        result = run_task_with_trials(task_file, num_trials)
        task_results.append(result)

        if verbose:
            status = "PASS" if result.pass_at_k else "FAIL"
            print(f"  pass@{num_trials}: {status} (rate: {result.pass_rate:.1%}, avg score: {result.avg_score:.2f})")

    # Calculate aggregate metrics
    total_tasks = len(task_results)
    passed_any = sum(1 for t in task_results if t.pass_at_k)
    passed_all = sum(1 for t in task_results if t.pass_power_k)
    pass_rate = passed_any / total_tasks if total_tasks > 0 else 0.0
    avg_score = sum(t.avg_score for t in task_results) / total_tasks if total_tasks > 0 else 0.0
    tokens_total = sum(t.tokens_total for t in task_results)
    cost_usd = sum(t.cost_usd for t in task_results)

    return EvalResult(
        agent_name=agent_name,
        num_trials=num_trials,
        timestamp=datetime.now().isoformat(),
        tasks=task_results,
        total_tasks=total_tasks,
        passed_any=passed_any,
        passed_all=passed_all,
        pass_rate=pass_rate,
        avg_score=avg_score,
        tokens_total=tokens_total,
        cost_usd=cost_usd,
    )


def format_eval_result(result: EvalResult) -> str:
    """
    Format an EvalResult for display in the testing skill.

    Returns a markdown-formatted report suitable for inclusion in
    the skill's test report output.
    """
    lines = [
        f"# Eval Results: {result.agent_name}",
        "",
        "## Summary",
        "",
        "| Metric | Result |",
        "|--------|--------|",
        f"| Tasks Run | {result.total_tasks} |",
        f"| Trials per Task | {result.num_trials} |",
        f"| Tasks Passed (any trial) | {result.passed_any} |",
        f"| Tasks Passed (all trials) | {result.passed_all} |",
        f"| Pass Rate | {result.pass_rate:.1%} |",
        f"| Avg Score | {result.avg_score:.2f} |",
        f"| Total Tokens | {result.tokens_total:,} |",
        f"| Total Cost | ${result.cost_usd:.4f} |",
        "",
    ]

    if result.tasks:
        lines.extend([
            "## Task Results",
            "",
            "| Task | pass@k | Pass Rate | Avg Score |",
            "|------|--------|-----------|-----------|",
        ])

        for task in result.tasks:
            pass_status = "PASS" if task.pass_at_k else "FAIL"
            lines.append(
                f"| {task.task_name or task.task_id} | {pass_status} | "
                f"{task.pass_rate:.1%} | {task.avg_score:.2f} |"
            )

        lines.append("")

    # Verdict
    if result.pass_rate >= 0.9:
        verdict = "READY FOR DEPLOYMENT"
    elif result.pass_rate >= 0.7:
        verdict = "NEEDS MINOR FIXES"
    else:
        verdict = "NEEDS MAJOR FIXES"

    lines.extend([
        "## Verdict",
        "",
        f"**{verdict}**",
        "",
        f"_Evaluated at {result.timestamp}_",
    ])

    return "\n".join(lines)


def format_skill_test_report(result: EvalResult) -> str:
    """
    Format eval results in the testing-agents-with-subagents skill's
    expected test report format.

    This format matches the skill's documented Test Report Format.
    """
    lines = [
        f"# Agent Test Report: {result.agent_name}",
        "",
        f"**Date:** {result.timestamp}",
        f"**Tester:** Eval Harness (testing-agents-with-subagents skill)",
        f"**Trials per Task:** {result.num_trials}",
        "",
        "## Summary",
        "",
        "| Metric | Result |",
        "|--------|--------|",
        f"| Tasks Run | {result.total_tasks} |",
        f"| Passed (any trial) | {result.passed_any} |",
        f"| Passed (all trials) | {result.passed_all} |",
        f"| Pass Rate | {result.pass_rate:.1%} |",
        "",
    ]

    # Individual task results
    if result.tasks:
        lines.append("## Test Results")
        lines.append("")

        for task in result.tasks:
            task_status = "PASS" if task.pass_at_k else "FAIL"
            lines.extend([
                f"### {task.task_id}: {task.task_name}",
                f"- Status: {task_status}",
                f"- pass@{result.num_trials}: {task.pass_at_k}",
                f"- pass^{result.num_trials}: {task.pass_power_k}",
                f"- Pass Rate: {task.pass_rate:.1%}",
                f"- Avg Score: {task.avg_score:.2f}",
                "",
                "**Trial Results:**",
                "",
                "| Trial | Passed | Score |",
                "|-------|--------|-------|",
            ])

            for trial in task.trials:
                trial_status = "PASS" if trial.passed else "FAIL"
                lines.append(f"| {trial.trial_num + 1} | {trial_status} | {trial.score:.2f} |")

            lines.append("")

    # Issues found (failing tasks)
    failing_tasks = [t for t in result.tasks if not t.pass_at_k]
    if failing_tasks:
        lines.append("## Issues Found")
        lines.append("")
        for i, task in enumerate(failing_tasks, 1):
            severity = "HIGH" if task.avg_score < 0.3 else "MEDIUM"
            lines.append(f"{i}. **{task.task_id}** - Severity: {severity}")
            lines.append(f"   - Avg Score: {task.avg_score:.2f}")
            lines.append(f"   - Best Trial Score: {max(t.score for t in task.trials):.2f}")
            lines.append("")

    # Verdict
    lines.append("## Verdict")
    lines.append("")

    if result.pass_rate >= 0.9 and result.avg_score >= 0.8:
        verdict = "READY FOR DEPLOYMENT"
    elif result.pass_rate >= 0.7:
        verdict = "NEEDS FIXES"
    else:
        verdict = "REQUIRES REVIEW"

    lines.append(f"**{verdict}**")

    return "\n".join(lines)


if __name__ == "__main__":
    # Quick test
    agents = list_available_agents()
    print("Available agents with eval tasks:")
    for agent, count in sorted(agents.items()):
        print(f"  {agent}: {count} task(s)")
