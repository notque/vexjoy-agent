#!/usr/bin/env python3
"""
Fetch a URL, convert to markdown, and save to research/{topic}/raw/.

Downloads images locally and rewrites paths. Saves with YAML frontmatter.

Usage:
    kb-clip.py --topic TOPIC --url URL
    kb-clip.py --topic TOPIC --url URL --title "Custom Title"
    kb-clip.py --topic TOPIC --url URL --type paper

Exit codes:
    0 = success
    1 = fatal error (network failure, parse error, write failure)
"""

from __future__ import annotations

import argparse
import contextlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import ClassVar

# --- Constants ---

_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_FETCH_TIMEOUT = 20
_MAX_SLUG_LEN = 60
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".avif"}


# --- Data model ---


@dataclass
class ClipResult:
    """Result from clipping a URL."""

    title: str
    source_url: str
    clipped: str
    content_type: str
    markdown: str
    image_count: int = 0
    slug: str = ""


# --- HTML parsing ---


class _TagNode:
    """Lightweight DOM node for block-level reconstruction."""

    def __init__(self, tag: str, attrs: dict[str, str]) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: list[_TagNode | str] = []
        self.parent: _TagNode | None = None

    def text_content(self) -> str:
        """Recursively collect all text."""
        parts: list[str] = []
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            else:
                parts.append(child.text_content())
        return "".join(parts)


class _HTMLToMarkdown(HTMLParser):
    """Convert HTML to markdown using stdlib html.parser.

    Handles: headings, paragraphs, links, images, ul/ol/li, bold, italic,
    code, pre/code blocks, blockquotes, and basic tables.
    """

    # Tags that are rendered inline
    _INLINE_TAGS: ClassVar[set[str]] = {"a", "strong", "b", "em", "i", "code", "span", "s", "del", "mark"}
    # Tags that are skipped entirely (no output)
    _SKIP_TAGS: ClassVar[set[str]] = {
        "script",
        "style",
        "nav",
        "footer",
        "header",
        "aside",
        "noscript",
        "button",
        "form",
        "iframe",
    }
    # Heading levels
    _HEADING_TAGS: ClassVar[set[str]] = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: list[str] = []
        self._output: list[str] = []
        self._list_depth = 0
        self._ordered_list_counters: list[int] = []
        self._skip_depth = 0
        self._in_pre = False
        self._in_code = False
        self._in_table = False
        self._table_rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._current_cell: list[str] = []
        self._link_href = ""
        self._link_text: list[str] = []
        self._in_link = False
        self._images: list[str] = []  # collected img srcs

    @property
    def images(self) -> list[str]:
        """Return collected image srcs."""
        return self._images

    def _current_tag(self) -> str:
        return self._stack[-1] if self._stack else ""

    def _in_skip(self) -> bool:
        return self._skip_depth > 0

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        """Process opening tag."""
        attrs = {k: (v or "") for k, v in attrs_list}

        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return

        if self._in_skip():
            return

        self._stack.append(tag)

        if tag == "pre":
            self._in_pre = True
            self._output.append("\n```\n")

        elif tag == "code":
            if not self._in_pre:
                self._in_code = True
                self._output.append("`")

        elif tag in self._HEADING_TAGS:
            level = int(tag[1])
            self._output.append(f"\n{'#' * level} ")

        elif tag == "p":
            self._output.append("\n\n")

        elif tag == "br":
            self._output.append("  \n")

        elif tag == "hr":
            self._output.append("\n---\n")

        elif tag == "a":
            href = attrs.get("href", "")
            self._in_link = True
            self._link_href = href
            self._link_text = []

        elif tag == "img":
            src = attrs.get("src", "")
            alt = attrs.get("alt", "")
            if src:
                self._images.append(src)
                self._output.append(f"![{alt}]({src})")

        elif tag in ("strong", "b"):
            self._output.append("**")

        elif tag in ("em", "i"):
            self._output.append("_")

        elif tag in ("s", "del"):
            self._output.append("~~")

        elif tag == "blockquote":
            self._output.append("\n> ")

        elif tag == "ul":
            self._list_depth += 1
            self._ordered_list_counters.append(-1)  # -1 = unordered marker
            self._output.append("\n")

        elif tag == "ol":
            self._list_depth += 1
            self._ordered_list_counters.append(0)  # counter starts at 0
            self._output.append("\n")

        elif tag == "li":
            indent = "  " * (self._list_depth - 1)
            if self._ordered_list_counters and self._ordered_list_counters[-1] >= 0:
                self._ordered_list_counters[-1] += 1
                n = self._ordered_list_counters[-1]
                self._output.append(f"\n{indent}{n}. ")
            else:
                self._output.append(f"\n{indent}- ")

        elif tag == "table":
            self._in_table = True
            self._table_rows = []
            self._current_row = []

        elif tag in ("tr",):
            self._current_row = []

        elif tag in ("td", "th"):
            self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        """Process closing tag."""
        if tag in self._SKIP_TAGS:
            self._skip_depth -= 1
            return

        if self._in_skip():
            return

        if self._stack and self._stack[-1] == tag:
            self._stack.pop()

        if tag == "pre":
            self._in_pre = False
            self._output.append("\n```\n")

        elif tag == "code":
            if not self._in_pre:
                self._in_code = False
                self._output.append("`")

        elif tag in self._HEADING_TAGS or tag == "p":
            self._output.append("\n")

        elif tag == "a":
            text = "".join(self._link_text).strip()
            href = self._link_href
            self._in_link = False
            self._link_href = ""
            self._link_text = []
            if text and href:
                self._output.append(f"[{text}]({href})")
            elif text:
                self._output.append(text)

        elif tag in ("strong", "b"):
            self._output.append("**")

        elif tag in ("em", "i"):
            self._output.append("_")

        elif tag in ("s", "del"):
            self._output.append("~~")

        elif tag in ("ul", "ol"):
            self._list_depth = max(0, self._list_depth - 1)
            if self._ordered_list_counters:
                self._ordered_list_counters.pop()
            self._output.append("\n")

        elif tag == "li":
            pass  # text already appended inline

        elif tag == "blockquote":
            self._output.append("\n")

        elif tag in ("td", "th"):
            cell_text = "".join(self._current_cell).strip().replace("|", "\\|")
            self._current_row.append(cell_text)
            self._current_cell = []

        elif tag == "tr":
            if self._current_row:
                self._table_rows.append(self._current_row)
                self._current_row = []

        elif tag == "table":
            self._in_table = False
            self._flush_table()

    def handle_data(self, data: str) -> None:
        """Process text content."""
        if self._in_skip():
            return

        if self._in_link:
            self._link_text.append(data)
            return

        if self._in_table and self._current_cell is not None:
            self._current_cell.append(data)
            return

        if self._in_pre:
            self._output.append(data)
            return

        # Collapse whitespace for inline text
        cleaned = re.sub(r"[ \t]+", " ", data)
        self._output.append(cleaned)

    def _flush_table(self) -> None:
        """Render accumulated table rows as a markdown table."""
        if not self._table_rows:
            return

        self._output.append("\n")
        for i, row in enumerate(self._table_rows):
            self._output.append("| " + " | ".join(row) + " |")
            self._output.append("\n")
            if i == 0:
                # Header separator
                sep = ["---"] * len(row)
                self._output.append("| " + " | ".join(sep) + " |")
                self._output.append("\n")

        self._table_rows = []

    def get_markdown(self) -> str:
        """Return the accumulated markdown, normalized."""
        text = "".join(self._output)
        # Normalize excessive blank lines (max 2 consecutive)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


