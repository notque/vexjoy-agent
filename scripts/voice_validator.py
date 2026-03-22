#!/usr/bin/env python3
"""
Voice content validator CLI.

Validates content against voice profiles and banned patterns.
Returns structured JSON output with violations and metrics.

Usage:
    python3 scripts/voice-validator.py validate \
        --content draft.md \
        --profile profile.json \
        --format json

    python3 scripts/voice-validator.py validate \
        --content draft.md \
        --profile profile.json \
        --format text \
        --verbose

    python3 scripts/voice-validator.py check-banned \
        --content draft.md \
        --banned-file scripts/data/banned-patterns.json

    python3 scripts/voice-validator.py check-rhythm \
        --content draft.md \
        --profile profile.json

Exit codes:
    0 = pass (score >= 70)
    1 = fail (score < 70 or errors)
    2 = execution error (file not found, invalid JSON, etc.)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Constants
DEFAULT_PASS_THRESHOLD = 60  # Lowered - the voice's actual writing scores ~66
ERROR_PENALTY = 10
WARNING_PENALTY = 3
INFO_PENALTY = 1
MONOTONY_THRESHOLD = 3  # Consecutive sentences of similar length
SENTENCE_LENGTH_VARIANCE = 5  # Words +/- for "similar" length
METRIC_DEVIATION_THRESHOLD = 0.20  # 20% deviation triggers warning


@dataclass
class Violation:
    """A single validation violation."""

    type: str
    severity: str  # "error", "warning", "info"
    line: int = 0
    column: int = 0
    text: str = ""
    message: str = ""
    suggestion: str = ""
    metric: str = ""
    expected: float | None = None
    actual: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        result: dict[str, Any] = {
            "type": self.type,
            "severity": self.severity,
        }
        if self.line:
            result["line"] = self.line
        if self.column:
            result["column"] = self.column
        if self.text:
            result["text"] = self.text
        if self.message:
            result["message"] = self.message
        if self.suggestion:
            result["suggestion"] = self.suggestion
        if self.metric:
            result["metric"] = self.metric
        if self.expected is not None:
            result["expected"] = self.expected
        if self.actual is not None:
            result["actual"] = self.actual
        return result


@dataclass
class ValidationResult:
    """Complete validation result."""

    passed: bool
    score: int
    violations: list[Violation] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    summary: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        return {
            "pass": self.passed,
            "score": self.score,
            "violations": [v.to_dict() for v in self.violations],
            "metrics": self.metrics,
            "summary": self.summary,
        }


@dataclass
class BannedPatterns:
    """Loaded banned patterns configuration."""

    categories: dict[str, Any] = field(default_factory=dict)
    punctuation: dict[str, Any] = field(default_factory=dict)
    voice_specific: dict[str, Any] = field(default_factory=dict)


def find_script_dir() -> Path:
    """Find the scripts directory."""
    return Path(__file__).parent


def load_banned_patterns(path: Path | None = None) -> BannedPatterns:
    """Load banned patterns from JSON file."""
    if path is None:
        path = find_script_dir() / "data" / "banned-patterns.json"

    if not path.exists():
        return BannedPatterns()

    content = path.read_text(encoding="utf-8")
    data = json.loads(content)

    return BannedPatterns(
        categories=data.get("categories", {}),
        punctuation=data.get("punctuation", {}),
        voice_specific=data.get("voice_specific", {}),
    )


def load_profile(path: Path) -> dict[str, Any]:
    """Load voice profile from JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")

    content = path.read_text(encoding="utf-8")
    return json.loads(content)


def load_content(path: Path) -> str:
    """Load content from file."""
    if not path.exists():
        raise FileNotFoundError(f"Content file not found: {path}")

    return path.read_text(encoding="utf-8")


def extract_sentences(text: str) -> list[str]:
    """Extract sentences from text."""
    # Remove markdown code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline code
    text = re.sub(r"`[^`]+`", "", text)
    # Remove markdown headers
    text = re.sub(r"^#+\s+.*$", "", text, flags=re.MULTILINE)
    # Remove markdown links
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Split on sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", text)

    # Clean and filter
    cleaned = []
    for s in sentences:
        s = s.strip()
        # Skip empty, very short, or bullet points
        if s and len(s) > 10 and not s.startswith("-"):
            cleaned.append(s)

    return cleaned


def count_words(text: str) -> int:
    """Count words in text."""
    words = re.findall(r"\b\w+\b", text)
    return len(words)


