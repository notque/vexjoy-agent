#!/usr/bin/env python3
"""
Branch name generation script for branch-naming skill.

Generates Git branch names from conventional commit messages or descriptions.
"""

__version__ = "1.0.0"

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Conventional commit type to branch prefix mapping
TYPE_PREFIX_MAP = {
    "feat": "feature/",
    "fix": "fix/",
    "docs": "docs/",
    "style": "style/",
    "refactor": "refactor/",
    "perf": "perf/",
    "test": "test/",
    "build": "build/",
    "ci": "ci/",
    "chore": "chore/",
    "revert": "revert/",
}

# Keywords for type inference
TYPE_INFERENCE_KEYWORDS = {
    "feat": ["add", "implement", "create", "introduce"],
    "fix": ["fix", "resolve", "correct", "repair", "patch"],
    "docs": ["document", "readme", "guide", "explain"],
    "refactor": ["refactor", "restructure", "reorganize", "simplify"],
    "test": ["test", "spec", "coverage"],
    "chore": ["remove", "delete", "cleanup", "update"],
}

# Common filler words to remove for truncation
FILLER_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "with",
    "for",
    "to",
    "from",
    "in",
    "on",
    "at",
    "by",
    "of",
    "as",
    "is",
    "was",
    "are",
    "were",
    "be",
    "been",
    "being",
}

# Common abbreviations for truncation
ABBREVIATIONS = {
    "authentication": "auth",
    "authorization": "authz",
    "configuration": "config",
    "development": "dev",
    "environment": "env",
    "production": "prod",
    "repository": "repo",
    "application": "app",
    "database": "db",
    "implementation": "impl",
    "documentation": "docs",
}


class BranchNameGenerator:
    """Generate branch names from commit messages or descriptions."""

    def __init__(self, max_length: int = 50, custom_type_map: Optional[Dict[str, str]] = None):
        self.max_length = max_length
        self.type_prefix_map = custom_type_map or TYPE_PREFIX_MAP

    def parse_conventional_commit(self, message: str) -> Dict[str, Optional[str]]:
        """
        Parse conventional commit message.

        Format: <type>[optional scope]: <description>

        Returns:
            {
                'commit_type': str or None,
                'scope': str or None,
                'subject': str,
                'full_message': str
            }
        """
        # Pattern: type(scope): subject
        pattern = r"^(\w+)(?:\(([^)]+)\))?: (.+)$"
        match = re.match(pattern, message.strip())

        if match:
            commit_type, scope, subject = match.groups()
            return {"commit_type": commit_type, "scope": scope, "subject": subject.strip(), "full_message": message}

        # Not conventional commit format
        return {"commit_type": None, "scope": None, "subject": message.strip(), "full_message": message}

    def infer_type_from_description(self, description: str) -> str:
        """
        Infer commit type from description keywords.

        Returns:
            Inferred type (default: 'feat')
        """
        description_lower = description.lower()

        for commit_type, keywords in TYPE_INFERENCE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in description_lower:
                    return commit_type

        # Default to feature
        return "feat"

    def validate_input(self, text: str) -> Tuple[bool, List[str]]:
        """
        Validate input for banned characters.

        Returns:
            (is_valid, list_of_issues)
        """
        issues = []

        # Check for emojis (simplified - checks common ranges)
        if re.search(r"[\U0001F300-\U0001F9FF]", text):
            issues.append("Input contains emojis")

        # Check for multiple exclamation marks
        if "!!!" in text:
            issues.append("Multiple exclamation marks detected: !!!")

        # Check for excessive special characters
        special_chars = re.findall(r"[@#$%^&*(){}\[\]]", text)
        if special_chars:
            issues.append(f"Input contains special characters: {', '.join(set(special_chars))}")

        return len(issues) == 0, issues

    def sanitize_to_kebab_case(self, text: str) -> str:
        """
        Convert text to kebab-case.

        Pipeline:
        1. Lowercase
        2. Remove leading/trailing whitespace
        3. Replace spaces/underscores with hyphens
        4. Remove special characters
        5. Collapse multiple hyphens
        6. Remove leading/trailing hyphens
        """
        # Step 1: Lowercase
        text = text.lower()

        # Step 2: Strip whitespace
        text = text.strip()

        # Step 3: Replace spaces and underscores with hyphens
        text = re.sub(r"[\s_]+", "-", text)

        # Step 4: Remove special characters (keep only a-z, 0-9, -)
        text = re.sub(r"[^a-z0-9-]", "", text)

        # Step 5: Collapse multiple hyphens
        text = re.sub(r"-+", "-", text)

        # Step 6: Remove leading/trailing hyphens
        text = text.strip("-")

        return text

    def intelligent_truncate(self, text: str, max_length: int) -> str:
        """
        Intelligently truncate text to fit max_length.

        Strategies:
        1. Remove filler words
        2. Apply abbreviations
        3. Truncate at word boundaries
        """
        if len(text) <= max_length:
            return text

        # Step 1: Remove filler words
        words = text.split("-")
        words = [w for w in words if w not in FILLER_WORDS]
        text = "-".join(words)

        if len(text) <= max_length:
            return text

        # Step 2: Apply abbreviations
        for full, abbr in ABBREVIATIONS.items():
            text = text.replace(full, abbr)

        if len(text) <= max_length:
            return text

        # Step 3: Truncate at word boundaries
        words = text.split("-")
        truncated_words = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 <= max_length:  # +1 for hyphen
                truncated_words.append(word)
                current_length += len(word) + 1
            else:
                break

        return "-".join(truncated_words)

    def generate(
        self, commit_message: Optional[str] = None, description: Optional[str] = None, commit_type: Optional[str] = None
    ) -> Dict:
        """
        Generate branch name.

        Args:
            commit_message: Conventional commit message
            description: Plain description
            commit_type: Explicit type (overrides inference)

        Returns:
            {
                'branch_name': str,
                'prefix': str,
                'subject': str,
                'length': int,
                'valid': bool,
                'warnings': list
            }
        """
        warnings = []

        # Parse input
        if commit_message:
            parsed = self.parse_conventional_commit(commit_message)
            detected_type = parsed["commit_type"]
            subject = parsed["subject"]
        elif description:
            detected_type = None
            subject = description
        else:
            return {"error": "empty_input", "message": "No commit message or description provided"}

        # Validate input
        valid, issues = self.validate_input(subject)
        if not valid:
            return {
                "error": "banned_characters",
                "issues": issues,
                "message": "Input contains banned characters or patterns",
            }

        # Determine commit type
        final_type = commit_type or detected_type or self.infer_type_from_description(subject)

        # Get branch prefix
        prefix = self.type_prefix_map.get(final_type, "feature/")

        # Sanitize subject to kebab-case
        sanitized_subject = self.sanitize_to_kebab_case(subject)

        if not sanitized_subject:
            return {
                "error": "empty_after_sanitization",
                "original": subject,
                "message": "Subject becomes empty after sanitization",
            }

        # Calculate available length for subject
        available_length = self.max_length - len(prefix)

        # Truncate if needed
        if len(sanitized_subject) > available_length:
            original_length = len(sanitized_subject)
            sanitized_subject = self.intelligent_truncate(sanitized_subject, available_length)
            warnings.append(
                {"type": "truncated", "original_length": original_length, "truncated_length": len(sanitized_subject)}
            )

        # Generate full branch name
        branch_name = f"{prefix}{sanitized_subject}"

        return {
            "branch_name": branch_name,
            "prefix": prefix,
            "subject": sanitized_subject,
            "commit_type": final_type,
            "length": len(branch_name),
            "valid": len(branch_name) <= self.max_length,
            "warnings": warnings,
        }


