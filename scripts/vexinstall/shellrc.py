"""One managed block in a shell startup file such as ``~/.bashrc``, for install.sh.

``set`` makes the file hold the block read from stdin, which starts with the BEGIN line and ends
with the END line: a file that already holds exactly that block is not written, an older block is
replaced where it stands (later copies are dropped), and a missing block is appended after a
newline. ``remove`` drops every copy. All other lines keep their bytes and their place, and a
symlinked rc file stays a link (its target is written, mode kept). Before any write the old file
is copied, mode 600 since rc files can export tokens, to ``<backup-dir>/shellrc-<name>.<ts>``;
the newest five are kept. A BEGIN without its END, or the other way round, leaves the file as it
is and exits 1: the ``sed '/BEGIN/,/END/d'`` this replaces deleted every line after such a BEGIN.

Messages name paths and line numbers, never file contents.

Usage: python3 -m vexinstall.shellrc set|remove <rc> <begin> <end> --backup-dir <dir> --label <name>
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

from .common import parse_ts, utc_ts
from .fsops import Guard, atomic_write_bytes

BACKUPS_KEEP = 5


class MarkerError(ValueError):
    """BEGIN and END marker lines that do not pair up."""


def _spans(lines: list[bytes], begin: bytes, end: bytes) -> list[tuple[int, int]]:
    """(first, past-last) line index of each BEGIN..END block; raises MarkerError when unbalanced."""
    spans: list[tuple[int, int]] = []
    start: int | None = None
    for i, line in enumerate(lines):
        text = line.rstrip(b"\r\n")
        if text == begin:
            if start is not None:
                raise MarkerError(
                    f"line {i + 1}: a second BEGIN marker inside the block that starts at line {start + 1}"
                )
            start = i
        elif text == end:
            if start is None:
                raise MarkerError(f"line {i + 1}: an END marker with no BEGIN marker before it")
            spans.append((start, i + 1))
            start = None
    if start is not None:
        raise MarkerError(f"line {start + 1}: a BEGIN marker with no END marker after it")
    return spans


def updated(data: bytes, block: bytes | None, begin: bytes, end: bytes) -> bytes:
    """*data* holding *block* once, where the first old block stood (else appended); None removes it."""
    lines = data.splitlines(keepends=True)
    out: list[bytes] = []
    pos = 0
    for start, stop in _spans(lines, begin, end):
        out.extend(lines[pos:start])
        if block is not None:
            out.append(block)
            block = None
        pos = stop
    out.extend(lines[pos:])
    if block is not None:
        if out and not out[-1].endswith(b"\n"):
            out.append(b"\n")
        out.append(block)
    return b"".join(out)


def _backup(rc: Path, data: bytes, backup_dir: Path, guard: Guard) -> Path:
    stem = "shellrc-" + rc.name.lstrip(".")
    dest = backup_dir / f"{stem}.{utc_ts()}"
    atomic_write_bytes(dest, data, guard, mode=0o600)
    olds = sorted(
        p for p in backup_dir.iterdir() if p.name.startswith(stem + ".") and parse_ts(p.name[len(stem) + 1 :])
    )
    for old in olds[:-BACKUPS_KEEP]:
        old.unlink()
    return dest


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns the exit code."""
    p = argparse.ArgumentParser(prog="vexinstall.shellrc", description="keep one managed block in a shell rc file")
    p.add_argument("action", choices=("set", "remove"))
    p.add_argument("rc", type=Path)
    p.add_argument("begin")
    p.add_argument("end")
    p.add_argument("--backup-dir", type=Path, required=True)
    p.add_argument("--label", default="shellrc")
    ns = p.parse_args(argv)
    begin, end, rc, label = ns.begin.encode(), ns.end.encode(), ns.rc, ns.label
    block: bytes | None = None
    if ns.action == "set":
        block = sys.stdin.buffer.read()
        if not block.endswith(b"\n"):
            block += b"\n"
        inner = block.splitlines()
        if len(inner) < 2 or inner[0] != begin or inner[-1] != end or begin in inner[1:-1] or end in inner[1:-1]:
            print(f"{label}: the block must start with its BEGIN line and end with its END line", file=sys.stderr)
            return 2
    target = Path(os.path.realpath(rc))  # write through a symlinked rc file, so the link stays
    try:
        current = target.read_bytes()
        mode = stat.S_IMODE(target.stat().st_mode)
        existed = True
    except FileNotFoundError:
        umask = os.umask(0o022)
        os.umask(umask)
        current, mode, existed = b"", 0o666 & ~umask, False  # what `cat >>` gave a new file
    except OSError as exc:
        print(f"{label}: {rc} left unchanged: cannot read it ({exc.strerror or exc})", file=sys.stderr)
        return 1
    try:
        had_block = bool(_spans(current.splitlines(keepends=True), begin, end))
        new = updated(current, block, begin, end)
    except MarkerError as exc:
        print(f"{label}: {rc} left unchanged: {exc}; fix the marker lines, then rerun", file=sys.stderr)
        return 1
    if new == current:
        print(f"  {label}: {rc} already {'holds the current block' if block is not None else 'has no block'}")
        return 0
    if not existed and not target.parent.is_dir():  # a dangling link into a missing dir: never create dirs
        print(f"{label}: {rc} left unchanged: {target.parent} does not exist", file=sys.stderr)
        return 1
    guard = Guard()
    try:
        saved = _backup(rc, current, ns.backup_dir, guard) if existed else None
        atomic_write_bytes(target, new, guard, mode=mode)
    except OSError as exc:
        print(f"{label}: {rc} left unchanged: cannot write ({exc.strerror or exc})", file=sys.stderr)
        return 1
    did = "removed the block from" if block is None else ("updated the block in" if had_block else "added the block to")
    print(f"  {label}: {did} {rc}" + (f" (old copy: {saved})" if saved else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
