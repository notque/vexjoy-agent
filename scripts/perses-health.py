#!/usr/bin/env python3
"""Perses Health Check.

Check Perses server connectivity, MCP server status,
percli availability, and auth token validity.

Usage:
    python3 scripts/perses-health.py [--url URL] [--verbose]
"""

import argparse
import json
import shutil
import subprocess
import sys


def check_percli():
    """Check if percli is installed and available."""
    path = shutil.which("percli")
    if path:
        try:
            result = subprocess.run(["percli", "version"], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return {"status": "error", "path": path, "error": result.stderr.strip() or "non-zero exit"}
            version = result.stdout.strip()
            return {"status": "ok", "path": path, "version": version}
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return {"status": "error", "path": path, "error": "failed to get version"}
    return {"status": "missing", "error": "percli not found in PATH"}


def check_auth():
    """Check if percli is authenticated."""
    try:
        result = subprocess.run(["percli", "whoami"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return {"status": "ok", "user": result.stdout.strip()}
        return {"status": "not_authenticated", "error": result.stderr.strip()}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"status": "error", "error": "percli not available"}


def check_server(url=None):
    """Check Perses server connectivity."""
    if not url:
        # Try to get URL from percli config
        try:
            result = subprocess.run(["percli", "config"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # percli is configured but we don't have the URL — report status only
                return {
                    "status": "unknown",
                    "error": "percli configured but no --url provided; pass --url to test connectivity",
                }
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    if not url:
        return {"status": "unknown", "error": "no URL provided and percli not configured"}

    try:
        import urllib.request

        req = urllib.request.Request(f"{url}/api/v1/projects", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                return {"status": "ok", "url": url}
            return {"status": "error", "url": url, "http_status": resp.status}
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as e:
        return {"status": "error", "url": url, "error": str(e)}


def check_mcp_server():
    """Check if perses-mcp-server is installed."""
    path = shutil.which("perses-mcp-server")
    if path:
        return {"status": "ok", "path": path}
    return {"status": "missing", "error": "perses-mcp-server not found in PATH"}


def main():
    parser = argparse.ArgumentParser(description="Perses health check")
    parser.add_argument("--url", help="Perses server URL")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    checks = {
        "percli": check_percli(),
        "auth": check_auth(),
        "server": check_server(args.url),
        "mcp_server": check_mcp_server(),
    }

    all_ok = all(c.get("status") == "ok" for c in checks.values())

    if args.verbose:
        print(json.dumps(checks, indent=2))
    else:
        for name, result in checks.items():
            status = result.get("status", "unknown")
            icon = "\u2713" if status == "ok" else "\u2717" if status in ("error", "missing") else "?"
            detail = result.get("error", result.get("version", result.get("user", result.get("url", ""))))
            print(f"  {icon} {name}: {status}" + (f" ({detail})" if detail else ""))

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
