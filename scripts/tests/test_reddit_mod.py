"""Tests for reddit_mod.py pure functions."""

from __future__ import annotations

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
    _FULLNAME_RE,
    _SUBREDDIT_RE,
    _USERNAME_RE,
    _analyze_mod_log,
    _check_action_limit,
    _detect_scan_flags,
    detect_mass_report,
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
