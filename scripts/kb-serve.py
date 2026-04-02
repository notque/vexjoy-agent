#!/usr/bin/env python3
"""
Serve a KB topic's wiki as a browsable site.

Uses Python's built-in http.server to serve the wiki markdown files as HTML.
Generates a Wikipedia-lite UI with sidebar navigation and on-the-fly markdown
rendering using stdlib only.

Usage:
    kb-serve.py --topic TOPIC
    kb-serve.py --topic TOPIC --port 8400
    kb-serve.py --topic TOPIC --build-only
    kb-serve.py --topic TOPIC --stop

Exit codes:
    0 = success
    1 = error
"""

from __future__ import annotations

import argparse
import html
import http.server
import os
import re
import signal
import socket
import sys
import threading
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

# --- Constants ---

_DEFAULT_PORT = 8400
_PID_FILE_TEMPLATE = "/tmp/kb-serve-{topic}.pid"
_REPO_ROOT = Path(__file__).resolve().parent.parent


# --- HTML Templates ---

_PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — {topic} KB</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                   "Helvetica Neue", Arial, sans-serif;
      font-size: 16px;
      line-height: 1.65;
      color: #202122;
      background: #f8f9fa;
    }}

    /* Layout */
    #layout {{
      display: flex;
      min-height: 100vh;
    }}

    /* Sidebar */
    #sidebar {{
      width: 230px;
      flex-shrink: 0;
      background: #fff;
      border-right: 1px solid #d3d3d3;
      padding: 16px 0;
      position: sticky;
      top: 0;
      height: 100vh;
      overflow-y: auto;
    }}

    #sidebar h2 {{
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #54595d;
      margin: 0 16px 8px;
      padding-bottom: 6px;
      border-bottom: 1px solid #eaecf0;
    }}

    #sidebar ul {{
      list-style: none;
      margin: 0;
      padding: 0;
    }}

    #sidebar ul li a {{
      display: block;
      padding: 5px 16px;
      color: #0645ad;
      text-decoration: none;
      font-size: 14px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    #sidebar ul li a:hover,
    #sidebar ul li a.active {{
      background: #eaf3fb;
      color: #0b57d0;
    }}

    #sidebar ul li a.active {{
      font-weight: 600;
      border-left: 3px solid #3ea7e9;
      padding-left: 13px;
    }}

    /* Main content */
    #main {{
      flex: 1;
      padding: 24px 40px 48px;
      max-width: 860px;
      min-width: 0;
    }}

    /* Breadcrumb */
    .breadcrumb {{
      font-size: 13px;
      color: #54595d;
      margin-bottom: 20px;
    }}

    .breadcrumb a {{
      color: #0645ad;
      text-decoration: none;
    }}

    .breadcrumb a:hover {{ text-decoration: underline; }}
    .breadcrumb span {{ margin: 0 6px; color: #a2a9b1; }}

    /* Article */
    h1 {{ font-size: 1.9em; font-weight: 700; border-bottom: 1px solid #a2a9b1;
          padding-bottom: 4px; margin-top: 0; }}
    h2 {{ font-size: 1.4em; font-weight: 600; border-bottom: 1px solid #eaecf0;
          padding-bottom: 2px; margin-top: 1.5em; }}
    h3 {{ font-size: 1.15em; font-weight: 600; margin-top: 1.2em; }}
    h4 {{ font-size: 1em; font-weight: 600; margin-top: 1em; }}

    p {{ margin: 0.6em 0; }}

    a {{ color: #0645ad; }}
    a:hover {{ text-decoration: underline; }}

    /* Code */
    code {{
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      font-size: 0.88em;
      background: #f3f4f6;
      border: 1px solid #d1d5da;
      border-radius: 3px;
      padding: 1px 5px;
    }}

    pre {{
      background: #1e2029;
      color: #cdd6f4;
      border-radius: 6px;
      padding: 16px 20px;
      overflow-x: auto;
      line-height: 1.5;
      margin: 1em 0;
    }}

    pre code {{
      background: none;
      border: none;
      padding: 0;
      color: inherit;
      font-size: 0.875em;
    }}

    /* Blockquote */
    blockquote {{
      border-left: 4px solid #3ea7e9;
      margin: 1em 0;
      padding: 4px 16px;
      color: #444;
      background: #f0f6fc;
      border-radius: 0 4px 4px 0;
    }}

    /* Tables */
    table {{
      border-collapse: collapse;
      width: 100%;
      margin: 1em 0;
      font-size: 0.93em;
    }}

    th, td {{
      border: 1px solid #d3d3d3;
      padding: 6px 12px;
      text-align: left;
    }}

    th {{
      background: #eaecf0;
      font-weight: 600;
    }}

    tr:nth-child(even) {{ background: #f8f9fa; }}

    /* Lists */
    ul, ol {{ padding-left: 1.6em; margin: 0.4em 0; }}
    li {{ margin: 0.15em 0; }}

    /* HR */
    hr {{ border: none; border-top: 1px solid #d3d3d3; margin: 1.5em 0; }}

    /* Responsive */
    @media (max-width: 700px) {{
      #sidebar {{ display: none; }}
      #main {{ padding: 16px; }}
    }}
  </style>
</head>
<body>
  <div id="layout">
    <nav id="sidebar">
      <h2>{topic} KB</h2>
      <ul>
{nav_items}
      </ul>
    </nav>
    <main id="main">
      <div class="breadcrumb">
        <a href="/">Home</a><span>&#x203A;</span>{breadcrumb}
      </div>
      <article>
        {content}
      </article>
    </main>
  </div>
</body>
</html>
"""

_INDEX_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{topic} Knowledge Base</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                   "Helvetica Neue", Arial, sans-serif;
      font-size: 16px; line-height: 1.65; color: #202122; background: #f8f9fa;
      margin: 0; padding: 40px;
    }}
    .container {{ max-width: 800px; margin: 0 auto; background: #fff;
                  padding: 32px 40px; border-radius: 8px;
                  box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    h1 {{ font-size: 2em; border-bottom: 1px solid #a2a9b1;
           padding-bottom: 8px; margin-top: 0; }}
    .subtitle {{ color: #54595d; margin-bottom: 28px; }}
    .article-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
                     gap: 12px; }}
    .article-card {{
      border: 1px solid #d3d3d3; border-radius: 6px; padding: 14px 16px;
      background: #fff; transition: box-shadow 0.15s;
    }}
    .article-card:hover {{ box-shadow: 0 2px 8px rgba(0,0,0,0.12); }}
    .article-card a {{ color: #0645ad; text-decoration: none; font-weight: 600; }}
    .article-card a:hover {{ text-decoration: underline; }}
    .article-card .size {{ font-size: 12px; color: #72777d; margin-top: 4px; }}
    .empty {{ color: #54595d; font-style: italic; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>{topic} Knowledge Base</h1>
    <p class="subtitle">{article_count} article(s) &mdash; served from <code>{wiki_dir}</code></p>
    <div class="article-grid">
{cards}
    </div>
  </div>
</body>
</html>
"""


# --- Markdown to HTML renderer ---


def _md_to_html(text: str) -> str:
    """Convert markdown text to HTML using stdlib only.

    Handles: headings, bold, italic, inline code, code fences, blockquotes,
    unordered/ordered lists, horizontal rules, tables, links, images, paragraphs.

    Args:
        text: Markdown source text.

    Returns:
        HTML string.
    """
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    in_list: str | None = None  # "ul" or "ol"
    in_table = False

    def flush_list() -> None:
        nonlocal in_list
        if in_list:
            out.append(f"</{in_list}>")
            in_list = None

    def flush_table() -> None:
        nonlocal in_table
        if in_table:
            out.append("</tbody></table>")
            in_table = False

    def inline(s: str) -> str:
        """Apply inline formatting to a string."""
        # Escape HTML first, then restore intentional tags
        s = html.escape(s)
        # Inline code (backtick) — preserve before other patterns
        s = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", s)
        # Bold+italic
        s = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", s)
        # Bold
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"__(.+?)__", r"<strong>\1</strong>", s)
        # Italic
        s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
        s = re.sub(r"_(.+?)_", r"<em>\1</em>", s)
        # Image (before links)
        s = re.sub(
            r"!\[([^\]]*)\]\(([^)]+)\)",
            lambda m: f'<img src="{m.group(2)}" alt="{m.group(1)}" style="max-width:100%">',
            s,
        )
        # Links
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', s)
        # Strikethrough
        s = re.sub(r"~~(.+?)~~", r"<del>\1</del>", s)
        return s

    while i < len(lines):
        line = lines[i]

        # --- Fenced code block ---
        fence_m = re.match(r"^(```|~~~)\s*(\w*)", line)
        if fence_m:
            flush_list()
            flush_table()
            fence_char = fence_m.group(1)
            lang = fence_m.group(2)
            lang_attr = f' class="lang-{lang}"' if lang else ""
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith(fence_char):
                code_lines.append(html.escape(lines[i]))
                i += 1
            code_body = "\n".join(code_lines)
            out.append(f"<pre><code{lang_attr}>{code_body}</code></pre>")
            i += 1
            continue

        # --- Horizontal rule ---
        if re.match(r"^(\*{3,}|-{3,}|_{3,})\s*$", line):
            flush_list()
            flush_table()
            out.append("<hr>")
            i += 1
            continue

        # --- Headings ---
        heading_m = re.match(r"^(#{1,6})\s+(.+)", line)
        if heading_m:
            flush_list()
            flush_table()
            level = len(heading_m.group(1))
            content = inline(heading_m.group(2))
            slug = re.sub(r"[^\w-]", "-", heading_m.group(2).lower()).strip("-")
            out.append(f'<h{level} id="{slug}">{content}</h{level}>')
            i += 1
            continue

        # --- Blockquote ---
        if line.startswith(">"):
            flush_list()
            flush_table()
            bq_lines: list[str] = []
            while i < len(lines) and lines[i].startswith(">"):
                bq_lines.append(inline(lines[i][1:].lstrip()))
                i += 1
            out.append("<blockquote><p>" + " ".join(bq_lines) + "</p></blockquote>")
            continue

        # --- Unordered list ---
        ul_m = re.match(r"^(\s*)[-*+]\s+(.+)", line)
        if ul_m:
            flush_table()
            if in_list != "ul":
                flush_list()
                out.append("<ul>")
                in_list = "ul"
            out.append(f"  <li>{inline(ul_m.group(2))}</li>")
            i += 1
            continue

        # --- Ordered list ---
        ol_m = re.match(r"^(\s*)\d+\.\s+(.+)", line)
        if ol_m:
            flush_table()
            if in_list != "ol":
                flush_list()
                out.append("<ol>")
                in_list = "ol"
            out.append(f"  <li>{inline(ol_m.group(2))}</li>")
            i += 1
            continue

        # --- Table ---
        if "|" in line and re.match(r"\s*\|", line):
            flush_list()
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            # Peek ahead for separator row
            if i + 1 < len(lines) and re.match(r"[\s|:-]+$", lines[i + 1]):
                # Header row
                if not in_table:
                    out.append("<table><thead><tr>")
                    for c in cells:
                        out.append(f"  <th>{inline(c)}</th>")
                    out.append("</tr></thead><tbody>")
                    in_table = True
                i += 2  # skip separator
                continue
            elif in_table:
                out.append("  <tr>")
                for c in cells:
                    out.append(f"    <td>{inline(c)}</td>")
                out.append("  </tr>")
                i += 1
                continue
            else:
                # Table row without header — treat as paragraph
                flush_table()

        # --- Empty line ---
        if not line.strip():
            flush_list()
            flush_table()
            i += 1
            continue

        # --- Paragraph ---
        flush_list()
        flush_table()
        para_lines: list[str] = []
        while i < len(lines) and lines[i].strip():
            # Stop if next line looks like a block element
            if re.match(r"^(#{1,6} |```|~~~|>|[-*+] |\d+\. |[|])", lines[i]):
                break
            para_lines.append(inline(lines[i]))
            i += 1
        if para_lines:
            out.append("<p>" + " ".join(para_lines) + "</p>")

    flush_list()
    flush_table()
    return "\n".join(out)


# --- Article discovery ---


@dataclass
class Article:
    """A wiki article discovered from the wiki directory."""

    path: Path
    slug: str
    title: str
    size_bytes: int = 0

    @classmethod
    def from_path(cls, path: Path, wiki_dir: Path) -> "Article":
        """Build an Article from a markdown file path.

        Args:
            path: Absolute path to the .md file.
            wiki_dir: Root wiki directory for computing the slug.

        Returns:
            Article instance.
        """
        rel = path.relative_to(wiki_dir)
        slug = str(rel).replace("\\", "/")
        if slug.endswith(".md"):
            slug = slug[:-3]

        # Derive a human-readable title
        raw_name = path.stem
        if raw_name.startswith("_"):
            raw_name = raw_name[1:]
        title = raw_name.replace("-", " ").replace("_", " ").title()

        try:
            size_bytes = path.stat().st_size
        except OSError:
            size_bytes = 0

        return cls(path=path, slug=slug, title=title, size_bytes=size_bytes)


def _discover_articles(wiki_dir: Path) -> list[Article]:
    """Discover all markdown files in the wiki directory, sorted by name.

    Args:
        wiki_dir: Path to the wiki directory.

    Returns:
        Sorted list of Article instances.
    """
    if not wiki_dir.is_dir():
        return []
    articles = [Article.from_path(p, wiki_dir) for p in sorted(wiki_dir.rglob("*.md"))]
    return articles


# --- HTML generation ---


def _build_nav_items(articles: list[Article], active_slug: str = "") -> str:
    """Build sidebar nav <li> items.

    Args:
        articles: All discovered articles.
        active_slug: The slug of the currently-active article.

    Returns:
        HTML string of <li> elements.
    """
    items: list[str] = []
    for article in articles:
        css_class = ' class="active"' if article.slug == active_slug else ""
        items.append(f'        <li><a href="/{article.slug}.html"{css_class}>{html.escape(article.title)}</a></li>')
    return "\n".join(items)


def _build_article_page(article: Article, articles: list[Article], topic: str) -> str:
    """Render a full article page.

    Args:
        article: The article to render.
        articles: All articles (for sidebar nav).
        topic: Topic name for page title.

    Returns:
        Full HTML page as a string.
    """
    md_text = article.path.read_text(encoding="utf-8", errors="replace")
    content_html = _md_to_html(md_text)
    nav_items = _build_nav_items(articles, active_slug=article.slug)

    breadcrumb = html.escape(article.title)

    return _PAGE_TEMPLATE.format(
        title=article.title,
        topic=topic,
        nav_items=nav_items,
        breadcrumb=breadcrumb,
        content=content_html,
    )


def _build_index_page(articles: list[Article], topic: str, wiki_dir: Path) -> str:
    """Build the root index listing page.

    Args:
        articles: All discovered articles.
        topic: Topic name.
        wiki_dir: Wiki directory path for display.

    Returns:
        Full HTML page as a string.
    """
    if not articles:
        cards = '      <p class="empty">No markdown articles found in this wiki.</p>'
    else:
        card_items: list[str] = []
        for article in articles:
            kb_label = f"{article.size_bytes:,} bytes" if article.size_bytes else "empty"
            card_items.append(
                f'      <div class="article-card">'
                f'<a href="/{article.slug}.html">{html.escape(article.title)}</a>'
                f'<div class="size">{kb_label}</div>'
                f"</div>"
            )
        cards = "\n".join(card_items)

    return _INDEX_TEMPLATE.format(
        topic=topic,
        article_count=len(articles),
        wiki_dir=str(wiki_dir),
        cards=cards,
    )


# --- Static site builder ---


def build_static_site(topic: str, wiki_dir: Path, site_dir: Path) -> int:
    """Generate static HTML files in site_dir from wiki_dir.

    Args:
        topic: KB topic name.
        wiki_dir: Source wiki markdown directory.
        site_dir: Output directory for generated HTML.

    Returns:
        0 on success, 1 on error.
    """
    if not wiki_dir.is_dir():
        print(f"ERROR: wiki directory not found: {wiki_dir}", file=sys.stderr)
        return 1

    articles = _discover_articles(wiki_dir)
    site_dir.mkdir(parents=True, exist_ok=True)

    # Write index
    index_html = _build_index_page(articles, topic, wiki_dir)
    (site_dir / "index.html").write_text(index_html, encoding="utf-8")
    print(f"  wrote: {site_dir / 'index.html'}")

    # Write article pages
    for article in articles:
        # Mirror subdirectory structure
        rel_slug = article.slug
        out_path = site_dir / f"{rel_slug}.html"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        page_html = _build_article_page(article, articles, topic)
        out_path.write_text(page_html, encoding="utf-8")
        print(f"  wrote: {out_path}")

    print(f"\nBuild complete: {len(articles)} article(s) → {site_dir}")
    return 0


# --- HTTP request handler ---


@dataclass
class _KBHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler that serves KB wiki pages on-the-fly."""

    # Set at class level before instantiation
    wiki_dir: Path = field(default_factory=Path)
    articles: list[Article] = field(default_factory=list)
    topic: str = ""

    # Suppress default request logging to stderr (we handle it ourselves)
    def log_message(self, fmt: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        """Handle GET requests."""
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)

        if path in ("/", "/index.html", ""):
            self._serve_index()
        elif path.endswith(".html"):
            slug = path.lstrip("/")[:-5]  # strip leading / and .html
            self._serve_article(slug)
        else:
            self._send_404(path)

    def _serve_index(self) -> None:
        """Serve the topic index page."""
        body = _build_index_page(self.articles, self.topic, self.wiki_dir)
        self._send_html(body)

    def _serve_article(self, slug: str) -> None:
        """Serve a single article by slug.

        Args:
            slug: Article slug (path relative to wiki_dir without .md extension).
        """
        matching = [a for a in self.articles if a.slug == slug]
        if not matching:
            self._send_404(slug)
            return

        article = matching[0]
        body = _build_article_page(article, self.articles, self.topic)
        self._send_html(body)

    def _send_html(self, body: str) -> None:
        """Send an HTML response.

        Args:
            body: Full HTML document string.
        """
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_404(self, path: str) -> None:
        """Send a 404 response.

        Args:
            path: The path that was not found.
        """
        body = f"<html><body><h1>404 Not Found</h1><p>{html.escape(path)}</p></body></html>"
        encoded = body.encode("utf-8")
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _make_handler(wiki_dir: Path, articles: list[Article], topic: str) -> type:
    """Create a handler class with the wiki context baked in.

    Args:
        wiki_dir: Wiki directory path.
        articles: Pre-discovered articles list.
        topic: Topic name.

    Returns:
        A BaseHTTPRequestHandler subclass.
    """

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, _fmt: str, *_args: object) -> None:
            # Minimal one-line request log
            print(f"  {self.address_string()} {self.requestline}", flush=True)

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = urllib.parse.unquote(parsed.path)

            if path in ("/", "/index.html", ""):
                self._serve_index()
            elif path.endswith(".html"):
                slug = path.lstrip("/")[:-5]
                self._serve_article(slug)
            else:
                self._send_404(path)

        def _serve_index(self) -> None:
            body = _build_index_page(articles, topic, wiki_dir)
            self._send_html(body)

        def _serve_article(self, slug: str) -> None:
            matching = [a for a in articles if a.slug == slug]
            if not matching:
                self._send_404(slug)
                return
            article = matching[0]
            body = _build_article_page(article, articles, topic)
            self._send_html(body)

        def _send_html(self, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_404(self, path: str) -> None:
            body = f"<html><body><h1>404 Not Found</h1><p>{html.escape(path)}</p></body></html>"
            encoded = body.encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return _Handler


# --- Server lifecycle ---


def _pid_file(topic: str) -> Path:
    """Return the PID file path for a topic.

    Args:
        topic: KB topic name.

    Returns:
        Path to the PID file.
    """
    return Path(_PID_FILE_TEMPLATE.format(topic=topic))


def _stop_server(topic: str) -> int:
    """Stop a running kb-serve instance for the given topic.

    Args:
        topic: KB topic name.

    Returns:
        0 on success (or no server running), 1 on error.
    """
    pid_file = _pid_file(topic)
    if not pid_file.exists():
        print(f"No running server found for topic '{topic}' (no PID file at {pid_file})")
        return 0

    try:
        pid = int(pid_file.read_text().strip())
    except (ValueError, OSError) as e:
        print(f"ERROR: Cannot read PID file: {e}", file=sys.stderr)
        return 1

    try:
        os.kill(pid, signal.SIGTERM)
        pid_file.unlink(missing_ok=True)
        print(f"Stopped kb-serve for '{topic}' (PID {pid})")
        return 0
    except ProcessLookupError:
        print(f"Process {pid} not found — server may have already stopped")
        pid_file.unlink(missing_ok=True)
        return 0
    except OSError as e:
        print(f"ERROR: Cannot stop PID {pid}: {e}", file=sys.stderr)
        return 1


def _start_server(topic: str, port: int, wiki_dir: Path) -> int:
    """Start the HTTP server and block until interrupted.

    Args:
        topic: KB topic name.
        port: TCP port to bind.
        wiki_dir: Wiki directory to serve.

    Returns:
        0 on clean exit, 1 on error.
    """
    if not wiki_dir.is_dir():
        print(f"ERROR: wiki directory not found: {wiki_dir}", file=sys.stderr)
        print(f"  Expected: {wiki_dir}", file=sys.stderr)
        print(f"  Run `kb-init.py --topic {topic}` first to scaffold the topic.", file=sys.stderr)
        return 1

    articles = _discover_articles(wiki_dir)

    try:
        server = http.server.HTTPServer(("localhost", port), _make_handler(wiki_dir, articles, topic))
    except OSError as e:
        print(f"ERROR: Cannot bind to port {port}: {e}", file=sys.stderr)
        return 1

    # Write PID file
    pid_file = _pid_file(topic)
    pid_file.write_text(str(os.getpid()))

    hostname = socket.gethostname()

    print(f"KB Viewer — topic: {topic}")
    print(f"  Wiki:    {wiki_dir}")
    print(f"  Articles: {len(articles)}")
    print(f"  URL:     http://localhost:{port}/")
    print(f"")
    print(f"  SSH tunnel (if remote):")
    print(f"    ssh -L {port}:localhost:{port} {hostname}")
    print(f"")
    print(f"  Press Ctrl+C to stop")
    print(f"", flush=True)

    def _cleanup(signum: int, frame: object) -> None:
        pid_file.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _cleanup)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        pid_file.unlink(missing_ok=True)
        server.server_close()

    return 0


# --- CLI ---


def main() -> int:
    """CLI entry point.

    Returns:
        Exit code: 0=success, 1=error.
    """
    parser = argparse.ArgumentParser(
        description="Serve a KB topic wiki as a browsable HTML site",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --topic mytopic
  %(prog)s --topic mytopic --port 8401
  %(prog)s --topic mytopic --build-only
  %(prog)s --topic mytopic --stop
        """,
    )

    parser.add_argument("--topic", required=True, help="KB topic name (matches research/{topic}/)")
    parser.add_argument("--port", type=int, default=_DEFAULT_PORT, help=f"Port to serve on (default: {_DEFAULT_PORT})")
    parser.add_argument(
        "--build-only", action="store_true", help="Generate static HTML in research/{topic}/site/ and exit"
    )
    parser.add_argument("--stop", action="store_true", help="Stop a running kb-serve for this topic")

    args = parser.parse_args()

    topic: str = args.topic
    wiki_dir = _REPO_ROOT / "research" / topic / "wiki"
    site_dir = _REPO_ROOT / "research" / topic / "site"

    if args.stop:
        return _stop_server(topic)

    if args.build_only:
        print(f"Building static site for topic '{topic}'...")
        return build_static_site(topic, wiki_dir, site_dir)

    return _start_server(topic, args.port, wiki_dir)


if __name__ == "__main__":
    sys.exit(main())
