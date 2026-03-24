#!/usr/bin/env python3
"""
GitHub Notification Triage — classify and report on unread GitHub notifications.

Fetches all unread notifications via the gh CLI, classifies each by reason,
and outputs an action report. Never marks notifications as read unless
--mark-read is explicitly passed.

Usage:
    python3 scripts/github-notification-triage.py              # Report only (default)
    python3 scripts/github-notification-triage.py --mark-read  # Report + mark informational as read
    python3 scripts/github-notification-triage.py --dry-run    # Same as default (explicit)
    python3 scripts/github-notification-triage.py --json       # JSON output for automation
    python3 scripts/github-notification-triage.py --save       # Save report to ~/.claude/reports/notifications/

Classification:
    Action Required:   review_requested, mention, assign, <unknown>
    Author:            author (always surface)
    CI:                ci_activity (show if failed, otherwise informational)
    Informational:     subscribed, state_change, team_mention

Exit codes:
    0 = success
    1 = error (gh not installed, not authenticated, API failure)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Classification constants
# ---------------------------------------------------------------------------

_ACTION_REQUIRED_REASONS = {"review_requested", "mention", "assign"}
_INFORMATIONAL_REASONS = {"subscribed", "state_change", "team_mention"}
_CI_REASONS = {"ci_activity"}
_AUTHOR_REASONS = {"author"}

# Labels for display
_REASON_LABELS: dict[str, str] = {
    "review_requested": "Reviews Waiting",
    "mention": "Direct Mentions",
    "assign": "Assigned",
    "author": "Your Items (author activity)",
    "ci_activity": "CI Activity",
    "subscribed": "subscribed",
    "state_change": "state_change",
    "team_mention": "team_mention",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Notification:
    """A single GitHub notification."""

    id: str
    reason: str
    title: str
    subject_type: str
    subject_url: str
    repo_full_name: str
    updated_at: str
    thread_url: str
    html_url: str = ""

    @property
    def age_display(self) -> str:
        """Return a human-readable relative age string like '2h ago' or '3d ago'."""
        try:
            dt = datetime.fromisoformat(self.updated_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = now - dt
            total_seconds = int(delta.total_seconds())
            if total_seconds < 3600:
                minutes = max(1, total_seconds // 60)
                return f"{minutes}m ago"
            if total_seconds < 86400:
                hours = total_seconds // 3600
                return f"{hours}h ago"
            days = total_seconds // 86400
            return f"{days}d ago"
        except (ValueError, AttributeError):
            return "unknown"

    @property
    def pr_or_issue_number(self) -> str:
        """Extract PR/issue number from subject URL, e.g. '#142'."""
        if self.subject_url:
            parts = self.subject_url.rstrip("/").split("/")
            for part in reversed(parts):
                if part.isdigit():
                    return f"#{part}"
        return ""

    @property
    def display_ref(self) -> str:
        """Short display reference like 'sapcc/go-bits#142'."""
        num = self.pr_or_issue_number
        if num:
            return f"{self.repo_full_name}{num}"
        return self.repo_full_name

    @property
    def browse_url(self) -> str:
        """Best URL for a human to open in browser."""
        if self.html_url:
            return self.html_url
        # Convert API URL to browser URL
        url = self.subject_url
        if url.startswith("https://api.github.com/repos/"):
            url = url.replace("https://api.github.com/repos/", "https://github.com/")
            url = url.replace("/pulls/", "/pull/")
        return url


@dataclass
class TriageResult:
    """Classified notifications grouped by category."""

    action_required: list[Notification] = field(default_factory=list)
    author: list[Notification] = field(default_factory=list)
    ci_failures: list[Notification] = field(default_factory=list)
    ci_informational: list[Notification] = field(default_factory=list)
    informational: list[Notification] = field(default_factory=list)
    unknown: list[Notification] = field(default_factory=list)

    def all_informational_ids(self) -> list[str]:
        """IDs eligible to be marked as read with --mark-read."""
        ids: list[str] = []
        for n in self.informational:
            ids.append(n.id)
        for n in self.ci_informational:
            ids.append(n.id)
        return ids

    def informational_by_reason(self) -> dict[str, int]:
        """Count of informational notifications grouped by reason."""
        counts: dict[str, int] = defaultdict(int)
        for n in self.informational:
            counts[n.reason] += 1
        return dict(counts)


# ---------------------------------------------------------------------------
# gh CLI helpers
# ---------------------------------------------------------------------------


def _run_gh(*args: str, input_data: str | None = None) -> tuple[str, int]:
    """Run a gh CLI command and return (stdout, returncode).

    Does not raise on non-zero exit — callers decide how to handle errors.
    """
    cmd = ["gh", *args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_data,
    )
    return result.stdout, result.returncode


def check_gh_available() -> bool:
    """Return True if gh is installed and authenticated."""
    _, rc = _run_gh("auth", "status")
    return rc == 0


def fetch_notifications() -> list[dict]:
    """Fetch all unread notifications via gh CLI.

    Returns list of raw notification dicts.
    Exits 1 on error.
    """
    stdout, rc = _run_gh("api", "notifications", "--paginate")
    if rc != 0:
        print("ERROR: Failed to fetch notifications via gh CLI.", file=sys.stderr)
        print("       Run 'gh auth status' to check authentication.", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        print(f"ERROR: Could not parse GitHub API response: {exc}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, list):
        print(f"ERROR: Unexpected response shape from GitHub API: {type(data)}", file=sys.stderr)
        sys.exit(1)

    return data


def mark_thread_read(thread_id: str) -> bool:
    """Mark a single notification thread as read. Returns True on success."""
    _, rc = _run_gh("api", "-X", "PATCH", f"/notifications/threads/{thread_id}")
    return rc == 0


def resolve_html_url(subject_url: str) -> str:
    """Attempt to resolve an API subject URL to a browser HTML URL.

    Falls back to converting the URL pattern instead of making an API call,
    to keep the script fast on large notification counts.
    """
    # Convert API URL patterns to browser URLs without extra API calls
    if subject_url.startswith("https://api.github.com/repos/"):
        url = subject_url.replace("https://api.github.com/repos/", "https://github.com/")
        url = url.replace("/pulls/", "/pull/")
        return url
    return subject_url


# ---------------------------------------------------------------------------
# Parsing + classification
# ---------------------------------------------------------------------------


def parse_notification(raw: dict) -> Notification:
    """Parse a raw GitHub API notification dict into a Notification."""
    subject = raw.get("subject") or {}
    repo = raw.get("repository") or {}

    subject_url = subject.get("url") or ""
    html_url = resolve_html_url(subject_url)

    return Notification(
        id=str(raw.get("id", "")),
        reason=raw.get("reason", "unknown"),
        title=subject.get("title", "(no title)"),
        subject_type=subject.get("type", ""),
        subject_url=subject_url,
        repo_full_name=repo.get("full_name", ""),
        updated_at=raw.get("updated_at", ""),
        thread_url=raw.get("url", ""),
        html_url=html_url,
    )


def classify(notifications: list[Notification]) -> TriageResult:
    """Classify a list of notifications into a TriageResult."""
    result = TriageResult()

    for n in notifications:
        if n.reason in _ACTION_REQUIRED_REASONS:
            result.action_required.append(n)
        elif n.reason in _AUTHOR_REASONS:
            result.author.append(n)
        elif n.reason in _CI_REASONS:
            # For v1, all CI activity is shown as "CI failures" section
            # (we don't have pass/fail detail without extra API calls)
            result.ci_failures.append(n)
        elif n.reason in _INFORMATIONAL_REASONS:
            result.informational.append(n)
        else:
            # Unknown reasons default to action-required (safe, not destructive)
            result.unknown.append(n)

    return result


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def _format_action_items(notifications: list[Notification], group_by_reason: bool = True) -> list[str]:
    """Format action-required notifications grouped by reason label."""
    lines: list[str] = []

    if group_by_reason:
        by_reason: dict[str, list[Notification]] = defaultdict(list)
        for n in notifications:
            by_reason[n.reason].append(n)

        # Emit in priority order: review_requested, mention, assign, then unknown
        ordered_reasons = ["review_requested", "mention", "assign"]
        # Add any unknown reasons not in the ordered list
        for reason in by_reason:
            if reason not in ordered_reasons:
                ordered_reasons.append(reason)

        for reason in ordered_reasons:
            group = by_reason.get(reason)
            if not group:
                continue
            label = _REASON_LABELS.get(reason, reason.replace("_", " ").title())
            lines.append(f"\n**{label}:**")
            for n in group:
                lines.append(f'- [ ] {n.display_ref} — "{n.title}" ({n.age_display})')
                lines.append(f"      {n.browse_url}")
    else:
        for n in notifications:
            lines.append(f'- [ ] {n.display_ref} — "{n.title}" ({n.age_display})')
            lines.append(f"      {n.browse_url}")

    return lines


def format_report(result: TriageResult, date_str: str) -> str:
    """Format the full triage report as a markdown string."""
    lines: list[str] = []

    lines.append(f"## GitHub Notification Triage — {date_str}")
    lines.append("")

    # --- Action Required ---
    action_all = result.action_required + result.unknown
    lines.append(f"### Action Required ({len(action_all)} items)")

    if action_all:
        lines.extend(_format_action_items(action_all, group_by_reason=True))
    else:
        lines.append("\nNo action-required notifications.")

    lines.append("")

    # --- Author ---
    lines.append("### Your Items (author activity — review if needed)")
    if result.author:
        for n in result.author:
            lines.append(f"- {n.display_ref} — new activity ({n.age_display})")
    else:
        lines.append("- (none)")

    lines.append("")

    # --- CI ---
    lines.append("### CI Failures (your PRs)")
    if result.ci_failures:
        for n in result.ci_failures:
            lines.append(f"- {n.display_ref} — {n.title}")
    else:
        lines.append("- (none)")

    lines.append("")

    # --- Summary ---
    lines.append("### Summary")
    lines.append(f"- Action required: {len(action_all)}")
    lines.append(f"- Author activity: {len(result.author)}")
    lines.append(f"- CI activity: {len(result.ci_failures)}")

    info_total = len(result.informational)
    lines.append(f"- Informational (would clear with --mark-read): {info_total}")
    for reason, count in sorted(result.informational_by_reason().items()):
        lines.append(f"  - {reason}: {count}")

    return "\n".join(lines)


def format_json(result: TriageResult, date_str: str) -> str:
    """Format the triage result as structured JSON."""

    def _serialize(n: Notification) -> dict:
        return {
            "id": n.id,
            "reason": n.reason,
            "title": n.title,
            "ref": n.display_ref,
            "url": n.browse_url,
            "age": n.age_display,
            "updated_at": n.updated_at,
        }

    action_all = result.action_required + result.unknown
    output = {
        "date": date_str,
        "action_required": [_serialize(n) for n in action_all],
        "author": [_serialize(n) for n in result.author],
        "ci_failures": [_serialize(n) for n in result.ci_failures],
        "informational": [_serialize(n) for n in result.informational],
        "summary": {
            "action_required": len(action_all),
            "author_activity": len(result.author),
            "ci_activity": len(result.ci_failures),
            "informational_total": len(result.informational),
            "informational_by_reason": result.informational_by_reason(),
        },
    }
    return json.dumps(output, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Triage GitHub notifications — report-only by default.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mark-read",
        action="store_true",
        help="Mark informational notifications as read after reporting.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report only, never mark as read (same as default, explicit).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output structured JSON instead of markdown report.",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save the report to ~/.claude/reports/notifications/{date}.md",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # --dry-run and --mark-read are mutually exclusive; dry-run wins
    do_mark_read = args.mark_read and not args.dry_run

    # Check gh is available
    if not check_gh_available():
        print("ERROR: 'gh' is not installed or not authenticated.", file=sys.stderr)
        print("       Install: https://cli.github.com/", file=sys.stderr)
        print("       Authenticate: gh auth login", file=sys.stderr)
        return 1

    # Fetch
    raw_notifications = fetch_notifications()
    notifications = [parse_notification(r) for r in raw_notifications]

    # Classify
    result = classify(notifications)

    # Format
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if args.json_output:
        output = format_json(result, date_str)
    else:
        output = format_report(result, date_str)

    print(output)

    # Save
    if args.save:
        reports_dir = Path.home() / ".claude" / "reports" / "notifications"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"{date_str}.md"
        # Use markdown content even if --json was also passed
        md_content = format_report(result, date_str) if args.json_output else output
        report_path.write_text(md_content, encoding="utf-8")
        print(f"\nReport saved to: {report_path}", file=sys.stderr)

    # Mark informational as read
    if do_mark_read:
        ids_to_clear = result.all_informational_ids()
        if not ids_to_clear:
            print("\nNo informational notifications to clear.", file=sys.stderr)
        else:
            print(f"\nMarking {len(ids_to_clear)} informational notifications as read...", file=sys.stderr)
            failed = 0
            for thread_id in ids_to_clear:
                if not mark_thread_read(thread_id):
                    failed += 1
            if failed:
                print(f"WARNING: {failed}/{len(ids_to_clear)} threads could not be marked as read.", file=sys.stderr)
            else:
                print(f"Cleared {len(ids_to_clear)} notifications.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
