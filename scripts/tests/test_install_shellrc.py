"""install.sh's no-agent-summary block in ~/.bashrc (lane C, C-08).

The block went in with ``sed -i '/BEGIN/,/END/d'`` plus an append on every install. That rewrote
the file each run and moved the block to the end, replaced a symlinked ~/.bashrc with a plain
file, glued BEGIN onto a last line without a newline, kept no backup, and with a BEGIN whose END
was gone deleted every line after it. The block itself must stay byte for byte what it was.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vexinstall import shellrc

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"
BEGIN = "# >>> no-agent-summary >>>"
END = "# <<< no-agent-summary <<<"
CANARY = "export VEXJOY_TEST_CANARY=canary-line\n"

if shutil.which("bash") is None:
    pytest.skip("bash not available", allow_module_level=True)


def _block(home: Path, source: Path = REPO_ROOT) -> str:
    """The block install.sh has always written, for a checkout at *source*."""
    hook = home / ".local" / "share" / "no-agent-summary" / "no-agent-summary.js"
    return (
        f"{BEGIN}\n"
        "# Bun preload that stops Claude Code's agent_summary side-query (status-line labels\n"
        "# for background agents, each a full-transcript model call every 30 s).\n"
        f"# Installed from: {source}\n"
        'case " ${BUN_OPTIONS-} " in\n'
        f'  *" --preload={hook} "*) ;;\n'
        f'  *) export BUN_OPTIONS="${{BUN_OPTIONS:+$BUN_OPTIONS }}--preload={hook}" ;;\n'
        "esac\n"
        f"{END}\n"
    )


def _run(home: Path, func: str) -> subprocess.CompletedProcess[str]:
    """Run one of install.sh's no-agent-summary functions against the temp *home*."""
    parts = (
        "/^NAS_DEST=/,/^NAS_RC=/p",
        "/^nas_block() {/,/^}/p",
        "/^nas_shellrc() {/,/^}/p",
        "/^install_no_agent_summary() {/,/^}/p",
        "/^uninstall_no_agent_summary() {/,/^}/p",
    )
    code = subprocess.run(
        ["sed", "-n", ";".join(parts), str(INSTALL_SH)], capture_output=True, text=True, check=True
    ).stdout
    body = (
        "set -euo pipefail\n"
        f'GREEN=""; YELLOW=""; NC=""; SCRIPT_DIR="{REPO_ROOT}"; STATE_DIR="{home}/.claude/vexjoy"\n'
        f'PYTHON_CMD="{sys.executable}"\n{code}\n{func}\n'
    )
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    return subprocess.run(["bash", "-c", body], capture_output=True, text=True, env=env, timeout=60)


@pytest.fixture
def home(tmp_path: Path) -> Path:
    h = tmp_path / "home"
    h.mkdir()
    return h


def _backups(home: Path) -> list[Path]:
    d = home / ".claude" / "vexjoy" / "backups"
    return sorted(d.glob("shellrc-bashrc.*")) if d.is_dir() else []


def _ok(res: subprocess.CompletedProcess[str]) -> None:
    assert res.returncode == 0, res.stdout + res.stderr


def test_block_is_unchanged_and_a_second_install_writes_nothing(home: Path) -> None:
    rc = home / ".bashrc"
    _ok(_run(home, "install_no_agent_summary"))
    assert rc.read_text() == _block(home)
    first = rc.stat()
    _ok(_run(home, "install_no_agent_summary"))
    assert rc.read_text() == _block(home)
    assert (rc.stat().st_ino, rc.stat().st_mtime_ns) == (first.st_ino, first.st_mtime_ns)
    assert _backups(home) == [], "nothing changed, so nothing was backed up"


def test_other_lines_keep_their_bytes_and_place(home: Path) -> None:
    rc = home / ".bashrc"
    old = _block(home, Path("/old/checkout"))
    original = "export A=1\n" + old + CANARY
    rc.write_text(original)
    rc.chmod(0o640)
    res = _run(home, "install_no_agent_summary")
    _ok(res)
    assert rc.read_text() == "export A=1\n" + _block(home) + CANARY
    assert stat.S_IMODE(rc.stat().st_mode) == 0o640
    (backup,) = _backups(home)
    assert backup.read_text() == original
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600, "an rc file can hold exported tokens"
    assert "canary-line" not in res.stdout + res.stderr


def test_a_symlinked_rc_stays_a_link(home: Path) -> None:
    dotfiles = home / "dotfiles"
    dotfiles.mkdir()
    (dotfiles / "bashrc").write_text(CANARY + _block(home, Path("/old/checkout")))
    rc = home / ".bashrc"
    rc.symlink_to(dotfiles / "bashrc")
    _ok(_run(home, "install_no_agent_summary"))
    assert rc.is_symlink()
    assert (dotfiles / "bashrc").read_text() == CANARY + _block(home)


def test_a_begin_without_its_end_leaves_the_file_alone(home: Path) -> None:
    rc = home / ".bashrc"
    original = f"export A=1\n{BEGIN}\n{CANARY}alias b=c\n"
    rc.write_text(original)
    res = _run(home, "install_no_agent_summary")
    _ok(res)  # the install goes on; only the rc file is left as it was
    assert rc.read_text() == original
    assert "line 2" in res.stderr and "canary-line" not in res.stdout + res.stderr
    assert _backups(home) == []