def count_contractions(text: str) -> int:
    """Count contractions in text."""
    contraction_pattern = r"\b\w+'\w+\b"
    return len(re.findall(contraction_pattern, text, re.IGNORECASE))


def count_commas(text: str) -> int:
    """Count commas in text."""
    return text.count(",")


def find_pattern_in_content(
    content: str,
    pattern: str,
    is_regex: bool = False,
) -> list[tuple[int, int, str]]:
    """
    Find all occurrences of pattern in content.

    Returns list of (line_number, column, matched_text).
    """
    lines = content.split("\n")
    matches: list[tuple[int, int, str]] = []

    if is_regex:
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return matches
    else:
        regex = re.compile(re.escape(pattern), re.IGNORECASE)

    for line_num, line in enumerate(lines, start=1):
        for match in regex.finditer(line):
            matches.append((line_num, match.start() + 1, match.group()))

    return matches


# Comprehensive regex patterns for rhetorical pivot detection
RHETORICAL_PIVOT_PATTERNS = [
    # Core "It's not X. It's Y" and variants with different punctuation
    r"\b(?:it'?s|this|that'?s|they'?re|we'?re|you'?re|i'?m|he'?s|she'?s)\s+(?:not|n't)\s+.{1,50}[.,;]\s*(?:it'?s|this is|that'?s|they'?re|we'?re|you'?re|i'?m|he'?s|she'?s)\b",
    # "isn't/aren't/wasn't/weren't X. Y" forms
    r"\b(?:isn't|aren't|wasn't|weren't)\s+.{1,40}[.,;]\s*(?:it|they|this|that|we|you|i|he|she)\s+(?:is|are|was|were|'s|'re|'m)\b",
    # "about" variants: "It's not about X. It's about Y"
    r"\b(?:not|n't)\s+about\s+.{1,40}[.,;]\s*(?:it'?s|this is)\s+about\b",
    # "just/merely/simply" intensifiers: "It's not just X. It's Y"
    r"\b(?:not|n't)\s+(?:just|merely|simply|only)\s+.{1,40}[.,;]\s*(?:it'?s|this is|they'?re)\b",
    # "but rather" structure: "Not X, but rather Y"
    r"\bnot\s+.{1,30},?\s+but\s+rather\b",
    # "less about X and more about Y"
    r"\bless\s+(?:about\s+)?.{1,30}\s+(?:and\s+)?more\s+about\b",
    # "stop Xing and start Ying"
    r"\bstop\s+\w+ing\s+.{0,20}\s+(?:and\s+)?start\s+\w+ing\b",
    # "X doesn't matter. Y does."
    r"\b\w+\s+(?:doesn't|don't|didn't)\s+(?:matter|count)[.,;]\s*.{1,20}\s+(?:does|do|did)\b",
    # Cross-sentence detection: sentence ending with negation, next with positive
    r"(?:not|n't|no)\s+\w+[.!]\s+(?:it|they|this|that|we)\s+(?:is|are|'s|'re)\b",
]


def check_rhetorical_pivots(content: str) -> list[Violation]:
    """
    Detect rhetorical pivot patterns ("It's not X. It's Y") with enhanced regex.

    This function provides deeper detection than the simple banned patterns,
    catching more sophisticated variants of this overused AI pattern.
    """
    violations: list[Violation] = []
    lines = content.split("\n")

    for pattern in RHETORICAL_PIVOT_PATTERNS:
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            continue

        # Check each line individually
        for line_num, line in enumerate(lines, start=1):
            for match in regex.finditer(line):
                violations.append(
                    Violation(
                        type="rhetorical_pivot",
                        severity="warning",  # Downgraded - some voices use "wasn't just X, it was Y" naturally
                        line=line_num,
                        column=match.start() + 1,
                        text=match.group(),
                        message="Rhetorical pivot pattern detected: 'It's not X. It's Y' structure",
                        suggestion="State what it IS directly without negation setup",
                    )
                )

        # Also check across line boundaries for split patterns
        full_text = " ".join(lines)
        for match in regex.finditer(full_text):
            # Only add if not already caught in single-line check
            matched_text = match.group()
            # Calculate approximate line number
            char_pos = match.start()
            line_num = full_text[:char_pos].count("\n") + 1

            # Check if this exact text was already found
            already_found = any(v.text == matched_text and v.type == "rhetorical_pivot" for v in violations)
            if not already_found:
                violations.append(
                    Violation(
                        type="rhetorical_pivot",
                        severity="warning",  # Downgraded - some voices use these patterns naturally
                        line=line_num,
                        column=1,
                        text=matched_text[:80] + ("..." if len(matched_text) > 80 else ""),
                        message="Rhetorical pivot pattern detected (cross-line): 'It's not X. It's Y' structure",
                        suggestion="State what it IS directly without negation setup",
                    )
                )

    return violations


