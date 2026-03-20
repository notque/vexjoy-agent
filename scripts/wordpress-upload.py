#!/usr/bin/env python3
"""WordPress REST API uploader for creating posts from markdown files.

Uploads markdown files to WordPress as posts using Application Passwords authentication.
Parses YAML frontmatter for metadata (title, categories, tags, slug, excerpt).
Categories and tags are resolved by name via the WordPress REST API.
Tags are created automatically if they don't exist.

Usage:
    python3 scripts/wordpress-upload.py --file article.md --status draft --human
    python3 scripts/wordpress-upload.py --file article.md --title "My Title" --category "News" --status draft
    python3 scripts/wordpress-upload.py --file article.md --classic --status draft

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

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]  # Only needed for upload, not --validate

# ---------------------------------------------------------------------------
# Module-level taxonomy caches (avoid repeated API calls within a single run)
# ---------------------------------------------------------------------------
_category_cache: dict[str, int | None] = {}
_tag_cache: dict[str, int] = {}


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


def _get_auth_headers(config: dict[str, str], content_type: str = "application/json") -> dict[str, str]:
    """Build HTTP headers with Basic Auth for WordPress REST API.

    Args:
        config: WordPress config dict.
        content_type: Content-Type header value.

    Returns:
        Headers dict.
    """
    credentials = f"{config['user']}:{config['password']}"
    token = base64.b64encode(credentials.encode()).decode("utf-8")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": content_type,
    }


# ---------------------------------------------------------------------------
# YAML Frontmatter
# ---------------------------------------------------------------------------


def strip_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Strip YAML frontmatter from markdown content.

    Supports two list formats:
        categories: ["Technology", "News"]
        tags:
          - Example Tag
          - Example Event

    Args:
        content: Raw markdown file content.

    Returns:
        Tuple of (frontmatter dict, markdown body without frontmatter).
    """
    if not content.startswith("---"):
        return {}, content

    # Find the closing --- (must be on its own line after the opening)
    lines = content.split("\n")
    end_line_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_line_idx = i
            break

    if end_line_idx is None:
        return {}, content

    frontmatter_lines = lines[1:end_line_idx]
    body = "\n".join(lines[end_line_idx + 1 :]).strip()

    metadata: dict[str, Any] = {}
    current_key: str | None = None

    for line in frontmatter_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Key: value line (not a list item)
        if ":" in stripped and not stripped.startswith("-"):
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()

            current_key = key

            if not value:
                # Value will come as subsequent list items
                continue

            # Handle inline JSON-style list: ["item1", "item2"]
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                if inner:
                    items = [item.strip().strip("\"'") for item in inner.split(",")]
                    metadata[key] = items
                else:
                    metadata[key] = []
                continue

            # Handle boolean
            if value.lower() in ("true", "false"):
                metadata[key] = value.lower() == "true"
                continue

            # Strip surrounding quotes
            metadata[key] = value.strip("\"'")

        elif stripped.startswith("- ") and current_key is not None:
            # Multi-line list item for the current key
            val = stripped[2:].strip().strip("\"'")
            if current_key not in metadata:
                metadata[current_key] = []
            elif isinstance(metadata[current_key], str):
                # Key had a scalar value, convert to list
                metadata[current_key] = [metadata[current_key]]
            metadata[current_key].append(val)

    return metadata, body


