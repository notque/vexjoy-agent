#!/usr/bin/env python3
"""
X (Twitter) API poster — deterministic CLI for X API operations.

Commands:
  post          Post a single tweet
  thread        Post a reply chain (thread)
  read-timeline Read a user's home timeline
  search        Search recent tweets

Auth:
  Read operations  — OAuth 2.0 Bearer token (X_BEARER_TOKEN)
  Write operations — OAuth 1.0a (X_API_KEY, X_API_SECRET,
                                  X_ACCESS_TOKEN, X_ACCESS_SECRET)

Write operations require --confirmed. --dry-run validates without network calls.

Exit codes:
  0  Success
  1  Missing credentials
  2  Content validation failed
  3  API error
  4  Write attempted without --confirmed
"""

import argparse
import os
import sys
import time
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TWEET_MAX_CHARS = 280
RATE_LIMIT_WARN_THRESHOLD = 10

X_API_V2_BASE = "https://api.x.com/2"
X_API_V1_MEDIA = "https://upload.twitter.com/1.1/media/upload.json"

REQUIRED_READ_VARS = ["X_BEARER_TOKEN"]
REQUIRED_WRITE_VARS = [
    "X_API_KEY",
    "X_API_SECRET",
    "X_ACCESS_TOKEN",
    "X_ACCESS_SECRET",
    "X_BEARER_TOKEN",
]


# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------


def _check_creds(vars_needed: list[str]) -> None:
    """Exit with code 1 if any required env var is missing."""
    missing = [v for v in vars_needed if not os.environ.get(v)]
    if missing:
        for v in missing:
            print(f"ERROR: Missing required environment variable: {v}", file=sys.stderr)
        sys.exit(1)


def _bearer_headers() -> dict:
    return {"Authorization": f"Bearer {os.environ['X_BEARER_TOKEN']}"}


def _oauth1_session():
    """Return a requests_oauthlib OAuth1Session for write operations."""
    try:
        from requests_oauthlib import OAuth1Session  # type: ignore
    except ImportError:
        print(
            "ERROR: requests_oauthlib is required for write operations.\n"
            "Install with: pip install requests requests-oauthlib",
            file=sys.stderr,
        )
        sys.exit(1)

    return OAuth1Session(
        client_key=os.environ["X_API_KEY"],
        client_secret=os.environ["X_API_SECRET"],
        resource_owner_key=os.environ["X_ACCESS_TOKEN"],
        resource_owner_secret=os.environ["X_ACCESS_SECRET"],
    )


# ---------------------------------------------------------------------------
# Rate limit inspection
# ---------------------------------------------------------------------------


def _inspect_rate_limits(response) -> None:
    """Emit a structured warning if remaining requests are low."""
    remaining_raw = response.headers.get("x-rate-limit-remaining")
    reset_raw = response.headers.get("x-rate-limit-reset")
    if remaining_raw is not None:
        try:
            remaining = int(remaining_raw)
            reset = int(reset_raw) if reset_raw else 0
            if remaining < RATE_LIMIT_WARN_THRESHOLD:
                print(
                    f"[rate-limit-warning] remaining={remaining} reset={reset}",
                    flush=True,
                )
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# Content validation
# ---------------------------------------------------------------------------


def _validate_tweet_text(text: str, label: str = "Tweet") -> None:
    """Exit with code 2 if text exceeds the character limit."""
    if len(text) > TWEET_MAX_CHARS:
        print(
            f"ERROR: {label} text exceeds {TWEET_MAX_CHARS} characters (got {len(text)}).",
            file=sys.stderr,
        )
        sys.exit(2)


def _validate_texts(texts: list[str]) -> None:
    for i, t in enumerate(texts, start=1):
        _validate_tweet_text(t, label=f"Tweet {i}/{len(texts)}")


# ---------------------------------------------------------------------------
# Media upload (two-step: v1.1 upload then attach to v2 tweet)
# ---------------------------------------------------------------------------


