#!/usr/bin/env python3
"""Consolidated toolkit health checks.

Consolidates the 4 Category C checks from kairos-lite monitor-prompt.md Phase 5
into a single structured script. Each dimension can be queried independently or
all at once.

Usage:
    python3 scripts/toolkit-health.py                  # human-readable report
    python3 scripts/toolkit-health.py --json           # machine-readable JSON
    python3 scripts/toolkit-health.py --check hook-errors
    python3 scripts/toolkit-health.py --check stale-memory
    python3 scripts/toolkit-health.py --check state-files
    python3 scripts/toolkit-health.py --check adr-backlog
    python3 scripts/toolkit-health.py --config ~/.claude/config/kairos.json

Exit codes:
    0 — All checks OK (no warnings)
    1 — One or more WARN flags raised
    2 — Script error (bad arguments, missing config)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLAUDE_DIR = Path.home() / ".claude"
LEARNING_DB = CLAUDE_DIR / "state" / "learning.db"
MEMORY_PROJECTS_DIR = CLAUDE_DIR / "projects"
STATE_DIR = CLAUDE_DIR / "state"
ADR_DIR = Path(__file__).resolve().parent.parent / "adr"

HOOK_ERROR_RATE_THRESHOLD = 20.0  # percent
STALE_MEMORY_WARN_COUNT = 5
STATE_FILE_WARN_COUNT = 50
ADR_BACKLOG_WARN_COUNT = 20

CHECK_NAMES = ("hook-errors", "stale-memory", "state-files", "adr-backlog")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

Status = Literal["OK", "WARN"]


@dataclass
class HookErrorResult:
    """Result of the hook error rate check."""

    blocked_count: int
    total_count: int
    error_rate: float
    trend: Literal["INCREASING", "STABLE", "DECREASING"]
    status: Status
    db_missing: bool = False

    def flag_message(self) -> str | None:
        if self.db_missing:
            return None
        if self.status == "WARN":
            return (
                f"Hook error rate {self.error_rate:.1f}% "
                f"({self.blocked_count}/{self.total_count} blocked, last 7d) "
                f"— above {HOOK_ERROR_RATE_THRESHOLD:.0f}% threshold, trending {self.trend}"
            )
        return None


@dataclass
class StaleMemoryFile:
    """A single stale memory file."""

    name: str
    age_days: int
    project: str


@dataclass
class StaleMemoryResult:
    """Result of the stale memory files check."""

    stale_files: list[StaleMemoryFile]
    status: Status
    threshold_days: int

    def flag_message(self) -> str | None:
        if self.status == "WARN":
            oldest = max(self.stale_files, key=lambda f: f.age_days)
            return (
                f"{len(self.stale_files)} stale memory files "
                f"(oldest: {oldest.name}, {oldest.age_days} days, project: {oldest.project})"
            )
        return None


@dataclass
class StateFileResult:
    """Result of the state file accumulation check."""

    file_count: int
    threshold: int
    status: Status

    def flag_message(self) -> str | None:
        if self.status == "WARN":
            return f"State directory: {self.file_count} files (threshold: {self.threshold})"
        return None


@dataclass
class AdrBacklogResult:
    """Result of the ADR backlog check."""

    adr_count: int
    threshold: int
    status: Status
    adr_dir: str

    def flag_message(self) -> str | None:
        if self.status == "WARN":
            return f"ADR backlog: {self.adr_count} files in {self.adr_dir} (threshold: {self.threshold})"
        return None


@dataclass
class HealthConfig:
    """Runtime configuration for health checks."""

    stale_memory_days: int = 14
    state_file_warn_count: int = STATE_FILE_WARN_COUNT
    adr_backlog_warn_count: int = ADR_BACKLOG_WARN_COUNT
    hook_error_rate_threshold: float = HOOK_ERROR_RATE_THRESHOLD


@dataclass
class HealthReport:
    """Aggregated health report for all dimensions."""

    hook_errors: HookErrorResult | None = None
    stale_memory: StaleMemoryResult | None = None
    state_files: StateFileResult | None = None
    adr_backlog: AdrBacklogResult | None = None
    flags: list[str] = field(default_factory=list)
    scan_timestamp: str = ""

    def has_warnings(self) -> bool:
        return bool(self.flags)


# ---------------------------------------------------------------------------
# Check implementations
# ---------------------------------------------------------------------------


def check_hook_errors(config: HealthConfig) -> HookErrorResult:
    """Query learning.db for hook error rate over the last 7 days with trend.

    Args:
        config: Health configuration with thresholds.

    Returns:
        HookErrorResult with rate, trend, and pass/warn status.
    """
    if not LEARNING_DB.exists():
        return HookErrorResult(
            blocked_count=0,
            total_count=0,
            error_rate=0.0,
            trend="STABLE",
            status="OK",
            db_missing=True,
        )

    cutoff_7d = (datetime.now(tz=timezone.utc) - timedelta(days=7)).isoformat()
    cutoff_recent = (datetime.now(tz=timezone.utc) - timedelta(days=3.5)).isoformat()

    conn = sqlite3.connect(str(LEARNING_DB))
    try:
        blocked_count = conn.execute(
            "SELECT COUNT(*) FROM governance_events WHERE blocked=1 AND created_at > ?",
            (cutoff_7d,),
        ).fetchone()[0]

        total_count = conn.execute(
            "SELECT COUNT(*) FROM governance_events WHERE created_at > ?",
            (cutoff_7d,),
        ).fetchone()[0]

        recent_blocked = conn.execute(
            "SELECT COUNT(*) FROM governance_events WHERE blocked=1 AND created_at > ?",
            (cutoff_recent,),
        ).fetchone()[0]

        older_blocked = conn.execute(
            "SELECT COUNT(*) FROM governance_events WHERE blocked=1 AND created_at > ? AND created_at <= ?",
            (cutoff_7d, cutoff_recent),
        ).fetchone()[0]
    except sqlite3.OperationalError:
        # Table may not exist yet on fresh installs
        return HookErrorResult(
            blocked_count=0,
            total_count=0,
            error_rate=0.0,
            trend="STABLE",
            status="OK",
            db_missing=True,
        )
    finally:
        conn.close()

    error_rate = (blocked_count / total_count * 100) if total_count > 0 else 0.0

    if recent_blocked > older_blocked * 1.5:
        trend: Literal["INCREASING", "STABLE", "DECREASING"] = "INCREASING"
    elif older_blocked > 0 and recent_blocked < older_blocked * 0.5:
        trend = "DECREASING"
    else:
        trend = "STABLE"

    status: Status = "WARN" if error_rate > config.hook_error_rate_threshold or trend == "INCREASING" else "OK"

    return HookErrorResult(
        blocked_count=blocked_count,
        total_count=total_count,
        error_rate=error_rate,
        trend=trend,
        status=status,
    )


def check_stale_memory(config: HealthConfig) -> StaleMemoryResult:
    """Scan project memory directories for files older than the stale threshold.

    Args:
        config: Health configuration with stale_memory_days threshold.

    Returns:
        StaleMemoryResult with list of stale files and pass/warn status.
    """
    threshold = timedelta(days=config.stale_memory_days)
    now = datetime.now(tz=timezone.utc)
    stale: list[StaleMemoryFile] = []

    if MEMORY_PROJECTS_DIR.exists():
        for memory_dir in MEMORY_PROJECTS_DIR.glob("*/memory"):
            for md_file in memory_dir.glob("*.md"):
                if md_file.name == "MEMORY.md":
                    continue
                mtime = datetime.fromtimestamp(md_file.stat().st_mtime, tz=timezone.utc)
                age = now - mtime
                if age > threshold:
                    project_name = md_file.parent.parent.name
                    stale.append(StaleMemoryFile(md_file.name, age.days, project_name))

    stale.sort(key=lambda f: -f.age_days)
    status: Status = "WARN" if len(stale) > STALE_MEMORY_WARN_COUNT else "OK"
    return StaleMemoryResult(stale_files=stale, status=status, threshold_days=config.stale_memory_days)


def check_state_files(config: HealthConfig) -> StateFileResult:
    """Count files in the Claude state directory.

    Args:
        config: Health configuration with state_file_warn_count threshold.

    Returns:
        StateFileResult with count and pass/warn status.
    """
    count = 0
    if STATE_DIR.exists():
        count = sum(1 for _ in STATE_DIR.iterdir())

    status: Status = "WARN" if count > config.state_file_warn_count else "OK"
    return StateFileResult(file_count=count, threshold=config.state_file_warn_count, status=status)


def check_adr_backlog(config: HealthConfig) -> AdrBacklogResult:
    """Count ADR markdown files in the toolkit adr/ directory.

    Args:
        config: Health configuration with adr_backlog_warn_count threshold.

    Returns:
        AdrBacklogResult with count and pass/warn status.
    """
    count = 0
    if ADR_DIR.exists():
        count = sum(1 for p in ADR_DIR.glob("*.md"))

    status: Status = "WARN" if count > config.adr_backlog_warn_count else "OK"
    return AdrBacklogResult(
        adr_count=count,
        threshold=config.adr_backlog_warn_count,
        status=status,
        adr_dir=str(ADR_DIR),
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def check_toolkit_health(
    config: HealthConfig,
    checks: tuple[str, ...] = CHECK_NAMES,
) -> HealthReport:
    """Run all requested health checks and aggregate results.

    Args:
        config: Runtime configuration for thresholds.
        checks: Which check names to run (subset of CHECK_NAMES).

    Returns:
        HealthReport with results for each dimension and aggregated flags.
    """
    report = HealthReport(
        scan_timestamp=datetime.now(tz=timezone.utc).isoformat(),
    )

    if "hook-errors" in checks:
        report.hook_errors = check_hook_errors(config)
        msg = report.hook_errors.flag_message()
        if msg:
            report.flags.append(msg)

    if "stale-memory" in checks:
        report.stale_memory = check_stale_memory(config)
        msg = report.stale_memory.flag_message()
        if msg:
            report.flags.append(msg)

    if "state-files" in checks:
        report.state_files = check_state_files(config)
        msg = report.state_files.flag_message()
        if msg:
            report.flags.append(msg)

    if "adr-backlog" in checks:
        report.adr_backlog = check_adr_backlog(config)
        msg = report.adr_backlog.flag_message()
        if msg:
            report.flags.append(msg)

    return report


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def report_to_dict(report: HealthReport) -> dict:
    """Serialise a HealthReport to a JSON-safe dict.

    Args:
        report: The health report to serialise.

    Returns:
        Dict suitable for json.dumps.
    """
    result: dict = {
        "scan_timestamp": report.scan_timestamp,
        "has_warnings": report.has_warnings(),
        "flags": report.flags,
        "checks": {},
    }

    if report.hook_errors is not None:
        he = report.hook_errors
        result["checks"]["hook_errors"] = {
            "status": he.status,
            "db_missing": he.db_missing,
            "blocked_count": he.blocked_count,
            "total_count": he.total_count,
            "error_rate": round(he.error_rate, 1),
            "trend": he.trend,
        }

    if report.stale_memory is not None:
        sm = report.stale_memory
        result["checks"]["stale_memory"] = {
            "status": sm.status,
            "stale_count": len(sm.stale_files),
            "threshold_days": sm.threshold_days,
            "files": [{"name": f.name, "age_days": f.age_days, "project": f.project} for f in sm.stale_files],
        }

    if report.state_files is not None:
        sf = report.state_files
        result["checks"]["state_files"] = {
            "status": sf.status,
            "file_count": sf.file_count,
            "threshold": sf.threshold,
        }

    if report.adr_backlog is not None:
        ab = report.adr_backlog
        result["checks"]["adr_backlog"] = {
            "status": ab.status,
            "adr_count": ab.adr_count,
            "threshold": ab.threshold,
            "adr_dir": ab.adr_dir,
        }

    return result


def format_human_report(report: HealthReport) -> str:
    """Format a HealthReport for human-readable terminal output.

    Args:
        report: The health report to format.

    Returns:
        Multi-line string suitable for print().
    """
    lines: list[str] = [
        f"Toolkit Health Report — {report.scan_timestamp}",
        "",
    ]

    def status_prefix(s: Status) -> str:
        return "[WARN]" if s == "WARN" else "[ OK ]"

    if report.hook_errors is not None:
        he = report.hook_errors
        if he.db_missing:
            lines.append("[ OK ] hook-errors: learning.db not found — skipped")
        else:
            lines.append(
                f"{status_prefix(he.status)} hook-errors: "
                f"{he.error_rate:.1f}% ({he.blocked_count}/{he.total_count} blocked, last 7d), "
                f"trend={he.trend}"
            )

    if report.stale_memory is not None:
        sm = report.stale_memory
        lines.append(
            f"{status_prefix(sm.status)} stale-memory: "
            f"{len(sm.stale_files)} stale files (threshold: >{STALE_MEMORY_WARN_COUNT}, "
            f"staleness: >{sm.threshold_days}d)"
        )
        for f in sm.stale_files[:5]:
            lines.append(f"         {f.name} — {f.age_days}d (project: {f.project})")

    if report.state_files is not None:
        sf = report.state_files
        lines.append(f"{status_prefix(sf.status)} state-files: {sf.file_count} files (threshold: {sf.threshold})")

    if report.adr_backlog is not None:
        ab = report.adr_backlog
        lines.append(f"{status_prefix(ab.status)} adr-backlog: {ab.adr_count} ADRs (threshold: {ab.threshold})")

    if report.flags:
        lines.append("")
        lines.append("Warnings:")
        for flag in report.flags:
            lines.append(f"  - {flag}")
    else:
        lines.append("")
        lines.append("All systems nominal.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_config(config_path: Path | None) -> HealthConfig:
    """Load health configuration from a JSON file.

    Falls back to defaults if the file does not exist.

    Args:
        config_path: Optional path to kairos.json config.

    Returns:
        HealthConfig with values from file or defaults.

    Raises:
        SystemExit: If the config file exists but cannot be parsed.
    """
    defaults = HealthConfig()
    if config_path is None:
        return defaults

    if not config_path.exists():
        return defaults

    try:
        raw = json.loads(config_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Error: Cannot parse config {config_path}: {exc}", file=sys.stderr)
        sys.exit(2)

    thresholds = raw.get("thresholds", {})
    return HealthConfig(
        stale_memory_days=thresholds.get("stale_memory_days", defaults.stale_memory_days),
        state_file_warn_count=thresholds.get("state_file_warn_count", defaults.state_file_warn_count),
        adr_backlog_warn_count=thresholds.get("adr_backlog_warn_count", defaults.adr_backlog_warn_count),
        hook_error_rate_threshold=thresholds.get("hook_error_rate_threshold", defaults.hook_error_rate_threshold),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for toolkit-health.py."""
    parser = argparse.ArgumentParser(
        prog="toolkit-health.py",
        description="Toolkit health checks: hook errors, stale memory, state files, ADR backlog.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 scripts/toolkit-health.py\n"
            "  python3 scripts/toolkit-health.py --json\n"
            "  python3 scripts/toolkit-health.py --check hook-errors --check adr-backlog\n"
            "  python3 scripts/toolkit-health.py --config ~/.claude/config/kairos.json\n"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON for machine consumption",
    )
    parser.add_argument(
        "--check",
        action="append",
        dest="checks",
        choices=list(CHECK_NAMES),
        metavar="CHECK",
        help=(f"Run only specific checks (may be repeated). Choices: {', '.join(CHECK_NAMES)}"),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to kairos.json config file (default: ~/.claude/config/kairos.json)",
    )
    return parser


def main() -> int:
    """Entry point for toolkit-health.py.

    Returns:
        0 if all checks pass, 1 if any checks warn, 2 on argument/config error.
    """
    parser = build_parser()
    args = parser.parse_args()

    config_path = args.config
    if config_path is None:
        config_path = CLAUDE_DIR / "config" / "kairos.json"

    config = load_config(config_path)

    checks_to_run: tuple[str, ...] = tuple(args.checks) if args.checks else CHECK_NAMES

    report = check_toolkit_health(config, checks=checks_to_run)

    if args.json_output:
        print(json.dumps(report_to_dict(report), indent=2))
    else:
        print(format_human_report(report))

    return 1 if report.has_warnings() else 0


if __name__ == "__main__":
    sys.exit(main())
