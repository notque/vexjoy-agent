#!/usr/bin/env python3
"""
Rules Compiler — deduplicate, categorize, and score extracted programming rules.

Caller: pipelines/github-profile-rules/SKILL.md (Phases 4-6)
Purpose: Deterministic processing of raw pattern data into confidence-scored,
         categorized rules. Produces both CLAUDE.md-compatible markdown and
         structured JSON output.

Usage:
    python3 scripts/rules-compiler.py compile --input-dir DIR --output FILE
    python3 scripts/rules-compiler.py validate --input-dir DIR --output FILE
    python3 scripts/rules-compiler.py format --input FILE --output-md FILE --output-json FILE

Output: JSON to specified file, validation results to stdout.
Exit codes: 0 = success, 1 = error.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Rule categories matching references/rule-categories.md
VALID_CATEGORIES = [
    "naming",
    "style",
    "architecture",
    "testing",
    "error-handling",
    "documentation",
    "dependencies",
    "git-workflow",
]

CONFIDENCE_THRESHOLDS = {
    "high": 3,  # Seen in 3+ repos OR 2+ repos + review signal
    "medium": 2,  # Seen in 2 repos
    "low": 1,  # Seen in 1 repo only
}


def load_input_data(input_dir: str) -> dict:
    """Load all JSON and markdown data files from input directory."""
    data = {
        "repos": None,
        "file_samples": [],
        "pr_reviews": None,
        "research_files": [],
    }

    input_path = Path(input_dir)
    if not input_path.exists():
        print(f"ERROR: Input directory '{input_dir}' not found.", file=sys.stderr)
        return data

    # Load repos.json
    repos_file = input_path / "repos.json"
    if repos_file.exists():
        with open(repos_file) as f:
            data["repos"] = json.load(f)

    # Load file sample JSONs
    for json_file in input_path.glob("files-*.json"):
        with open(json_file) as f:
            data["file_samples"].append(json.load(f))

    # Load PR reviews
    reviews_file = input_path / "pr-reviews.json"
    if reviews_file.exists():
        with open(reviews_file) as f:
            data["pr_reviews"] = json.load(f)

    # Load research markdown files
    for md_file in input_path.glob("research-*.md"):
        with open(md_file) as f:
            data["research_files"].append(
                {
                    "name": md_file.stem,
                    "content": f.read(),
                }
            )

    return data


def compute_confidence(repos_count: int, review_signals: int) -> str:
    """Compute confidence level based on repo count and review signals."""
    if repos_count >= 3 or (repos_count >= 2 and review_signals >= 1):
        return "high"
    elif repos_count >= 2:
        return "medium"
    else:
        return "low"


def compute_score(confidence: str, repos_count: int, review_signals: int) -> float:
    """Compute a numeric score (0.0-1.0) for sorting rules."""
    base_scores = {"high": 0.8, "medium": 0.5, "low": 0.2}
    score = base_scores.get(confidence, 0.2)

    # Bonus for more repos (up to 0.1)
    score += min(repos_count * 0.02, 0.1)

    # Bonus for review signals (up to 0.1)
    score += min(review_signals * 0.05, 0.1)

    return round(min(score, 1.0), 2)


def deduplicate_rules(rules: list[dict]) -> list[dict]:
    """Deduplicate rules with similar names or descriptions."""
    if not rules:
        return rules

    deduped = []
    seen_keys: set[str] = set()

    for rule in rules:
        # Create a normalized key from category + rule text
        key = rule.get("category", "").lower() + ":" + rule.get("rule", "").lower().strip()

        # Simple dedup: skip exact matches
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(rule)

    return deduped


def validate_rules(rules: list[dict]) -> list[dict]:
    """Validate rules for actionability, contradictions, and scoping.

    Returns list of validation issues.
    """
    issues = []

    for i, rule in enumerate(rules):
        rule_name = rule.get("name", f"rule-{i}")

        # Check actionability: rule text should be specific
        rule_text = rule.get("rule", "")
        if len(rule_text) < 10:
            issues.append(
                {
                    "rule": rule_name,
                    "issue": "too_short",
                    "message": f"Rule text is too short ({len(rule_text)} chars). "
                    "Rules must be specific enough to follow.",
                }
            )

        # Check for evidence
        repos_observed = rule.get("repos_observed", [])
        examples = rule.get("examples", [])
        if not repos_observed and not examples:
            issues.append(
                {
                    "rule": rule_name,
                    "issue": "no_evidence",
                    "message": "Rule has no evidence (no repos or examples cited).",
                }
            )

        # Check category validity
        category = rule.get("category", "")
        if category not in VALID_CATEGORIES:
            issues.append(
                {
                    "rule": rule_name,
                    "issue": "invalid_category",
                    "message": f"Category '{category}' is not in the valid set: {', '.join(VALID_CATEGORIES)}",
                }
            )

    # Check for contradictions (simple heuristic)
    by_category: dict[str, list[dict]] = {}
    for rule in rules:
        cat = rule.get("category", "unknown")
        by_category.setdefault(cat, []).append(rule)

    for cat, cat_rules in by_category.items():
        texts = [r.get("rule", "").lower() for r in cat_rules]
        # Basic contradiction detection: look for opposing keywords
        opposites = [
            ("camelcase", "snake_case"),
            ("tabs", "spaces"),
            ("single quotes", "double quotes"),
            ("semicolons", "no semicolons"),
        ]
        for t1, t2 in opposites:
            has_t1 = any(t1 in t for t in texts)
            has_t2 = any(t2 in t for t in texts)
            if has_t1 and has_t2:
                issues.append(
                    {
                        "rule": f"{cat} category",
                        "issue": "contradiction",
                        "message": f"Potential contradiction in {cat}: "
                        f"rules mention both '{t1}' and '{t2}'. "
                        "Check if they apply to different languages.",
                    }
                )

    return issues


def format_rules_markdown(rules: list[dict], username: str, metadata: dict) -> str:
    """Format rules as CLAUDE.md-compatible markdown."""
    lines = [
        f"# Programming Rules for {username}",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Generation Metadata",
        "",
        f"- **Repos analyzed**: {metadata.get('repos_analyzed', 0)}",
        f"- **Files sampled**: {metadata.get('files_sampled', 0)}",
        f"- **PR reviews mined**: {metadata.get('reviews_mined', 0)}",
        f"- **Total rules**: {len(rules)}",
        f"- **High confidence**: {sum(1 for r in rules if r.get('confidence') == 'high')}",
        f"- **Medium confidence**: {sum(1 for r in rules if r.get('confidence') == 'medium')}",
        f"- **Low confidence**: {sum(1 for r in rules if r.get('confidence') == 'low')}",
        "",
        "---",
        "",
    ]

    # Group by category
    by_category: dict[str, list[dict]] = {}
    for rule in rules:
        cat = rule.get("category", "uncategorized")
        by_category.setdefault(cat, []).append(rule)

    # Sort categories by total rule count (descending)
    sorted_cats = sorted(by_category.items(), key=lambda x: len(x[1]), reverse=True)

    for cat, cat_rules in sorted_cats:
        cat_title = cat.replace("-", " ").title()
        lines.append(f"## {cat_title}")
        lines.append("")

        # Sort rules within category by confidence (high first)
        confidence_order = {"high": 0, "medium": 1, "low": 2}
        cat_rules.sort(key=lambda r: confidence_order.get(r.get("confidence", "low"), 3))

        for rule in cat_rules:
            name = rule.get("name", "Unnamed Rule")
            confidence = rule.get("confidence", "low")
            rule_text = rule.get("rule", "")
            repos = rule.get("repos_observed", [])
            review_signals = rule.get("review_signals", 0)

            lines.append(f"### {cat_title}: {name}")
            lines.append("")
            lines.append(f"**Confidence**: {confidence} (seen in {len(repos)} repos, {review_signals} review comments)")
            lines.append("")
            lines.append(rule_text)
            lines.append("")

            # Evidence
            if repos or rule.get("examples"):
                lines.append("**Evidence**:")
                for repo in repos:
                    lines.append(f"- Repo: {repo}")
                for example in rule.get("examples", []):
                    if isinstance(example, dict):
                        lines.append(
                            f"- {example.get('repo', '')}: `{example.get('file', '')}` -- {example.get('pattern', '')}"
                        )
                    else:
                        lines.append(f"- {example}")
                lines.append("")

            # Language scope
            scope = rule.get("language_scope", [])
            if scope:
                lines.append(f"**Applies to**: {', '.join(scope)}")
                lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def format_rules_json(rules: list[dict], username: str, metadata: dict) -> str:
    """Format rules as structured JSON."""
    output = {
        "username": username,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "total_rules": len(rules),
        "rules_by_confidence": {
            "high": sum(1 for r in rules if r.get("confidence") == "high"),
            "medium": sum(1 for r in rules if r.get("confidence") == "medium"),
            "low": sum(1 for r in rules if r.get("confidence") == "low"),
        },
        "rules": rules,
    }
    return json.dumps(output, indent=2)


def cmd_compile(args: argparse.Namespace) -> int:
    """Compile raw data into structured rules."""
    input_dir = args.input_dir
    output = args.output

    data = load_input_data(input_dir)

    # Build a skeleton structure for rules
    # The actual pattern extraction is done by the LLM in the skill phases;
    # this script handles the mechanical parts: dedup, scoring, categorization
    rules: list[dict] = []

    # Check if compiled rules already exist (from LLM phase)
    compiled_path = Path(input_dir) / "patterns.json"
    if compiled_path.exists():
        with open(compiled_path) as f:
            raw_rules = json.load(f)
            if isinstance(raw_rules, list):
                rules = raw_rules
            elif isinstance(raw_rules, dict) and "rules" in raw_rules:
                rules = raw_rules["rules"]

    # Deduplicate
    rules = deduplicate_rules(rules)

    # Ensure confidence scores
    for rule in rules:
        repos_count = len(rule.get("repos_observed", []))
        review_signals = rule.get("review_signals", 0)
        if "confidence" not in rule:
            rule["confidence"] = compute_confidence(repos_count, review_signals)
        if "score" not in rule:
            rule["score"] = compute_score(rule["confidence"], repos_count, review_signals)

    # Sort by score descending
    rules.sort(key=lambda r: r.get("score", 0), reverse=True)

    # Build metadata
    metadata = {
        "repos_analyzed": (data["repos"].get("repos_fetched", 0) if data["repos"] else 0),
        "files_sampled": sum(fs.get("files_sampled", 0) for fs in data["file_samples"]),
        "reviews_mined": (data["pr_reviews"].get("reviews_fetched", 0) if data["pr_reviews"] else 0),
    }

    # Determine username
    username = "unknown"
    if data["repos"]:
        username = data["repos"].get("username", "unknown")

    output_data = {
        "username": username,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "total_rules": len(rules),
        "rules": rules,
    }

    # Write output
    if output:
        os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
        with open(output, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"Compiled {len(rules)} rules to {output}", file=sys.stderr)

    print(json.dumps(output_data, indent=2))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate compiled rules for quality."""
    input_dir = args.input_dir
    output = args.output

    # Load compiled rules
    compiled_path = Path(input_dir) / "compiled-rules.json"
    if not compiled_path.exists():
        # Try patterns.json as fallback
        compiled_path = Path(input_dir) / "patterns.json"

    if not compiled_path.exists():
        print(f"ERROR: No compiled rules found in '{input_dir}'.", file=sys.stderr)
        return 1

    with open(compiled_path) as f:
        data = json.load(f)

    rules = data.get("rules", []) if isinstance(data, dict) else data

    # Run validation
    issues = validate_rules(rules)

    result = {
        "total_rules": len(rules),
        "issues_found": len(issues),
        "issues": issues,
        "verdict": "PASS" if len(issues) == 0 else "WARN",
    }

    if output:
        os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
        with open(output, "w") as f:
            json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))

    # Return 0 even with warnings (validation issues are advisory, not blocking)
    return 0


