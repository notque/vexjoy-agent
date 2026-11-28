"""Shared shell and Windows cmd.exe argument quoting helpers."""

from __future__ import annotations

import re
import shlex

_CMD_SAFE = re.compile(r"[A-Za-z0-9_.\-]+")
_CMD_UNQUOTABLE = re.compile(r'["%!\r\n]')


def quote_cmd(val: str, *, windows: bool = True) -> str:
    """Quote *val* for cmd.exe on Windows or POSIX shells otherwise.

    shlex.quote targets POSIX shells. cmd.exe does not treat single quotes as
    quotes, so its output reaches python with the quote characters inside the
    path, and a ``|`` in a matcher such as ``edit_file|write_file`` becomes a
    pipe. Double quotes protect spaces and ``& | < > ^ ( )``, but cmd.exe still
    expands ``%VAR%`` inside them, and ``!VAR!`` too when delayed expansion is
    on (a registry setting this generator cannot see). A literal ``"`` would
    need ``^`` escaping that depends on how the caller launches cmd.exe. Values
    holding any of these are refused rather than written as a command that
    could silently run something else.
    """
    if not windows:
        return shlex.quote(val)
    if _CMD_SAFE.fullmatch(val):
        return val
    if _CMD_UNQUOTABLE.search(val):
        raise ValueError(f"Cannot quote {val!r} for cmd.exe: it contains a double quote, %, ! or a line break.")
    # The C runtime argv parser reads backslashes before the closing quote as escapes.
    trailing = len(val) - len(val.rstrip("\\"))
    return '"' + val + "\\" * trailing + '"'