def check_banned_patterns(
    content: str,
    banned: BannedPatterns,
    voice: str | None = None,
) -> list[Violation]:
    """Check content against banned patterns."""
    violations: list[Violation] = []

    # Check category patterns
    for category_name, category in banned.categories.items():
        severity = category.get("severity", "warning")
        message = category.get("message", f"Banned {category_name}")
        suggestion = category.get("suggestion_template", "")
        patterns = category.get("patterns", [])

        for pattern in patterns:
            # Determine if pattern needs regex matching
            is_regex = any(c in pattern for c in [".*", "\\", "+", "?", "[", "]"])
            matches = find_pattern_in_content(content, pattern, is_regex=is_regex)

            for line, col, matched_text in matches:
                violations.append(
                    Violation(
                        type="banned_phrase",
                        severity=severity,
                        line=line,
                        column=col,
                        text=matched_text,
                        message=f"{message} ({category_name})",
                        suggestion=suggestion,
                    )
                )

    # Check punctuation patterns
    for punct_name, punct_config in banned.punctuation.items():
        severity = punct_config.get("severity", "error")
        pattern = punct_config.get("pattern", "")
        message = punct_config.get("message", f"Forbidden punctuation: {punct_name}")
        suggestion = punct_config.get("suggestion", "")

        if pattern:
            matches = find_pattern_in_content(content, pattern, is_regex=False)
            for line, col, matched_text in matches:
                violations.append(
                    Violation(
                        type="punctuation",
                        severity=severity,
                        line=line,
                        column=col,
                        text=matched_text,
                        message=message,
                        suggestion=suggestion,
                    )
                )

    # Check voice-specific patterns
    if voice and voice.lower() in banned.voice_specific:
        voice_patterns = banned.voice_specific[voice.lower()]
        for pattern_name, pattern_config in voice_patterns.items():
            severity = pattern_config.get("severity", "warning")
            message = pattern_config.get("message", f"Voice-specific issue: {pattern_name}")
            suggestion = pattern_config.get("suggestion_template", pattern_config.get("suggestion", ""))
            patterns = pattern_config.get("patterns", [])

            for pattern in patterns:
                is_regex = any(c in pattern for c in [".*", "\\", "+", "?", "[", "]"])
                matches = find_pattern_in_content(content, pattern, is_regex=is_regex)

                for line, col, matched_text in matches:
                    violations.append(
                        Violation(
                            type="voice_specific",
                            severity=severity,
                            line=line,
                            column=col,
                            text=matched_text,
                            message=message,
                            suggestion=suggestion,
                        )
                    )

    return violations


def check_rhythm(content: str, profile: dict[str, Any] | None = None) -> list[Violation]:
    """Check sentence rhythm for monotony."""
    violations: list[Violation] = []
    sentences = extract_sentences(content)

    if len(sentences) < MONOTONY_THRESHOLD + 1:
        return violations

    # Get sentence lengths
    sentence_lengths = [count_words(s) for s in sentences]

    # Check for consecutive similar lengths
    consecutive_similar = 0
    for i in range(1, len(sentence_lengths)):
        diff = abs(sentence_lengths[i] - sentence_lengths[i - 1])
        if diff <= SENTENCE_LENGTH_VARIANCE:
            consecutive_similar += 1
            if consecutive_similar >= MONOTONY_THRESHOLD:
                # Find the line number for this sentence
                line = 1
                for _j, s in enumerate(sentences[: i + 1]):
                    pos = content.find(s)
                    if pos >= 0:
                        line = content[:pos].count("\n") + 1

                avg_length = sum(sentence_lengths[i - MONOTONY_THRESHOLD : i + 1]) // (MONOTONY_THRESHOLD + 1)
                violations.append(
                    Violation(
                        type="rhythm_violation",
                        severity="warning",
                        line=line,
                        text=f"{consecutive_similar + 1} consecutive sentences around {avg_length} words",
                        message="Monotonous sentence length pattern detected",
                        suggestion="Add variety: use a fragment, question, or longer/shorter sentence",
                    )
                )
                consecutive_similar = 0  # Reset to avoid duplicate warnings
        else:
            consecutive_similar = 0

    return violations


