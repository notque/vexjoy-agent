"""Tests for sync-to-user-claude.py symlink preservation logic."""

import json
import os
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks/ to sys.path so we can import the module
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

# Import the module under test (filename has hyphens, use importlib)
import importlib.util

spec = importlib.util.spec_from_file_location(
    "sync_to_user_claude",
    HOOKS_DIR / "sync-to-user-claude.py",
)
sync_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_mod)


class TestReadInstallMode:
    """Tests for _read_install_mode."""

    def test_symlink_mode(self, tmp_path: Path) -> None:
        manifest = {"mode": "symlink", "toolkit_path": "/some/path"}
        (tmp_path / ".install-manifest.json").write_text(json.dumps(manifest))
        assert sync_mod._read_install_mode(tmp_path) == "symlink"

    def test_copy_mode(self, tmp_path: Path) -> None:
        manifest = {"mode": "copy", "toolkit_path": "/some/path"}
        (tmp_path / ".install-manifest.json").write_text(json.dumps(manifest))
        assert sync_mod._read_install_mode(tmp_path) == "copy"

    def test_missing_manifest(self, tmp_path: Path) -> None:
        assert sync_mod._read_install_mode(tmp_path) == "copy"

    def test_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / ".install-manifest.json").write_text("{invalid json")
        assert sync_mod._read_install_mode(tmp_path) == "copy"

    def test_missing_mode_key(self, tmp_path: Path) -> None:
        manifest = {"toolkit_path": "/some/path"}
        (tmp_path / ".install-manifest.json").write_text(json.dumps(manifest))
        assert sync_mod._read_install_mode(tmp_path) == "copy"


