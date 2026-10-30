#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SessionStart Hook: No-Agent-Summary Preload Check

Warns INSIDE the session when the agent_summary preload is not loaded or the
Claude Code build no longer contains the suppression anchors. The preload's own
stderr warning is drawn over by Claude Code's full-screen UI, so this hook is
the channel that is actually seen.

Silent when all is well. Two failure modes, both read from the preload's state
directory:
  - This session did not load the preload (no pid marker; e.g. started from a
    shell or app without BUN_OPTIONS).
  - It loaded, but this build no longer contains the strings it matches on.

Ported from check.sh (MIT, declanbx, https://gist.github.com/declanbx/c4511b8642c9d7179ab5761ff6473871)
to follow the vexinstall Python+pyguard hook convention.
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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

EVENT = "SessionStart"


def main() -> None:
    state_dir = os.environ.get(
        "CC_AGENT_SUMMARY_STATE",
        os.path.join(
            os.environ.get("XDG_STATE_HOME", os.path.join(os.environ.get("HOME", ""), ".local", "state")),
            "no-agent-summary",
        ),
    )

    # The Claude Code process that runs this hook.
    pid = os.environ.get("CLAUDE_PID") or str(os.getppid())
    marker = os.path.join(state_dir, "pids", pid)

    if not os.path.exists(marker):
        _say(
            "NOT loaded in this session, so background-agent summaries are running. "
            "Start Claude from a new terminal (the shell setup adds BUN_OPTIONS)."
        )
        return

    # Read the exe path from the marker and check the static verdict.
    try:
        exe = open(marker, "r").readline().strip()
    except OSError:
        return  # can't read marker; don't warn

    state_path = Path(state_dir)
    for f in state_path.glob("*.txt"):
        try:
            first_line = f.read_text().split("\n", 1)[0]
        except OSError:
            continue
        # Match: the state file's exe= field matches this process's exe
        if first_line.endswith("exe=" + exe) and first_line.startswith("static FAIL"):
            _say(
                "this Claude Code build (%s) no longer contains the code it blocks, "
                "so summaries are NOT blocked. Update no-agent-summary.js." % exe
            )
            return


def _say(message: str) -> None:
    """Emit a systemMessage visible inside the session."""
    out = {"systemMessage": "agent-summary blocker: " + message}
    print(json.dumps(out))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # non-blocking: never fail the session
    finally:
        sys.exit(0)