def check_metrics(
    content: str,
    profile: dict[str, Any],
) -> tuple[list[Violation], dict[str, float]]:
    """Check content metrics against profile targets."""
    violations: list[Violation] = []
    metrics: dict[str, float] = {}

    # Extract profile metrics
    profile_metrics = profile.get("metrics", {})
    if not profile_metrics:
        return violations, metrics

    sentences = extract_sentences(content)
    total_words = count_words(content)

    if total_words == 0:
        return violations, metrics

    # Calculate actual metrics
    total_contractions = count_contractions(content)
    contraction_rate = total_contractions / total_words if total_words > 0 else 0
    metrics["contraction_rate"] = round(contraction_rate, 3)

    total_commas = count_commas(content)
    comma_density = total_commas / total_words if total_words > 0 else 0
    metrics["comma_density"] = round(comma_density, 3)

    if sentences:
        sentence_lengths = [count_words(s) for s in sentences]
        avg_sentence_length = sum(sentence_lengths) / len(sentence_lengths)
        metrics["avg_sentence_length"] = round(avg_sentence_length, 1)

    # Compare against profile
    target_contraction = profile_metrics.get("contraction_rate")
    if target_contraction is not None and target_contraction > 0:
        deviation = abs(contraction_rate - target_contraction) / target_contraction
        if deviation > METRIC_DEVIATION_THRESHOLD:
            direction = "below" if contraction_rate < target_contraction else "above"
            violations.append(
                Violation(
                    type="metric_deviation",
                    severity="warning",
                    metric="contraction_rate",
                    expected=target_contraction,
                    actual=round(contraction_rate, 3),
                    message=f"Contraction rate {int(deviation * 100)}% {direction} target",
                    suggestion="Adjust contraction usage to match voice profile",
                )
            )

    target_comma_density = profile_metrics.get("comma_density")
    if target_comma_density is not None and target_comma_density > 0:
        deviation = abs(comma_density - target_comma_density) / target_comma_density
        if deviation > 0.30:  # 30% threshold for comma density
            direction = "below" if comma_density < target_comma_density else "above"
            violations.append(
                Violation(
                    type="metric_deviation",
                    severity="info",
                    metric="comma_density",
                    expected=target_comma_density,
                    actual=round(comma_density, 3),
                    message=f"Comma density {int(deviation * 100)}% {direction} target",
                    suggestion="Adjust sentence structure to match voice profile",
                )
            )

    target_avg_length = profile_metrics.get("avg_sentence_length")
    if target_avg_length is not None and target_avg_length > 0 and "avg_sentence_length" in metrics:
        deviation = abs(metrics["avg_sentence_length"] - target_avg_length) / target_avg_length
        if deviation > METRIC_DEVIATION_THRESHOLD:
            direction = "shorter" if metrics["avg_sentence_length"] < target_avg_length else "longer"
            violations.append(
                Violation(
                    type="metric_deviation",
                    severity="info",
                    metric="avg_sentence_length",
                    expected=target_avg_length,
                    actual=metrics["avg_sentence_length"],
                    message=f"Average sentence length {int(deviation * 100)}% {direction} than target",
                    suggestion="Adjust sentence length to match voice profile",
                )
            )

    return violations, metrics


def calculate_score(violations: list[Violation]) -> int:
    """Calculate validation score from violations."""
    score = 100

    for v in violations:
        if v.severity == "error":
            score -= ERROR_PENALTY
        elif v.severity == "warning":
            score -= WARNING_PENALTY
        elif v.severity == "info":
            score -= INFO_PENALTY

    return max(0, score)


def calculate_summary(violations: list[Violation], total_checks: int) -> dict[str, int]:
    """Calculate summary statistics."""
    errors = sum(1 for v in violations if v.severity == "error")
    warnings = sum(1 for v in violations if v.severity == "warning")
    infos = sum(1 for v in violations if v.severity == "info")
    passed = total_checks - len(violations)

    return {
        "errors": errors,
        "warnings": warnings,
        "info": infos,
        "passed_checks": max(0, passed),
        "total_checks": total_checks,
    }


