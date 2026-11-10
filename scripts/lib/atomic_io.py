"""Atomic file-write helper for generated index files."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write *text* to *path* so a reader sees the old file or the new one.

    A temporary file is written in the same directory and renamed over the
    target.  This guarantees that concurrent readers never observe a
    partially-written file.

    Args:
        path: Destination file path.
        text: Content to write.
        encoding: Text encoding (default ``utf-8``).

    Raises:
        OSError: On any I/O failure (including ``PermissionError``).
            The original file, if present, is left untouched.
    """
    fd = -1
    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        os.write(fd, text.encode(encoding))
        os.fsync(fd)
        os.close(fd)
        fd = -1  # mark closed

        # Preserve existing permissions, or apply default (0o666 & ~umask).
        if path.exists():
            mode = path.stat().st_mode & 0o7777
        else:
            mask = os.umask(0)
            os.umask(mask)
            mode = 0o666 & ~mask
        os.chmod(tmp_path, mode)

        os.replace(tmp_path, path)
        tmp_path = None  # rename succeeded; nothing to clean up

        # Touch the file so its mtime is >= the directory mtime that the
        # rename just updated.  Without this, freshness checks that compare
        # the file against its parent directory see the file as older.
        os.utime(path)
    except BaseException:
        if fd >= 0:
            os.close(fd)
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise
