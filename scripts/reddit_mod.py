#!/usr/bin/env python3
"""
Reddit moderation CLI using PRAW.

Fetch modqueue items, reported content, unmoderated posts, and take mod actions.
Designed for use by Claude in /loop automation or standalone CLI usage.

Usage:
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

Environment variables (Fish shell):
    set -gx REDDIT_CLIENT_ID "your_client_id"
    set -gx REDDIT_CLIENT_SECRET "your_client_secret"
    set -gx REDDIT_USERNAME "your_bot_username"
    set -gx REDDIT_PASSWORD "your_bot_password"
    set -gx REDDIT_SUBREDDIT "your_default_subreddit"

Exit codes:
    0 = success
    1 = runtime error (network, invalid ID, API failure)
    2 = configuration error (missing credentials, missing praw)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

praw = None  # lazy import — see _ensure_praw()
PrawcoreException = Exception  # fallback base for type hints until praw is loaded


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


# --- Lazy import ---


def _ensure_praw() -> None:
    """Import praw on first use, exit with instructions if missing."""
    global praw, PrawcoreException
    if praw is not None:
        return
    try:
        import praw as _praw
        from prawcore.exceptions import PrawcoreException as _PrawcoreException

        praw = _praw
        PrawcoreException = _PrawcoreException
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
        print("Set them in Fish shell:", file=sys.stderr)
        for var in _REQUIRED_ENV_VARS:
            print(f'  set -gx {var} "your_{var.lower().removeprefix("reddit_")}"', file=sys.stderr)
        print('  set -gx REDDIT_SUBREDDIT "your_default_subreddit"  # optional', file=sys.stderr)
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
    comment_karma: int
    link_karma: int
    account_created_utc: float
    is_suspended: bool
    recent_posts: list[dict] = field(default_factory=list)
    recent_comments: list[dict] = field(default_factory=list)

    @property
    def account_age_days(self) -> int:
        """Account age in days."""
        created = datetime.fromtimestamp(self.account_created_utc, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - created).days

    def format_text(self) -> str:
        """Format as human-readable text."""
        lines = [
            f"User: /u/{self.username}",
            f"  Comment karma: {self.comment_karma}",
            f"  Link karma:    {self.link_karma}",
            f"  Account age:   {self.account_age_days} days",
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


def _parse_mod_item(item: object) -> ModQueueItem:
    """Parse a PRAW submission or comment into a ModQueueItem."""
    is_submission = hasattr(item, "title")
    report_reasons = []
    if item.mod_reports:
        report_reasons.extend(reason for reason, _mod in item.mod_reports)
    if item.user_reports:
        report_reasons.extend(reason for reason, _count in item.user_reports)

    return ModQueueItem(
        id=item.id,
        fullname=item.fullname,
        title=item.title if is_submission else getattr(item, "link_title", ""),
        author=str(item.author) if item.author else "[deleted]",
        body=item.selftext if is_submission else item.body,
        score=item.score,
        num_reports=item.num_reports or 0,
        report_reasons=report_reasons,
        created_utc=item.created_utc,
        permalink=item.permalink,
        item_type="submission" if is_submission else "comment",
    )


def _filter_since_minutes(items: list[ModQueueItem], since_minutes: int | None) -> list[ModQueueItem]:
    """Filter items to only those created within the last N minutes."""
    if since_minutes is None:
        return items
    cutoff = datetime.now(timezone.utc).timestamp() - (since_minutes * 60)
    return [item for item in items if item.created_utc >= cutoff]


# --- Subcommand handlers ---


def _cmd_queue(args: argparse.Namespace) -> int:
    """Fetch modqueue items."""
    reddit = _build_reddit()
    subreddit_name = _resolve_subreddit(args)
    subreddit = reddit.subreddit(subreddit_name)
    limit = min(args.limit, _MAX_LIMIT)

    items = [_parse_mod_item(item) for item in subreddit.mod.modqueue(limit=limit)]
    items = _filter_since_minutes(items, getattr(args, "since_minutes", None))

    result = ModQueueResult(subreddit=subreddit_name, source="modqueue", items=items)

    use_json = args.json_output or getattr(args, "auto", False)
    print(result.format_json() if use_json else result.format_text())
    return 0


def _cmd_reports(args: argparse.Namespace) -> int:
    """Fetch reported items."""
    reddit = _build_reddit()
    subreddit_name = _resolve_subreddit(args)
    subreddit = reddit.subreddit(subreddit_name)
    limit = min(args.limit, _MAX_LIMIT)

    items = [_parse_mod_item(item) for item in subreddit.mod.reports(limit=limit)]
    items = _filter_since_minutes(items, getattr(args, "since_minutes", None))

    result = ModQueueResult(subreddit=subreddit_name, source="reports", items=items)

    use_json = args.json_output or getattr(args, "auto", False)
    print(result.format_json() if use_json else result.format_text())
    return 0


def _cmd_unmoderated(args: argparse.Namespace) -> int:
    """Fetch unmoderated submissions."""
    reddit = _build_reddit()
    subreddit_name = _resolve_subreddit(args)
    subreddit = reddit.subreddit(subreddit_name)
    limit = min(args.limit, _MAX_LIMIT)

    items = [_parse_mod_item(item) for item in subreddit.mod.unmoderated(limit=limit)]
    items = _filter_since_minutes(items, getattr(args, "since_minutes", None))

    result = ModQueueResult(subreddit=subreddit_name, source="unmoderated", items=items)

    print(result.format_json() if args.json_output else result.format_text())
    return 0


def _cmd_approve(args: argparse.Namespace) -> int:
    """Approve an item by fullname ID."""
    reddit = _build_reddit()
    fullname = args.id

    if not (fullname.startswith("t1_") or fullname.startswith("t3_")):
        print(
            f"ERROR: Invalid fullname '{fullname}'. Expected t1_ (comment) or t3_ (submission).",
            file=sys.stderr,
        )
        return 1

    if fullname.startswith("t1_"):
        item = reddit.comment(fullname[3:])
    else:
        item = reddit.submission(fullname[3:])

    item.mod.approve()
    print(f"Approved {fullname}")
    return 0


def _cmd_remove(args: argparse.Namespace) -> int:
    """Remove an item by fullname ID."""
    reddit = _build_reddit()
    fullname = args.id

    if not (fullname.startswith("t1_") or fullname.startswith("t3_")):
        print(
            f"ERROR: Invalid fullname '{fullname}'. Expected t1_ (comment) or t3_ (submission).",
            file=sys.stderr,
        )
        return 1

    if fullname.startswith("t1_"):
        item = reddit.comment(fullname[3:])
    else:
        item = reddit.submission(fullname[3:])

    item.mod.remove(spam=args.spam, mod_note=args.reason)
    label = "Removed as spam" if args.spam else "Removed"
    print(f"{label} {fullname} — reason: {args.reason}")
    return 0


def _cmd_lock(args: argparse.Namespace) -> int:
    """Lock a thread by fullname ID."""
    reddit = _build_reddit()
    fullname = args.id

    if not fullname.startswith("t3_"):
        print(
            f"ERROR: Invalid fullname '{fullname}'. Lock only works on submissions (t3_).",
            file=sys.stderr,
        )
        return 1

    submission = reddit.submission(fullname[3:])
    submission.mod.lock()
    print(f"Locked {fullname}")
    return 0


def _cmd_user_history(args: argparse.Namespace) -> int:
    """Fetch a user's recent activity."""
    reddit = _build_reddit()
    username = args.username
    limit = min(args.limit, _MAX_LIMIT)

    try:
        redditor = reddit.redditor(username)
        # Force-fetch to detect suspended/shadow-banned accounts
        _ = redditor.id
    except Exception:
        print(f"ERROR: Could not fetch user /u/{username}. User may be suspended or deleted.", file=sys.stderr)
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
        comment_karma=getattr(redditor, "comment_karma", 0),
        link_karma=getattr(redditor, "link_karma", 0),
        account_created_utc=getattr(redditor, "created_utc", 0.0),
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
  %(prog)s queue --subreddit mysubreddit --limit 10
  %(prog)s reports --subreddit mysubreddit --json
  %(prog)s approve --id t3_abc123
  %(prog)s remove --id t3_abc123 --reason "Rule 3 violation"
  %(prog)s lock --id t3_abc123
  %(prog)s user-history --username someuser
  %(prog)s rules --subreddit mysubreddit
  %(prog)s modmail --subreddit mysubreddit --state new
  %(prog)s queue --auto --since-minutes 15
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- queue ---
    queue_parser = subparsers.add_parser("queue", help="Fetch modqueue items")
    _add_common_listing_args(queue_parser, with_auto=True)

    # --- reports ---
    reports_parser = subparsers.add_parser("reports", help="Fetch reported items")
    _add_common_listing_args(reports_parser, with_auto=True)

    # --- unmoderated ---
    unmod_parser = subparsers.add_parser("unmoderated", help="Fetch unmoderated submissions")
    _add_common_listing_args(unmod_parser)

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

    args = parser.parse_args()

    handlers = {
        "queue": _cmd_queue,
        "reports": _cmd_reports,
        "unmoderated": _cmd_unmoderated,
        "approve": _cmd_approve,
        "remove": _cmd_remove,
        "lock": _cmd_lock,
        "user-history": _cmd_user_history,
        "rules": _cmd_rules,
        "modmail": _cmd_modmail,
    }

    handler = handlers.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except PrawcoreException as e:
        print(f"ERROR: Reddit API authentication failed: {e}", file=sys.stderr)
        print("Check your REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD.", file=sys.stderr)
        return 1
    except ConnectionError as e:
        print(f"ERROR: Network error: {e}", file=sys.stderr)
        print("Check your internet connectivity.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
