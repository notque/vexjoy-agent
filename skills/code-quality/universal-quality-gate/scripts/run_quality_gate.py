#!/usr/bin/env python3
"""
Universal Quality Gate - Skill Entry Point

Thin wrapper around the shared quality_gate library.
Provides CLI interface for manual invocation via skill.
"""

import argparse
import sys
from pathlib import Path

# Add hooks/lib to path for shared library
HOOKS_LIB = Path(__file__).parent.parent.parent.parent / "hooks" / "lib"
sys.path.insert(0, str(HOOKS_LIB))

from quality_gate import format_report, run_quality_gate


def main():
    """Run quality gate with CLI arguments."""
    parser = argparse.ArgumentParser(description="Universal Quality Gate - Multi-language code quality checking")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix issues where possible",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Only check git staged files",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show verbose output with full tool messages",
    )
    parser.add_argument(
        "--lang",
        type=str,
        help="Check only this language (e.g., python, go, javascript)",
    )
    parser.add_argument(
        "--no-patterns",
        action="store_true",
        help="Skip pattern matching checks",
    )
    parser.add_argument(
        "--tools",
        type=str,
        help="Only run these tools, comma-separated (e.g., lint,format)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project path (default: current directory)",
    )

    args = parser.parse_args()

    # Parse options
    project_path = Path(args.path).resolve()
    languages = [args.lang] if args.lang else None
    tools_filter = args.tools.split(",") if args.tools else None

    # Run quality gate
    report = run_quality_gate(
        project_path=project_path,
        languages=languages,
        fix=args.fix,
        staged_only=args.staged,
        include_patterns=not args.no_patterns,
        tools_filter=tools_filter,
    )

    # Output
    if args.json:
        import json

        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(format_report(report, verbose=args.verbose))

    # Exit code
    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