def extract_title_from_markdown(content: str) -> str | None:
    """Extract title from the first H1 heading in markdown.

    Args:
        content: Markdown content.

    Returns:
        Title string or None if no H1 found.
    """
    match = re.search(r"^# (.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else None


# ---------------------------------------------------------------------------
# Taxonomy Lookup (Categories & Tags)
# ---------------------------------------------------------------------------


def lookup_category_id(config: dict[str, str], name: str) -> int | None:
    """Look up a WordPress category ID by exact name match.

    Args:
        config: WordPress config dict.
        name: Category name (case-insensitive).

    Returns:
        Category ID if found, None otherwise.
    """
    cache_key = name.lower()
    if cache_key in _category_cache:
        return _category_cache[cache_key]

    api_url = f"{config['site'].rstrip('/')}/wp-json/wp/v2/categories"
    headers = _get_auth_headers(config)

    try:
        response = requests.get(api_url, headers=headers, params={"search": name, "per_page": 100}, timeout=15)
        if response.status_code == 200:
            for cat in response.json():
                if cat.get("name", "").lower() == cache_key:
                    _category_cache[cache_key] = cat["id"]
                    return cat["id"]
    except Exception as e:
        print(f"Warning: category lookup failed for '{name}': {e}", file=sys.stderr)

    _category_cache[cache_key] = None
    return None


def lookup_or_create_tag_id(config: dict[str, str], name: str) -> int | None:
    """Look up a WordPress tag by name, creating it if it doesn't exist.

    Args:
        config: WordPress config dict.
        name: Tag name to find or create.

    Returns:
        Tag ID if found or created, None on failure.
    """
    cache_key = name.lower()
    if cache_key in _tag_cache:
        return _tag_cache[cache_key]

    api_url = f"{config['site'].rstrip('/')}/wp-json/wp/v2/tags"
    headers = _get_auth_headers(config)

    try:
        # Search for existing tag
        response = requests.get(api_url, headers=headers, params={"search": name, "per_page": 100}, timeout=15)
        if response.status_code == 200:
            for tag in response.json():
                if tag.get("name", "").lower() == cache_key:
                    _tag_cache[cache_key] = tag["id"]
                    return tag["id"]

        # Not found -- create it
        create_resp = requests.post(api_url, headers=headers, json={"name": name}, timeout=15)
        if create_resp.status_code == 201:
            new_tag = create_resp.json()
            _tag_cache[cache_key] = new_tag["id"]
            return new_tag["id"]

        # Handle "term_exists" (tag exists but search missed it due to slug mismatch)
        if create_resp.status_code == 400:
            error_data = create_resp.json()
            if error_data.get("code") == "term_exists":
                existing_id = error_data.get("data", {}).get("term_id")
                if existing_id:
                    _tag_cache[cache_key] = existing_id
                    return existing_id

        print(f"Warning: failed to create tag '{name}': HTTP {create_resp.status_code}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: tag lookup/create failed for '{name}': {e}", file=sys.stderr)

    return None


def resolve_taxonomy_ids(config: dict[str, str], frontmatter: dict[str, Any]) -> tuple[list[int], list[int]]:
    """Resolve frontmatter category/tag names to WordPress taxonomy IDs.

    Categories that don't exist are skipped with a warning.
    Tags that don't exist are created automatically.

    Args:
        config: WordPress config dict.
        frontmatter: Parsed YAML frontmatter dict.

    Returns:
        Tuple of (category_ids, tag_ids).
    """
    category_ids: list[int] = []
    tag_ids: list[int] = []

    raw_categories = frontmatter.get("categories", [])
    if isinstance(raw_categories, str):
        raw_categories = [raw_categories]

    raw_tags = frontmatter.get("tags", [])
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]

    for cat_name in raw_categories:
        cat_id = lookup_category_id(config, cat_name)
        if cat_id is not None:
            category_ids.append(cat_id)
        else:
            print(f"Warning: category '{cat_name}' not found in WordPress, skipping", file=sys.stderr)

    for tag_name in raw_tags:
        tag_id = lookup_or_create_tag_id(config, tag_name)
        if tag_id is not None:
            tag_ids.append(tag_id)

    return category_ids, tag_ids


# ---------------------------------------------------------------------------
# Markdown to HTML Conversion
# ---------------------------------------------------------------------------


def _apply_inline_formatting(text: str) -> str:
    """Apply inline markdown formatting (bold, italic, images, links).

    Args:
        text: Text possibly containing inline markdown.

    Returns:
        Text with inline markdown converted to HTML.
    """
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1"/>', text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    return text


