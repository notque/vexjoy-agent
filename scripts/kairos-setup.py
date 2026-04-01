#!/usr/bin/env python3
"""KAIROS-lite setup script.

Creates the config file, validates prerequisites, and installs cron jobs for
KAIROS-lite monitoring. Idempotent: safe to run multiple times.

Usage:
    python3 scripts/kairos-setup.py
    python3 scripts/kairos-setup.py --non-interactive
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KAIROS_MARKER = "KAIROS-lite"
CONFIG_DIR = Path.home() / ".claude" / "config"
CONFIG_FILE = CONFIG_DIR / "kairos.json"
LOG_DIR = Path.home() / ".claude" / "logs"
TOOLKIT_DIR = Path("/home/feedgen/claude-code-toolkit")

CRON_BLOCK = """\
# KAIROS-lite: Quick check every 4 hours during business hours
0 8,12,16,20 * * * cd /home/feedgen/claude-code-toolkit && CLAUDE_KAIROS_ENABLED=true claude -p "$(cat skills/kairos-lite/monitor-prompt.md)" --model sonnet >> /tmp/claude-kairos.log 2>&1

# KAIROS-lite: Deep scan nightly at 2:30 AM
30 2 * * * cd /home/feedgen/claude-code-toolkit && CLAUDE_KAIROS_ENABLED=true KAIROS_MODE=deep claude -p "$(cat skills/kairos-lite/monitor-prompt.md)" --model sonnet >> /tmp/claude-kairos.log 2>&1"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def info(msg: str) -> None:
    """Print a status message with the [kairos] prefix."""
    print(f"[kairos] {msg}")


def error(msg: str) -> None:
    """Print an error message and flush immediately."""
    print(f"[kairos] ERROR: {msg}", file=sys.stderr)


