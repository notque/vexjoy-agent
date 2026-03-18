#!/usr/bin/env python3
"""
Report generation script for docs-sync-checker skill.
Creates human-readable markdown reports from sync issues.
"""

__version__ = "1.0.0"

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class ReportGenerator:
    """Generate sync reports from issues data."""

    def __init__(self, strict: bool = False, auto_fix: bool = False):
        self.strict = strict
        self.auto_fix = auto_fix

    def generate_suggested_fix_markdown(self, issue: Dict[str, Any]) -> str:
        """
        Generate suggested markdown to add/remove for an issue.
        """
        tool_type = issue["tool_type"]
        tool_name = issue["tool_name"]
        description = issue.get("yaml_description", "")

        if tool_type == "skill":
            # Skills README table row
            return f"| {tool_name} | {description} | `skill: {tool_name}` | - |"
        elif tool_type == "agent":
            # Agents README table row (or list item)
            return f"| {tool_name} | {description} |"
        elif tool_type == "command":
            # Commands README list item
            return f"- `/{tool_name}` - {description}"

        return ""

    def generate_markdown_report(self, issues_data: Dict[str, Any], scan_results: Dict[str, Any] = None) -> str:
        """
        Generate human-readable markdown report.
        """
        issues = issues_data.get("issues", {})
        summary = issues_data.get("summary", {})

        lines = []

        # Header
        lines.append("# Documentation Sync Report")
        lines.append("")
        lines.append(f"**Generated**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")

        if scan_results:
            lines.append(f"**Repository**: {scan_results.get('repo_root', 'N/A')}")

        # Status
        total_issues = summary.get("total_issues", 0)
        if total_issues == 0:
            lines.append("**Status**: ✅ ALL IN SYNC")
        else:
            lines.append(f"**Status**: ⚠️ {total_issues} ISSUES FOUND")

        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")

        if scan_results:
            total_tools = scan_results.get("summary", {}).get("total_tools", 0)
            skills_count = scan_results.get("summary", {}).get("skills_count", 0)
            agents_count = scan_results.get("summary", {}).get("agents_count", 0)
            commands_count = scan_results.get("summary", {}).get("commands_count", 0)

            lines.append(
                f"- **Total Tools**: {total_tools} ({skills_count} skills, {agents_count} agents, {commands_count} commands)"
            )

        lines.append(f"- **Missing Entries**: {summary.get('missing_entries', 0)} HIGH priority")
        lines.append(f"- **Stale Entries**: {summary.get('stale_entries', 0)} MEDIUM priority")
        lines.append(f"- **Version Mismatches**: {summary.get('version_mismatches', 0)} LOW priority")

        if total_issues > 0 and scan_results:
            total_tools = scan_results.get("summary", {}).get("total_tools", 1)
            sync_score = ((total_tools - total_issues) / total_tools) * 100
            lines.append(
                f"- **Sync Score**: {sync_score:.0f}% ({total_tools - total_issues}/{total_tools} tools properly documented)"
            )

        lines.append("")
        lines.append("---")
        lines.append("")

        # Missing Entries
        missing = issues.get("missing_entries", [])
        if missing:
            lines.append("## ⚠️ HIGH Priority Issues")
            lines.append("")
            lines.append(f"### Missing Entries ({len(missing)})")
            lines.append("")
            lines.append("Tools exist but are NOT documented in required files:")
            lines.append("")

            for i, issue in enumerate(missing, 1):
                tool_type = issue["tool_type"].capitalize()
                tool_name = issue["tool_name"]
                tool_path = issue["tool_path"]
                missing_from = ", ".join(issue["missing_from"])

                lines.append(f"#### {i}. {tool_type}: {tool_name}")
                lines.append(f"**Path**: `{tool_path}`")
                lines.append(f"**Missing from**: {missing_from}")
                lines.append("")

                # Suggested fixes for each location
                for location in issue["missing_from"]:
                    suggested_fix = self.generate_suggested_fix_markdown(issue)
                    if suggested_fix:
                        lines.append(f"**Suggested Fix for {location}**:")
                        lines.append("```markdown")
                        lines.append(suggested_fix)
                        lines.append("```")
                        lines.append("")

            lines.append("---")
            lines.append("")

        # Stale Entries
        stale = issues.get("stale_entries", [])
        if stale:
            lines.append("## MEDIUM Priority Issues")
            lines.append("")
            lines.append(f"### Stale Entries ({len(stale)})")
            lines.append("")
            lines.append("Documented tools that NO LONGER EXIST in filesystem:")
            lines.append("")

            for i, issue in enumerate(stale, 1):
                tool_type = issue["tool_type"].capitalize()
                tool_name = issue["tool_name"]
                documented_in = ", ".join(issue["documented_in"])

                lines.append(f"#### {i}. {tool_type}: {tool_name}")
                lines.append(f"**Documented in**: {documented_in}")
                lines.append("")
                lines.append("**Suggested Fix**:")
                lines.append(f'- Remove the entry for "{tool_name}" from {documented_in}')
                lines.append(f'- Check README.md for references to "{tool_name}" and remove')
                lines.append("")

            lines.append("---")
            lines.append("")

        # Version Mismatches
        version_mismatches = issues.get("version_mismatches", [])
        if version_mismatches:
            lines.append("## LOW Priority Issues")
            lines.append("")
            lines.append(f"### Version Mismatches ({len(version_mismatches)})")
            lines.append("")
            lines.append("YAML version differs from documented version:")
            lines.append("")

            for i, issue in enumerate(version_mismatches, 1):
                tool_name = issue["tool_name"]
                yaml_version = issue["yaml_version"]
                documented_version = issue["documented_version"]
                documented_in = issue["documented_in"]

                lines.append(f"#### {i}. {tool_name}")
                lines.append(f"**YAML Version**: {yaml_version}")
                lines.append(f"**Documented Version**: {documented_version}")
                lines.append(f"**File**: {documented_in}")
                lines.append("")
                lines.append("**Suggested Fix**:")
                lines.append(f"Update {documented_in} to show version {yaml_version}")
                lines.append("")

            lines.append("---")
            lines.append("")

        # Recommendations
        if total_issues > 0:
            lines.append("## Recommendations")
            lines.append("")

            if missing:
                lines.append(f"1. **Add missing entries** for new tools ({len(missing)} tools)")
            if stale:
                lines.append(f"2. **Remove stale entries** for deleted tools ({len(stale)} tools)")
            if version_mismatches:
                lines.append(f"3. **Update versions** to match YAML frontmatter ({len(version_mismatches)} tools)")

            lines.append("4. **Run this check** before committing documentation changes")
            lines.append("5. **Integrate with CI/CD** to prevent future drift")
            lines.append("")
        else:
            lines.append("## Status: All Clear! ✅")
            lines.append("")
            lines.append("All tools are properly documented. No sync issues detected.")
            lines.append("")

        # Files Checked
        if issues_data.get("files_parsed"):
            lines.append("---")
            lines.append("")
            lines.append("## Files Checked")
            lines.append("")

            documented = issues_data.get("documented", {})
            for file_path, tools in documented.items():
                count = len(tools) if tools else 0
                lines.append(f"- ✅ {file_path} (parsed {count} entries)")

        # Next Steps
        if total_issues > 0:
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append("## Next Steps")
            lines.append("")
            lines.append("```bash")
            lines.append("# Review suggested fixes above")
            lines.append("# Manually update documentation files")
            lines.append("# Re-run sync checker to verify")
            lines.append("python3 skills/docs-sync-checker/scripts/scan_tools.py --repo-root .")
            lines.append(
                "python3 skills/docs-sync-checker/scripts/parse_docs.py --repo-root . --scan-results /tmp/scan.json"
            )
            lines.append("python3 skills/docs-sync-checker/scripts/generate_report.py --issues /tmp/issues.json")
            lines.append("```")

        return "\n".join(lines)

    def generate_json_report(self, issues_data: Dict[str, Any], scan_results: Dict[str, Any] = None) -> str:
        """
        Generate machine-readable JSON report.
        """
        report = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "summary": issues_data.get("summary", {}),
            "issues": issues_data.get("issues", {}),
            "report_version": __version__,
        }

        if scan_results:
            report["scan_summary"] = scan_results.get("summary", {})

        return json.dumps(report, indent=2, ensure_ascii=False)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate documentation sync report", formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--issues", type=Path, help="Path to issues JSON from parse_docs.py")
    parser.add_argument("--scan-results", type=Path, help="Path to scan results JSON from scan_tools.py")
    parser.add_argument("--output", type=Path, help="Output file (default: stdout)")
    parser.add_argument(
        "--format", choices=["markdown", "json"], default="markdown", help="Output format (default: markdown)"
    )
    parser.add_argument("--strict", action="store_true", help="Exit with error code if issues found (for CI/CD)")
    parser.add_argument("--auto-fix", action="store_true", help="Automatically fix missing entries (EXPERIMENTAL)")

    args = parser.parse_args()

    try:
        # Load issues data
        issues_data = {}
        if args.issues:
            with open(args.issues, "r", encoding="utf-8") as f:
                issues_data = json.load(f)
        else:
            # If no issues file, run the pipeline inline
            print("Error: --issues parameter required", file=sys.stderr)
            print("Run scan_tools.py and parse_docs.py first", file=sys.stderr)
            sys.exit(1)

        # Load scan results (optional)
        scan_results = None
        if args.scan_results:
            with open(args.scan_results, "r", encoding="utf-8") as f:
                scan_results = json.load(f)

        # Generate report
        generator = ReportGenerator(strict=args.strict, auto_fix=args.auto_fix)

        if args.format == "markdown":
            report_content = generator.generate_markdown_report(issues_data, scan_results)
        else:
            report_content = generator.generate_json_report(issues_data, scan_results)

        # Output report
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(report_content)
            print(f"Report written to: {args.output}", file=sys.stderr)
        else:
            print(report_content)

        # Exit code for CI/CD
        total_issues = issues_data.get("summary", {}).get("total_issues", 0)
        if args.strict and total_issues > 0:
            print(f"\nERROR: {total_issues} sync issues found (strict mode)", file=sys.stderr)
            sys.exit(1)

        sys.exit(0)

    except Exception as e:
        print(
            json.dumps({"status": "error", "error_type": type(e).__name__, "message": str(e)}, indent=2),
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
