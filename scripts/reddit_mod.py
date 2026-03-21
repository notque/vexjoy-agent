#!/usr/bin/env python3
"""
Reddit moderation CLI using PRAW.

Fetch modqueue items, reported content, unmoderated posts, and take mod actions.
Designed for use by Claude in /loop automation or standalone CLI usage.

Usage:
    reddit_mod.py setup --subreddit mysubreddit
    reddit_mod.py subreddit-info --subreddit mysubreddit --json
    reddit_mod.py mod-log-summary --subreddit mysubreddit --limit 500
    reddit_mod.py queue --subreddit mysubreddit --limit 10
    reddit_mod.py reports --subreddit mysubreddit --json
    reddit_mod.py unmoderated --subreddit mysubreddit --limit 25
    reddit_mod.py approve --id t3_abc123
    reddit_mod.py remove --id t3_abc123 --reason "Rule 3 violation"
    reddit_mod.py remove --id t1_xyz789 --reason "Spam" --spam
    reddit_mod.py lock --id t3_abc123
    reddit_mod.py user-history --username someuser --limit 20
    reddit_mod.py rules --subreddit mysubreddit
    reddit_mod.py modmail --subreddit mysubreddit --limit 10 --state all
    reddit_mod.py scan --subreddit mysubreddit --limit 50 --since-hours 24

Environment variables (set in ~/.env or export directly):
    REDDIT_CLIENT_ID="your_client_id"
    REDDIT_CLIENT_SECRET="your_client_secret"
    REDDIT_USERNAME="your_bot_username"
    REDDIT_PASSWORD="your_bot_password"
    REDDIT_SUBREDDIT="your_default_subreddit"

Exit codes:
    0 = success
    1 = runtime error (network, invalid ID, API failure)
    2 = configuration error (missing credentials, missing praw)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Auto-load ~/.env before any os.environ access
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.expanduser("~/.env"))
except ImportError:
    pass  # dotenv optional — env vars can be set directly

praw = None  # lazy import — see _ensure_praw()
PrawcoreException = Exception  # fallback base for type hints until praw is loaded
OAuthException = Exception
NotFound = Exception
Forbidden = Exception
TooManyRequests = Exception
ServerError = Exception


# --- Constants ---

_DEFAULT_LIMIT = 25
_MAX_LIMIT = 100
_BODY_TRUNCATE = 500
_USER_AGENT = "python:reddit_mod:v1.0 (by /u/claude-code-toolkit)"

_REQUIRED_ENV_VARS = [
    "REDDIT_CLIENT_ID",
    "REDDIT_CLIENT_SECRET",
    "REDDIT_USERNAME",
    "REDDIT_PASSWORD",
]

_FULLNAME_RE = re.compile(r"^t[13]_[a-z0-9]{1,10}$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
_SUBREDDIT_RE = re.compile(r"^[A-Za-z0-9_]{2,21}$")

_DATA_DIR = Path(__file__).resolve().parent.parent / "reddit-data"
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "reddit"

_DEFAULT_CONFIG: dict[str, object] = {
    "confidence_auto_approve": 95,
    "confidence_auto_remove": 90,
    "trust_reporters": True,
    "community_type": "professional-technical",
    "max_auto_actions_per_run": 25,
    "required_language": None,
    "scan_recent_hours": 24,
    "scan_limit": 50,
}

# Heuristic patterns for scan_flags detection
_JOB_AD_PATTERNS = re.compile(
    r"\b(hiring|we(?:'re| are) (?:looking for|building)|job opportunity|open position|"
    r"looking for .{0,30}(?:developer|engineer|consultant|architect|freelancer)|"
    r"join our team|apply now|send your (?:cv|resume))\b",
    re.IGNORECASE,
)

_TRAINING_VENDOR_PATTERNS = re.compile(
    r"\b(register now|free demo|online training|enroll today|"
    r"certification (?:training|course|program)|training (?:course|program|institute)|"
    r"limited seats|batch starting|upcoming batch|discount (?:code|offer))\b",
    re.IGNORECASE,
)


# --- Lazy import ---


def _ensure_praw() -> None:
    """Import praw on first use, exit with instructions if missing."""
    global praw, PrawcoreException, OAuthException, NotFound, Forbidden, TooManyRequests, ServerError
    if praw is not None:
        return
    try:
        import praw as _praw
        from prawcore.exceptions import Forbidden as _Forbidden
        from prawcore.exceptions import NotFound as _NotFound
        from prawcore.exceptions import OAuthException as _OAuthException
        from prawcore.exceptions import PrawcoreException as _PrawcoreException
        from prawcore.exceptions import ServerError as _ServerError
        from prawcore.exceptions import TooManyRequests as _TooManyRequests

        praw = _praw
        PrawcoreException = _PrawcoreException
        OAuthException = _OAuthException
        NotFound = _NotFound
        Forbidden = _Forbidden
        TooManyRequests = _TooManyRequests
        ServerError = _ServerError
    except ImportError:
        print("ERROR: praw is not installed. Install it with:", file=sys.stderr)
        print("  pip install praw", file=sys.stderr)
        sys.exit(2)


# --- Credential handling ---


def _get_credentials() -> dict[str, str]:
    """Read Reddit API credentials from environment variables.

    Returns:
        Dict with client_id, client_secret, username, password.

    Raises:
        SystemExit: If any required variable is missing (exit code 2).
    """
    missing = [var for var in _REQUIRED_ENV_VARS if not os.environ.get(var)]
    if missing:
        print("ERROR: Missing required environment variables:", file=sys.stderr)
        for var in missing:
            print(f"  - {var}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Set them in ~/.env or export directly:", file=sys.stderr)
        for var in _REQUIRED_ENV_VARS:
            print(f'  {var}="your_{var.lower().removeprefix("reddit_")}"', file=sys.stderr)
        print('  REDDIT_SUBREDDIT="your_default_subreddit"  # optional', file=sys.stderr)
        sys.exit(2)

    return {
        "client_id": os.environ["REDDIT_CLIENT_ID"],
        "client_secret": os.environ["REDDIT_CLIENT_SECRET"],
        "username": os.environ["REDDIT_USERNAME"],
        "password": os.environ["REDDIT_PASSWORD"],
    }


def _build_reddit():
    """Create an authenticated PRAW Reddit instance."""
    _ensure_praw()
    creds = _get_credentials()
    return praw.Reddit(
        client_id=creds["client_id"],
        client_secret=creds["client_secret"],
        username=creds["username"],
        password=creds["password"],
        user_agent=_USER_AGENT,
    )


def _resolve_subreddit(args: argparse.Namespace) -> str:
    """Resolve subreddit from args or env, exit if neither is set."""
    sub = getattr(args, "subreddit", None) or os.environ.get("REDDIT_SUBREDDIT")
    if not sub:
        print("ERROR: No subreddit specified. Use --subreddit or set REDDIT_SUBREDDIT.", file=sys.stderr)
        sys.exit(2)
    if not _SUBREDDIT_RE.match(sub):
        print(
            f"ERROR: Invalid subreddit name '{sub}'. Must be 2-21 alphanumeric/underscore characters.",
            file=sys.stderr,
        )
        sys.exit(2)
    return sub


# --- Data models ---


@dataclass
class ModQueueItem:
    """A single item from the modqueue, reports, or unmoderated listing."""

    id: str
    fullname: str
    title: str
    author: str
    body: str
    score: int
    num_reports: int
    report_reasons: list[str]
    created_utc: float
    permalink: str
    item_type: str  # "submission" or "comment"

    @property
    def created_iso(self) -> str:
        """ISO 8601 timestamp from created_utc."""
        return datetime.fromtimestamp(self.created_utc, tz=timezone.utc).isoformat()

    @property
    def truncated_body(self) -> str:
        """Body truncated to _BODY_TRUNCATE characters."""
        if len(self.body) <= _BODY_TRUNCATE:
            return self.body
        return self.body[:_BODY_TRUNCATE] + "..."

    def to_dict(self) -> dict:
        """Serialize to dict for JSON output."""
        return {
            "id": self.id,
            "fullname": self.fullname,
            "title": self.title,
            "author": self.author,
            "body": self.truncated_body,
            "score": self.score,
            "num_reports": self.num_reports,
            "report_reasons": self.report_reasons,
            "created_utc": self.created_utc,
            "created_iso": self.created_iso,
            "permalink": f"https://reddit.com{self.permalink}",
            "item_type": self.item_type,
        }

    def format_text(self) -> str:
        """Format as human-readable text."""
        lines = [
            f"[{self.item_type.upper()}] {self.fullname}",
            f"  Title:    {self.title}" if self.title else None,
            f"  Author:   /u/{self.author}",
            f"  Score:    {self.score}",
            f"  Reports:  {self.num_reports}",
            f"  Reasons:  {', '.join(self.report_reasons)}" if self.report_reasons else None,
            f"  Created:  {self.created_iso}",
            f"  Link:     https://reddit.com{self.permalink}",
            f"  Body:     {self.truncated_body}" if self.body else None,
        ]
        return "\n".join(line for line in lines if line is not None)


@dataclass
class ModQueueResult:
    """Result from fetching a modqueue listing."""

    subreddit: str
    source: str  # "modqueue", "reports", "unmoderated"
    items: list[ModQueueItem] = field(default_factory=list)

    def format_text(self) -> str:
        """Format as human-readable text."""
        if not self.items:
            return f"No items in {self.source} for r/{self.subreddit}"
        header = f"r/{self.subreddit} — {self.source} ({len(self.items)} items)"
        separator = "=" * len(header)
        parts = [header, separator]
        for i, item in enumerate(self.items):
            if i > 0:
                parts.append("")
                parts.append("---")
            parts.append("")
            parts.append(item.format_text())
        return "\n".join(parts)

    def format_json(self) -> str:
        """Format as structured JSON."""
        data = {
            "subreddit": self.subreddit,
            "source": self.source,
            "count": len(self.items),
            "items": [item.to_dict() for item in self.items],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)


@dataclass
class UserHistory:
    """A user's recent activity summary."""

    username: str
    comment_karma: int | None
    link_karma: int | None
    account_created_utc: float | None
    is_suspended: bool
    recent_posts: list[dict] = field(default_factory=list)
    recent_comments: list[dict] = field(default_factory=list)

    @property
    def account_age_days(self) -> int | None:
        """Account age in days."""
        if self.account_created_utc is None:
            return None
        created = datetime.fromtimestamp(self.account_created_utc, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - created).days

    def format_text(self) -> str:
        """Format as human-readable text."""
        karma_comment = self.comment_karma if self.comment_karma is not None else "unknown"
        karma_link = self.link_karma if self.link_karma is not None else "unknown"
        age = self.account_age_days
        age_str = f"{age} days" if age is not None else "unknown"
        lines = [
            f"User: /u/{self.username}",
            f"  Comment karma: {karma_comment}",
            f"  Link karma:    {karma_link}",
            f"  Account age:   {age_str}",
            f"  Suspended:     {self.is_suspended}",
        ]
        if self.recent_posts:
            lines.append("")
            lines.append(f"  Recent posts ({len(self.recent_posts)}):")
            for post in self.recent_posts:
                lines.append(f"    - [{post['score']}] {post['title'][:80]}")
                lines.append(f"      {post['permalink']}")
        if self.recent_comments:
            lines.append("")
            lines.append(f"  Recent comments ({len(self.recent_comments)}):")
            for comment in self.recent_comments:
                body_preview = comment["body"][:100].replace("\n", " ")
                lines.append(f"    - [{comment['score']}] {body_preview}")
                lines.append(f"      {comment['permalink']}")
        return "\n".join(lines)

    def format_json(self) -> str:
        """Format as structured JSON."""
        data = {
            "username": self.username,
            "comment_karma": self.comment_karma,
            "link_karma": self.link_karma,
            "account_created_utc": self.account_created_utc,
            "account_age_days": self.account_age_days,
            "is_suspended": self.is_suspended,
            "recent_posts": self.recent_posts,
            "recent_comments": self.recent_comments,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)


