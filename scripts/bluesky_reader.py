#!/usr/bin/env python3
"""
Read public Bluesky feeds via the AT Protocol public API.

No authentication required -- uses the public app view endpoint.

Usage:
    bluesky_reader.py feed --handle user.example.com --limit 20
    bluesky_reader.py search --handle user.example.com --query "search query here"
    bluesky_reader.py feed --handle user.example.com --json

Exit codes:
    0 = success
    1 = fatal error (network failure, invalid handle, no posts)
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

# --- Constants ---

_BASE_URL = "https://public.api.bsky.app/xrpc"
_FEED_ENDPOINT = f"{_BASE_URL}/app.bsky.feed.getAuthorFeed"
_DEFAULT_LIMIT = 30
_MAX_LIMIT = 100


# --- Data model ---


@dataclass
class BlueskyPost:
    """A single Bluesky post."""

    uri: str
    cid: str
    author_handle: str
    author_display_name: str
    text: str
    created_at: str
    like_count: int = 0
    repost_count: int = 0
    reply_count: int = 0
    is_repost: bool = False
    reposted_by: str = ""

    @property
    def relative_time(self) -> str:
        """Human-readable relative time from created_at."""
        try:
            # Handle both Z and +00:00 suffixes
            ts = self.created_at.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
            now = datetime.now(timezone.utc)
            delta = now - dt
            seconds = int(delta.total_seconds())

            if seconds < 60:
                return "just now"
            if seconds < 3600:
                m = seconds // 60
                return f"{m}m ago"
            if seconds < 86400:
                h = seconds // 3600
                return f"{h}h ago"
            d = seconds // 86400
            return f"{d}d ago"
        except (ValueError, TypeError):
            return self.created_at

    @property
    def short_url(self) -> str:
        """Construct a bsky.app URL from the AT URI."""
        # at://did:plc:xxx/app.bsky.feed.post/rkey -> https://bsky.app/profile/handle/post/rkey
        parts = self.uri.split("/")
        if len(parts) >= 5:
            rkey = parts[-1]
            return f"https://bsky.app/profile/{self.author_handle}/post/{rkey}"
        return self.uri


@dataclass
class FeedResult:
    """Result from fetching a Bluesky feed."""

    handle: str
    posts: list[BlueskyPost] = field(default_factory=list)
    cursor: str = ""

    def format_text(self) -> str:
        """Format as human-readable text output."""
        if not self.posts:
            return f"No posts found for @{self.handle}"

        lines: list[str] = []
        for i, post in enumerate(self.posts):
            if i > 0:
                lines.append("")
                lines.append("---")
                lines.append("")

            header = f"@{post.author_handle}"
            if post.author_display_name:
                header = f"{post.author_display_name} ({header})"
            if post.is_repost:
                header = f"[reposted by @{post.reposted_by}] {header}"
            header += f"  {post.relative_time}"
            lines.append(header)
            lines.append(post.text)
            lines.append(f"  {post.short_url}")

            stats = f"  likes: {post.like_count}  reposts: {post.repost_count}  replies: {post.reply_count}"
            lines.append(stats)

        return "\n".join(lines)

    def format_json(self) -> str:
        """Format as structured JSON."""
        data = {
            "handle": self.handle,
            "post_count": len(self.posts),
            "posts": [
                {
                    "uri": p.uri,
                    "cid": p.cid,
                    "author_handle": p.author_handle,
                    "author_display_name": p.author_display_name,
                    "text": p.text,
                    "created_at": p.created_at,
                    "url": p.short_url,
                    "like_count": p.like_count,
                    "repost_count": p.repost_count,
                    "reply_count": p.reply_count,
                    "is_repost": p.is_repost,
                    "reposted_by": p.reposted_by,
                }
                for p in self.posts
            ],
        }
        if self.cursor:
            data["cursor"] = self.cursor
        return json.dumps(data, indent=2, ensure_ascii=False)


# --- API interaction ---


def _build_feed_url(handle: str, limit: int, cursor: str = "") -> str:
    """Build the getAuthorFeed API URL.

    Args:
        handle: Bluesky handle (e.g., 'user.example.com').
        limit: Maximum number of posts to fetch.
        cursor: Pagination cursor for next page.

    Returns:
        Fully-formed API URL string.
    """
    url = f"{_FEED_ENDPOINT}?actor={urllib.request.quote(handle)}&limit={limit}"
    if cursor:
        url += f"&cursor={urllib.request.quote(cursor)}"
    return url


def _fetch_json(url: str) -> dict:
    """Fetch JSON from a URL using stdlib urllib.

    Args:
        url: URL to fetch.

    Returns:
        Parsed JSON as a dict.

    Raises:
        SystemExit: On network or API errors.
    """
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "bluesky-reader/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = ""
        with contextlib.suppress(Exception):
            body = e.read().decode("utf-8", errors="replace")
        print(f"ERROR: API returned HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: Network error: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except TimeoutError:
        print("ERROR: Request timed out after 15 seconds", file=sys.stderr)
        sys.exit(1)


def _parse_post(feed_item: dict) -> BlueskyPost:
    """Parse a single feed item from the API response into a BlueskyPost.

    Args:
        feed_item: A single item from the 'feed' array in the API response.

    Returns:
        Parsed BlueskyPost instance.
    """
    post_data = feed_item.get("post", {})
    record = post_data.get("record", {})
    author = post_data.get("author", {})

    # Detect reposts
    reason = feed_item.get("reason", {})
    is_repost = reason.get("$type", "") == "app.bsky.feed.defs#reasonRepost"
    reposted_by = ""
    if is_repost:
        repost_author = reason.get("by", {})
        reposted_by = repost_author.get("handle", "")

    return BlueskyPost(
        uri=post_data.get("uri", ""),
        cid=post_data.get("cid", ""),
        author_handle=author.get("handle", ""),
        author_display_name=author.get("displayName", ""),
        text=record.get("text", ""),
        created_at=record.get("createdAt", ""),
        like_count=post_data.get("likeCount", 0),
        repost_count=post_data.get("repostCount", 0),
        reply_count=post_data.get("replyCount", 0),
        is_repost=is_repost,
        reposted_by=reposted_by,
    )


def fetch_feed(handle: str, limit: int = _DEFAULT_LIMIT, cursor: str = "") -> FeedResult:
    """Fetch the public feed for a Bluesky handle.

    Args:
        handle: Bluesky handle (e.g., 'user.example.com').
        limit: Maximum number of posts to return.
        cursor: Pagination cursor for next page.

    Returns:
        FeedResult containing parsed posts.
    """
    clamped_limit = max(1, min(limit, _MAX_LIMIT))
    url = _build_feed_url(handle, clamped_limit, cursor)
    data = _fetch_json(url)

    posts = [_parse_post(item) for item in data.get("feed", [])]
    return FeedResult(
        handle=handle,
        posts=posts,
        cursor=data.get("cursor", ""),
    )


def search_feed(handle: str, query: str, limit: int = _MAX_LIMIT) -> FeedResult:
    """Fetch feed and filter posts by keyword query.

    Fetches up to `limit` posts, then filters locally for posts whose text
    contains all query words (case-insensitive).

    Args:
        handle: Bluesky handle to fetch.
        query: Space-separated keywords to match (all must be present).
        limit: How many posts to fetch before filtering.

    Returns:
        FeedResult containing only matching posts.
    """
    result = fetch_feed(handle, limit=limit)
    keywords = query.lower().split()

    matched = [post for post in result.posts if all(kw in post.text.lower() for kw in keywords)]

    return FeedResult(handle=handle, posts=matched)


# --- CLI ---


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Read public Bluesky feeds via the AT Protocol API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s feed --handle user.example.com --limit 20
  %(prog)s search --handle user.example.com --query "search query here"
  %(prog)s feed --handle user.example.com --json
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- feed subcommand ---
    feed_parser = subparsers.add_parser("feed", help="Fetch recent posts from a Bluesky profile")
    feed_parser.add_argument("--handle", required=True, help="Bluesky handle (e.g., user.example.com)")
    feed_parser.add_argument(
        "--limit",
        type=int,
        default=_DEFAULT_LIMIT,
        help=f"Max posts to fetch (default: {_DEFAULT_LIMIT}, max: {_MAX_LIMIT})",
    )
    feed_parser.add_argument("--json", action="store_true", dest="json_output", help="Output as structured JSON")
    feed_parser.add_argument("--cursor", default="", help="Pagination cursor for next page")

    # --- search subcommand ---
    search_parser = subparsers.add_parser("search", help="Search a profile's posts by keyword")
    search_parser.add_argument("--handle", required=True, help="Bluesky handle (e.g., user.example.com)")
    search_parser.add_argument("--query", required=True, help="Keywords to search for (all must match)")
    search_parser.add_argument(
        "--limit", type=int, default=_MAX_LIMIT, help=f"Posts to fetch before filtering (default: {_MAX_LIMIT})"
    )
    search_parser.add_argument("--json", action="store_true", dest="json_output", help="Output as structured JSON")

    args = parser.parse_args()

    if args.command == "feed":
        return _cmd_feed(args)
    elif args.command == "search":
        return _cmd_search(args)
    else:
        parser.print_help()
        return 1


def _cmd_feed(args: argparse.Namespace) -> int:
    """Handle the feed subcommand."""
    result = fetch_feed(args.handle, limit=args.limit, cursor=args.cursor)

    if not result.posts:
        print(f"No posts found for @{args.handle}", file=sys.stderr)
        return 1

    output = result.format_json() if args.json_output else result.format_text()
    print(output)

    if result.cursor:
        print(f"\n[next page: --cursor {result.cursor}]", file=sys.stderr)

    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    """Handle the search subcommand."""
    result = search_feed(args.handle, args.query, limit=args.limit)

    if not result.posts:
        print(f"No posts matching '{args.query}' for @{args.handle}", file=sys.stderr)
        return 1

    output = result.format_json() if args.json_output else result.format_text()
    print(output)

    print(f"\n[{len(result.posts)} post(s) matched]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
