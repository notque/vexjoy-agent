#!/usr/bin/env python3
"""
with_server.py — Start a local HTTP server, run a command, then stop the server.

Usage:
    python3 with_server.py [OPTIONS] COMMAND

    COMMAND is executed via the shell after the server is ready.
    Exit code mirrors the command's exit code.

Examples:
    python3 with_server.py "npx playwright test"
    python3 with_server.py --port 8080 --dir dist/ "npx playwright test tests/"
    python3 with_server.py --port 3000 --timeout 30 "python3 tests/run_tests.py"

Options:
    --port      Port to serve on (default: 3000)
    --dir       Directory to serve (default: current directory)
    --timeout   Seconds to wait for server ready (default: 10)
    --host      Host to bind (default: 127.0.0.1)
"""

import argparse
import http.server
import os
import signal
import socket
import subprocess
import sys
import threading
import time


def find_free_port(preferred: int, host: str = "127.0.0.1") -> int:
    """Return `preferred` if available, otherwise find a free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, preferred))
            return preferred
        except OSError:
            # Port in use — find a free one
            s.bind((host, 0))
            return s.getsockname()[1]


def is_port_open(host: str, port: int) -> bool:
    """Return True if the given host:port accepts TCP connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect((host, port))
            return True
        except (ConnectionRefusedError, OSError):
            return False


def wait_for_server(host: str, port: int, timeout: float) -> bool:
    """Poll until the server accepts connections or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_port_open(host, port):
            return True
        time.sleep(0.2)
    return False


class SilentHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with logging suppressed."""

    def log_message(self, fmt, *args):
        pass  # suppress all access log output

    def log_error(self, fmt, *args):
        # Only log actual errors (4xx/5xx), not 200s
        pass


def start_server(host: str, port: int, directory: str) -> http.server.HTTPServer:
    """Start SimpleHTTPServer in a daemon thread and return the server object."""
    os.chdir(directory)
    server = http.server.HTTPServer(
        (host, port),
        SilentHTTPHandler,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main():
    parser = argparse.ArgumentParser(
        description="Start a local HTTP server, run a command, then stop the server.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 with_server.py "npx playwright test"
  python3 with_server.py --port 8080 --dir dist "npx playwright test tests/"
  python3 with_server.py --port 3000 --timeout 30 "python3 -m pytest tests/"
        """,
    )
    parser.add_argument(
        "command",
        help="Shell command to run after server is ready",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=3000,
        help="Port to serve on (default: 3000)",
    )
    parser.add_argument(
        "--dir",
        "-d",
        default=".",
        help="Directory to serve (default: current directory)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Seconds to wait for server to become ready (default: 10)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host/interface to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print server start/stop messages",
    )

    args = parser.parse_args()

    # Resolve serve directory
    serve_dir = os.path.abspath(args.dir)
    if not os.path.isdir(serve_dir):
        print(f"ERROR: Directory not found: {serve_dir}", file=sys.stderr)
        sys.exit(2)

    # Find a usable port
    port = find_free_port(args.port, args.host)
    if port != args.port and args.verbose:
        print(f"[with_server] Port {args.port} in use, using {port}", file=sys.stderr)

    # Start server
    if args.verbose:
        print(f"[with_server] Serving {serve_dir} on http://{args.host}:{port}/", file=sys.stderr)

    server = None
    exit_code = 1

    try:
        server = start_server(args.host, port, serve_dir)

        # Wait for server to be ready
        if not wait_for_server(args.host, port, args.timeout):
            print(
                f"ERROR: Server did not become ready on {args.host}:{port} within {args.timeout}s",
                file=sys.stderr,
            )
            sys.exit(2)

        if args.verbose:
            print(f"[with_server] Server ready. Running: {args.command}", file=sys.stderr)

        # Set SERVER_PORT env var so the command can use it
        env = os.environ.copy()
        env["SERVER_PORT"] = str(port)
        env["SERVER_HOST"] = args.host
        env["SERVER_URL"] = f"http://{args.host}:{port}"

        # Run the command
        result = subprocess.run(
            args.command,
            shell=True,
            env=env,
        )
        exit_code = result.returncode

    except KeyboardInterrupt:
        print("\n[with_server] Interrupted", file=sys.stderr)
        exit_code = 130  # SIGINT convention

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        exit_code = 2

    finally:
        if server is not None:
            server.shutdown()
            if args.verbose:
                print("[with_server] Server stopped", file=sys.stderr)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