def _html_escape_code(text: str) -> str:
    """Escape HTML special characters for use inside <code> blocks.

    Args:
        text: Raw code text.

    Returns:
        HTML-escaped text safe for embedding in <code> elements.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def markdown_to_gutenberg_blocks(markdown_content: str) -> str:
    """Convert markdown to WordPress Gutenberg block format.

    Each element becomes a proper Gutenberg block that WordPress
    can edit natively in the block editor.

    Supported block types:
        - Headings (H1-H4) -> wp:heading
        - Paragraphs -> wp:paragraph
        - Unordered lists -> wp:list
        - Ordered lists -> wp:list (ordered)
        - Blockquotes -> wp:quote
        - Images -> wp:image
        - Separators -> wp:separator
        - Fenced code blocks -> wp:code
        - Button links -> wp:buttons / wp:button

    Args:
        markdown_content: Markdown text (frontmatter already stripped).

    Returns:
        Gutenberg block HTML string.
    """
    lines = markdown_content.split("\n")
    blocks: list[str] = []
    current_paragraph: list[str] = []
    list_items: list[str] = []
    in_list = False
    list_type: str = "ul"  # "ul" for unordered, "ol" for ordered

    # Fenced code block state
    in_code_block = False
    code_lines: list[str] = []
    code_language: str = ""

    def flush_paragraph() -> None:
        nonlocal current_paragraph
        if current_paragraph:
            text = _apply_inline_formatting(" ".join(current_paragraph))
            blocks.append(f"<!-- wp:paragraph -->\n<p>{text}</p>\n<!-- /wp:paragraph -->")
            current_paragraph = []

    def flush_list() -> None:
        nonlocal in_list, list_items, list_type
        if list_items:
            items_html = "\n".join(f"<li>{item}</li>" for item in list_items)
            if list_type == "ol":
                blocks.append(f'<!-- wp:list {{"ordered":true}} -->\n<ol>\n{items_html}\n</ol>\n<!-- /wp:list -->')
            else:
                blocks.append(f"<!-- wp:list -->\n<ul>\n{items_html}\n</ul>\n<!-- /wp:list -->")
            list_items = []
            in_list = False
            list_type = "ul"

    for line in lines:
        stripped = line.strip()

        # --- Fenced code block handling ---
        if stripped.startswith("```"):
            if not in_code_block:
                # Opening fence: flush other accumulators and start code block
                flush_paragraph()
                flush_list()
                in_code_block = True
                code_lines = []
                code_language = stripped[3:].strip()
                continue
            else:
                # Closing fence: emit the wp:code block
                in_code_block = False
                code_content = _html_escape_code("\n".join(code_lines))
                if code_language:
                    attr = f' {{"language":"{code_language}"}}'
                else:
                    attr = ""
                code_html = f'<pre class="wp-block-code"><code>{code_content}</code></pre>'
                blocks.append(f"<!-- wp:code{attr} -->\n{code_html}\n<!-- /wp:code -->")
                code_lines = []
                code_language = ""
                continue

        if in_code_block:
            # Preserve original line content (not stripped) inside code blocks
            code_lines.append(line)
            continue

        # Empty line -- flush accumulators
        if not stripped:
            flush_paragraph()
            flush_list()
            continue

        # H1 -- skip (becomes the post title, not rendered in body)
        if stripped.startswith("# ") and not stripped.startswith("## "):
            flush_paragraph()
            flush_list()
            continue

        # H2
        if stripped.startswith("## ") and not stripped.startswith("### "):
            flush_paragraph()
            flush_list()
            heading = _apply_inline_formatting(stripped[3:].strip())
            blocks.append(f"<!-- wp:heading -->\n<h2>{heading}</h2>\n<!-- /wp:heading -->")
            continue

        # H3
        if stripped.startswith("### ") and not stripped.startswith("#### "):
            flush_paragraph()
            flush_list()
            heading = _apply_inline_formatting(stripped[4:].strip())
            blocks.append(f'<!-- wp:heading {{"level":3}} -->\n<h3>{heading}</h3>\n<!-- /wp:heading -->')
            continue

        # H4
        if stripped.startswith("#### "):
            flush_paragraph()
            flush_list()
            heading = _apply_inline_formatting(stripped[5:].strip())
            blocks.append(f'<!-- wp:heading {{"level":4}} -->\n<h4>{heading}</h4>\n<!-- /wp:heading -->')
            continue

        # Horizontal rule / separator (--- *** ___)
        if stripped in ("---", "***", "___"):
            flush_paragraph()
            flush_list()
            sep_html = '<hr class="wp-block-separator has-alpha-channel-opacity"/>'
            blocks.append(f"<!-- wp:separator -->\n{sep_html}\n<!-- /wp:separator -->")
            continue

        # Button link: [Button Text](url){.wp-button}
        button_match = re.match(r"^\[(.+?)\]\((.+?)\)\{\.wp-button\}$", stripped)
        if button_match:
            flush_paragraph()
            flush_list()
            btn_text = button_match.group(1)
            btn_url = button_match.group(2)
            btn_inner = (
                f'<div class="wp-block-button"><a class="wp-block-button__link" href="{btn_url}">{btn_text}</a></div>'
            )
            blocks.append(
                f"<!-- wp:buttons -->\n"
                f'<div class="wp-block-buttons"><!-- wp:button -->\n'
                f"{btn_inner}\n"
                f"<!-- /wp:button --></div>\n"
                f"<!-- /wp:buttons -->"
            )
            continue

        # List item (unordered: - or *)
        if stripped.startswith("- ") or stripped.startswith("* "):
            flush_paragraph()
            # If switching from ordered to unordered, flush first
            if in_list and list_type == "ol":
                flush_list()
            in_list = True
            list_type = "ul"
            item_text = _apply_inline_formatting(stripped[2:].strip())
            list_items.append(item_text)
            continue

        # List item (ordered: 1. 2. etc.)
        ordered_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if ordered_match:
            flush_paragraph()
            # If switching from unordered to ordered, flush first
            if in_list and list_type == "ul":
                flush_list()
            in_list = True
            list_type = "ol"
            item_text = _apply_inline_formatting(ordered_match.group(1).strip())
            list_items.append(item_text)
            continue

        # Blockquote
        if stripped.startswith("> "):
            flush_paragraph()
            flush_list()
            quote_text = _apply_inline_formatting(stripped[2:].strip())
            bq_html = f'<blockquote class="wp-block-quote"><p>{quote_text}</p></blockquote>'
            blocks.append(f"<!-- wp:quote -->\n{bq_html}\n<!-- /wp:quote -->")
            continue

        # Standalone image on its own line (markdown syntax)
        image_match = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if image_match:
            flush_paragraph()
            flush_list()
            alt_text = image_match.group(1)
            img_url = image_match.group(2)
            fig_html = f'<figure class="wp-block-image aligncenter"><img src="{img_url}" alt="{alt_text}"/></figure>'
            blocks.append(f'<!-- wp:image {{"align":"center"}} -->\n{fig_html}\n<!-- /wp:image -->')
            continue

        # Standalone raw <img> tag on its own line
        raw_img_match = re.match(r"^<img\s", stripped)
        if raw_img_match:
            flush_paragraph()
            flush_list()
            fig_html = f'<figure class="wp-block-image aligncenter">{stripped}</figure>'
            blocks.append(f'<!-- wp:image {{"align":"center"}} -->\n{fig_html}\n<!-- /wp:image -->')
            continue

        # Regular paragraph text -- accumulate
        if in_list:
            flush_list()
        current_paragraph.append(stripped)

    # Flush remaining content
    flush_paragraph()
    flush_list()

    return "\n\n".join(blocks)


def markdown_to_classic_html(markdown_content: str) -> str:
    """Convert markdown to classic HTML (no Gutenberg blocks).

    Args:
        markdown_content: Markdown text (frontmatter already stripped).

    Returns:
        Classic HTML string.
    """
    try:
        import markdown as md_lib

        return md_lib.markdown(markdown_content, extensions=["extra", "smarty", "sane_lists"])
    except ImportError:
        pass

    # Fallback: basic regex-based conversion
    html = markdown_content

    # Headers (order matters: most specific first)
    html = re.sub(r"^#### (.+)$", r"<h4>\1</h4>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

    # Images (before links, since ![alt](url) would match link pattern)
    html = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1" class="aligncenter size-full" />', html)

    # Links
    html = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', html)

    # Horizontal rules
    html = re.sub(r"^---+$", r"<hr>", html, flags=re.MULTILINE)

    # Unordered list items
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)

    # Wrap non-tagged lines in <p> tags
    result: list[str] = []
    for line in html.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("<"):
            result.append(f"<p>{stripped}</p>")
        else:
            result.append(line)

    return "\n".join(result)


def markdown_to_html(markdown_content: str, use_blocks: bool = True) -> str:
    """Convert markdown to HTML, with Gutenberg blocks or classic format.

    Args:
        markdown_content: Markdown text (frontmatter already stripped).
        use_blocks: If True, use Gutenberg block format. If False, classic HTML.

    Returns:
        HTML string ready for WordPress.
    """
    if use_blocks:
        return markdown_to_gutenberg_blocks(markdown_content)
    return markdown_to_classic_html(markdown_content)


# ---------------------------------------------------------------------------
# Block Validation
# ---------------------------------------------------------------------------

# Regex for Gutenberg block comments: opening, closing, and self-closing
_BLOCK_OPEN_RE = re.compile(r"<!--\s+wp:(\S+?)(?:\s+(\{.*?\}))?\s+-->")
_BLOCK_CLOSE_RE = re.compile(r"<!--\s+/wp:(\S+?)\s+-->")
_BLOCK_SELF_CLOSE_RE = re.compile(r"<!--\s+wp:(\S+?)(?:\s+(\{.*?\}))?\s+/-->")


def validate_gutenberg_blocks(html: str) -> list[str]:
    """Validate Gutenberg block HTML for structural correctness.

    Checks:
        1. Block balance: opening comments must have matching closing comments.
           Self-closing blocks (e.g., ``<!-- wp:separator /-->``) are excluded.
        2. JSON attributes: any JSON in block comments must be valid.

    Args:
        html: Gutenberg block HTML string.

    Returns:
        List of error strings. Empty list means valid.
    """
    errors: list[str] = []

    # Track opening and closing counts per block type
    open_counts: dict[str, int] = {}
    close_counts: dict[str, int] = {}

    # Find self-closing blocks first (these don't need closing tags)
    self_closing_positions: set[int] = set()
    for match in _BLOCK_SELF_CLOSE_RE.finditer(html):
        self_closing_positions.add(match.start())
        # Validate JSON in self-closing blocks too
        json_str = match.group(2)
        if json_str:
            try:
                json.loads(json_str)
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON in self-closing wp:{match.group(1)} block: {e}")

    # Count opening blocks (excluding self-closing ones)
    for match in _BLOCK_OPEN_RE.finditer(html):
        if match.start() in self_closing_positions:
            continue
        block_name = match.group(1)
        open_counts[block_name] = open_counts.get(block_name, 0) + 1

        # Validate JSON attributes
        json_str = match.group(2)
        if json_str:
            try:
                json.loads(json_str)
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON in wp:{block_name} block: {e}")

    # Count closing blocks
    for match in _BLOCK_CLOSE_RE.finditer(html):
        block_name = match.group(1)
        close_counts[block_name] = close_counts.get(block_name, 0) + 1

    # Check balance
    all_block_names = set(open_counts.keys()) | set(close_counts.keys())
    for name in sorted(all_block_names):
        opened = open_counts.get(name, 0)
        closed = close_counts.get(name, 0)
        if opened != closed:
            errors.append(f"Block wp:{name} mismatch: {opened} opening vs {closed} closing")

    return errors


def count_gutenberg_blocks(html: str) -> int:
    """Count the total number of Gutenberg blocks in HTML.

    Args:
        html: Gutenberg block HTML string.

    Returns:
        Total block count (opening + self-closing blocks).
    """
    self_closing = len(_BLOCK_SELF_CLOSE_RE.findall(html))
    # Count opening blocks excluding self-closing positions
    opening = 0
    self_closing_positions: set[int] = set()
    for match in _BLOCK_SELF_CLOSE_RE.finditer(html):
        self_closing_positions.add(match.start())
    for match in _BLOCK_OPEN_RE.finditer(html):
        if match.start() not in self_closing_positions:
            opening += 1
    return opening + self_closing


# ---------------------------------------------------------------------------
# Post Creation
# ---------------------------------------------------------------------------


def update_post(
    config: dict[str, str],
    post_id: int,
    title: str | None = None,
    content: str | None = None,
    status: str | None = None,
    categories: list[int] | None = None,
    tags: list[int] | None = None,
    excerpt: str | None = None,
    slug: str | None = None,
) -> dict[str, Any]:
    """Update an existing post via WordPress REST API.

    Only sends fields that are provided (not None).

    Args:
        config: WordPress config dict.
        post_id: The post ID to update.
        title: New title (optional).
        content: New HTML content (optional).
        status: New status (optional).
        categories: Category IDs (optional, replaces existing).
        tags: Tag IDs (optional, replaces existing).
        excerpt: Post excerpt (optional).
        slug: URL slug (optional).

    Returns:
        Result dict with status, post_id, post_url on success, or error details.
    """
    api_url = f"{config['site'].rstrip('/')}/wp-json/wp/v2/posts/{post_id}"
    headers = _get_auth_headers(config)

    post_data: dict[str, Any] = {}
    if title is not None:
        post_data["title"] = title
    if content is not None:
        post_data["content"] = content
    if status is not None:
        post_data["status"] = status
    if categories is not None:
        post_data["categories"] = categories
    if tags is not None:
        post_data["tags"] = tags
    if excerpt is not None:
        post_data["excerpt"] = excerpt
    if slug is not None:
        post_data["slug"] = slug

    try:
        response = requests.post(api_url, headers=headers, json=post_data, timeout=30)

        if response.status_code == 200:
            data = response.json()
            return {
                "status": "success",
                "action": "updated",
                "post_id": data.get("id"),
                "post_url": data.get("link"),
                "edit_url": f"{config['site'].rstrip('/')}/wp-admin/post.php?post={data.get('id')}&action=edit",
                "post_status": data.get("status"),
            }
        else:
            error_data = {}
            with contextlib.suppress(Exception):
                error_data = response.json()
            return {
                "status": "error",
                "error": f"WordPress API error: {response.status_code}",
                "details": error_data.get("message", response.text[:200]),
            }
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": f"Request failed: {e}"}


def create_post(
    config: dict[str, str],
    title: str,
    content: str,
    status: str = "draft",
    categories: list[int] | None = None,
    tags: list[int] | None = None,
    author: int | None = None,
    excerpt: str | None = None,
    slug: str | None = None,
) -> dict[str, Any]:
    """Create a post via WordPress REST API.

    Args:
        config: WordPress config dict.
        title: Post title.
        content: Post HTML content.
        status: Post status (draft, publish, pending, private).
        categories: List of category IDs.
        tags: List of tag IDs.
        author: Author user ID.
        excerpt: Post excerpt.
        slug: URL slug.

    Returns:
        Result dict with status, post_id, post_url on success, or error details.
    """
    api_url = f"{config['site'].rstrip('/')}/wp-json/wp/v2/posts"
    headers = _get_auth_headers(config)

    post_data: dict[str, Any] = {
        "title": title,
        "content": content,
        "status": status,
    }
    if categories:
        post_data["categories"] = categories
    if tags:
        post_data["tags"] = tags
    if author:
        post_data["author"] = author
    if excerpt:
        post_data["excerpt"] = excerpt
    if slug:
        post_data["slug"] = slug

    try:
        response = requests.post(api_url, headers=headers, json=post_data, timeout=30)

        if response.status_code == 201:
            data = response.json()
            return {
                "status": "success",
                "post_id": data.get("id"),
                "post_url": data.get("link"),
                "edit_url": f"{config['site'].rstrip('/')}/wp-admin/post.php?post={data.get('id')}&action=edit",
                "post_status": data.get("status"),
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _output_result(result: dict[str, Any], human: bool) -> int:
    """Print result in human or JSON format and return exit code.

    Args:
        result: Result dict with "status" key.
        human: If True, print human-readable output on success.

    Returns:
        0 on success, 1 on error.
    """
    if human and result["status"] == "success":
        action = result.get("action", "created")
        print(f"Post {action} successfully!")
        print(f"  ID:     {result['post_id']}")
        print(f"  Status: {result['post_status']}")
        print(f"  View:   {result['post_url']}")
        print(f"  Edit:   {result['edit_url']}")
    else:
        print(json.dumps(result, indent=2))

    return 0 if result["status"] == "success" else 1


def main() -> int:
    """CLI entry point for WordPress upload."""
    parser = argparse.ArgumentParser(
        description="Upload markdown files to WordPress as posts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--file", "-f", required=True, help="Path to markdown file to upload")
    parser.add_argument("--title", "-t", help="Post title (overrides frontmatter/H1)")
    parser.add_argument(
        "--status",
        "-s",
        default="draft",
        choices=["draft", "publish", "pending", "private"],
        help="Post status (default: draft)",
    )
    parser.add_argument("--category", action="append", help="Category name to look up (repeatable)")
    parser.add_argument("--tag", action="append", help="Tag name to look up or create (repeatable)")
    parser.add_argument("--author", type=int, help="Author user ID")
    parser.add_argument(
        "--update", type=int, metavar="POST_ID", help="Update existing post instead of creating new (pass post ID)"
    )
    parser.add_argument("--classic", action="store_true", help="Use classic HTML format instead of Gutenberg blocks")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Convert to Gutenberg HTML, validate blocks, print results, and exit (no upload)",
    )
    parser.add_argument("--human", action="store_true", help="Output human-readable format instead of JSON")

    args = parser.parse_args()

    # Read markdown file (needed for both --validate and upload)
    file_path = Path(args.file)
    if not file_path.exists():
        print(json.dumps({"status": "error", "error": f"File not found: {args.file}"}, indent=2))
        return 1

    raw_content = file_path.read_text()

    # Parse frontmatter
    frontmatter, markdown_body = strip_frontmatter(raw_content)

    # Convert markdown to HTML
    use_blocks = not args.classic
    html_content = markdown_to_html(markdown_body, use_blocks=use_blocks)

    # --validate mode: validate and exit without uploading
    if args.validate:
        if args.classic:
            print(
                json.dumps(
                    {"status": "skipped", "reason": "Validation only applies to Gutenberg blocks (not --classic)"}
                )
            )
            return 0
        validation_errors = validate_gutenberg_blocks(html_content)
        block_count = count_gutenberg_blocks(html_content)
        if validation_errors:
            print(json.dumps({"status": "invalid", "errors": validation_errors, "block_count": block_count}, indent=2))
            return 1
        print(json.dumps({"status": "valid", "block_count": block_count}, indent=2))
        return 0

    # Validate config (only needed for upload, not --validate)
    config = get_config()
    errors = validate_config(config)
    if errors:
        print(json.dumps({"status": "error", "error": "Configuration errors", "details": errors}, indent=2))
        return 1

    # Auto-validate Gutenberg blocks before upload (non-blocking warnings)
    if use_blocks:
        validation_errors = validate_gutenberg_blocks(html_content)
        if validation_errors:
            for err in validation_errors:
                print(f"Warning: block validation: {err}", file=sys.stderr)

    # Resolve title: CLI arg > frontmatter > first H1
    title = args.title
    if not title:
        title = frontmatter.get("title")
        if isinstance(title, list):
            title = title[0] if title else None
    if not title:
        title = extract_title_from_markdown(markdown_body)
    if not title:
        print(json.dumps({"status": "error", "error": "No title provided and no H1 found in markdown"}, indent=2))
        return 1

    # Resolve taxonomy IDs from frontmatter
    fm_category_ids, fm_tag_ids = resolve_taxonomy_ids(config, frontmatter)

    # Resolve taxonomy IDs from CLI args
    cli_category_ids: list[int] = []
    cli_tag_ids: list[int] = []

    if args.category:
        for cat_name in args.category:
            cat_id = lookup_category_id(config, cat_name)
            if cat_id is not None:
                cli_category_ids.append(cat_id)
            else:
                print(f"Warning: category '{cat_name}' not found in WordPress, skipping", file=sys.stderr)

    if args.tag:
        for tag_name in args.tag:
            tag_id = lookup_or_create_tag_id(config, tag_name)
            if tag_id is not None:
                cli_tag_ids.append(tag_id)

    # Merge CLI + frontmatter IDs (deduplicated, CLI first)
    all_category_ids = list(dict.fromkeys(cli_category_ids + fm_category_ids))
    all_tag_ids = list(dict.fromkeys(cli_tag_ids + fm_tag_ids))

    # Extract optional metadata from frontmatter
    excerpt = frontmatter.get("description") or frontmatter.get("excerpt")
    if isinstance(excerpt, list):
        excerpt = excerpt[0] if excerpt else None
    slug = frontmatter.get("slug")
    if isinstance(slug, list):
        slug = slug[0] if slug else None

    # Create or update post
    if args.update:
        result = update_post(
            config=config,
            post_id=args.update,
            title=title,
            content=html_content,
            status=args.status,
            categories=all_category_ids or None,
            tags=all_tag_ids or None,
            excerpt=excerpt,
            slug=slug,
        )
    else:
        result = create_post(
            config=config,
            title=title,
            content=html_content,
            status=args.status,
            categories=all_category_ids or None,
            tags=all_tag_ids or None,
            author=args.author,
            excerpt=excerpt,
            slug=slug,
        )

    return _output_result(result, args.human)


if __name__ == "__main__":
    sys.exit(main())
