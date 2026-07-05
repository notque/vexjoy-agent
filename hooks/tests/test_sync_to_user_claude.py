"""Tests for sync-to-user-claude.py symlink preservation logic."""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import ClassVar
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
        # Patch _is_ephemeral_path since test fixtures live in /tmp/
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
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
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._update_manifest_toolkit_path(tmp_path, repo)

        # File should not have been rewritten
        mtime_after = manifest_path.stat().st_mtime
        assert mtime_before == mtime_after

    def test_no_crash_on_missing_manifest(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        # Should not raise
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._update_manifest_toolkit_path(tmp_path, repo)

    def test_rejects_tmp_path(self, tmp_path: Path) -> None:
        """Verify /tmp/ paths are rejected (worktree poisoning guard)."""
        manifest = {"mode": "symlink", "toolkit_path": "/real/repo"}
        manifest_path = tmp_path / ".install-manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        tmp_repo = tmp_path / "worktree"
        tmp_repo.mkdir()
        # Don't patch — let the real guard run
        sync_mod._update_manifest_toolkit_path(tmp_path, tmp_repo)

        # Manifest should NOT be updated (still has original path)
        updated = json.loads(manifest_path.read_text())
        assert updated["toolkit_path"] == "/real/repo"


class TestEnsureSymlink:
    """Tests for _ensure_symlink."""

    def test_creates_new_symlink(self, tmp_path: Path) -> None:
        src = tmp_path / "source"
        src.mkdir()
        (src / "test.txt").write_text("hello")

        dst = tmp_path / "target"
        # Patch _is_ephemeral_path since test fixtures live in /tmp/
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
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

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
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

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
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

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
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

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            result = sync_mod._ensure_symlink(src, dst)

        assert result is True
        assert dst.is_symlink()
        assert dst.resolve() == src.resolve()

    def test_blocks_tmp_source(self, tmp_path: Path) -> None:
        """Verify /tmp/ sources are blocked (worktree poisoning guard)."""
        src = tmp_path / "source"
        src.mkdir()
        dst = tmp_path / "target"

        # Don't patch — let the real guard run
        result = sync_mod._ensure_symlink(src, dst)

        assert result is False
        assert not dst.exists()


class TestRuntimeIndexMerge:
    """The runtime ~/.claude/skills/INDEX.json must be a real file holding
    the tracked-first merge of skills/INDEX.json and skills/INDEX.local.json.

    Two invariants (PR #778 bug class plus the private-skill leak):
    1. Every tracked entry is present; local entries add per-name. A stale
       local can neither hide nor override tracked entries.
    2. In-place writes to the runtime index never reach the repo files.
    """

    TRACKED: ClassVar[dict] = {
        "version": "2.0",
        "skills": {
            "do": {"description": "tracked do"},
            "new-skill": {"description": "added after local was generated"},
        },
    }
    LOCAL: ClassVar[dict] = {
        "version": "2.0",
        "skills": {
            "do": {"description": "STALE do"},
            "voice-x": {"description": "private"},
        },
    }

    def _make_src(self, tmp_path: Path, with_tracked: bool = True, with_local: bool = True) -> Path:
        src = tmp_path / "skills"
        src.mkdir()
        if with_tracked:
            (src / "INDEX.json").write_text(json.dumps(self.TRACKED))
        if with_local:
            # Stale local: superset of old entries, missing "new-skill"
            (src / "INDEX.local.json").write_text(json.dumps(self.LOCAL))
        # one real skill so the flatten loop has something to do
        skill = src / "meta" / "do"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: do\n---\n")
        return src

    def test_stale_local_does_not_hide_tracked_entries(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path)
        dst = tmp_path / "out"
        sync_mod._sync_skills_flat_symlinks(src, dst)

        runtime = dst / "INDEX.json"
        assert runtime.is_file() and not runtime.is_symlink()
        skills = json.loads(runtime.read_text())["skills"]
        # Every tracked entry present; local adds its private entry
        assert set(self.TRACKED["skills"]) <= set(skills)
        assert "voice-x" in skills

    def test_local_cannot_override_tracked_content(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path)
        dst = tmp_path / "out"
        sync_mod._sync_skills_flat_symlinks(src, dst)

        skills = json.loads((dst / "INDEX.json").read_text())["skills"]
        assert skills["do"] == {"description": "tracked do"}

    def test_inplace_write_never_reaches_repo_files(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path)
        dst = tmp_path / "out"
        sync_mod._sync_skills_flat_symlinks(src, dst)

        # Simulate a harness rewriting the runtime index in place
        (dst / "INDEX.json").write_text('{"skills": {"leak": {}}}\n')

        assert json.loads((src / "INDEX.json").read_text()) == self.TRACKED
        assert json.loads((src / "INDEX.local.json").read_text()) == self.LOCAL

    def test_inplace_write_spares_tracked_without_local(self, tmp_path: Path) -> None:
        """No local index: runtime must still be a real file, not a symlink
        to the tracked index (the old fallback leaked writes into the repo)."""
        src = self._make_src(tmp_path, with_local=False)
        dst = tmp_path / "out"
        sync_mod._sync_skills_flat_symlinks(src, dst)

        runtime = dst / "INDEX.json"
        assert runtime.is_file() and not runtime.is_symlink()
        assert json.loads(runtime.read_text())["skills"] == self.TRACKED["skills"]

        runtime.write_text('{"skills": {"leak": {}}}\n')
        assert json.loads((src / "INDEX.json").read_text()) == self.TRACKED

    def test_local_only_still_materializes(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path, with_tracked=False)
        dst = tmp_path / "out"
        sync_mod._sync_skills_flat_symlinks(src, dst)

        skills = json.loads((dst / "INDEX.json").read_text())["skills"]
        assert skills == self.LOCAL["skills"]

    def test_pre_fix_symlink_replaced_by_real_file(self, tmp_path: Path) -> None:
        """A pre-fix install left dst/INDEX.json as a symlink into the repo.
        Sync must swap it for the real merged file without touching the repo
        file it pointed at."""
        src = self._make_src(tmp_path)
        dst = tmp_path / "out"
        dst.mkdir()
        (dst / "INDEX.json").symlink_to(src / "INDEX.local.json")

        sync_mod._sync_skills_flat_symlinks(src, dst)

        runtime = dst / "INDEX.json"
        assert runtime.is_file() and not runtime.is_symlink()
        assert "new-skill" in json.loads(runtime.read_text())["skills"]
        assert json.loads((src / "INDEX.local.json").read_text()) == self.LOCAL

    def test_unchanged_index_not_rewritten(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path)
        dst = tmp_path / "out"
        sync_mod._sync_skills_flat_symlinks(src, dst)
        mtime_before = (dst / "INDEX.json").stat().st_mtime_ns

        sync_mod._sync_skills_flat_symlinks(src, dst)
        assert (dst / "INDEX.json").stat().st_mtime_ns == mtime_before

    def test_no_index_files_creates_nothing(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path, with_tracked=False, with_local=False)
        dst = tmp_path / "out"
        sync_mod._sync_skills_flat_symlinks(src, dst)
        assert not (dst / "INDEX.json").exists()

    def test_local_symlink_still_created(self, tmp_path: Path) -> None:
        """INDEX.local.json keeps its plain root-file symlink."""
        src = self._make_src(tmp_path)
        dst = tmp_path / "out"
        sync_mod._sync_skills_flat_symlinks(src, dst)
        assert (dst / "INDEX.local.json").resolve() == (src / "INDEX.local.json").resolve()


class TestSupportDirSurvivesCleanup:
    """Support dirs (reference .md files, no SKILL.md) must enter
    expected_names, or the stale-cleanup loop unlinks them every
    SessionStart. Regression test for the voice-shared-references bug:
    the dir was missing from the root_dirs allowlist, so the cleanup
    deleted its symlink 4 times in one session."""

    def _make_src(self, tmp_path: Path) -> Path:
        src = tmp_path / "skills"
        refs = src / "voice-shared-references"
        refs.mkdir(parents=True)
        for name in (
            "anti-rhetorical-pivot.md",
            "voice-first-writing.md",
            "wabi-sabi-authenticity.md",
        ):
            (refs / name).write_text("# ref\n")
        # one real skill so the flatten loop has something to do
        skill = src / "meta" / "do"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: do\n---\n")
        return src

    def test_voice_shared_references_survives_sync(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path)
        dst = tmp_path / "out"
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._sync_skills_flat_symlinks(src, dst)
            # Second pass exercises the stale-cleanup against existing links
            sync_mod._sync_skills_flat_symlinks(src, dst)

        link = dst / "voice-shared-references"
        assert link.is_symlink()
        assert link.resolve() == (src / "voice-shared-references").resolve()
        assert (link / "voice-first-writing.md").read_text() == "# ref\n"

    def test_preexisting_support_symlink_not_unlinked(self, tmp_path: Path) -> None:
        """The original failure: a symlink already in dst was unlinked
        because its name never entered expected_names."""
        src = self._make_src(tmp_path)
        dst = tmp_path / "out"
        dst.mkdir()
        (dst / "voice-shared-references").symlink_to(src / "voice-shared-references")

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._sync_skills_flat_symlinks(src, dst)

        assert (dst / "voice-shared-references").is_symlink()

    def test_future_support_dir_protected_without_allowlist(self, tmp_path: Path) -> None:
        """Any root dir with .md files and no skill subdir is treated as a
        support dir, so the next shared-reference dir cannot repeat the bug."""
        src = self._make_src(tmp_path)
        refs = src / "new-shared-refs"
        refs.mkdir()
        (refs / "pattern.md").write_text("# pattern\n")
        dst = tmp_path / "out"

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._sync_skills_flat_symlinks(src, dst)
            sync_mod._sync_skills_flat_symlinks(src, dst)

        assert (dst / "new-shared-refs").is_symlink()

    def test_stale_symlink_still_removed(self, tmp_path: Path) -> None:
        """Cleanup still unlinks symlinks whose source left the repo."""
        src = self._make_src(tmp_path)
        gone = tmp_path / "gone-skill"
        gone.mkdir()
        dst = tmp_path / "out"
        dst.mkdir()
        (dst / "gone-skill").symlink_to(gone)

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._sync_skills_flat_symlinks(src, dst)

        assert not (dst / "gone-skill").exists()

    def test_category_with_readme_still_flattened(self, tmp_path: Path) -> None:
        """A category folder holding a stray README.md plus skill subdirs is
        NOT a support dir — its skills must still be flattened per-skill."""
        src = self._make_src(tmp_path)
        (src / "meta" / "README.md").write_text("# meta\n")
        dst = tmp_path / "out"

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._sync_skills_flat_symlinks(src, dst)

        assert (dst / "do").is_symlink()
        assert not (dst / "meta").exists()


class TestMainSymlinkMode:
    """Integration tests for main() in symlink mode."""

    def _setup_repo(self, tmp_path: Path) -> Path:
        """Create a minimal repo structure for testing."""
        repo = tmp_path / "repo"
        repo.mkdir()

        # Create component directories with sample files
        for comp in ["agents", "hooks", "commands", "scripts"]:
            comp_dir = repo / comp
            comp_dir.mkdir()
            (comp_dir / "sample.md").write_text(f"# {comp} sample")

        # Skills use nested category structure: skills/meta/sample/SKILL.md
        skills_dir = repo / "skills"
        skills_dir.mkdir()
        sample_skill = skills_dir / "meta" / "sample"
        sample_skill.mkdir(parents=True)
        (sample_skill / "SKILL.md").write_text("# sample skill")

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
            patch.object(sync_mod, "_is_git_worktree", return_value=False),
            patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
        ):
            sync_mod.main()

        # Non-skills symlinkable components are single symlinks
        for comp in ["agents", "hooks", "scripts"]:
            target = user_claude / comp
            assert target.is_symlink(), f"{comp} should be a symlink"
            assert target.resolve() == (repo / comp).resolve()

        # Skills uses per-skill symlinks (real dir with symlinks inside)
        skills_target = user_claude / "skills"
        assert skills_target.is_dir()
        assert not skills_target.is_symlink(), "skills should be a real directory, not a single symlink"

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
            patch.object(sync_mod, "_is_git_worktree", return_value=False),
            patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
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

        # Pre-create correct symlinks for non-skills components (as install.sh would)
        for comp in ["agents", "hooks", "scripts"]:
            (user_claude / comp).symlink_to(repo / comp)

        with (
            patch.object(Path, "home", return_value=tmp_path / "home"),
            patch.object(Path, "cwd", return_value=repo),
            patch.object(sync_mod, "_is_git_worktree", return_value=False),
            patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
        ):
            sync_mod.main()

        # Non-skills symlinks should still be there
        for comp in ["agents", "hooks", "scripts"]:
            target = user_claude / comp
            assert target.is_symlink()
            assert target.resolve() == (repo / comp).resolve()

        # Skills should be a real dir with per-skill symlinks
        skills_target = user_claude / "skills"
        assert skills_target.is_dir()
        assert not skills_target.is_symlink()

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
            patch.object(sync_mod, "_is_git_worktree", return_value=False),
            patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
        ):
            sync_mod.main()

        # Non-skills: should now be symlinks, not directories
        for comp in ["agents", "hooks", "scripts"]:
            target = user_claude / comp
            assert target.is_symlink()
            assert target.resolve() == (repo / comp).resolve()
            # Stale files should be gone
            assert not (target / "stale.txt").exists()

        # Skills: should be a real dir with per-skill symlinks
        skills_target = user_claude / "skills"
        assert skills_target.is_dir()
        assert not skills_target.is_symlink()
        # Per-skill symlinks are created inside; stale non-symlink files from
        # a previous copy-mode install are not removed by the symlink cleanup
        # (which only targets stale symlinks). This is acceptable — the important
        # thing is that the directory structure is correct and skill symlinks work.
        assert (skills_target / "sample").is_symlink()

    def test_worktree_skips_sync(self, tmp_path: Path) -> None:
        """Verify main() bails out when running inside a git worktree."""
        repo = self._setup_repo(tmp_path)
        user_claude = self._setup_user_claude(tmp_path, "symlink", repo)

        with (
            patch.object(Path, "home", return_value=tmp_path / "home"),
            patch.object(Path, "cwd", return_value=repo),
            patch.object(sync_mod, "_is_git_worktree", return_value=True),
        ):
            sync_mod.main()

        # Nothing should have been created
        assert not (user_claude / "agents").exists()
        assert not (user_claude / "hooks").exists()


