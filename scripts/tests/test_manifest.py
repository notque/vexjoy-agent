"""Tests for scripts/manifest.py snapshot and rollback system."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "manifest.py"


def run_script(*args: str, expect_rc: int = 0) -> subprocess.CompletedProcess[str]:
    """Run manifest.py with given arguments."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == expect_rc, (
        f"Expected rc={expect_rc}, got {result.returncode}\nstderr: {result.stderr}\nstdout: {result.stdout}"
    )
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a minimal repo structure for isolated tests."""
    # agents
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "test-agent.md").write_text("---\nname: test-agent\n---\n# Test Agent\nContent here.\n")

    # skills
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: test-skill\n---\n# Test Skill\nContent here.\n")

    # scripts dir (so REPO_ROOT detection works if needed)
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()

    return tmp_path


@pytest.fixture
def manifest_module(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch):
    """Import manifest module with REPO_ROOT patched to tmp_repo."""
    monkeypatch.syspath_prepend(str(REPO_ROOT / "scripts"))

    import manifest

    monkeypatch.setattr(manifest, "REPO_ROOT", tmp_repo)
    monkeypatch.setattr(manifest, "MANIFESTS_DIR", tmp_repo / ".claude" / "manifests")
    monkeypatch.setattr(manifest, "BACKUPS_DIR", tmp_repo / ".claude" / "backups")
    monkeypatch.setattr(manifest, "SCORE_SCRIPT", tmp_repo / "scripts" / "score-component.py")

    return manifest


# ---------------------------------------------------------------------------
# SHA-256 computation
# ---------------------------------------------------------------------------


class TestSha256:
    """Test SHA-256 computation."""

    def test_sha256_known_content(self, tmp_path: Path, manifest_module) -> None:
        """SHA-256 of known content matches expected hash."""
        f = tmp_path / "hello.txt"
        f.write_text("hello\n")
        result = manifest_module.compute_sha256(f)
        # sha256 of "hello\n"
        assert len(result) == 64
        assert result == "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03"

    def test_sha256_empty_file(self, tmp_path: Path, manifest_module) -> None:
        """SHA-256 of empty file is the well-known empty hash."""
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        result = manifest_module.compute_sha256(f)
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_sha256_binary_content(self, tmp_path: Path, manifest_module) -> None:
        """SHA-256 works on binary content."""
        f = tmp_path / "binary.bin"
        f.write_bytes(bytes(range(256)))
        result = manifest_module.compute_sha256(f)
        assert len(result) == 64


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


class TestSnapshot:
    """Test the snapshot subcommand."""

    def test_snapshot_creates_manifest_and_backups(self, tmp_repo: Path, manifest_module) -> None:
        """Snapshot creates manifest JSON and backup copies."""
        import argparse

        args = argparse.Namespace(all=False, files=["agents/test-agent.md"])
        rc = manifest_module.cmd_snapshot(args)
        assert rc == 0

        # Manifest directory created
        manifests_dir = tmp_repo / ".claude" / "manifests"
        assert manifests_dir.is_dir()

        # Exactly one manifest
        manifests = list(manifests_dir.glob("upgrade-*.json"))
        assert len(manifests) == 1

        # Parse manifest
        data = json.loads(manifests[0].read_text())
        assert "timestamp" in data
        assert len(data["files"]) == 1

        entry = data["files"][0]
        assert entry["path"] == "agents/test-agent.md"
        assert entry["action"] == "existing"
        assert len(entry["sha256"]) == 64

        # Backup file exists
        backup = tmp_repo / entry["backup_path"]
        assert backup.exists()
        assert backup.read_text() == (tmp_repo / "agents" / "test-agent.md").read_text()

    def test_snapshot_all_finds_agents_and_skills(self, tmp_repo: Path, manifest_module) -> None:
        """Snapshot --all discovers all agent and skill files."""
        import argparse

        args = argparse.Namespace(all=True, files=[])
        rc = manifest_module.cmd_snapshot(args)
        assert rc == 0

        manifests = list((tmp_repo / ".claude" / "manifests").glob("upgrade-*.json"))
        data = json.loads(manifests[0].read_text())

        paths = [e["path"] for e in data["files"]]
        assert "agents/test-agent.md" in paths
        assert "skills/test-skill/SKILL.md" in paths

    def test_snapshot_missing_file_returns_error(self, tmp_repo: Path, manifest_module) -> None:
        """Snapshot with nonexistent file returns exit code 2."""
        import argparse

        args = argparse.Namespace(all=False, files=["agents/nonexistent.md"])
        rc = manifest_module.cmd_snapshot(args)
        assert rc == 2

    def test_snapshot_no_args_returns_error(self, tmp_repo: Path, manifest_module) -> None:
        """Snapshot with no files and no --all returns exit code 2."""
        import argparse

        args = argparse.Namespace(all=False, files=[])
        rc = manifest_module.cmd_snapshot(args)
        assert rc == 2

    def test_snapshot_preserves_relative_path_in_backup(self, tmp_repo: Path, manifest_module) -> None:
        """Backup preserves the relative directory structure."""
        import argparse

        args = argparse.Namespace(all=False, files=["skills/test-skill/SKILL.md"])
        rc = manifest_module.cmd_snapshot(args)
        assert rc == 0

        manifests = list((tmp_repo / ".claude" / "manifests").glob("upgrade-*.json"))
        data = json.loads(manifests[0].read_text())
        entry = data["files"][0]

        backup = tmp_repo / entry["backup_path"]
        assert backup.exists()
        # The backup should be under .claude/backups/<ts>/skills/test-skill/SKILL.md
        assert "skills/test-skill/SKILL.md" in entry["backup_path"]


# ---------------------------------------------------------------------------
# Undo
# ---------------------------------------------------------------------------


class TestUndo:
    """Test the undo subcommand."""

    def test_undo_restores_files(self, tmp_repo: Path, manifest_module, capsys: pytest.CaptureFixture[str]) -> None:
        """Undo restores files to their snapshotted state."""
        import argparse

        original_content = (tmp_repo / "agents" / "test-agent.md").read_text()

        # Snapshot
        args = argparse.Namespace(all=False, files=["agents/test-agent.md"])
        manifest_module.cmd_snapshot(args)

        # Modify the file
        (tmp_repo / "agents" / "test-agent.md").write_text("MODIFIED CONTENT")
        assert (tmp_repo / "agents" / "test-agent.md").read_text() == "MODIFIED CONTENT"

        # Find the manifest
        manifests = list((tmp_repo / ".claude" / "manifests").glob("upgrade-*.json"))
        rel_manifest = str(manifests[0].relative_to(tmp_repo))

        # Undo
        args = argparse.Namespace(manifest=rel_manifest)
        rc = manifest_module.cmd_undo(args)
        assert rc == 0

        # File restored
        assert (tmp_repo / "agents" / "test-agent.md").read_text() == original_content

        captured = capsys.readouterr()
        assert "Restored: agents/test-agent.md" in captured.out
        assert "Restored 1 files from manifest" in captured.out

    def test_undo_missing_backup_warns(
        self, tmp_repo: Path, manifest_module, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Undo warns gracefully when backup file is missing."""
        import argparse

        # Create a manifest pointing to a nonexistent backup
        manifests_dir = tmp_repo / ".claude" / "manifests"
        manifests_dir.mkdir(parents=True, exist_ok=True)

        manifest_data = {
            "timestamp": "2026-03-22T14:30:00Z",
            "files": [
                {
                    "path": "agents/test-agent.md",
                    "action": "existing",
                    "sha256": "abc123",
                    "backup_path": ".claude/backups/2026-03-22T143000/agents/test-agent.md",
                }
            ],
        }
        manifest_path = manifests_dir / "upgrade-2026-03-22T143000.json"
        manifest_path.write_text(json.dumps(manifest_data))

        args = argparse.Namespace(manifest=str(manifest_path.relative_to(tmp_repo)))
        rc = manifest_module.cmd_undo(args)
        assert rc == 0

        captured = capsys.readouterr()
        assert "Warning: Backup missing" in captured.err
        assert "Restored 0 files from manifest" in captured.out

    def test_undo_nonexistent_manifest_returns_error(self, tmp_repo: Path, manifest_module) -> None:
        """Undo with nonexistent manifest returns exit code 2."""
        import argparse

        args = argparse.Namespace(manifest="nonexistent.json")
        rc = manifest_module.cmd_undo(args)
        assert rc == 2

    def test_undo_creates_parent_dirs(self, tmp_repo: Path, manifest_module) -> None:
        """Undo creates parent directories if target dir was deleted."""
        import argparse

        # Snapshot a file
        args = argparse.Namespace(all=False, files=["agents/test-agent.md"])
        manifest_module.cmd_snapshot(args)

        manifests = list((tmp_repo / ".claude" / "manifests").glob("upgrade-*.json"))

        # Delete the entire agents directory
        import shutil

        shutil.rmtree(tmp_repo / "agents")
        assert not (tmp_repo / "agents").exists()

        # Undo should recreate it
        args = argparse.Namespace(manifest=str(manifests[0].relative_to(tmp_repo)))
        rc = manifest_module.cmd_undo(args)
        assert rc == 0
        assert (tmp_repo / "agents" / "test-agent.md").exists()


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


