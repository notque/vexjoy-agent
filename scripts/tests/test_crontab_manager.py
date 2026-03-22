"""Tests for crontab-manager.py.

All tests use monkeypatched subprocess calls — never touches real crontab.
"""

import argparse
import os
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the module under test
sys_path_entry = str(Path(__file__).resolve().parent.parent)
import importlib
import sys

sys.path.insert(0, sys_path_entry)
import importlib

crontab_manager = importlib.import_module("crontab-manager")
sys.path.pop(0)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CRONTAB = textwrap.dedent("""\
    # existing job
    0 3 * * * /usr/local/bin/backup.sh
    # claude-cron: reddit-automod
    7 */12 * * * /home/user/scripts/reddit-automod-cron.sh --execute >> /home/user/logs/cron.log 2>&1
""")


def _args(**kwargs: object) -> argparse.Namespace:
    defaults = {"dry_run": False, "force": False}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class FakeCrontab:
    """Simulates crontab read/write via subprocess monkeypatch."""

    def __init__(self, content: str = "") -> None:
        self.content = content
        self.installed: str | None = None

    def run(
        self,
        cmd: list[str],
        capture_output: bool = False,
        text: bool = False,
    ) -> MagicMock:
        result = MagicMock()
        if cmd == ["crontab", "-l"]:
            if not self.content:
                result.returncode = 1
                result.stderr = "no crontab for user"
                result.stdout = ""
            else:
                result.returncode = 0
                result.stdout = self.content
                result.stderr = ""
        elif len(cmd) == 2 and cmd[0] == "crontab" and cmd[1] != "-l":
            # Install from file
            path = cmd[1]
            self.content = Path(path).read_text()
            self.installed = self.content
            result.returncode = 0
            result.stderr = ""
        elif cmd == ["which", "claude"]:
            result.returncode = 0
            result.stdout = "/usr/local/bin/claude\n"
            result.stderr = ""
        else:
            result.returncode = 1
            result.stderr = f"unexpected command: {cmd}"
        return result


# ---------------------------------------------------------------------------
# _get_crontab / _install_crontab
# ---------------------------------------------------------------------------


class TestGetCrontab:
    def test_reads_existing(self) -> None:
        fake = FakeCrontab(SAMPLE_CRONTAB)
        with patch.object(crontab_manager.subprocess, "run", fake.run):
            result = crontab_manager._get_crontab()
        assert "backup.sh" in result
        assert "reddit-automod" in result

    def test_empty_crontab(self) -> None:
        fake = FakeCrontab("")
        with patch.object(crontab_manager.subprocess, "run", fake.run):
            result = crontab_manager._get_crontab()
        assert result == ""


class TestInstallCrontab:
    def test_installs_via_temp_file(self) -> None:
        fake = FakeCrontab("")
        with patch.object(crontab_manager.subprocess, "run", fake.run):
            crontab_manager._install_crontab("new content\n")
        assert fake.installed == "new content\n"


# ---------------------------------------------------------------------------
# _find_tag_lines
# ---------------------------------------------------------------------------


class TestFindTagLines:
    def test_finds_existing_tag(self) -> None:
        start, end = crontab_manager._find_tag_lines(SAMPLE_CRONTAB, "reddit-automod")
        assert start == 2
        assert end == 4

    def test_missing_tag(self) -> None:
        start, end = crontab_manager._find_tag_lines(SAMPLE_CRONTAB, "nonexistent")
        assert start == -1
        assert end == -1


# ---------------------------------------------------------------------------
# cmd_list
# ---------------------------------------------------------------------------


class TestCmdList:
    def test_lists_entries(self, capsys: pytest.CaptureFixture[str]) -> None:
        fake = FakeCrontab(SAMPLE_CRONTAB)
        with patch.object(crontab_manager.subprocess, "run", fake.run):
            result = crontab_manager.cmd_list(_args())
        assert result == 0
        output = capsys.readouterr().out
        assert "reddit-automod" in output
        assert "Other cron entries" in output

    def test_empty_crontab(self, capsys: pytest.CaptureFixture[str]) -> None:
        fake = FakeCrontab("")
        with patch.object(crontab_manager.subprocess, "run", fake.run):
            result = crontab_manager.cmd_list(_args())
        assert result == 0
        assert "empty" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# cmd_backup
# ---------------------------------------------------------------------------


