#!/usr/bin/env python3
"""StopFailure hook: record session failure for pattern analysis.

Fires when a session ends due to an API error. Appends a failure record
to ~/.claude/state/session-failures.jsonl for later analysis.
"""

import sys  # vexjoy-pyguard

if sys.version_info < (3, 10):  # vexjoy-pyguard advisory
    import os

    if not os.environ.get("VEXJOY_PYGUARD_REEXEC"):
        os.environ["VEXJOY_PYGUARD_REEXEC"] = "1"
        for _d in [*os.environ.get("PATH", "").split(os.pathsep), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
            for _v in ("14", "13", "12", "11", "10"):
                _p = os.path.join(_d, "python3." + _v)
                if _d and "/shims" not in _d and os.access(_p, os.X_OK):
                    os.execv(_p, [_p, *sys.argv])
    sys.stderr.write(
        "[vexjoy] hook %s needs Python 3.10+, got %s (%s); run ./install.sh in vexjoy-agent from a terminal"
        " outside Claude Code (gated tool calls stay blocked until then)\n"
        % (__file__.rsplit("/", 1)[-1], sys.version.split()[0], sys.executable)
    )
    sys.exit(0)

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_BYPASS_ENV = "STOP_FAILURE_HANDLER_BYPASS"


def main():
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print("[stop-failure-handler] Bypassed via STOP_FAILURE_HANDLER_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    try:
        state_dir = Path.home() / ".claude" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "stop_failure",
            "cwd": os.getcwd(),
        }

        failures_file = state_dir / "session-failures.jsonl"
        with open(failures_file, "a") as f:
            f.write(json.dumps(record) + "\n")

    except Exception:
        pass  # Hook must never fail itself

    sys.exit(0)


if __name__ == "__main__":
    main()