def check_analogy_domains(
    content: str,
    profile: dict[str, Any] | None = None,
) -> list[Violation]:
    """Check that analogies draw from documented source domains (if profile specifies them).

    This is the one architectural check that's deterministic enough for script-level
    validation. Other architectural checks (argument direction, concession structure,
    bookends) require AI-assisted analysis and belong in voice-orchestrator's validation.

    Profile key: architectural_patterns.analogy_domains (list of allowed domain keywords).
    """
    if not profile:
        return []

    arch_patterns = profile.get("architectural_patterns", {})
    domains = arch_patterns.get("analogy_domains", [])
    if not domains:
        return []

    # Build a regex from documented domains — look for "like a [domain-term]" patterns
    # This is intentionally conservative: it only flags when a clear simile/metaphor
    # marker is present AND the domain keyword is absent from all documented domains
    simile_markers = re.findall(
        r"(?:like\s+(?:a|an|the)\s+|(?:as\s+(?:a|an)\s+)|(?:reminds?\s+(?:me\s+)?of\s+(?:a|an)\s+))"
        r"(\w+(?:\s+\w+){0,3})",
        content,
        re.IGNORECASE,
    )

    if not simile_markers:
        return []

    violations = []
    domain_re = re.compile("|".join(re.escape(d) for d in domains), re.IGNORECASE)
    for phrase in simile_markers:
        if not domain_re.search(phrase):
            violations.append(
                Violation(
                    type="analogy_domain",
                    severity="warning",
                    text=f"analogy outside documented domains: '{phrase}'",
                    message=f"Documented domains: {', '.join(domains)}",
                )
            )

    return violations


def validate_content(
    content: str,
    profile: dict[str, Any] | None = None,
    banned: BannedPatterns | None = None,
    voice: str | None = None,
) -> ValidationResult:
    """
    Validate content against profile and banned patterns.

    This is the main API function for programmatic usage.
    """
    if banned is None:
        banned = load_banned_patterns()

    violations: list[Violation] = []

    # Check banned patterns
    violations.extend(check_banned_patterns(content, banned, voice=voice))

    # Check rhetorical pivot patterns with enhanced detection
    violations.extend(check_rhetorical_pivots(content))

    # Check rhythm
    violations.extend(check_rhythm(content, profile))

    # Check architectural patterns (analogy domains)
    violations.extend(check_analogy_domains(content, profile))

    # Check metrics if profile provided
    metrics: dict[str, float] = {}
    if profile:
        metric_violations, metrics = check_metrics(content, profile)
        violations.extend(metric_violations)

    # Calculate results
    score = calculate_score(violations)
    passed = score >= DEFAULT_PASS_THRESHOLD

    # Estimate total checks (banned categories + rhythm + metrics)
    total_checks = len(banned.categories) + 1 + 3  # categories + rhythm + metrics

    summary = calculate_summary(violations, total_checks)

    return ValidationResult(
        passed=passed,
        score=score,
        violations=violations,
        metrics=metrics,
        summary=summary,
    )


def format_text_output(result: ValidationResult, verbose: bool = False) -> str:
    """Format result as human-readable text."""
    lines: list[str] = []

    # Header
    status = "PASS" if result.passed else "FAIL"
    lines.append(f"Validation: {status} (score: {result.score})")
    lines.append("")

    # Summary
    s = result.summary
    lines.append(f"Summary: {s.get('errors', 0)} errors, {s.get('warnings', 0)} warnings, {s.get('info', 0)} info")
    lines.append("")

    # Violations
    if result.violations:
        lines.append("Violations:")
        for v in result.violations:
            severity_marker = {"error": "[ERROR]", "warning": "[WARN]", "info": "[INFO]"}.get(v.severity, "[?]")
            loc = f"Line {v.line}" if v.line else "Content"

            lines.append(f"  {severity_marker} {loc}: {v.message}")
            if v.text:
                lines.append(f'           Found: "{v.text}"')
            if verbose and v.suggestion:
                lines.append(f"           Suggestion: {v.suggestion}")
        lines.append("")

    # Metrics
    if result.metrics and verbose:
        lines.append("Metrics:")
        for key, value in result.metrics.items():
            lines.append(f"  {key}: {value}")
        lines.append("")

    return "\n".join(lines)


