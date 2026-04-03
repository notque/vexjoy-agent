#!/usr/bin/env python3
"""
FTS5 full-text search over KB wiki content.

Builds and queries a per-topic SQLite FTS5 index from wiki markdown files.
Index files are stored at research/{topic}/.kb-search.db (hidden, per-topic).

Usage:
    kb-search.py index --topic TOPIC
    kb-search.py search --topic TOPIC --query "search terms" [--limit 10]
    kb-search.py search --all --query "search terms" [--limit 10]
    kb-search.py search --topic TOPIC --query "search terms" --json

Exit codes:
    0 = success (results found, or index built)
    1 = error (argument error, DB failure, topic not found)
    2 = no results
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# ─── Constants ────────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_RESEARCH_DIR = _REPO_ROOT / "research"

# Mutable module-level reference, overridden by --output-root CLI flag.
_RESEARCH_DIR = _DEFAULT_RESEARCH_DIR

_DB_FILENAME = ".kb-search.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS wiki_pages (
    id INTEGER PRIMARY KEY,
    topic TEXT NOT NULL,
    path TEXT NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    page_type TEXT,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_wiki_pages_topic_path
    ON wiki_pages (topic, path);

CREATE INDEX IF NOT EXISTS idx_wiki_pages_topic
    ON wiki_pages (topic);

CREATE INDEX IF NOT EXISTS idx_wiki_pages_page_type
    ON wiki_pages (page_type);

CREATE VIRTUAL TABLE IF NOT EXISTS wiki_pages_fts USING fts5(
    title,
    content,
    path,
    content=wiki_pages,
    content_rowid=id,
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS wiki_pages_ai
    AFTER INSERT ON wiki_pages BEGIN
    INSERT INTO wiki_pages_fts(rowid, title, content, path)
    VALUES (new.id, new.title, new.content, new.path);
END;

CREATE TRIGGER IF NOT EXISTS wiki_pages_ad
    AFTER DELETE ON wiki_pages BEGIN
    INSERT INTO wiki_pages_fts(wiki_pages_fts, rowid, title, content, path)
    VALUES ('delete', old.id, old.title, old.content, old.path);
END;

CREATE TRIGGER IF NOT EXISTS wiki_pages_au
    AFTER UPDATE ON wiki_pages BEGIN
    INSERT INTO wiki_pages_fts(wiki_pages_fts, rowid, title, content, path)
    VALUES ('delete', old.id, old.title, old.content, old.path);
    INSERT INTO wiki_pages_fts(rowid, title, content, path)
    VALUES (new.id, new.title, new.content, new.path);
END;
"""


# ─── DB helpers ───────────────────────────────────────────────────────────────


def _db_path(topic_dir: Path) -> Path:
    """Return the hidden DB file path for a topic directory.

    Args:
        topic_dir: Absolute path to the topic directory under research/.

    Returns:
        Path to the .kb-search.db file inside the topic directory.
    """
    return topic_dir / _DB_FILENAME


def _open_db(db_path: Path) -> sqlite3.Connection:
    """Open (and initialize) the SQLite DB at db_path.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        An open sqlite3.Connection with WAL mode and row_factory set.

    Raises:
        SystemExit: If the database cannot be opened or initialized.
    """
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
        conn.commit()
        return conn
    except sqlite3.Error as exc:
        _die(f"Cannot open database at {db_path}: {exc}")


