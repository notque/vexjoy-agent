#!/usr/bin/env python3
"""Notify search engines when a new URL is published.

Submits URLs to Google Indexing API, IndexNow (Bing, Yandex, Seznam, Naver),
and Baidu Push API for immediate crawl notification. Each API is independent --
if one fails or is not configured, the others still run.

Usage:
    python3 scripts/search-engine-indexer.py --url https://your-blog.com/new-post
    python3 scripts/search-engine-indexer.py --url https://your-blog.com/new-post --human
    python3 scripts/search-engine-indexer.py --url https://your-blog.com/new-post --dry-run
    python3 scripts/search-engine-indexer.py --url https://your-blog.com/post --host your-blog.com --human

Environment Variables (from ~/.env):
    GOOGLE_INDEXING_CREDENTIALS  Path to Google service account JSON file
    INDEXNOW_KEY                 IndexNow API key (8-128 char string)
    BAIDU_PUSH_TOKEN             Baidu push token (from ziyuan.baidu.com)
    WEBSITE_HOST                 Default host domain (e.g., your-blog.com)

Exit codes:
    0 = at least one API succeeded
    1 = all APIs failed or invalid input
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
    """Get indexing configuration from environment variables and ~/.env.

    Returns:
        Dict with keys: google_credentials, indexnow_key, website_host.
    """
    env_vars = load_env_file()
    return {
        "google_credentials": os.environ.get(
            "GOOGLE_INDEXING_CREDENTIALS", env_vars.get("GOOGLE_INDEXING_CREDENTIALS", "")
        ),
        "indexnow_key": os.environ.get("INDEXNOW_KEY", env_vars.get("INDEXNOW_KEY", "")),
        "baidu_push_token": os.environ.get("BAIDU_PUSH_TOKEN", env_vars.get("BAIDU_PUSH_TOKEN", "")),
        "website_host": os.environ.get("WEBSITE_HOST", env_vars.get("WEBSITE_HOST", "")),
    }


def extract_host_from_url(url: str) -> str:
    """Extract the host domain from a URL.

    Args:
        url: Full URL string.

    Returns:
        Host domain (e.g., "your-blog.com").
    """
    parsed = urlparse(url)
    return parsed.netloc


# ---------------------------------------------------------------------------
# Google Indexing API
# ---------------------------------------------------------------------------

GOOGLE_INDEXING_ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"
GOOGLE_INDEXING_SCOPES = ["https://www.googleapis.com/auth/indexing"]


def submit_google(url: str, credentials_path: str, dry_run: bool = False) -> dict[str, Any]:
    """Submit a URL to the Google Indexing API.

    Args:
        url: The URL to submit for indexing.
        credentials_path: Path to Google service account JSON file.
        dry_run: If True, show what would be sent without sending.

    Returns:
        Result dict with status, response_code, or error details.
    """
    if not credentials_path:
        return {"status": "skipped", "reason": "GOOGLE_INDEXING_CREDENTIALS not configured"}

    if dry_run:
        return {
            "status": "dry_run",
            "endpoint": GOOGLE_INDEXING_ENDPOINT,
            "payload": {"url": url, "type": "URL_UPDATED"},
        }

    creds_file = Path(credentials_path)
    if not creds_file.exists():
        return {"status": "error", "error": f"credentials file not found: {credentials_path}"}

    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_file(
            str(creds_file), scopes=GOOGLE_INDEXING_SCOPES
        )
        credentials.refresh(Request())

        response = requests.post(
            GOOGLE_INDEXING_ENDPOINT,
            headers={"Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json"},
            json={"url": url, "type": "URL_UPDATED"},
            timeout=30,
        )

        if response.status_code == 200:
            return {"status": "success", "response_code": response.status_code}
        else:
            return {"status": "error", "response_code": response.status_code, "error": response.text[:300]}

    except ImportError:
        return {"status": "error", "error": "google-auth package not installed (pip install google-auth)"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# IndexNow API (Bing, Yandex, Seznam, Naver)
# ---------------------------------------------------------------------------

INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"


def submit_indexnow(url: str, host: str, indexnow_key: str, dry_run: bool = False) -> dict[str, Any]:
    """Submit a URL to the IndexNow API.

    Args:
        url: The URL to submit for indexing.
        host: The host domain (e.g., "your-blog.com").
        indexnow_key: IndexNow API key.
        dry_run: If True, show what would be sent without sending.

    Returns:
        Result dict with status, response_code, or error details.
    """
    if not indexnow_key:
        return {"status": "skipped", "reason": "INDEXNOW_KEY not configured"}

    payload = {
        "host": host,
        "key": indexnow_key,
        "keyLocation": f"https://{host}/{indexnow_key}.txt",
        "urlList": [url],
    }

    if dry_run:
        return {"status": "dry_run", "endpoint": INDEXNOW_ENDPOINT, "payload": payload}

    try:
        response = requests.post(
            INDEXNOW_ENDPOINT,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )

        # IndexNow returns 200 or 202 on success
        if response.status_code in (200, 202):
            return {"status": "success", "response_code": response.status_code}
        else:
            return {"status": "error", "response_code": response.status_code, "error": response.text[:300]}

    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Baidu Push API
# ---------------------------------------------------------------------------

BAIDU_PUSH_ENDPOINT = "http://data.zz.baidu.com/urls"


def submit_baidu(url: str, site_url: str, push_token: str, dry_run: bool = False) -> dict[str, Any]:
    """Submit a URL to the Baidu Push API.

    Args:
        url: The URL to submit for indexing.
        site_url: The site URL with scheme (e.g., "https://your-blog.com").
        push_token: Baidu push token from ziyuan.baidu.com.
        dry_run: If True, show what would be sent without sending.

    Returns:
        Result dict with status, response_code, or error details.
    """
    if not push_token:
        return {"status": "skipped", "reason": "BAIDU_PUSH_TOKEN not configured"}

    endpoint = f"{BAIDU_PUSH_ENDPOINT}?site={site_url}&token={push_token}"

    if dry_run:
        return {"status": "dry_run", "endpoint": endpoint, "payload": url}

    try:
        response = requests.post(
            endpoint,
            headers={"Content-Type": "text/plain"},
            data=url,
            timeout=30,
        )

        if response.status_code == 200:
            return {"status": "success", "response_code": response.status_code}
        else:
            return {"status": "error", "response_code": response.status_code, "error": response.text[:300]}

    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _determine_overall_status(
    google_result: dict[str, Any],
    indexnow_result: dict[str, Any],
    baidu_result: dict[str, Any],
) -> str:
    """Determine the overall status from individual API results.

    Args:
        google_result: Result dict from Google submission.
        indexnow_result: Result dict from IndexNow submission.
        baidu_result: Result dict from Baidu submission.

    Returns:
        "success" if all attempted APIs succeeded, "partial" if some failed,
        "error" if all failed/skipped, "dry_run" if dry run mode.
    """
    statuses = [google_result["status"], indexnow_result["status"], baidu_result["status"]]

    if all(s == "dry_run" for s in statuses):
        return "dry_run"

    successes = [s for s in statuses if s == "success"]
    failures = [s for s in statuses if s == "error"]
    skipped = [s for s in statuses if s == "skipped"]
    dry_runs = [s for s in statuses if s == "dry_run"]

    # All skipped or all failed = error
    if len(failures) + len(skipped) == len(statuses):
        return "error"

    # At least one success
    if successes:
        # Any failures alongside successes = partial
        if failures:
            return "partial"
        return "success"

    # Mix of dry_run and other statuses
    if dry_runs:
        return "dry_run"

    return "error"


def _output_result(result: dict[str, Any], human: bool) -> int:
    """Print result in human or JSON format and return exit code.

    Args:
        result: Result dict with "status" key.
        human: If True, print human-readable output.

    Returns:
        0 on success/partial/dry_run, 1 on error.
    """
    if human:
        status = result["status"]
        print(f"URL: {result['url']}")
        print(f"Overall: {status}")
        print()

        for api_name in ("google", "indexnow", "baidu"):
            api_result = result[api_name]
            api_status = api_result["status"]
            print(f"  {api_name.upper()}:")

            if api_status == "success":
                print(f"    Status: OK ({api_result.get('response_code', '')})")
            elif api_status == "skipped":
                print(f"    Status: Skipped ({api_result.get('reason', '')})")
            elif api_status == "dry_run":
                print("    Status: Dry run")
                print(f"    Endpoint: {api_result.get('endpoint', '')}")
            elif api_status == "error":
                print("    Status: FAILED")
                print(f"    Error: {api_result.get('error', 'unknown')}")
            print()
    else:
        print(json.dumps(result, indent=2))

    return 0 if result["status"] in ("success", "partial", "dry_run") else 1


def main() -> int:
    """CLI entry point for search engine indexing."""
    parser = argparse.ArgumentParser(
        description="Notify search engines when a new URL is published",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--url", required=True, help="URL to submit for indexing")
    parser.add_argument("--host", help="Override host domain (defaults to WEBSITE_HOST env var or extracted from URL)")
    parser.add_argument("--human", action="store_true", help="Output human-readable format instead of JSON")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be sent without actually sending")

    args = parser.parse_args()

    # Validate URL
    parsed = urlparse(args.url)
    if not parsed.scheme or not parsed.netloc:
        print(json.dumps({"status": "error", "error": f"Invalid URL: {args.url}"}), file=sys.stderr)
        return 1

    if parsed.scheme not in ("http", "https"):
        error = {"status": "error", "error": f"URL must use http or https scheme: {args.url}"}
        print(json.dumps(error), file=sys.stderr)
        return 1

    # Load config
    config = get_config()

    # Resolve host: CLI arg > env var > extracted from URL
    host = args.host or config["website_host"] or extract_host_from_url(args.url)
    if not host:
        print(json.dumps({"status": "error", "error": "Could not determine host domain"}), file=sys.stderr)
        return 1

    # Check that at least one API is configured (unless dry-run)
    has_any_api = config["google_credentials"] or config["indexnow_key"] or config["baidu_push_token"]
    if not args.dry_run and not has_any_api:
        result = {
            "status": "error",
            "url": args.url,
            "error": "No APIs configured. Set GOOGLE_INDEXING_CREDENTIALS, INDEXNOW_KEY, and/or BAIDU_PUSH_TOKEN.",
            "google": {"status": "skipped", "reason": "GOOGLE_INDEXING_CREDENTIALS not configured"},
            "indexnow": {"status": "skipped", "reason": "INDEXNOW_KEY not configured"},
            "baidu": {"status": "skipped", "reason": "BAIDU_PUSH_TOKEN not configured"},
        }
        return _output_result(result, args.human)

    # Build site URL with scheme for Baidu (e.g., "https://your-blog.com")
    parsed_site = urlparse(args.url)
    site_url = f"{parsed_site.scheme}://{host}"

    # Submit to each API independently
    google_result = submit_google(args.url, config["google_credentials"], dry_run=args.dry_run)
    indexnow_result = submit_indexnow(args.url, host, config["indexnow_key"], dry_run=args.dry_run)
    baidu_result = submit_baidu(args.url, site_url, config["baidu_push_token"], dry_run=args.dry_run)

    # Build output
    overall_status = _determine_overall_status(google_result, indexnow_result, baidu_result)
    result = {
        "status": overall_status,
        "url": args.url,
        "google": google_result,
        "indexnow": indexnow_result,
        "baidu": baidu_result,
    }

    return _output_result(result, args.human)


if __name__ == "__main__":
    sys.exit(main())
