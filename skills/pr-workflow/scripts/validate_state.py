#!/usr/bin/env python3
"""
Git working tree state validation script.

Validates:
- Working tree state (merge, rebase, detached HEAD)
- Sensitive file patterns
- CLAUDE.md parsing and rule extraction
- Branch state analysis
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Sensitive file patterns (regex)
SENSITIVE_PATTERNS = [
    # Environment files
    (r"\.env$", "Environment file", "critical"),
    (r"\.env\..*", "Environment file pattern (.env.*)", "critical"),
    (r".*\.env$", "Environment file pattern (*.env)", "critical"),
    # Credentials and secrets
    (r".*credentials.*", "Credentials in filename", "critical"),
    (r".*secret.*", "Secret in filename", "critical"),
    (r".*password.*", "Password in filename", "critical"),
    (r".*apikey.*", "API key in filename", "critical"),
    (r".*api[_-]key.*", "API key in filename", "critical"),
    # Certificate files
    (r".*\.pem$", "PEM certificate file", "critical"),
    (r".*\.key$", "Private key file", "critical"),
    (r".*\.p12$", "P12 certificate file", "critical"),
    (r".*\.pfx$", "PFX certificate file", "critical"),
    # Package manager auth
    (r"\.npmrc$", "NPM authentication config", "critical"),
    (r"\.pypirc$", "PyPI authentication config", "critical"),
    (r"\.netrc$", "Network authentication config", "critical"),
    # Cloud provider credentials
    (r".*aws.*credentials.*", "AWS credentials file", "critical"),
    (r".*gcp.*credentials.*", "GCP credentials file", "critical"),
    (r".*azure.*credentials.*", "Azure credentials file", "critical"),
    # SSH keys
    (r"id_rsa$", "SSH private key", "critical"),
    (r"id_dsa$", "SSH private key", "critical"),
    (r"id_ed25519$", "SSH private key", "critical"),
    # Database
    (r".*\.sql\.gz$", "Compressed database dump", "warning"),
    (r".*dump\.sql$", "Database dump file", "warning"),
]

# Default banned patterns in commit messages
DEFAULT_BANNED_PATTERNS = [
    "Generated with Claude Code",
    "Co-Authored-By: Claude",
    "🤖 Generated",
    "AI-generated",
    "Automated commit by AI",
]


class ValidationError(Exception):
    """Custom exception for validation errors."""

    pass


def run_git_command(args: List[str], check: bool = True) -> Tuple[int, str, str]:
    """
    Run git command and return (exit_code, stdout, stderr).

    Args:
        args: Git command arguments (without 'git' prefix)
        check: Raise CalledProcessError if exit code non-zero

    Returns:
        (exit_code, stdout, stderr)
    """
    try:
        result = subprocess.run(["git"] + args, capture_output=True, text=True, check=check)
        return result.returncode, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        if check:
            raise
        return e.returncode, e.stdout if e.stdout else "", e.stderr if e.stderr else ""


def validate_working_tree() -> Dict[str, Any]:
    """
    Validate working tree state.

    Returns:
        {
            "status": "clean" | "merge_in_progress" | "rebase_in_progress" | "detached_head",
            "branch": "branch-name" | "HEAD",
            "detached": bool,
            "merge_in_progress": bool,
            "rebase_in_progress": bool,
            "clean": bool
        }
    """
    result = {"detached": False, "merge_in_progress": False, "rebase_in_progress": False, "clean": True}

    # Check current branch
    exit_code, branch, stderr = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], check=False)
    if exit_code != 0:
        raise ValidationError(f"Failed to get current branch: {stderr}")

    branch = branch.strip()
    result["branch"] = branch

    # Check if detached HEAD
    if branch == "HEAD":
        result["detached"] = True
        result["clean"] = False
        result["status"] = "detached_head"

    # Check for merge in progress
    git_dir = Path(".git")
    if not git_dir.exists():
        # Try to find git dir
        exit_code, git_dir_path, _ = run_git_command(["rev-parse", "--git-dir"], check=False)
        if exit_code == 0:
            git_dir = Path(git_dir_path.strip())

    if (git_dir / "MERGE_HEAD").exists():
        result["merge_in_progress"] = True
        result["clean"] = False
        result["status"] = "merge_in_progress"

    # Check for rebase in progress
    if (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
        result["rebase_in_progress"] = True
        result["clean"] = False
        result["status"] = "rebase_in_progress"

    # If no issues, status is clean
    if result["clean"]:
        result["status"] = "clean"

    return result


def get_changed_files(staged_only: bool = False) -> List[str]:
    """
    Get list of changed files.

    Args:
        staged_only: Only return staged files

    Returns:
        List of file paths
    """
    if staged_only:
        # Get staged files only
        exit_code, output, stderr = run_git_command(["diff", "--cached", "--name-only"], check=False)
    else:
        # Get all changed files (staged and unstaged)
        exit_code, output, stderr = run_git_command(["status", "--porcelain"], check=False)

    if exit_code != 0:
        raise ValidationError(f"Failed to get changed files: {stderr}")

    if staged_only:
        return [line.strip() for line in output.split("\n") if line.strip()]
    else:
        # Parse porcelain format
        files = []
        for line in output.split("\n"):
            if line.strip():
                # Format: "XY filename"
                # Skip first 3 characters (status + space)
                if len(line) > 3:
                    files.append(line[3:].strip())
        return files


def validate_sensitive_files(staged_only: bool = False) -> Dict[str, Any]:
    """
    Scan files for sensitive patterns.

    Args:
        staged_only: Only scan staged files

    Returns:
        {
            "sensitive_files_found": bool,
            "scanned_files": int,
            "sensitive_files": [
                {
                    "path": "file/path",
                    "reason": "Pattern description",
                    "severity": "critical" | "warning"
                }
            ],
            "clean": bool
        }
    """
    files = get_changed_files(staged_only=staged_only)
    sensitive_files = []

    for file_path in files:
        # Check each pattern
        for pattern, reason, severity in SENSITIVE_PATTERNS:
            if re.search(pattern, file_path, re.IGNORECASE):
                sensitive_files.append({"path": file_path, "reason": reason, "severity": severity, "pattern": pattern})
                break  # Only report first matching pattern per file

    return {
        "sensitive_files_found": len(sensitive_files) > 0,
        "scanned_files": len(files),
        "sensitive_files": sensitive_files,
        "clean": len(sensitive_files) == 0,
    }


def find_claude_md() -> Optional[Path]:
    """
    Find CLAUDE.md file.

    Search order:
    1. Current directory
    2. Git repository root
    3. ~/.claude/CLAUDE.md

    Returns:
        Path to CLAUDE.md or None
    """
    # Check current directory
    if Path("CLAUDE.md").exists():
        return Path("CLAUDE.md")

    # Check git repository root
    exit_code, git_root, _ = run_git_command(["rev-parse", "--show-toplevel"], check=False)
    if exit_code == 0:
        repo_claude = Path(git_root.strip()) / "CLAUDE.md"
        if repo_claude.exists():
            return repo_claude

    # Check global CLAUDE.md
    global_claude = Path.home() / ".claude" / "CLAUDE.md"
    if global_claude.exists():
        return global_claude

    return None


def parse_claude_md(claude_md_path: Path) -> Dict[str, Any]:
    """
    Parse CLAUDE.md file to extract commit message rules.

    Args:
        claude_md_path: Path to CLAUDE.md

    Returns:
        {
            "claude_md_found": bool,
            "path": str,
            "banned_patterns": List[str],
            "conventional_commits_required": bool,
            "custom_rules": List[str]
        }
    """
    if not claude_md_path or not claude_md_path.exists():
        return {
            "claude_md_found": False,
            "using_defaults": True,
            "banned_patterns": DEFAULT_BANNED_PATTERNS.copy(),
            "conventional_commits_required": False,
            "custom_rules": [],
        }

    result = {
        "claude_md_found": True,
        "path": str(claude_md_path),
        "banned_patterns": DEFAULT_BANNED_PATTERNS.copy(),  # Always include defaults
        "conventional_commits_required": False,
        "custom_rules": [],
    }

    try:
        with open(claude_md_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Look for Git Commit Style section
        if "## Git Commit Style" in content:
            # Extract section
            section_start = content.find("## Git Commit Style")
            section_end = content.find("\n## ", section_start + 1)
            if section_end == -1:
                section_end = len(content)

            section = content[section_start:section_end]

            # Look for banned patterns
            if "Do NOT add" in section or "IMPORTANT" in section:
                # Extract explicit prohibitions
                lines = section.split("\n")
                for line in lines:
                    if "Do NOT add" in line or "prohibited" in line.lower():
                        result["custom_rules"].append(line.strip("- ").strip())

            # Check for conventional commit requirement
            if "conventional commit" in section.lower():
                result["conventional_commits_required"] = True

    except Exception as e:
        # If parsing fails, return defaults
        result["parse_error"] = str(e)

    return result


def validate_claude_md() -> Dict[str, Any]:
    """
    Load and parse CLAUDE.md.

    Returns:
        CLAUDE.md parsing result
    """
    claude_md_path = find_claude_md()
    return parse_claude_md(claude_md_path)


def detect_branch_state() -> Dict[str, Any]:
    """
    Detect current branch and its state.

    Returns:
        {
            "branch": str,
            "is_main_branch": bool,
            "is_feature_branch": bool,
            "branch_type": str,
            "requires_confirmation": bool
        }
    """
    exit_code, branch, stderr = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], check=False)
    if exit_code != 0:
        raise ValidationError(f"Failed to get branch: {stderr}")

    branch = branch.strip()

    # Check if main/master branch
    is_main = branch in ["main", "master"]

    # Check if feature branch
    is_feature = any(
        branch.startswith(prefix) for prefix in ["feature/", "fix/", "docs/", "refactor/", "test/", "chore/"]
    )

    # Determine branch type
    if is_main:
        branch_type = "main"
    elif is_feature:
        branch_type = "feature"
    else:
        branch_type = "other"

    return {
        "branch": branch,
        "is_main_branch": is_main,
        "is_feature_branch": is_feature,
        "branch_type": branch_type,
        "requires_confirmation": is_main,  # Require confirmation for main branch commits
    }


def validate_all(staged_only: bool = False) -> Dict[str, Any]:
    """
    Run all validations.

    Args:
        staged_only: Only check staged files for sensitive patterns

    Returns:
        Combined validation results
    """
    results = {
        "working_tree": validate_working_tree(),
        "sensitive_files": validate_sensitive_files(staged_only=staged_only),
        "claude_md": validate_claude_md(),
        "branch_state": detect_branch_state(),
    }

    # Determine overall status
    all_clean = results["working_tree"]["clean"] and results["sensitive_files"]["clean"]

    results["overall_status"] = "clean" if all_clean else "issues_found"
    results["can_proceed"] = all_clean

    return results


def format_validation_report(results: Dict[str, Any]) -> str:
    """Format validation results as human-readable report."""
    lines = []
    lines.append("=" * 60)
    lines.append(" VALIDATION REPORT")
    lines.append("=" * 60)
    lines.append("")

    # Working Tree
    lines.append("Working Tree State:")
    lines.append("-" * 60)
    wt = results["working_tree"]
    status_symbol = "✓" if wt["clean"] else "✗"
    lines.append(f"  {status_symbol} Status: {wt['status']}")
    lines.append(f"  {status_symbol} Branch: {wt['branch']}")
    if wt["detached"]:
        lines.append("  ⚠ WARNING: Detached HEAD state")
    if wt["merge_in_progress"]:
        lines.append("  ✗ ERROR: Merge in progress - complete or abort merge first")
    if wt["rebase_in_progress"]:
        lines.append("  ✗ ERROR: Rebase in progress - complete or abort rebase first")
    lines.append("")

    # Sensitive Files
    lines.append("Sensitive Files Check:")
    lines.append("-" * 60)
    sf = results["sensitive_files"]
    status_symbol = "✓" if sf["clean"] else "✗"
    lines.append(f"  {status_symbol} Scanned: {sf['scanned_files']} files")

    if sf["sensitive_files_found"]:
        lines.append(f"  ✗ CRITICAL: {len(sf['sensitive_files'])} sensitive files detected")
        for item in sf["sensitive_files"]:
            lines.append(f"    - {item['path']}")
            lines.append(f"      Reason: {item['reason']}")
            lines.append(f"      Severity: {item['severity']}")
    else:
        lines.append("  ✓ No sensitive files detected")
    lines.append("")

    # CLAUDE.md
    lines.append("CLAUDE.md Compliance:")
    lines.append("-" * 60)
    cm = results["claude_md"]
    if cm["claude_md_found"]:
        lines.append(f"  ✓ Found: {cm['path']}")
        lines.append(f"  ✓ Banned patterns loaded: {len(cm['banned_patterns'])} patterns")
        lines.append(f"  ✓ Conventional commits: {'required' if cm['conventional_commits_required'] else 'optional'}")
    else:
        lines.append("  ⚠ CLAUDE.md not found - using defaults")
        lines.append(f"  ✓ Default banned patterns: {len(cm['banned_patterns'])} patterns")
    lines.append("")

    # Branch State
    lines.append("Branch State:")
    lines.append("-" * 60)
    bs = results["branch_state"]
    lines.append(f"  ✓ Current branch: {bs['branch']}")
    lines.append(f"  ✓ Branch type: {bs['branch_type']}")
    if bs["requires_confirmation"]:
        lines.append("  ⚠ WARNING: Committing to main/master branch")
        lines.append("    Consider using feature branch instead")
    lines.append("")

    # Overall Status
    lines.append("=" * 60)
    if results["can_proceed"]:
        lines.append(" VALIDATION PASSED - OK to proceed")
    else:
        lines.append(" VALIDATION FAILED - Address issues before proceeding")
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Validate git working tree state and environment")
    parser.add_argument(
        "--check",
        choices=["all", "working-tree", "sensitive-files", "claude-md", "branch-state"],
        default="all",
        help="Which validation to run",
    )
    parser.add_argument("--staged-only", action="store_true", help="Only check staged files for sensitive patterns")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    try:
        # Run requested validation
        if args.check == "all":
            results = validate_all(staged_only=args.staged_only)
        elif args.check == "working-tree":
            results = validate_working_tree()
        elif args.check == "sensitive-files":
            results = validate_sensitive_files(staged_only=args.staged_only)
        elif args.check == "claude-md":
            results = validate_claude_md()
        elif args.check == "branch-state":
            results = detect_branch_state()

        # Output results
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            if args.check == "all":
                print(format_validation_report(results))
            else:
                print(json.dumps(results, indent=2))

        # Exit code
        if args.check == "all":
            sys.exit(0 if results["can_proceed"] else 1)
        elif args.check == "sensitive-files" or args.check == "working-tree":
            sys.exit(0 if results["clean"] else 1)
        else:
            sys.exit(0)

    except ValidationError as e:
        print(
            json.dumps({"status": "error", "error_type": "ValidationError", "message": str(e)}, indent=2),
            file=sys.stderr,
        )
        sys.exit(2)
    except Exception as e:
        print(
            json.dumps({"status": "error", "error_type": type(e).__name__, "message": str(e)}, indent=2),
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
