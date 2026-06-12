"""Tests for scripts/voice-stylometry.py.

ADR voice-stylometry-upgrade: three deterministic lenses (burstiness band,
punctuation profile, inverse AI-tell detectors) plus profile decay metadata.
Seeded fixtures; pytest green is the validation verdict.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

stylo = importlib.import_module("voice-stylometry")

SCRIPT = Path(__file__).resolve().parent.parent / "voice-stylometry.py"

# ---------------------------------------------------------------------------
# Seeded fixtures
# ---------------------------------------------------------------------------

VARIED_CORPUS = """Sometimes the brightest lights shine in the darkest corners of the building.
She inspires.
The community came together to celebrate this moment, and what a celebration it was, filled with joy and laughter and the kind of warmth that only comes from shared experience.
She grows.
Whether the crowd knew it or not, the night belonged to the people who showed up early and stayed late.
Together, we rise."""

UNIFORM_DRAFT = """The match was exciting today. The crowd was very loud. The performers were all great. The finish was quite good. The show was real fun. The ending was very nice. The fans were all happy. The night was a success."""

VARIED_DRAFT = """The lights dimmed and the crowd held its breath, waiting for something none of them could name.
She walked out.
Nobody in the building expected what came next, a sequence so fast and so clean that the replay would trend for days afterward.
Silence.
Then the roar came back, louder than before, carrying everyone with it."""

EM_DASH_DRAFT = """The match — one of the best of the year — set a new standard for the company.
The underdog finally won — and the crowd erupted in disbelief.
Nobody saw it coming — least of all the champion."""

ANTITHESIS_DRAFT = """The crowd stayed long after the show ended.
It's not about the winning, it's about the story they watched unfold.
Everyone went home tired and happy."""

ANTITHESIS_SENTENCE_PAIR = """This is not a story about failure. It is a story about timing.
The rest of the night went quietly."""

TEMPORAL_OPENER_DRAFT = """In today's fast-paced world, wrestling shows compete with everything for attention.

The main event delivered anyway."""

UNIFORM_PARAGRAPH_DRAFT = """The opener set the tone early. The crowd responded with real energy. Both workers earned the reaction.

The second match slowed things down. The pacing dragged in the middle. The finish saved the segment.

The third match raised the stakes. The champion looked vulnerable throughout. The challenger gained real credibility.

The main event closed the loop. The story paid off every beat. The crowd left satisfied and loud."""

CLEAN_DRAFT = """The lights dimmed and the crowd held its breath, waiting for something none of them could name.
She walked out.
Nobody in the building expected what came next, a sequence so fast and so clean that the replay would trend for days afterward.

Silence. Then the roar came back, louder than before, carrying everyone with it. The night kept building from there.

