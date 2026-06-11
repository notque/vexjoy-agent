#!/usr/bin/env python3
"""Render an HTML artifact listing the user's open GitHub issues.

Sources data via `gh search issues --involves @me` (assigned + mentioned +
review-requested). For each issue, fetches up to 20 comments via `gh issue
view` and truncates each comment body to ~200 chars for an at-a-glance
discussion summary. No LLM in the loop — pure deterministic rendering.

The output substitutes {{TITLE}}, {{GENERATED_AT}}, {{ISSUES_JSON}} into the
saved template at templates/saved/github-issues.html.

Usage:
    python3 scripts/render-github-issues.py
    python3 scripts/render-github-issues.py --limit 100 --out /tmp/issues.html
    python3 scripts/render-github-issues.py --dry-run
    python3 scripts/render-github-issues.py --no-discussion  # skip per-issue gh issue view

Exit codes:
    0: rendered successfully
    1: gh CLI failed (auth, rate-limit, etc.)
    2: template missing
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = SKILL_DIR / "templates" / "saved" / "github-issues.html"

COMMENT_TRUNC = 200  # chars per comment body
COMMENT_MAX = 20  # comments per issue
GH_HOST = "github.com"  # disambiguate from SAP enterprise host


def run_gh(args: list[str]) -> str:
    """Run gh with GH_HOST=github.com pinned. Return stdout, raise on failure."""
    env = os.environ.copy()
    env["GH_HOST"] = GH_HOST
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SystemExit(f"gh CLI not found: {exc}") from exc
    if result.returncode != 0:
        sys.stderr.write(f"gh {' '.join(args)} failed:\n{result.stderr}\n")
        raise SystemExit(1)
    return result.stdout


def fetch_issues(limit: int) -> list[dict]:
    """Fetch open issues involving @me from github.com."""
    raw = run_gh(
        [
            "search",
            "issues",
            "--involves",
            "@me",
            "--state",
            "open",
            "--json",
            "number,title,url,repository,createdAt,updatedAt,commentsCount,author,state,labels",
            "--limit",
            str(limit),
        ]
    )
    return json.loads(raw or "[]")


def fetch_comments(repo_nwo: str, number: int) -> list[dict]:
    """Fetch comments for one issue. Returns [] on any error (best-effort)."""
    try:
        raw = run_gh(
            [
                "issue",
                "view",
                str(number),
                "--repo",
                repo_nwo,
                "--json",
                "comments",
            ]
        )
    except SystemExit:
        return []
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return []
    return data.get("comments", []) or []


def truncate(s: str, n: int) -> str:
    if not s:
        return ""
    s = s.strip()
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "…"


def shape_issue(issue: dict, comments: list[dict]) -> dict:
    """Reduce gh JSON to the minimal shape the template renders."""
    repo = issue.get("repository", {}) or {}
    repo_nwo = repo.get("nameWithOwner") or repo.get("name") or ""
    author = issue.get("author") or {}
    discussion = []
    for c in comments[:COMMENT_MAX]:
        c_author = c.get("author") or {}
        discussion.append(
            {
                "author": c_author.get("login") or "unknown",
                "authorAvatar": c_author.get("avatarUrl") or "",
                "createdAt": c.get("createdAt") or "",
                "summary": truncate(c.get("body") or "", COMMENT_TRUNC),
            }
        )
    return {
        "number": issue.get("number"),
        "title": issue.get("title") or "",
        "url": issue.get("url") or "",
        "repo": repo_nwo,
        "state": issue.get("state") or "open",
        "createdAt": issue.get("createdAt") or "",
        "updatedAt": issue.get("updatedAt") or "",
        "commentsCount": issue.get("commentsCount") or 0,
        "author": author.get("login") or "unknown",
        "authorAvatar": author.get("avatarUrl") or "",
        "labels": [{"name": l.get("name") or "", "color": l.get("color") or ""} for l in (issue.get("labels") or [])],
        "discussion": discussion,
    }


def render(issues: list[dict], title: str, generated_at: str) -> str:
    """Substitute placeholder tokens into the saved template.

    The template ships with a sample dataset inside
    `<script id="issues-data" type="application/json">…</script>` so it opens
    standalone for testing. The renderer replaces that script tag's content
    with the live JSON.
    """
    if not TEMPLATE_PATH.exists():
        sys.stderr.write(f"Template not found at {TEMPLATE_PATH}\n")
        raise SystemExit(2)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    # JSON-encode so the data lands inside <script type="application/json">.
    # Escape </ to neutralize a stray closing tag inside string content.
    payload = json.dumps(issues, ensure_ascii=False).replace("</", "<\\/")
    import re as _re

    rendered, n = _re.subn(
        r'(<script id="issues-data" type="application/json">)(.*?)(</script>)',
        lambda m: m.group(1) + "\n" + payload + "\n" + m.group(3),
        template,
        count=1,
        flags=_re.DOTALL,
    )
    if n == 0:
        sys.stderr.write('Template missing <script id="issues-data"> tag.\n')
        raise SystemExit(2)
    return rendered.replace("{{TITLE}}", title).replace("{{GENERATED_AT}}", generated_at)


def default_out_path() -> Path:
    today = dt.date.today().isoformat()
    return Path.home() / "Documents" / "vexjoy-personal-reports" / f"github-issues-{today}.html"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=50, help="max issues to fetch (default 50)")
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output path (default ~/Documents/vexjoy-personal-reports/github-issues-<DATE>.html)",
    )
    ap.add_argument("--dry-run", action="store_true", help="emit HTML to stdout, write nothing")
    ap.add_argument(
        "--no-discussion", action="store_true", help="skip per-issue gh issue view (faster, no comment summaries)"
    )
    ap.add_argument("--title", default="My GitHub Issues", help="page title")
    args = ap.parse_args()

    issues_raw = fetch_issues(args.limit)
    sys.stderr.write(f"Fetched {len(issues_raw)} issue(s).\n")

    shaped = []
    for i, issue in enumerate(issues_raw, 1):
        repo = (issue.get("repository") or {}).get("nameWithOwner") or ""
        number = issue.get("number")
        if args.no_discussion or not repo or number is None:
            comments = []
        else:
            sys.stderr.write(f"  [{i}/{len(issues_raw)}] {repo}#{number}\n")
            comments = fetch_comments(repo, number)
        shaped.append(shape_issue(issue, comments))

    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M %Z").strip()
    html = render(shaped, args.title, generated_at)

    if args.dry_run:
        sys.stdout.write(html)
        return

    out = args.out if args.out else default_out_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    sys.stderr.write(f"Wrote {out} ({len(html):,} bytes, {len(shaped)} issues)\n")
    sys.stdout.write(str(out) + "\n")


if __name__ == "__main__":
    main()
