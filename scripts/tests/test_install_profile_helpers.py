"""Tests for scripts/load-profile.py (the install profile parser the vexinstall engine uses)."""

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