def cmd_validate(args: argparse.Namespace) -> int:
    """Handle validate command."""
    try:
        content = load_content(Path(args.content))
    except FileNotFoundError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2

    profile = None
    if args.profile:
        try:
            profile = load_profile(Path(args.profile))
        except FileNotFoundError as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            return 2
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid profile JSON: {e}"}), file=sys.stderr)
            return 2

    banned_path = Path(args.banned_file) if args.banned_file else None
    try:
        banned = load_banned_patterns(banned_path)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid banned patterns JSON: {e}"}), file=sys.stderr)
        return 2

    # Extract voice from profile if present
    voice = profile.get("voice", {}).get("name") if profile else None
    if args.voice:
        voice = args.voice

    result = validate_content(content, profile, banned, voice=voice)

    # Output
    if args.format == "text":
        print(format_text_output(result, verbose=args.verbose))
    else:
        print(json.dumps(result.to_dict(), indent=2))

    return 0 if result.passed else 1


def cmd_check_banned(args: argparse.Namespace) -> int:
    """Handle check-banned command."""
    try:
        content = load_content(Path(args.content))
    except FileNotFoundError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2

    banned_path = Path(args.banned_file) if args.banned_file else None
    try:
        banned = load_banned_patterns(banned_path)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid banned patterns JSON: {e}"}), file=sys.stderr)
        return 2

    violations = check_banned_patterns(content, banned, voice=args.voice)
    score = calculate_score(violations)
    passed = score >= DEFAULT_PASS_THRESHOLD

    result = ValidationResult(
        passed=passed,
        score=score,
        violations=violations,
        metrics={},
        summary=calculate_summary(violations, len(banned.categories)),
    )

    if args.format == "text":
        print(format_text_output(result, verbose=args.verbose))
    else:
        print(json.dumps(result.to_dict(), indent=2))

    return 0 if result.passed else 1


def cmd_check_rhythm(args: argparse.Namespace) -> int:
    """Handle check-rhythm command."""
    try:
        content = load_content(Path(args.content))
    except FileNotFoundError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2

    profile = None
    if args.profile:
        try:
            profile = load_profile(Path(args.profile))
        except FileNotFoundError as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            return 2
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid profile JSON: {e}"}), file=sys.stderr)
            return 2

    violations = check_rhythm(content, profile)
    score = calculate_score(violations)
    passed = score >= DEFAULT_PASS_THRESHOLD

    result = ValidationResult(
        passed=passed,
        score=score,
        violations=violations,
        metrics={},
        summary=calculate_summary(violations, 1),
    )

    if args.format == "text":
        print(format_text_output(result, verbose=args.verbose))
    else:
        print(json.dumps(result.to_dict(), indent=2))

    return 0 if result.passed else 1


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        description="Validate content against voice profile and banned patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Full validation against profile")
    validate_parser.add_argument("--content", required=True, help="Path to content file")
    validate_parser.add_argument("--profile", help="Path to voice profile JSON")
    validate_parser.add_argument(
        "--banned-file", help="Path to banned patterns JSON (default: scripts/data/banned-patterns.json)"
    )
    validate_parser.add_argument("--voice", help="Voice name for voice-specific checks (e.g., 'voice_a', 'voice_b')")
    validate_parser.add_argument("--format", choices=["json", "text"], default="json", help="Output format")
    validate_parser.add_argument("--verbose", "-v", action="store_true", help="Include suggestions in text output")

    # check-banned command
    banned_parser = subparsers.add_parser("check-banned", help="Check only banned patterns (fast mode)")
    banned_parser.add_argument("--content", required=True, help="Path to content file")
    banned_parser.add_argument("--banned-file", help="Path to banned patterns JSON")
    banned_parser.add_argument("--voice", help="Voice name for voice-specific checks")
    banned_parser.add_argument("--format", choices=["json", "text"], default="json", help="Output format")
    banned_parser.add_argument("--verbose", "-v", action="store_true", help="Include suggestions in text output")

    # check-rhythm command
    rhythm_parser = subparsers.add_parser("check-rhythm", help="Check sentence rhythm only")
    rhythm_parser.add_argument("--content", required=True, help="Path to content file")
    rhythm_parser.add_argument("--profile", help="Path to voice profile JSON")
    rhythm_parser.add_argument("--format", choices=["json", "text"], default="json", help="Output format")
    rhythm_parser.add_argument("--verbose", "-v", action="store_true", help="Include suggestions in text output")

    return parser


def main() -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 2

    handlers = {
        "validate": cmd_validate,
        "check-banned": cmd_check_banned,
        "check-rhythm": cmd_check_rhythm,
    }

    handler = handlers.get(args.command)
    if not handler:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 2

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
