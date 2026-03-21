"""Tests for reddit_mod.py pure functions."""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Add scripts dir to path so we can import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import reddit_mod
from reddit_mod import (
    _DEFAULT_CONFIG,
    _FULLNAME_RE,
    _SUBREDDIT_RE,
    _USERNAME_RE,
    CLASSIFICATION_CATEGORIES,
    ClassificationResult,
    _analyze_mod_log,
    _check_action_limit,
    _cmd_classify,
    _count_author_removals_today,
    _detect_scan_flags,
    build_classification_prompt,
    detect_mass_report,
    load_classification_context,
    wrap_untrusted,
)

# --- detect_mass_report ---


class TestDetectMassReport:
    """Tests for detect_mass_report(num_reports, report_reasons)."""

    @pytest.mark.parametrize(
        ("num_reports", "report_reasons", "expected", "description"),
        [
            pytest.param(
                10,
                ["spam", "harassment", "misinformation"],
                False,
                "boundary: exactly 10 reports with 3 categories",
                id="boundary-10-reports",
            ),
            pytest.param(
                11,
                ["spam", "harassment"],
                False,
                "11 reports but only 2 distinct categories",
                id="11-reports-2-categories",
            ),
            pytest.param(
                11,
                ["spam", "harassment", "misinformation"],
                True,
                "11 reports with 3 distinct categories triggers flag",
                id="11-reports-3-categories",
            ),
            pytest.param(
                11,
                ["spam", "spam", "spam", "harassment", "harassment"],
                False,
                "11 reports with duplicates reducing distinct below 3",
                id="11-reports-duplicates-below-threshold",
            ),
            pytest.param(
                0,
                [],
                False,
                "zero reports with empty list",
                id="zero-reports-empty",
            ),
            pytest.param(
                50,
                ["spam", "harassment", "misinformation", "brigading", "self-harm", "other"],
                True,
                "50 reports with 6 categories",
                id="50-reports-6-categories",
            ),
        ],
    )
    def test_detect_mass_report(
        self, num_reports: int, report_reasons: list[str], expected: bool, description: str
    ) -> None:
        assert detect_mass_report(num_reports, report_reasons) is expected, description


# --- wrap_untrusted ---


class TestWrapUntrusted:
    """Tests for wrap_untrusted(text)."""

    def test_normal_text(self) -> None:
        result = wrap_untrusted("Hello world")
        assert result == "<untrusted-content>Hello world</untrusted-content>"

    def test_strips_opening_tag(self) -> None:
        result = wrap_untrusted("prefix <untrusted-content> suffix")
        assert result == "<untrusted-content>prefix  suffix</untrusted-content>"

    def test_strips_closing_tag(self) -> None:
        result = wrap_untrusted("prefix </untrusted-content> suffix")
        assert result == "<untrusted-content>prefix  suffix</untrusted-content>"

    def test_strips_both_tags(self) -> None:
        result = wrap_untrusted("<untrusted-content>injected</untrusted-content>")
        assert result == "<untrusted-content>injected</untrusted-content>"

    def test_empty_string(self) -> None:
        result = wrap_untrusted("")
        assert result == "<untrusted-content></untrusted-content>"

    def test_nested_tag_attempts(self) -> None:
        text = "a<untrusted-content>b<untrusted-content>c</untrusted-content>d</untrusted-content>e"
        result = wrap_untrusted(text)
        # All tag occurrences stripped, then wrapped once
        assert "<untrusted-content>" not in result[len("<untrusted-content>") : -len("</untrusted-content>")]
        assert result.startswith("<untrusted-content>")
        assert result.endswith("</untrusted-content>")

    def test_multiple_opening_tags(self) -> None:
        text = "<untrusted-content><untrusted-content>double"
        result = wrap_untrusted(text)
        assert result == "<untrusted-content>double</untrusted-content>"


# --- _SUBREDDIT_RE ---


