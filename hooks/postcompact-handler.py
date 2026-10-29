#!/usr/bin/env python3
"""PostCompact hook: re-inject plan context after context compaction.

After compaction shrinks the conversation, this hook reminds the model
about the active task plan and/or ADR session so work can continue
without losing track of goals.
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
from pathlib import Path

_BYPASS_ENV = "POSTCOMPACT_HANDLER_BYPASS"


def main():
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print("[postcompact-handler] Bypassed via POSTCOMPACT_HANDLER_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    try:
        cwd = Path(os.getcwd())

        # Check for active task plan
        plan_file = cwd / "task_plan.md"
        if plan_file.is_file():
            lines = plan_file.read_text().splitlines()[:20]
            preview = "\n".join(lines)
            print(f"[post-compact] Active plan reminder:\n{preview}")

        # Check for active ADR session
        adr_session_file = cwd / ".adr-session.json"
        if adr_session_file.is_file():
            try:
                data = json.loads(adr_session_file.read_text())
                adr_path = data.get("adr_path", "unknown")
                print(f"[post-compact] Active ADR session: {adr_path}")
            except (json.JSONDecodeError, KeyError):
                pass  # Malformed file, skip silently

    except Exception:
        pass  # Hook must never fail itself

    sys.exit(0)


if __name__ == "__main__":
    main()
