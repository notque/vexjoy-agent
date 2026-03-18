#!/usr/bin/env python3
"""Bulk re-index URLs from a sitemap via Google Indexing API and IndexNow.

Fetches a sitemap (or sitemap index), optionally checks each URL's indexing
status via the Google URL Inspection API, and submits non-indexed URLs to both
Google Indexing API and IndexNow. Handles sitemap index files that contain
``<sitemap>`` entries pointing to sub-sitemaps.

Usage:
    python3 scripts/search-engine-bulk-indexer.py --sitemap https://your-blog.com/sitemap.xml --human
    python3 scripts/search-engine-bulk-indexer.py --sitemap https://your-blog.com/sitemap.xml --check-status --human
    python3 scripts/search-engine-bulk-indexer.py --sitemap https://your-blog.com/sitemap.xml --limit 50 --human
    python3 scripts/search-engine-bulk-indexer.py --sitemap https://your-blog.com/sitemap.xml --dry-run --human

Environment Variables (from ~/.env):
    GOOGLE_INDEXING_CREDENTIALS  Path to Google service account JSON file
    INDEXNOW_KEY                 IndexNow API key (8-128 char string)
    WEBSITE_HOST                 Default host domain (e.g., your-blog.com)

Exit codes:
    0 = completed (even if some submissions failed)
    1 = fatal error (bad input, sitemap unreachable, etc.)
"""

from __future__ import annotations

import argparse
import importlib.util as _ilu
import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

# ---------------------------------------------------------------------------
# Reuse config helpers from the single-URL indexer
# ---------------------------------------------------------------------------

# The source file uses hyphens in its name, so we import via importlib.

_INDEXER_PATH = Path(__file__).resolve().parent / "search-engine-indexer.py"
_spec = _ilu.spec_from_file_location("search_engine_indexer", _INDEXER_PATH)
assert _spec is not None and _spec.loader is not None
_indexer = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_indexer)

extract_host_from_url = _indexer.extract_host_from_url
get_config = _indexer.get_config
submit_google = _indexer.submit_google
submit_indexnow = _indexer.submit_indexnow

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
URL_INSPECTION_ENDPOINT = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
URL_INSPECTION_SCOPES = [
    "https://www.googleapis.com/auth/indexing",
    "https://www.googleapis.com/auth/webmasters.readonly",
]


# ---------------------------------------------------------------------------
# Sitemap fetching & parsing
# ---------------------------------------------------------------------------


def fetch_sitemap(sitemap_url: str, timeout: int = 30) -> str:
    """Fetch sitemap XML content from a URL.

    Args:
        sitemap_url: URL of the sitemap to fetch.
        timeout: Request timeout in seconds.

    Returns:
        Raw XML string.

    Raises:
        SystemExit: If the sitemap cannot be fetched.
    """
    try:
        response = requests.get(sitemap_url, timeout=timeout, headers={"User-Agent": "BulkIndexer/1.0"})
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(json.dumps({"status": "error", "error": f"Failed to fetch sitemap: {e}"}), file=sys.stderr)
        sys.exit(1)


