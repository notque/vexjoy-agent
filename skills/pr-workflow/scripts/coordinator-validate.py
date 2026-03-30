#!/usr/bin/env python3
"""
Validation script for pr-mining-coordinator skill.
Tests skill structure and verifies prerequisites.
"""

import sys
from pathlib import Path
from typing import List, Tuple


def validate_skill_structure() -> List[Tuple[str, bool, str]]:
    """Validate skill directory structure."""
    results = []
    skill_dir = Path(__file__).parent.parent

    # Check required files
    required_files = [
        "SKILL.md",
        "references/mining-commands.md",
        "references/reviewer-usernames.md",
        "references/pattern-categories.md",
    ]

    for file_path in required_files:
        full_path = skill_dir / file_path
        exists = full_path.exists()
        results.append(
            (
                f"File exists: {file_path}",
                exists,
                f"Missing required file: {file_path}" if not exists else "OK",
            )
        )

    return results


def validate_yaml_frontmatter() -> List[Tuple[str, bool, str]]:
    """Validate SKILL.md YAML frontmatter."""
    results = []
    skill_dir = Path(__file__).parent.parent
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        return [("YAML frontmatter validation", False, "SKILL.md not found")]

    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for YAML frontmatter
    if not content.startswith("---"):
        results.append(("YAML frontmatter exists", False, "Missing opening ---"))
        return results

    # Extract frontmatter
    parts = content.split("---", 2)
    if len(parts) < 3:
        results.append(("YAML frontmatter format", False, "Missing closing ---"))
        return results

    frontmatter = parts[1].strip()

    # Check required fields
    required_fields = ["name:", "description:", "version:"]
    for field in required_fields:
        if field in frontmatter:
            results.append((f"YAML field {field}", True, "OK"))
        else:
            results.append((f"YAML field {field}", False, f"Missing {field}"))

    # Check specific field values
    if "name: pr-mining-coordinator" in frontmatter:
        results.append(("Skill name correct", True, "OK"))
    else:
        results.append(("Skill name correct", False, "Name should be 'pr-mining-coordinator'"))

    return results


def validate_pr_miner_skill() -> List[Tuple[str, bool, str]]:
    """Validate pr-miner skill prerequisites."""
    results = []

    pr_miner_path = Path.home() / ".claude/skills/pr-miner"

    if not pr_miner_path.exists():
        results.append(
            (
                "PR miner skill exists",
                False,
                f"pr-miner skill not found at {pr_miner_path}",
            )
        )
        return results

    results.append(("PR miner skill exists", True, "OK"))

    # Check for miner script
    miner_script = pr_miner_path / "scripts/miner.py"
    if miner_script.exists():
        results.append(("Miner script exists", True, "OK"))
    else:
        results.append(("Miner script exists", False, f"Missing {miner_script}"))

    # Check for required directories
    required_dirs = ["mined_data", "rules", "venv"]
    for dir_name in required_dirs:
        dir_path = pr_miner_path / dir_name
        if dir_path.exists():
            results.append((f"Directory exists: {dir_name}", True, "OK"))
        else:
            results.append(
                (
                    f"Directory exists: {dir_name}",
                    False,
                    f"Missing {dir_path} (will be created on first use)",
                )
            )

    return results


def validate_github_token() -> List[Tuple[str, bool, str]]:
    """Validate GitHub token availability (macOS keychain)."""
    results = []

    # Try to get token from keychain (only works on macOS)
    import subprocess

    try:
        result = subprocess.run(
            ["security", "find-internet-password", "-s", "github.com", "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0 and result.stdout.strip():
            token = result.stdout.strip()
            # Check token starts with expected prefix
            if token.startswith("ghp_") or token.startswith("github_pat_"):
                results.append(("GitHub token available", True, "Token found in macOS keychain"))
            else:
                results.append(
                    (
                        "GitHub token format",
                        False,
                        f"Token doesn't match expected format (starts with: {token[:4]})",
                    )
                )
        else:
            results.append(
                (
                    "GitHub token available",
                    False,
                    "No GitHub token in macOS keychain - add with 'security add-internet-password'",
                )
            )

    except FileNotFoundError:
        results.append(
            (
                "GitHub token check",
                False,
                "Not on macOS - cannot check keychain (token check skipped)",
            )
        )
    except Exception as e:
        results.append(("GitHub token check", False, f"Error checking keychain: {e}"))

    return results


def run_all_validations() -> bool:
    """Run all validation checks."""
    all_results = []

    print("=" * 60)
    print("PR MINING COORDINATOR SKILL VALIDATION")
    print("=" * 60)
    print()

    # Run validation categories
    validations = [
        ("Skill Structure", validate_skill_structure),
        ("YAML Frontmatter", validate_yaml_frontmatter),
        ("PR Miner Prerequisites", validate_pr_miner_skill),
        ("GitHub Token", validate_github_token),
    ]

    all_passed = True

    for category, validation_func in validations:
        print(f"\n{category}:")
        print("-" * 60)
        results = validation_func()
        all_results.extend(results)

        for description, passed, message in results:
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {status} - {description}")
            if not passed:
                print(f"         {message}")
                # Don't fail overall for missing directories (created on demand)
                if "will be created on first use" not in message and category != "GitHub Token":
                    all_passed = False

    # Summary
    print("\n" + "=" * 60)
    total_checks = len(all_results)
    passed_checks = sum(1 for _, passed, _ in all_results if passed)
    failed_checks = total_checks - passed_checks

    print(f"SUMMARY: {passed_checks}/{total_checks} checks passed")
    if failed_checks > 0:
        print(f"         {failed_checks} checks failed")
    print("=" * 60)

    return all_passed


def main():
    """Main entry point."""
    try:
        all_passed = run_all_validations()
        sys.exit(0 if all_passed else 1)
    except Exception as e:
        print(f"\nValidation error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