class TestSubredditRegex:
    """Tests for _SUBREDDIT_RE pattern."""

    @pytest.mark.parametrize(
        "name",
        [
            pytest.param("sap", id="lowercase"),
            pytest.param("SquaredCircle", id="mixed-case"),
            pytest.param("SAP_Cloud", id="with-underscore"),
            pytest.param("ab", id="min-length-2"),
            pytest.param("a" * 21, id="max-length-21"),
        ],
    )
    def test_valid_subreddit_names(self, name: str) -> None:
        assert _SUBREDDIT_RE.match(name) is not None, f"'{name}' should be valid"

    @pytest.mark.parametrize(
        "name",
        [
            pytest.param("a", id="too-short-1-char"),
            pytest.param("../etc", id="path-traversal"),
            pytest.param("sub with spaces", id="spaces"),
            pytest.param("", id="empty"),
            pytest.param("a" * 22, id="too-long-22-chars"),
            pytest.param("sub/path", id="slash"),
        ],
    )
    def test_invalid_subreddit_names(self, name: str) -> None:
        assert _SUBREDDIT_RE.match(name) is None, f"'{name}' should be invalid"


# --- _FULLNAME_RE ---


class TestFullnameRegex:
    """Tests for _FULLNAME_RE pattern."""

    @pytest.mark.parametrize(
        "fullname",
        [
            pytest.param("t1_abc123", id="comment"),
            pytest.param("t3_xyz", id="submission-short"),
            pytest.param("t1_a", id="single-char-id"),
            pytest.param("t3_0123456789", id="max-length-10-id"),
        ],
    )
    def test_valid_fullnames(self, fullname: str) -> None:
        assert _FULLNAME_RE.match(fullname) is not None, f"'{fullname}' should be valid"

    @pytest.mark.parametrize(
        "fullname",
        [
            pytest.param("abc123", id="no-prefix"),
            pytest.param("t2_abc", id="invalid-type-t2"),
            pytest.param("t1_", id="empty-id"),
            pytest.param("", id="empty-string"),
            pytest.param("t4_abc", id="invalid-type-t4"),
            pytest.param("t1_ABC", id="uppercase-id"),
            pytest.param("t1_a" + "b" * 10, id="id-too-long-11"),
        ],
    )
    def test_invalid_fullnames(self, fullname: str) -> None:
        assert _FULLNAME_RE.match(fullname) is None, f"'{fullname}' should be invalid"


# --- _USERNAME_RE ---


class TestUsernameRegex:
    """Tests for _USERNAME_RE pattern."""

    @pytest.mark.parametrize(
        "username",
        [
            pytest.param("AndyNemmity", id="mixed-case"),
            pytest.param("rob0d", id="alphanumeric"),
            pytest.param("a-b_c", id="hyphen-and-underscore"),
            pytest.param("a" * 20, id="max-length-20"),
            pytest.param("x", id="min-length-1"),
        ],
    )
    def test_valid_usernames(self, username: str) -> None:
        assert _USERNAME_RE.match(username) is not None, f"'{username}' should be valid"

    @pytest.mark.parametrize(
        "username",
        [
            pytest.param("", id="empty"),
            pytest.param("a" * 21, id="too-long-21-chars"),
            pytest.param("user name", id="space"),
            pytest.param("user.name", id="dot"),
            pytest.param("user@name", id="at-sign"),
        ],
    )
    def test_invalid_usernames(self, username: str) -> None:
        assert _USERNAME_RE.match(username) is None, f"'{username}' should be invalid"


# --- MockItem for scan flag tests ---


@dataclass
class MockItem:
    """Minimal mock of a PRAW submission/comment for _detect_scan_flags tests."""

    title: str = ""
    selftext: str = ""
    body: str = ""
    is_submission: bool = True


# --- _detect_scan_flags ---