def parse_sitemap_urls(xml_text: str) -> list[str]:
    """Parse URLs from sitemap XML, handling both regular sitemaps and sitemap indexes.

    For sitemap index files (containing ``<sitemap>`` entries), recursively
    fetches each sub-sitemap and extracts URLs.

    Args:
        xml_text: Raw XML string from a sitemap.

    Returns:
        List of URL strings extracted from all ``<loc>`` elements.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(json.dumps({"status": "error", "error": f"Failed to parse sitemap XML: {e}"}), file=sys.stderr)
        sys.exit(1)

    urls: list[str] = []

    # Check if this is a sitemap index (contains <sitemap> elements)
    sitemap_entries = root.findall("sm:sitemap/sm:loc", SITEMAP_NS)
    if sitemap_entries:
        for loc_el in sitemap_entries:
            if loc_el.text:
                sub_xml = fetch_sitemap(loc_el.text.strip())
                urls.extend(parse_sitemap_urls(sub_xml))
        return urls

    # Regular sitemap — extract <url><loc> entries
    for loc_el in root.findall("sm:url/sm:loc", SITEMAP_NS):
        if loc_el.text:
            urls.append(loc_el.text.strip())

    return urls


# ---------------------------------------------------------------------------
# Google URL Inspection API
# ---------------------------------------------------------------------------


def check_index_status(url: str, credentials_path: str) -> dict[str, Any]:
    """Check whether a URL is indexed via the Google URL Inspection API.

    Args:
        url: The URL to inspect.
        credentials_path: Path to Google service account JSON file.

    Returns:
        Dict with keys: indexed (bool), coverage_state (str), error (str|None).
    """
    if not credentials_path:
        return {"indexed": False, "coverage_state": "unknown", "error": "no credentials"}

    creds_file = Path(credentials_path)
    if not creds_file.exists():
        return {"indexed": False, "coverage_state": "unknown", "error": f"credentials not found: {credentials_path}"}

    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_file(
            str(creds_file), scopes=URL_INSPECTION_SCOPES
        )
        credentials.refresh(Request())

        # Determine siteUrl from the URL's domain
        parsed = urlparse(url)
        site_url = f"sc-domain:{parsed.netloc}"

        response = requests.post(
            URL_INSPECTION_ENDPOINT,
            headers={"Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json"},
            json={"inspectionUrl": url, "siteUrl": site_url},
            timeout=30,
        )

        if response.status_code != 200:
            return {
                "indexed": False,
                "coverage_state": "error",
                "error": f"HTTP {response.status_code}: {response.text[:300]}",
            }

        data = response.json()
        coverage_state = data.get("inspectionResult", {}).get("indexStatusResult", {}).get("coverageState", "unknown")
        is_indexed = coverage_state == "Submitted and indexed"

        return {"indexed": is_indexed, "coverage_state": coverage_state, "error": None}

    except ImportError:
        return {"indexed": False, "coverage_state": "unknown", "error": "google-auth not installed"}
    except Exception as e:
        return {"indexed": False, "coverage_state": "unknown", "error": str(e)}


# ---------------------------------------------------------------------------
# Bulk submission
# ---------------------------------------------------------------------------


def process_urls(
    urls: list[str],
    config: dict[str, str],
    host: str,
    *,
    check_status: bool = False,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Process a list of URLs: optionally check status, then submit for indexing.

    Args:
        urls: List of URLs to process.
        config: Configuration dict from get_config().
        host: Host domain for IndexNow.
        check_status: If True, check indexing status before submitting.
        limit: Max number of URLs to submit (None = no limit).
        dry_run: If True, show what would be done without sending.

    Returns:
        Summary dict with counts and per-URL details.
    """
    total = len(urls)
    checked = 0
    already_indexed = 0
    submitted = 0
    failed = 0
    skipped_quota = 0
    details: list[dict[str, Any]] = []

    for url in urls:
        # Stop submitting if we hit the limit (but we track skipped_quota)
        if limit is not None and submitted >= limit:
            skipped_quota += 1
            continue

        url_detail: dict[str, Any] = {"url": url}

        # Optionally check indexing status
        if check_status:
            checked += 1
            status_result = check_index_status(url, config["google_credentials"])
            url_detail["inspection"] = status_result

            if status_result["indexed"]:
                already_indexed += 1
                url_detail["action"] = "skipped_indexed"
                details.append(url_detail)
                continue

            # Rate limit inspection API calls
            if not dry_run:
                time.sleep(1)

        # Check limit again after inspection (inspection doesn't count toward limit)
        if limit is not None and submitted >= limit:
            skipped_quota += 1
            continue

        # Submit to both APIs
        google_result = submit_google(url, config["google_credentials"], dry_run=dry_run)
        indexnow_result = submit_indexnow(url, host, config["indexnow_key"], dry_run=dry_run)

        url_detail["google"] = google_result
        url_detail["indexnow"] = indexnow_result
        url_detail["action"] = "dry_run" if dry_run else "submitted"

        # Count as failed only if both APIs failed
        google_ok = google_result["status"] in ("success", "dry_run", "skipped")
        indexnow_ok = indexnow_result["status"] in ("success", "dry_run", "skipped")

        if not google_ok and not indexnow_ok:
            failed += 1
        else:
            submitted += 1

        details.append(url_detail)

        # Rate limit Google API calls
        if not dry_run:
            time.sleep(1)

    return {
        "total_urls": total,
        "checked": checked,
        "already_indexed": already_indexed,
        "submitted": submitted,
        "failed": failed,
        "skipped_quota": skipped_quota,
        "details": details,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _output_result(result: dict[str, Any], human: bool) -> int:
    """Print result in human or JSON format and return exit code.

    Args:
        result: Result dict with summary counts.
        human: If True, print human-readable output.

    Returns:
        0 on success, 1 on fatal error.
    """
    if human:
        print(f"Sitemap: {result['sitemap']}")
        print(f"Status:  {result['status']}")
        print()
        print(f"  Total URLs in sitemap:  {result['total_urls']}")
        print(f"  Checked (inspection):   {result['checked']}")
        print(f"  Already indexed:        {result['already_indexed']}")
        print(f"  Submitted:              {result['submitted']}")
        print(f"  Failed:                 {result['failed']}")
        print(f"  Skipped (quota):        {result['skipped_quota']}")

        if result.get("details"):
            print()
            print("Details:")
            for detail in result["details"]:
                action = detail.get("action", "unknown")
                if action == "skipped_indexed":
                    coverage = detail.get("inspection", {}).get("coverage_state", "")
                    print(f"  INDEXED  {detail['url']}  ({coverage})")
                elif action in ("submitted", "dry_run"):
                    g_status = detail.get("google", {}).get("status", "n/a")
                    i_status = detail.get("indexnow", {}).get("status", "n/a")
                    label = "DRY RUN" if action == "dry_run" else "SUBMIT "
                    print(f"  {label}  {detail['url']}  (google={g_status}, indexnow={i_status})")
        print()
    else:
        # Remove verbose details from JSON summary output
        output = {k: v for k, v in result.items() if k != "details"}
        print(json.dumps(output, indent=2))

    return 0 if result["status"] != "error" else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    """CLI entry point for bulk search engine re-indexing."""
    parser = argparse.ArgumentParser(
        description="Bulk re-index URLs from a sitemap via Google Indexing API and IndexNow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--sitemap", required=True, help="URL to the sitemap.xml")
    parser.add_argument(
        "--check-status",
        action="store_true",
        help="Check indexing status via Google URL Inspection API before submitting",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max URLs to submit (for quota management)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without actually sending")
    parser.add_argument("--human", action="store_true", help="Output human-readable format instead of JSON")
    parser.add_argument(
        "--host", help="Override host domain (defaults to WEBSITE_HOST env var or extracted from sitemap)"
    )

    args = parser.parse_args()

    # Validate sitemap URL
    parsed = urlparse(args.sitemap)
    if not parsed.scheme or not parsed.netloc:
        print(json.dumps({"status": "error", "error": f"Invalid sitemap URL: {args.sitemap}"}), file=sys.stderr)
        return 1

    if parsed.scheme not in ("http", "https"):
        print(
            json.dumps({"status": "error", "error": f"Sitemap URL must use http or https: {args.sitemap}"}),
            file=sys.stderr,
        )
        return 1

    # Load config
    config = get_config()

    # Resolve host
    host = args.host or config["website_host"] or extract_host_from_url(args.sitemap)
    if not host:
        print(json.dumps({"status": "error", "error": "Could not determine host domain"}), file=sys.stderr)
        return 1

    # Check that at least one API is configured (unless dry-run)
    if not args.dry_run and not config["google_credentials"] and not config["indexnow_key"]:
        result = {
            "status": "error",
            "sitemap": args.sitemap,
            "error": "No APIs configured. Set GOOGLE_INDEXING_CREDENTIALS and/or INDEXNOW_KEY.",
            "total_urls": 0,
            "checked": 0,
            "already_indexed": 0,
            "submitted": 0,
            "failed": 0,
            "skipped_quota": 0,
        }
        return _output_result(result, args.human)

    # Fetch and parse sitemap
    xml_text = fetch_sitemap(args.sitemap)
    urls = parse_sitemap_urls(xml_text)

    if not urls:
        result = {
            "status": "success",
            "sitemap": args.sitemap,
            "total_urls": 0,
            "checked": 0,
            "already_indexed": 0,
            "submitted": 0,
            "failed": 0,
            "skipped_quota": 0,
        }
        return _output_result(result, args.human)

    # Process URLs
    summary = process_urls(
        urls,
        config,
        host,
        check_status=args.check_status,
        limit=args.limit,
        dry_run=args.dry_run,
    )

    # Determine overall status
    if summary["failed"] > 0 and summary["submitted"] == 0:
        status = "error"
    elif summary["failed"] > 0:
        status = "partial"
    elif args.dry_run:
        status = "dry_run"
    else:
        status = "success"

    result = {"status": status, "sitemap": args.sitemap, **summary}
    return _output_result(result, args.human)


if __name__ == "__main__":
    sys.exit(main())
