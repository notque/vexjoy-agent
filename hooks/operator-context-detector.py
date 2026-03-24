#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SessionStart Hook: Operator Context Detection

Detects the operator context (personal, work, ci, production) based on
environment variables, git state, and project files. Injects the
appropriate behavioral profile into the session.

Detection Logic (first match wins):
1. CI=true / GITHUB_ACTIONS=true / GITLAB_CI=true env var -> ci
2. PRODUCTION=true env var or branch matches release/* or production -> production
3. /.dockerenv exists -> ci (ephemeral container)
4. OPERATOR_PROFILE env var set -> use that value directly
5. PROTECTED_ORGS env var or classify-repo.py detects protected org -> work
6. Default -> personal

Configuration:
- Set OPERATOR_PROFILE env var to override detection
- Set PROTECTED_ORGS env var (comma-separated) to define protected organizations
  Example: PROTECTED_ORGS="my-company,my-org-name"
- Or configure protected orgs in scripts/classify-repo.py

Output Format:
- [operator-context] Profile: {profile}
- [operator-context] Detection: {what matched}

Design Principles:
- Lightweight detection (env vars, file existence, git config read only)
- No subprocess calls (reads .git/config directly for remote detection)
- Non-blocking (always exits 0)
- Fast execution (<50ms target)
"""

import os
import re
import sys
import traceback
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output

EVENT_NAME = "SessionStart"

# Branch patterns indicating production context
PRODUCTION_BRANCH_PATTERN = re.compile(r"^(refs/heads/)?(release/|production$)")

# Profile-specific behavioral guidance
PROFILE_GUIDANCE = {
    "personal": (
        "Full autonomy. No approval gates. Branch safety only.\n"
        "- Create feature branches for changes (never commit to main)\n"
        "- No additional approval steps required\n"
        "- Learning database updates ungated"
    ),
    "work": (
        "Convention-enforced. APPROVE for production changes.\n"
        "- Follow team conventions (linting, naming, commit format)\n"
        "- APPROVE required before merging to main or deploying\n"
        "- Respect .editorconfig, .golangci.yaml, CI requirements\n"
        "- Check for CODEOWNERS before modifying shared files"
    ),
    "ci": (
        "Fully autonomous, disposable environment. Database ungated.\n"
        "- Environment is ephemeral; no persistent state expected\n"
        "- Skip interactive prompts and confirmations\n"
        "- Optimize for deterministic, reproducible output\n"
        "- Exit codes matter; failures must be explicit"
    ),
    "production": (
        "Maximum gates. APPROVE mandatory. SNAPSHOT before changes.\n"
        "- APPROVE required before ANY file modification\n"
        "- Create snapshot/backup before destructive operations\n"
        "- Double-verify all commands before execution\n"
        "- Prefer read-only operations; mutate only when confirmed"
    ),
}


def detect_ci_environment() -> str | None:
    """
    Detect CI/CD environment via standard env vars.

    Returns:
        Detection reason string, or None if not CI.
    """
    ci_vars = {
        "CI": "CI=true",
        "GITHUB_ACTIONS": "GITHUB_ACTIONS=true",
        "GITLAB_CI": "GITLAB_CI=true",
    }
    for var, label in ci_vars.items():
        if os.environ.get(var, "").lower() == "true":
            return label
    return None


def detect_production_context() -> str | None:
    """
    Detect production context via env var or branch name.

    Reads branch from .git/HEAD directly (no subprocess).

    Returns:
        Detection reason string, or None if not production.
    """
    if os.environ.get("PRODUCTION", "").lower() == "true":
        return "PRODUCTION=true"

    # Read current branch from .git/HEAD
    branch = _read_git_branch()
    if branch and PRODUCTION_BRANCH_PATTERN.search(branch):
        return f"branch={branch}"

    return None


def detect_docker_container() -> bool:
    """Check if running inside a Docker container."""
    return Path("/.dockerenv").exists()


def _get_protected_orgs() -> list[str]:
    """
    Get list of protected organization name patterns.

    Reads from PROTECTED_ORGS env var (comma-separated).
    Returns lowercase patterns for case-insensitive matching.
    """
    orgs_env = os.environ.get("PROTECTED_ORGS", "").strip()
    if not orgs_env:
        return []
    return [org.strip().lower() for org in orgs_env.split(",") if org.strip()]


def detect_protected_org() -> str | None:
    """
    Detect if the current repo belongs to a protected organization.

    Checks git remote URL against PROTECTED_ORGS env var patterns.

    Returns:
        Detection reason string, or None if not a protected org.
    """
    protected_orgs = _get_protected_orgs()
    if not protected_orgs:
        return None

    # Check git remote
    remote_url = _read_git_remote()
    if not remote_url:
        return None

    remote_lower = remote_url.lower()
    for org in protected_orgs:
        if org in remote_lower:
            return f"git remote matches protected org '{org}' ({remote_url})"

    return None


def _read_git_branch() -> str | None:
    """
    Read current git branch from .git/HEAD directly.

    No subprocess call. Returns branch name or None.
    """
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents[:3]):
        head_file = parent / ".git" / "HEAD"
        if head_file.is_file():
            try:
                content = head_file.read_text(encoding="utf-8").strip()
                if content.startswith("ref: refs/heads/"):
                    return content[len("ref: refs/heads/") :]
                # Detached HEAD (commit hash) - not a branch
                return None
            except OSError:
                return None
    return None


def _read_git_remote() -> str | None:
    """
    Read the origin remote URL from .git/config directly.

    No subprocess call. Returns URL string or None.
    """
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents[:3]):
        git_config = parent / ".git" / "config"
        if git_config.is_file():
            try:
                content = git_config.read_text(encoding="utf-8", errors="replace")
                # Match [remote "origin"] section's url line
                match = re.search(
                    r'\[remote\s+"origin"\]\s*\n(?:\s+\w+\s*=.*\n)*?\s+url\s*=\s*(\S+)',
                    content,
                )
                if match:
                    return match.group(1)
            except OSError:
                pass
            return None
    return None


def detect_profile() -> tuple[str, str]:
    """
    Detect the operator profile. First match wins.

    Returns:
        Tuple of (profile_name, detection_reason).
    """
    # 1. CI environment
    ci_reason = detect_ci_environment()
    if ci_reason:
        return "ci", ci_reason

    # 2. Production context
    prod_reason = detect_production_context()
    if prod_reason:
        return "production", prod_reason

    # 3. Docker container -> ci
    if detect_docker_container():
        return "ci", "/.dockerenv exists (ephemeral container)"

    # 4. Explicit override
    explicit = os.environ.get("OPERATOR_PROFILE", "").strip()
    if explicit:
        return explicit, f"OPERATOR_PROFILE={explicit}"

    # 5. Protected organization -> work
    org_reason = detect_protected_org()
    if org_reason:
        return "work", org_reason

    # 6. Default
    return "personal", "default (no signals detected)"


def get_profile_injection(profile: str, detection: str) -> str:
    """Build the context injection string for the detected profile."""
    guidance = PROFILE_GUIDANCE.get(profile, PROFILE_GUIDANCE["personal"])

    return f"""[operator-context] Profile: {profile}
[operator-context] Detection: {detection}

Operator Profile: {profile}
- personal: Full autonomy. No approval gates. Branch safety only.
- work: Convention-enforced. APPROVE for production changes.
- ci: Fully autonomous, disposable environment. Database ungated.
- production: Maximum gates. APPROVE mandatory. SNAPSHOT before changes.

Current profile ({profile}) means:
{guidance}
"""


def main():
    """Main entry point for the hook."""
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    try:
        profile, detection = detect_profile()

        if debug:
            print(
                f"[operator-context] Detected profile: {profile} ({detection})",
                file=sys.stderr,
            )

        injection = get_profile_injection(profile, detection)
        context_output(EVENT_NAME, injection).print_and_exit()

    except Exception as e:
        if debug:
            print(f"[operator-context] Error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"[operator-context] Error: {type(e).__name__}: {e}", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    main()
