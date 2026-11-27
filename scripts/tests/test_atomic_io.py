"""Tests for scripts/lib/atomic_io.atomic_write_text."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure the repo root is on sys.path so ``scripts.lib`` resolves.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.lib.atomic_io import atomic_write_text


class TestAtomicWriteText:
    """Suite for atomic_write_text."""

    def test_writes_new_file(self, tmp_path: Path) -> None:
        """Write a new file; content matches."""
        target = tmp_path / "out.json"
        atomic_write_text(target, '{"a": 1}\n')
        assert target.read_text(encoding="utf-8") == '{"a": 1}\n'

    def test_replaces_existing_file(self, tmp_path: Path) -> None:
        """Replace an existing file; content matches; no temp file left."""
        target = tmp_path / "out.json"
        target.write_text("old", encoding="utf-8")
        atomic_write_text(target, "new")
        assert target.read_text(encoding="utf-8") == "new"
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == [], f"leftover temp files: {tmp_files}"

    def test_preserves_existing_mode(self, tmp_path: Path) -> None:
        """Existing file with mode 0o640 keeps 0o640 after the write."""
        target = tmp_path / "out.json"
        target.write_text("old", encoding="utf-8")
        os.chmod(target, 0o640)
        atomic_write_text(target, "new")
        assert oct(target.stat().st_mode & 0o7777) == oct(0o640)

    def test_new_file_gets_default_mode(self, tmp_path: Path) -> None:
        """New file gets 0o666 & ~umask."""
        target = tmp_path / "out.json"
        mask = os.umask(0)
        os.umask(mask)
        expected = 0o666 & ~mask
        atomic_write_text(target, "content")
        assert oct(target.stat().st_mode & 0o7777) == oct(expected)

    def test_failure_leaves_original_intact(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """On os.replace failure, original stays and no temp file remains."""
        target = tmp_path / "out.json"
        target.write_text("original", encoding="utf-8")

        import scripts.lib.atomic_io as _mod

        monkeypatch.setattr(_mod, "os", _make_failing_os_replace())
        with pytest.raises(OSError, match="injected"):
            atomic_write_text(target, "replacement")
        assert target.read_text(encoding="utf-8") == "original"
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == [], f"leftover temp files: {tmp_files}"

    def test_missing_parent_raises(self, tmp_path: Path) -> None:
        """Missing parent directory raises OSError (FileNotFoundError)."""
        target = tmp_path / "no" / "such" / "dir" / "out.json"
        with pytest.raises(OSError):
            atomic_write_text(target, "content")

    def test_file_mtime_not_older_than_directory(self, tmp_path: Path) -> None:
        """After a write, file mtime >= parent directory mtime."""
        # Replace an existing file.
        target = tmp_path / "out.json"
        target.write_text("old", encoding="utf-8")
        atomic_write_text(target, "replaced")
        assert target.stat().st_mtime_ns >= target.parent.stat().st_mtime_ns

        # Create a new file in a subdirectory.
        sub = tmp_path / "sub"
        sub.mkdir()
        new_target = sub / "new.json"
        atomic_write_text(new_target, "created")
        assert new_target.stat().st_mtime_ns >= new_target.parent.stat().st_mtime_ns

    def test_does_not_mutate_process_umask(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Creating a new file never calls os.umask."""
        import scripts.lib.atomic_io as _mod

        def _forbid_umask(_mask: int) -> int:
            raise AssertionError("os.umask must not be called")

        monkeypatch.setattr(_mod.os, "umask", _forbid_umask)
        target = tmp_path / "no_umask.json"
        atomic_write_text(target, "data")
        assert target.read_text(encoding="utf-8") == "data"

    def test_default_file_mode_fallback_without_proc_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Falls back to 0o644 when /proc/self/status is unavailable."""
        import scripts.lib.atomic_io as _mod

        orig_read_text = Path.read_text

        def _missing_proc(self: Path, *args: object, **kwargs: object) -> str:
            if str(self) == "/proc/self/status":
                raise FileNotFoundError("no /proc")
            return orig_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(Path, "read_text", _missing_proc)
        assert _mod._default_file_mode() == 0o644

    def test_writes_large_payload_completely(self, tmp_path: Path) -> None:
        """Writes multi-megabyte content without truncation."""
        target = tmp_path / "large.txt"
        payload = ("abcdefgh" * 1024 + "\n") * 256
        atomic_write_text(target, payload)
        assert target.read_text(encoding="utf-8") == payload


def _make_failing_os_replace():
    """Return a patched ``os`` module namespace where ``replace`` always raises."""
    import types

    fake = types.ModuleType("fake_os")
    # Copy everything from os, then override replace.
    for attr in dir(os):
        if not attr.startswith("__"):
            setattr(fake, attr, getattr(os, attr))

    def _bad_replace(src: str, dst: str | os.PathLike[str]) -> None:
        # Clean up the temp file the way real code would not.
        try:
            os.unlink(src)
        except OSError:
            pass
        raise OSError("injected")

    fake.replace = _bad_replace  # type: ignore[attr-defined]
    return fake
