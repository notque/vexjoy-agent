"""Tests for scripts/load-profile.py, filter-codex-allowlist.py, filter-settings-hooks.py."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_module(name: str, filename: str):
    path = REPO_ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def load_profile():
    return _load_module("load_profile", "load-profile.py")


@pytest.fixture(scope="module")
def filter_codex():
    return _load_module("filter_codex_allowlist", "filter-codex-allowlist.py")


@pytest.fixture(scope="module")
def filter_settings():
    return _load_module("filter_settings_hooks", "filter-settings-hooks.py")


# ---------- load-profile.py ----------


def test_load_profile_missing_file(tmp_path: Path, load_profile) -> None:
    out = load_profile.load(tmp_path / "missing.yaml")
    assert out == {"skills": [], "agents": [], "hooks": []}


def test_load_profile_basic(tmp_path: Path, load_profile) -> None:
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        "disabled:\n  skills: [foo, bar]\n  agents: [baz]\n  hooks: []\n",
        encoding="utf-8",
    )
    out = load_profile.load(profile)
    assert out["skills"] == ["foo", "bar"]
    assert out["agents"] == ["baz"]
    assert out["hooks"] == []


def test_load_profile_malformed_yaml(tmp_path: Path, load_profile, capsys) -> None:
    profile = tmp_path / "bad.yaml"
    profile.write_text("disabled: [unclosed\n", encoding="utf-8")
    out = load_profile.load(profile)
    assert out == {"skills": [], "agents": [], "hooks": []}
    err = capsys.readouterr().err
    assert "not valid YAML" in err


def test_load_profile_missing_disabled_key(tmp_path: Path, load_profile) -> None:
    profile = tmp_path / "profile.yaml"
    profile.write_text("other: stuff\n", encoding="utf-8")
    out = load_profile.load(profile)
    assert out == {"skills": [], "agents": [], "hooks": []}


def test_load_profile_non_list_values(tmp_path: Path, load_profile, capsys) -> None:
    profile = tmp_path / "profile.yaml"
    profile.write_text("disabled:\n  skills: not-a-list\n", encoding="utf-8")
    out = load_profile.load(profile)
    assert out["skills"] == []
    err = capsys.readouterr().err
    assert "not a list" in err


def test_load_profile_strips_whitespace_and_blanks(tmp_path: Path, load_profile) -> None:
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        "disabled:\n  hooks:\n    - '  foo.py  '\n    - ''\n    - bar.py\n",
        encoding="utf-8",
    )
    out = load_profile.load(profile)
    assert out["hooks"] == ["foo.py", "bar.py"]


# ---------- filter-codex-allowlist.py ----------


def test_filter_codex_preserves_comments_and_blanks(filter_codex) -> None:
    text = "# header comment\n\nUserPromptSubmit:foo.py\nPreToolUse:bar.py Bash\n"
    out = filter_codex.filter_allowlist(text, {"foo.py"})
    assert out == "# header comment\n\nPreToolUse:bar.py Bash\n"


def test_filter_codex_no_disabled_returns_input(filter_codex) -> None:
    text = "PreToolUse:bar.py Bash\n"
    assert filter_codex.filter_allowlist(text, set()) == text


def test_filter_codex_strips_only_matching_filename(filter_codex) -> None:
    text = "Event:keep.py args\nEvent:drop.py args\n"
    out = filter_codex.filter_allowlist(text, {"drop.py"})
    assert out == "Event:keep.py args\n"


def test_filter_codex_handles_no_trailing_newline(filter_codex) -> None:
    text = "Event:drop.py"
    assert filter_codex.filter_allowlist(text, {"drop.py"}) == ""


def test_filter_codex_read_disabled(tmp_path: Path, filter_codex) -> None:
    f = tmp_path / "d.txt"
    f.write_text("# comment\nfoo.py\n\nbar.py\n", encoding="utf-8")
    assert filter_codex.read_disabled(f) == {"foo.py", "bar.py"}


def test_filter_codex_read_disabled_missing(tmp_path: Path, filter_codex) -> None:
    assert filter_codex.read_disabled(tmp_path / "nope.txt") == set()


# ---------- filter-settings-hooks.py ----------


def _hook_entry(filename: str) -> dict:
    return {"type": "command", "command": f'python3 "$HOME/.claude/hooks/{filename}"'}


def test_filter_settings_drops_disabled_entries(filter_settings) -> None:
    settings = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [_hook_entry("keep.py"), _hook_entry("drop.py")]},
                {"matcher": "Edit", "hooks": [_hook_entry("drop.py")]},
            ]
        }
    }
    out = filter_settings.filter_hooks(settings, {"drop.py"})
    assert out["hooks"] == {
        "PreToolUse": [
            {"matcher": "Bash", "hooks": [_hook_entry("keep.py")]},
        ]
    }


def test_filter_settings_drops_event_when_all_groups_empty(filter_settings) -> None:
    settings = {
        "hooks": {
            "PreToolUse": [{"matcher": "Bash", "hooks": [_hook_entry("drop.py")]}],
            "PostToolUse": [{"matcher": "*", "hooks": [_hook_entry("keep.py")]}],
        }
    }
    out = filter_settings.filter_hooks(settings, {"drop.py"})
    assert "PreToolUse" not in out["hooks"]
    assert "PostToolUse" in out["hooks"]


def test_filter_settings_no_hooks_block(filter_settings) -> None:
    settings = {"other": "value"}
    assert filter_settings.filter_hooks(settings, {"drop.py"}) == settings


def test_filter_settings_command_without_hooks_marker_is_kept(filter_settings) -> None:
    settings = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hi"}]}]}}
    out = filter_settings.filter_hooks(settings, {"drop.py"})
    assert out["hooks"]["PreToolUse"][0]["hooks"] == [{"type": "command", "command": "echo hi"}]


def test_filter_settings_hook_filename_helper(filter_settings) -> None:
    h = filter_settings.hook_filename_from_command
    assert h('python3 "$HOME/.claude/hooks/foo.py"') == "foo.py"
    assert h("python3 $HOME/.claude/hooks/bar.py extra") == "bar.py"
    assert h("echo no marker") is None


def test_filter_settings_main_writes_output(tmp_path: Path, filter_settings, monkeypatch) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [_hook_entry("drop.py"), _hook_entry("keep.py")]}]}}
        ),
        encoding="utf-8",
    )
    disabled_path = tmp_path / "disabled.txt"
    disabled_path.write_text("drop.py\n", encoding="utf-8")
    out_path = tmp_path / "out.json"

    monkeypatch.setattr(
        "sys.argv",
        [
            "filter-settings-hooks.py",
            "--input",
            str(settings_path),
            "--disabled",
            str(disabled_path),
            "--output",
            str(out_path),
        ],
    )
    assert filter_settings.main() == 0
    data = json.loads(out_path.read_text(encoding="utf-8"))
    names = [h["command"].split("/hooks/")[-1].rstrip('"') for h in data["hooks"]["PreToolUse"][0]["hooks"]]
    assert names == ["keep.py"]
