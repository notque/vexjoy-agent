#!/usr/bin/env python3
"""
Scheduler CLI — manage and query the Agent Scheduler Daemon.

Usage:
    scheduler-ctl.py list                      # List all configured jobs
    scheduler-ctl.py run <job-name>            # Trigger a job immediately
    scheduler-ctl.py enable <job-name>         # Enable a disabled job
    scheduler-ctl.py disable <job-name>        # Disable a job without removing
    scheduler-ctl.py history [job-name]        # Last 20 results
    scheduler-ctl.py last <job-name>           # Most recent result with output
    scheduler-ctl.py failures                  # Failed runs in last 24h
    scheduler-ctl.py costs [--days N]          # Daily cost summary
    scheduler-ctl.py status                    # Daemon status
    scheduler-ctl.py reload                    # Send SIGHUP to reload config

Exit codes:
    0 = success
    1 = error
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG = _REPO_ROOT / "schedules.json"
_DB_DIR = Path.home() / ".claude" / "learning"
_DB_PATH = _DB_DIR / "scheduler-results.db"
_PID_FILE = Path("/tmp/agent-scheduler.pid")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


@contextmanager
def get_connection():
    """Get a database connection with Row factory."""
    if not _DB_PATH.exists():
        print(f"Error: Database not found at {_DB_PATH}", file=sys.stderr)
        print("Has the scheduler daemon been started at least once?", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(str(_DB_PATH), timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load schedules.json configuration."""
    path = config_path or _DEFAULT_CONFIG
    if not path.exists():
        print(f"Error: Config not found at {path}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(path.read_text())
    defaults = data.get("defaults", {})
    for job in data.get("jobs", []):
        job.setdefault("model", defaults.get("model", "haiku"))
        job.setdefault("timeout_seconds", defaults.get("timeout_seconds", 120))
        job.setdefault("enabled", defaults.get("enabled", True))
        job.setdefault("cost_limit_usd", 1.0)
    return data


def save_config(config: dict[str, Any], config_path: Path | None = None) -> None:
    """Write configuration back to schedules.json."""
    path = config_path or _DEFAULT_CONFIG
    path.write_text(json.dumps(config, indent=2) + "\n")


def _get_daemon_pid() -> int | None:
    """Get the daemon PID if running, else None."""
    if not _PID_FILE.exists():
        return None
    try:
        pid = int(_PID_FILE.read_text().strip())
        os.kill(pid, 0)  # Check if process exists
        return pid
    except (ValueError, ProcessLookupError):
        return None


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> int:
    """List all configured jobs."""
    config = load_config()
    jobs = config.get("jobs", [])

    if args.json_output:
        print(json.dumps(jobs, indent=2))
        return 0

    if not jobs:
        print("No jobs configured.")
        return 0

    print(f"{'NAME':<25} {'TRIGGER':<12} {'MODEL':<8} {'TIMEOUT':<8} {'COST LIM':<10} {'STATUS'}")
    print("-" * 80)
    for job in jobs:
        trigger = job["trigger"]["type"]
        detail = ""
        if trigger == "cron":
            detail = f" ({job['trigger'].get('schedule', '')})"
        elif trigger == "webhook":
            detail = f" ({job['trigger'].get('path', '')})"
        elif trigger == "file_watch":
            detail = f" ({job['trigger'].get('directory', '')})"

        status = "enabled" if job.get("enabled", True) else "DISABLED"
        cost_str = f"${job.get('cost_limit_usd', 0):.2f}"
        timeout_str = f"{job.get('timeout_seconds', 0)}s"
        print(f"{job['name']:<25} {trigger:<12} {job['model']:<8} {timeout_str:<8} {cost_str:<10} {status}")
        if detail:
            print(f"  {job.get('description', '')}{detail}")

    print(f"\nDaily budget: ${config.get('daily_budget_usd', 0):.2f}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Trigger a job immediately via subprocess."""
    config = load_config()
    job = next((j for j in config["jobs"] if j["name"] == args.job_name), None)

    if not job:
        print(f"Error: Job '{args.job_name}' not found", file=sys.stderr)
        return 1

    model = job.get("model", "haiku")
    timeout = job.get("timeout_seconds", 120)
    prompt = job["prompt"]
    allowed_tools: list[str] = job.get("allowed_tools", [])

    print(f"Running job '{args.job_name}' (model={model}, timeout={timeout}s)...")

    if allowed_tools:
        # Per-job tool scoping: pass --allowedTools instead of --dangerously-skip-permissions
        cmd = ["claude", "-p", prompt, "--model", model, "--allowedTools", ",".join(allowed_tools), "--print"]
    else:
        cmd = ["claude", "-p", prompt, "--model", model, "--dangerously-skip-permissions", "--print"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(_REPO_ROOT))
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"Error: Job timed out after {timeout}s", file=sys.stderr)
        return 124
    except FileNotFoundError:
        print("Error: claude CLI not found in PATH", file=sys.stderr)
        return 127


def cmd_enable(args: argparse.Namespace) -> int:
    """Enable a disabled job."""
    config = load_config()
    job = next((j for j in config["jobs"] if j["name"] == args.job_name), None)
    if not job:
        print(f"Error: Job '{args.job_name}' not found", file=sys.stderr)
        return 1

    job["enabled"] = True
    save_config(config)
    print(f"Job '{args.job_name}' enabled. Run 'scheduler-ctl.py reload' to apply.")
    return 0


def cmd_disable(args: argparse.Namespace) -> int:
    """Disable a job without removing it."""
    config = load_config()
    job = next((j for j in config["jobs"] if j["name"] == args.job_name), None)
    if not job:
        print(f"Error: Job '{args.job_name}' not found", file=sys.stderr)
        return 1

    job["enabled"] = False
    save_config(config)
    print(f"Job '{args.job_name}' disabled. Run 'scheduler-ctl.py reload' to apply.")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    """Show recent job results."""
    with get_connection() as conn:
        if args.job_name:
            rows = conn.execute(
                "SELECT * FROM job_results WHERE job_name = ? ORDER BY started_at DESC LIMIT 20",
                (args.job_name,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM job_results ORDER BY started_at DESC LIMIT 20").fetchall()

    if args.json_output:
        print(json.dumps([dict(r) for r in rows], indent=2))
        return 0

    if not rows:
        print("No results found.")
        return 0

    print(f"{'JOB':<25} {'TRIGGER':<10} {'EXIT':<5} {'DURATION':<10} {'COST':<10} {'STARTED'}")
    print("-" * 90)
    for row in rows:
        exit_str = "OK" if row["exit_code"] == 0 else f"ERR({row['exit_code']})"
        duration_str = f"{row['duration_seconds']:.1f}s"
        cost_str = f"${row['cost_estimate_usd']:.4f}" if row["cost_estimate_usd"] else "-"
        started = row["started_at"][:19].replace("T", " ")
        print(
            f"{row['job_name']:<25} {row['trigger_type']:<10} {exit_str:<5} {duration_str:<10} {cost_str:<10} {started}"
        )

    return 0


def cmd_last(args: argparse.Namespace) -> int:
    """Show the most recent result for a job with full output."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM job_results WHERE job_name = ? ORDER BY started_at DESC LIMIT 1",
            (args.job_name,),
        ).fetchone()

    if not row:
        print(f"No results found for job '{args.job_name}'")
        return 1

    if args.json_output:
        print(json.dumps(dict(row), indent=2))
        return 0

    exit_str = "OK" if row["exit_code"] == 0 else f"FAILED (exit {row['exit_code']})"
    print(f"Job:      {row['job_name']}")
    print(f"Trigger:  {row['trigger_type']} ({row['trigger_detail']})")
    print(f"Model:    {row['model']}")
    print(f"Status:   {exit_str}")
    print(f"Started:  {row['started_at']}")
    print(f"Finished: {row['finished_at']}")
    print(f"Duration: {row['duration_seconds']:.1f}s")
    print(f"Cost:     ${row['cost_estimate_usd']:.4f}" if row["cost_estimate_usd"] else "Cost:     -")
    print()
    if row["stdout"]:
        print("--- STDOUT ---")
        print(row["stdout"][:5000])
    if row["stderr"]:
        print("--- STDERR ---")
        print(row["stderr"][:2000])

    return 0


def cmd_failures(args: argparse.Namespace) -> int:
    """Show all failed runs in the last 24 hours."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM job_results
            WHERE exit_code != 0 AND started_at >= datetime('now', '-1 day')
            ORDER BY started_at DESC
            """,
        ).fetchall()

    if args.json_output:
        print(json.dumps([dict(r) for r in rows], indent=2))
        return 0

    if not rows:
        print("No failures in the last 24 hours.")
        return 0

    print(f"Failures in last 24h: {len(rows)}\n")
    for row in rows:
        started = row["started_at"][:19].replace("T", " ")
        print(f"  {row['job_name']:<25} exit={row['exit_code']}  {started}  {row['model']}")
        if row["stderr"]:
            first_line = row["stderr"].split("\n")[0][:80]
            print(f"    {first_line}")
        print()

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show daemon status."""
    pid = _get_daemon_pid()
    running = pid is not None

    if args.json_output:
        print(json.dumps({"running": running, "pid": pid}))
        return 0 if running else 1

    if pid:
        print(f"Scheduler is RUNNING (pid={pid})")
        # Show details if /proc is available
        try:
            Path(f"/proc/{pid}/stat").read_text()
            print(f"  PID file: {_PID_FILE}")
            print(f"  Database: {_DB_PATH}")
        except (FileNotFoundError, PermissionError):
            pass
        return 0
    else:
        print("Scheduler is NOT RUNNING")
        if _PID_FILE.exists():
            print(f"  Stale PID file: {_PID_FILE} (will be cleaned on next start)")
        return 1


def cmd_reload(_args: argparse.Namespace) -> int:
    """Send SIGHUP to the daemon to reload configuration."""
    pid = _get_daemon_pid()
    if not pid:
        print("Error: Scheduler is not running", file=sys.stderr)
        return 1

    try:
        os.kill(pid, signal.SIGHUP)
        print(f"Sent SIGHUP to scheduler (pid={pid}). Config will be reloaded.")
        return 0
    except ProcessLookupError:
        print("Error: Scheduler process not found", file=sys.stderr)
        _PID_FILE.unlink(missing_ok=True)
        return 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point for the scheduler control CLI."""
    parser = argparse.ArgumentParser(
        description="Agent Scheduler Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output as JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    subparsers.add_parser("list", help="List all configured jobs")

    # run
    p_run = subparsers.add_parser("run", help="Trigger a job immediately")
    p_run.add_argument("job_name", help="Name of the job to run")

    # enable / disable
    p_enable = subparsers.add_parser("enable", help="Enable a disabled job")
    p_enable.add_argument("job_name", help="Name of the job to enable")

    p_disable = subparsers.add_parser("disable", help="Disable a job")
    p_disable.add_argument("job_name", help="Name of the job to disable")

    # history
    p_history = subparsers.add_parser("history", help="Show recent job results")
    p_history.add_argument("job_name", nargs="?", help="Filter by job name")

    # last
    p_last = subparsers.add_parser("last", help="Show most recent result with full output")
    p_last.add_argument("job_name", help="Name of the job")

    # failures
    subparsers.add_parser("failures", help="Show failed runs in last 24h")

    # status
    subparsers.add_parser("status", help="Daemon status")

    # reload
    subparsers.add_parser("reload", help="Reload daemon configuration")

    args = parser.parse_args()

    commands = {
        "list": cmd_list,
        "run": cmd_run,
        "enable": cmd_enable,
        "disable": cmd_disable,
        "history": cmd_history,
        "last": cmd_last,
        "failures": cmd_failures,
        "status": cmd_status,
        "reload": cmd_reload,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