# --- Item parsing ---


def _parse_mod_item(item: object) -> ModQueueItem | None:
    """Parse a PRAW submission or comment into a ModQueueItem. Returns None for malformed items."""
    try:
        is_submission = isinstance(item, praw.models.Submission)
        report_reasons = []
        for entry in getattr(item, "mod_reports", None) or []:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                report_reasons.append(str(entry[0]))
        for entry in getattr(item, "user_reports", None) or []:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                report_reasons.append(str(entry[0]))

        return ModQueueItem(
            id=item.id,
            fullname=item.fullname,
            title=item.title if is_submission else getattr(item, "link_title", ""),
            author=str(item.author) if item.author else "[deleted]",
            body=item.selftext if is_submission else getattr(item, "body", ""),
            score=item.score,
            num_reports=item.num_reports or 0,
            report_reasons=report_reasons,
            created_utc=item.created_utc,
            permalink=item.permalink,
            item_type="submission" if is_submission else "comment",
        )
    except Exception as e:
        item_id = getattr(item, "id", "<unknown>")
        print(f"WARNING: Failed to parse modqueue item {item_id}: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def _filter_since_minutes(items: list[ModQueueItem], since_minutes: int | None) -> list[ModQueueItem]:
    """Filter items to only those created within the last N minutes."""
    if since_minutes is None:
        return items
    cutoff = datetime.now(timezone.utc).timestamp() - (since_minutes * 60)
    return [item for item in items if item.created_utc >= cutoff]


# --- Mass-report detection ---


def detect_mass_report(num_reports: int, report_reasons: list[str]) -> bool:
    """Flag items with >10 reports across 3+ distinct categories."""
    if num_reports <= 10:
        return False
    unique_categories = len(set(report_reasons))
    return unique_categories >= 3


def wrap_untrusted(text: str) -> str:
    """Wrap user-generated content in untrusted-content tags.

    Strips existing tags to prevent boundary escape.
    """
    sanitized = text.replace("<untrusted-content>", "").replace("</untrusted-content>", "")
    return f"<untrusted-content>{sanitized}</untrusted-content>"


# --- Audit log ---


def write_audit_log(subreddit: str, entry: dict) -> None:
    """Append a classification/action entry to the audit log.

    Writes a JSONL entry to reddit-data/{subreddit}/audit.jsonl with a
    timestamp added automatically.

    Args:
        subreddit: The subreddit name (used to determine the data directory).
        entry: Dict of metadata to log (item_id, action, reason, etc.).
    """
    try:
        audit_dir = _DATA_DIR / subreddit
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / "audit.jsonl"

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "subreddit": subreddit,
            **entry,
        }
        with audit_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"WARNING: Failed to write audit log: {e}", file=sys.stderr)