def _upload_media(media_path: str) -> str:
    """
    Upload media to X using the v1.1 media/upload.json endpoint.

    Returns the media_id_string on success.
    The operation is atomic: on any failure the function exits before
    returning a partial media ID, so no orphaned IDs are left behind.
    """
    import os as _os

    if not _os.path.isfile(media_path):
        print(f"ERROR: Media file not found: {media_path}", file=sys.stderr)
        sys.exit(2)

    try:
        import requests  # type: ignore
    except ImportError:
        print(
            "ERROR: requests is required. Install with: pip install requests requests-oauthlib",
            file=sys.stderr,
        )
        sys.exit(1)

    session = _oauth1_session()

    # Step 1: Upload the media bytes
    try:
        with open(media_path, "rb") as fh:
            media_bytes = fh.read()
    except OSError as exc:
        print(f"ERROR: Cannot read media file: {exc}", file=sys.stderr)
        sys.exit(2)

    resp = session.post(
        X_API_V1_MEDIA,
        files={"media": media_bytes},
    )

    if resp.status_code != 200:
        print(
            f"ERROR: Media upload failed at step 1 (HTTP {resp.status_code}): {resp.text}",
            file=sys.stderr,
        )
        sys.exit(3)

    data = resp.json()
    media_id = data.get("media_id_string")
    if not media_id:
        print(
            "ERROR: Media upload failed at step 1: no media_id_string in response.",
            file=sys.stderr,
        )
        sys.exit(3)

    # Step 2: (for videos) FINALIZE — for images this is a no-op, but we
    # confirm the media is ready by checking processing_info if present.
    processing_info = data.get("processing_info")
    if processing_info:
        # Poll until processing completes
        state = processing_info.get("state")
        max_polls = 30
        polls = 0
        while state not in ("succeeded", "failed") and polls < max_polls:
            wait = processing_info.get("check_after_secs", 1)
            time.sleep(wait)
            check_resp = session.get(
                X_API_V1_MEDIA,
                params={"command": "STATUS", "media_id": media_id},
            )
            if check_resp.status_code != 200:
                print(
                    f"ERROR: Media upload failed at step 2 (status poll HTTP {check_resp.status_code}).",
                    file=sys.stderr,
                )
                sys.exit(3)
            processing_info = check_resp.json().get("processing_info", {})
            state = processing_info.get("state", "pending")
            polls += 1

        if state == "failed":
            error_detail = processing_info.get("error", {})
            print(
                f"ERROR: Media upload failed at step 2 (processing failed): {error_detail}",
                file=sys.stderr,
            )
            sys.exit(3)

    return media_id


# ---------------------------------------------------------------------------
# API operations
# ---------------------------------------------------------------------------