def load_custom_config(config_path: Optional[Path] = None) -> Optional[Dict]:
    """Load custom type mapping from .branch-naming.json."""
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
        description="Generate Git branch names from commit messages or descriptions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--from-commit-message", type=str, help="Generate from conventional commit message")
    input_group.add_argument("--description", type=str, help="Generate from plain description")
    input_group.add_argument("--sanitize", type=str, help="Only sanitize text to kebab-case (no branch generation)")
    input_group.add_argument("--validate-input", type=str, help="Validate input for banned characters")

    # Generation options
    parser.add_argument(
        "--type", type=str, choices=list(TYPE_PREFIX_MAP.keys()), help="Explicit commit type (overrides inference)"
    )
    parser.add_argument("--prefix", type=str, help="Custom branch prefix")
    parser.add_argument("--max-length", type=int, default=50, help="Maximum branch name length (default: 50)")
    parser.add_argument("--config", type=Path, help="Path to .branch-naming.json config file")

    # Output options
    parser.add_argument(
        "--output-format", choices=["json", "name-only"], default="json", help="Output format (default: json)"
    )
    parser.add_argument("--auto-accept", action="store_true", help="Skip confirmation, output name directly")
    parser.add_argument("--abbreviate", action="store_true", help="Apply abbreviations during sanitization")

    args = parser.parse_args()

    try:
        # Load custom config if provided
        config = load_custom_config(args.config)
        custom_type_map = None
        if config and "type_prefix_map" in config:
            custom_type_map = config["type_prefix_map"]

        generator = BranchNameGenerator(max_length=args.max_length, custom_type_map=custom_type_map)

        # Handle different input modes
        if args.validate_input:
            valid, issues = generator.validate_input(args.validate_input)
            result = {"valid": valid, "input": args.validate_input, "issues": issues}
            if valid:
                result["sanitized_input"] = generator.sanitize_to_kebab_case(args.validate_input)
            print(json.dumps(result, indent=2))
            sys.exit(0 if valid else 1)

        elif args.sanitize:
            sanitized = generator.sanitize_to_kebab_case(args.sanitize)
            if args.abbreviate:
                for full, abbr in ABBREVIATIONS.items():
                    sanitized = sanitized.replace(full, abbr)

            result = {
                "original": args.sanitize,
                "sanitized": sanitized,
                "transformations": ["lowercase", "whitespace_to_hyphens", "remove_special_chars", "collapse_hyphens"],
            }
            if args.abbreviate:
                result["transformations"].append("abbreviations")

            print(json.dumps(result, indent=2))
            sys.exit(0)

        # Generate branch name
        result = generator.generate(
            commit_message=args.from_commit_message, description=args.description, commit_type=args.type
        )

        # Check for errors
        if "error" in result:
            print(json.dumps(result, indent=2), file=sys.stderr)
            sys.exit(1)

        # Output result
        if args.output_format == "name-only":
            print(result["branch_name"])
        else:
            print(json.dumps(result, indent=2))

        sys.exit(0)

    except Exception as e:
        print(
            json.dumps({"error": "generation_failed", "error_type": type(e).__name__, "message": str(e)}, indent=2),
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
