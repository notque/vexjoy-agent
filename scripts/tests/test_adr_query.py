"""Tests for Windows/non-dir_fd paths in adr-query.py, repository_artifact.py, and adr-compliance.py."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


adr_query = _load("adr_query_mod", "adr-query.py")
repo_artifact = _load("repository_artifact_mod", "repository_artifact.py")


# ---------------------------------------------------------------------------
# adr-query.py Windows / non-dir_fd fallback
# ---------------------------------------------------------------------------


def test_adr_query_session_read_and_delete_no_dir_fd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adr_query, "_supports_dir_fd", lambda: False)
    session_file = tmp_path / ".adr-session.json"
    session_file.write_text(json.dumps({"adr_path": "adr/001.md"}), encoding="utf-8")

    data = adr_query._session_read(tmp_path)
    assert data == {"adr_path": "adr/001.md"}

    deleted = adr_query._session_delete(tmp_path)
    assert deleted == session_file
    assert not session_file.exists()


def test_adr_query_session_read_no_dir_fd_rejects_bad_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adr_query, "_supports_dir_fd", lambda: False)

    # Missing file
    with pytest.raises(ValueError, match="no active ADR session"):
        adr_query._session_read(tmp_path)
    with pytest.raises(ValueError, match="no active ADR session"):
        adr_query._session_delete(tmp_path)

    # Non-dict JSON
    session_file = tmp_path / ".adr-session.json"
    session_file.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        adr_query._session_read(tmp_path)

    # Invalid JSON
    session_file.write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        adr_query._session_read(tmp_path)

    # Directory instead of regular file
    session_file.unlink()
    session_file.mkdir()
    with pytest.raises(ValueError, match="regular file"):
        adr_query._session_read(tmp_path)
    session_file.rmdir()

    # Symlink session file (skip only if host forbids symlinks)
    outside = tmp_path / "outside.json"
    outside.write_text('{"adr_path": "adr/001.md"}', encoding="utf-8")
    try:
        os.symlink(outside, session_file)
    except OSError:
        pytest.skip("host cannot create symlinks")
    with pytest.raises(ValueError, match="symbolic link"):
        adr_query._session_read(tmp_path)


# ---------------------------------------------------------------------------
# repository_artifact.py Windows / non-dir_fd fallback
# ---------------------------------------------------------------------------


def test_repository_artifact_atomic_write_no_dir_fd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(repo_artifact, "_supports_dir_fd", lambda: False)
    (tmp_path / "adr").mkdir()

    written = repo_artifact.atomic_write_text(tmp_path, "adr/sub/001.md", "hello\n", allowed_root="adr")
    assert written == (tmp_path.resolve() / "adr" / "sub" / "001.md")
    assert written.read_text(encoding="utf-8") == "hello\n"

    # Overwrite works cleanly
    repo_artifact.atomic_write_text(tmp_path, "adr/sub/001.md", "updated\n", allowed_root="adr")
    assert written.read_text(encoding="utf-8") == "updated\n"

    # Outside allowed_root is rejected
    with pytest.raises(ValueError, match="below adr/"):
        repo_artifact.atomic_write_text(tmp_path, "other/001.md", "x", allowed_root="adr")


def test_repository_artifact_no_dir_fd_rejects_symlinks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(repo_artifact, "_supports_dir_fd", lambda: False)
    (tmp_path / "adr").mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    target_link = tmp_path / "adr" / "link.md"
    try:
        os.symlink(outside, target_link)
    except OSError:
        pytest.skip("host cannot create symlinks")

    with pytest.raises(ValueError, match="symbolic link"):
        repo_artifact.atomic_write_text(tmp_path, "adr/link.md", "overwrite", allowed_root="adr")

    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    os.symlink(outside_dir, tmp_path / "adr" / "escape_dir")
    with pytest.raises(ValueError, match="real directories"):
        repo_artifact.atomic_write_text(tmp_path, "adr/escape_dir/file.md", "overwrite", allowed_root="adr")


# ---------------------------------------------------------------------------
# adr-compliance.py check-session edge cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "session_payload",
    [
        json.dumps({"adr_path": ""}),
        json.dumps({"adr_path": "   "}),
        json.dumps({"adr_path": "."}),
        json.dumps(["not", "a", "dict"]),
        json.dumps({"adr_path": 123}),
    ],
)
def test_adr_compliance_check_session_skips_empty_dir_or_nondict_session(tmp_path: Path, session_payload: str) -> None:
    """Empty adr_path ('') or directory path must SKIP instead of crashing with IsADirectoryError."""
    (tmp_path / ".adr-session.json").write_text(session_payload, encoding="utf-8")
    comp = tmp_path / "SKILL.md"
    comp.write_text("---\nname: demo\n---\nbody\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "adr-compliance.py"), "check-adr", "--file", str(comp)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["verdict"] == "SKIP"


def test_adr_compliance_check_session_reads_utf8_adr_and_passes(tmp_path: Path) -> None:
    adr = tmp_path / "adr-001.md"
    adr.write_text("# ADR — demo-skill\n\nIncludes UTF-8 em-dash — and demo-skill.\n", encoding="utf-8")
    (tmp_path / ".adr-session.json").write_text(json.dumps({"adr_path": str(adr)}), encoding="utf-8")
    comp = tmp_path / "SKILL.md"
    comp.write_text("---\nname: demo-skill\n---\nbody\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "adr-compliance.py"), "check-adr", "--file", str(comp)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["verdict"] == "PASS"
    assert out["mentioned_in_adr"] is True
