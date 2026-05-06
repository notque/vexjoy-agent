#!/usr/bin/env python3
"""WordPress REST API post editor.

Edit, delete, and list existing WordPress posts via the REST API.

Usage:
    python3 skills/content/publish/scripts/wordpress-edit-post.py --id 12345 --get --human
    python3 skills/content/publish/scripts/wordpress-edit-post.py --id 12345 --title "New Title"
    python3 skills/content/publish/scripts/wordpress-edit-post.py --id 12345 --content-file updated.md
    python3 skills/content/publish/scripts/wordpress-edit-post.py --id 12345 --status publish
    python3 skills/content/publish/scripts/wordpress-edit-post.py --id 12345 --featured-image 67890
    python3 skills/content/publish/scripts/wordpress-edit-post.py --id 12345 --delete --human
    python3 skills/content/publish/scripts/wordpress-edit-post.py --list-drafts --human

Environment Variables (from ~/.env):
    WORDPRESS_SITE         WordPress site URL (e.g., https://your-blog.com)
    WORDPRESS_USER         WordPress username
    WORDPRESS_APP_PASSWORD Application password from WordPress admin

Exit codes:
    0 = success
    1 = error
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def load_env_file(env_path: Path | None = None) -> dict[str, str]:
    """Load key=value pairs from a .env file.

    Args:
        env_path: Path to .env file. Defaults to ~/.env.

    Returns:
        Dict of environment variable name to value.
    """
    if env_path is None:
        env_path = Path.home() / ".env"

    env_vars: dict[str, str] = {}
    if not env_path.exists():
        return env_vars

    with env_path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()

    return env_vars


def get_config() -> dict[str, str]:
    """Get WordPress configuration from environment variables and ~/.env.

    Returns:
        Dict with keys: site, user, password.
    """
    env_vars = load_env_file()
    return {
        "site": os.environ.get("WORDPRESS_SITE", env_vars.get("WORDPRESS_SITE", "")),
        "user": os.environ.get("WORDPRESS_USER", env_vars.get("WORDPRESS_USER", "")),
        "password": os.environ.get("WORDPRESS_APP_PASSWORD", env_vars.get("WORDPRESS_APP_PASSWORD", "")),
    }


def validate_config(config: dict[str, str]) -> list[str]:
    """Validate WordPress configuration, return list of error messages.

    Args:
        config: WordPress config dict.

    Returns:
        List of error strings (empty if valid).
    """
    errors: list[str] = []
    if not config["site"]:
        errors.append("WORDPRESS_SITE not set")
    if not config["user"]:
        errors.append("WORDPRESS_USER not set")
    if not config["password"]:
        errors.append("WORDPRESS_APP_PASSWORD not set")
    if config["site"] and not config["site"].startswith("https://"):
        errors.append("WORDPRESS_SITE must use HTTPS for Application Passwords")
    return errors


def _get_auth_headers(config: dict[str, str], content_type: str | None = "application/json") -> dict[str, str]:
    """Build HTTP headers with Basic Auth for WordPress REST API.

    Args:
        config: WordPress config dict.
        content_type: Content-Type header value. None to omit.

    Returns:
        Headers dict.
    """
    credentials = f"{config['user']}:{config['password']}"
    token = base64.b64encode(credentials.encode()).decode("utf-8")
    headers: dict[str, str] = {"Authorization": f"Basic {token}"}
    if content_type:
        headers["Content-Type"] = content_type
    return headers


# ---------------------------------------------------------------------------
# Markdown to HTML (for --content-file)
# ---------------------------------------------------------------------------


def strip_yaml_frontmatter(text: str) -> str:
    """Strip a leading YAML frontmatter block from markdown text.

    A frontmatter block opens with a line containing only ``---`` (after an
    optional UTF-8 BOM) and closes with the next line that is exactly ``---``.
    Anything between those fences is discarded; everything after the closing
    fence is returned, with leading blank lines stripped.

    No-op cases (input returned verbatim):
        - Text that does not start with a ``---`` fence line.
        - Text that opens with ``---`` but never closes (malformed) — a
          warning is logged to stderr so the caller notices, and the original
          text is returned so the rendered post still ships rather than crashing.

    Handles both LF and CRLF line endings.

    Args:
        text: Raw markdown content, possibly with frontmatter.

    Returns:
        Markdown body with frontmatter removed (or the original text if there
        is no frontmatter or it is malformed).
    """
    # Strip optional UTF-8 BOM only for the leading-fence check; preserve in
    # output if no frontmatter is present.
    probe = text.lstrip("﻿")
    # Normalize line endings for fence detection without mutating return value.
    # We split on \n and strip trailing \r so CRLF input behaves like LF.
    lines = probe.split("\n")
    if not lines or lines[0].rstrip("\r").strip() != "---":
        return text

    # Find the closing fence line (exactly --- after stripping CR/whitespace).
    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r").strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        print(
            "Warning: content file opens with '---' but no closing '---' fence was found; treating as no frontmatter.",
            file=sys.stderr,
        )
        return text

    body = "\n".join(lines[end_idx + 1 :])
    return body.lstrip("\n").lstrip("\r\n")


def markdown_to_html(markdown_content: str) -> str:
    """Convert markdown to HTML for content updates.

    Args:
        markdown_content: Raw markdown text.

    Returns:
        HTML string.
    """
    try:
        import markdown as md_lib

        return md_lib.markdown(markdown_content, extensions=["extra", "smarty", "sane_lists"])
    except ImportError:
        pass

    # Fallback: basic regex-based conversion
    html = markdown_content

    html = re.sub(r"^#### (.+)$", r"<h4>\1</h4>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

    html = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1" class="aligncenter size-full" />', html)
    html = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', html)

    html = re.sub(r"^---+$", r"<hr>", html, flags=re.MULTILINE)
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)

    result: list[str] = []
    for line in html.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("<"):
            result.append(f"<p>{stripped}</p>")
        else:
            result.append(line)

    return "\n".join(result)


# ---------------------------------------------------------------------------
# API Operations
# ---------------------------------------------------------------------------


def get_post(config: dict[str, str], post_id: int, context: str = "view") -> dict[str, Any]:
    """Get post details by ID.

    Args:
        config: WordPress config dict.
        post_id: Post ID to fetch.
        context: API context -- "view" for rendered HTML, "edit" for raw content.

    Returns:
        Result dict with post data on success.
    """
    api_url = f"{config['site'].rstrip('/')}/wp-json/wp/v2/posts/{post_id}"
    headers = _get_auth_headers(config, content_type=None)

    try:
        response = requests.get(api_url, headers=headers, params={"context": context}, timeout=30)

        if response.status_code == 200:
            return {"status": "success", "data": response.json()}

        error_data: dict[str, Any] = {}
        with contextlib.suppress(Exception):
            error_data = response.json()
        return {
            "status": "error",
            "http_status": response.status_code,
            "error": error_data.get("message", response.text[:500]),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def edit_post(
    config: dict[str, str],
    post_id: int,
    title: str | None = None,
    content: str | None = None,
    status: str | None = None,
    featured_image: int | None = None,
    categories: list[int] | None = None,
    tags: list[int] | None = None,
    excerpt: str | None = None,
) -> dict[str, Any]:
    """Edit an existing post via WordPress REST API.

    Args:
        config: WordPress config dict.
        post_id: Post ID to update.
        title: New title (None to skip).
        content: New HTML content (None to skip).
        status: New status (None to skip).
        featured_image: Featured image media ID (None to skip).
        categories: List of category IDs (None to skip).
        tags: List of tag IDs (None to skip).
        excerpt: New excerpt (None to skip).

    Returns:
        Result dict with updated post info on success.
    """
    api_url = f"{config['site'].rstrip('/')}/wp-json/wp/v2/posts/{post_id}"
    headers = _get_auth_headers(config)

    update_data: dict[str, Any] = {}
    if title is not None:
        update_data["title"] = title
    if content is not None:
        update_data["content"] = content
    if status is not None:
        update_data["status"] = status
    if featured_image is not None:
        update_data["featured_media"] = featured_image
    if categories is not None:
        update_data["categories"] = categories
    if tags is not None:
        update_data["tags"] = tags
    if excerpt is not None:
        update_data["excerpt"] = excerpt

    if not update_data:
        return {"status": "error", "error": "No fields provided to update"}

    try:
        response = requests.post(api_url, headers=headers, json=update_data, timeout=30)

        if response.status_code == 200:
            data = response.json()
            return {
                "status": "success",
                "post_id": data.get("id"),
                "post_url": data.get("link"),
                "edit_url": f"{config['site'].rstrip('/')}/wp-admin/post.php?post={data.get('id')}&action=edit",
                "post_status": data.get("status"),
                "updated_fields": list(update_data.keys()),
            }

        error_data: dict[str, Any] = {}
        with contextlib.suppress(Exception):
            error_data = response.json()
        return {
            "status": "error",
            "http_status": response.status_code,
            "error": error_data.get("message", response.text[:500]),
            "code": error_data.get("code", "unknown"),
        }

    except requests.exceptions.ConnectionError as e:
        return {"status": "error", "error": f"Connection failed: {e}"}
    except requests.exceptions.Timeout:
        return {"status": "error", "error": "Request timed out after 30 seconds"}
    except Exception as e:
        return {"status": "error", "error": f"Unexpected error: {e}"}


def delete_post(config: dict[str, str], post_id: int) -> dict[str, Any]:
    """Permanently delete a post via WordPress REST API (bypasses trash).

    Args:
        config: WordPress config dict.
        post_id: Post ID to delete.

    Returns:
        Result dict with deleted post info on success.
    """
    api_url = f"{config['site'].rstrip('/')}/wp-json/wp/v2/posts/{post_id}"
    headers = _get_auth_headers(config, content_type=None)

    try:
        response = requests.delete(api_url, headers=headers, params={"force": "true"}, timeout=30)

        if response.status_code == 200:
            data = response.json()
            return {
                "status": "success",
                "post_id": data.get("id"),
                "title": data.get("title", {}).get("rendered", ""),
                "deleted": True,
            }

        if response.status_code == 404:
            return {"status": "error", "http_status": 404, "error": f"Post {post_id} not found"}

        error_data: dict[str, Any] = {}
        with contextlib.suppress(Exception):
            error_data = response.json()
        return {
            "status": "error",
            "http_status": response.status_code,
            "error": error_data.get("message", response.text[:500]),
            "code": error_data.get("code", "unknown"),
        }

    except requests.exceptions.ConnectionError as e:
        return {"status": "error", "error": f"Connection failed: {e}"}
    except requests.exceptions.Timeout:
        return {"status": "error", "error": "Request timed out after 30 seconds"}
    except Exception as e:
        return {"status": "error", "error": f"Unexpected error: {e}"}


def list_drafts(config: dict[str, str]) -> dict[str, Any]:
    """List all draft posts via WordPress REST API.

    Args:
        config: WordPress config dict.

    Returns:
        Result dict with list of drafts on success.
    """
    api_url = f"{config['site'].rstrip('/')}/wp-json/wp/v2/posts"
    headers = _get_auth_headers(config, content_type=None)

    try:
        response = requests.get(api_url, headers=headers, params={"status": "draft", "per_page": 20}, timeout=30)

        if response.status_code == 200:
            posts = response.json()
            drafts = [
                {
                    "id": post.get("id"),
                    "title": post.get("title", {}).get("rendered", ""),
                    "date": post.get("date"),
                    "modified": post.get("modified"),
                    "link": post.get("link"),
                }
                for post in posts
            ]
            return {"status": "success", "count": len(drafts), "drafts": drafts}

        error_data: dict[str, Any] = {}
        with contextlib.suppress(Exception):
            error_data = response.json()
        return {
            "status": "error",
            "http_status": response.status_code,
            "error": error_data.get("message", response.text[:500]),
        }

    except requests.exceptions.ConnectionError as e:
        return {"status": "error", "error": f"Connection failed: {e}"}
    except requests.exceptions.Timeout:
        return {"status": "error", "error": "Request timed out after 30 seconds"}
    except Exception as e:
        return {"status": "error", "error": f"Unexpected error: {e}"}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    """CLI entry point for WordPress post editor."""
    parser = argparse.ArgumentParser(
        description="Edit, delete, and list WordPress posts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("--id", "-i", type=int, help="Post ID (required for get/edit/delete)")
    parser.add_argument("--title", "-t", help="New post title")
    parser.add_argument("--content", help="New post content (HTML)")
    parser.add_argument("--content-file", help="Path to markdown file for new content")
    parser.add_argument("--status", "-s", choices=["draft", "publish", "pending", "private"], help="New post status")
    parser.add_argument("--featured-image", type=int, help="Featured image media ID")
    parser.add_argument("--category", action="append", type=int, help="Category ID (repeatable, replaces existing)")
    parser.add_argument("--tag", action="append", type=int, help="Tag ID (repeatable, replaces existing)")
    parser.add_argument("--excerpt", help="Post excerpt")
    parser.add_argument("--get", action="store_true", help="Fetch and display the post (no edits)")
    parser.add_argument("--raw", action="store_true", help="Get raw content instead of rendered HTML (with --get)")
    parser.add_argument("--delete", action="store_true", help="Permanently delete the post (bypass trash)")
    parser.add_argument("--list-drafts", action="store_true", help="List all draft posts")
    parser.add_argument("--human", action="store_true", help="Output human-readable format instead of JSON")

    args = parser.parse_args()

    # Validate config
    config = get_config()
    errors = validate_config(config)
    if errors:
        print(json.dumps({"status": "error", "error": "Configuration errors", "details": errors}, indent=2))
        return 1

    # --list-drafts does not require --id
    if args.list_drafts:
        result = list_drafts(config)
        if args.human and result["status"] == "success":
            drafts = result["drafts"]
            print(f"Found {result['count']} draft(s):")
            for draft in drafts:
                print(f"  #{draft['id']}  {draft['title']}")
                print(f"         modified: {draft['modified']}")
        else:
            print(json.dumps(result, indent=2))
        return 0 if result["status"] == "success" else 1

    # All other operations require --id
    if args.id is None:
        print(json.dumps({"status": "error", "error": "--id is required for get/edit/delete operations"}, indent=2))
        return 1

    # --delete
    if args.delete:
        result = delete_post(config, args.id)
        if args.human and result["status"] == "success":
            print(f"Deleted post #{result['post_id']}: {result['title']}")
        else:
            print(json.dumps(result, indent=2))
        return 0 if result["status"] == "success" else 1

    # --get
    if args.get:
        context = "edit" if args.raw else "view"
        result = get_post(config, args.id, context=context)
        if args.human and result["status"] == "success":
            data = result["data"]
            title_data = data.get("title", {})
            title = title_data.get("raw") if args.raw else title_data.get("rendered", "N/A")
            print(f"Post #{args.id}")
            print(f"  Title:          {title}")
            print(f"  Status:         {data.get('status')}")
            print(f"  URL:            {data.get('link')}")
            print(f"  Featured Image: {data.get('featured_media', 'None')}")
            if args.raw:
                raw_content = data.get("content", {}).get("raw", "")
                print(f"\n--- Raw Content ---\n{raw_content}")
        else:
            print(json.dumps(result, indent=2))
        return 0 if result["status"] == "success" else 1

    # Edit post
    content = args.content
    if args.content_file:
        file_path = Path(args.content_file)
        if not file_path.exists():
            print(json.dumps({"status": "error", "error": f"Content file not found: {args.content_file}"}, indent=2))
            return 1
        content = markdown_to_html(strip_yaml_frontmatter(file_path.read_text()))

    result = edit_post(
        config=config,
        post_id=args.id,
        title=args.title,
        content=content,
        status=args.status,
        featured_image=args.featured_image,
        categories=args.category,
        tags=args.tag,
        excerpt=args.excerpt,
    )

    if args.human and result["status"] == "success":
        print("Post updated successfully!")
        print(f"  ID:      {result['post_id']}")
        print(f"  Status:  {result['post_status']}")
        print(f"  Updated: {', '.join(result['updated_fields'])}")
        print(f"  View:    {result['post_url']}")
        print(f"  Edit:    {result['edit_url']}")
    else:
        print(json.dumps(result, indent=2))

    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