class TestCmdBackup:
    def test_creates_backup(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        fake = FakeCrontab(SAMPLE_CRONTAB)
        with (
            patch.object(crontab_manager.subprocess, "run", fake.run),
            patch.object(crontab_manager, "BACKUP_DIR", tmp_path),
        ):
            result = crontab_manager.cmd_backup(_args())
        assert result == 0
        backups = list(tmp_path.glob("crontab-*.txt"))
        assert len(backups) == 1
        assert SAMPLE_CRONTAB in backups[0].read_text()


# ---------------------------------------------------------------------------
# cmd_add
# ---------------------------------------------------------------------------


class TestCmdAdd:
    def test_adds_entry(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        fake = FakeCrontab(SAMPLE_CRONTAB)
        with (
            patch.object(crontab_manager.subprocess, "run", fake.run),
            patch.object(crontab_manager, "BACKUP_DIR", tmp_path),
        ):
            result = crontab_manager.cmd_add(
                _args(
                    tag="test-job",
                    schedule="23 6 * * *",
                    command="/path/to/test.sh",
                )
            )
        assert result == 0
        assert "test-job" in fake.content
        assert "23 6 * * *" in fake.content

    def test_rejects_duplicate_tag(self, capsys: pytest.CaptureFixture[str]) -> None:
        fake = FakeCrontab(SAMPLE_CRONTAB)
        with patch.object(crontab_manager.subprocess, "run", fake.run):
            result = crontab_manager.cmd_add(
                _args(
                    tag="reddit-automod",
                    schedule="0 3 * * *",
                    command="/path/to/dupe.sh",
                )
            )
        assert result == 1
        assert "already exists" in capsys.readouterr().err

    def test_rejects_bad_schedule(self, capsys: pytest.CaptureFixture[str]) -> None:
        fake = FakeCrontab("")
        with patch.object(crontab_manager.subprocess, "run", fake.run):
            result = crontab_manager.cmd_add(
                _args(
                    tag="bad",
                    schedule="every 5 minutes",
                    command="/path/to/bad.sh",
                )
            )
        assert result == 1
        assert "5 fields" in capsys.readouterr().err

    def test_dry_run(self, capsys: pytest.CaptureFixture[str]) -> None:
        fake = FakeCrontab("")
        with patch.object(crontab_manager.subprocess, "run", fake.run):
            result = crontab_manager.cmd_add(
                _args(
                    tag="dry-test",
                    schedule="0 3 * * *",
                    command="/path/to/test.sh",
                    dry_run=True,
                )
            )
        assert result == 0
        assert fake.installed is None  # nothing actually installed
        assert "DRY RUN" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# cmd_remove
# ---------------------------------------------------------------------------


class TestCmdRemove:
    def test_removes_entry(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        fake = FakeCrontab(SAMPLE_CRONTAB)
        with (
            patch.object(crontab_manager.subprocess, "run", fake.run),
            patch.object(crontab_manager, "BACKUP_DIR", tmp_path),
        ):
            result = crontab_manager.cmd_remove(_args(tag="reddit-automod"))
        assert result == 0
        assert "reddit-automod" not in fake.content

    def test_remove_nonexistent(self, capsys: pytest.CaptureFixture[str]) -> None:
        fake = FakeCrontab(SAMPLE_CRONTAB)
        with patch.object(crontab_manager.subprocess, "run", fake.run):
            result = crontab_manager.cmd_remove(_args(tag="nonexistent"))
        assert result == 1


# ---------------------------------------------------------------------------
# cmd_verify
# ---------------------------------------------------------------------------


class TestCmdVerify:
    def test_verify_missing_tag(self, capsys: pytest.CaptureFixture[str]) -> None:
        fake = FakeCrontab(SAMPLE_CRONTAB)
        with patch.object(crontab_manager.subprocess, "run", fake.run):
            result = crontab_manager.cmd_verify(_args(tag="nonexistent"))
        assert result == 1
        assert "not found" in capsys.readouterr().out

    def test_verify_existing_with_script(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        # Create a fake script
        script = tmp_path / "test-cron.sh"
        script.write_text("#!/bin/bash\nflock stuff\nLOG_DIR=x\nmkdir -p $LOG_DIR\n")
        script.chmod(0o755)

        crontab_content = f"# claude-cron: test-job\n0 3 * * * {script} --execute\n"
        fake = FakeCrontab(crontab_content)
        with patch.object(crontab_manager.subprocess, "run", fake.run):
            result = crontab_manager.cmd_verify(_args(tag="test-job"))
        assert result == 0
        output = capsys.readouterr().out
        assert "[PASS]" in output


# ---------------------------------------------------------------------------
# cmd_generate_wrapper
# ---------------------------------------------------------------------------


class TestGenerateWrapper:
    def test_generates_script(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        fake = FakeCrontab("")
        with patch.object(crontab_manager.subprocess, "run", fake.run):
            result = crontab_manager.cmd_generate_wrapper(
                _args(
                    name="test-job",
                    prompt="Do the thing",
                    schedule="7 */6 * * *",
                    workdir=str(tmp_path),
                    budget="1.50",
                    allowed_tools="Bash Read",
                    logdir=str(tmp_path / "logs"),
                    output_dir=str(tmp_path / "scripts"),
                    force=False,
                )
            )
        assert result == 0
        script = tmp_path / "scripts" / "test-job-cron.sh"
        assert script.exists()
        assert os.access(script, os.X_OK)
        content = script.read_text()
        assert "flock" in content
        assert "Do the thing" in content
        assert "1.50" in content
        assert "claude-cron-test-job" in content  # lockfile name

    def test_refuses_overwrite(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        out_dir = tmp_path / "scripts"
        out_dir.mkdir()
        (out_dir / "exist-cron.sh").write_text("existing")

        fake = FakeCrontab("")
        with patch.object(crontab_manager.subprocess, "run", fake.run):
            result = crontab_manager.cmd_generate_wrapper(
                _args(
                    name="exist",
                    prompt="x",
                    schedule="0 0 * * *",
                    workdir=str(tmp_path),
                    budget="2.00",
                    allowed_tools="Bash Read",
                    logdir=None,
                    output_dir=str(out_dir),
                    force=False,
                )
            )
        assert result == 1

    def test_force_overwrite(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        out_dir = tmp_path / "scripts"
        out_dir.mkdir()
        (out_dir / "exist-cron.sh").write_text("existing")

        fake = FakeCrontab("")
        with patch.object(crontab_manager.subprocess, "run", fake.run):
            result = crontab_manager.cmd_generate_wrapper(
                _args(
                    name="exist",
                    prompt="new prompt",
                    schedule="0 0 * * *",
                    workdir=str(tmp_path),
                    budget="2.00",
                    allowed_tools="Bash Read",
                    logdir=None,
                    output_dir=str(out_dir),
                    force=True,
                )
            )
        assert result == 0
        assert "new prompt" in (out_dir / "exist-cron.sh").read_text()
