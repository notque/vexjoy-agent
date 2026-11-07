"""Hosts that refuse symlinks (Windows without Developer Mode) get a script pin instead of a link."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from scripts.tests.vexinstall_support import Env, world

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vexinstall import interp
from vexinstall.fsops import Guard

FIX = "rerun ./install.sh"


def _refused(winerror: int) -> OSError:
    """An OSError carrying *winerror* on every platform (the attribute is real only on Windows)."""
    return type("Refused", (OSError,), {"winerror": winerror})(winerror, "symlink refused")


def _deny_symlinks(monkeypatch: pytest.MonkeyPatch, exc: BaseException) -> None:
    def refuse(*_a: object, **_k: object) -> None:
        raise exc

    monkeypatch.setattr(os, "symlink", refuse)


def _real() -> interp.Interpreter:
    path = sys.executable
    info = interp.probe_info(path)
    assert info is not None
    return interp.Interpreter(path, info[0])


def _posix(path: str) -> str:
    return path.replace("\\", "/")


def _can_symlink(tmp: Path) -> bool:
    try:
        os.symlink(sys.executable, tmp / "probe-link")
    except (OSError, NotImplementedError):
        return False
    return True


def _write_pin(home: Path, body: bytes | str) -> Path:
    link = interp.link_path(home)
    link.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(body, str):
        body = body.encode()
    link.write_bytes(body)
    link.chmod(0o755)
    return link


@pytest.mark.parametrize(
    "make",
    [lambda: _refused(1314), lambda: _refused(50), lambda: NotImplementedError("no symlinks")],
    ids=["winerror-1314", "winerror-50", "not-implemented"],
)
def test_refused_symlink_writes_a_script_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make: Callable[[], BaseException]
) -> None:
    _deny_symlinks(monkeypatch, make())
    me = _real()
    assert interp.write_link(tmp_path, me, Guard()) is True
    link = interp.link_path(tmp_path)
    assert not os.path.islink(link)
    assert link.read_bytes() == interp.pin_script_bytes(me.path)
    assert interp.read_pin(link) == interp.Pin("script", _posix(me.path))
    assert interp.link_ok(tmp_path)
    assert interp.link_blocker(tmp_path) is None
    assert interp.drift(tmp_path) == []
    if os.name != "nt":
        assert os.stat(link).st_mode & 0o777 == 0o755
    assert [p.name for p in link.parent.iterdir()] == ["python3"]


@pytest.mark.parametrize(
    "make", [lambda: _refused(5), lambda: PermissionError(13, "denied")], ids=["winerror-5", "eacces"]
)
def test_other_symlink_errors_propagate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make: Callable[[], BaseException]
) -> None:
    exc = make()
    _deny_symlinks(monkeypatch, exc)
    with pytest.raises(type(exc)):
        interp.write_link(tmp_path, _real(), Guard())
    assert not os.path.lexists(interp.link_path(tmp_path))


@pytest.mark.parametrize(
    ("path", "posix"),
    [
        ("C:\\Python313\\python.exe", "C:/Python313/python.exe"),
        ("C:\\Program Files\\Python312\\python.exe", "C:/Program Files/Python312/python.exe"),
        ("C:\\Users\\O'Brien\\python.exe", "C:/Users/O'Brien/python.exe"),
        ("/usr/bin/python3", "/usr/bin/python3"),
    ],
)
def test_script_pin_names_and_execs_its_interpreter(tmp_path: Path, path: str, posix: str) -> None:
    body = interp.pin_script_bytes(path)
    lines = body.decode().split("\n")
    assert lines[:3] == ["#!/bin/sh", interp.PIN_SCRIPT_MARK, interp.PIN_SCRIPT_TARGET + posix]
    assert shlex.split(lines[3]) == ["exec", posix, "$@"]
    assert lines[4:] == [""] and b"\r" not in body
    assert interp.read_pin(_write_pin(tmp_path, body)) == interp.Pin("script", posix)


@pytest.mark.skipif(os.name == "nt", reason="Windows cannot exec an sh script from python")
def test_script_pin_runs_its_interpreter_with_arguments_intact(tmp_path: Path) -> None:
    link = _write_pin(tmp_path, interp.pin_script_bytes(sys.executable))
    code = "import sys; print(sys.argv[1:])"
    proc = subprocess.run([str(link), "-c", code, "a b", "c'd"], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "['a b', \"c'd\"]\n"


def test_script_pin_is_rewritten_only_when_it_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _deny_symlinks(monkeypatch, _refused(1314))
    me = _real()
    link = interp.link_path(tmp_path)
    assert interp.write_link(tmp_path, me, Guard()) is True
    assert interp.write_link(tmp_path, me, Guard()) is False
    other = interp.Interpreter(me.path + "x", me.version)
    assert interp.write_link(tmp_path, other, Guard()) is True
    assert link.read_bytes() == interp.pin_script_bytes(other.path)
    # A script pin without the target line (an earlier format) is upgraded in place.
    _write_pin(tmp_path, f'#!/bin/sh\n{interp.PIN_SCRIPT_MARK}\nexec {shlex.quote(_posix(me.path))} "$@"\n')
    assert interp.read_pin(link) == interp.Pin("script", None)
    assert interp.write_link(tmp_path, me, Guard()) is True
    assert link.read_bytes() == interp.pin_script_bytes(me.path)


def test_symlink_pin_becomes_a_script_pin_when_symlinks_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not _can_symlink(tmp_path):
        pytest.skip("host cannot create symlinks")
    me = _real()
    link = interp.link_path(tmp_path)
    assert interp.write_link(tmp_path, me, Guard()) is True
    assert interp.read_pin(link) == interp.Pin("link", me.path)
    same = os.path.join(os.path.dirname(me.path), ".", os.path.basename(me.path))
    assert interp.write_link(tmp_path, interp.Interpreter(same, me.version), Guard()) is False
    _deny_symlinks(monkeypatch, _refused(1314))
    other = interp.Interpreter(me.path + "x", me.version)
    assert interp.write_link(tmp_path, other, Guard()) is True
    assert interp.read_pin(link) == interp.Pin("script", _posix(other.path))


def test_foreign_regular_file_is_refused_not_adopted(tmp_path: Path) -> None:
    link = _write_pin(tmp_path, '#!/bin/sh\nexec python3 "$@"\n')
    assert interp.read_pin(link) == interp.Pin("foreign")
    blocker = interp.link_blocker(tmp_path)
    assert blocker is not None
    assert "is a regular file, not a symlink" in blocker and interp.PIN_SCRIPT_MARK in blocker
    assert interp.drift(tmp_path) == [
        ("python-pin-not-link", f"expected a symlink or a vexjoy script pin to python 3.10+; {FIX}")
    ]
    assert not interp.link_ok(tmp_path)


def test_script_pin_drift_names_the_problem(tmp_path: Path) -> None:
    gone = str(tmp_path / "gone" / "python3")
    link = _write_pin(tmp_path, interp.pin_script_bytes(gone))
    assert interp.drift(tmp_path) == [
        ("python-pin-dangling", f"{_posix(gone)} is gone; hooks fall back to bare python3; {FIX}")
    ]
    unreadable = [("python-pin-broken", f"script pin {link} has no readable target line; {FIX}")]
    _write_pin(tmp_path, f"#!/bin/sh\n{interp.PIN_SCRIPT_MARK}\n")
    assert interp.drift(tmp_path) == unreadable
    # CRLF: pyrun.sh keeps the carriage return and cannot use the target, so the engine must not either.
    _write_pin(tmp_path, interp.pin_script_bytes(sys.executable).replace(b"\n", b"\r\n"))
    assert interp.read_pin(link) == interp.Pin("script", None)
    assert interp.drift(tmp_path) == unreadable
    assert not interp.link_ok(tmp_path)
    _write_pin(tmp_path, f"#!/bin/sh\n{interp.PIN_SCRIPT_MARK}\n{interp.PIN_SCRIPT_TARGET}bin/python3\n")
    assert interp.drift(tmp_path) == [
        ("python-pin-broken", f"script pin {link} names a relative interpreter 'bin/python3'; {FIX}")
    ]
    assert not interp.link_ok(tmp_path)


@pytest.mark.skipif(os.name == "nt", reason="the fake interpreter is an sh script")
def test_script_pin_to_an_old_python_is_reported(tmp_path: Path) -> None:
    old = tmp_path / "old" / "python3"
    old.parent.mkdir()
    old.write_text("#!/bin/sh\necho 3.9 0\n")
    old.chmod(0o755)
    _write_pin(tmp_path, interp.pin_script_bytes(str(old)))
    assert interp.drift(tmp_path) == [("python-pin-old", f"{old} is 3.9, need 3.10+; {FIX}")]
    assert not interp.link_ok(tmp_path)


def test_missing_modules_probes_the_script_pin_interpreter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Doctor's dependency probe runs the named interpreter; Windows cannot exec an sh script directly."""
    _write_pin(tmp_path, interp.pin_script_bytes(sys.executable))
    argv0: list[str] = []
    real_run = subprocess.run

    def spy(argv: list[str], *a: Any, **k: Any) -> subprocess.CompletedProcess[str]:
        argv0.append(argv[0])
        return real_run(argv, *a, **k)

    monkeypatch.setattr(interp.subprocess, "run", spy)
    assert interp.missing_modules(tmp_path, ("json", "vexjoy_no_such_module")) == ["vexjoy_no_such_module"]
    assert argv0 == [_posix(sys.executable)]
    _write_pin(tmp_path, f"#!/bin/sh\n{interp.PIN_SCRIPT_MARK}\n")
    assert interp.missing_modules(tmp_path) == []
    assert len(argv0) == 1