def run(cmd: list[str], *, capture: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a subprocess and return the result."""
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
    )


# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------


def check_gh_auth() -> bool:
    """Return True if `gh auth status` succeeds."""
    result = run(["gh", "auth", "status"])
    if result.returncode != 0:
        error("gh auth status failed — run `gh auth login` first.")
        error(result.stderr.strip() if result.stderr else "(no output)")
        return False
    info("gh auth: OK")
    return True


def check_claude_cli() -> None:
    """Warn (but don't abort) if the claude CLI is missing."""
    if shutil.which("claude") is None:
        print("[kairos] WARN: `claude` CLI not found on PATH — cron jobs will fail until it is installed.")
    else:
        info("claude CLI: OK")


def check_cron() -> bool:
    """Return True if crontab is usable."""
    result = run(["crontab", "-l"])
    # exit 1 with "no crontab for …" is normal on a fresh system
    if result.returncode not in (0, 1):
        error("crontab -l failed unexpectedly — is cron installed?")
        return False
    info("cron: OK")
    return True


def validate_prerequisites() -> bool:
    """Run all prerequisite checks. Return False if any hard check fails."""
    ok = True
    if not check_gh_auth():
        ok = False
    check_claude_cli()  # warn only
    if not check_cron():
        ok = False
    return ok


# ---------------------------------------------------------------------------
# Repo detection
# ---------------------------------------------------------------------------


def detect_repo() -> tuple[str, str] | None:
    """Return (owner, repo) parsed from the git remote origin URL, or None."""
    result = run(["git", "remote", "get-url", "origin"])
    if result.returncode != 0:
        return None
    url = result.stdout.strip()
    # Handles both HTTPS and SSH variants:
    #   https://github.com/owner/repo.git
    #   git@github.com:owner/repo.git
    for sep in ("github.com/", "github.com:"):
        if sep in url:
            path = url.split(sep, 1)[1]
            path = path.removesuffix(".git")
            parts = path.split("/")
            if len(parts) >= 2:
                return parts[0], parts[1]
    return None


def determine_targets(non_interactive: bool) -> tuple[str, str]:
    """Return (owner, repo) after optional interactive confirmation."""
    detected = detect_repo()
    default_owner = detected[0] if detected else "unknown"
    default_repo = detected[1] if detected else "unknown"

    if non_interactive or not sys.stdin.isatty():
        info(f"Using detected repo: {default_owner}/{default_repo}")
        return default_owner, default_repo

    # Interactive: let the user confirm or override.
    print(f"[kairos] Detected repo: {default_owner}/{default_repo}")
    owner_input = input(f"[kairos] Owner [{default_owner}]: ").strip()
    repo_input = input(f"[kairos] Repo  [{default_repo}]: ").strip()
    owner = owner_input or default_owner
    repo = repo_input or default_repo
    return owner, repo


# ---------------------------------------------------------------------------
# Config file
# ---------------------------------------------------------------------------


def build_config(owner: str, repo: str) -> dict:
    """Build the kairos.json config dict."""
    return {
        "version": 1,
        "enabled": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repos": [
            {
                "owner": owner,
                "repo": repo,
                "branches": ["main"],
                "check_ci": True,
                "check_prs": True,
                "check_issues": True,
                "check_dependabot": True,
            }
        ],
        "business_hours": {
            "start": 8,
            "end": 20,
            "timezone": "UTC",
        },
        "deep_scan": {
            "enabled": True,
            "hour": 2,
        },
        "briefing": {
            "max_age_hours": 24,
            "max_injection_tokens": 400,
        },
        "thresholds": {
            "stale_branch_days": 7,
            "stale_memory_days": 14,
            "hook_error_rate_pct": 10,
            "pr_review_wait_hours": 24,
        },
    }


def write_config(owner: str, repo: str) -> None:
    """Write kairos.json to ~/.claude/config/, creating the directory if needed."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = build_config(owner, repo)
    CONFIG_FILE.write_text(json.dumps(config, indent=2) + "\n")
    info(f"Config written: {CONFIG_FILE}")


# ---------------------------------------------------------------------------
# Cron installation
# ---------------------------------------------------------------------------


def read_crontab() -> str:
    """Return the current crontab as a string (empty string if none set)."""
    result = run(["crontab", "-l"])
    if result.returncode == 0:
        return result.stdout
    # "no crontab for user" — treat as empty
    return ""


def write_crontab(content: str) -> bool:
    """Write content as the new crontab. Returns True on success."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".crontab", delete=False) as fh:
        fh.write(content)
        tmp_path = fh.name
    result = run(["crontab", tmp_path])
    Path(tmp_path).unlink(missing_ok=True)
    return result.returncode == 0


def install_cron_jobs() -> None:
    """Add KAIROS-lite cron entries if not already present."""
    existing = read_crontab()

    if KAIROS_MARKER in existing:
        info("Cron jobs already installed — skipping.")
        return

    separator = "\n" if existing and not existing.endswith("\n") else ""
    new_crontab = existing + separator + CRON_BLOCK + "\n"

    if write_crontab(new_crontab):
        info("Cron jobs installed.")
    else:
        error("Failed to write crontab. Run `crontab -e` to add entries manually.")


# ---------------------------------------------------------------------------
# Log directory
# ---------------------------------------------------------------------------


def ensure_log_dir() -> None:
    """Create ~/.claude/logs/ if it does not exist."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    info(f"Log directory: {LOG_DIR}")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def print_summary(owner: str, repo: str) -> None:
    """Print post-setup instructions."""
    print()
    print("[kairos] Setup complete.")
    print()
    print(f"  Config:   {CONFIG_FILE}")
    print(f"  Repo:     {owner}/{repo}")
    print(f"  Logs:     /tmp/claude-kairos.log")
    print()
    print("  Cron schedule:")
    print("    Every 4 h (08:00, 12:00, 16:00, 20:00 UTC)  — quick check")
    print("    Daily at 02:30 UTC                           — deep scan")
    print()
    print("  Manual check:")
    print(
        "    cd /home/feedgen/claude-code-toolkit && "
        'CLAUDE_KAIROS_ENABLED=true claude -p "$(cat skills/kairos-lite/monitor-prompt.md)" --model sonnet'
    )
    print()
    print("  To disable:")
    print("    Run `crontab -e` and remove the KAIROS-lite block, or")
    print("    unset CLAUDE_KAIROS_ENABLED in your environment.")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Configure KAIROS-lite monitoring: config, prerequisites, cron.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Skip confirmation prompts; use auto-detected values.",
    )
    return parser.parse_args()


def main() -> int:
    """Run KAIROS-lite setup. Returns exit code."""
    args = parse_args()

    info("Starting KAIROS-lite setup...")
    print()

    # 1. Prerequisites
    info("Checking prerequisites...")
    if not validate_prerequisites():
        return 1
    print()

    # 2. Monitoring targets
    info("Determining monitoring targets...")
    owner, repo = determine_targets(non_interactive=args.non_interactive)
    print()

    # 3. Config file
    info("Writing config file...")
    write_config(owner, repo)
    print()

    # 4. Log directory
    info("Ensuring log directory...")
    ensure_log_dir()
    print()

    # 5. Cron jobs
    info("Installing cron jobs...")
    install_cron_jobs()
    print()

    # 6. Summary
    print_summary(owner, repo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
