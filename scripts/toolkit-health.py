#!/usr/bin/env python3
"""Consolidated toolkit health checks.

Consolidates the Category C checks from kairos-lite monitor-prompt.md Phase 5
into a single structured script. Each dimension can be queried independently or
all at once.

Two hook dimensions, from two stores:
    hook-errors   crashes: entries hook_error() appended to hook-errors.jsonl.
                  WARN when one hook crashed more than the threshold in 7 days.
    hook-denials  denials: governance_events rows in learning.db. Every recorded
                  row is a hook doing its job, so this is a count and never warns.

Usage:
    python3 scripts/toolkit-health.py                  # human-readable report
    python3 scripts/toolkit-health.py --json           # machine-readable JSON
    python3 scripts/toolkit-health.py --check hook-errors
    python3 scripts/toolkit-health.py --check hook-denials
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
import os
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


def learning_db_path() -> Path:
    """The store the hooks write: ``$CLAUDE_LEARNING_DIR/learning.db``, else ``~/.claude/learning/learning.db``.

    Same rule as ``hooks/lib/learning_db_v2.get_db_dir()``, without importing that module.
    """
    env_dir = os.environ.get("CLAUDE_LEARNING_DIR")
    return (Path(env_dir) if env_dir else CLAUDE_DIR / "learning") / "learning.db"


LEARNING_DB = learning_db_path()
MEMORY_PROJECTS_DIR = CLAUDE_DIR / "projects"
STATE_DIR = CLAUDE_DIR / "state"
ADR_DIR = Path(__file__).resolve().parent.parent / "adr"

HOOK_ERRORS_JSONL = CLAUDE_DIR / "learning" / "hook-errors.jsonl"
HOOK_WINDOW_DAYS = 7
# Same bar as the repeat-offender check in scripts/validate-hook-health.py.
HOOK_CRASH_WARN_COUNT = 5  # crashes of one hook inside the window
HOOK_CRASH_TOP_N = 5
STALE_MEMORY_WARN_COUNT = 5
STATE_FILE_WARN_COUNT = 50
ADR_BACKLOG_WARN_COUNT = 20

CHECK_NAMES = ("hook-errors", "hook-denials", "stale-memory", "state-files", "adr-backlog")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

Status = Literal["OK", "WARN"]


Trend = Literal["INCREASING", "STABLE", "DECREASING"]


@dataclass
class HookErrorResult:
    """Hook crashes recorded in hook-errors.jsonl over the window."""

    crash_count: int
    by_hook: list[tuple[str, int]]  # most crashes first
    trend: Trend
    threshold: int
    status: Status
    log_missing: bool = False

    def flag_message(self) -> str | None:
        if self.status != "WARN":
            return None
        over = [f"{hook} ({count})" for hook, count in self.by_hook if count > self.threshold]
        return (
            f"Hook crashes: {self.crash_count} in the last {HOOK_WINDOW_DAYS}d; "
            f"more than {self.threshold} from {', '.join(over[:HOOK_CRASH_TOP_N])}, trending {self.trend}"
        )


@dataclass
class HookDenialResult:
    """Hook denials recorded in governance_events over the window. A count, never an alarm."""

    denial_count: int
    event_count: int
    trend: Trend
    status: Status = "OK"
    db_missing: bool = False

    def flag_message(self) -> str | None:
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
    hook_crash_warn_count: int = HOOK_CRASH_WARN_COUNT


@dataclass
class HealthReport:
    """Aggregated health report for all dimensions."""

    hook_errors: HookErrorResult | None = None
    hook_denials: HookDenialResult | None = None
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


def hook_errors_path() -> Path:
    """The crash log hook_error() appends to: ``$CLAUDE_HOOK_ERRORS_PATH``, else the default.

    Same rule as ``hooks/lib/hook_utils._hook_errors_path()``, without importing that module.
    """
    override = os.environ.get("CLAUDE_HOOK_ERRORS_PATH")
    return Path(override) if override else HOOK_ERRORS_JSONL


def _trend(recent: int, older: int) -> Trend:
    """Compare the newer half of the window with the older half."""
    if recent > older * 1.5:
        return "INCREASING"
    if older > 0 and recent < older * 0.5:
        return "DECREASING"
    return "STABLE"


def _entry_time(value: object) -> datetime | None:
    """A hook-errors.jsonl ``ts`` as aware UTC. hook_error() writes UTC; a naive value is read as UTC."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def check_hook_errors(config: HealthConfig) -> HookErrorResult:
    """Count hook crashes in hook-errors.jsonl over the last 7 days, per hook, with trend.

    Lines that are not JSON objects, or carry no readable ``ts``, are skipped.

    Args:
        config: Health configuration with thresholds.

    Returns:
        HookErrorResult. WARN when one hook crashed more than the threshold.
    """
    threshold = config.hook_crash_warn_count
    missing = HookErrorResult(
        crash_count=0, by_hook=[], trend="STABLE", threshold=threshold, status="OK", log_missing=True
    )
    path = hook_errors_path()
    if not path.is_file():
        return missing

    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(days=HOOK_WINDOW_DAYS)
    cutoff_recent = now - timedelta(days=HOOK_WINDOW_DAYS / 2)
    counts: dict[str, int] = {}
    recent = older = 0
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(entry, dict):
                    continue
                ts = _entry_time(entry.get("ts"))
                if ts is None or ts <= cutoff:
                    continue
                hook = entry.get("hook")
                if not isinstance(hook, str) or not hook:
                    hook = "unknown"
                counts[hook] = counts.get(hook, 0) + 1
                if ts > cutoff_recent:
                    recent += 1
                else:
                    older += 1
    except OSError:
        return missing

    by_hook = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    status: Status = "WARN" if by_hook and by_hook[0][1] > threshold else "OK"
    return HookErrorResult(
        crash_count=recent + older,
        by_hook=by_hook,
        trend=_trend(recent, older),
        threshold=threshold,
        status=status,
    )


