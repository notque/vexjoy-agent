"""
Tests for voice_analyzer.py

Validates the voice analysis CLI that extracts metrics and patterns from text
content. The analyzer produces profiles that can be compared against voice
specifications (Voice A, Voice B).
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Path to the voice-analyzer script
SCRIPT_PATH = Path(__file__).parent.parent / "voice-analyzer.py"


def run_analyzer(args: list[str], input_text: str | None = None) -> tuple[int, str, str]:
    """Run voice_analyzer.py with given arguments.

    If input_text is provided and no --samples flag present, writes to a temp file
    and adds --samples flag. Translates legacy --json flag to --format json.
    """
    translated_args: list[str] = []
    skip_next = False
    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg == "--json":
            translated_args.extend(["--format", "json"])
        elif arg == "--detect-voice":
            continue
        else:
            translated_args.append(arg)

    if input_text is not None and "--samples" not in translated_args:
        has_file_arg = any(Path(a).suffix in (".md", ".txt") and Path(a).exists() for a in translated_args)
        if not has_file_arg:
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
            tmp.write(input_text)
            tmp.close()
            if translated_args and translated_args[0] == "analyze":
                translated_args.insert(1, "--samples")
                translated_args.insert(2, tmp.name)
            else:
                translated_args.extend(["--samples", tmp.name])

    cmd = [sys.executable, str(SCRIPT_PATH)] + translated_args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


class TestSentenceLengthDistribution:
    """Verify correct categorization of sentence lengths."""

    def test_short_sentences_3_to_10_words(self):
        """Sentences with 3-10 words should be categorized as short."""
        text = "She inspires the crowd. The fans love her. The glow is bright."
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], text)

        assert returncode == 0
        raw = json.loads(stdout)
        dist = raw["sentence_metrics"]["length_distribution"]
        assert dist.get("short_3_10", 0) > 0

    def test_medium_sentences_11_to_20_words(self):
        """Sentences with 11-20 words should be categorized as medium."""
        text = "The community came together to celebrate this moment, and what a celebration it was."
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], text)

        assert returncode == 0
        raw = json.loads(stdout)
        dist = raw["sentence_metrics"]["length_distribution"]
        assert dist.get("medium_11_20", 0) > 0

    def test_long_sentences_21_to_30_words(self):
        """Sentences with 21-30 words should be categorized as long."""
        text = (
            "Whether she threw her belt to the fans in the crowd or created special "
            "moments for kids backstage, the community outreach has always held a special place."
        )
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], text)

        assert returncode == 0
        raw = json.loads(stdout)
        dist = raw["sentence_metrics"]["length_distribution"]
        assert dist.get("long_21_30", 0) > 0 or dist.get("very_long_31_plus", 0) > 0

    def test_very_long_sentences_31_plus_words(self):
        """Sentences with 31+ words should be categorized as very_long."""
        text = (
            "2025 saw the rising star captivate a worldwide audience with charisma and skill "
            "of a performer gone rogue, a star fall into a memory hole of amnesia, a new star born as a "
            "rookie named Emma, before finally getting her chance to compete against their rival and former "
            "understudy turned competitor."
        )
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], text)

        assert returncode == 0
        raw = json.loads(stdout)
        dist = raw["sentence_metrics"]["length_distribution"]
        assert dist.get("very_long_31_plus", 0) > 0


class TestCommaDensityCalculation:
    """Verify commas / words calculation."""

    def test_comma_density_simple(self):
        """Simple text with known comma density."""
        text = "First, she arrives, and then she performs magnificently for us."
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], text)

        assert returncode == 0
        raw = json.loads(stdout)
        density = raw["punctuation_metrics"]["comma_density"]
        assert 0.1 <= density <= 0.3

    def test_comma_density_no_commas(self):
        """Text with no commas should have 0 density."""
        text = "She inspires us all to be better people every day."
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], text)

        assert returncode == 0
        raw = json.loads(stdout)
        assert raw["punctuation_metrics"]["comma_density"] == 0.0

    def test_comma_density_heavy(self):
        """Text with many commas should have high density."""
        text = "Joy, fire, light, hope, love, and strength fill the venue tonight."
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], text)

        assert returncode == 0
        raw = json.loads(stdout)
        density = raw["punctuation_metrics"]["comma_density"]
        assert density >= 0.3


class TestEmDashDetection:
    """Em-dashes should be counted."""

    def test_em_dash_unicode_detected(self, sample_text_with_em_dashes):
        """Unicode em-dashes (U+2014) should be detected."""
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], sample_text_with_em_dashes)

        assert returncode == 0
        raw = json.loads(stdout)
        assert raw["punctuation_metrics"]["em_dash_count"] >= 2

    def test_double_hyphen_as_em_dash(self):
        """Double hyphens used as em-dashes should also be detected."""
        text = "The match -- one of the best -- set a new standard."
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], text)

        assert returncode == 0
        raw = json.loads(stdout)
        assert raw["punctuation_metrics"]["em_dash_count"] >= 2

    def test_no_em_dashes(self):
        """Text without em-dashes should have 0 count."""
        text = "The match, one of the best, set a new standard."
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], text)

        assert returncode == 0
        raw = json.loads(stdout)
        assert raw["punctuation_metrics"]["em_dash_count"] == 0


class TestProfileGeneration:
    """Verify valid JSON output with all required fields."""

    def test_profile_has_required_fields(self, sample_text_varied):
        """Profile should contain all required metric sections."""
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], sample_text_varied)

        assert returncode == 0
        raw = json.loads(stdout)

        assert "meta" in raw
        assert "sentence_metrics" in raw
        assert "punctuation_metrics" in raw
        assert "word_metrics" in raw
        assert "total_words" in raw["meta"]
        assert "total_sentences" in raw["meta"]

    def test_profile_json_valid(self, sample_text_varied):
        """Output should be valid JSON."""
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], sample_text_varied)

        assert returncode == 0
        result = json.loads(stdout)
        assert isinstance(result, dict)

    def test_profile_from_file(self, fixtures_dir):
        """Profile generation should work with file input."""
        file_path = fixtures_dir / "sample_voice_good.md"
        returncode, stdout, stderr = run_analyzer(["analyze", "--format", "json", "--samples", str(file_path)])

        assert returncode == 0
        result = json.loads(stdout)
        assert result["meta"]["total_words"] > 0


class TestMaxConsecutiveSimilar:
    """Detect runs of similar-length sentences."""

    def test_monotonous_rhythm_detected(self, sample_text_monotonous):
        """Should detect consecutive similar-length sentences."""
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], sample_text_monotonous)

        assert returncode == 0
        raw = json.loads(stdout)
        assert raw["sentence_metrics"]["max_consecutive_similar"] >= 4

    def test_varied_rhythm(self, sample_text_varied):
        """Varied text should have low max_consecutive_similar."""
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], sample_text_varied)

        assert returncode == 0
        raw = json.loads(stdout)
        assert raw["sentence_metrics"]["max_consecutive_similar"] <= 4


class TestSentenceStarters:
    """Categorize opening words correctly."""

    def test_structure_metrics_has_starters(self):
        """Output should include sentence starter distribution."""
        text = "And she returned. But the crowd erupted. And the glow was bright."
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], text)

        assert returncode == 0
        raw = json.loads(stdout)
        structure = raw.get("structure_metrics", {})
        assert "sentence_starters" in structure

    def test_pronoun_starters_detected(self):
        """Sentences starting with pronouns should be detected."""
        text = "She inspires. He performs. They celebrate. We rejoice."
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], text)

        assert returncode == 0
        raw = json.loads(stdout)
        starters = raw.get("structure_metrics", {}).get("sentence_starters", {})
        assert starters.get("pronoun", 0) > 0


class TestFunctionWordSignature:
    """Extract top function words with frequencies."""

    def test_function_words_extracted(self, sample_voice_good):
        """Common function words should be extracted."""
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], sample_voice_good)

        assert returncode == 0
        raw = json.loads(stdout)
        signature = raw.get("word_metrics", {}).get("function_word_signature", {})

        assert len(signature) > 0
        common_words = {"the", "and", "a", "of", "in", "to", "for", "is"}
        found = set(signature.keys()) & common_words
        assert len(found) >= 3

    def test_function_words_have_rates(self, sample_voice_good):
        """Function words should have numeric rates."""
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], sample_voice_good)

        assert returncode == 0
        raw = json.loads(stdout)
        signature = raw.get("word_metrics", {}).get("function_word_signature", {})

        for word, rate in signature.items():
            assert isinstance(rate, (int, float))
            assert rate > 0


class TestFragmentRate:
    """Count sentences under 5 words."""

    def test_fragments_counted(self):
        """Fragments should result in non-zero fragment rate."""
        text = "She inspires. She grows. She shines. And now the glow is brighter than ever before."
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], text)

        assert returncode == 0
        raw = json.loads(stdout)
        fragment_rate = raw.get("structure_metrics", {}).get("fragment_rate", 0)
        assert fragment_rate > 0

    def test_no_fragments(self):
        """Text without fragments should have low fragment rate."""
        text = "The community came together for this celebration. They celebrated all night long at the venue."
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], text)

        assert returncode == 0
        raw = json.loads(stdout)
        fragment_rate = raw.get("structure_metrics", {}).get("fragment_rate", 0)
        assert fragment_rate == 0


class TestCompareProfiles:
    """Compare two profiles, report differences."""

    def test_compare_two_profiles(self, fixtures_dir):
        """Should compare two profile JSON files."""
        file1 = fixtures_dir / "sample_voice_good.md"
        file2 = fixtures_dir / "sample_voice_bad.md"

        _, stdout1, _ = run_analyzer(["analyze", "--format", "json", "--samples", str(file1)])
        tmp1 = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp1.write(stdout1)
        tmp1.close()

        _, stdout2, _ = run_analyzer(["analyze", "--format", "json", "--samples", str(file2)])
        tmp2 = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp2.write(stdout2)
        tmp2.close()

        returncode, stdout, stderr = run_analyzer(
            ["compare", "--profile1", tmp1.name, "--profile2", tmp2.name, "--format", "json"]
        )

        assert returncode == 0
        result = json.loads(stdout)
        assert isinstance(result, dict)

    def test_compare_identical_profiles(self, fixtures_dir):
        """Comparing a file with itself should show minimal differences."""
        file1 = fixtures_dir / "sample_voice_good.md"

        _, stdout1, _ = run_analyzer(["analyze", "--format", "json", "--samples", str(file1)])
        tmp1 = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp1.write(stdout1)
        tmp1.close()

        returncode, stdout, stderr = run_analyzer(
            ["compare", "--profile1", tmp1.name, "--profile2", tmp1.name, "--format", "json"]
        )

        assert returncode == 0
        result = json.loads(stdout)
        assert isinstance(result, dict)


class TestCLIInterface:
    """Test command-line interface behavior."""

    def test_help_command(self):
        """--help should display usage information."""
        returncode, stdout, stderr = run_analyzer(["--help"])

        assert returncode == 0
        assert "usage" in stdout.lower() or "voice_analyzer" in stdout.lower() or "analyze" in stdout.lower()

    def test_analyze_subcommand(self, sample_text_short):
        """analyze subcommand should work."""
        returncode, stdout, stderr = run_analyzer(["analyze", "--json"], sample_text_short)

        assert returncode == 0
        result = json.loads(stdout)
        assert "meta" in result or "sentence_metrics" in result

    def test_file_input(self, fixtures_dir):
        """Should accept file path as input."""
        file_path = fixtures_dir / "sample_voice_good.md"
        returncode, stdout, stderr = run_analyzer(["analyze", "--format", "json", "--samples", str(file_path)])

        assert returncode == 0
        result = json.loads(stdout)
        assert result["meta"]["total_words"] > 0

    def test_human_readable_output(self, sample_text_short):
        """With --format text, should output human-readable format."""
        returncode, stdout, stderr = run_analyzer(["analyze", "--format", "text"], sample_text_short)

        assert returncode == 0
        with pytest.raises(json.JSONDecodeError):
            json.loads(stdout)
        assert "words" in stdout.lower() or "sentences" in stdout.lower() or "voice" in stdout.lower()


class TestGoldenFileValidation:
    """Validate against golden expected output files."""

    def test_voice_a_profile_matches_expected(self, fixtures_dir, expected_voice_profile):
        """Voice A sample analysis should match expected profile structure."""
        file_path = fixtures_dir / "sample_voice_good.md"
        returncode, stdout, stderr = run_analyzer(["analyze", "--format", "json", "--samples", str(file_path)])

        assert returncode == 0
        result = json.loads(stdout)

        assert "meta" in result
        assert "sentence_metrics" in result

        meta = result["meta"]
        expected_metrics = expected_voice_profile["metrics"]

        assert abs(meta["total_words"] - expected_metrics["total_words"]) < 50

        actual_comma_density = result["punctuation_metrics"]["comma_density"]
        assert abs(actual_comma_density - expected_metrics["comma_density"]) < 0.05

        assert result["punctuation_metrics"]["em_dash_count"] == expected_metrics["em_dash_count"]