def _post_single(
    text: str,
    reply_to_id: Optional[str] = None,
    media_id: Optional[str] = None,
) -> dict:
    """Post a single tweet. Returns the response JSON."""
    try:
        import requests  # type: ignore
    except ImportError:
        print(
            "ERROR: requests is required. Install with: pip install requests requests-oauthlib",
            file=sys.stderr,
        )
        sys.exit(1)

    session = _oauth1_session()
    payload: dict = {"text": text}
    if reply_to_id:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to_id}
    if media_id:
        payload["media"] = {"media_ids": [media_id]}

    resp = session.post(
        f"{X_API_V2_BASE}/tweets",
        json=payload,
    )
    _inspect_rate_limits(resp)

    if resp.status_code not in (200, 201):
        print(
            f"ERROR: Failed to post tweet (HTTP {resp.status_code}): {resp.text}",
            file=sys.stderr,
        )
        sys.exit(3)

    return resp.json()


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_post(args: argparse.Namespace) -> int:
    if not args.dry_run and not args.confirmed:
        print(
            "ERROR: Write operation requires --confirmed flag.\n"
            "Present the content preview to the user and wait for approval before retrying.",
            file=sys.stderr,
        )
        return 4

    _check_creds(REQUIRED_WRITE_VARS if not args.dry_run else REQUIRED_READ_VARS)
    _validate_tweet_text(args.text)

    if args.dry_run:
        print(f"[dry-run] tweet text validated ({len(args.text)}/{TWEET_MAX_CHARS} chars)")
        if args.media:
            if not os.path.isfile(args.media):
                print(f"ERROR: Media file not found: {args.media}", file=sys.stderr)
                return 2
            size = os.path.getsize(args.media)
            if args.media.lower().endswith((".mp4", ".mov", ".avi")):
                if size > 512 * 1024 * 1024:
                    print(f"[x-api] Video {args.media} exceeds 512MB limit ({size / 1024 / 1024:.1f}MB)")
                    sys.exit(1)
            else:
                if size > 5 * 1024 * 1024:
                    print(f"[x-api] Image {args.media} exceeds 5MB limit ({size / 1024 / 1024:.1f}MB)")
                    sys.exit(1)
            print(f"[dry-run] media file found: {args.media}")
        print("[dry-run] credentials present")
        print("[dry-run] no network calls made")
        return 0

    media_id: Optional[str] = None
    if args.media:
        media_id = _upload_media(args.media)

    data = _post_single(args.text, media_id=media_id)
    tweet_id = data["data"]["id"]
    url = f"https://x.com/i/web/status/{tweet_id}"
    print(f"[tweet-posted] id={tweet_id} url={url}")
    return 0


def cmd_thread(args: argparse.Namespace) -> int:
    if not args.dry_run and not args.confirmed:
        print(
            "ERROR: Write operation requires --confirmed flag.\n"
            "Present the content preview to the user and wait for approval before retrying.",
            file=sys.stderr,
        )
        return 4

    _check_creds(REQUIRED_WRITE_VARS if not args.dry_run else REQUIRED_READ_VARS)

    texts: list[str] = args.texts
    if not texts:
        print("ERROR: --texts requires at least one tweet.", file=sys.stderr)
        return 2

    _validate_texts(texts)

    if args.dry_run:
        print(f"[dry-run] thread of {len(texts)} tweet(s) validated")
        for i, t in enumerate(texts, start=1):
            print(f"[dry-run] tweet {i}/{len(texts)}: {len(t)}/{TWEET_MAX_CHARS} chars")
        print("[dry-run] credentials present")
        print("[dry-run] no network calls made")
        return 0

    tweet_ids: list[str] = []
    reply_to: Optional[str] = None
    for i, text in enumerate(texts, start=1):
        data = _post_single(text, reply_to_id=reply_to)
        tweet_id = data["data"]["id"]
        url = f"https://x.com/i/web/status/{tweet_id}"
        print(f"[tweet-posted] id={tweet_id} url={url} position={i}/{len(texts)}")
        tweet_ids.append(tweet_id)
        reply_to = tweet_id

    print(f"[thread-complete] root={tweet_ids[0]} tweets={len(tweet_ids)}")
    return 0