def cmd_format(args: argparse.Namespace) -> int:
    """Format compiled rules into markdown and JSON output files."""
    input_file = args.input
    output_md = args.output_md
    output_json = args.output_json

    if not os.path.exists(input_file):
        print(f"ERROR: Input file '{input_file}' not found.", file=sys.stderr)
        return 1

    with open(input_file) as f:
        data = json.load(f)

    rules = data.get("rules", [])
    username = data.get("username", "unknown")
    metadata = data.get("metadata", {})

    if output_md:
        md_content = format_rules_markdown(rules, username, metadata)
        os.makedirs(os.path.dirname(output_md) or ".", exist_ok=True)
        with open(output_md, "w") as f:
            f.write(md_content)
        print(f"Written markdown to {output_md}", file=sys.stderr)

    if output_json:
        json_content = format_rules_json(rules, username, metadata)
        os.makedirs(os.path.dirname(output_json) or ".", exist_ok=True)
        with open(output_json, "w") as f:
            f.write(json_content)
        print(f"Written JSON to {output_json}", file=sys.stderr)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="rules-compiler",
        description=(
            "Compile, validate, and format programming rules extracted "
            "from GitHub profiles. Handles deduplication, confidence scoring, "
            "and output formatting."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # compile command
    compile_parser = subparsers.add_parser("compile", help="Compile raw pattern data into structured rules")
    compile_parser.add_argument("--input-dir", required=True, help="Directory containing fetched data")
    compile_parser.add_argument("--output", required=True, help="Output file path for compiled rules JSON")

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate compiled rules for quality")
    validate_parser.add_argument("--input-dir", required=True, help="Directory containing compiled rules")
    validate_parser.add_argument("--output", default=None, help="Output file for validation report")

    # format command
    format_parser = subparsers.add_parser("format", help="Format compiled rules into markdown and JSON")
    format_parser.add_argument("--input", required=True, help="Input compiled rules JSON file")
    format_parser.add_argument("--output-md", default=None, help="Output markdown file path")
    format_parser.add_argument("--output-json", default=None, help="Output JSON file path")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    commands = {
        "compile": cmd_compile,
        "validate": cmd_validate,
        "format": cmd_format,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
