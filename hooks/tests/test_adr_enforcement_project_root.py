"""Project-root behavior for the ADR enforcement PostToolUse hook."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "adr-enforcement.py"


def test_absolute_target_path_uses_trusted_checker_and_project_relative_command(tmp_path: Path) -> None:
    target = tmp_path / "target"
    trusted = tmp_path / "trusted"
    installed_hook = trusted / "hooks" / HOOK.name
    installed_hook.parent.mkdir(parents=True)
    shutil.copy2(HOOK, installed_hook)
    shutil.copytree(HOOK.parent / "lib", installed_hook.parent / "lib")

    agent = target / "agents" / "example.md"
    agent.parent.mkdir(parents=True)
    agent.write_text("---\nname: example\n---\n", encoding="utf-8")
    (target / ".adr-session.json").write_text("{}\n", encoding="utf-8")

    sentinel = tmp_path / "malicious-adr-ran"
    malicious = target / "scripts" / "adr-compliance.py"
    malicious.parent.mkdir()
    malicious.write_text(
        f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('owned')\n",
        encoding="utf-8",
    )
    argv_record = tmp_path / "trusted-adr-argv.json"
    checker = trusted / "scripts" / "adr-compliance.py"
    checker.parent.mkdir()
    checker.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        f"Path({str(argv_record)!r}).write_text(json.dumps(sys.argv[1:]))\n"
        "print(json.dumps({'verdict': 'FAIL', 'violations': "
        "[{'line': 1, 'type': 'test', 'value': 'bad'}]}))\n",
        encoding="utf-8",
    )

    event = {
        "hook_event_name": "PostToolUse",
        "cwd": str(target),
        "tool_input": {"file_path": str(agent)},
    }
    result = subprocess.run(
        [sys.executable, str(installed_hook)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd="/",
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert not sentinel.exists()
    argv = json.loads(argv_record.read_text(encoding="utf-8"))
    assert argv[argv.index("--file") + 1] == str(agent)
    assert argv[argv.index("--step-menu") + 1].startswith(str(target))
    assert argv[argv.index("--spec-format") + 1].startswith(str(target))
    output = json.loads(result.stdout)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "COMPLIANCE CHECK: agents/example.md" in context
    assert "python3 scripts/adr-compliance.py check --file agents/example.md" in context
    assert str(target) not in context
