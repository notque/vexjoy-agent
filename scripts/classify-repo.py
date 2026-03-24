#!/usr/bin/env python3
"""
Deterministic repo classification for PR workflow routing.

Classifies the current git repository as 'protected-org' or 'personal' based on
the GitHub remote URL. Protected-org repos (configured via PROTECTED_ORGS env var)
get human-gated PR workflows. All others get automated review-fix loops.

Also detects the primary language/domain of the repository for router skill gating.

Configuration:
    Set PROTECTED_ORGS env var (comma-separated) to define protected organizations.
    Example: PROTECTED_ORGS="my-company,acme-corp"
    When PROTECTED_ORGS is not set, all repos classify as personal.

Usage:
    python3 scripts/classify-repo.py                # JSON output (includes domain)
    python3 scripts/classify-repo.py --human        # Human-readable
    python3 scripts/classify-repo.py --type-only    # Just "protected-org" or "personal"
    python3 scripts/classify-repo.py --domain       # Just the domain string
    python3 scripts/classify-repo.py --check-protected  # Exit 0 if protected, 1 if not

Exit codes:
    0 = success (or repo is protected when --check-protected)
    1 = error (or repo is not protected when --check-protected)
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def _get_git_root() -> Path | None:
    """Get the root directory of the current git repository.

    Returns:
        Path to the git root, or None if not in a git repo.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def get_remote_url(remote: str = "origin") -> str | None:
    """Get the URL of a git remote.

    Args:
        remote: Name of the git remote to query.

    Returns:
        The remote URL string, or None if not found.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", remote],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        stderr_msg = result.stderr.strip()
        if stderr_msg:
            print(f"classify-repo: git remote get-url {remote}: {stderr_msg}", file=sys.stderr)
    except FileNotFoundError:
        print("classify-repo: git not found in PATH", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(f"classify-repo: git remote get-url {remote} timed out", file=sys.stderr)
    return None


def _get_protected_orgs() -> list[str]:
    """Get list of protected organization name patterns from env var.

    Returns lowercase patterns for case-insensitive matching.
    Returns empty list when PROTECTED_ORGS is not set — configure via env var
    or Fish config: set -gx PROTECTED_ORGS "org1,org2"
    """
    orgs_env = os.environ.get("PROTECTED_ORGS", "").strip()
    if not orgs_env:
        return []
    return [org.strip().lower() for org in orgs_env.split(",") if org.strip()]


def classify_repo(remote_url: str | None) -> dict[str, str | None]:
    """Classify a repo based on its remote URL.

    Args:
        remote_url: The git remote URL to classify.

    Returns:
        Dict with keys:
            type: "protected-org" | "personal" | "unknown"
            org: extracted org name or None
            reason: why this classification was chosen
    """
    if not remote_url:
        return {"type": "unknown", "org": None, "reason": "No remote URL found"}

    # Extract org from GitHub URL patterns:
    # https://github.com/ORG/repo.git
    # git@github.com:ORG/repo.git
    org_match = re.search(r"github\.com[:/]([^/]+)/", remote_url)
    if not org_match:
        return {"type": "personal", "org": None, "reason": f"Non-GitHub remote: {remote_url}"}

    org = org_match.group(1)

    # Check against protected organizations from env var
    protected_orgs = _get_protected_orgs()
    for protected_org in protected_orgs:
        if protected_org in org.lower():
            return {"type": "protected-org", "org": org, "reason": f"Protected org detected: {org}"}

    return {"type": "personal", "org": org, "reason": f"Non-protected org: {org}"}


def detect_domain(root: Path | None = None) -> dict:
    """Detect the primary language/domain of a repository.

    Checks for well-known project files at the repo root to determine
    the primary language. Also detects if this is a claude-code-toolkit repo.

    Args:
        root: Repository root path. Auto-detected from git if None.

    Returns:
        Dict with keys:
            domain: "go" | "typescript" | "javascript" | "python" | "hugo" | "general"
            is_toolkit: True if skills/INDEX.json exists (claude-code-toolkit repo)
    """
    if root is None:
        root = _get_git_root()
    if root is None:
        return {"domain": "general", "is_toolkit": False}

    is_toolkit = (root / "skills" / "INDEX.json").is_file()

    # Go
    if (root / "go.mod").is_file():
        return {"domain": "go", "is_toolkit": is_toolkit}

    # Node.js / TypeScript / JavaScript
    if (root / "package.json").is_file():
        # Check for TypeScript indicators
        if (root / "tsconfig.json").is_file():
            return {"domain": "typescript", "is_toolkit": is_toolkit}
        return {"domain": "javascript", "is_toolkit": is_toolkit}

    # Python
    if (root / "pyproject.toml").is_file() or (root / "setup.py").is_file():
        return {"domain": "python", "is_toolkit": is_toolkit}

    # Hugo
    if (root / "hugo.toml").is_file() or (root / "hugo.yaml").is_file():
        return {"domain": "hugo", "is_toolkit": is_toolkit}
    if (root / "config.toml").is_file() and (root / "content").is_dir():
        return {"domain": "hugo", "is_toolkit": is_toolkit}

    return {"domain": "general", "is_toolkit": is_toolkit}


def main() -> None:
    """Parse arguments and output repo classification."""
    parser = argparse.ArgumentParser(description="Classify git repo for PR workflow routing")
    parser.add_argument("--human", action="store_true", help="Human-readable output")
    parser.add_argument("--type-only", action="store_true", help="Print just the type")
    parser.add_argument("--domain", action="store_true", help="Print just the domain string")
    parser.add_argument("--check-protected", action="store_true", help="Exit 0 if protected-org, 1 if not")
    parser.add_argument("--remote", default="origin", help="Git remote name (default: origin)")
    args = parser.parse_args()

    remote_url = get_remote_url(args.remote)
    result = classify_repo(remote_url)
    domain_info = detect_domain()

    if args.check_protected:
        sys.exit(0 if result["type"] == "protected-org" else 1)
    elif args.type_only:
        print(result["type"])
    elif args.domain:
        print(domain_info["domain"])
    elif args.human:
        print(f"Repo Type: {result['type']}")
        if result["org"]:
            print(f"Org: {result['org']}")
        print(f"Domain: {domain_info['domain']}")
        print(f"Is Toolkit: {domain_info['is_toolkit']}")
        print(f"Reason: {result['reason']}")
    else:
        result["domain"] = domain_info["domain"]
        result["is_toolkit"] = domain_info["is_toolkit"]
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"classify-repo: unexpected error: {e}", file=sys.stderr)
        sys.exit(2)
