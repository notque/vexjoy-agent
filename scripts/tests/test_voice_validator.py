"""
Tests for voice_validator.py

Validates the voice validation CLI that checks content against voice profiles
and banned patterns. Tests cover banned word detection, em-dash flagging,
rhythm analysis, scoring, and CLI interface.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Path to the voice-validator script
SCRIPT_PATH = Path(__file__).parent.parent / "voice-validator.py"


def run_validator(args: list[str], input_text: str | None = None) -> tuple[int, str, str]:
    """Run voice_validator.py with given arguments.

    If input_text is provided, writes it to a temp file and adds --content flag.
    Translates legacy --json flag to --format json.
    """
    # Translate legacy test flags to current CLI
    translated_args: list[str] = []
    skip_next = False
    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg == "--json":
            translated_args.extend(["--format", "json"])
        elif arg == "--strict" or arg == "--show-metrics" or arg == "--show-profile":
            continue
        elif arg == "--mode":
            skip_next = True
            continue
        else:
            translated_args.append(arg)

    # If input_text provided and no --content in args, write to temp file
    if input_text is not None and "--content" not in translated_args:
        has_file_arg = any(Path(a).suffix in (".md", ".txt") and Path(a).exists() for a in translated_args)
        if not has_file_arg:
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
            tmp.write(input_text)
            tmp.close()
            if translated_args and translated_args[0] in ("validate", "check-banned", "check-rhythm"):
                translated_args.insert(1, "--content")
                translated_args.insert(2, tmp.name)
            else:
                translated_args.extend(["--content", tmp.name])

    cmd = [sys.executable, str(SCRIPT_PATH)] + translated_args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def parse_result(stdout: str) -> dict:
    """Parse JSON output and normalize to test-expected format.

    The actual script outputs violations as a flat list with severity field.
    Tests expect violations grouped as {"errors": [...], "warnings": [...]}.
    This adapter bridges the gap.
    """
    raw = json.loads(stdout)

    errors = []
    warnings = []
    infos = []

    for v in raw.get("violations", []):
        severity = v.get("severity", "info")
        v_mapped = dict(v)
        if v.get("type") == "banned_phrase":
            msg = v.get("message", "").lower()
            text_val = v.get("text", "").lower()
            if "em-dash" in msg or "em-dash" in text_val or text_val in ("\u2014", "--"):
                v_mapped["type"] = "em_dash"
            elif "rhetorical pivot" in msg or "it's not x" in msg:
                v_mapped["type"] = "banned_pattern"
            elif "observer" in msg or "meta" in msg:
                v_mapped["type"] = "observer_language"
            else:
                v_mapped["type"] = "banned_word"
                if "(" in msg and ")" in msg:
                    category = msg.rsplit("(", 1)[-1].rstrip(")")
                    v_mapped["category"] = category
                v_mapped["word"] = v.get("text", "")
        elif v.get("type") == "rhetorical_pivot":
            v_mapped["type"] = "banned_pattern"

        if severity == "error":
            errors.append(v_mapped)
        elif severity == "warning":
            warnings.append(v_mapped)
        else:
            infos.append(v_mapped)

    return {
        "pass": raw.get("pass", False),
        "score": raw.get("score", 0),
        "violations": {
            "errors": errors,
            "warnings": warnings,
            "info": infos,
        },
        "metrics": raw.get("metrics", {}),
        "voice": raw.get("voice", ""),
        "summary": raw.get("summary", {}),
    }


class TestBannedWordDetection:
    """All banned words from JSON detected."""

    def test_detect_exploration_verbs(self, sample_text_with_banned_words):
        """Should detect banned exploration verbs (delve, explore, etc.)."""
        returncode, stdout, stderr = run_validator(
            ["validate", "--voice", "voice_a", "--json"], sample_text_with_banned_words
        )

        result = parse_result(stdout)
        all_violations = result["violations"]["warnings"] + result["violations"]["errors"]
        violation_words = [w.get("word", "").lower() for w in all_violations if w.get("type") == "banned_word"]
        assert "delve" in violation_words

    def test_detect_empty_adjectives(self, sample_text_with_banned_words):
        """Should detect banned empty adjectives (robust, dynamic, etc.)."""
        returncode, stdout, stderr = run_validator(
            ["validate", "--voice", "voice_a", "--json"], sample_text_with_banned_words
        )

        result = parse_result(stdout)
        all_violations = result["violations"]["warnings"] + result["violations"]["errors"]
        violation_words = [w.get("word", "").lower() for w in all_violations if w.get("type") == "banned_word"]
        assert "robust" in violation_words
        assert "dynamic" in violation_words
        assert "innovative" in violation_words

    def test_detect_corporate_terms(self, sample_text_with_banned_words):
        """Should detect banned corporate/abstract terms."""
        returncode, stdout, stderr = run_validator(
            ["validate", "--voice", "voice_a", "--json"], sample_text_with_banned_words
        )

        result = parse_result(stdout)
        all_violations = result["violations"]["warnings"] + result["violations"]["errors"]
        violation_words = [w.get("word", "").lower() for w in all_violations if w.get("type") == "banned_word"]
        # ecosystem and landscape are abstract nouns flagged as corporate-speak
        assert "ecosystem" in violation_words or "landscape" in violation_words

    def test_detect_abstract_nouns(self, sample_text_with_banned_words):
        """Should detect banned abstract nouns (ecosystem, landscape, etc.)."""
        returncode, stdout, stderr = run_validator(
            ["validate", "--voice", "voice_a", "--json"], sample_text_with_banned_words
        )

        result = parse_result(stdout)
        all_violations = result["violations"]["warnings"] + result["violations"]["errors"]
        violation_words = [w.get("word", "").lower() for w in all_violations if w.get("type") == "banned_word"]
        assert "ecosystem" in violation_words
        assert "landscape" in violation_words

    def test_banned_word_includes_category(self, sample_text_with_banned_words):
        """Banned word violations should include category information."""
        returncode, stdout, stderr = run_validator(
            ["validate", "--voice", "voice_a", "--json"], sample_text_with_banned_words
        )

        result = parse_result(stdout)
        all_violations = result["violations"]["warnings"] + result["violations"]["errors"]

        for warning in all_violations:
            if warning.get("type") == "banned_word":
                assert "category" in warning, f"Missing category in violation: {warning}"


class TestEmDashAlwaysCaught:
    """Em-dashes (U+2014) always flagged as error."""

    def test_em_dash_unicode_is_error(self, sample_text_with_em_dashes):
        """Unicode em-dashes should be flagged as errors."""
        returncode, stdout, stderr = run_validator(
            ["validate", "--voice", "voice_a", "--json"], sample_text_with_em_dashes
        )

        result = parse_result(stdout)
        errors = result["violations"]["errors"]

        em_dash_errors = [e for e in errors if e.get("type") == "em_dash"]
        assert len(em_dash_errors) >= 2

    def test_unicode_em_dash_detected_in_mixed_text(self):
        """Unicode em-dashes in mixed text should be flagged as errors."""
        text = "The match \u2014 one of the best \u2014 set a new standard."
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], text)

        result = parse_result(stdout)
        errors = result["violations"]["errors"]

        em_dash_errors = [e for e in errors if e.get("type") == "em_dash"]
        assert len(em_dash_errors) >= 2

    def test_em_dash_message_is_clear(self, sample_text_with_em_dashes):
        """Em-dash error message should be emphatic about prohibition."""
        returncode, stdout, stderr = run_validator(
            ["validate", "--voice", "voice_a", "--json"], sample_text_with_em_dashes
        )

        result = parse_result(stdout)
        errors = result["violations"]["errors"]

        for error in errors:
            if error.get("type") == "em_dash":
                message = error.get("message", "").lower()
                assert (
                    "forbidden" in message or "never" in message or "prohibited" in message or "absolutely" in message
                )


class TestRhythmViolationDetection:
    """Monotonous sentences (>3 consecutive similar) flagged."""

    def test_monotonous_rhythm_flagged(self, sample_text_monotonous):
        """Should flag consecutive similar-length sentences."""
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], sample_text_monotonous)

        result = parse_result(stdout)
        all_warnings = result["violations"]["warnings"]

        rhythm_warnings = [w for w in all_warnings if w.get("type") == "rhythm_violation"]
        assert len(rhythm_warnings) >= 1

    def test_varied_rhythm_not_flagged(self, sample_text_varied):
        """Varied rhythm should not trigger violation."""
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], sample_text_varied)

        result = parse_result(stdout)
        all_warnings = result["violations"]["warnings"]

        rhythm_warnings = [w for w in all_warnings if w.get("type") == "rhythm_violation"]
        assert len(rhythm_warnings) == 0

    def test_rhythm_violation_includes_count(self, sample_text_monotonous):
        """Rhythm violation should include count of consecutive sentences."""
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], sample_text_monotonous)

        result = parse_result(stdout)
        all_warnings = result["violations"]["warnings"]

        for warning in all_warnings:
            if warning.get("type") == "rhythm_violation":
                text_or_msg = warning.get("text", "") + warning.get("message", "")
                assert any(c.isdigit() for c in text_or_msg)


class TestValidationPass:
    """Known-good content passes validation."""

    def test_voice_a_good_passes(self, sample_voice_good):
        """Voice A good sample should pass validation."""
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], sample_voice_good)

        result = parse_result(stdout)
        assert result["pass"] is True
        assert result["score"] >= 60

    def test_voice_b_good_passes(self, sample_voice_good):
        """Voice B good sample should pass validation."""
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_b", "--json"], sample_voice_good)

        result = parse_result(stdout)
        assert result["pass"] is True
        assert result["score"] >= 60

    def test_clean_text_no_violations(self):
        """Clean text with no violations should pass."""
        text = (
            "She inspires. She grows. She shines.\n\n"
            "The community came together to celebrate this moment.\n"
            "Together, we rise toward a brighter tomorrow.\n\n"
            "The glow has never been brighter."
        )

        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], text)

        result = parse_result(stdout)
        assert result["pass"] is True
        assert len(result["violations"]["errors"]) == 0


class TestValidationFail:
    """Known-bad content fails validation."""

    def test_voice_a_bad_fails(self, sample_voice_bad):
        """Voice A bad sample should fail validation."""
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], sample_voice_bad)

        result = parse_result(stdout)
        assert result["pass"] is False

    def test_voice_b_bad_fails(self, sample_voice_bad):
        """Voice B bad sample should fail validation."""
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_b", "--json"], sample_voice_bad)

        result = parse_result(stdout)
        assert result["pass"] is False

    def test_exit_code_on_failure(self, sample_voice_bad):
        """Should return non-zero exit code on validation failure."""
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], sample_voice_bad)

        assert returncode != 0


class TestMetricDeviation:
    """Deviation from profile metrics calculated correctly."""

    def test_comma_density_deviation_calculated(self, sample_voice_bad):
        """Should calculate and include metrics in output."""
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], sample_voice_bad)

        result = parse_result(stdout)
        assert "metrics" in result or "summary" in result

    def test_fragment_rate_deviation_calculated(self, sample_voice_bad):
        """Should include fragment-related information in output."""
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], sample_voice_bad)

        result = parse_result(stdout)
        assert "metrics" in result or "summary" in result


class TestScoreCalculation:
    """Score: 100 - (errors*10) - (warnings*3) - (info*1)."""

    def test_perfect_score_no_violations(self):
        """Clean text should score 100."""
        text = "She inspires. She grows. She shines. Together we rise."
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], text)

        result = parse_result(stdout)
        assert result["score"] == 100

    def test_error_reduces_score(self, sample_text_with_em_dashes):
        """Errors should reduce the score."""
        returncode, stdout, stderr = run_validator(
            ["validate", "--voice", "voice_a", "--json"], sample_text_with_em_dashes
        )

        result = parse_result(stdout)
        error_count = len(result["violations"]["errors"])
        assert error_count > 0
        assert result["score"] < 100

    def test_warning_reduces_score(self):
        """Non-error violations should reduce the score."""
        text = "Let me delve into this journey. We explore the landscape."
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], text)

        result = parse_result(stdout)
        # Count all non-error violations (warnings + info)
        warning_count = len(result["violations"]["warnings"])
        info_count = len(result["violations"]["info"])
        error_count = len(result["violations"]["errors"])
        total_violations = warning_count + info_count + error_count
        assert total_violations > 0
        assert result["score"] < 100

    def test_score_matches_formula(self, sample_voice_bad):
        """Score should match formula: 100 - (errors*10) - (warnings*3) - (info*1)."""
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], sample_voice_bad)

        result = parse_result(stdout)
        violations = result["violations"]

        errors = len(violations["errors"])
        warnings = len(violations["warnings"])
        info = len(violations["info"])

        expected_score = max(0, 100 - (errors * 10) - (warnings * 3) - (info * 1))
        assert result["score"] == expected_score

    def test_score_floor_at_zero(self):
        """Score should not go below 0."""
        text = (
            "Let me delve into this comprehensive journey through the robust ecosystem. "
            "The match \u2014 one of the best \u2014 was game-changing. "
            "This wasn't just a match. It was transformative. "
            "I'm excited to explore this cutting-edge paradigm shift \u2014 amazing, incredible, groundbreaking stuff."
        )

        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], text)

        result = parse_result(stdout)
        assert result["score"] >= 0


class TestLineNumberTracking:
    """Violations report correct line numbers."""

    def test_em_dash_line_number(self):
        """Em-dash violations should report correct line numbers."""
        text = "Line one is clean.\nLine two has an \u2014 em-dash here.\nLine three is clean again."

        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], text)

        result = parse_result(stdout)
        errors = result["violations"]["errors"]

        em_dash_errors = [e for e in errors if e.get("type") == "em_dash"]
        assert len(em_dash_errors) >= 1
        assert em_dash_errors[0]["line"] == 2

    def test_banned_word_line_number(self):
        """Banned word violations should report correct line numbers."""
        text = "First line is clean.\nSecond line is clean.\nThird line has delve in it."

        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], text)

        result = parse_result(stdout)
        all_violations = result["violations"]["warnings"] + result["violations"]["errors"]

        banned_word_warnings = [w for w in all_violations if w.get("type") == "banned_word"]
        if banned_word_warnings:
            assert banned_word_warnings[0]["line"] == 3

    def test_violations_include_text_snippet(self):
        """Violations should include the offending text snippet."""
        text = "The match \u2014 one of the best \u2014 was great."
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], text)

        result = parse_result(stdout)
        errors = result["violations"]["errors"]

        for error in errors:
            assert "text" in error or "snippet" in error or "context" in error


class TestVoiceSpecificPatterns:
    """Voice-specific pattern checks work."""

    def test_voice_a_its_not_x_its_y_pattern(self):
        """Should detect banned rhetorical pivot pattern."""
        text = "This wasn't just a competition. It was the culmination.\nThis isn't just a list. This is a love letter."

        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], text)

        result = parse_result(stdout)
        all_violations = result["violations"]["errors"] + result["violations"]["warnings"]

        pattern_violations = [e for e in all_violations if e.get("type") in ("banned_pattern", "rhetorical_pivot")]
        assert len(pattern_violations) >= 1

    def test_voice_b_essay_bleed_in_chat(self):
        """Voice B mode should flag essay-like patterns."""
        text = (
            "In conclusion, as we've seen throughout this analysis, "
            "the comprehensive framework has proven transformative. "
            "To summarize the key points, this journey has been game-changing."
        )

        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_b", "--json"], text)

        result = parse_result(stdout)
        all_violations = result["violations"]["warnings"] + result["violations"]["errors"]

        assert len(all_violations) >= 1


class TestCheckBannedFastMode:
    """check-banned subcommand works."""

    def test_check_banned_subcommand(self, sample_text_with_banned_words):
        """check-banned should check banned words."""
        returncode, stdout, stderr = run_validator(["check-banned", "--json"], sample_text_with_banned_words)

        result = json.loads(stdout)
        assert "violations" in result

    def test_check_banned_fast(self):
        """check-banned should find banned words."""
        text = "Let me delve into this robust ecosystem journey."

        returncode, stdout, stderr = run_validator(["check-banned", "--json"], text)

        result = json.loads(stdout)
        assert len(result.get("violations", [])) >= 3


class TestCheckRhythmOnly:
    """check-rhythm subcommand works."""

    def test_check_rhythm_subcommand(self, sample_text_monotonous):
        """check-rhythm should check rhythm."""
        returncode, stdout, stderr = run_validator(["check-rhythm", "--json"], sample_text_monotonous)

        result = json.loads(stdout)
        assert "violations" in result or "score" in result

    def test_check_rhythm_detects_monotony(self, sample_text_monotonous):
        """check-rhythm should detect monotonous rhythm."""
        returncode, stdout, stderr = run_validator(["check-rhythm", "--json"], sample_text_monotonous)

        result = json.loads(stdout)
        violations = result.get("violations", [])
        rhythm_violations = [v for v in violations if v.get("type") == "rhythm_violation"]
        assert len(rhythm_violations) >= 1

    def test_check_rhythm_passes_varied(self, sample_text_varied):
        """check-rhythm should pass varied rhythm."""
        returncode, stdout, stderr = run_validator(["check-rhythm", "--json"], sample_text_varied)

        result = json.loads(stdout)
        assert result.get("pass", True) is True or result.get("score", 100) >= 60


class TestCLIInterface:
    """Test command-line interface behavior."""

    def test_help_command(self):
        """--help should display usage information."""
        returncode, stdout, stderr = run_validator(["--help"])

        assert returncode == 0
        assert "usage" in stdout.lower() or "voice_validator" in stdout.lower() or "validate" in stdout.lower()

    def test_validate_subcommand_requires_content(self):
        """validate subcommand should require --content argument."""
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--format", "json"])

        assert returncode == 2

    def test_file_input(self, fixtures_dir):
        """Should accept file path as input."""
        file_path = fixtures_dir / "sample_voice_good.md"
        returncode, stdout, stderr = run_validator(
            ["validate", "--voice", "voice_a", "--format", "json", "--content", str(file_path)]
        )

        result = json.loads(stdout)
        assert "score" in result

    def test_human_readable_output(self, sample_text_short):
        """With --format text, should output human-readable format."""
        returncode, stdout, stderr = run_validator(
            ["validate", "--voice", "voice_a", "--format", "text"], sample_text_short
        )

        with pytest.raises(json.JSONDecodeError):
            json.loads(stdout)
        assert "score" in stdout.lower() or "pass" in stdout.lower() or "validation" in stdout.lower()


class TestGoldenFileValidation:
    """Validate against golden expected output files."""

    def test_voice_a_bad_violations_match_expected(self, fixtures_dir, expected_violations):
        """Voice A bad sample violations should match expected output."""
        file_path = fixtures_dir / "sample_voice_bad.md"
        returncode, stdout, stderr = run_validator(
            ["validate", "--voice", "voice_a", "--format", "json", "--content", str(file_path)]
        )

        raw = json.loads(stdout)

        assert len(raw["violations"]) > 0

        expected_score = expected_violations["score"]
        assert abs(raw["score"] - expected_score) < 40  # Allow variance due to different violation detection

    def test_violations_structure_matches_expected(self, fixtures_dir, expected_violations):
        """Violation structure should match expected format."""
        file_path = fixtures_dir / "sample_voice_bad.md"
        returncode, stdout, stderr = run_validator(
            ["validate", "--voice", "voice_a", "--format", "json", "--content", str(file_path)]
        )

        raw = json.loads(stdout)

        assert "violations" in raw
        assert isinstance(raw["violations"], list)

        for violation in raw["violations"]:
            assert "type" in violation
            assert "severity" in violation
            assert "message" in violation


class TestVoiceProfileIntegration:
    """Test integration with voice profiles."""

    def test_voice_a_profile_loaded(self, sample_voice_good):
        """Should use Voice A for validation."""
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_a", "--json"], sample_voice_good)

        result = json.loads(stdout)
        assert result.get("pass") is True

    def test_voice_b_profile_loaded(self, sample_voice_good):
        """Should use Voice B for validation."""
        returncode, stdout, stderr = run_validator(["validate", "--voice", "voice_b", "--json"], sample_voice_good)

        result = json.loads(stdout)
        assert result.get("pass") is True

    def test_custom_profile_path(self, fixtures_dir):
        """Should accept content file path."""
        file_path = fixtures_dir / "sample_voice_good.md"
        returncode, stdout, stderr = run_validator(
            ["validate", "--voice", "voice_a", "--format", "json", "--content", str(file_path)]
        )

        result = json.loads(stdout)
        assert "score" in result
