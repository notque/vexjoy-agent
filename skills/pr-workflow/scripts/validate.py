#!/usr/bin/env python3
"""
Validate pr-miner skill setup
"""

import os
import sys
from pathlib import Path


def check_command(command: str) -> bool:
    """Check if a command is available"""
    import shutil

    return shutil.which(command) is not None


def check_python_package(package: str) -> bool:
    """Check if Python package is installed"""
    try:
        __import__(package)
        return True
    except ImportError:
        return False


def check_file(file_path: Path, description: str) -> bool:
    """Check if a file exists"""
    exists = file_path.exists()
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {file_path}")
    return exists


def check_github_token() -> bool:
    """Check if GitHub token is available"""
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        print(f"✓ GITHUB_TOKEN is set (length: {len(token)})")
        return True

    token_file = Path.home() / ".github-token"
    if token_file.exists():
        token = token_file.read_text().strip()
        print(f"✓ GitHub token found in ~/.github-token (length: {len(token)})")
        return True

    print("✗ GitHub token not found")
    print("  Set GITHUB_TOKEN or create ~/.github-token")
    return False


def main():
    print("=" * 70)
    print("PR Miner - Skill Validation")
    print("=" * 70)

    skill_dir = Path(__file__).parent.parent
    all_good = True

    # Check Python
    print("\nChecking Python environment:")
    if not check_command("python3"):
        print("✗ python3 is NOT installed")
        all_good = False
    else:
        print("✓ python3 is installed")

    # Check PyGithub
    print("\nChecking Python packages:")
    if not check_python_package("github"):
        print("✗ PyGithub is NOT installed")
        print("  Run: pip install PyGithub")
        all_good = False
    else:
        print("✓ PyGithub is installed")

    # Check GitHub token
    print("\nChecking GitHub authentication:")
    if not check_github_token():
        all_good = False

    # Check skill files
    print("\nChecking skill files:")
    check_file(skill_dir / "SKILL.md", "SKILL.md")
    check_file(skill_dir / "scripts" / "miner.py", "miner.py")
    check_file(skill_dir / "references", "references directory")

    # Summary
    print("\n" + "=" * 70)
    if all_good:
        print("✓ Skill validation PASSED")
        print("Ready to mine PRs!")
        return 0
    else:
        print("✗ Skill validation FAILED")
        print("Please install missing dependencies:")
        print("  - Python 3.7+")
        print("  - PyGithub: pip install PyGithub")
        print("  - GitHub token: Set GITHUB_TOKEN or create ~/.github-token")
        return 1


if __name__ == "__main__":
    sys.exit(main())
