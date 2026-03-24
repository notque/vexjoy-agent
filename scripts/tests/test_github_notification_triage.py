"""Tests for github-notification-triage.py pure functions."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import the module via importlib because the filename has hyphens.
# Must register in sys.modules BEFORE exec_module so that dataclass()
# can resolve cls.__module__ during class body execution.
import importlib.util

_MODULE_NAME = "github_notification_triage"
_spec = importlib.util.spec_from_file_location(
    _MODULE_NAME,
    Path(__file__).resolve().parent.parent / "github-notification-triage.py",
)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules[_MODULE_NAME] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

Notification = _mod.Notification
TriageResult = _mod.TriageResult
classify = _mod.classify
parse_notification = _mod.parse_notification
format_report = _mod.format_report
format_json = _mod.format_json
build_parser = _mod.build_parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw(
    id: str = "1",
    reason: str = "subscribed",
    title: str = "Test Issue",
    subject_type: str = "Issue",
    subject_url: str = "https://api.github.com/repos/org/repo/issues/1",
    repo_full_name: str = "org/repo",
    updated_at: str = "2026-03-24T10:00:00Z",
    thread_url: str = "https://api.github.com/notifications/threads/1",
) -> dict:
    """Build a raw GitHub API notification dict."""
    return {
        "id": id,
        "reason": reason,
        "subject": {
            "title": title,
            "type": subject_type,
            "url": subject_url,
        },
        "repository": {"full_name": repo_full_name},
        "updated_at": updated_at,
        "url": thread_url,
    }


def _make_notification(
    id: str = "1",
    reason: str = "subscribed",
    title: str = "Test",
    repo: str = "org/repo",
    updated_at: str = "2026-03-24T10:00:00Z",
    subject_url: str = "https://api.github.com/repos/org/repo/issues/1",
) -> Notification:
    """Build a Notification directly."""
    return Notification(
        id=id,
        reason=reason,
        title=title,
        subject_type="Issue",
        subject_url=subject_url,
        repo_full_name=repo,
        updated_at=updated_at,
        thread_url=f"https://api.github.com/notifications/threads/{id}",
    )


# ---------------------------------------------------------------------------
# Notification.age_display
# ---------------------------------------------------------------------------


class TestAgeDisplay:
    """Tests for Notification.age_display relative time formatting."""

    def _notification_with_delta(self, delta: timedelta) -> Notification:
        dt = datetime.now(timezone.utc) - delta
        updated_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return _make_notification(updated_at=updated_at)

    @pytest.mark.parametrize(
        ("delta", "expected"),
        [
            pytest.param(timedelta(minutes=30), "30m ago", id="30-minutes"),
            pytest.param(timedelta(minutes=59), "59m ago", id="59-minutes"),
            pytest.param(timedelta(hours=2), "2h ago", id="2-hours"),
            pytest.param(timedelta(hours=23), "23h ago", id="23-hours"),
            pytest.param(timedelta(days=1), "1d ago", id="1-day"),
            pytest.param(timedelta(days=3), "3d ago", id="3-days"),
            pytest.param(timedelta(days=14), "14d ago", id="14-days"),
        ],
    )
    def test_relative_age(self, delta: timedelta, expected: str) -> None:
        n = self._notification_with_delta(delta)
        assert n.age_display == expected

    def test_invalid_updated_at_returns_unknown(self) -> None:
        n = _make_notification(updated_at="not-a-date")
        assert n.age_display == "unknown"

    def test_empty_updated_at_returns_unknown(self) -> None:
        n = _make_notification(updated_at="")
        assert n.age_display == "unknown"

    def test_less_than_one_minute_shows_1m(self) -> None:
        n = self._notification_with_delta(timedelta(seconds=10))
        assert n.age_display == "1m ago"


# ---------------------------------------------------------------------------
# Notification.pr_or_issue_number and display_ref
# ---------------------------------------------------------------------------


class TestDisplayRef:
    """Tests for display_ref and PR/issue number extraction."""

    @pytest.mark.parametrize(
        ("subject_url", "expected_num"),
        [
            pytest.param(
                "https://api.github.com/repos/org/repo/issues/42",
                "#42",
                id="issue-url",
            ),
            pytest.param(
                "https://api.github.com/repos/org/repo/pulls/142",
                "#142",
                id="pull-url",
            ),
            pytest.param(
                "https://api.github.com/repos/org/repo",
                "",
                id="no-number-in-url",
            ),
            pytest.param("", "", id="empty-url"),
        ],
    )
    def test_pr_or_issue_number(self, subject_url: str, expected_num: str) -> None:
        n = _make_notification(subject_url=subject_url)
        assert n.pr_or_issue_number == expected_num

    def test_display_ref_with_number(self) -> None:
        n = _make_notification(
            repo="sapcc/go-bits",
            subject_url="https://api.github.com/repos/sapcc/go-bits/pulls/142",
        )
        assert n.display_ref == "sapcc/go-bits#142"

    def test_display_ref_without_number(self) -> None:
        n = _make_notification(repo="org/repo", subject_url="")
        assert n.display_ref == "org/repo"


# ---------------------------------------------------------------------------
# Notification.browse_url
# ---------------------------------------------------------------------------


class TestBrowseUrl:
    """Tests for URL conversion from API to browser-friendly format."""

    def test_pull_request_url_converted(self) -> None:
        n = _make_notification(subject_url="https://api.github.com/repos/org/repo/pulls/5")
        assert n.browse_url == "https://github.com/org/repo/pull/5"

    def test_issue_url_converted(self) -> None:
        n = _make_notification(subject_url="https://api.github.com/repos/org/repo/issues/10")
        assert n.browse_url == "https://github.com/org/repo/issues/10"

    def test_html_url_preferred_over_conversion(self) -> None:
        n = _make_notification(subject_url="https://api.github.com/repos/org/repo/pulls/5")
        n.html_url = "https://github.com/org/repo/pull/5#issuecomment-99"
        assert n.browse_url == "https://github.com/org/repo/pull/5#issuecomment-99"

    def test_non_api_url_returned_unchanged(self) -> None:
        n = _make_notification(subject_url="https://github.com/org/repo/releases/v1.0")
        assert n.browse_url == "https://github.com/org/repo/releases/v1.0"


# ---------------------------------------------------------------------------
# classify()
# ---------------------------------------------------------------------------


class TestClassify:
    """Tests for the classify() routing function."""

    @pytest.mark.parametrize(
        "reason",
        [
            pytest.param("review_requested", id="review_requested"),
            pytest.param("mention", id="mention"),
            pytest.param("assign", id="assign"),
        ],
    )
    def test_action_required_reasons(self, reason: str) -> None:
        n = _make_notification(reason=reason)
        result = classify([n])
        assert n in result.action_required
        assert result.informational == []
        assert result.author == []

    @pytest.mark.parametrize(
        "reason",
        [
            pytest.param("subscribed", id="subscribed"),
            pytest.param("state_change", id="state_change"),
            pytest.param("team_mention", id="team_mention"),
        ],
    )
    def test_informational_reasons(self, reason: str) -> None:
        n = _make_notification(reason=reason)
        result = classify([n])
        assert n in result.informational
        assert result.action_required == []

    def test_author_reason(self) -> None:
        n = _make_notification(reason="author")
        result = classify([n])
        assert n in result.author

    def test_ci_activity_reason(self) -> None:
        n = _make_notification(reason="ci_activity")
        result = classify([n])
        assert n in result.ci_failures

    def test_unknown_reason_goes_to_unknown_bucket(self) -> None:
        n = _make_notification(reason="some_future_reason")
        result = classify([n])
        assert n in result.unknown
        # Unknown should NOT be in action_required directly
        assert n not in result.action_required

    def test_empty_notifications_returns_empty_result(self) -> None:
        result = classify([])
        assert result.action_required == []
        assert result.informational == []
        assert result.author == []
        assert result.ci_failures == []
        assert result.unknown == []

    def test_mixed_reasons_all_routed_correctly(self) -> None:
        notifications = [
            _make_notification(id="1", reason="review_requested"),
            _make_notification(id="2", reason="subscribed"),
            _make_notification(id="3", reason="author"),
            _make_notification(id="4", reason="ci_activity"),
            _make_notification(id="5", reason="state_change"),
            _make_notification(id="6", reason="mystery_reason"),
        ]
        result = classify(notifications)
        assert len(result.action_required) == 1
        assert len(result.informational) == 2
        assert len(result.author) == 1
        assert len(result.ci_failures) == 1
        assert len(result.unknown) == 1


# ---------------------------------------------------------------------------
# TriageResult.all_informational_ids and informational_by_reason
# ---------------------------------------------------------------------------


class TestTriageResult:
    """Tests for TriageResult aggregate methods."""

    def test_all_informational_ids_includes_informational(self) -> None:
        result = TriageResult(informational=[_make_notification(id="10", reason="subscribed")])
        assert "10" in result.all_informational_ids()

    def test_all_informational_ids_includes_ci_informational(self) -> None:
        result = TriageResult(ci_informational=[_make_notification(id="20", reason="ci_activity")])
        assert "20" in result.all_informational_ids()

    def test_all_informational_ids_excludes_action_required(self) -> None:
        result = TriageResult(
            action_required=[_make_notification(id="99", reason="mention")],
            informational=[_make_notification(id="10", reason="subscribed")],
        )
        ids = result.all_informational_ids()
        assert "99" not in ids
        assert "10" in ids

    def test_informational_by_reason_counts(self) -> None:
        result = TriageResult(
            informational=[
                _make_notification(id="1", reason="subscribed"),
                _make_notification(id="2", reason="subscribed"),
                _make_notification(id="3", reason="state_change"),
            ]
        )
        counts = result.informational_by_reason()
        assert counts["subscribed"] == 2
        assert counts["state_change"] == 1

    def test_informational_by_reason_empty(self) -> None:
        result = TriageResult()
        assert result.informational_by_reason() == {}


# ---------------------------------------------------------------------------
# parse_notification()
# ---------------------------------------------------------------------------


class TestParseNotification:
    """Tests for raw dict → Notification parsing."""

    def test_basic_parse(self) -> None:
        raw = _make_raw(
            id="42",
            reason="mention",
            title="Fix the bug",
            repo_full_name="org/repo",
        )
        n = parse_notification(raw)
        assert n.id == "42"
        assert n.reason == "mention"
        assert n.title == "Fix the bug"
        assert n.repo_full_name == "org/repo"

    def test_missing_subject_graceful(self) -> None:
        raw = {"id": "1", "reason": "subscribed", "updated_at": "2026-03-24T10:00:00Z", "url": ""}
        n = parse_notification(raw)
        assert n.title == "(no title)"
        assert n.subject_url == ""

    def test_missing_repository_graceful(self) -> None:
        raw = _make_raw()
        del raw["repository"]
        n = parse_notification(raw)
        assert n.repo_full_name == ""

    def test_id_coerced_to_str(self) -> None:
        raw = _make_raw(id=999)  # type: ignore[arg-type]
        n = parse_notification(raw)
        assert n.id == "999"

    def test_html_url_resolved_for_issue(self) -> None:
        raw = _make_raw(subject_url="https://api.github.com/repos/org/repo/issues/5")
        n = parse_notification(raw)
        assert n.html_url == "https://github.com/org/repo/issues/5"

    def test_html_url_resolved_for_pull(self) -> None:
        raw = _make_raw(subject_url="https://api.github.com/repos/org/repo/pulls/10")
        n = parse_notification(raw)
        assert n.html_url == "https://github.com/org/repo/pull/10"


# ---------------------------------------------------------------------------
# format_report()
# ---------------------------------------------------------------------------


class TestFormatReport:
    """Tests for the markdown report formatter."""

    def _make_result_with_all_types(self) -> TriageResult:
        return TriageResult(
            action_required=[
                _make_notification(id="1", reason="review_requested", title="Review this PR"),
                _make_notification(id="2", reason="mention", title="Mention here"),
            ],
            author=[_make_notification(id="3", reason="author", title="My issue")],
            ci_failures=[_make_notification(id="4", reason="ci_activity", title="CI failed")],
            informational=[
                _make_notification(id="5", reason="subscribed"),
                _make_notification(id="6", reason="subscribed"),
                _make_notification(id="7", reason="state_change"),
            ],
        )

    def test_report_contains_date(self) -> None:
        result = TriageResult()
        report = format_report(result, "2026-03-24")
        assert "2026-03-24" in report

    def test_report_has_action_required_header(self) -> None:
        result = self._make_result_with_all_types()
        report = format_report(result, "2026-03-24")
        assert "### Action Required" in report

    def test_report_action_count_correct(self) -> None:
        result = self._make_result_with_all_types()
        report = format_report(result, "2026-03-24")
        assert "Action Required (2 items)" in report

    def test_report_unknown_count_adds_to_action_required(self) -> None:
        result = TriageResult(
            action_required=[_make_notification(id="1", reason="mention")],
            unknown=[_make_notification(id="2", reason="future_reason")],
        )
        report = format_report(result, "2026-03-24")
        assert "Action Required (2 items)" in report

    def test_report_shows_summary_counts(self) -> None:
        result = self._make_result_with_all_types()
        report = format_report(result, "2026-03-24")
        assert "- Action required: 2" in report
        assert "- Author activity: 1" in report
        assert "- CI activity: 1" in report
        assert "Informational (would clear with --mark-read): 3" in report

    def test_report_shows_informational_breakdown(self) -> None:
        result = self._make_result_with_all_types()
        report = format_report(result, "2026-03-24")
        assert "subscribed: 2" in report
        assert "state_change: 1" in report

    def test_report_empty_sections_show_none(self) -> None:
        result = TriageResult()
        report = format_report(result, "2026-03-24")
        assert "Action Required (0 items)" in report
        assert "No action-required notifications." in report

    def test_report_action_items_have_checkbox(self) -> None:
        result = TriageResult(action_required=[_make_notification(id="1", reason="mention", title="Ping")])
        report = format_report(result, "2026-03-24")
        assert "- [ ]" in report

    def test_report_has_url_on_second_line(self) -> None:
        result = TriageResult(
            action_required=[
                _make_notification(
                    id="1",
                    reason="review_requested",
                    title="Add feature",
                    subject_url="https://api.github.com/repos/org/repo/pulls/5",
                )
            ]
        )
        report = format_report(result, "2026-03-24")
        assert "https://github.com/org/repo/pull/5" in report


# ---------------------------------------------------------------------------
# format_json()
# ---------------------------------------------------------------------------


class TestFormatJson:
    """Tests for the JSON output formatter."""

    def _result(self) -> TriageResult:
        return TriageResult(
            action_required=[_make_notification(id="1", reason="mention", title="Ping")],
            informational=[_make_notification(id="2", reason="subscribed")],
        )

    def test_valid_json_output(self) -> None:
        output = format_json(self._result(), "2026-03-24")
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_json_has_required_keys(self) -> None:
        output = format_json(self._result(), "2026-03-24")
        parsed = json.loads(output)
        assert "action_required" in parsed
        assert "informational" in parsed
        assert "summary" in parsed
        assert "date" in parsed

    def test_json_action_required_count(self) -> None:
        output = format_json(self._result(), "2026-03-24")
        parsed = json.loads(output)
        assert parsed["summary"]["action_required"] == 1

    def test_json_unknown_adds_to_action_required(self) -> None:
        result = TriageResult(
            action_required=[_make_notification(id="1", reason="mention")],
            unknown=[_make_notification(id="2", reason="future_reason")],
        )
        output = format_json(result, "2026-03-24")
        parsed = json.loads(output)
        assert parsed["summary"]["action_required"] == 2
        assert len(parsed["action_required"]) == 2

    def test_json_notification_has_expected_fields(self) -> None:
        output = format_json(self._result(), "2026-03-24")
        parsed = json.loads(output)
        item = parsed["action_required"][0]
        for key in ("id", "reason", "title", "ref", "url", "age", "updated_at"):
            assert key in item, f"Missing key: {key}"

    def test_json_informational_count(self) -> None:
        output = format_json(self._result(), "2026-03-24")
        parsed = json.loads(output)
        assert parsed["summary"]["informational_total"] == 1


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------


class TestBuildParser:
    """Tests for CLI argument parsing."""

    def test_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.mark_read is False
        assert args.dry_run is False
        assert args.json_output is False
        assert args.save is False

    def test_mark_read_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--mark-read"])
        assert args.mark_read is True

    def test_dry_run_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_json_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--json"])
        assert args.json_output is True

    def test_save_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--save"])
        assert args.save is True

    def test_multiple_flags_together(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--mark-read", "--save", "--json"])
        assert args.mark_read is True
        assert args.save is True
        assert args.json_output is True


# ---------------------------------------------------------------------------
# Integration: check_gh_available and main() error path
# ---------------------------------------------------------------------------


class TestCheckGhAvailable:
    """Tests for gh authentication check."""

    def test_returns_true_when_gh_auth_succeeds(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            assert _mod.check_gh_available() is True

    def test_returns_false_when_gh_auth_fails(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not logged in")
            assert _mod.check_gh_available() is False


class TestMainErrorHandling:
    """Tests for main() error exit codes."""

    def test_exits_1_when_gh_not_available(self, capsys: pytest.CaptureFixture) -> None:
        with patch.object(_mod, "check_gh_available", return_value=False):
            result = _mod.main(argv=[])
        assert result == 1

    def test_exits_1_when_fetch_fails(self, capsys: pytest.CaptureFixture) -> None:
        with patch.object(_mod, "check_gh_available", return_value=True), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            with pytest.raises(SystemExit) as exc_info:
                _mod.main(argv=[])
            assert exc_info.value.code == 1

    def test_returns_0_on_empty_notifications(self, capsys: pytest.CaptureFixture) -> None:
        with (
            patch.object(_mod, "check_gh_available", return_value=True),
            patch.object(_mod, "fetch_notifications", return_value=[]),
        ):
            result = _mod.main(argv=[])
            assert result == 0
