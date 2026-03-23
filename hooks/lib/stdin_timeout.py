"""
Shared utility for safe stdin reading with timeout.

Prevents hook deadlocks when the parent process pipe hangs (crash, broken IPC).
Uses signal.alarm on Unix. Returns empty string on timeout so hooks exit cleanly.

ADR: adr/070-prompt-injection-defense-layer.md
"""

import signal
import sys


def _timeout_handler(signum, frame):
    raise TimeoutError("Stdin read timed out")


def read_stdin(timeout: int = 10) -> str:
    """Read all of stdin with a timeout guard.

    Args:
        timeout: Maximum seconds to wait for stdin. Default 10.

    Returns:
        The stdin content as a string, or empty string on timeout/error.
    """
    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    try:
        signal.alarm(timeout)
        data = sys.stdin.read()
        signal.alarm(0)
        return data
    except TimeoutError:
        print(f"[stdin-timeout] WARNING: stdin read timed out after {timeout}s", file=sys.stderr)
        return ""
    except OSError as e:
        print(f"[stdin-timeout] WARNING: stdin read failed: {e}", file=sys.stderr)
        return ""
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
