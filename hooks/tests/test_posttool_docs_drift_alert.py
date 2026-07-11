"""Target-project behavior for the documentation drift PostToolUse hook."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "posttool-docs-drift-alert.py"


def test_target_project_scanner_warning_is_model_visible_context(tmp_path: Path) -> None:
    target = tmp_path / "target"
    trusted = tmp_path / "trusted"
    installed_hook = trusted / "hooks" / HOOK.name
    installed_hook.parent.mkdir(parents=True)
    shutil.copy2(HOOK, installed_hook)
    shutil.copytree(HOOK.parent / "lib", installed_hook.parent / "lib")

    sentinel = tmp_path / "malicious-docs-ran"
    malicious = target / "skills" / "meta" / "docs-sync-checker" / "scripts" / "scan_tools.py"
    malicious.parent.mkdir(parents=True)
    malicious.write_text(
        f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('owned')\n",
        encoding="utf-8",
    )
    argv_record = tmp_path / "trusted-docs-argv.json"
    scanner = trusted / "skills" / "meta" / "docs-sync-checker" / "scripts" / "scan_tools.py"
    scanner.parent.mkdir(parents=True)
    scanner.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        f"Path({str(argv_record)!r}).write_text(json.dumps(sys.argv[1:]))\n"
        "print('TRUSTED SCANNER DRIFT', file=sys.stderr)\nraise SystemExit(1)\n",
        encoding="utf-8",
    )
    agent = target / "agents" / "example.md"
    agent.parent.mkdir()
    agent.write_text("---\nname: example\n---\n", encoding="utf-8")

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
    assert argv[argv.index("--repo-root") + 1] == str(target)
    output = json.loads(result.stdout)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "[docs-drift] WARNING" in context
    assert "TRUSTED SCANNER DRIFT" in context
    assert "TRUSTED SCANNER DRIFT" not in result.stderr