class TestDetectScanFlags:
    """Tests for _detect_scan_flags heuristic flagging."""

    def test_normal_post_no_flags(self) -> None:
        item = MockItem(title="How to configure SAP HANA", selftext="I need help with configuration steps.")
        flags = _detect_scan_flags(item, required_language=None, is_submission=True)
        assert flags == []

    def test_job_ad_in_title(self) -> None:
        item = MockItem(title="We're hiring a SAP consultant", selftext="Great opportunity.")
        flags = _detect_scan_flags(item, required_language=None, is_submission=True)
        assert "job_ad_pattern" in flags

    def test_training_vendor_in_body(self) -> None:
        item = MockItem(title="SAP Training", selftext="Register now for free demo of our platform.")
        flags = _detect_scan_flags(item, required_language=None, is_submission=True)
        assert "training_vendor_pattern" in flags

    def test_comment_hiring_no_job_ad_flag(self) -> None:
        """Job ad patterns only match submission titles, not comment bodies."""
        item = MockItem(body="We're hiring a SAP consultant", is_submission=False)
        flags = _detect_scan_flags(item, required_language=None, is_submission=False)
        assert "job_ad_pattern" not in flags

    def test_non_ascii_heavy_text_flags_language(self) -> None:
        # Build text that is >30% non-ASCII alpha characters (>20 alpha chars total)
        non_ascii_text = "\u0410\u0411\u0412\u0413\u0414\u0415\u0416\u0417\u0418\u0419" * 3  # 30 Cyrillic chars
        item = MockItem(title=non_ascii_text, selftext="")
        flags = _detect_scan_flags(item, required_language="en", is_submission=True)
        assert any("possible_non_english" in f for f in flags)

    def test_short_text_no_language_flag(self) -> None:
        """Text shorter than 20 alpha characters should not trigger language flag."""
        short_non_ascii = "\u0410\u0411\u0412"  # only 3 chars
        item = MockItem(title=short_non_ascii, selftext="")
        flags = _detect_scan_flags(item, required_language="en", is_submission=True)
        assert not any("possible_non_english" in f for f in flags)

    def test_multiple_flags_at_once(self) -> None:
        non_ascii_text = "\u0410\u0411\u0412\u0413\u0414\u0415\u0416\u0417\u0418\u0419" * 3
        item = MockItem(
            title=f"We're hiring {non_ascii_text}",
            selftext="Register now for free demo",
        )
        flags = _detect_scan_flags(item, required_language="en", is_submission=True)
        assert "job_ad_pattern" in flags
        assert "training_vendor_pattern" in flags
        assert any("possible_non_english" in f for f in flags)


# --- _check_action_limit ---