class TestUpdateManifestToolkitPath:
    """Tests for _update_manifest_toolkit_path."""

    def test_updates_stale_path(self, tmp_path: Path) -> None:
        manifest = {"mode": "symlink", "toolkit_path": "/old/repo/path"}
        manifest_path = tmp_path / ".install-manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        new_repo = tmp_path / "new-repo"
        new_repo.mkdir()
        sync_mod._update_manifest_toolkit_path(tmp_path, new_repo)

        updated = json.loads(manifest_path.read_text())
        assert updated["toolkit_path"] == str(new_repo)
        assert updated["mode"] == "symlink"

    def test_no_update_when_path_matches(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        manifest = {"mode": "symlink", "toolkit_path": str(repo)}
        manifest_path = tmp_path / ".install-manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        mtime_before = manifest_path.stat().st_mtime
        sync_mod._update_manifest_toolkit_path(tmp_path, repo)

        # File should not have been rewritten
        mtime_after = manifest_path.stat().st_mtime
        assert mtime_before == mtime_after

    def test_no_crash_on_missing_manifest(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        # Should not raise
        sync_mod._update_manifest_toolkit_path(tmp_path, repo)


class TestEnsureSymlink:
    """Tests for _ensure_symlink."""

    def test_creates_new_symlink(self, tmp_path: Path) -> None:
        src = tmp_path / "source"
        src.mkdir()
        (src / "test.txt").write_text("hello")

        dst = tmp_path / "target"
        result = sync_mod._ensure_symlink(src, dst)

        assert result is True
        assert dst.is_symlink()
        assert dst.resolve() == src.resolve()
        assert (dst / "test.txt").read_text() == "hello"

    def test_preserves_correct_symlink(self, tmp_path: Path) -> None:
        src = tmp_path / "source"
        src.mkdir()
        dst = tmp_path / "target"
        dst.symlink_to(src)

        result = sync_mod._ensure_symlink(src, dst)

        assert result is True
        assert dst.is_symlink()

    def test_replaces_wrong_symlink(self, tmp_path: Path) -> None:
        src = tmp_path / "source"
        src.mkdir()
        wrong_src = tmp_path / "wrong"
        wrong_src.mkdir()
        dst = tmp_path / "target"
        dst.symlink_to(wrong_src)

        result = sync_mod._ensure_symlink(src, dst)

        assert result is True
        assert dst.is_symlink()
        assert dst.resolve() == src.resolve()

    def test_replaces_regular_directory(self, tmp_path: Path) -> None:
        src = tmp_path / "source"
        src.mkdir()
        (src / "real.txt").write_text("real")

        dst = tmp_path / "target"
        dst.mkdir()
        (dst / "copied.txt").write_text("copy")

        result = sync_mod._ensure_symlink(src, dst)

        assert result is True
        assert dst.is_symlink()
        assert dst.resolve() == src.resolve()
        # The copied file should be gone, replaced by symlink to source
        assert (dst / "real.txt").read_text() == "real"
        assert not (dst / "copied.txt").exists()

    def test_replaces_broken_symlink(self, tmp_path: Path) -> None:
        src = tmp_path / "source"
        src.mkdir()
        dst = tmp_path / "target"
        dst.symlink_to(tmp_path / "nonexistent")

        result = sync_mod._ensure_symlink(src, dst)

        assert result is True
        assert dst.is_symlink()
        assert dst.resolve() == src.resolve()


class TestMainSymlinkMode:
    """Integration tests for main() in symlink mode."""

    def _setup_repo(self, tmp_path: Path) -> Path:
        """Create a minimal repo structure for testing."""
        repo = tmp_path / "repo"
        repo.mkdir()

        # Create component directories with sample files
        for comp in ["agents", "skills", "hooks", "commands", "scripts"]:
            comp_dir = repo / comp
            comp_dir.mkdir()
            (comp_dir / "sample.md").write_text(f"# {comp} sample")

        # Create .claude/settings.json in repo
        repo_claude = repo / ".claude"
        repo_claude.mkdir()
        settings = {"hooks": {"SessionStart": []}}
        (repo_claude / "settings.json").write_text(json.dumps(settings))

        return repo

    def _setup_user_claude(self, tmp_path: Path, mode: str, repo: Path) -> Path:
        """Create ~/.claude with install manifest."""
        user_claude = tmp_path / "home" / ".claude"
        user_claude.mkdir(parents=True)
        manifest = {
            "mode": mode,
            "toolkit_path": str(repo),
            "components": ["agents", "skills", "hooks", "commands", "scripts"],
        }
        (user_claude / ".install-manifest.json").write_text(json.dumps(manifest))
        return user_claude

    def test_symlink_mode_creates_symlinks(self, tmp_path: Path) -> None:
        repo = self._setup_repo(tmp_path)
        user_claude = self._setup_user_claude(tmp_path, "symlink", repo)

        with (
            patch.object(Path, "home", return_value=tmp_path / "home"),
            patch.object(Path, "cwd", return_value=repo),
        ):
            sync_mod.main()

        # Check that symlinkable components are symlinks
        for comp in ["agents", "skills", "hooks", "scripts"]:
            target = user_claude / comp
            assert target.is_symlink(), f"{comp} should be a symlink"
            assert target.resolve() == (repo / comp).resolve()

        # Commands is additive-only, should be a directory (not symlink)
        commands_target = user_claude / "commands"
        assert commands_target.is_dir()
        assert not commands_target.is_symlink()

    def test_copy_mode_creates_directories(self, tmp_path: Path) -> None:
        repo = self._setup_repo(tmp_path)
        user_claude = self._setup_user_claude(tmp_path, "copy", repo)

        with (
            patch.object(Path, "home", return_value=tmp_path / "home"),
            patch.object(Path, "cwd", return_value=repo),
        ):
            sync_mod.main()

        # All components should be regular directories
        for comp in ["agents", "skills", "hooks", "commands", "scripts"]:
            target = user_claude / comp
            assert target.is_dir()
            assert not target.is_symlink(), f"{comp} should NOT be a symlink in copy mode"

    def test_symlink_mode_preserves_existing_symlinks(self, tmp_path: Path) -> None:
        repo = self._setup_repo(tmp_path)
        user_claude = self._setup_user_claude(tmp_path, "symlink", repo)

        # Pre-create correct symlinks (as install.sh would)
        for comp in ["agents", "skills", "hooks", "scripts"]:
            (user_claude / comp).symlink_to(repo / comp)

        with (
            patch.object(Path, "home", return_value=tmp_path / "home"),
            patch.object(Path, "cwd", return_value=repo),
        ):
            sync_mod.main()

        # Symlinks should still be there
        for comp in ["agents", "skills", "hooks", "scripts"]:
            target = user_claude / comp
            assert target.is_symlink()
            assert target.resolve() == (repo / comp).resolve()

    def test_symlink_mode_replaces_copy_directories(self, tmp_path: Path) -> None:
        repo = self._setup_repo(tmp_path)
        user_claude = self._setup_user_claude(tmp_path, "symlink", repo)

        # Pre-create regular directories (as broken copy-mode sync would)
        for comp in ["agents", "skills", "hooks", "scripts"]:
            comp_dir = user_claude / comp
            comp_dir.mkdir()
            (comp_dir / "stale.txt").write_text("stale copy")

        with (
            patch.object(Path, "home", return_value=tmp_path / "home"),
            patch.object(Path, "cwd", return_value=repo),
        ):
            sync_mod.main()

        # Should now be symlinks, not directories
        for comp in ["agents", "skills", "hooks", "scripts"]:
            target = user_claude / comp
            assert target.is_symlink()
            assert target.resolve() == (repo / comp).resolve()
            # Stale files should be gone
            assert not (target / "stale.txt").exists()