def check_hook_denials(config: HealthConfig) -> HookDenialResult:
    """Count hook denials in learning.db governance_events over the last 7 days, with trend.

    Every caller of record_governance() is a deny or warn path, so blocked/total
    is near 100% by construction and says nothing about hook health. This check
    reports the count and never warns.

    Args:
        config: Health configuration (unused; kept for a uniform check signature).

    Returns:
        HookDenialResult with counts and trend. Status is always OK.
    """
    missing = HookDenialResult(denial_count=0, event_count=0, trend="STABLE", db_missing=True)
    if not LEARNING_DB.exists():
        return missing

    # governance_events.created_at holds naive local time, compared as text (see
    # learning_db_v2.governance_timestamp). A UTC or offset-suffixed cutoff here
    # shifts the window by the local UTC offset.
    now = datetime.now()
    cutoff_7d = (now - timedelta(days=HOOK_WINDOW_DAYS)).isoformat()
    cutoff_recent = (now - timedelta(days=HOOK_WINDOW_DAYS / 2)).isoformat()

    conn = None
    try:
        # Read-only: the hooks own this database, and a health check never writes to it.
        conn = sqlite3.connect(f"{LEARNING_DB.absolute().as_uri()}?mode=ro", uri=True)
        denial_count = conn.execute(
            "SELECT COUNT(*) FROM governance_events WHERE blocked=1 AND created_at > ?",
            (cutoff_7d,),
        ).fetchone()[0]

        event_count = conn.execute(
            "SELECT COUNT(*) FROM governance_events WHERE created_at > ?",
            (cutoff_7d,),
        ).fetchone()[0]

        recent_denials = conn.execute(
            "SELECT COUNT(*) FROM governance_events WHERE blocked=1 AND created_at > ?",
            (cutoff_recent,),
        ).fetchone()[0]
    except sqlite3.OperationalError:
        # No governance_events table yet (fresh install), or the file cannot be opened read-only
        return missing
    finally:
        if conn is not None:
            conn.close()

    return HookDenialResult(
        denial_count=denial_count,
        event_count=event_count,
        trend=_trend(recent_denials, denial_count - recent_denials),
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

    if "hook-denials" in checks:
        report.hook_denials = check_hook_denials(config)

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
            "log_missing": he.log_missing,
            "crash_count": he.crash_count,
            "threshold": he.threshold,
            "trend": he.trend,
            "by_hook": [{"hook": hook, "count": count} for hook, count in he.by_hook],
        }

    if report.hook_denials is not None:
        hd = report.hook_denials
        result["checks"]["hook_denials"] = {
            "status": hd.status,
            "db_missing": hd.db_missing,
            "denial_count": hd.denial_count,
            "event_count": hd.event_count,
            "trend": hd.trend,
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
        if he.log_missing:
            lines.append("[ OK ] hook-errors: hook-errors.jsonl not found — skipped")
        else:
            lines.append(
                f"{status_prefix(he.status)} hook-errors: "
                f"{he.crash_count} crashes (last {HOOK_WINDOW_DAYS}d, per-hook threshold: >{he.threshold}), "
                f"trend={he.trend}"
            )
            for hook, count in he.by_hook[:HOOK_CRASH_TOP_N]:
                lines.append(f"         {hook} — {count}")

    if report.hook_denials is not None:
        hd = report.hook_denials
        if hd.db_missing:
            lines.append("[ OK ] hook-denials: learning.db not found — skipped")
        else:
            lines.append(
                f"[ OK ] hook-denials: {hd.denial_count} denials of {hd.event_count} governance events "
                f"(last {HOOK_WINDOW_DAYS}d, count only), trend={hd.trend}"
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
        # The retired "hook_error_rate_threshold" key is ignored: that rate was denials, not errors.
        hook_crash_warn_count=thresholds.get("hook_crash_warn_count", defaults.hook_crash_warn_count),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for toolkit-health.py."""
    parser = argparse.ArgumentParser(
        prog="toolkit-health.py",
        description="Toolkit health checks: hook crashes, hook denials, stale memory, state files, ADR backlog.",
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
