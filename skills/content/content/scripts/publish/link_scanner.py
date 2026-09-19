#!/usr/bin/env python3
"""
Link Scanner for Hugo Sites

Scans markdown content, extracts links, builds link graph,
and validates internal/external link health.

Usage:
    python3 link_scanner.py ~/mysite/content/
    python3 link_scanner.py ~/mysite/content/ --check-external
    python3 link_scanner.py ~/mysite/content/ --min-inbound 3
    python3 link_scanner.py ~/mysite/content/ --json
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple


class Link(NamedTuple):
    """Represents an extracted link."""

    source_file: str
    line_number: int
    link_type: str  # 'internal', 'external', 'image'
    target: str
    text: str


class LinkIssue(NamedTuple):
    """Represents a link issue."""

    source_file: str
    line_number: int
    issue_type: str
    target: str
    message: str


class PageMetrics(NamedTuple):
    """Link metrics for a page."""

    path: str
    inbound_count: int
    outbound_count: int
    inbound_from: List[str]
    outbound_to: List[str]


# Known sites that block bot requests
FALSE_POSITIVE_DOMAINS = {
    "linkedin.com": "Returns 403/999 for bots",
    "twitter.com": "Returns 400 for bots",
    "x.com": "Returns 400 for bots",
    "facebook.com": "Requires authentication",
    "instagram.com": "Requires authentication",
    "medium.com": "Sometimes blocks bots",
}


def extract_links_from_file(file_path: Path, content_root: Path) -> List[Link]:
    """Extract all links from a markdown file."""
    links = []
    relative_path = str(file_path.relative_to(content_root))

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return links

    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        # Skip front matter
        if line_num == 1 and line.strip() in ("---", "+++"):
            continue

        # Standard markdown links: [text](url)
        for match in re.finditer(r"\[([^\]]*)\]\(([^)]+)\)", line):
            text, target = match.groups()
            link_type = classify_link(target)
            links.append(
                Link(
                    source_file=relative_path,
                    line_number=line_num,
                    link_type=link_type,
                    target=target.strip(),
                    text=text,
                )
            )

        # Markdown images: ![alt](path)
        for match in re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", line):
            alt_text, target = match.groups()
            links.append(
                Link(
                    source_file=relative_path,
                    line_number=line_num,
                    link_type="image",
                    target=target.strip(),
                    text=alt_text,
                )
            )

        # Hugo ref shortcode: {{< ref "path" >}}
        for match in re.finditer(r'\{\{<\s*ref\s+"([^"]+)"\s*>\}\}', line):
            target = match.group(1)
            links.append(
                Link(
                    source_file=relative_path,
                    line_number=line_num,
                    link_type="internal",
                    target=target,
                    text="[hugo ref]",
                )
            )

        # Hugo figure shortcode: {{< figure src="path" >}}
        for match in re.finditer(r'\{\{<\s*figure\s+[^>]*src="([^"]+)"[^>]*>\}\}', line):
            target = match.group(1)
            links.append(
                Link(
                    source_file=relative_path,
                    line_number=line_num,
                    link_type="image",
                    target=target,
                    text="[hugo figure]",
                )
            )

    return links


def classify_link(target: str) -> str:
    """Classify a link as internal or external."""
    target = target.strip()

    # Anchors only
    if target.startswith("#"):
        return "anchor"

    # External links
    if target.startswith(("http://", "https://", "//")):
        return "external"

    # mailto, tel, etc.
    if ":" in target.split("/")[0]:
        return "external"

    # Everything else is internal
    return "internal"


def normalize_internal_path(target: str, source_file: str, content_root: Path) -> str:
    """Normalize internal link to content file path."""
    # Remove anchor
    target = target.split("#")[0]

    # Handle relative paths
    if not target.startswith("/"):
        source_dir = Path(source_file).parent
        target = str(source_dir / target)

    # Remove leading slash
    target = target.lstrip("/")

    # Normalize path
    target = os.path.normpath(target)

    return target


def resolve_internal_link(target: str, content_root: Path) -> Optional[Path]:
    """Try to resolve internal link to actual file."""
    # Possible file patterns
    patterns = [
        f"{target}.md",
        f"{target}/index.md",
        f"{target}/_index.md",
        target,  # Already includes .md
    ]

    for pattern in patterns:
        full_path = content_root / pattern
        if full_path.exists() and full_path.is_file():
            return full_path

    return None


def resolve_image_path(target: str, site_root: Path) -> Optional[Path]:
    """Try to resolve image path to actual file."""
    # Remove leading slash for path resolution
    clean_target = target.lstrip("/")

    # Check static/ directory
    static_path = site_root / "static" / clean_target
    if static_path.exists():
        return static_path

    # Check if path includes 'static'
    if clean_target.startswith("static/"):
        direct_path = site_root / clean_target
        if direct_path.exists():
            return direct_path

    # Check assets/ directory (Hugo Pipes)
    assets_path = site_root / "assets" / clean_target
    if assets_path.exists():
        return assets_path

    return None


def validate_external_link(url: str, timeout: int = 10) -> Tuple[bool, str]:
    """Validate external URL via HTTP HEAD request."""
    # Check for known false positives
    for domain, _reason in FALSE_POSITIVE_DOMAINS.items():
        if domain in url:
            return True, f"blocked ({domain} - expected)"

    try:
        req = urllib.request.Request(
            url,
            method="HEAD",
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; LinkAuditor/1.0)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status < 400:
                return True, "valid"
            return False, f"HTTP {response.status}"
    except urllib.error.HTTPError as e:
        # Some sites block HEAD, try GET
        if e.code in (403, 405):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; LinkAuditor/1.0)",
                        "Accept": "text/html,application/xhtml+xml",
                    },
                )
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    if response.status < 400:
                        return True, "valid"
                    return False, f"HTTP {response.status}"
            except Exception:
                pass
        return False, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, f"URL error: {e.reason}"
    except Exception as e:
        return False, f"Error: {e!s}"


def build_link_graph(links: List[Link], content_root: Path) -> Dict[str, PageMetrics]:
    """Build link graph and calculate metrics for each page."""
    # Find all content files
    all_pages = set()
    for md_file in content_root.rglob("*.md"):
        rel_path = str(md_file.relative_to(content_root))
        all_pages.add(rel_path)

    # Track inbound/outbound for each page
    inbound: Dict[str, List[str]] = defaultdict(list)
    outbound: Dict[str, List[str]] = defaultdict(list)

    # Process internal links
    for link in links:
        if link.link_type != "internal":
            continue

        # Normalize target path
        normalized = normalize_internal_path(link.target, link.source_file, content_root)
        resolved = resolve_internal_link(normalized, content_root)

        if resolved:
            target_rel = str(resolved.relative_to(content_root))
            outbound[link.source_file].append(target_rel)
            inbound[target_rel].append(link.source_file)

    # Build metrics for all pages
    metrics = {}
    for page in all_pages:
        metrics[page] = PageMetrics(
            path=page,
            inbound_count=len(set(inbound.get(page, []))),
            outbound_count=len(set(outbound.get(page, []))),
            inbound_from=list(set(inbound.get(page, []))),
            outbound_to=list(set(outbound.get(page, []))),
        )

    return metrics


def analyze_graph(metrics: Dict[str, PageMetrics], min_inbound: int = 2) -> Dict[str, List[PageMetrics]]:
    """Analyze link graph for issues."""
    orphans = []
    under_linked = []
    sinks = []
    hubs = []

    for page, m in metrics.items():
        # Skip index files for orphan detection (they're navigation)
        is_index = page.endswith("_index.md") or page.endswith("index.md")

        if m.inbound_count == 0 and not is_index:
            orphans.append(m)
        elif m.inbound_count < min_inbound and not is_index:
            under_linked.append(m)

        if m.inbound_count > 0 and m.outbound_count == 0 and not is_index:
            sinks.append(m)

        if m.outbound_count >= 5:
            hubs.append(m)

    return {
        "orphans": sorted(orphans, key=lambda x: x.path),
        "under_linked": sorted(under_linked, key=lambda x: x.inbound_count),
        "sinks": sorted(sinks, key=lambda x: -x.inbound_count),
        "hubs": sorted(hubs, key=lambda x: -x.outbound_count),
    }


def validate_links(
    links: List[Link], content_root: Path, site_root: Path, check_external: bool = False, timeout: int = 10
) -> List[LinkIssue]:
    """Validate all links and return issues."""
    issues = []
    external_results = {}  # Cache external validation results

    for link in links:
        if link.link_type == "internal":
            normalized = normalize_internal_path(link.target, link.source_file, content_root)
            resolved = resolve_internal_link(normalized, content_root)
            if not resolved:
                issues.append(
                    LinkIssue(
                        source_file=link.source_file,
                        line_number=link.line_number,
                        issue_type="broken_internal",
                        target=link.target,
                        message=f"Internal link target not found: {link.target}",
                    )
                )

        elif link.link_type == "image":
            resolved = resolve_image_path(link.target, site_root)
            if not resolved:
                issues.append(
                    LinkIssue(
                        source_file=link.source_file,
                        line_number=link.line_number,
                        issue_type="missing_image",
                        target=link.target,
                        message=f"Image file not found: {link.target}",
                    )
                )

        elif link.link_type == "external" and check_external:
            # Cache results to avoid duplicate requests
            if link.target not in external_results:
                valid, status = validate_external_link(link.target, timeout)
                external_results[link.target] = (valid, status)

            valid, status = external_results[link.target]
            if not valid:
                issues.append(
                    LinkIssue(
                        source_file=link.source_file,
                        line_number=link.line_number,
                        issue_type="broken_external",
                        target=link.target,
                        message=f"External link failed: {status}",
                    )
                )

    return issues


def format_report(
    content_root: Path,
    links: List[Link],
    issues: List[LinkIssue],
    graph_analysis: Dict[str, List[PageMetrics]],
    check_external: bool = False,
) -> str:
    """Format the audit report."""
    lines = []

    # Header
    lines.append("=" * 63)
    lines.append(f" LINK AUDIT: {content_root}")
    lines.append("=" * 63)
    lines.append("")

    # Summary
    internal_count = sum(1 for l in links if l.link_type == "internal")
    external_count = sum(1 for l in links if l.link_type == "external")
    image_count = sum(1 for l in links if l.link_type == "image")
    source_files = len(set(l.source_file for l in links))

    lines.append(" SCAN SUMMARY:")
    lines.append(f"   Posts scanned: {source_files}")
    lines.append(f"   Internal links: {internal_count}")
    lines.append(f"   External links: {external_count}")
    lines.append(f"   Image references: {image_count}")
    lines.append("")

    # Link Graph Analysis
    lines.append(" LINK GRAPH ANALYSIS:")
    lines.append("")

    # Orphans
    orphans = graph_analysis.get("orphans", [])
    if orphans:
        lines.append(" ORPHAN PAGES (Critical - 0 inbound links):")
        for m in orphans:
            lines.append(f"   ! /{m.path}")
            lines.append("     No other posts link to this. Consider:")
            lines.append("     - Adding link from a related post")
            lines.append("     - Adding to navigation or index page")
        lines.append("")

    # Under-linked
    under_linked = graph_analysis.get("under_linked", [])
    if under_linked:
        lines.append(" UNDER-LINKED (< 2 inbound links):")
        for m in under_linked:
            lines.append(f"   > /{m.path} ({m.inbound_count} inbound)")
        lines.append("")

    # Sinks
    sinks = graph_analysis.get("sinks", [])
    if sinks:
        lines.append(" LINK SINKS (receive but don't link out):")
        for m in sinks:
            lines.append(f"   > /{m.path} ({m.inbound_count} inbound, 0 outbound)")
        lines.append("")

    # Hubs
    hubs = graph_analysis.get("hubs", [])
    if hubs:
        lines.append(" HUB PAGES (many outbound links):")
        for m in hubs:
            lines.append(f"   > /{m.path} ({m.outbound_count} outbound links)")
        lines.append("")

    if not orphans and not under_linked and not sinks and not hubs:
        lines.append(" No graph issues detected.")
        lines.append("")

    # Broken Internal Links
    broken_internal = [i for i in issues if i.issue_type == "broken_internal"]
    lines.append(" BROKEN INTERNAL LINKS:")
    if broken_internal:
        for issue in broken_internal:
            lines.append(f"   X /{issue.source_file} line {issue.line_number}:")
            lines.append(f"     Links to {issue.target} (not found)")
    else:
        lines.append("   None found")
    lines.append("")

    # External Links
    lines.append(" EXTERNAL LINK STATUS:")
    if check_external:
        broken_external = [i for i in issues if i.issue_type == "broken_external"]
        valid_external = external_count - len(broken_external)

        blocked = [i for i in broken_external if "blocked" in i.message.lower() or "expected" in i.message.lower()]
        truly_broken = [i for i in broken_external if i not in blocked]

        lines.append(f"   OK {valid_external} links valid")
        if blocked:
            lines.append(f"   ! {len(blocked)} links blocked (expected - see false-positives.md)")
        if truly_broken:
            for issue in truly_broken:
                lines.append(f"   X {issue.target}")
                lines.append(f"     {issue.message}")
    else:
        lines.append("   [SKIP] Use --check-external to validate")
    lines.append("")

    # Image Issues
    missing_images = [i for i in issues if i.issue_type == "missing_image"]
    lines.append(" IMAGE ISSUES:")
    if missing_images:
        for issue in missing_images:
            lines.append(f"   X /{issue.source_file} line {issue.line_number}:")
            lines.append(f"     References {issue.target} (not found)")
    else:
        lines.append("   None found")
    lines.append("")

    # Recommendations
    lines.append("=" * 63)
    lines.append(" RECOMMENDATIONS:")

    recommendations = []
    if orphans:
        recommendations.append(f"   1. Add internal links to {len(orphans)} orphan page(s)")
    if broken_internal:
        recommendations.append(f"   {len(recommendations) + 1}. Fix {len(broken_internal)} broken internal link(s)")
    if check_external:
        truly_broken = [i for i in issues if i.issue_type == "broken_external" and "blocked" not in i.message.lower()]
        if truly_broken:
            recommendations.append(
                f"   {len(recommendations) + 1}. Update or remove {len(truly_broken)} dead external link(s)"
            )
    if missing_images:
        recommendations.append(f"   {len(recommendations) + 1}. Add missing image(s) or fix path(s)")

    if recommendations:
        for rec in recommendations:
            lines.append(rec)
    else:
        lines.append("   Site link structure is healthy")

    lines.append("=" * 63)

    return "\n".join(lines)


def format_json(
    content_root: Path,
    links: List[Link],
    issues: List[LinkIssue],
    graph_analysis: Dict[str, List[PageMetrics]],
    page_metrics: Dict[str, PageMetrics],
) -> str:
    """Format output as JSON."""
    output = {
        "content_root": str(content_root),
        "summary": {
            "posts_scanned": len(set(l.source_file for l in links)),
            "internal_links": sum(1 for l in links if l.link_type == "internal"),
            "external_links": sum(1 for l in links if l.link_type == "external"),
            "image_references": sum(1 for l in links if l.link_type == "image"),
        },
        "graph_analysis": {
            "orphans": [m.path for m in graph_analysis.get("orphans", [])],
            "under_linked": [
                {"path": m.path, "inbound": m.inbound_count} for m in graph_analysis.get("under_linked", [])
            ],
            "sinks": [{"path": m.path, "inbound": m.inbound_count} for m in graph_analysis.get("sinks", [])],
            "hubs": [{"path": m.path, "outbound": m.outbound_count} for m in graph_analysis.get("hubs", [])],
        },
        "issues": [
            {
                "source_file": i.source_file,
                "line_number": i.line_number,
                "issue_type": i.issue_type,
                "target": i.target,
                "message": i.message,
            }
            for i in issues
        ],
        "page_metrics": {
            path: {
                "inbound_count": m.inbound_count,
                "outbound_count": m.outbound_count,
                "inbound_from": m.inbound_from,
                "outbound_to": m.outbound_to,
            }
            for path, m in page_metrics.items()
        },
    }
    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Link Scanner for Hugo Sites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s ~/mysite/content/
    %(prog)s ~/mysite/content/ --check-external
    %(prog)s ~/mysite/content/ --min-inbound 3
    %(prog)s ~/mysite/content/ --json
        """,
    )
    parser.add_argument("content_path", help="Path to Hugo content/ directory")
    parser.add_argument("--check-external", action="store_true", help="Validate external URLs via HTTP")
    parser.add_argument("--min-inbound", type=int, default=2, help="Minimum inbound links before flagging (default: 2)")
    parser.add_argument("--timeout", type=int, default=10, help="Timeout for external link validation (default: 10s)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", action="store_true", help="Show all links, not just issues")

    args = parser.parse_args()

    content_root = Path(args.content_path).resolve()
    if not content_root.exists():
        print(f"Error: Content path does not exist: {content_root}", file=sys.stderr)
        sys.exit(1)

    # Determine site root (parent of content/)
    if content_root.name == "content":
        site_root = content_root.parent
    else:
        site_root = content_root
        # Check if this is content directory or if content/ is inside
        if (content_root / "content").exists():
            content_root = content_root / "content"

    # Find all markdown files
    md_files = list(content_root.rglob("*.md"))
    if not md_files:
        print(f"Error: No markdown files found in {content_root}", file=sys.stderr)
        sys.exit(1)

    # Extract all links
    all_links = []
    for md_file in md_files:
        links = extract_links_from_file(md_file, content_root)
        all_links.extend(links)

    # Build link graph
    page_metrics = build_link_graph(all_links, content_root)

    # Analyze graph
    graph_analysis = analyze_graph(page_metrics, args.min_inbound)

    # Validate links
    issues = validate_links(
        all_links, content_root, site_root, check_external=args.check_external, timeout=args.timeout
    )

    # Output
    if args.json:
        print(format_json(content_root, all_links, issues, graph_analysis, page_metrics))
    else:
        print(format_report(content_root, all_links, issues, graph_analysis, args.check_external))


if __name__ == "__main__":
    main()