# --- Config loading ---


def load_config(subreddit: str) -> dict:
    """Load per-subreddit config from reddit-data/{subreddit}/config.json.

    Returns the config dict merged over defaults. If the file does not exist
    or is malformed, returns the default config.

    Args:
        subreddit: The subreddit name.

    Returns:
        Config dict with all expected keys populated.
    """
    config = dict(_DEFAULT_CONFIG)
    config_path = _DATA_DIR / subreddit / "config.json"
    if config_path.exists():
        try:
            user_config = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(user_config, dict):
                config.update(user_config)
        except (json.JSONDecodeError, OSError) as e:
            print(f"WARNING: Could not load config.json for r/{subreddit}: {e}", file=sys.stderr)
    return config


def _check_action_limit(subreddit: str) -> tuple[int, int]:
    """Check today's action count against the configured max_auto_actions_per_run.

    Reads today's audit log entries and counts approve/remove/lock actions.

    Args:
        subreddit: The subreddit name.

    Returns:
        Tuple of (actions_today, max_allowed). max_allowed is 0 if no limit is configured.
    """
    config = load_config(subreddit)
    max_allowed = int(config.get("max_auto_actions_per_run", 25))

    audit_file = _DATA_DIR / subreddit / "audit.jsonl"
    if not audit_file.exists():
        return 0, max_allowed

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    actions_today = 0
    action_types = {"approve", "remove", "remove_spam", "lock"}

    try:
        for line in audit_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                print("WARNING: Malformed audit log line (skipping)", file=sys.stderr)
                continue
            timestamp = entry.get("timestamp", "")
            action = entry.get("action", "")
            if timestamp.startswith(today_str) and action in action_types:
                actions_today += 1
    except OSError as e:
        print(f"WARNING: Cannot read audit log for action limit check: {e}", file=sys.stderr)
        return max_allowed, max_allowed  # fail-safe: assume budget exhausted

    return actions_today, max_allowed


# --- Mod log analysis ---


def _fetch_mod_log(subreddit_obj: object, limit: int = 500) -> list[dict]:
    """Fetch mod log entries and return as a list of dicts.

    Args:
        subreddit_obj: A PRAW Subreddit instance.
        limit: Maximum number of log entries to fetch.

    Returns:
        List of dicts with action, mod, target_author, details, description, created_utc.
    """
    entries = []
    for entry in subreddit_obj.mod.log(limit=limit):
        entries.append(
            {
                "action": getattr(entry, "action", ""),
                "mod": str(getattr(entry, "mod", "")),
                "target_author": str(getattr(entry, "target_author", "") or ""),
                "target_fullname": getattr(entry, "target_fullname", ""),
                "details": getattr(entry, "details", ""),
                "description": getattr(entry, "description", ""),
                "created_utc": getattr(entry, "created_utc", 0),
            }
        )
    return entries


