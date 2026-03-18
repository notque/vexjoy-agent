#!/usr/bin/env python3
"""
Branch name validation script for branch-naming skill.

Validates Git branch names against repository conventions.
"""

__version__ = "1.0.0"

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Valid branch prefixes (from conventional commits)
VALID_PREFIXES = [
    "feature/",
    "fix/",
    "docs/",
    "style/",
    "refactor/",
    "perf/",
    "test/",
    "build/",
    "ci/",
    "chore/",
    "revert/",
]


class BranchNameValidator:
    """Validate branch names against conventions."""

    def __init__(
        self, max_length: int = 50, allowed_prefixes: Optional[List[str]] = None, check_duplicates: bool = False
    ):
        self.max_length = max_length
        self.allowed_prefixes = allowed_prefixes or VALID_PREFIXES
        self.check_duplicates = check_duplicates

    def validate_format(self, branch_name: str) -> Tuple[bool, List[Dict]]:
        """
        Validate branch name format.

        Checks:
        - Has valid prefix
        - Subject is kebab-case
        - Length <= max_length
        - Only allowed characters (a-z, 0-9, -)

        Returns:
            (is_valid, list_of_issues)
        """
        issues = []

        # Check if branch_name has a prefix
        has_prefix = "/" in branch_name
        if not has_prefix:
            issues.append(
                {
                    "type": "missing_prefix",
                    "message": "Branch name missing prefix (feature/, fix/, etc.)",
                    "suggestion": f"Add prefix: feature/{branch_name}",
                }
            )
            return False, issues

        # Extract prefix and subject
        parts = branch_name.split("/", 1)
        prefix = parts[0] + "/"
        subject = parts[1] if len(parts) > 1 else ""

        # Check if prefix is valid
        if prefix not in self.allowed_prefixes:
            issues.append(
                {
                    "type": "invalid_prefix",
                    "message": f"Invalid prefix: {prefix}",
                    "prefix": prefix,
                    "allowed_prefixes": self.allowed_prefixes,
                    "suggestion": f"Use one of: {', '.join(self.allowed_prefixes)}",
                }
            )

        # Check subject exists
        if not subject:
            issues.append(
                {
                    "type": "empty_subject",
                    "message": "Branch name has no subject after prefix",
                    "suggestion": "Provide description: feature/add-feature",
                }
            )
            return False, issues

        # Check for uppercase letters
        if any(c.isupper() for c in branch_name):
            uppercase_chars = [c for c in branch_name if c.isupper()]
            issues.append(
                {
                    "type": "case_error",
                    "message": f"Branch name contains uppercase letters: {branch_name}",
                    "uppercase_chars": uppercase_chars,
                    "suggestion": f"Use lowercase: {branch_name.lower()}",
                }
            )

        # Check for underscores
        if "_" in subject:
            issues.append(
                {
                    "type": "invalid_character",
                    "message": f"Branch name contains underscores: {subject}",
                    "character": "_",
                    "suggestion": f"Replace underscores with hyphens: {subject.replace('_', '-')}",
                }
            )

        # Check for invalid characters (only a-z, 0-9, - allowed in subject)
        invalid_chars = re.findall(r"[^a-z0-9-]", subject)
        if invalid_chars:
            issues.append(
                {
                    "type": "invalid_characters",
                    "message": f"Branch name contains invalid characters: {', '.join(set(invalid_chars))}",
                    "invalid_chars": list(set(invalid_chars)),
                    "suggestion": "Only a-z, 0-9, and hyphens allowed",
                }
            )

        # Check for leading/trailing hyphens in subject
        if subject.startswith("-") or subject.endswith("-"):
            issues.append(
                {
                    "type": "hyphen_position",
                    "message": "Subject has leading or trailing hyphens",
                    "suggestion": f"Remove: {subject.strip('-')}",
                }
            )

        # Check for multiple consecutive hyphens
        if "--" in subject:
            issues.append(
                {
                    "type": "multiple_hyphens",
                    "message": "Subject has multiple consecutive hyphens",
                    "suggestion": f"Collapse hyphens: {re.sub(r'-+', '-', subject)}",
                }
            )

        # Check length
        if len(branch_name) > self.max_length:
            issues.append(
                {
                    "type": "exceeds_max_length",
                    "message": f"Branch name too long: {len(branch_name)} chars (limit: {self.max_length})",
                    "length": len(branch_name),
                    "max_length": self.max_length,
                    "suggestion": f"Shorten by {len(branch_name) - self.max_length} characters",
                }
            )

        return len(issues) == 0, issues

    def check_duplicate_branches(self, branch_name: str) -> Dict:
        """
        Check if branch name already exists locally or remotely.

        Returns:
            {
                'duplicate_found': bool,
                'local_exists': bool,
                'remote_exists': bool,
                'alternatives': list (if duplicate found)
            }
        """
        result = {"duplicate_found": False, "local_exists": False, "remote_exists": False, "alternatives": []}

        # Check local branches
        try:
            local_check = subprocess.run(
                ["git", "branch", "--list", branch_name], capture_output=True, text=True, timeout=5
            )
            result["local_exists"] = bool(local_check.stdout.strip())
        except Exception:
            pass  # Git command failed, skip local check

        # Check remote branches
        try:
            remote_check = subprocess.run(
                ["git", "ls-remote", "--heads", "origin", f"refs/heads/{branch_name}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            result["remote_exists"] = bool(remote_check.stdout.strip())
        except Exception:
            pass  # Git command failed, skip remote check

        # Generate alternatives if duplicate found
        if result["local_exists"] or result["remote_exists"]:
            result["duplicate_found"] = True
            result["alternatives"] = self.generate_alternatives(branch_name)

        return result

    def generate_alternatives(self, branch_name: str) -> List[str]:
        """Generate alternative branch names for duplicates."""
        alternatives = []

        # Extract prefix and subject
        if "/" in branch_name:
            prefix, subject = branch_name.split("/", 1)
            prefix += "/"
        else:
            prefix = "feature/"
            subject = branch_name

        # Alternative 1: Version suffix
        alternatives.append(f"{prefix}{subject}-v2")

        # Alternative 2: Semantic suffix
        alternatives.append(f"{prefix}{subject}-alt")

        # Alternative 3: Timestamp suffix
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d")
        alternatives.append(f"{prefix}{subject}-{timestamp}")

        return alternatives

    def validate(self, branch_name: str) -> Dict:
        """
        Comprehensive validation.

        Returns:
            {
                'valid': bool,
                'branch_name': str,
                'format_valid': bool,
                'issues': list,
                'duplicate_check': dict (if check_duplicates enabled)
            }
        """
        # Format validation
        format_valid, issues = self.validate_format(branch_name)

        result = {"valid": format_valid, "branch_name": branch_name, "format_valid": format_valid, "issues": issues}

        # Extract prefix and subject for result
        if "/" in branch_name:
            parts = branch_name.split("/", 1)
            result["prefix"] = parts[0] + "/"
            result["subject"] = parts[1] if len(parts) > 1 else ""
            result["length"] = len(branch_name)

        # Duplicate check if enabled
        if self.check_duplicates and format_valid:
            duplicate_check = self.check_duplicate_branches(branch_name)
            result["duplicate_check"] = duplicate_check

            if duplicate_check["duplicate_found"]:
                result["valid"] = False
                issues.append(
                    {
                        "type": "duplicate_branch",
                        "message": f'Branch "{branch_name}" already exists',
                        "local": duplicate_check["local_exists"],
                        "remote": duplicate_check["remote_exists"],
                        "alternatives": duplicate_check["alternatives"],
                    }
                )

        return result


def load_repository_config(config_path: Optional[Path] = None) -> Optional[Dict]:
    """Load repository branch naming config from .branch-naming.json."""
    if config_path and config_path.exists():
        with open(config_path, "r") as f:
            return json.load(f)

    # Try default location
    default_config = Path(".branch-naming.json")
    if default_config.exists():
        with open(default_config, "r") as f:
            return json.load(f)

    return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate Git branch names against repository conventions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Required arguments
    parser.add_argument("--branch-name", type=str, required=True, help="Branch name to validate")

    # Validation options
    parser.add_argument(
        "--check-duplicates", action="store_true", help="Check if branch already exists (local and remote)"
    )
    parser.add_argument("--max-length", type=int, default=50, help="Maximum branch name length (default: 50)")
    parser.add_argument("--config", type=Path, help="Path to .branch-naming.json config file")

    # Output options
    parser.add_argument("--quiet", action="store_true", help="Quiet mode (only exit code, no output)")
    parser.add_argument(
        "--output-format", choices=["json", "text"], default="json", help="Output format (default: json)"
    )

    args = parser.parse_args()

    try:
        # Load repository config
        config = load_repository_config(args.config)
        allowed_prefixes = None
        max_length = args.max_length

        if config:
            if "allowed_prefixes" in config:
                allowed_prefixes = config["allowed_prefixes"]
            if "max_length" in config:
                max_length = config["max_length"]

        # Create validator
        validator = BranchNameValidator(
            max_length=max_length, allowed_prefixes=allowed_prefixes, check_duplicates=args.check_duplicates
        )

        # Validate branch name
        result = validator.validate(args.branch_name)

        # Output result
        if args.quiet:
            # Quiet mode - only exit code
            sys.exit(0 if result["valid"] else 1)

        if args.output_format == "json":
            print(json.dumps(result, indent=2))
        else:
            # Text format
            if result["valid"]:
                print(f"✓ Branch name valid: {args.branch_name}")
            else:
                print(f"✗ Branch name invalid: {args.branch_name}")
                print(f"\nIssues found: {len(result['issues'])}")
                for issue in result["issues"]:
                    print(f"  - [{issue['type']}] {issue['message']}")
                    if "suggestion" in issue:
                        print(f"    Suggestion: {issue['suggestion']}")

                if "duplicate_check" in result and result["duplicate_check"]["duplicate_found"]:
                    print("\nAlternative names:")
                    for alt in result["duplicate_check"]["alternatives"]:
                        print(f"  - {alt}")

        sys.exit(0 if result["valid"] else 1)

    except Exception as e:
        if not args.quiet:
            print(
                json.dumps({"error": "validation_failed", "error_type": type(e).__name__, "message": str(e)}, indent=2),
                file=sys.stderr,
            )
        sys.exit(2)


if __name__ == "__main__":
    main()