class TestCheckActionLimit:
    """Tests for _check_action_limit audit log counting."""

    def test_no_audit_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(reddit_mod, "_DATA_DIR", tmp_path)
        actions, max_a = _check_action_limit("testsub")
        assert actions == 0

    def test_counts_todays_actions(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(reddit_mod, "_DATA_DIR", tmp_path)
        sub_dir = tmp_path / "testsub"
        sub_dir.mkdir()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        audit = sub_dir / "audit.jsonl"
        audit.write_text(
            "\n".join(
                [
                    json.dumps({"timestamp": f"{today}T10:00:00+00:00", "action": "approve"}),
                    json.dumps({"timestamp": f"{today}T11:00:00+00:00", "action": "remove"}),
                    json.dumps({"timestamp": "2020-01-01T00:00:00+00:00", "action": "approve"}),  # old
                    json.dumps({"timestamp": f"{today}T12:00:00+00:00", "action": "classify"}),  # not counted
                ]
            )
        )
        actions, _ = _check_action_limit("testsub")
        assert actions == 2  # only today's approve + remove

    def test_malformed_lines_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(reddit_mod, "_DATA_DIR", tmp_path)
        sub_dir = tmp_path / "testsub"
        sub_dir.mkdir()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        audit = sub_dir / "audit.jsonl"
        audit.write_text(
            "not json\n" + json.dumps({"timestamp": f"{today}T10:00:00+00:00", "action": "approve"}) + "\n"
        )
        actions, _ = _check_action_limit("testsub")
        assert actions == 1

    def test_os_error_fails_safe(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(reddit_mod, "_DATA_DIR", tmp_path)
        sub_dir = tmp_path / "testsub"
        sub_dir.mkdir()
        audit = sub_dir / "audit.jsonl"
        audit.write_text("data")
        audit.chmod(0o000)  # unreadable
        actions, max_a = _check_action_limit("testsub")
        assert actions == max_a  # fail-safe: budget exhausted
        audit.chmod(0o644)  # cleanup


# --- _analyze_mod_log ---


class TestAnalyzeModLog:
    """Tests for _analyze_mod_log structured summary."""

    def test_empty(self) -> None:
        result = _analyze_mod_log([], "test")
        assert result["total_entries"] == 0

    def test_repeat_offender_threshold(self) -> None:
        entries = [
            {"action": "removelink", "mod": "mod1", "target_author": "spammer", "details": "spam", "description": ""},
            {
                "action": "removecomment",
                "mod": "mod1",
                "target_author": "spammer",
                "details": "spam",
                "description": "",
            },
            {
                "action": "removelink",
                "mod": "mod1",
                "target_author": "once_user",
                "details": "spam",
                "description": "",
            },
        ]
        result = _analyze_mod_log(entries, "test")
        assert "spammer" in result["repeat_offenders"]
        assert "once_user" not in result["repeat_offenders"]

    def test_removal_reason_fallback(self) -> None:
        entries = [
            {
                "action": "removelink",
                "mod": "mod1",
                "target_author": "u1",
                "details": "",
                "description": "Rule 3 violation",
            },
        ]
        result = _analyze_mod_log(entries, "test")
        assert "Rule 3 violation" in result["removal_reasons"]

    def test_automod_categorization(self) -> None:
        entries = [
            {"action": "removelink", "mod": "AutoModerator", "target_author": "", "details": "", "description": ""},
            {"action": "removelink", "mod": "humanmod", "target_author": "", "details": "", "description": ""},
        ]
        result = _analyze_mod_log(entries, "test")
        assert result["moderator_activity"]["AutoModerator"] == 1
        assert result["moderator_activity"]["humanmod"] == 1


# --- _DEFAULT_CONFIG auto-ban fields ---


class TestDefaultConfigAutoBanFields:
    """Tests that _DEFAULT_CONFIG contains the required auto-ban fields."""

    def test_auto_ban_repeat_offenders_present_and_false(self) -> None:
        assert "auto_ban_repeat_offenders" in _DEFAULT_CONFIG
        assert _DEFAULT_CONFIG["auto_ban_repeat_offenders"] is False

    def test_auto_ban_threshold_present_and_default(self) -> None:
        assert "auto_ban_threshold" in _DEFAULT_CONFIG
        assert _DEFAULT_CONFIG["auto_ban_threshold"] == 3

    def test_auto_ban_message_present_and_default(self) -> None:
        assert "auto_ban_message" in _DEFAULT_CONFIG
        assert _DEFAULT_CONFIG["auto_ban_message"] == "Banned for repeated rule violations."


# --- _count_author_removals_today ---


class TestCountAuthorRemovalsToday:
    """Tests for _count_author_removals_today audit log counting."""

    def test_no_audit_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(reddit_mod, "_DATA_DIR", tmp_path)
        count = _count_author_removals_today("testsub", "someuser")
        assert count == 0

    def test_counts_only_matching_author(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(reddit_mod, "_DATA_DIR", tmp_path)
        sub_dir = tmp_path / "testsub"
        sub_dir.mkdir()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        audit = sub_dir / "audit.jsonl"
        audit.write_text(
            "\n".join(
                [
                    json.dumps({"timestamp": f"{today}T10:00:00+00:00", "action": "remove", "author": "spammer"}),
                    json.dumps({"timestamp": f"{today}T11:00:00+00:00", "action": "remove_spam", "author": "spammer"}),
                    json.dumps({"timestamp": f"{today}T12:00:00+00:00", "action": "remove", "author": "otheruser"}),
                    json.dumps({"timestamp": f"{today}T13:00:00+00:00", "action": "approve", "author": "spammer"}),
                ]
            )
        )
        count = _count_author_removals_today("testsub", "spammer")
        assert count == 2  # only remove + remove_spam for "spammer"

    def test_ignores_old_entries(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(reddit_mod, "_DATA_DIR", tmp_path)
        sub_dir = tmp_path / "testsub"
        sub_dir.mkdir()
        audit = sub_dir / "audit.jsonl"
        audit.write_text(
            json.dumps({"timestamp": "2020-01-01T00:00:00+00:00", "action": "remove", "author": "spammer"}) + "\n"
        )
        count = _count_author_removals_today("testsub", "spammer")
        assert count == 0

    def test_malformed_lines_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(reddit_mod, "_DATA_DIR", tmp_path)
        sub_dir = tmp_path / "testsub"
        sub_dir.mkdir()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        audit = sub_dir / "audit.jsonl"
        audit.write_text(
            "not json\n"
            + json.dumps({"timestamp": f"{today}T10:00:00+00:00", "action": "remove", "author": "spammer"})
            + "\n"
        )
        count = _count_author_removals_today("testsub", "spammer")
        assert count == 1

    def test_os_error_returns_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fail closed: OSError returns 0 (conservative — won't trigger a false auto-ban)."""
        monkeypatch.setattr(reddit_mod, "_DATA_DIR", tmp_path)
        sub_dir = tmp_path / "testsub"
        sub_dir.mkdir()
        audit = sub_dir / "audit.jsonl"
        audit.write_text("data")
        audit.chmod(0o000)
        count = _count_author_removals_today("testsub", "spammer")
        assert count == 0
        audit.chmod(0o644)  # cleanup


# --- _check_action_limit counts ban actions ---


class TestCheckActionLimitBans:
    """Tests that _check_action_limit counts ban and auto_ban actions."""

    def test_counts_ban_actions(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(reddit_mod, "_DATA_DIR", tmp_path)
        sub_dir = tmp_path / "testsub"
        sub_dir.mkdir()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        audit = sub_dir / "audit.jsonl"
        audit.write_text(
            "\n".join(
                [
                    json.dumps({"timestamp": f"{today}T10:00:00+00:00", "action": "ban"}),
                    json.dumps({"timestamp": f"{today}T11:00:00+00:00", "action": "auto_ban"}),
                    json.dumps({"timestamp": f"{today}T12:00:00+00:00", "action": "remove"}),
                ]
            )
        )
        actions, _ = _check_action_limit("testsub")
        assert actions == 3  # ban + auto_ban + remove all counted


# --- CLASSIFICATION_CATEGORIES ---


class TestClassificationCategories:
    """Tests for CLASSIFICATION_CATEGORIES constant."""

    def test_ban_recommended_present(self) -> None:
        assert "BAN_RECOMMENDED" in CLASSIFICATION_CATEGORIES

    def test_all_six_categories(self) -> None:
        expected = {
            "FALSE_REPORT",
            "VALID_REPORT",
            "MASS_REPORT_ABUSE",
            "SPAM",
            "BAN_RECOMMENDED",
            "NEEDS_HUMAN_REVIEW",
        }
        assert set(CLASSIFICATION_CATEGORIES) == expected
        assert len(CLASSIFICATION_CATEGORIES) == 6

    def test_tuple_immutable(self) -> None:
        assert isinstance(CLASSIFICATION_CATEGORIES, tuple)


# --- ClassificationResult ---


class TestClassificationResult:
    """Tests for ClassificationResult dataclass."""

    def test_to_dict_complete(self) -> None:
        result = ClassificationResult(
            item_id="t3_abc123",
            item_type="submission",
            author="testuser",
            title="Test Post",
            classification="SPAM",
            confidence=95,
            reasoning="Obvious spam link",
            mass_report_flag=False,
            repeat_offender_count=2,
            prompt="full prompt text here",
        )
        d = result.to_dict()
        assert d["item_id"] == "t3_abc123"
        assert d["item_type"] == "submission"
        assert d["author"] == "testuser"
        assert d["title"] == "Test Post"
        assert d["classification"] == "SPAM"
        assert d["confidence"] == 95
        assert d["reasoning"] == "Obvious spam link"
        assert d["mass_report_flag"] is False
        assert d["repeat_offender_count"] == 2
        assert d["prompt"] == "full prompt text here"

    def test_to_dict_none_classification(self) -> None:
        result = ClassificationResult(
            item_id="t1_xyz789",
            item_type="comment",
            author="someone",
            title="",
            classification=None,
            confidence=None,
            reasoning="",
            mass_report_flag=True,
            repeat_offender_count=0,
            prompt="assembled prompt",
        )
        d = result.to_dict()
        assert d["classification"] is None
        assert d["confidence"] is None
        assert d["reasoning"] == ""
        assert d["mass_report_flag"] is True


# --- load_classification_context ---


class TestLoadClassificationContext:
    """Tests for load_classification_context."""

    def test_all_files_present(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(reddit_mod, "_DATA_DIR", tmp_path)
        sub_dir = tmp_path / "testsub"
        sub_dir.mkdir()
        (sub_dir / "rules.md").write_text("# Rules\nNo spam allowed.", encoding="utf-8")
        (sub_dir / "mod-log-summary.md").write_text("=== MOD LOG ===\n10 removals", encoding="utf-8")
        (sub_dir / "moderator-notes.md").write_text("Watch for vendor spam.", encoding="utf-8")
        (sub_dir / "repeat-offenders.json").write_text(json.dumps({"spammer1": 5, "spammer2": 3}), encoding="utf-8")
        (sub_dir / "config.json").write_text(
            json.dumps({"trust_reporters": True, "required_language": "en"}), encoding="utf-8"
        )

        ctx = load_classification_context("testsub")
        assert "No spam allowed" in ctx["rules"]
        assert "10 removals" in ctx["mod_log_summary"]
        assert "vendor spam" in ctx["moderator_notes"]
        assert ctx["repeat_offenders"] == {"spammer1": 5, "spammer2": 3}
        assert ctx["config"]["trust_reporters"] is True

    def test_missing_files_graceful(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(reddit_mod, "_DATA_DIR", tmp_path)
        sub_dir = tmp_path / "testsub"
        sub_dir.mkdir()
        # Empty directory — no files at all

        ctx = load_classification_context("testsub")
        assert ctx["rules"] == ""
        assert ctx["mod_log_summary"] == ""
        assert ctx["moderator_notes"] == ""
        assert ctx["repeat_offenders"] == {}
        assert isinstance(ctx["config"], dict)

    def test_malformed_repeat_offenders(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(reddit_mod, "_DATA_DIR", tmp_path)
        sub_dir = tmp_path / "testsub"
        sub_dir.mkdir()
        (sub_dir / "repeat-offenders.json").write_text("not valid json {{{", encoding="utf-8")

        ctx = load_classification_context("testsub")
        assert ctx["repeat_offenders"] == {}
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "Malformed" in captured.err

    def test_missing_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(reddit_mod, "_DATA_DIR", tmp_path)
        # No "testsub" directory exists at all

        ctx = load_classification_context("testsub")
        assert ctx["rules"] == ""
        assert ctx["mod_log_summary"] == ""
        assert ctx["moderator_notes"] == ""
        assert ctx["repeat_offenders"] == {}


# --- build_classification_prompt ---


def _make_item(**overrides: object) -> dict:
    """Create a minimal item dict for build_classification_prompt tests."""
    base: dict = {
        "id": "abc123",
        "fullname": "t3_abc123",
        "item_type": "submission",
        "title": "Test Post Title",
        "author": "testauthor",
        "body": "This is the body text.",
        "score": 10,
        "num_reports": 1,
        "report_reasons": ["spam"],
        "created_utc": datetime.now(timezone.utc).timestamp() - 3600,  # 1 hour ago
        "created_iso": "2026-03-21T12:00:00+00:00",
        "permalink": "https://reddit.com/r/test/comments/abc123/test_post/",
    }
    base.update(overrides)
    return base


def _make_context(**overrides: object) -> dict:
    """Create a minimal context dict for build_classification_prompt tests."""
    base: dict = {
        "rules": "# Rules for r/testsub\nNo spam.",
        "mod_log_summary": "=== MOD LOG ===",
        "moderator_notes": "Watch for vendor spam.",
        "repeat_offenders": {},
        "config": {"subreddit": "testsub"},
    }
    base.update(overrides)
    return base


class TestBuildClassificationPrompt:
    """Tests for build_classification_prompt."""

    def test_basic_prompt_structure(self) -> None:
        item = _make_item()
        context = _make_context()
        result = build_classification_prompt(item, context)

        assert isinstance(result, ClassificationResult)
        assert result.classification is None
        assert result.confidence is None
        assert result.item_id == "t3_abc123"
        assert result.item_type == "submission"
        assert result.author == "testauthor"

        # Key prompt sections present
        prompt = result.prompt
        assert "You are classifying a reported Reddit item for moderation." in prompt
        assert "SECURITY:" in prompt
        assert "Subreddit: r/testsub" in prompt
        assert "Subreddit rules (moderator-provided, TRUSTED):" in prompt
        assert "Community context (moderator-provided, TRUSTED):" in prompt
        assert "Mod log patterns (auto-generated, TRUSTED):" in prompt
        assert "--- ITEM TO CLASSIFY" in prompt
        assert "--- END ITEM ---" in prompt
        assert "IMPORTANT:" in prompt

    def test_untrusted_wrapping(self) -> None:
        item = _make_item(
            author="evil_user",
            title="Buy my stuff",
            body="Click here for deals",
            report_reasons=["spam", "self-promotion"],
        )
        context = _make_context()
        result = build_classification_prompt(item, context)
        prompt = result.prompt

        # All untrusted fields must be wrapped
        assert "<untrusted-content>evil_user</untrusted-content>" in prompt
        assert "<untrusted-content>Buy my stuff</untrusted-content>" in prompt
        assert "<untrusted-content>Click here for deals</untrusted-content>" in prompt
        assert "<untrusted-content>spam, self-promotion</untrusted-content>" in prompt

    def test_mass_report_flag_true(self) -> None:
        item = _make_item(
            num_reports=15,
            report_reasons=["spam", "harassment", "misinformation", "other"],
        )
        context = _make_context()
        result = build_classification_prompt(item, context)

        assert result.mass_report_flag is True
        assert "Mass-report flag: True" in result.prompt

    def test_mass_report_flag_false(self) -> None:
        item = _make_item(num_reports=2, report_reasons=["spam"])
        context = _make_context()
        result = build_classification_prompt(item, context)

        assert result.mass_report_flag is False
        assert "Mass-report flag: False" in result.prompt

    def test_repeat_offender_noted(self) -> None:
        item = _make_item(author="known_spammer")
        context = _make_context(repeat_offenders={"known_spammer": 5, "other": 2})
        result = build_classification_prompt(item, context)

        assert result.repeat_offender_count == 5

    def test_ban_recommended_in_categories(self) -> None:
        item = _make_item()
        context = _make_context()
        result = build_classification_prompt(item, context)

        assert "BAN_RECOMMENDED" in result.prompt
        # Verify the full categories line is in the prompt
        assert (
            "FALSE_REPORT, VALID_REPORT, MASS_REPORT_ABUSE, SPAM, BAN_RECOMMENDED, NEEDS_HUMAN_REVIEW" in result.prompt
        )

    def test_missing_context_handled(self) -> None:
        item = _make_item()
        # Minimal context with empty/missing fields
        context: dict = {"config": {"subreddit": "empty"}}
        result = build_classification_prompt(item, context)

        assert isinstance(result, ClassificationResult)
        assert "No custom rules" in result.prompt
        assert "No moderator notes available" in result.prompt
        assert "No mod log summary available" in result.prompt

    def test_item_age_computed(self) -> None:
        # Item created 2 hours ago
        two_hours_ago = datetime.now(timezone.utc).timestamp() - 7200
        item = _make_item(created_utc=two_hours_ago)
        context = _make_context()
        result = build_classification_prompt(item, context)

        assert "Age: 2h ago" in result.prompt

    def test_user_history_included(self) -> None:
        item = _make_item()
        context = _make_context()
        result = build_classification_prompt(item, context, user_history_summary="Posts only about TrainingCube")

        assert "Posts only about TrainingCube" in result.prompt
        # Should be wrapped in untrusted tags
        assert "<untrusted-content>Posts only about TrainingCube</untrusted-content>" in result.prompt


# --- _cmd_classify ---


class TestCmdClassify:
    """Tests for _cmd_classify stdin parsing and subreddit resolution."""

    def _make_args(self, subreddit: str | None = None) -> argparse.Namespace:
        ns = argparse.Namespace()
        ns.subreddit = subreddit
        return ns

    def test_empty_stdin_returns_1(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        assert _cmd_classify(self._make_args()) == 1
        assert "No input" in capsys.readouterr().err

    def test_malformed_json_returns_1(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO("{{{"))
        assert _cmd_classify(self._make_args()) == 1
        assert "Invalid JSON" in capsys.readouterr().err

    def test_non_dict_json_returns_1(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO('"just a string"'))
        assert _cmd_classify(self._make_args()) == 1
        assert "Expected JSON object" in capsys.readouterr().err

    def test_no_subreddit_anywhere_returns_1(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO('{"items": []}'))
        monkeypatch.delenv("REDDIT_SUBREDDIT", raising=False)
        assert _cmd_classify(self._make_args()) == 1
        assert "No subreddit" in capsys.readouterr().err

    def test_invalid_subreddit_returns_1(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO('{"subreddit": "../etc", "items": []}'))
        monkeypatch.delenv("REDDIT_SUBREDDIT", raising=False)
        assert _cmd_classify(self._make_args()) == 1
        assert "Invalid subreddit" in capsys.readouterr().err

    def test_empty_items_returns_empty_array(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        monkeypatch.setattr(reddit_mod, "_DATA_DIR", tmp_path)
        payload = json.dumps({"subreddit": "testsub", "items": []})
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        assert _cmd_classify(self._make_args()) == 0
        assert json.loads(capsys.readouterr().out) == []

    def test_subreddit_from_json(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        monkeypatch.setattr(reddit_mod, "_DATA_DIR", tmp_path)
        item = {
            "id": "abc",
            "fullname": "t3_abc",
            "item_type": "submission",
            "title": "Test",
            "author": "user1",
            "body": "hello",
            "score": 5,
            "num_reports": 0,
            "report_reasons": [],
            "created_utc": 1000000,
            "permalink": "/r/test/1",
        }
        payload = json.dumps({"subreddit": "testsub", "items": [item]})
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        assert _cmd_classify(self._make_args()) == 0
        output = json.loads(capsys.readouterr().out)
        assert len(output) == 1
        assert output[0]["item_id"] == "t3_abc"

    def test_user_history_summary_passed_through(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """user_history_summary from input JSON should appear in the classification prompt."""
        monkeypatch.setattr(reddit_mod, "_DATA_DIR", tmp_path)
        item = {
            "id": "hist1",
            "fullname": "t3_hist1",
            "item_type": "submission",
            "title": "Promo Post",
            "author": "vendorbot",
            "body": "Check out our product!",
            "score": 1,
            "num_reports": 2,
            "report_reasons": ["spam"],
            "created_utc": 1000000,
            "permalink": "/r/test/hist1",
            "user_history_summary": "Posts exclusively about VendorCorp products",
        }
        payload = json.dumps({"subreddit": "testsub", "items": [item]})
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        assert _cmd_classify(self._make_args()) == 0
        output = json.loads(capsys.readouterr().out)
        assert len(output) == 1
        assert "Posts exclusively about VendorCorp products" in output[0]["prompt"]
