#!/usr/bin/env python3
"""get_session_id() keys per-session state on the id Claude Code sends (B-04).

Claude Code puts ``session_id`` in every hook's stdin JSON and never sets
``CLAUDE_SESSION_ID``. The helper used to read only the env var and fall back
to a hash of the parent pid and the hour; the parent pid changes on every hook
call, so per-session state never accumulated (suggest-compact never fired and
every learning.db session row was unique).

Run with: python3 -m pytest hooks/tests/test_hook_utils_session_id.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

import hook_utils
from hook_utils import get_session_id, get_state_file


@pytest.fixture(autouse=True)
def _no_env_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)


def test_event_session_id_is_preferred_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_SESSION_ID", "env-session")
    assert get_session_id({"session_id": "event-session"}) == "event-session"


def test_env_session_id_is_used_when_the_event_has_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_SESSION_ID", "env-session")
    assert get_session_id({"hook_event_name": "Stop"}) == "env-session"
    assert get_session_id() == "env-session"


def test_fallback_is_a_short_hash_when_no_id_is_available() -> None:
    sid = get_session_id({})
    assert len(sid) == 12
    assert all(c in "0123456789abcdef" for c in sid)
    assert get_session_id(None) == sid


@pytest.mark.parametrize(
    "unsafe",
    [
        "",
        None,
        123,
        ["s"],
        ".",
        "..",
        "../escape",
        "a/b",
        "a\\b",
        "a\x00b",
        "line\nbreak",
        "x" * 129,
    ],
    ids=repr,
)
def test_unsafe_or_malformed_event_ids_fall_through_to_the_env(monkeypatch: pytest.MonkeyPatch, unsafe) -> None:
    """Session ids name files (/tmp/claude-<prefix>-<id>.state), so path-shaped ids are not used."""
    monkeypatch.setenv("CLAUDE_SESSION_ID", "env-session")
    assert get_session_id({"session_id": unsafe}) == "env-session"


def test_unsafe_env_id_falls_through_to_the_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_SESSION_ID", "../escape")
    assert get_session_id({}) == get_session_id(None)
    assert "/" not in get_session_id({})
    assert len(get_session_id({})) == 12


def test_realistic_ids_are_kept_verbatim() -> None:
    for sid in ("398f7ce1-f06f-43a2-9aea-c3549e1a994f", "conv-agy-123", "runtime-Stop-x_y.1"):
        assert get_session_id({"session_id": sid}) == sid


def test_state_file_is_keyed_on_the_event_session_id() -> None:
    assert get_state_file("compact-count", {"session_id": "sess-1"}) == Path("/tmp/claude-compact-count-sess-1.state")


def test_state_file_without_an_event_keeps_the_old_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_SESSION_ID", "env-session")
    assert get_state_file("compact-count") == Path("/tmp/claude-compact-count-env-session.state")


def test_lib_package_still_exports_the_helpers() -> None:
    assert hook_utils.get_session_id is get_session_id
    assert hook_utils.get_state_file is get_state_file
