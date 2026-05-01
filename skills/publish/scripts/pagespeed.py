#!/usr/bin/env python3
"""
PageSpeed Insights Analyzer

Calls the Google PageSpeed Insights API v5 and outputs structured results
for performance, SEO, accessibility, and best-practices scores.

Usage:
    python3 pagespeed.py --url https://vexjoy.com
    python3 pagespeed.py --url https://vexjoy.com --strategy mobile --format markdown
    python3 pagespeed.py --url https://vexjoy.com --threshold 90 --output report.md
    python3 pagespeed.py --url https://vexjoy.com --categories performance,seo --format json
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API_BASE = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
ALL_CATEGORIES = ["performance", "seo", "accessibility", "best-practices"]
STRATEGIES = ["mobile", "desktop"]
VALID_FORMATS = ["summary", "json", "markdown"]

# Display names for categories
CATEGORY_DISPLAY = {
    "performance": "Performance",
    "seo": "SEO",
    "accessibility": "Accessibility",
    "best-practices": "Best Practices",
}


def build_api_url(url: str, strategy: str, categories: list[str], api_key: str | None = None) -> str:
    """Build the PSI API request URL."""
    query_parts = [
        f"url={urllib.parse.quote(url, safe='')}",
        f"strategy={strategy}",
    ]

    for cat in categories:
        query_parts.append(f"category={cat}")

    if api_key:
        query_parts.append(f"key={api_key}")

    return f"{API_BASE}?{'&'.join(query_parts)}"


def fetch_psi_data(url: str, strategy: str, categories: list[str], api_key: str | None = None) -> dict[str, Any]:
    """Fetch PageSpeed Insights data from the API with one retry on 429."""
    api_url = build_api_url(url, strategy, categories, api_key)
    req = urllib.request.Request(
        api_url,
        headers={
            "User-Agent": "VexJoy-PageSpeed/1.0",
            "Accept": "application/json",
        },
    )

    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 0:
                print(
                    "  Rate limited (429). Retrying in 2 seconds...",
                    file=sys.stderr,
                )
                time.sleep(2)
                continue
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            raise SystemExit(
                f"API error: HTTP {e.code}\n{body}\n\n"
                "Hint: Set PAGESPEED_API_KEY env var for reliable access.\n"
                "Get a free key at https://developers.google.com/speed/docs/insights/v5/get-started"
            ) from None
        except urllib.error.URLError as e:
            raise SystemExit(f"Network error: {e.reason}") from None

    raise SystemExit("Rate limited after retry. Set PAGESPEED_API_KEY for reliable access.")


def extract_scores(data: dict[str, Any], categories: list[str]) -> dict[str, float | None]:
    """Extract category scores (0-100) from API response."""
    scores: dict[str, float | None] = {}
    lighthouse = data.get("lighthouseResult", {})
    cat_data = lighthouse.get("categories", {})

    for cat in categories:
        cat_info = cat_data.get(cat)
        if cat_info and cat_info.get("score") is not None:
            scores[cat] = round(cat_info["score"] * 100)
        else:
            scores[cat] = None

    return scores


def extract_failing_audits(data: dict[str, Any], categories: list[str]) -> dict[str, list[dict[str, str]]]:
    """Extract audits with score < 1.0 grouped by category."""
    lighthouse = data.get("lighthouseResult", {})
    cat_data = lighthouse.get("categories", {})
    all_audits = lighthouse.get("audits", {})
    failing: dict[str, list[dict[str, str]]] = {}

    for cat in categories:
        cat_info = cat_data.get(cat, {})
        audit_refs = cat_info.get("auditRefs", [])
        cat_failures: list[dict[str, str]] = []

        for ref in audit_refs:
            audit_id = ref.get("id", "")
            audit = all_audits.get(audit_id, {})
            score = audit.get("score")
            # Include audits that failed (score < 1.0) and are not informational
            if score is not None and score < 1.0 and audit.get("scoreDisplayMode") != "informative":
                detail: dict[str, str] = {
                    "id": audit_id,
                    "title": audit.get("title", audit_id),
                }
                # Extract savings info from details
                display_value = audit.get("displayValue", "")
                if display_value:
                    detail["savings"] = display_value
                cat_failures.append(detail)

        if cat_failures:
            failing[cat] = cat_failures

    return failing


def extract_opportunities(data: dict[str, Any]) -> list[dict[str, str]]:
    """Extract top optimization opportunities from performance audits."""
    lighthouse = data.get("lighthouseResult", {})
    all_audits = lighthouse.get("audits", {})
    opportunities: list[dict[str, str]] = []

    for audit_id, audit in all_audits.items():
        if audit.get("scoreDisplayMode") == "opportunity" or (
            audit.get("score") is not None
            and audit["score"] < 1.0
            and audit.get("details", {}).get("type") == "opportunity"
        ):
            savings = audit.get("displayValue", "")
            if not savings:
                # Try to extract from numeric details
                details = audit.get("details", {})
                overall = details.get("overallSavingsMs")
                if overall:
                    savings = f"{overall / 1000:.1f}s"
                else:
                    overall_bytes = details.get("overallSavingsBytes")
                    if overall_bytes:
                        if overall_bytes > 1024 * 1024:
                            savings = f"{overall_bytes / (1024 * 1024):.1f} MiB"
                        elif overall_bytes > 1024:
                            savings = f"{overall_bytes / 1024:.0f} KiB"
                        else:
                            savings = f"{overall_bytes} bytes"

            opportunities.append(
                {
                    "id": audit_id,
                    "title": audit.get("title", audit_id),
                    "savings": savings,
                }
            )

    # Sort by savings string (rough heuristic: longer savings = more impactful)
    # Put items with savings first
    opportunities.sort(key=lambda x: (not x["savings"], x["title"]))
    return opportunities[:5]


def format_summary(
    url: str,
    strategy: str,
    scores: dict[str, float | None],
    failing_audits: dict[str, list[dict[str, str]]],
    opportunities: list[dict[str, str]],
    threshold: int,
) -> str:
    """Format results as a human-readable summary."""
    lines: list[str] = []

    lines.append("=" * 64)
    lines.append(f" PageSpeed Insights: {url}")
    lines.append(f" Strategy: {strategy}")
    lines.append("=" * 64)
    lines.append("")
    lines.append(" SCORES:")

    passing = 0
    total = 0
    for cat, score in scores.items():
        display_name = CATEGORY_DISPLAY.get(cat, cat)
        total += 1
        if score is None:
            lines.append(f"   {display_name + ':':<18} n/a")
            continue
        passed = score >= threshold
        if passed:
            passing += 1
            marker = "PASS"
        else:
            marker = f"FAIL (below threshold: {threshold})"
        lines.append(f"   {display_name + ':':<18}{score:>3}/100  {marker}")

    lines.append("")

    # Failing audits
    if failing_audits:
        lines.append(" FAILING AUDITS (score < 1.0):")
        for cat, audits in failing_audits.items():
            display_name = CATEGORY_DISPLAY.get(cat, cat)
            lines.append(f"   {display_name}:")
            for audit in audits[:8]:  # Cap at 8 per category for readability
                savings_part = f" ({audit['savings']})" if audit.get("savings") else ""
                lines.append(f"     - {audit['id']}: {audit['title']}{savings_part}")
        lines.append("")

    # Opportunities
    if opportunities:
        lines.append(" TOP OPPORTUNITIES:")
        for i, opp in enumerate(opportunities, 1):
            savings_part = f" -- potential savings: {opp['savings']}" if opp.get("savings") else ""
            lines.append(f"   {i}. {opp['title']}{savings_part}")
        lines.append("")

    lines.append("=" * 64)
    lines.append(f" RESULT: {passing} of {total} categories pass (threshold: {threshold})")
    lines.append("=" * 64)

    return "\n".join(lines)


def format_markdown(
    url: str,
    strategy: str,
    scores: dict[str, float | None],
    failing_audits: dict[str, list[dict[str, str]]],
    opportunities: list[dict[str, str]],
    threshold: int,
) -> str:
    """Format results as a Markdown report."""
    lines: list[str] = []

    lines.append(f"# PageSpeed Insights Report: {url}")
    lines.append("")
    lines.append(f"**Strategy:** {strategy}")
    lines.append(f"**Threshold:** {threshold}")
    lines.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    lines.append("")

    # Scores table
    lines.append("## Scores")
    lines.append("")
    lines.append("| Category | Score | Status |")
    lines.append("|----------|------:|--------|")

    passing = 0
    total = 0
    for cat, score in scores.items():
        display_name = CATEGORY_DISPLAY.get(cat, cat)
        total += 1
        if score is None:
            lines.append(f"| {display_name} | n/a | - |")
            continue
        passed = score >= threshold
        if passed:
            passing += 1
            status = "PASS"
        else:
            status = "FAIL"
        lines.append(f"| {display_name} | {score}/100 | {status} |")

    lines.append("")

    # Failing audits
    if failing_audits:
        lines.append("## Failing Audits")
        lines.append("")
        for cat, audits in failing_audits.items():
            display_name = CATEGORY_DISPLAY.get(cat, cat)
            lines.append(f"### {display_name}")
            lines.append("")
            for audit in audits:
                savings_part = f" ({audit['savings']})" if audit.get("savings") else ""
                lines.append(f"- **{audit['id']}**: {audit['title']}{savings_part}")
            lines.append("")

    # Opportunities
    if opportunities:
        lines.append("## Top Opportunities")
        lines.append("")
        for i, opp in enumerate(opportunities, 1):
            savings_part = f" -- potential savings: {opp['savings']}" if opp.get("savings") else ""
            lines.append(f"{i}. **{opp['title']}**{savings_part}")
        lines.append("")

    lines.append("---")
    lines.append(f"**Result:** {passing} of {total} categories pass (threshold: {threshold})")

    return "\n".join(lines)


def run_analysis(
    url: str,
    strategy: str,
    categories: list[str],
    output_format: str,
    threshold: int,
    api_key: str | None,
) -> tuple[str, bool]:
    """Run PSI analysis for a single strategy. Returns (formatted output, all_pass)."""
    print(f"  Analyzing {url} ({strategy})...", file=sys.stderr)
    data = fetch_psi_data(url, strategy, categories, api_key)

    if output_format == "json":
        return json.dumps(data, indent=2), True

    scores = extract_scores(data, categories)
    failing_audits = extract_failing_audits(data, categories)
    opportunities = extract_opportunities(data)

    all_pass = all(s is not None and s >= threshold for s in scores.values())

    if output_format == "markdown":
        text = format_markdown(url, strategy, scores, failing_audits, opportunities, threshold)
    else:
        text = format_summary(url, strategy, scores, failing_audits, opportunities, threshold)

    return text, all_pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PageSpeed Insights Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s --url https://vexjoy.com
    %(prog)s --url https://vexjoy.com --strategy mobile
    %(prog)s --url https://vexjoy.com --format markdown --output report.md
    %(prog)s --url https://vexjoy.com --categories performance,seo --threshold 90
    %(prog)s --url https://vexjoy.com --format json

Environment:
    PAGESPEED_API_KEY   Google API key for reliable access (optional).
                        Without a key, requests use shared rate limits
                        and may receive 429 errors.
                        Get a free key: https://developers.google.com/speed/docs/insights/v5/get-started
        """,
    )
    parser.add_argument("--url", required=True, help="URL to analyze")
    parser.add_argument(
        "--strategy",
        default="both",
        choices=["mobile", "desktop", "both"],
        help="Analysis strategy (default: both)",
    )
    parser.add_argument(
        "--categories",
        default=",".join(ALL_CATEGORIES),
        help=f"Comma-separated categories (default: {','.join(ALL_CATEGORIES)})",
    )
    parser.add_argument(
        "--format",
        default="summary",
        choices=VALID_FORMATS,
        dest="output_format",
        help="Output format (default: summary)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=80,
        help="Score threshold below which categories are flagged (default: 80)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="File path to write results (default: stdout)",
    )

    args = parser.parse_args()

    # Parse categories
    categories = [c.strip() for c in args.categories.split(",")]
    for cat in categories:
        if cat not in ALL_CATEGORIES:
            print(f"Error: Unknown category '{cat}'. Valid: {', '.join(ALL_CATEGORIES)}", file=sys.stderr)
            sys.exit(2)

    # Check for API key
    api_key = os.environ.get("PAGESPEED_API_KEY")
    if not api_key:
        print(
            "Note: PAGESPEED_API_KEY not set. Using shared rate limits (may get 429 errors).\n"
            "Get a free key: https://developers.google.com/speed/docs/insights/v5/get-started\n",
            file=sys.stderr,
        )

    # Determine strategies to run
    if args.strategy == "both":
        strategies = STRATEGIES
    else:
        strategies = [args.strategy]

    # Run analysis
    results: list[str] = []
    all_pass = True

    for strategy in strategies:
        text, passed = run_analysis(
            args.url,
            strategy,
            categories,
            args.output_format,
            args.threshold,
            api_key,
        )
        results.append(text)
        if not passed:
            all_pass = False

    output = "\n\n".join(results)

    # Write output
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
                f.write("\n")
            print(f"  Results written to {args.output}", file=sys.stderr)
        except OSError as e:
            print(f"Error writing to {args.output}: {e}", file=sys.stderr)
            sys.exit(2)
    else:
        print(output)

    # Exit code: 0 if all pass, 1 if any fail
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