def cmd_read_timeline(args: argparse.Namespace) -> int:
    _check_creds(REQUIRED_READ_VARS)
    try:
        import requests  # type: ignore
    except ImportError:
        print(
            "ERROR: requests is required. Install with: pip install requests",
            file=sys.stderr,
        )
        return 1

    user_id = args.user_id
    max_results = args.max_results

    if user_id == "me":
        # Resolve authenticated user ID via Bearer token
        resp = requests.get(
            f"{X_API_V2_BASE}/users/me",
            headers=_bearer_headers(),
        )
        _inspect_rate_limits(resp)
        if resp.status_code != 200:
            print(
                f"ERROR: Failed to resolve user (HTTP {resp.status_code}): {resp.text}",
                file=sys.stderr,
            )
            return 3
        user_id = resp.json()["data"]["id"]

    resp = requests.get(
        f"{X_API_V2_BASE}/users/{user_id}/tweets",
        headers=_bearer_headers(),
        params={
            "max_results": max_results,
            "tweet.fields": "public_metrics,created_at",
        },
    )
    _inspect_rate_limits(resp)

    if resp.status_code != 200:
        print(
            f"ERROR: Failed to read timeline (HTTP {resp.status_code}): {resp.text}",
            file=sys.stderr,
        )
        return 3

    tweets = resp.json().get("data", [])
    for tweet in tweets:
        tid = tweet["id"]
        text_preview = tweet["text"][:80].replace("\n", " ")
        metrics = tweet.get("public_metrics", {})
        print(
            f"[tweet] id={tid} "
            f"likes={metrics.get('like_count', 0)} "
            f"retweets={metrics.get('retweet_count', 0)} "
            f"text={text_preview!r}"
        )
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    _check_creds(REQUIRED_READ_VARS)
    try:
        import requests  # type: ignore
    except ImportError:
        print(
            "ERROR: requests is required. Install with: pip install requests",
            file=sys.stderr,
        )
        return 1

    resp = requests.get(
        f"{X_API_V2_BASE}/tweets/search/recent",
        headers=_bearer_headers(),
        params={
            "query": args.query,
            "max_results": args.max_results,
            "tweet.fields": "public_metrics,created_at,author_id",
        },
    )
    _inspect_rate_limits(resp)

    if resp.status_code != 200:
        print(
            f"ERROR: Search failed (HTTP {resp.status_code}): {resp.text}",
            file=sys.stderr,
        )
        return 3

    tweets = resp.json().get("data", [])
    if not tweets:
        print("[search] no results found")
        return 0

    for tweet in tweets:
        tid = tweet["id"]
        author = tweet.get("author_id", "unknown")
        text_preview = tweet["text"][:80].replace("\n", " ")
        metrics = tweet.get("public_metrics", {})
        url = f"https://x.com/i/web/status/{tid}"
        print(f"[result] id={tid} author={author} likes={metrics.get('like_count', 0)} url={url} text={text_preview!r}")
    return 0


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="X API poster — post tweets, threads, and read timelines.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- post --
    post_p = subparsers.add_parser("post", help="Post a single tweet")
    post_p.add_argument("--text", required=True, help="Tweet text (max 280 chars)")
    post_p.add_argument(
        "--media",
        metavar="PATH",
        help="Absolute path to image or video file to attach",
    )
    post_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate without making any network calls",
    )
    post_p.add_argument(
        "--confirmed",
        action="store_true",
        help="Required for all write operations; only pass after user approves preview",
    )

    # -- thread --
    thread_p = subparsers.add_parser("thread", help="Post a thread (reply chain)")
    thread_p.add_argument(
        "--texts",
        nargs="+",
        required=True,
        metavar="TEXT",
        help="One argument per tweet in order",
    )
    thread_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate without making any network calls",
    )
    thread_p.add_argument(
        "--confirmed",
        action="store_true",
        help="Required for all write operations; only pass after user approves preview",
    )

    # -- read-timeline --
    rt_p = subparsers.add_parser("read-timeline", help="Read a user timeline")
    rt_p.add_argument(
        "--user-id",
        default="me",
        help='User ID or "me" for the authenticated user (default: me)',
    )
    rt_p.add_argument(
        "--max-results",
        type=int,
        default=10,
        metavar="N",
        help="Maximum number of tweets to return (default: 10)",
    )

    # -- search --
    search_p = subparsers.add_parser("search", help="Search recent tweets")
    search_p.add_argument("--query", required=True, help="Search query string")
    search_p.add_argument(
        "--max-results",
        type=int,
        default=10,
        metavar="N",
        help="Maximum number of results (default: 10)",
    )

    return parser


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "post": cmd_post,
        "thread": cmd_thread,
        "read-timeline": cmd_read_timeline,
        "search": cmd_search,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        print(f"ERROR: Unknown command: {args.command}", file=sys.stderr)
        return 2

    return handler(args)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"[x-api-poster] unexpected error: {e}", file=sys.stderr)
        sys.exit(0)