def _die(msg: str, code: int = 1) -> None:
    """Print an error message to stderr and exit.

    Args:
        msg: Error message to display.
        code: Exit code (default 1).
    """
    print(f"[kb-search] ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# ─── Frontmatter parsing ──────────────────────────────────────────────────────

_FM_FENCE = re.compile(r"^---\s*$", re.MULTILINE)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter from a markdown string.

    Splits on the first pair of '---' fences and returns a dict of
    top-level key: value string pairs plus the body after the fence.
    Only handles simple scalar values (strings, unquoted).

    Args:
        text: Full markdown file content.

    Returns:
        Tuple of (frontmatter_dict, body_text). If no frontmatter fence
        is found, returns ({}, text).
    """
    parts = _FM_FENCE.split(text, maxsplit=2)
    if len(parts) < 3 or parts[0].strip():
        return {}, text

    fm_block = parts[1]
    body = parts[2] if len(parts) > 2 else ""

    fm: dict[str, str] = {}
    for line in fm_block.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'")

    return fm, body


# ─── Page type detection ──────────────────────────────────────────────────────


def _page_type(rel_path: str) -> str:
    """Determine the wiki page type from its relative path.

    Args:
        rel_path: Path relative to the wiki/ directory (e.g. 'concepts/foo.md').

    Returns:
        One of 'concept', 'source', 'query', 'index', or 'other'.
    """
    p = rel_path.replace("\\", "/")
    if p == "_index.md" or p.endswith("/_index.md"):
        return "index"
    if "concepts/" in p:
        return "concept"
    if "sources/" in p:
        return "source"
    if "queries/" in p:
        return "query"
    return "other"


# ─── Index command ────────────────────────────────────────────────────────────


def _index_topic(topic: str) -> int:
    """Build or rebuild the FTS5 index for a single topic.

    Reads all .md files under research/{topic}/wiki/, parses frontmatter,
    and upserts rows into wiki_pages (triggering FTS5 sync via triggers).

    Args:
        topic: Topic slug (directory name under research/).

    Returns:
        Number of pages indexed.

    Raises:
        SystemExit: If the topic directory does not exist.
    """
    topic_dir = _RESEARCH_DIR / topic
    if not topic_dir.is_dir():
        _die(f"Topic directory not found: {topic_dir}")

    wiki_dir = topic_dir / "wiki"
    if not wiki_dir.is_dir():
        _die(f"Wiki directory not found: {wiki_dir}. Run kb-compile first.")

    db_path = _db_path(topic_dir)
    conn = _open_db(db_path)

    now = datetime.now(tz=timezone.utc).isoformat()
    count = 0

    try:
        # Clear existing pages for this topic so stale entries are removed.
        conn.execute("DELETE FROM wiki_pages WHERE topic = ?", (topic,))

        md_files = sorted(wiki_dir.rglob("*.md"))
        for md_file in md_files:
            rel = md_file.relative_to(wiki_dir).as_posix()
            text = md_file.read_text(encoding="utf-8", errors="replace")
            fm, body = _parse_frontmatter(text)

            title = fm.get("title") or fm.get("name") or md_file.stem
            ptype = _page_type(rel)
            # Store full content (frontmatter + body) for FTS; snippet may show either.
            full_content = text

            conn.execute(
                """
                INSERT INTO wiki_pages (topic, path, title, content, page_type, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (topic, rel, title, full_content, ptype, now),
            )
            count += 1

        # Rebuild FTS index from current content table state.
        conn.execute("INSERT INTO wiki_pages_fts(wiki_pages_fts) VALUES('rebuild')")
        conn.commit()
    except sqlite3.Error as exc:
        conn.close()
        _die(f"Index failed for topic '{topic}': {exc}")
    finally:
        conn.close()

    return count


def cmd_index(args: argparse.Namespace) -> None:
    """Handle the 'index' subcommand.

    Args:
        args: Parsed CLI arguments with .topic attribute.
    """
    topic = args.topic
    count = _index_topic(topic)
    topic_dir = _RESEARCH_DIR / topic
    db_path = _db_path(topic_dir)
    print(f"Indexed {count} pages for topic '{topic}' → {db_path}")


# ─── Search helpers ───────────────────────────────────────────────────────────


def _sanitize_fts_query(query: str) -> str:
    """Strip FTS5 operators from query terms to prevent injection.

    Removes FTS5 special characters and keyword operators (NOT, AND, OR,
    NEAR) that could alter query semantics unexpectedly.

    Args:
        query: Raw user query string.

    Returns:
        Sanitized query safe for FTS5 MATCH.
    """
    # Remove special FTS5 chars
    cleaned = re.sub(r'["\(\)\*:\-\^\+]', "", query)
    # Remove FTS5 keyword operators (case-insensitive, whole word)
    cleaned = re.sub(r"\b(NOT|NEAR|AND|OR)\b", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _search_db(
    conn: sqlite3.Connection,
    topic: str,
    query: str,
    limit: int,
) -> list[dict]:
    """Run an FTS5 search against a single open DB connection.

    Uses FTS5 highlight() for snippet extraction and rank for BM25 scoring.

    Args:
        conn: Open sqlite3.Connection to a .kb-search.db file.
        topic: Topic slug for display purposes.
        query: Sanitized FTS5 query string.
        limit: Maximum number of results to return.

    Returns:
        List of result dicts with keys: topic, path, title, page_type,
        snippet, rank.
    """
    sql = """
        SELECT
            p.topic,
            p.path,
            p.title,
            p.page_type,
            highlight(wiki_pages_fts, 1, '[', ']') AS snippet,
            wiki_pages_fts.rank AS rank
        FROM wiki_pages_fts
        JOIN wiki_pages p ON p.id = wiki_pages_fts.rowid
        WHERE wiki_pages_fts MATCH ?
          AND p.topic = ?
        ORDER BY rank
        LIMIT ?
    """
    try:
        rows = conn.execute(sql, (query, topic, limit)).fetchall()
    except sqlite3.OperationalError:
        # FTS index may not exist yet (never indexed)
        return []

    results = []
    for row in rows:
        # Trim snippet: take first 200 chars of match context
        raw_snippet = row["snippet"] or ""
        # Extract the window around the first highlight marker
        snippet = _trim_snippet(raw_snippet, max_len=200)
        results.append(
            {
                "topic": row["topic"],
                "path": row["path"],
                "title": row["title"] or row["path"],
                "page_type": row["page_type"] or "other",
                "snippet": snippet,
                "rank": round(float(row["rank"]), 4),
            }
        )
    return results


def _trim_snippet(text: str, max_len: int = 200) -> str:
    """Trim snippet text to max_len, preferring content around highlight markers.

    The highlight() function returns full content with [highlighted] markers.
    We extract a window centered on the first marker.

    Args:
        text: Raw text from FTS5 highlight() with '[' / ']' markers.
        max_len: Maximum characters in output.

    Returns:
        Trimmed snippet string, possibly with leading '...' if truncated.
    """
    # Find first highlight marker
    marker_pos = text.find("[")
    if marker_pos == -1:
        # No match found — just return the start
        return text[:max_len].strip()

    # Center the window on the marker
    half = max_len // 2
    start = max(0, marker_pos - half)
    end = min(len(text), start + max_len)
    prefix = "..." if start > 0 else ""
    return prefix + text[start:end].strip()


# ─── Search command ───────────────────────────────────────────────────────────


def cmd_search(args: argparse.Namespace) -> None:
    """Handle the 'search' subcommand.

    Searches one topic (--topic) or all indexed topics (--all).
    Outputs human-readable results or JSON with --json.

    Args:
        args: Parsed CLI arguments.

    Raises:
        SystemExit: With code 1 on error, code 2 on no results.
    """
    raw_query = args.query or ""
    if not raw_query.strip():
        _die("--query cannot be empty")

    query = _sanitize_fts_query(raw_query)
    if not query:
        _die("Query contained only FTS5 operators — provide search terms")

    limit = getattr(args, "limit", 10)
    emit_json = getattr(args, "json", False)
    search_all = getattr(args, "all", False)

    # Collect (topic, db_path) pairs to search
    targets: list[tuple[str, Path]] = []

    if search_all:
        if not _RESEARCH_DIR.is_dir():
            _die(f"research/ directory not found at {_RESEARCH_DIR}")
        for topic_dir in sorted(_RESEARCH_DIR.iterdir()):
            if not topic_dir.is_dir():
                continue
            db_path = _db_path(topic_dir)
            if db_path.is_file():
                targets.append((topic_dir.name, db_path))
        if not targets:
            _die("No indexed topics found under research/. Run 'kb-search.py index --topic TOPIC' first.")
    else:
        topic = args.topic
        if not topic:
            _die("Provide --topic TOPIC or --all")
        topic_dir = _RESEARCH_DIR / topic
        if not topic_dir.is_dir():
            _die(f"Topic directory not found: {topic_dir}")
        db_path = _db_path(topic_dir)
        if not db_path.is_file():
            _die(f"No index found for topic '{topic}'. Run: kb-search.py index --topic {topic}")
        targets.append((topic, db_path))

    all_results: list[dict] = []
    for topic, db_path in targets:
        conn = _open_db(db_path)
        try:
            results = _search_db(conn, topic, query, limit)
            all_results.extend(results)
        finally:
            conn.close()

    # Sort combined results by rank (lower = better in FTS5 BM25)
    all_results.sort(key=lambda r: r["rank"])
    if limit:
        all_results = all_results[:limit]

    if not all_results:
        if emit_json:
            print(json.dumps({"query": raw_query, "results": []}, indent=2))
        else:
            print(f"No results for: {raw_query!r}")
        sys.exit(2)

    if emit_json:
        print(json.dumps({"query": raw_query, "results": all_results}, indent=2))
        sys.exit(0)

    # Human-readable output
    print(f"Results for: {raw_query!r}  ({len(all_results)} found)\n")
    for r in all_results:
        print(f"[{r['rank']:+.4f}] {r['topic']}/wiki/{r['path']}")
        print(f"  Title: {r['title']}  ({r['page_type']})")
        if r["snippet"]:
            print(f"  ...{r['snippet']}...")
        print()

    sys.exit(0)


# ─── CLI ──────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser.

    Returns:
        Configured argparse.ArgumentParser with index and search subcommands.
    """
    parser = argparse.ArgumentParser(
        prog="kb-search.py",
        description="FTS5 full-text search over KB wiki content.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # index subcommand
    idx = sub.add_parser("index", help="Build or rebuild FTS5 index for a topic.")
    idx.add_argument("--topic", required=True, help="Topic slug under research/")
    idx.add_argument(
        "--output-root",
        default=None,
        help="Root research directory (default: research/ relative to repo root)",
    )

    # search subcommand
    srch = sub.add_parser("search", help="Search indexed wiki content.")
    topic_group = srch.add_mutually_exclusive_group(required=True)
    topic_group.add_argument("--topic", help="Topic slug to search")
    topic_group.add_argument("--all", action="store_true", help="Search across all indexed topics")
    srch.add_argument("--query", required=True, help="Search terms")
    srch.add_argument("--limit", type=int, default=10, help="Maximum results (default: 10)")
    srch.add_argument("--json", action="store_true", help="Emit JSON output")
    srch.add_argument(
        "--output-root",
        default=None,
        help="Root research directory (default: research/ relative to repo root)",
    )

    return parser


def main() -> None:
    """Entry point for kb-search.py CLI."""
    global _RESEARCH_DIR
    parser = _build_parser()
    args = parser.parse_args()

    if getattr(args, "output_root", None):
        _RESEARCH_DIR = Path(args.output_root)

    if args.command == "index":
        cmd_index(args)
    elif args.command == "search":
        cmd_search(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