class _ContentExtractor(HTMLParser):
    """Extract the main article content node from HTML.

    Strategy:
    1. Try <article> element first.
    2. Try <main> element.
    3. Try <div> with most <p> children.
    4. Fall back to <body>.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._root = _TagNode("__root__", {})
        self._stack: list[_TagNode] = [self._root]
        self._title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {k: (v or "") for k, v in attrs_list}
        node = _TagNode(tag, attrs)
        node.parent = self._stack[-1]
        self._stack[-1].children.append(node)
        self._stack.append(node)
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if self._in_title and tag == "title":
            self._in_title = False
        # Pop matching tag from stack
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                self._stack = self._stack[: i + 1]
                self._stack.pop()
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(data)
        if self._in_title:
            self._title += data

    @property
    def page_title(self) -> str:
        """Return <title> text."""
        return self._title.strip()

    def _find_by_tag(self, node: _TagNode, tag: str) -> _TagNode | None:
        """DFS search for first node with given tag."""
        if node.tag == tag:
            return node
        for child in node.children:
            if isinstance(child, _TagNode):
                result = self._find_by_tag(child, tag)
                if result:
                    return result
        return None

    def _count_p_descendants(self, node: _TagNode) -> int:
        """Count <p> descendants in subtree."""
        count = 0
        for child in node.children:
            if isinstance(child, _TagNode):
                if child.tag == "p":
                    count += 1
                count += self._count_p_descendants(child)
        return count

    def _best_div(self, node: _TagNode) -> tuple[_TagNode | None, int]:
        """Find div with most <p> descendants."""
        best: _TagNode | None = None
        best_count = 0
        if node.tag == "div":
            count = self._count_p_descendants(node)
            if count > best_count:
                best = node
                best_count = count
        for child in node.children:
            if isinstance(child, _TagNode):
                candidate, c_count = self._best_div(child)
                if c_count > best_count:
                    best = candidate
                    best_count = c_count
        return best, best_count

    def _node_to_html(self, node: _TagNode) -> str:
        """Serialize a node subtree back to an HTML string."""
        attrs_str = ""
        for k, v in node.attrs.items():
            attrs_str += f' {k}="{v}"'
        parts = [f"<{node.tag}{attrs_str}>"]
        for child in node.children:
            if isinstance(child, str):
                parts.append(child)
            else:
                parts.append(self._node_to_html(child))
        parts.append(f"</{node.tag}>")
        return "".join(parts)

    def extract_content_html(self) -> str:
        """Return the best content node serialized as HTML."""
        root = self._root

        # 1. Try <article>
        node = self._find_by_tag(root, "article")
        if node:
            return self._node_to_html(node)

        # 2. Try <main>
        node = self._find_by_tag(root, "main")
        if node:
            return self._node_to_html(node)

        # 3. Try best <div>
        body = self._find_by_tag(root, "body")
        search_root = body if body else root
        best, count = self._best_div(search_root)
        if best and count >= 3:
            return self._node_to_html(best)

        # 4. Fall back to body
        if body:
            return self._node_to_html(body)

        return self._node_to_html(root)


# --- Core logic ---


def _slugify(text: str, max_len: int = _MAX_SLUG_LEN) -> str:
    """Convert text to a kebab-case slug.

    Args:
        text: Input text (title or URL path).
        max_len: Maximum length of the slug.

    Returns:
        Kebab-case slug, truncated at word boundary if needed.
    """
    text = text.lower().strip()
    # Remove non-alphanumeric characters (keep spaces and hyphens)
    text = re.sub(r"[^\w\s-]", "", text)
    # Replace whitespace/underscores with hyphens
    text = re.sub(r"[\s_]+", "-", text)
    # Collapse multiple hyphens
    text = re.sub(r"-+", "-", text)
    # Truncate at word boundary
    if len(text) > max_len:
        truncated = text[:max_len]
        # Back off to last hyphen to avoid cutting mid-word
        last_hyphen = truncated.rfind("-")
        if last_hyphen > max_len // 2:
            truncated = truncated[:last_hyphen]
        text = truncated
    return text.strip("-")


def _slug_from_url(url: str) -> str:
    """Derive a slug from a URL path.

    Args:
        url: Full URL string.

    Returns:
        Kebab-case slug derived from URL path.
    """
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.rstrip("/")
    # Use the last path segment
    last = path.split("/")[-1] if "/" in path else path
    # Strip extension
    last = re.sub(r"\.[^.]+$", "", last)
    return _slugify(last) if last else _slugify(parsed.netloc.replace(".", "-"))


def _fetch_url(url: str) -> bytes:
    """Fetch raw bytes from a URL, following redirects.

    Args:
        url: URL to fetch.

    Returns:
        Raw response bytes.

    Raises:
        SystemExit: On network or HTTP errors.
    """
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        body = ""
        with contextlib.suppress(Exception):
            body = e.read().decode("utf-8", errors="replace")[:200]
        print(f"ERROR: HTTP {e.code} fetching {url}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: Network error fetching {url}: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except TimeoutError:
        print(f"ERROR: Timeout fetching {url}", file=sys.stderr)
        sys.exit(1)


def _download_image(img_url: str, dest_dir: Path) -> Path | None:
    """Download an image to dest_dir, returning the local path.

    Args:
        img_url: Full URL of the image.
        dest_dir: Directory to save the image to.

    Returns:
        Path to the saved image, or None if download failed.
    """
    # Skip data URIs
    if img_url.startswith("data:"):
        return None

    parsed = urllib.parse.urlparse(img_url)
    filename = Path(parsed.path).name
    if not filename:
        filename = "image"

    # Ensure a reasonable extension
    suffix = Path(filename).suffix.lower()
    if suffix not in _IMAGE_EXTS:
        filename = filename + ".jpg"

    # Avoid duplicate filenames
    dest = dest_dir / filename
    counter = 1
    while dest.exists():
        stem = Path(filename).stem
        ext = Path(filename).suffix
        dest = dest_dir / f"{stem}-{counter}{ext}"
        counter += 1

    req = urllib.request.Request(img_url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(resp.read())
            return dest
    except Exception as e:
        print(f"  [warn] Failed to download image {img_url}: {e}", file=sys.stderr)
        return None


def _resolve_img_url(src: str, base_url: str) -> str:
    """Resolve a potentially relative image src against the page base URL.

    Args:
        src: Image src attribute value.
        base_url: The page URL used as base for relative resolution.

    Returns:
        Absolute image URL.
    """
    if src.startswith(("http://", "https://", "data:")):
        return src
    return urllib.parse.urljoin(base_url, src)


def _build_frontmatter(title: str, source: str, clipped: str, content_type: str, image_count: int) -> str:
    """Build YAML frontmatter string.

    Args:
        title: Page title.
        source: Original source URL.
        clipped: ISO 8601 timestamp.
        content_type: Content type (article, paper, note, etc.).
        image_count: Number of images downloaded.

    Returns:
        YAML frontmatter block including opening/closing delimiters.
    """
    safe_title = title.replace('"', '\\"')
    lines = [
        "---",
        f'title: "{safe_title}"',
        f'source: "{source}"',
        f'clipped: "{clipped}"',
        f"type: {content_type}",
        f"images: {image_count}",
        "---",
    ]
    return "\n".join(lines)


def clip_url(topic: str, url: str, title: str | None, content_type: str, output_root: Path) -> ClipResult:
    """Fetch URL, convert to markdown, download images, save to raw/.

    Args:
        topic: KB topic name (determines output directory).
        url: URL to clip.
        title: Optional title override.
        content_type: Content type tag (article, paper, note, etc.).
        output_root: Root research/ directory path.

    Returns:
        ClipResult with metadata about the clipped page.
    """
    print(f"Fetching {url} ...", file=sys.stderr)
    raw_bytes = _fetch_url(url)

    # Parse HTML: extract title and main content
    extractor = _ContentExtractor()
    try:
        html_str = raw_bytes.decode("utf-8", errors="replace")
        extractor.feed(html_str)
    except Exception as e:
        print(f"ERROR: Failed to parse HTML: {e}", file=sys.stderr)
        sys.exit(1)

    page_title = title or extractor.page_title or "Untitled"
    content_html = extractor.extract_content_html()

    # Convert content to markdown
    converter = _HTMLToMarkdown()
    converter.feed(content_html)
    markdown_body = converter.get_markdown()
    raw_image_srcs = converter.images

    # Determine slug
    slug = _slugify(page_title) or _slug_from_url(url)

    # Prepare output directories
    raw_dir = output_root / topic / "raw"
    images_dir = raw_dir / "images" / slug
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Download images and rewrite markdown paths
    image_count = 0
    for src in raw_image_srcs:
        abs_src = _resolve_img_url(src, url)
        local_path = _download_image(abs_src, images_dir)
        if local_path:
            image_count += 1
            # Rewrite path in markdown — use relative path from raw/
            rel = local_path.relative_to(raw_dir)
            markdown_body = markdown_body.replace(src, str(rel))

    # Build final document
    clipped = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    frontmatter = _build_frontmatter(page_title, url, clipped, content_type, image_count)
    full_content = frontmatter + "\n\n" + markdown_body + "\n"

    # Save file
    out_file = raw_dir / f"{slug}.md"
    try:
        out_file.write_text(full_content, encoding="utf-8")
    except OSError as e:
        print(f"ERROR: Failed to write {out_file}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Saved: {out_file}", file=sys.stderr)
    if image_count:
        print(f"Downloaded: {image_count} image(s) to {images_dir}", file=sys.stderr)

    return ClipResult(
        title=page_title,
        source_url=url,
        clipped=clipped,
        content_type=content_type,
        markdown=full_content,
        image_count=image_count,
        slug=slug,
    )


# --- CLI ---


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch a URL, convert to markdown, and save to research/{topic}/raw/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --topic llm-patterns --url https://example.com/article
  %(prog)s --topic llm-patterns --url https://example.com/paper --title "Custom Title" --type paper
  %(prog)s --topic agents --url https://example.com/blog-post --type article
        """,
    )
    parser.add_argument("--topic", required=True, help="KB topic name (output goes to research/{topic}/raw/)")
    parser.add_argument("--url", required=True, help="URL to fetch and clip")
    parser.add_argument("--title", default=None, help="Override page title (default: use <title> tag)")
    parser.add_argument(
        "--type",
        default="article",
        choices=["article", "paper", "note", "image", "reference"],
        help="Content type (default: article)",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Root research directory (default: research/ relative to script)",
    )

    args = parser.parse_args()

    # Resolve output root
    if args.output_root:
        output_root = Path(args.output_root)
    else:
        # Default: research/ relative to repo root (script lives in scripts/)
        script_dir = Path(__file__).parent
        output_root = script_dir.parent / "research"

    clip_url(
        topic=args.topic,
        url=args.url,
        title=args.title,
        content_type=args.type,
        output_root=output_root,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
