#!/usr/bin/env python3
"""WordPress.com blog scraper — fetches all posts via the public REST API and saves as markdown.

Scrapes posts from any WordPress.com-hosted blog using the WordPress.com public API
(public-api.wordpress.com/rest/v1.1/). Converts HTML content to markdown and saves
each post as a separate .md file with YAML frontmatter.

Usage:
    python3 skills/content/publish/scripts/wordpress-scraper.py \\
        --source https://example-blog.wordpress.com --output /tmp/articles/ --human
    python3 skills/content/publish/scripts/wordpress-scraper.py \\
        --source https://example-blog.wordpress.com --output /tmp/articles/ --limit 5 --human
    python3 skills/content/publish/scripts/wordpress-scraper.py \\
        --source https://example-blog.wordpress.com --output /tmp/articles/ \\
        --download-images --human

Exit codes:
    0 = success
    1 = error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
from html import unescape
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

_last_request_time: float = 0.0
RATE_LIMIT_SECONDS: float = 1.0


def _rate_limited_get(url: str, params: dict[str, Any] | None = None, timeout: int = 30) -> requests.Response:
    """Send a GET request with rate limiting (1 request per second).

    Args:
        url: Request URL.
        params: Query parameters.
        timeout: Request timeout in seconds.

    Returns:
        Response object.
    """
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < RATE_LIMIT_SECONDS:
        time.sleep(RATE_LIMIT_SECONDS - elapsed)
    _last_request_time = time.monotonic()
    return requests.get(url, params=params, timeout=timeout)


# ---------------------------------------------------------------------------
# WordPress.com Public API fetching
# ---------------------------------------------------------------------------

WPCOM_API_BASE = "https://public-api.wordpress.com/rest/v1.1/sites"


def _site_id(source_url: str) -> str:
    """Extract the site identifier from a WordPress.com blog URL.

    Args:
        source_url: Blog URL (e.g., https://example-blog.wordpress.com).

    Returns:
        Site hostname for API calls (e.g., example-blog.wordpress.com).
    """
    parsed = urllib.parse.urlparse(source_url)
    return parsed.netloc or parsed.path.strip("/")


def fetch_all_posts(
    source_url: str,
    post_type: str = "post",
    limit: int | None = None,
    human: bool = False,
) -> list[dict[str, Any]]:
    """Fetch all posts or pages from the WordPress.com public API.

    Uses offset-based pagination with the /posts/ endpoint.

    Args:
        source_url: Blog URL (e.g., https://example-blog.wordpress.com).
        post_type: Content type — 'post' or 'page'.
        limit: Maximum number of items to fetch. None for all.
        human: If True, print progress to stderr.

    Returns:
        List of post/page dicts from the API.
    """
    site = _site_id(source_url)
    api_url = f"{WPCOM_API_BASE}/{site}/posts/"
    all_items: list[dict[str, Any]] = []
    offset = 0
    per_page = 100

    while True:
        page_num = (offset // per_page) + 1
        if human:
            print(f"  Fetching {post_type}s page {page_num}...", file=sys.stderr)

        params: dict[str, Any] = {
            "number": per_page,
            "offset": offset,
            "type": post_type,
            "status": "publish",
        }

        try:
            response = _rate_limited_get(api_url, params=params)
        except requests.exceptions.RequestException as e:
            print(f"Error: request failed for {post_type}s at offset {offset}: {e}", file=sys.stderr)
            break

        if response.status_code != 200:
            print(f"Error: HTTP {response.status_code} fetching {post_type}s at offset {offset}", file=sys.stderr)
            break

        data = response.json()
        posts = data.get("posts", [])
        total_found = data.get("found", 0)

        if not posts:
            break

        all_items.extend(posts)

        if limit is not None and len(all_items) >= limit:
            all_items = all_items[:limit]
            break

        offset += len(posts)
        if offset >= total_found:
            break

    return all_items


# ---------------------------------------------------------------------------
# HTML to Markdown conversion
# ---------------------------------------------------------------------------


def _strip_html_tags(text: str) -> str:
    """Remove all HTML tags from text.

    Args:
        text: HTML string.

    Returns:
        Plain text with tags removed.
    """
    return re.sub(r"<[^>]+>", "", text)


def html_to_markdown(html: str) -> str:
    """Convert HTML content to markdown.

    Handles common WordPress HTML elements: headings, paragraphs, links,
    images, bold, italic, lists, blockquotes, and iframes.

    Args:
        html: HTML content string.

    Returns:
        Markdown-formatted string.
    """
    if not html:
        return ""

    text = html

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Handle <br> tags before block processing
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    # --- Block-level elements ---

    # Headings (h1-h6)
    for level in range(6, 0, -1):
        prefix = "#" * level
        text = re.sub(
            rf"<h{level}[^>]*>(.*?)</h{level}>",
            lambda m, p=prefix: f"\n\n{p} {_strip_html_tags(m.group(1)).strip()}\n\n",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

    # Blockquotes
    text = re.sub(
        r"<blockquote[^>]*>(.*?)</blockquote>",
        lambda m: "\n\n> " + _strip_html_tags(m.group(1)).strip().replace("\n", "\n> ") + "\n\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Ordered list items
    text = re.sub(
        r"<ol[^>]*>(.*?)</ol>",
        lambda m: _convert_ordered_list(m.group(1)),
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Unordered list items
    text = re.sub(
        r"<ul[^>]*>(.*?)</ul>",
        lambda m: _convert_unordered_list(m.group(1)),
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # --- Inline elements (before stripping remaining tags) ---

    # Images — extract src and alt (handle both orderings of attributes)
    text = re.sub(
        r'<img[^>]*\ssrc=["\']([^"\']+)["\'][^>]*\salt=["\']([^"\']*)["\'][^>]*/?>',
        r"![\2](\1)",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r'<img[^>]*\salt=["\']([^"\']*)["\'][^>]*\ssrc=["\']([^"\']+)["\'][^>]*/?>',
        r"![\1](\2)",
        text,
        flags=re.IGNORECASE,
    )
    # Images with src only (no alt)
    text = re.sub(
        r'<img[^>]*\ssrc=["\']([^"\']+)["\'][^>]*/?>',
        r"![](\1)",
        text,
        flags=re.IGNORECASE,
    )

    # Links
    text = re.sub(
        r'<a[^>]*\shref=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        lambda m: f"[{_strip_html_tags(m.group(2)).strip()}]({m.group(1)})",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Bold
    text = re.sub(r"<(?:strong|b)>(.*?)</(?:strong|b)>", r"**\1**", text, flags=re.IGNORECASE | re.DOTALL)

    # Italic
    text = re.sub(r"<(?:em|i)>(.*?)</(?:em|i)>", r"*\1*", text, flags=re.IGNORECASE | re.DOTALL)

    # Iframes (YouTube embeds etc.) — preserve URL
    text = re.sub(
        r'<iframe[^>]*\ssrc=["\']([^"\']+)["\'][^>]*>.*?</iframe>',
        r"\n\n\1\n\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Paragraphs — convert to double newlines
    text = re.sub(r"<p[^>]*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)

    # Divs and figures — treat as block separators
    block_tags = r"</?(?:div|figure|figcaption|section|article|aside|header|footer|nav)[^>]*>"
    text = re.sub(block_tags, "\n\n", text, flags=re.IGNORECASE)

    # Horizontal rules
    text = re.sub(r"<hr[^>]*/?>", "\n\n---\n\n", text, flags=re.IGNORECASE)

    # WordPress caption shortcodes
    text = re.sub(r"\[caption[^\]]*\](.*?)\[/caption\]", r"\1", text, flags=re.IGNORECASE | re.DOTALL)

    # Strip any remaining HTML tags
    text = _strip_html_tags(text)

    # Decode HTML entities
    text = unescape(text)

    # Clean up whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = text.strip()

    return text


def _convert_unordered_list(list_html: str) -> str:
    """Convert <li> items inside a <ul> to markdown unordered list.

    Args:
        list_html: Inner HTML of the <ul> element.

    Returns:
        Markdown list string.
    """
    items = re.findall(r"<li[^>]*>(.*?)</li>", list_html, flags=re.IGNORECASE | re.DOTALL)
    md_items = [f"- {_strip_html_tags(item).strip()}" for item in items]
    return "\n\n" + "\n".join(md_items) + "\n\n"


def _convert_ordered_list(list_html: str) -> str:
    """Convert <li> items inside an <ol> to markdown ordered list.

    Args:
        list_html: Inner HTML of the <ol> element.

    Returns:
        Markdown list string.
    """
    items = re.findall(r"<li[^>]*>(.*?)</li>", list_html, flags=re.IGNORECASE | re.DOTALL)
    md_items = [f"{i}. {_strip_html_tags(item).strip()}" for i, item in enumerate(items, 1)]
    return "\n\n" + "\n".join(md_items) + "\n\n"


# ---------------------------------------------------------------------------
# Image downloading
# ---------------------------------------------------------------------------


def extract_image_urls(html: str) -> list[str]:
    """Extract all image URLs from HTML content.

    Args:
        html: HTML content string.

    Returns:
        List of unique image URLs found in <img> tags.
    """
    urls = re.findall(r'<img[^>]*\ssrc=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def download_image(url: str, output_dir: Path, human: bool = False) -> str | None:
    """Download an image and return the local filename.

    Args:
        url: Image URL to download.
        output_dir: Directory to save images into.
        human: If True, print progress to stderr.

    Returns:
        Local filename (not full path) on success, None on failure.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Derive filename from URL
    parsed = urllib.parse.urlparse(url)
    filename = Path(parsed.path).name
    if not filename:
        filename = "image.jpg"

    # Ensure unique filename
    local_path = output_dir / filename
    counter = 1
    while local_path.exists():
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        local_path = output_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    try:
        response = _rate_limited_get(url, timeout=30)
        if response.status_code == 200:
            local_path.write_bytes(response.content)
            if human:
                print(f"    Downloaded: {local_path.name}", file=sys.stderr)
            return local_path.name
        else:
            if human:
                print(f"    Failed to download {url}: HTTP {response.status_code}", file=sys.stderr)
            return None
    except requests.exceptions.RequestException as e:
        if human:
            print(f"    Failed to download {url}: {e}", file=sys.stderr)
        return None


def download_and_replace_images(
    html: str,
    markdown: str,
    output_dir: Path,
    human: bool = False,
) -> str:
    """Download all images from HTML content and replace URLs in markdown.

    Args:
        html: Original HTML content (for extracting image URLs).
        markdown: Converted markdown content.
        output_dir: Base output directory (images saved to output_dir/images/).
        human: If True, print progress to stderr.

    Returns:
        Markdown with image URLs replaced with local paths.
    """
    image_urls = extract_image_urls(html)
    if not image_urls:
        return markdown

    images_dir = output_dir / "images"
    updated_markdown = markdown

    for url in image_urls:
        local_name = download_image(url, images_dir, human=human)
        if local_name:
            updated_markdown = updated_markdown.replace(url, f"images/{local_name}")

    return updated_markdown


# ---------------------------------------------------------------------------
# Post processing and file output
# ---------------------------------------------------------------------------


def get_featured_image_url(post: dict[str, Any]) -> str | None:
    """Extract featured image URL from a WordPress.com API post.

    Args:
        post: Post dict from the WordPress.com public API.

    Returns:
        Featured image URL or None.
    """
    # WordPress.com API puts featured image URL directly on the post
    featured = post.get("featured_image")
    if featured:
        return featured

    # Fallback: post_thumbnail object
    thumbnail = post.get("post_thumbnail")
    if thumbnail and isinstance(thumbnail, dict):
        return thumbnail.get("URL")

    return None


def get_author_name(post: dict[str, Any]) -> str:
    """Extract author display name from a WordPress.com API post.

    Args:
        post: Post dict from the WordPress.com public API.

    Returns:
        Author display name, or "Unknown" if not available.
    """
    author = post.get("author", {})
    if isinstance(author, dict):
        # Prefer first_name + last_name, fall back to name field
        first = author.get("first_name", "")
        last = author.get("last_name", "")
        if first or last:
            return f"{first} {last}".strip()
        return author.get("name", "Unknown")
    return "Unknown"


def extract_categories(post: dict[str, Any]) -> list[str]:
    """Extract category names from a WordPress.com API post.

    WordPress.com API returns categories as an object keyed by slug.

    Args:
        post: Post dict from the WordPress.com public API.

    Returns:
        List of category name strings.
    """
    cats = post.get("categories", {})
    if isinstance(cats, dict):
        return [unescape(cat.get("name", slug)) for slug, cat in cats.items()]
    return []


def extract_tags(post: dict[str, Any]) -> list[str]:
    """Extract tag names from a WordPress.com API post.

    WordPress.com API returns tags as an object keyed by slug.

    Args:
        post: Post dict from the WordPress.com public API.

    Returns:
        List of tag name strings.
    """
    tags = post.get("tags", {})
    if isinstance(tags, dict):
        return [unescape(tag.get("name", slug)) for slug, tag in tags.items()]
    return []


def build_frontmatter(post: dict[str, Any], source_url: str) -> str:
    """Build YAML frontmatter string for a post.

    Args:
        post: Post dict from the WordPress.com public API.
        source_url: Blog base URL for reference.

    Returns:
        YAML frontmatter string including opening/closing --- delimiters.
    """
    title = unescape(post.get("title", "Untitled"))
    # Escape quotes in title for YAML safety
    title = title.replace('"', '\\"')

    date = post.get("date", "")
    slug = post.get("slug", "")
    author = get_author_name(post)
    featured_image = get_featured_image_url(post)

    categories = extract_categories(post)
    tags = extract_tags(post)

    original_url = post.get("URL", f"{source_url.rstrip('/')}/{slug}/")

    lines = [
        "---",
        f'title: "{title}"',
        f'date: "{date}"',
        f'author: "{author}"',
    ]

    if categories:
        cat_list = ", ".join(f'"{c}"' for c in categories)
        lines.append(f"categories: [{cat_list}]")

    if tags:
        tag_list = ", ".join(f'"{t}"' for t in tags)
        lines.append(f"tags: [{tag_list}]")

    lines.append(f'slug: "{slug}"')
    lines.append(f'original_url: "{original_url}"')

    if featured_image:
        lines.append(f'featured_image: "{featured_image}"')

    lines.append("---")
    return "\n".join(lines)


def post_to_filename(post: dict[str, Any]) -> str:
    """Generate a filename for a post based on date and slug.

    Format: YYYY-MM-DD-slug.md

    Args:
        post: Post dict from the WordPress.com public API.

    Returns:
        Filename string.
    """
    date_str = post.get("date", "")[:10]  # YYYY-MM-DD
    slug = post.get("slug", "untitled")

    # Sanitize slug for filesystem safety
    slug = re.sub(r"[^\w\-]", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")

    if date_str:
        return f"{date_str}-{slug}.md"
    return f"{slug}.md"


def save_post(
    post: dict[str, Any],
    output_dir: Path,
    source_url: str,
    download_images: bool = False,
    human: bool = False,
) -> str | None:
    """Convert a post to markdown and save to disk.

    Args:
        post: Post dict from the WordPress.com public API.
        output_dir: Directory to write markdown files.
        source_url: Blog base URL.
        download_images: If True, download images and rewrite URLs.
        human: If True, print progress to stderr.

    Returns:
        Filename of saved post, or None on failure.
    """
    filename = post_to_filename(post)
    file_path = output_dir / filename

    # WordPress.com API: content is a direct string field
    html_content = post.get("content", "")
    markdown_body = html_to_markdown(html_content)

    # Download images if requested
    if download_images:
        markdown_body = download_and_replace_images(html_content, markdown_body, output_dir, human=human)

        # Also download featured image
        featured_url = get_featured_image_url(post)
        if featured_url:
            images_dir = output_dir / "images"
            download_image(featured_url, images_dir, human=human)

    frontmatter = build_frontmatter(post, source_url)
    full_content = f"{frontmatter}\n\n{markdown_body}\n"

    file_path.write_text(full_content, encoding="utf-8")
    return filename


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    """CLI entry point for WordPress scraper."""
    parser = argparse.ArgumentParser(
        description="Scrape all posts from a WordPress.com blog and save as markdown files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--source",
        required=True,
        help="WordPress.com blog URL (e.g., https://example-blog.wordpress.com)",
    )
    parser.add_argument("--output", required=True, help="Directory to save markdown files")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of posts to scrape (for testing)")
    parser.add_argument(
        "--download-images", action="store_true", help="Download images and rewrite URLs to local paths"
    )
    parser.add_argument("--skip-existing", action="store_true", help="Skip posts that already have a markdown file")
    parser.add_argument("--human", action="store_true", help="Human-readable progress output instead of JSON")

    args = parser.parse_args()

    source_url = args.source.rstrip("/")
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.human:
        print(f"Scraping: {source_url}", file=sys.stderr)
        print(f"Output:   {output_dir}", file=sys.stderr)
        if args.limit:
            print(f"Limit:    {args.limit} posts", file=sys.stderr)
        print(file=sys.stderr)

    # Fetch all posts
    if args.human:
        print("Fetching posts...", file=sys.stderr)

    posts = fetch_all_posts(source_url, post_type="post", limit=args.limit, human=args.human)

    if args.human:
        print(f"  Found {len(posts)} posts", file=sys.stderr)
        print(file=sys.stderr)

    # Also fetch pages
    if args.human:
        print("Fetching pages...", file=sys.stderr)

    pages = fetch_all_posts(source_url, post_type="page", limit=None, human=args.human)

    if args.human:
        print(f"  Found {len(pages)} pages", file=sys.stderr)
        print(file=sys.stderr)

    # Process all items
    all_items = posts + pages
    saved: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    if args.human:
        print(f"Processing {len(all_items)} items...", file=sys.stderr)

    for i, post in enumerate(all_items, 1):
        title = unescape(post.get("title", "Untitled"))
        filename = post_to_filename(post)

        # Skip existing files if requested
        if args.skip_existing and (output_dir / filename).exists():
            skipped.append(filename)
            if args.human:
                print(f"  [{i}/{len(all_items)}] SKIP: {title}", file=sys.stderr)
            continue

        if args.human:
            print(f"  [{i}/{len(all_items)}] {title}", file=sys.stderr)

        try:
            saved_name = save_post(
                post=post,
                output_dir=output_dir,
                source_url=source_url,
                download_images=args.download_images,
                human=args.human,
            )
            if saved_name:
                saved.append(saved_name)
            else:
                errors.append(f"Failed to save: {title}")
        except Exception as e:
            errors.append(f"{title}: {e}")
            if args.human:
                print(f"    ERROR: {e}", file=sys.stderr)

    # Output summary
    result: dict[str, Any] = {
        "status": "success" if not errors else "partial",
        "source": source_url,
        "output_dir": str(output_dir),
        "posts_found": len(posts),
        "pages_found": len(pages),
        "saved": len(saved),
        "skipped": len(skipped),
        "errors": len(errors),
        "files": saved,
    }

    if errors:
        result["error_details"] = errors

    if args.human:
        print(file=sys.stderr)
        print("Done!", file=sys.stderr)
        print(f"  Posts found:  {len(posts)}", file=sys.stderr)
        print(f"  Pages found:  {len(pages)}", file=sys.stderr)
        print(f"  Saved:        {len(saved)}", file=sys.stderr)
        if skipped:
            print(f"  Skipped:      {len(skipped)}", file=sys.stderr)
        if errors:
            print(f"  Errors:       {len(errors)}", file=sys.stderr)
            for err in errors:
                print(f"    - {err}", file=sys.stderr)
    else:
        print(json.dumps(result, indent=2))

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