def _analyze_mod_log(entries: list[dict], subreddit_name: str) -> dict:
    """Analyze mod log entries into structured summary data.

    Args:
        entries: List of mod log entry dicts from _fetch_mod_log.
        subreddit_name: Subreddit name for header text.

    Returns:
        Dict with action_summary, removal_reasons, moderator_activity,
        repeat_offenders, and formatted summary_text.
    """
    action_counts: Counter[str] = Counter()
    removal_reasons: Counter[str] = Counter()
    moderator_activity: Counter[str] = Counter()
    removal_authors: Counter[str] = Counter()

    for entry in entries:
        action = entry["action"]
        mod = entry["mod"]
        action_counts[action] += 1
        moderator_activity[mod] += 1

        # Track removal reasons and authors
        if action in ("removecomment", "removelink", "spamcomment", "spamlink"):
            reason = entry["details"] or entry["description"] or "No reason given"
            removal_reasons[reason] += 1
            author = entry["target_author"]
            if author and author != "[deleted]":
                removal_authors[author] += 1

    # Repeat offenders: authors appearing 2+ times in removals
    repeat_offenders = {author: count for author, count in removal_authors.items() if count >= 2}

    # Build human-readable summary
    total_removals = sum(
        count
        for action, count in action_counts.items()
        if action in ("removecomment", "removelink", "spamcomment", "spamlink")
    )

    lines = [
        f"=== MODERATION PATTERNS FOR r/{subreddit_name} ===",
        "",
        f"Action Summary ({len(entries)} total log entries):",
    ]
    for action, count in action_counts.most_common():
        lines.append(f"  {action}: {count}")

    lines.append("")
    lines.append(f"Removal Reasons ({total_removals} total removals):")
    for reason, count in removal_reasons.most_common():
        pct = (count / total_removals * 100) if total_removals > 0 else 0
        lines.append(f"  {reason}: {count} ({pct:.0f}%)")

    # AutoMod vs human mod patterns
    automod_count = moderator_activity.get("AutoModerator", 0)
    anti_evil_count = moderator_activity.get("Anti-Evil Operations", 0)
    human_count = sum(
        count
        for mod, count in moderator_activity.items()
        if mod not in ("AutoModerator", "Anti-Evil Operations", "reddit")
    )
    lines.append("")
    lines.append("Moderator Activity:")
    for mod, count in moderator_activity.most_common():
        lines.append(f"  {mod}: {count}")
    lines.append("")
    lines.append(f"AutoMod actions: {automod_count} | Human mod actions: {human_count} | Anti-Evil: {anti_evil_count}")

    lines.append("")
    if repeat_offenders:
        lines.append(f"Repeat Offender Authors ({len(repeat_offenders)} authors with 2+ removals):")
        for author, count in sorted(repeat_offenders.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {author}: {count} removals")
    else:
        lines.append("Repeat Offender Authors: none found")

    return {
        "action_summary": dict(action_counts.most_common()),
        "removal_reasons": dict(removal_reasons.most_common()),
        "moderator_activity": dict(moderator_activity.most_common()),
        "repeat_offenders": repeat_offenders,
        "total_entries": len(entries),
        "total_removals": total_removals,
        "summary_text": "\n".join(lines),
    }


# --- Subcommand handlers ---


def _format_result_with_mass_report(result: ModQueueResult, use_json: bool) -> str:
    """Format a ModQueueResult, adding mass_report_flag to JSON output.

    Args:
        result: The modqueue result to format.
        use_json: Whether to output JSON (with mass_report_flag) or text.

    Returns:
        Formatted string output.
    """
    if not use_json:
        return result.format_text()
    data = {
        "subreddit": result.subreddit,
        "source": result.source,
        "count": len(result.items),
        "items": [],
    }
    for item in result.items:
        item_dict = item.to_dict()
        item_dict["mass_report_flag"] = detect_mass_report(item.num_reports, item.report_reasons)
        data["items"].append(item_dict)
    return json.dumps(data, indent=2, ensure_ascii=False)


def _cmd_queue(args: argparse.Namespace) -> int:
    """Fetch modqueue items."""
    reddit = _build_reddit()
    subreddit_name = _resolve_subreddit(args)
    subreddit = reddit.subreddit(subreddit_name)
    limit = min(args.limit, _MAX_LIMIT)

    # Show action limit status if requested
    if getattr(args, "check_limit", False):
        actions_today, max_allowed = _check_action_limit(subreddit_name)
        remaining = max(0, max_allowed - actions_today)
        print(f"Action limit: {actions_today}/{max_allowed} used today ({remaining} remaining)")
        print()

    items = [parsed for item in subreddit.mod.modqueue(limit=limit) if (parsed := _parse_mod_item(item)) is not None]
    items = _filter_since_minutes(items, getattr(args, "since_minutes", None))

    result = ModQueueResult(subreddit=subreddit_name, source="modqueue", items=items)

    use_json = args.json_output or getattr(args, "auto", False)
    print(_format_result_with_mass_report(result, use_json))
    return 0


def _cmd_reports(args: argparse.Namespace) -> int:
    """Fetch reported items."""
    reddit = _build_reddit()
    subreddit_name = _resolve_subreddit(args)
    subreddit = reddit.subreddit(subreddit_name)
    limit = min(args.limit, _MAX_LIMIT)

    items = [parsed for item in subreddit.mod.reports(limit=limit) if (parsed := _parse_mod_item(item)) is not None]
    items = _filter_since_minutes(items, getattr(args, "since_minutes", None))

    result = ModQueueResult(subreddit=subreddit_name, source="reports", items=items)

    use_json = args.json_output or getattr(args, "auto", False)
    print(_format_result_with_mass_report(result, use_json))
    return 0


def _cmd_unmoderated(args: argparse.Namespace) -> int:
    """Fetch unmoderated submissions."""
    reddit = _build_reddit()
    subreddit_name = _resolve_subreddit(args)
    subreddit = reddit.subreddit(subreddit_name)
    limit = min(args.limit, _MAX_LIMIT)

    items = [parsed for item in subreddit.mod.unmoderated(limit=limit) if (parsed := _parse_mod_item(item)) is not None]
    items = _filter_since_minutes(items, getattr(args, "since_minutes", None))

    result = ModQueueResult(subreddit=subreddit_name, source="unmoderated", items=items)

    use_json = args.json_output or getattr(args, "auto", False)
    print(_format_result_with_mass_report(result, use_json))
    return 0


def _resolve_item(reddit: object, fullname: str, *, allow_comments: bool = True) -> tuple[object | None, int]:
    """Validate fullname and resolve to a PRAW object.

    Returns:
        (item, 0) on success, (None, exit_code) on failure.
    """
    if not _FULLNAME_RE.match(fullname):
        allowed = "t1_ (comment) or t3_ (submission)" if allow_comments else "t3_ (submission)"
        print(f"ERROR: Invalid fullname '{fullname}'. Expected {allowed}.", file=sys.stderr)
        return None, 1

    if not allow_comments and fullname.startswith("t1_"):
        print(f"ERROR: Invalid fullname '{fullname}'. This command only works on submissions (t3_).", file=sys.stderr)
        return None, 1

    if fullname.startswith("t1_"):
        return reddit.comment(fullname[3:]), 0
    return reddit.submission(fullname[3:]), 0


def _cmd_approve(args: argparse.Namespace) -> int:
    """Approve an item by fullname ID."""
    reddit = _build_reddit()
    item, rc = _resolve_item(reddit, args.id)
    if item is None:
        return rc

    try:
        item.mod.approve()
    except NotFound:
        print(f"ERROR: Item {args.id} not found.", file=sys.stderr)
        return 1
    except Forbidden:
        print(f"ERROR: Permission denied to approve {args.id}.", file=sys.stderr)
        return 1

    # Write audit log if subreddit is known
    subreddit_name = getattr(args, "subreddit", None) or os.environ.get("REDDIT_SUBREDDIT")
    if subreddit_name:
        write_audit_log(subreddit_name, {"item_id": args.id, "action": "approve"})

    print(f"Approved {args.id}")
    return 0


def _cmd_remove(args: argparse.Namespace) -> int:
    """Remove an item by fullname ID."""
    reddit = _build_reddit()
    item, rc = _resolve_item(reddit, args.id)
    if item is None:
        return rc

    try:
        item.mod.remove(spam=args.spam, mod_note=args.reason)
    except NotFound:
        print(f"ERROR: Item {args.id} not found.", file=sys.stderr)
        return 1
    except Forbidden:
        print(f"ERROR: Permission denied to remove {args.id}.", file=sys.stderr)
        return 1

    # Write audit log if subreddit is known
    subreddit_name = getattr(args, "subreddit", None) or os.environ.get("REDDIT_SUBREDDIT")
    if subreddit_name:
        write_audit_log(
            subreddit_name,
            {
                "item_id": args.id,
                "action": "remove_spam" if args.spam else "remove",
                "reason": (args.reason[:500] if args.reason else ""),
            },
        )

    label = "Removed as spam" if args.spam else "Removed"
    print(f"{label} {args.id} — reason: {args.reason}")
    return 0


def _cmd_lock(args: argparse.Namespace) -> int:
    """Lock a thread by fullname ID."""
    reddit = _build_reddit()
    item, rc = _resolve_item(reddit, args.id, allow_comments=False)
    if item is None:
        return rc

    try:
        item.mod.lock()
    except NotFound:
        print(f"ERROR: Item {args.id} not found.", file=sys.stderr)
        return 1
    except Forbidden:
        print(f"ERROR: Permission denied to lock {args.id}.", file=sys.stderr)
        return 1

    # Write audit log if subreddit is known
    subreddit_name = getattr(args, "subreddit", None) or os.environ.get("REDDIT_SUBREDDIT")
    if subreddit_name:
        write_audit_log(subreddit_name, {"item_id": args.id, "action": "lock"})

    print(f"Locked {args.id}")
    return 0


def _cmd_setup(args: argparse.Namespace) -> int:
    """Bootstrap the reddit-data/{subreddit}/ directory with auto-generated context files.

    Creates rules.md, mod-log-summary.md, repeat-offenders.json, and templates
    for moderator-notes.md and config.json.
    """
    reddit = _build_reddit()
    subreddit_name = _resolve_subreddit(args)
    subreddit = reddit.subreddit(subreddit_name)
    data_dir = _DATA_DIR / subreddit_name
    data_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    updated: list[str] = []

    # 1. Fetch sidebar (description) + formal rules → write rules.md
    print(f"Fetching rules for r/{subreddit_name}...")
    rules_lines = [f"# Rules for r/{subreddit_name}", ""]

    # Sidebar rules (from subreddit description)
    sidebar = getattr(subreddit, "description", "") or ""
    if sidebar:
        rules_lines.append("## Sidebar / Description")
        rules_lines.append("")
        rules_lines.append(sidebar)
        rules_lines.append("")

    # Formal rules via API
    formal_rules = []
    try:
        for rule in subreddit.rules:
            formal_rules.append(
                {
                    "short_name": rule.short_name,
                    "kind": rule.kind,
                    "description": rule.description,
                    "violation_reason": rule.violation_reason,
                }
            )
    except Exception as e:
        print(f"  Warning: Could not fetch formal rules: {type(e).__name__}: {e}", file=sys.stderr)

    if formal_rules:
        rules_lines.append("## Formal Rules")
        rules_lines.append("")
        for i, rule in enumerate(formal_rules, 1):
            rules_lines.append(f"### {i}. {rule['short_name']} ({rule['kind']})")
            if rule["description"]:
                rules_lines.append(f"{rule['description']}")
            if rule["violation_reason"]:
                rules_lines.append(f"Violation reason: {rule['violation_reason']}")
            rules_lines.append("")
    elif not sidebar:
        rules_lines.append("No rules found (neither sidebar nor formal rules API).")
        rules_lines.append("")

    rules_path = data_dir / "rules.md"
    rules_path.write_text("\n".join(rules_lines), encoding="utf-8")
    updated.append("rules.md")

    # 2. Fetch mod log → analyze → write mod-log-summary.md + repeat-offenders.json
    limit = getattr(args, "limit", 500)
    print(f"Fetching mod log ({limit} entries) for r/{subreddit_name}...")
    entries = _fetch_mod_log(subreddit, limit=limit)
    analysis = _analyze_mod_log(entries, subreddit_name)

    summary_path = data_dir / "mod-log-summary.md"
    summary_path.write_text(analysis["summary_text"], encoding="utf-8")
    updated.append("mod-log-summary.md")

    offenders_path = data_dir / "repeat-offenders.json"
    offenders_path.write_text(
        json.dumps(analysis["repeat_offenders"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    updated.append("repeat-offenders.json")

    # 3. Create template moderator-notes.md if it doesn't exist
    notes_path = data_dir / "moderator-notes.md"
    if not notes_path.exists():
        notes_template_path = _TEMPLATE_DIR / "moderator-notes.md.template"
        if notes_template_path.exists():
            try:
                notes_content = notes_template_path.read_text(encoding="utf-8")
                notes_content = notes_content.replace("{subreddit}", subreddit_name)
                if not notes_content.strip():
                    notes_content = None  # empty template, fall back to stub
            except OSError as e:
                print(f"  Warning: Could not read template {notes_template_path}: {e}", file=sys.stderr)
                notes_content = None
        else:
            notes_content = None

        if notes_content is None:
            # Fallback to hardcoded stub
            notes_content = f"""# Moderator Notes: {subreddit_name}

## Common spam patterns
- [describe recurring spam patterns here]

## Community norms
- [describe what is considered acceptable behavior]

## Known false-report patterns
- [describe any recurring false-report patterns]
"""
        notes_path.write_text(notes_content, encoding="utf-8")
        created.append("moderator-notes.md")
    else:
        print("  moderator-notes.md already exists, skipping (won't overwrite)")

    # 4. Create default config.json if it doesn't exist
    config_path = data_dir / "config.json"
    if not config_path.exists():
        config_template_path = _TEMPLATE_DIR / "config.json.template"
        default_config = None
        if config_template_path.exists():
            try:
                template_text = config_template_path.read_text(encoding="utf-8")
                template_config = json.loads(template_text)
                if isinstance(template_config, dict):
                    # Strip _comment_* keys from the template
                    default_config = {k: v for k, v in template_config.items() if not k.startswith("_comment_")}
                    if not default_config:
                        default_config = None  # empty template, fall back to defaults
            except (json.JSONDecodeError, OSError) as e:
                print(f"  Warning: Could not read template {config_template_path}: {e}", file=sys.stderr)

        if default_config is None:
            # Fallback to hardcoded defaults
            default_config = {
                "confidence_auto_approve": 95,
                "confidence_auto_remove": 90,
                "trust_reporters": True,
                "community_type": "professional-technical",
                "max_auto_actions_per_run": 25,
            }
        config_path.write_text(json.dumps(default_config, indent=2, ensure_ascii=False), encoding="utf-8")
        created.append("config.json")
    else:
        print("  config.json already exists, skipping (won't overwrite)")

    # 5. Print summary
    print(f"\nSetup complete for r/{subreddit_name} in {data_dir}/")
    if created:
        print(f"  Created: {', '.join(created)}")
    if updated:
        print(f"  Updated: {', '.join(updated)}")
    print(f"  Mod log entries analyzed: {analysis['total_entries']}")
    print(f"  Total removals found: {analysis['total_removals']}")
    print(f"  Repeat offenders: {len(analysis['repeat_offenders'])}")
    return 0


def _cmd_subreddit_info(args: argparse.Namespace) -> int:
    """Fetch and display subreddit information."""
    reddit = _build_reddit()
    subreddit_name = _resolve_subreddit(args)
    subreddit = reddit.subreddit(subreddit_name)

    # Force-fetch attributes
    _ = subreddit.id

    # Gather info
    info: dict = {
        "name": subreddit.display_name,
        "subscribers": subreddit.subscribers,
        "description": getattr(subreddit, "description", "") or "",
        "public_description": getattr(subreddit, "public_description", "") or "",
        "submit_text": getattr(subreddit, "submit_text", "") or "",
        "over18": getattr(subreddit, "over18", False),
        "created_utc": getattr(subreddit, "created_utc", 0),
    }

    # Sidebar rules (from description)
    sidebar = info["description"]

    # Formal rules
    formal_rules = []
    try:
        for rule in subreddit.rules:
            formal_rules.append(
                {
                    "short_name": rule.short_name,
                    "kind": rule.kind,
                    "description": rule.description,
                    "violation_reason": rule.violation_reason,
                }
            )
    except Exception as e:
        print(f"  Warning: Could not fetch formal rules: {type(e).__name__}: {e}", file=sys.stderr)
    info["formal_rules"] = formal_rules

    if args.json_output:
        print(json.dumps(info, indent=2, ensure_ascii=False))
    else:
        print(f"r/{info['name']}")
        print("=" * (len(info["name"]) + 2))
        print(f"  Subscribers: {info['subscribers']:,}")
        print(f"  NSFW:        {info['over18']}")
        if info["created_utc"]:
            created = datetime.fromtimestamp(info["created_utc"], tz=timezone.utc)
            print(f"  Created:     {created.isoformat()}")
        if info["public_description"]:
            print(f"\nPublic description:\n  {info['public_description']}")
        if sidebar:
            # Truncate long sidebars for terminal display
            preview = sidebar[:1000]
            if len(sidebar) > 1000:
                preview += "\n  ... (truncated)"
            print(f"\nSidebar / Description:\n  {preview}")
        if formal_rules:
            print(f"\nFormal Rules ({len(formal_rules)}):")
            for i, rule in enumerate(formal_rules, 1):
                print(f"  {i}. {rule['short_name']} ({rule['kind']})")
                if rule["description"]:
                    print(f"     {rule['description'][:200]}")
        else:
            print("\nFormal Rules: none (check sidebar for rules)")
        if info["submit_text"]:
            preview = info["submit_text"][:500]
            if len(info["submit_text"]) > 500:
                preview += "\n  ... (truncated)"
            print(f"\nSubmission text:\n  {preview}")
    return 0


def _cmd_mod_log_summary(args: argparse.Namespace) -> int:
    """Fetch mod log and produce structured analysis."""
    reddit = _build_reddit()
    subreddit_name = _resolve_subreddit(args)
    subreddit = reddit.subreddit(subreddit_name)
    limit = min(args.limit, 1000)

    print(f"Fetching mod log ({limit} entries) for r/{subreddit_name}...", file=sys.stderr)
    entries = _fetch_mod_log(subreddit, limit=limit)
    analysis = _analyze_mod_log(entries, subreddit_name)

    if args.json_output:
        # Remove summary_text from JSON output (it's the human-readable version)
        json_data = {k: v for k, v in analysis.items() if k != "summary_text"}
        print(json.dumps(json_data, indent=2, ensure_ascii=False))
    else:
        print(analysis["summary_text"])

    # Optionally write to reddit-data/ directory
    if getattr(args, "save", False):
        data_dir = _DATA_DIR / subreddit_name
        data_dir.mkdir(parents=True, exist_ok=True)

        summary_path = data_dir / "mod-log-summary.md"
        summary_path.write_text(analysis["summary_text"], encoding="utf-8")

        offenders_path = data_dir / "repeat-offenders.json"
        offenders_path.write_text(
            json.dumps(analysis["repeat_offenders"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nSaved to {data_dir}/mod-log-summary.md and repeat-offenders.json", file=sys.stderr)

    return 0


def _cmd_user_history(args: argparse.Namespace) -> int:
    """Fetch a user's recent activity."""
    username = args.username
    if not _USERNAME_RE.match(username):
        print(f"ERROR: Invalid username '{username}'.", file=sys.stderr)
        return 1

    reddit = _build_reddit()
    limit = min(args.limit, _MAX_LIMIT)

    try:
        redditor = reddit.redditor(username)
        # Force-fetch to detect suspended/shadow-banned accounts
        _ = redditor.id
    except PrawcoreException as e:
        print(f"ERROR: Could not fetch user /u/{username} ({type(e).__name__}).", file=sys.stderr)
        return 1

    is_suspended = getattr(redditor, "is_suspended", False)

    recent_posts: list[dict] = []
    recent_comments: list[dict] = []

    if not is_suspended:
        for post in redditor.submissions.new(limit=limit):
            recent_posts.append(
                {
                    "id": post.id,
                    "fullname": post.fullname,
                    "title": post.title,
                    "subreddit": str(post.subreddit),
                    "score": post.score,
                    "created_utc": post.created_utc,
                    "permalink": f"https://reddit.com{post.permalink}",
                }
            )

        for comment in redditor.comments.new(limit=limit):
            recent_comments.append(
                {
                    "id": comment.id,
                    "fullname": comment.fullname,
                    "body": comment.body[:_BODY_TRUNCATE],
                    "subreddit": str(comment.subreddit),
                    "score": comment.score,
                    "created_utc": comment.created_utc,
                    "permalink": f"https://reddit.com{comment.permalink}",
                }
            )

    history = UserHistory(
        username=username,
        comment_karma=getattr(redditor, "comment_karma", None),
        link_karma=getattr(redditor, "link_karma", None),
        account_created_utc=getattr(redditor, "created_utc", None),
        is_suspended=is_suspended,
        recent_posts=recent_posts,
        recent_comments=recent_comments,
    )

    print(history.format_json() if args.json_output else history.format_text())
    return 0


def _cmd_rules(args: argparse.Namespace) -> int:
    """Fetch subreddit rules."""
    reddit = _build_reddit()
    subreddit_name = _resolve_subreddit(args)
    subreddit = reddit.subreddit(subreddit_name)

    rules_list = []
    for rule in subreddit.rules:
        rules_list.append(
            {
                "short_name": rule.short_name,
                "kind": rule.kind,
                "description": rule.description,
                "violation_reason": rule.violation_reason,
            }
        )

    if args.json_output:
        data = {"subreddit": subreddit_name, "count": len(rules_list), "rules": rules_list}
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        if not rules_list:
            print(f"No rules found for r/{subreddit_name}")
        else:
            print(f"r/{subreddit_name} — Rules ({len(rules_list)})")
            print("=" * 40)
            for i, rule in enumerate(rules_list, 1):
                print(f"\n{i}. {rule['short_name']} ({rule['kind']})")
                if rule["description"]:
                    print(f"   {rule['description']}")
                if rule["violation_reason"]:
                    print(f"   Violation reason: {rule['violation_reason']}")
    return 0


def _cmd_modmail(args: argparse.Namespace) -> int:
    """Fetch recent modmail conversations."""
    reddit = _build_reddit()
    subreddit_name = _resolve_subreddit(args)
    limit = min(args.limit, _MAX_LIMIT)
    state = args.state

    conversations = list(reddit.subreddit(subreddit_name).modmail.conversations(limit=limit, state=state))

    conv_list = []
    for conv in conversations:
        conv_list.append(
            {
                "id": conv.id,
                "subject": conv.subject,
                "authors": [author.name for author in conv.authors],
                "num_messages": conv.num_messages,
                "is_highlighted": conv.is_highlighted,
                "last_updated": conv.last_updated,
                "state": str(getattr(conv, "state", "unknown")),
            }
        )

    if args.json_output:
        data = {"subreddit": subreddit_name, "state": state, "count": len(conv_list), "conversations": conv_list}
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        if not conv_list:
            print(f"No modmail conversations for r/{subreddit_name} (state: {state})")
        else:
            print(f"r/{subreddit_name} — Modmail ({len(conv_list)} conversations, state: {state})")
            print("=" * 50)
            for conv in conv_list:
                print(f"\n  [{conv['id']}] {conv['subject']}")
                print(f"    Authors:  {', '.join(conv['authors'])}")
                print(f"    Messages: {conv['num_messages']}")
                print(f"    Updated:  {conv['last_updated']}")
                if conv["is_highlighted"]:
                    print("    ** HIGHLIGHTED **")
    return 0


# --- Scan helpers ---


def _detect_scan_flags(
    item: object,
    *,
    required_language: str | None,
    is_submission: bool,
) -> list[str]:
    """Detect basic heuristic flags on a scanned item.

    This provides lightweight, deterministic flagging. The real content analysis
    is done by the LLM classifier — these flags surface obvious patterns.

    Args:
        item: A PRAW Submission or Comment object.
        required_language: ISO 639-1 code (e.g. "en") or None.
        is_submission: Whether the item is a submission.

    Returns:
        List of flag strings describing detected issues.
    """
    flags: list[str] = []

    title = getattr(item, "title", "") or ""
    body = (getattr(item, "selftext", "") if is_submission else getattr(item, "body", "")) or ""
    text = f"{title} {body}"

    # Language heuristic: check for non-Latin script when required_language is set
    if required_language and required_language.lower() in ("en", "english"):
        # Basic heuristic: if a significant portion of alpha chars are non-ASCII, flag it
        alpha_chars = [c for c in text if c.isalpha()]
        if len(alpha_chars) > 20:  # need enough text to judge
            non_ascii_alpha = sum(1 for c in alpha_chars if ord(c) > 127)
            ratio = non_ascii_alpha / len(alpha_chars)
            if ratio > 0.3:
                flags.append(f"possible_non_english (required_language={required_language})")

    # Job ad patterns in title
    if is_submission and _JOB_AD_PATTERNS.search(title):
        flags.append("job_ad_pattern")

    # Training vendor patterns in body
    if _TRAINING_VENDOR_PATTERNS.search(body):
        flags.append("training_vendor_pattern")

    return flags


def _parse_scan_item(item: object, *, required_language: str | None) -> dict | None:
    """Parse a PRAW submission or comment into a scan result dict.

    Returns None for items that should be skipped (already moderated or malformed).

    Args:
        item: A PRAW Submission or Comment object.
        required_language: ISO 639-1 code or None.

    Returns:
        Dict with item details and scan_flags, or None if skipped.
    """
    try:
        # Skip already-moderated items
        if getattr(item, "approved_by", None) is not None:
            return None
        if getattr(item, "removed_by_category", None) is not None:
            return None

        is_submission = isinstance(item, praw.models.Submission)
        title = item.title if is_submission else getattr(item, "link_title", "")
        body = item.selftext if is_submission else getattr(item, "body", "")
        author = str(item.author) if item.author else "[deleted]"

        scan_flags = _detect_scan_flags(item, required_language=required_language, is_submission=is_submission)

        truncated_body = body[:_BODY_TRUNCATE] + "..." if len(body) > _BODY_TRUNCATE else body

        return {
            "id": item.id,
            "fullname": item.fullname,
            "item_type": "submission" if is_submission else "comment",
            "title": title,
            "author": author,
            "body": truncated_body,
            "score": item.score,
            "created_utc": item.created_utc,
            "created_iso": datetime.fromtimestamp(item.created_utc, tz=timezone.utc).isoformat(),
            "permalink": f"https://reddit.com{item.permalink}",
            "scan_flags": scan_flags,
        }
    except Exception as e:
        item_id = getattr(item, "id", "<unknown>")
        print(f"WARNING: Failed to parse scan item {item_id}: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def _format_age(created_utc: float) -> str:
    """Format item age as a human-readable string.

    Args:
        created_utc: Unix timestamp of creation.

    Returns:
        Human-readable age string (e.g. "2h ago", "3d ago").
    """
    delta_seconds = datetime.now(timezone.utc).timestamp() - created_utc
    if delta_seconds < 3600:
        return f"{int(delta_seconds / 60)}m ago"
    if delta_seconds < 86400:
        return f"{int(delta_seconds / 3600)}h ago"
    return f"{int(delta_seconds / 86400)}d ago"


def _cmd_scan(args: argparse.Namespace) -> int:
    """Scan recent posts and comments for potential issues.

    Fetches content from subreddit.new() and subreddit.comments(), filters by
    time window, skips already-moderated items, and flags potential issues using
    basic heuristics. The LLM classifier handles the real content analysis.
    """
    reddit = _build_reddit()
    subreddit_name = _resolve_subreddit(args)
    subreddit = reddit.subreddit(subreddit_name)

    # Load config for defaults
    config = load_config(subreddit_name)

    # Resolve limit and time window (CLI flags override config)
    limit = min(args.limit if args.limit is not None else int(config.get("scan_limit", 50)), _MAX_LIMIT)
    since_hours = args.since_hours if args.since_hours is not None else float(config.get("scan_recent_hours", 24))
    required_language = config.get("required_language")

    cutoff = datetime.now(timezone.utc).timestamp() - (since_hours * 3600)

    # Fetch recent posts
    scan_items: list[dict] = []
    post_count = 0
    for post in subreddit.new(limit=limit):
        if post.created_utc < cutoff:
            continue
        post_count += 1
        parsed = _parse_scan_item(post, required_language=required_language)
        if parsed is not None:
            scan_items.append(parsed)

    # Fetch recent comments
    comment_count = 0
    for comment in subreddit.comments(limit=limit):
        if comment.created_utc < cutoff:
            continue
        comment_count += 1
        parsed = _parse_scan_item(comment, required_language=required_language)
        if parsed is not None:
            scan_items.append(parsed)

    # Output
    if args.json_output:
        data = {
            "subreddit": subreddit_name,
            "source": "scan",
            "since_hours": since_hours,
            "posts_scanned": post_count,
            "comments_scanned": comment_count,
            "count": len(scan_items),
            "items": scan_items,
        }
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        flagged = [item for item in scan_items if item["scan_flags"]]
        header = (
            f"r/{subreddit_name} — scan (last {since_hours:.0f}h, "
            f"{post_count} posts + {comment_count} comments, "
            f"{len(scan_items)} unmoderated, {len(flagged)} flagged)"
        )
        print(header)
        print("=" * len(header))

        if not scan_items:
            print("\nNo unmoderated items found in the time window.")
            return 0

        for item in scan_items:
            print()
            item_type = item["item_type"].upper()
            age = _format_age(item["created_utc"])
            print(f"[{item_type}] {item['fullname']}  ({age})")
            if item["title"]:
                print(f"  Title:   {item['title']}")
            print(f"  Author:  /u/{item['author']}")
            print(f"  Score:   {item['score']}")
            print(f"  Link:    {item['permalink']}")
            if item["body"]:
                print(f"  Body:    {item['body']}")
            if item["scan_flags"]:
                print(f"  Flags:   {', '.join(item['scan_flags'])}")

    return 0


# --- CLI ---


def _add_common_listing_args(
    parser: argparse.ArgumentParser,
    *,
    with_auto: bool = False,
) -> None:
    """Add common arguments for listing subcommands."""
    parser.add_argument("--subreddit", "-s", default=None, help="Subreddit name (default: REDDIT_SUBREDDIT env var)")
    parser.add_argument(
        "--limit", "-l", type=int, default=_DEFAULT_LIMIT, help=f"Max items (default: {_DEFAULT_LIMIT})"
    )
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")
    if with_auto:
        parser.add_argument("--auto", action="store_true", help="Auto mode: JSON output for Claude /loop parsing")
        parser.add_argument(
            "--since-minutes",
            type=int,
            default=None,
            help="Only show items from the last N minutes",
        )


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Reddit moderation CLI using PRAW",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s setup --subreddit mysubreddit
  %(prog)s subreddit-info --subreddit mysubreddit --json
  %(prog)s mod-log-summary --subreddit mysubreddit --limit 500
  %(prog)s queue --subreddit mysubreddit --limit 10
  %(prog)s reports --subreddit mysubreddit --json
  %(prog)s approve --id t3_abc123
  %(prog)s remove --id t3_abc123 --reason "Rule 3 violation"
  %(prog)s lock --id t3_abc123
  %(prog)s user-history --username someuser
  %(prog)s rules --subreddit mysubreddit
  %(prog)s modmail --subreddit mysubreddit --state new
  %(prog)s queue --auto --since-minutes 15
  %(prog)s queue --check-limit --subreddit mysubreddit
  %(prog)s scan --subreddit mysubreddit --limit 50 --since-hours 24
  %(prog)s scan --subreddit mysubreddit --json
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- setup ---
    setup_parser = subparsers.add_parser("setup", help="Bootstrap reddit-data/{subreddit}/ directory")
    setup_parser.add_argument(
        "--subreddit", "-s", default=None, help="Subreddit name (default: REDDIT_SUBREDDIT env var)"
    )
    setup_parser.add_argument("--limit", "-l", type=int, default=500, help="Mod log entries to fetch (default: 500)")

    # --- subreddit-info ---
    subinfo_parser = subparsers.add_parser("subreddit-info", help="Fetch and display subreddit information")
    subinfo_parser.add_argument(
        "--subreddit", "-s", default=None, help="Subreddit name (default: REDDIT_SUBREDDIT env var)"
    )
    subinfo_parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")

    # --- mod-log-summary ---
    modlog_parser = subparsers.add_parser("mod-log-summary", help="Fetch mod log and produce structured analysis")
    modlog_parser.add_argument(
        "--subreddit", "-s", default=None, help="Subreddit name (default: REDDIT_SUBREDDIT env var)"
    )
    modlog_parser.add_argument("--limit", "-l", type=int, default=500, help="Mod log entries to fetch (default: 500)")
    modlog_parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")
    modlog_parser.add_argument("--save", action="store_true", help="Save results to reddit-data/{subreddit}/ directory")

    # --- queue ---
    queue_parser = subparsers.add_parser("queue", help="Fetch modqueue items")
    _add_common_listing_args(queue_parser, with_auto=True)
    queue_parser.add_argument(
        "--check-limit", action="store_true", dest="check_limit", help="Show action limit status in output header"
    )

    # --- reports ---
    reports_parser = subparsers.add_parser("reports", help="Fetch reported items")
    _add_common_listing_args(reports_parser, with_auto=True)

    # --- unmoderated ---
    unmod_parser = subparsers.add_parser("unmoderated", help="Fetch unmoderated submissions")
    _add_common_listing_args(unmod_parser, with_auto=True)

    # --- approve ---
    approve_parser = subparsers.add_parser("approve", help="Approve an item by fullname ID")
    approve_parser.add_argument("--id", required=True, help="Fullname ID (e.g., t3_abc123 or t1_xyz789)")

    # --- remove ---
    remove_parser = subparsers.add_parser("remove", help="Remove an item by fullname ID")
    remove_parser.add_argument("--id", required=True, help="Fullname ID (e.g., t3_abc123 or t1_xyz789)")
    remove_parser.add_argument("--reason", required=True, help="Removal reason / mod note")
    remove_parser.add_argument("--spam", action="store_true", help="Mark as spam")

    # --- lock ---
    lock_parser = subparsers.add_parser("lock", help="Lock a submission thread")
    lock_parser.add_argument("--id", required=True, help="Submission fullname ID (t3_...)")

    # --- user-history ---
    user_parser = subparsers.add_parser("user-history", help="Fetch user's recent activity")
    user_parser.add_argument("--username", "-u", required=True, help="Reddit username")
    user_parser.add_argument(
        "--limit", "-l", type=int, default=_DEFAULT_LIMIT, help=f"Max items per category (default: {_DEFAULT_LIMIT})"
    )
    user_parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")

    # --- rules ---
    rules_parser = subparsers.add_parser("rules", help="Fetch subreddit rules")
    rules_parser.add_argument(
        "--subreddit", "-s", default=None, help="Subreddit name (default: REDDIT_SUBREDDIT env var)"
    )
    rules_parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")

    # --- modmail ---
    modmail_parser = subparsers.add_parser("modmail", help="Fetch recent modmail conversations")
    modmail_parser.add_argument(
        "--subreddit", "-s", default=None, help="Subreddit name (default: REDDIT_SUBREDDIT env var)"
    )
    modmail_parser.add_argument(
        "--limit", "-l", type=int, default=_DEFAULT_LIMIT, help=f"Max conversations (default: {_DEFAULT_LIMIT})"
    )
    modmail_parser.add_argument(
        "--state",
        default="all",
        choices=["all", "new", "inprogress", "mod", "notifications", "archived", "appeals", "join_requests"],
        help="Modmail state filter (default: all)",
    )
    modmail_parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")

    # --- scan ---
    scan_parser = subparsers.add_parser("scan", help="Scan recent posts/comments for potential issues")
    scan_parser.add_argument(
        "--subreddit", "-s", default=None, help="Subreddit name (default: REDDIT_SUBREDDIT env var)"
    )
    scan_parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Max items to fetch per category (default: config scan_limit or 50)",
    )
    scan_parser.add_argument(
        "--since-hours",
        type=float,
        default=None,
        help="Only scan items from the last N hours (default: config scan_recent_hours or 24)",
    )
    scan_parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")

    args = parser.parse_args()

    handlers = {
        "setup": _cmd_setup,
        "subreddit-info": _cmd_subreddit_info,
        "mod-log-summary": _cmd_mod_log_summary,
        "queue": _cmd_queue,
        "reports": _cmd_reports,
        "unmoderated": _cmd_unmoderated,
        "approve": _cmd_approve,
        "remove": _cmd_remove,
        "lock": _cmd_lock,
        "user-history": _cmd_user_history,
        "rules": _cmd_rules,
        "modmail": _cmd_modmail,
        "scan": _cmd_scan,
    }

    handler = handlers.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except OAuthException as e:
        print(
            f"ERROR: Reddit API authentication failed ({type(e).__name__}). Check credential env vars.", file=sys.stderr
        )
        return 2  # config error
    except TooManyRequests:
        print("ERROR: Rate limited by Reddit. Wait a minute and retry.", file=sys.stderr)
        return 1
    except NotFound as e:
        print(f"ERROR: Resource not found: {type(e).__name__}", file=sys.stderr)
        return 1
    except ServerError:
        print("ERROR: Reddit server error. Try again later.", file=sys.stderr)
        return 1
    except Forbidden:
        print("ERROR: Permission denied. Check moderator status.", file=sys.stderr)
        return 1
    except PrawcoreException as e:
        print(f"ERROR: Reddit API error ({type(e).__name__}). Re-run to diagnose.", file=sys.stderr)
        return 1
    except ConnectionError:
        print("ERROR: Network error. Check your internet connectivity.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