def test_apply_doctor_sync_uninstall_with_a_script_pin(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the python pin loses symlinks; every other install path keeps the host's real os.symlink.

    A host that refuses symlinks installs everything else in copy mode.
    """
    real = os.symlink

    def refuse_pin(src: object, dst: object, *a: object, **k: object) -> None:
        if os.path.basename(str(dst)).startswith(".python3.vexinstall-"):
            raise _refused(1314)
        real(src, dst, *a, **k)

    monkeypatch.setattr(os, "symlink", refuse_pin)
    res = world.run("apply", "--target", "claude")
    assert res.code == 0, res.err
    link = interp.link_path(world.home)
    chosen = res.data["python"]["target"].rsplit(" (", 1)[0]
    assert interp.read_pin(link) == interp.Pin("script", _posix(chosen))
    assert res.data["python"]["kind"] == "script"
    assert any(line.endswith("(script pin: this host refuses symlinks)") for line in res.out), res.out
    body = link.read_bytes()
    findings = world.run("doctor", "--target", "claude").data["findings"]
    assert [f for f in findings if f["check"].startswith("python-pin")] == []
    assert world.run("sync", "--target", "claude").code == 0
    assert link.read_bytes() == body
    assert world.run("uninstall", "--target", "claude").code == 0
    assert not os.path.lexists(link)


def test_apply_writes_settings_and_ledger_when_the_pin_cannot_be_written(
    world: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    def locked(*_a: object, **_k: object) -> bool:
        raise PermissionError(13, "pin locked")

    real_write = interp.write_link
    monkeypatch.setattr(interp, "write_link", locked)
    res = world.run("apply", "--target", "claude")
    assert res.code == 1
    assert any("python pin" in line and "pin locked" in line for line in res.err), res.err
    assert res.data["python"]["error"] == "[Errno 13] pin locked"
    assert world.ledger_dests("claude")
    assert json.loads((world.home / ".claude" / "settings.json").read_text())["hooks"]
    # sync never fails: the same error is a warning there.
    monkeypatch.setattr(interp, "write_link", real_write)
    assert world.run("apply", "--target", "claude").code == 0
    interp.link_path(world.home).unlink()
    monkeypatch.setattr(interp, "write_link", locked)
    res = world.run("sync", "--target", "claude")
    assert res.code == 0
    assert any("warning: python pin" in line and "pin locked" in line for line in res.err), res.err