def test_a_last_line_without_a_newline_is_not_joined(home: Path) -> None:
    rc = home / ".bashrc"
    rc.write_text("alias x=y")
    _ok(_run(home, "install_no_agent_summary"))
    assert rc.read_text() == "alias x=y\n" + _block(home)


def test_uninstall_removes_only_the_block(home: Path) -> None:
    rc = home / ".bashrc"
    rc.write_text("export A=1\n" + _block(home) + CANARY)
    _ok(_run(home, "uninstall_no_agent_summary"))
    assert rc.read_text() == "export A=1\n" + CANARY
    assert len(_backups(home)) == 1
    first = rc.stat()
    _ok(_run(home, "uninstall_no_agent_summary"))
    assert rc.stat().st_ino == first.st_ino


def test_uninstall_with_a_begin_without_its_end_leaves_the_file_alone(home: Path) -> None:
    rc = home / ".bashrc"
    original = f"{BEGIN}\n{CANARY}"
    rc.write_text(original)
    _ok(_run(home, "uninstall_no_agent_summary"))
    assert rc.read_text() == original


# --- shellrc.updated: the edit itself ------------------------------------------------------------

B, E = BEGIN.encode(), END.encode()
BLOCK = B + b"\nnew\n" + E + b"\n"


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (b"", BLOCK),
        (b"a\n", b"a\n" + BLOCK),
        (b"a\n" + B + b"\nold\n" + E + b"\nz\n", b"a\n" + BLOCK + b"z\n"),
        (b"a\n" + B + b"\nold\n" + E, b"a\n" + BLOCK),
        (B + b"\r\nold\r\n" + E + b"\r\nz\r\n", BLOCK + b"z\r\n"),
        (B + b"\n1\n" + E + b"\nm\n" + B + b"\n2\n" + E + b"\n", BLOCK + b"m\n"),
    ],
    ids=["empty", "append", "in-place", "end-at-eof", "crlf", "duplicates"],
)
def test_set(before: bytes, after: bytes) -> None:
    assert shellrc.updated(before, BLOCK, B, E) == after
    assert shellrc.updated(after, BLOCK, B, E) == after


def test_remove() -> None:
    assert shellrc.updated(b"a\n" + BLOCK + b"z\n", None, B, E) == b"a\nz\n"
    assert shellrc.updated(b"a\n", None, B, E) == b"a\n"


@pytest.mark.parametrize(
    ("text", "line"),
    [(b"a\n" + B + b"\nx\n", 2), (E + b"\n", 1), (B + b"\n" + B + b"\n" + E + b"\n", 2)],
    ids=["begin-only", "end-only", "two-begins"],
)
def test_unbalanced_markers_refuse(text: bytes, line: int) -> None:
    with pytest.raises(shellrc.MarkerError, match=f"line {line}"):
        shellrc.updated(text, BLOCK, B, E)


def test_a_block_without_its_markers_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rc = tmp_path / ".bashrc"
    rc.write_text("a\n")
    monkeypatch.setattr(sys, "stdin", type("S", (), {"buffer": __import__("io").BytesIO(b"no markers\n")})())
    argv = ["set", str(rc), BEGIN, END, "--backup-dir", str(tmp_path / "b"), "--label", "t"]
    assert shellrc.main(argv) == 2
    assert rc.read_text() == "a\n"


def test_a_new_rc_gets_the_umask_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rc = tmp_path / ".bashrc"
    monkeypatch.setattr(sys, "stdin", type("S", (), {"buffer": __import__("io").BytesIO(BLOCK)})())
    old = os.umask(0o077)
    try:
        assert shellrc.main(["set", str(rc), BEGIN, END, "--backup-dir", str(tmp_path / "b"), "--label", "t"]) == 0
    finally:
        os.umask(old)
    assert rc.read_bytes() == BLOCK and stat.S_IMODE(rc.stat().st_mode) == 0o600


def test_a_link_into_a_missing_dir_creates_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rc = tmp_path / ".bashrc"
    rc.symlink_to(tmp_path / "gone" / "bashrc")
    monkeypatch.setattr(sys, "stdin", type("S", (), {"buffer": __import__("io").BytesIO(BLOCK)})())
    assert shellrc.main(["set", str(rc), BEGIN, END, "--backup-dir", str(tmp_path / "b"), "--label", "t"]) == 1
    assert not (tmp_path / "gone").exists() and rc.is_symlink()


def test_backups_keep_the_newest_five(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rc = tmp_path / ".bashrc"
    stamps = iter(f"2026010{i}T000000000000Z" for i in range(1, 8))
    monkeypatch.setattr(shellrc, "utc_ts", lambda: next(stamps))
    for i in range(7):
        rc.write_text(f"v{i}\n")
        monkeypatch.setattr(sys, "stdin", type("S", (), {"buffer": __import__("io").BytesIO(BLOCK)})())
        assert shellrc.main(["set", str(rc), BEGIN, END, "--backup-dir", str(tmp_path / "b"), "--label", "t"]) == 0
    kept = sorted(p.name for p in (tmp_path / "b").iterdir())
    assert kept == [f"shellrc-bashrc.2026010{i}T000000000000Z" for i in range(3, 8)]
    assert os.path.exists(rc)