By the final bell the building had nothing left to give."""

NOW = datetime(2026, 6, 12, tzinfo=timezone.utc)


@pytest.fixture
def varied_profile() -> dict:
    """Profile banded from the varied corpus, fresh decay metadata."""
    profile = stylo.build_band_profile([VARIED_CORPUS], refresh_after_days=90, analyzed_at=NOW)
    return profile


def rule_ids(findings) -> list[str]:
    return [f.rule_id for f in findings]


# ---------------------------------------------------------------------------
# Burstiness band
# ---------------------------------------------------------------------------


class TestBurstiness:
    def test_band_computed_from_corpus(self):
        band = stylo.compute_burstiness([VARIED_CORPUS])
        assert band["stdev"] > 0
        assert 0 <= band["band"]["min"] < band["band"]["max"]

    def test_uniform_draft_flagged(self, varied_profile):
        findings = stylo.check_burstiness(varied_profile, UNIFORM_DRAFT)
        assert rule_ids(findings) == ["burstiness.band"]
        f = findings[0]
        assert f.severity == "warning"
        assert f.span == (0, len(UNIFORM_DRAFT))

    def test_varied_draft_passes(self, varied_profile):
        assert stylo.check_burstiness(varied_profile, VARIED_DRAFT) == []

    def test_short_draft_skipped(self, varied_profile):
        assert stylo.check_burstiness(varied_profile, "One line. Two lines. Three.") == []

    def test_profile_without_band_skipped(self):
        assert stylo.check_burstiness({}, UNIFORM_DRAFT) == []


# ---------------------------------------------------------------------------
# Punctuation profile
# ---------------------------------------------------------------------------


class TestPunctuation:
    def test_classes(self):
        assert stylo.classify_rate(0.0) == "never"
        assert stylo.classify_rate(0.05) == "rare"
        assert stylo.classify_rate(0.5) == "habitual"

    def test_profile_rates_and_classes(self):
        punct = stylo.compute_punctuation([EM_DASH_DRAFT])
        assert punct["em_dash"]["class"] == "habitual"
        assert punct["semicolon"]["class"] == "never"

    def test_never_profile_flags_em_dash_draft(self, varied_profile):
        findings = stylo.check_punctuation(varied_profile, EM_DASH_DRAFT)
        assert "punctuation.em_dash" in rule_ids(findings)
        f = next(x for x in findings if x.rule_id == "punctuation.em_dash")
        assert f.severity == "warning"

    def test_matching_draft_passes(self, varied_profile):
        assert stylo.check_punctuation(varied_profile, VARIED_DRAFT) == []

    def test_profile_without_punctuation_skipped(self):
        assert stylo.check_punctuation({}, EM_DASH_DRAFT) == []


# ---------------------------------------------------------------------------
# Inverse AI-tell detectors
# ---------------------------------------------------------------------------


class TestAiTells:
    def test_corrective_antithesis_comma_form(self):
        findings = stylo.check_corrective_antithesis(ANTITHESIS_DRAFT)
        assert rule_ids(findings) == ["ai_tell.corrective_antithesis"]
        f = findings[0]
        assert f.severity == "error"
        start, end = f.span
        assert "not" in ANTITHESIS_DRAFT[start:end]
        assert f.line == 2

    def test_corrective_antithesis_sentence_pair(self):
        findings = stylo.check_corrective_antithesis(ANTITHESIS_SENTENCE_PAIR)
        assert rule_ids(findings) == ["ai_tell.corrective_antithesis"]

    def test_corrective_antithesis_clean(self):
        assert stylo.check_corrective_antithesis(CLEAN_DRAFT) == []

    def test_temporal_opener_at_paragraph_start(self):
        findings = stylo.check_temporal_openers(TEMPORAL_OPENER_DRAFT)
        assert rule_ids(findings) == ["ai_tell.temporal_opener"]
        start, end = findings[0].span
        assert TEMPORAL_OPENER_DRAFT[start:end].lower().startswith("in today")

    def test_temporal_phrase_mid_paragraph_not_flagged(self):
        text = "The show thrives even in today's crowded market.\n\nIt earned that."
        assert stylo.check_temporal_openers(text) == []

    def test_uniform_paragraphs_flagged(self):
        findings = stylo.check_uniform_paragraphs(UNIFORM_PARAGRAPH_DRAFT)
        assert rule_ids(findings) == ["ai_tell.uniform_paragraphs"]
        assert findings[0].severity == "error"

    def test_varied_paragraphs_pass(self):
        assert stylo.check_uniform_paragraphs(CLEAN_DRAFT) == []

    def test_few_paragraphs_skipped(self):
        text = "One. Two. Three.\n\nFour. Five. Six."
        assert stylo.check_uniform_paragraphs(text) == []


# ---------------------------------------------------------------------------
# Profile decay
# ---------------------------------------------------------------------------


class TestDecay:
    def test_stale_profile_warns_advisory(self):
        profile = {"analyzed_at": "2025-01-01T00:00:00+00:00", "refresh_after_days": 30}
        findings = stylo.check_decay(profile, now=NOW)
        assert rule_ids(findings) == ["profile.stale"]
        assert findings[0].severity == "advisory"

    def test_fresh_profile_passes(self):
        profile = {"analyzed_at": "2026-06-01T00:00:00+00:00", "refresh_after_days": 90}
        assert stylo.check_decay(profile, now=NOW) == []

    def test_profile_without_metadata_skipped(self):
        assert stylo.check_decay({}, now=NOW) == []

    def test_zulu_timestamp_accepted(self):
        profile = {"analyzed_at": "2025-01-01T00:00:00Z", "refresh_after_days": 30}
        assert rule_ids(stylo.check_decay(profile, now=NOW)) == ["profile.stale"]


# ---------------------------------------------------------------------------
# Orchestration + add-only compatibility
# ---------------------------------------------------------------------------


class TestCheckDraft:
    def test_planted_violations_all_detected(self, varied_profile):
        planted = "\n\n".join(
            [
                "In today's fast-paced world, every show fights for attention.",
                "It's not about the winning, it's about the story.",
                UNIFORM_PARAGRAPH_DRAFT,
            ]
        )
        findings = stylo.check_draft(varied_profile, planted, now=NOW)
        ids = set(rule_ids(findings))
        assert {"ai_tell.temporal_opener", "ai_tell.corrective_antithesis", "ai_tell.uniform_paragraphs"} <= ids

    def test_clean_draft_passes(self, varied_profile):
        findings = stylo.check_draft(varied_profile, CLEAN_DRAFT, now=NOW)
        assert [f for f in findings if f.severity in ("error", "warning")] == []

    def test_legacy_profile_without_new_fields_still_valid(self):
        legacy = json.loads((Path(__file__).parent / "fixtures" / "expected_voice_profile.json").read_text())
        findings = stylo.check_draft(legacy, CLEAN_DRAFT, now=NOW)
        assert [f for f in findings if f.severity in ("error", "warning")] == []

    def test_stale_profile_advisory_does_not_block(self, varied_profile):
        varied_profile["analyzed_at"] = "2020-01-01T00:00:00+00:00"
        findings = stylo.check_draft(varied_profile, CLEAN_DRAFT, now=NOW)
        assert rule_ids(findings) == ["profile.stale"]
        assert stylo.verdict(findings) == "pass"

    def test_finding_dict_shape(self, varied_profile):
        findings = stylo.check_draft(varied_profile, ANTITHESIS_DRAFT, now=NOW)
        d = findings[0].to_dict()
        assert set(d) == {"rule_id", "severity", "span", "line", "message"}
        assert d["span"] == {"start": d["span"]["start"], "end": d["span"]["end"]}


# ---------------------------------------------------------------------------
# Profile build
# ---------------------------------------------------------------------------


class TestBuildBandProfile:
    def test_fields_present_and_add_only(self):
        profile = stylo.build_band_profile([VARIED_CORPUS], refresh_after_days=60, analyzed_at=NOW)
        assert profile["analyzed_at"] == "2026-06-12T00:00:00+00:00"
        assert profile["refresh_after_days"] == 60
        sty = profile["stylometry"]
        assert sty["burstiness"]["band"]["min"] < sty["burstiness"]["band"]["max"]
        assert sty["punctuation"]["em_dash"]["class"] == "never"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


class TestCli:
    def test_band_command(self, tmp_path):
        sample = tmp_path / "s1.md"
        sample.write_text(VARIED_CORPUS)
        result = run_cli("band", "--samples", str(sample), "--analyzed-at", "2026-06-12T00:00:00+00:00")
        assert result.returncode == 0, result.stderr
        profile = json.loads(result.stdout)
        assert "stylometry" in profile
        assert profile["refresh_after_days"] == 90

    def test_check_clean_exits_zero(self, tmp_path):
        sample = tmp_path / "s1.md"
        sample.write_text(VARIED_CORPUS)
        band = run_cli("band", "--samples", str(sample), "--analyzed-at", "2026-06-12T00:00:00+00:00")
        profile = tmp_path / "profile.json"
        profile.write_text(band.stdout)
        draft = tmp_path / "draft.md"
        draft.write_text(CLEAN_DRAFT)
        result = run_cli(
            "check", "--profile", str(profile), "--draft", str(draft), "--now", "2026-06-12T00:00:00+00:00"
        )
        assert result.returncode == 0, result.stdout
        payload = json.loads(result.stdout)
        assert payload["verdict"] == "pass"

    def test_check_violations_exit_one(self, tmp_path):
        sample = tmp_path / "s1.md"
        sample.write_text(VARIED_CORPUS)
        band = run_cli("band", "--samples", str(sample), "--analyzed-at", "2026-06-12T00:00:00+00:00")
        profile = tmp_path / "profile.json"
        profile.write_text(band.stdout)
        draft = tmp_path / "draft.md"
        draft.write_text(ANTITHESIS_DRAFT)
        result = run_cli(
            "check", "--profile", str(profile), "--draft", str(draft), "--now", "2026-06-12T00:00:00+00:00"
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["verdict"] == "fail"
        assert payload["findings"][0]["rule_id"] == "ai_tell.corrective_antithesis"

    def test_check_stale_profile_exits_zero(self, tmp_path):
        sample = tmp_path / "s1.md"
        sample.write_text(VARIED_CORPUS)
        band = run_cli("band", "--samples", str(sample), "--analyzed-at", "2020-01-01T00:00:00+00:00")
        profile = tmp_path / "profile.json"
        profile.write_text(band.stdout)
        draft = tmp_path / "draft.md"
        draft.write_text(CLEAN_DRAFT)
        result = run_cli(
            "check", "--profile", str(profile), "--draft", str(draft), "--now", "2026-06-12T00:00:00+00:00"
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert [f["rule_id"] for f in payload["findings"]] == ["profile.stale"]