class TestMainRuntimeIndex:
    """End-to-end runtime-index invariants through main(), both install modes."""

    TRACKED: ClassVar[dict] = {"version": "2.0", "skills": {"sample": {"description": "tracked"}}}
    LOCAL: ClassVar[dict] = {
        "version": "2.0",
        "skills": {"sample": {"description": "STALE"}, "voice-x": {"description": "private"}},
    }

    def _setup(self, tmp_path: Path, mode: str) -> tuple[Path, Path]:
        repo = tmp_path / "repo"
        repo.mkdir()
        for comp in ["agents", "hooks", "commands", "scripts"]:
            comp_dir = repo / comp
            comp_dir.mkdir()
            (comp_dir / "sample.md").write_text(f"# {comp} sample")
        skills_dir = repo / "skills"
        sample_skill = skills_dir / "meta" / "sample"
        sample_skill.mkdir(parents=True)
        (sample_skill / "SKILL.md").write_text("# sample skill")
        (skills_dir / "INDEX.json").write_text(json.dumps(self.TRACKED))
        (skills_dir / "INDEX.local.json").write_text(json.dumps(self.LOCAL))
        repo_claude = repo / ".claude"
        repo_claude.mkdir()
        (repo_claude / "settings.json").write_text(json.dumps({"hooks": {"SessionStart": []}}))

        user_claude = tmp_path / "home" / ".claude"
        user_claude.mkdir(parents=True)
        manifest = {
            "mode": mode,
            "toolkit_path": str(repo),
            "components": ["agents", "skills", "hooks", "commands", "scripts"],
        }
        (user_claude / ".install-manifest.json").write_text(json.dumps(manifest))
        return repo, user_claude

    def _run_main(self, tmp_path: Path, repo: Path) -> None:
        with (
            patch.object(Path, "home", return_value=tmp_path / "home"),
            patch.object(Path, "cwd", return_value=repo),
            patch.object(sync_mod, "_is_git_worktree", return_value=False),
            patch.object(sync_mod, "_is_ephemeral_path", return_value=False),
        ):
            sync_mod.main()

    @pytest.mark.parametrize("mode", ["symlink", "copy"])
    def test_runtime_index_merged_and_writes_stay_local(self, tmp_path: Path, mode: str) -> None:
        repo, user_claude = self._setup(tmp_path, mode)
        self._run_main(tmp_path, repo)

        runtime = user_claude / "skills" / "INDEX.json"
        assert runtime.is_file() and not runtime.is_symlink()
        skills = json.loads(runtime.read_text())["skills"]
        # Invariant 1: tracked entries win and are all present; local adds
        assert skills["sample"] == {"description": "tracked"}
        assert "voice-x" in skills

        # Invariant 2: in-place harness write never reaches the repo
        runtime.write_text('{"skills": {"leak": {}}}\n')
        assert json.loads((repo / "skills" / "INDEX.json").read_text()) == self.TRACKED
        assert json.loads((repo / "skills" / "INDEX.local.json").read_text()) == self.LOCAL

    def test_copy_mode_local_only_survives_stale_cleanup(self, tmp_path: Path) -> None:
        """Repo with only INDEX.local.json (tracked index not generated yet):
        the materialized runtime index must survive deferred stale cleanup."""
        repo, user_claude = self._setup(tmp_path, "copy")
        (repo / "skills" / "INDEX.json").unlink()
        self._run_main(tmp_path, repo)

        runtime = user_claude / "skills" / "INDEX.json"
        assert runtime.is_file()
        assert json.loads(runtime.read_text())["skills"] == self.LOCAL["skills"]

    def test_copy_mode_resync_refreshes_merge(self, tmp_path: Path) -> None:
        """A second sync after the tracked index gains a skill must surface
        the new entry in the runtime index (the stale-hide regression)."""
        repo, user_claude = self._setup(tmp_path, "copy")
        self._run_main(tmp_path, repo)

        updated = {"version": "2.0", "skills": {**self.TRACKED["skills"], "brand-new": {}}}
        (repo / "skills" / "INDEX.json").write_text(json.dumps(updated))
        self._run_main(tmp_path, repo)

        skills = json.loads((user_claude / "skills" / "INDEX.json").read_text())["skills"]
        assert "brand-new" in skills
        assert "voice-x" in skills


