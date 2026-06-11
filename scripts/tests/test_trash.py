"""Tests for trash.py.

Covers XDG trash root resolution, file/dir moves with .trashinfo records,
collision-safe naming, --allow-missing, and the copy fallback path.
All tests redirect the trash via XDG_DATA_HOME to a temp directory.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

sys_path_entry = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, sys_path_entry)
trash = importlib.import_module("trash")
sys.path.pop(0)


@pytest.fixture()
def trash_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point XDG_DATA_HOME at a temp dir; return the resulting Trash root."""
    data_home = tmp_path / "data"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    monkeypatch.chdir(tmp_path)
    return data_home / "Trash"


class TestTrashRoot:
    def test_uses_xdg_data_home(self, trash_dir: Path) -> None:
        assert trash.trash_root() == trash_dir

    def test_defaults_to_local_share(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        assert trash.trash_root() == Path.home() / ".local" / "share" / "Trash"


class TestMove:
    def test_moves_file_and_writes_trashinfo(self, tmp_path: Path, trash_dir: Path) -> None:
        target = tmp_path / "doomed.txt"
        target.write_text("bye")
        assert trash.main([str(target)]) == 0
        assert not target.exists()
        assert (trash_dir / "files" / "doomed.txt").read_text() == "bye"
        info = (trash_dir / "info" / "doomed.txt.trashinfo").read_text()
        assert "[Trash Info]" in info
        assert str(target) in info
        assert "DeletionDate=" in info

    def test_moves_directory(self, tmp_path: Path, trash_dir: Path) -> None:
        target = tmp_path / "dir"
        target.mkdir()
        (target / "inner.txt").write_text("x")
        assert trash.main([str(target)]) == 0
        assert not target.exists()
        assert (trash_dir / "files" / "dir" / "inner.txt").read_text() == "x"

    def test_collision_gets_unique_name(self, tmp_path: Path, trash_dir: Path) -> None:
        for content in ("one", "two"):
            target = tmp_path / "same.txt"
            target.write_text(content)
            assert trash.main([str(target)]) == 0
        files = sorted(p.name for p in (trash_dir / "files").iterdir())
        assert len(files) == 2
        assert "same.txt" in files
        other = next(name for name in files if name != "same.txt")
        assert other.startswith("same-") and other.endswith(".txt")
        assert (trash_dir / "info" / f"{other}.trashinfo").exists()

    def test_relative_path(self, tmp_path: Path, trash_dir: Path) -> None:
        (tmp_path / "rel.txt").write_text("r")
        assert trash.main(["rel.txt"]) == 0
        assert (trash_dir / "files" / "rel.txt").exists()

    def test_copy_fallback_when_rename_fails(
        self, tmp_path: Path, trash_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "xfs.txt"
        target.write_text("cross")

        def raise_exdev(self: Path, dest: Path) -> None:
            raise OSError(18, "Invalid cross-device link")

        monkeypatch.setattr(Path, "rename", raise_exdev)
        assert trash.main([str(target)]) == 0
        assert not target.exists()
        assert (trash_dir / "files" / "xfs.txt").read_text() == "cross"


class TestMissing:
    def test_missing_target_fails(self, tmp_path: Path, trash_dir: Path, capsys: pytest.CaptureFixture) -> None:
        assert trash.main([str(tmp_path / "ghost.txt")]) == 1
        assert "not found" in capsys.readouterr().err

    def test_allow_missing_skips(self, tmp_path: Path, trash_dir: Path) -> None:
        real = tmp_path / "real.txt"
        real.write_text("r")
        assert trash.main(["--allow-missing", str(tmp_path / "ghost.txt"), str(real)]) == 0
        assert (trash_dir / "files" / "real.txt").exists()
