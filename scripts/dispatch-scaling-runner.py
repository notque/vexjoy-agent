#!/usr/bin/env python3
"""
Dispatch Scaling Runner — ADR-178 experiment infrastructure.

Benchmarks parallel agent dispatch at different scales by launching N
concurrent `claude -p` subprocesses and measuring wall-clock time and
output volume for each agent count.

Usage:
    python3 scripts/dispatch-scaling-runner.py --task "review this codebase" --counts 1,3,5
    python3 scripts/dispatch-scaling-runner.py --task "..." --agent-type code-reviewer --counts 1,3,5,8
    python3 scripts/dispatch-scaling-runner.py --task "..." --dry-run
    python3 scripts/dispatch-scaling-runner.py --task "..." --output-dir /tmp/my-results

Exit codes:
    0 = success
    1 = fatal error (bad args, git failure, etc.)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "benchmark" / "dispatch-scaling" / "results"


# ---------------------------------------------------------------------------
# Worktree management
# ---------------------------------------------------------------------------


def create_worktrees(count: int, base_dir: Path) -> list[Path]:
    """Create N temporary git worktrees rooted under base_dir.

    Args:
        count: Number of worktrees to create.
        base_dir: Parent directory for all worktrees.

    Returns:
        List of worktree paths that were successfully created.
    """
    paths: list[Path] = []
    for i in range(count):
        wt_path = base_dir / f"agent{i}"
        try:
            subprocess.run(
                ["git", "worktree", "add", "--detach", str(wt_path)],
                cwd=str(REPO_ROOT),
                capture_output=True,
                check=True,
                text=True,
            )
            paths.append(wt_path)
        except subprocess.CalledProcessError as exc:
            print(
                f"warning: failed to create worktree {wt_path}: {exc.stderr.strip()}",
                file=sys.stderr,
            )
    return paths


def remove_worktrees(paths: list[Path]) -> None:
    """Remove git worktrees, ignoring individual failures.

    Args:
        paths: Worktree paths to remove.
    """
    for wt_path in paths:
        try:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(wt_path)],
                cwd=str(REPO_ROOT),
                capture_output=True,
                check=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            print(
                f"warning: failed to remove worktree {wt_path}: {exc.stderr.strip()}",
                file=sys.stderr,
            )


# ---------------------------------------------------------------------------
# Core benchmarking
# ---------------------------------------------------------------------------


def run_agents(
    task: str,
    agent_type: str,
    worktrees: list[Path],
    output_dir: Path,
    agent_count: int,
) -> tuple[float, list[dict]]:
    """Launch N agents in parallel and collect their outputs.

    Args:
        task: Prompt passed to each agent via `claude -p`.
        agent_type: Agent type name passed via `--agent-type`.
        worktrees: Worktree directories, one per agent.
        output_dir: Directory where raw output files are written.
        agent_count: Number of agents (used for output file naming).

    Returns:
        Tuple of (wall_clock_seconds, list of per-agent output dicts).
    """
    cmd = ["claude", "-p", task, "--agent-type", agent_type]

    processes: list[subprocess.Popen] = []
    start_time = time.monotonic()

    for wt_path in worktrees:
        proc = subprocess.Popen(
            cmd,
            cwd=str(wt_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        processes.append(proc)

    outputs: list[dict] = []
    for i, proc in enumerate(processes):
        stdout, stderr = proc.communicate()
        combined = stdout if stdout else stderr
        file_name = f"n{agent_count}_agent{i}.txt"
        out_file = output_dir / file_name
        try:
            out_file.write_text(combined, encoding="utf-8")
        except OSError as exc:
            print(f"warning: could not write {out_file}: {exc}", file=sys.stderr)

        if proc.returncode != 0:
            print(
                f"warning: agent {i} exited with code {proc.returncode}: {stderr.strip()[:200]}",
                file=sys.stderr,
            )

        outputs.append(
            {
                "agent_index": i,
                "output_length": len(combined),
                "token_estimate": len(combined.split()),
                "file": file_name,
                "exit_code": proc.returncode,
            }
        )

    wall_clock = time.monotonic() - start_time
    return wall_clock, outputs


def run_dry(task: str, agent_type: str, count: int) -> None:
    """Print the commands that would be executed without running them.

    Args:
        task: Task prompt.
        agent_type: Agent type name.
        count: Number of agents.
    """
    print(f"[dry-run] Would create {count} git worktree(s) under a temporary directory")
    for i in range(count):
        print(f"  [dry-run] agent {i}: claude -p {task!r} --agent-type {agent_type}")
    print(f"[dry-run] Would remove {count} worktree(s) and write results.json")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="dispatch-scaling-runner.py",
        description="Benchmark parallel agent dispatch at different scales (ADR-178).",
    )
    parser.add_argument(
        "--task",
        required=True,
        metavar="DESCRIPTION",
        help="Task prompt to give each agent.",
    )
    parser.add_argument(
        "--agent-type",
        default="general",
        metavar="NAME",
        help="Agent type name passed to claude --agent-type (default: general).",
    )
    parser.add_argument(
        "--counts",
        default="1,3,5,8",
        metavar="N,N,...",
        help="Comma-separated list of agent counts to test (default: 1,3,5,8).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        metavar="PATH",
        help=f"Directory to write results (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print commands that would be executed without running them.",
    )
    return parser


def main() -> int:
    """Entry point — parse args, run benchmarks, write results.json."""
    parser = _build_parser()
    args = parser.parse_args()

    # Parse counts
    try:
        counts = [int(c.strip()) for c in args.counts.split(",")]
    except ValueError:
        print(f"error: --counts must be comma-separated integers, got: {args.counts!r}", file=sys.stderr)
        return 1

    if any(c < 1 for c in counts):
        print("error: all counts must be >= 1", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR

    # Dry-run: just print and exit
    if args.dry_run:
        for count in counts:
            run_dry(args.task, args.agent_type, count)
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)

    runs: list[dict] = []

    for count in counts:
        print(f"Running {count} agent(s)...", flush=True)
        worktrees: list[Path] = []

        with tempfile.TemporaryDirectory(prefix="dispatch-scaling-") as tmp_str:
            tmp_dir = Path(tmp_str)
            try:
                worktrees = create_worktrees(count, tmp_dir)

                if len(worktrees) < count:
                    print(
                        f"warning: only {len(worktrees)}/{count} worktrees created; running with available count",
                        file=sys.stderr,
                    )
                    if not worktrees:
                        print(f"error: no worktrees available for count={count}, skipping", file=sys.stderr)
                        continue

                wall_clock, outputs = run_agents(
                    task=args.task,
                    agent_type=args.agent_type,
                    worktrees=worktrees,
                    output_dir=output_dir,
                    agent_count=count,
                )

                runs.append(
                    {
                        "agent_count": len(worktrees),
                        "wall_clock_seconds": round(wall_clock, 3),
                        "outputs": outputs,
                    }
                )
                print(f"  wall_clock={wall_clock:.1f}s  agents={len(worktrees)}")

            finally:
                remove_worktrees(worktrees)

    results = {
        "task": args.task,
        "agent_type": args.agent_type,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "runs": runs,
    }

    results_file = output_dir / "results.json"
    results_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nResults written to {results_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