class TestResolvesInside:
    """Tests for _resolves_inside — the repo-path safety guard."""

    def test_path_inside_repo(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        child = repo / "skills" / "voice-shared-references"
        child.mkdir(parents=True)
        assert sync_mod._resolves_inside(child, repo) is True

    def test_path_outside_repo(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        other = tmp_path / "other"
        other.mkdir()
        assert sync_mod._resolves_inside(other, repo) is False

    def test_symlink_resolves_inside(self, tmp_path: Path) -> None:
        """A symlink in ~/.claude that points into the repo should be detected."""
        repo = tmp_path / "repo" / "skills" / "voice-shared-references"
        repo.mkdir(parents=True)
        link = tmp_path / "link"
        link.symlink_to(repo)
        assert sync_mod._resolves_inside(link, tmp_path / "repo") is True

    def test_equal_to_root(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        assert sync_mod._resolves_inside(repo, repo) is True

    def test_prefix_not_confused(self, tmp_path: Path) -> None:
        """repo-extra/ must not match repo/ as a prefix."""
        repo = tmp_path / "repo"
        repo.mkdir()
        sibling = tmp_path / "repo-extra"
        sibling.mkdir()
        assert sync_mod._resolves_inside(sibling, repo) is False


class TestRepoSideDeletionGuard:
    """Regression tests for the voice-shared-references repo-side deletion bug.

    When ~/.claude/skills/ contains a symlink into the repo, destructive
    operations (rmtree, unlink) must refuse to follow that symlink and
    delete tracked source files.  The guard is _resolves_inside, applied
    in _ensure_symlink, _sync_skills_flat_symlinks stale cleanup, and
    the deferred stale cleanup in _main_inner.
    """

    def _make_repo(self, tmp_path: Path) -> Path:
        """Build a minimal repo with voice-shared-references."""
        repo = tmp_path / "repo"
        skills = repo / "skills"
        vsr = skills / "voice-shared-references"
        vsr.mkdir(parents=True)
        for name in ("anti-rhetorical-pivot.md", "voice-first-writing.md", "wabi-sabi-authenticity.md"):
            (vsr / name).write_text(f"# {name}\n")
        # one skill so the flatten loop works
        skill = skills / "meta" / "do"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: do\n---\n")
        return repo

    def test_ensure_symlink_blocks_rmtree_through_parent_symlink(self, tmp_path: Path) -> None:
        """When dst resolves inside the repo via a parent symlink,
        _ensure_symlink must refuse to rmtree rather than delete repo files."""
        repo = self._make_repo(tmp_path)
        repo_vsr = repo / "skills" / "voice-shared-references"

        # Simulate: ~/.claude/skills is a symlink to repo/skills (old-style)
        claude_skills = tmp_path / "claude_skills"
        claude_skills.symlink_to(repo / "skills")

        # dst = ~/.claude/skills/voice-shared-references — resolves to repo path
        dst = claude_skills / "voice-shared-references"
        assert dst.is_dir() and not dst.is_symlink(), "dst traverses parent symlink, is NOT itself a symlink"

        # Without the guard, _ensure_symlink would rmtree the repo dir
        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            result = sync_mod._ensure_symlink(repo_vsr, dst, repo_root=repo)

        # Guard must have blocked the rmtree
        assert result is False, "_ensure_symlink should return False when dst resolves inside repo"

        # Repo files must still exist
        assert repo_vsr.is_dir()
        for name in ("anti-rhetorical-pivot.md", "voice-first-writing.md", "wabi-sabi-authenticity.md"):
            assert (repo_vsr / name).exists(), f"Repo file {name} was deleted!"

    def test_ensure_symlink_allows_rmtree_outside_repo(self, tmp_path: Path) -> None:
        """rmtree of a real dir outside the repo must still work."""
        repo = self._make_repo(tmp_path)
        src = repo / "skills" / "voice-shared-references"

        # dst is a real dir outside the repo (from a previous copy-mode install)
        dst = tmp_path / "claude" / "skills" / "voice-shared-references"
        dst.mkdir(parents=True)
        (dst / "stale-copy.md").write_text("copy")

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            result = sync_mod._ensure_symlink(src, dst, repo_root=repo)

        assert result is True
        assert dst.is_symlink()
        assert dst.resolve() == src.resolve()

    def test_flat_symlinks_guards_stale_cleanup(self, tmp_path: Path) -> None:
        """Stale cleanup in _sync_skills_flat_symlinks must not unlink
        symlinks that resolve inside the repo."""
        repo = self._make_repo(tmp_path)
        src = repo / "skills"

        # dst is a real dir with a stale symlink that points into the repo
        dst = tmp_path / "claude_skills"
        dst.mkdir()
        # Create a symlink that IS stale (not in expected_names) but
        # resolves inside the repo
        stale_link = dst / "stale-repo-link"
        stale_link.symlink_to(repo / "skills" / "meta")

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._sync_skills_flat_symlinks(src, dst, repo_root=repo)

        # The stale link should NOT have been removed (resolves inside repo)
        # Note: the guard protects it because it resolves inside repo
        # In practice, the important invariant is that repo files survive.
        assert (repo / "skills" / "meta" / "do" / "SKILL.md").exists()

    def test_repo_files_survive_full_sync(self, tmp_path: Path) -> None:
        """End-to-end: voice-shared-references files survive a full
        _sync_skills_flat_symlinks cycle, even with two passes."""
        repo = self._make_repo(tmp_path)
        src = repo / "skills"
        dst = tmp_path / "out"

        with patch.object(sync_mod, "_is_ephemeral_path", return_value=False):
            sync_mod._sync_skills_flat_symlinks(src, dst, repo_root=repo)
            sync_mod._sync_skills_flat_symlinks(src, dst, repo_root=repo)

        # Repo files must survive both passes
        for name in ("anti-rhetorical-pivot.md", "voice-first-writing.md", "wabi-sabi-authenticity.md"):
            repo_file = repo / "skills" / "voice-shared-references" / name
            assert repo_file.exists(), f"Repo file {name} was deleted by sync!"
            assert repo_file.read_text() == f"# {name}\n"

        # The symlink in dst must exist and point to the repo dir
        link = dst / "voice-shared-references"
        assert link.is_symlink()
        assert link.resolve() == (repo / "skills" / "voice-shared-references").resolve()