class TestList:
    """Test the list subcommand."""

    def test_list_no_manifests(self, tmp_repo: Path, manifest_module, capsys: pytest.CaptureFixture[str]) -> None:
        """List with no manifests prints appropriate message."""
        import argparse

        args = argparse.Namespace()
        rc = manifest_module.cmd_list(args)
        assert rc == 0

        captured = capsys.readouterr()
        assert "No manifests found" in captured.out

    def test_list_shows_manifests_sorted(
        self, tmp_repo: Path, manifest_module, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """List shows manifests sorted by timestamp descending."""
        manifests_dir = tmp_repo / ".claude" / "manifests"
        manifests_dir.mkdir(parents=True, exist_ok=True)

        # Create two manifests with different timestamps
        for ts, count in [("2026-03-20T100000", 2), ("2026-03-22T143000", 5)]:
            data = {
                "timestamp": ts,
                "files": [
                    {"path": f"file{i}.md", "action": "existing", "sha256": "a" * 64, "backup_path": f"backup{i}"}
                    for i in range(count)
                ],
            }
            (manifests_dir / f"upgrade-{ts}.json").write_text(json.dumps(data))

        import argparse

        args = argparse.Namespace()
        rc = manifest_module.cmd_list(args)
        assert rc == 0

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")

        # The newer manifest should appear first (sorted descending by filename)
        data_lines = [l for l in lines if "upgrade-" in l]
        assert len(data_lines) == 2
        assert "2026-03-22" in data_lines[0]
        assert "2026-03-20" in data_lines[1]


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------


class TestVerify:
    """Test the verify subcommand."""

    def test_verify_unchanged_files(self, tmp_repo: Path, manifest_module, capsys: pytest.CaptureFixture[str]) -> None:
        """Verify reports unchanged when files haven't been modified."""
        import argparse

        # Snapshot
        args = argparse.Namespace(all=False, files=["agents/test-agent.md"])
        manifest_module.cmd_snapshot(args)

        manifests = list((tmp_repo / ".claude" / "manifests").glob("upgrade-*.json"))
        args = argparse.Namespace(manifest=str(manifests[0].relative_to(tmp_repo)))
        rc = manifest_module.cmd_verify(args)
        assert rc == 0

        captured = capsys.readouterr()
        assert "UNCHANGED" in captured.out
        assert "1 unchanged" in captured.out

    def test_verify_detects_modified(self, tmp_repo: Path, manifest_module, capsys: pytest.CaptureFixture[str]) -> None:
        """Verify detects files that have been modified since snapshot."""
        import argparse

        # Snapshot
        args = argparse.Namespace(all=False, files=["agents/test-agent.md"])
        manifest_module.cmd_snapshot(args)

        # Modify
        (tmp_repo / "agents" / "test-agent.md").write_text("CHANGED")

        manifests = list((tmp_repo / ".claude" / "manifests").glob("upgrade-*.json"))
        args = argparse.Namespace(manifest=str(manifests[0].relative_to(tmp_repo)))
        rc = manifest_module.cmd_verify(args)
        assert rc == 0

        captured = capsys.readouterr()
        assert "MODIFIED" in captured.out
        assert "1 modified" in captured.out

    def test_verify_detects_deleted(self, tmp_repo: Path, manifest_module, capsys: pytest.CaptureFixture[str]) -> None:
        """Verify detects files that have been deleted since snapshot."""
        import argparse

        # Snapshot
        args = argparse.Namespace(all=False, files=["agents/test-agent.md"])
        manifest_module.cmd_snapshot(args)

        # Delete
        (tmp_repo / "agents" / "test-agent.md").unlink()

        manifests = list((tmp_repo / ".claude" / "manifests").glob("upgrade-*.json"))
        args = argparse.Namespace(manifest=str(manifests[0].relative_to(tmp_repo)))
        rc = manifest_module.cmd_verify(args)
        assert rc == 0

        captured = capsys.readouterr()
        assert "DELETED" in captured.out
        assert "1 deleted" in captured.out

    def test_verify_nonexistent_manifest_returns_error(self, tmp_repo: Path, manifest_module) -> None:
        """Verify with nonexistent manifest returns exit code 2."""
        import argparse

        args = argparse.Namespace(manifest="nonexistent.json")
        rc = manifest_module.cmd_verify(args)
        assert rc == 2


# ---------------------------------------------------------------------------
# Directory creation
# ---------------------------------------------------------------------------


class TestDirectoryCreation:
    """Test that directories are created as needed."""

    def test_snapshot_creates_claude_dirs(self, tmp_repo: Path, manifest_module) -> None:
        """Snapshot creates .claude/manifests and .claude/backups directories."""
        import argparse

        assert not (tmp_repo / ".claude" / "manifests").exists()
        assert not (tmp_repo / ".claude" / "backups").exists()

        args = argparse.Namespace(all=False, files=["agents/test-agent.md"])
        manifest_module.cmd_snapshot(args)

        assert (tmp_repo / ".claude" / "manifests").is_dir()
        assert (tmp_repo / ".claude" / "backups").is_dir()


# ---------------------------------------------------------------------------
# find_all_components
# ---------------------------------------------------------------------------


class TestFindAllComponents:
    """Test component discovery."""

    def test_finds_agents_and_skills(self, tmp_repo: Path, manifest_module) -> None:
        """find_all_components discovers agents and skills."""
        components = manifest_module.find_all_components()
        paths = [str(c.relative_to(tmp_repo)) for c in components]
        assert "agents/test-agent.md" in paths
        assert "skills/test-skill/SKILL.md" in paths

    def test_empty_repo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """find_all_components returns empty list for empty repo."""
        monkeypatch.syspath_prepend(str(REPO_ROOT / "scripts"))
        import manifest

        empty_dir = tmp_path / "empty_repo"
        empty_dir.mkdir()
        monkeypatch.setattr(manifest, "REPO_ROOT", empty_dir)
        components = manifest.find_all_components()
        assert components == []


# ---------------------------------------------------------------------------
# CLI integration (subprocess)
# ---------------------------------------------------------------------------


class TestCLIIntegration:
    """Integration tests running the script as a subprocess."""

    def test_snapshot_single_file(self) -> None:
        """Snapshot a real agent file via CLI."""
        result = run_script("snapshot", "agents/golang-general-engineer.md")
        assert ".claude/manifests/upgrade-" in result.stdout

        # Clean up created manifest and backup
        manifest_path = REPO_ROOT / result.stdout.strip()
        if manifest_path.exists():
            data = json.loads(manifest_path.read_text())
            manifest_path.unlink()
            # Clean up backup files and their timestamp directory
            for entry in data.get("files", []):
                backup = REPO_ROOT / entry["backup_path"]
                if backup.exists():
                    backup.unlink()
            # Remove the timestamp backup directory (and any empty parents up to .claude/backups)
            if data.get("files"):
                backup_ts_dir = (REPO_ROOT / data["files"][0]["backup_path"]).parent
                while backup_ts_dir != REPO_ROOT / ".claude" / "backups" and backup_ts_dir.exists():
                    try:
                        backup_ts_dir.rmdir()  # only removes if empty
                    except OSError:
                        break
                    backup_ts_dir = backup_ts_dir.parent

    def test_no_subcommand_fails(self) -> None:
        """Running without a subcommand should fail."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode != 0

    def test_help_flag(self) -> None:
        """--help prints usage information."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        assert "snapshot" in result.stdout
        assert "undo" in result.stdout
        assert "list" in result.stdout
        assert "verify" in result.stdout
