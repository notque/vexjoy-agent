"""
Shared utility for safe stdin reading with timeout and byte cap.

Prevents hook deadlocks when the parent process pipe hangs (crash, broken IPC)
and bounds memory use on oversized stdin payloads. Uses ``signal.setitimer``
(supporting fractional timeouts) on POSIX and a daemon reader thread on Windows.

ADR: adr/070-prompt-injection-defense-layer.md
"""

from __future__ import annotations

import signal
import sys

DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB
_READ_CHUNK_SIZE = 65536


def _timeout_handler(signum, frame):
    raise TimeoutError("Stdin read timed out")


def _read_bounded(max_bytes: int | None) -> str:
    """Read stdin up to *max_bytes* UTF-8 bytes (or unbounded when None)."""
    if max_bytes is None:
        return sys.stdin.read()
    if max_bytes <= 0:
        return ""
    chunks: list[str] = []
    byte_count = 0
    while byte_count < max_bytes:
        remaining = max_bytes - byte_count
        requested = min(_READ_CHUNK_SIZE, remaining)
        chunk = sys.stdin.read(requested)
        if not chunk:
            break
        encoded = chunk.encode("utf-8", errors="replace")
        if byte_count + len(encoded) > max_bytes:
            allowed = encoded[: max_bytes - byte_count].decode("utf-8", errors="ignore")
            if allowed:
                chunks.append(allowed)
            break
        chunks.append(chunk)
        byte_count += len(encoded)
        if len(chunk) != requested:
            break
    return "".join(chunks)


def read_stdin_optional(timeout: float = 10.0, max_bytes: int | None = DEFAULT_MAX_BYTES) -> str | None:
    """Read stdin with a timeout guard and optional byte cap.

    Returns:
        The stdin content as a string, ``None`` if stdin did not close within
        *timeout* seconds, or ``""`` on OSError.
    """
    if timeout <= 0:
        try:
            return _read_bounded(max_bytes)
        except OSError as e:
            print(f"[stdin-timeout] WARNING: stdin read failed: {e}", file=sys.stderr)
            return ""

    # Check sys.platform without importing platform (it loads subprocess on Python 3.10)
    use_thread = sys.platform == "win32" or not hasattr(signal, "setitimer")
    old_handler = None
    if not use_thread:
        try:
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        except ValueError:
            # signal.signal only works in the main thread; fall back to a daemon reader.
            use_thread = True

    if use_thread:
        import threading

        box: list[str] = []

        def _reader() -> None:
            try:
                box.append(_read_bounded(max_bytes))
            except OSError:
                box.append("")

        thread = threading.Thread(target=_reader, daemon=True)
        thread.start()
        thread.join(timeout=timeout)
        if thread.is_alive():
            return None
        return box[0] if box else ""

    try:
        signal.setitimer(signal.ITIMER_REAL, float(timeout))
        data = _read_bounded(max_bytes)
        signal.setitimer(signal.ITIMER_REAL, 0)
        return data
    except TimeoutError:
        return None
    except OSError as e:
        print(f"[stdin-timeout] WARNING: stdin read failed: {e}", file=sys.stderr)
        return ""
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


def read_stdin(timeout: float = 10, max_bytes: int | None = DEFAULT_MAX_BYTES) -> str:
    """Read all of stdin with a timeout guard and optional byte cap.

    Args:
        timeout: Maximum seconds to wait for stdin (int or float). Default 10.
        max_bytes: Maximum UTF-8 bytes to read (None for unbounded). Default 10 MiB.

    Returns:
        The stdin content as a string, or empty string on timeout/error.
    """
    result = read_stdin_optional(timeout=timeout, max_bytes=max_bytes)
    if result is None:
        print(f"[stdin-timeout] WARNING: stdin read timed out after {timeout}s", file=sys.stderr)
        return ""
    return result
