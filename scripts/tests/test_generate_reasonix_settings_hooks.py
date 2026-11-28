"""Tests for scripts/generate-reasonix-settings-hooks.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "generate-reasonix-settings-hooks.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("generate_reasonix_settings_hooks", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()
parse_allowlist = _mod.parse_allowlist
build_hooks = _mod.build_hooks
merge_settings = _mod.merge_settings


def test_parse_allowlist_valid_and_ignores_comments():
    text = (
        "# comment\n"
        "\n"
        "PreToolUse:pretool-branch-safety.py Bash\n"
        "PostToolUse:posttool-check.py Edit|Write\n"
        "UserPromptSubmit:prompt-capture.py\n"
        "Stop:stop-guard.py\n"
    )
    entries = parse_allowlist(text)
    assert entries == [
        {"event": "PreToolUse", "filename": "pretool-branch-safety.py", "match": "Bash"},
        {"event": "PostToolUse", "filename": "posttool-check.py", "match": "Edit|Write"},
        {"event": "UserPromptSubmit", "filename": "prompt-capture.py", "match": None},
        {"event": "Stop", "filename": "stop-guard.py", "match": None},
    ]


@pytest.mark.parametrize(
    ("bad_line", "expected"),
    [
        ("no-colon-here\n", "missing ':'"),
        ("PreToolUse:\n", "missing filename"),
        ("UnknownEvent:foo.py\n", "unknown event"),
        ("PreToolUse:foo.py\n", "requires a match"),
        ("Stop:foo.py Bash\n", "does not accept a match"),
        ("Stop:../escape.py\n", "bare .py"),
        ("Stop:sub/hook.py\n", "bare .py"),
        ("Stop:sub\\hook.py\n", "bare .py"),
        ("Stop:hook..py\n", "bare .py"),
        ("Stop:hook.sh\n", "bare .py"),
        ("Stop:.py\n", "bare .py"),
    ],
)
def test_parse_allowlist_rejects_invalid_lines(bad_line: str, expected: str):
    with pytest.raises(ValueError, match=expected):
        parse_allowlist(bad_line)


def test_build_hooks_posix_and_windows_quoting():
    entries = parse_allowlist("PreToolUse:pretool-branch-safety.py Bash\nStop:stop-guard.py\n")
    posix_hooks = build_hooks(entries, reasonix_hooks_dir="/home/jo doe/.reasonix/hooks", windows=False)
    assert posix_hooks["PreToolUse"] == [
        {
            "command": "python3 '/home/jo doe/.reasonix/hooks/pretool-branch-safety.py'",
            "timeout": 5000,
            "match": "Bash",
        }
    ]
    assert posix_hooks["Stop"] == [
        {
            "command": "python3 '/home/jo doe/.reasonix/hooks/stop-guard.py'",
            "timeout": 30000,
        }
    ]

    win_hooks = build_hooks(entries, reasonix_hooks_dir=r"C:\Users\Jo Doe\.reasonix\hooks", windows=True)
    assert (
        win_hooks["PreToolUse"][0]["command"] == r'python3 "C:\Users\Jo Doe\.reasonix\hooks/pretool-branch-safety.py"'
    )
    assert "'" not in win_hooks["Stop"][0]["command"]


@pytest.mark.parametrize("bad_dir", [r"C:\Users\%USERNAME%\hooks", r"C:\Users\!VAR!\hooks", 'C:\\"bad"', "a\nb"])
def test_build_hooks_windows_refuses_unquotable_paths(bad_dir: str):
    entries = parse_allowlist("Stop:stop-guard.py\n")
    with pytest.raises(ValueError, match=r"cmd\.exe"):
        build_hooks(entries, reasonix_hooks_dir=bad_dir, windows=True)


@pytest.mark.parametrize("bad_existing", [[], "not-a-dict", 42, None])
def test_merge_settings_handles_non_dict_existing(bad_existing):
    hooks_data = {"Stop": [{"command": "python3 /hooks/stop.py", "timeout": 30000}]}
    merged = merge_settings(bad_existing, hooks_data)
    assert merged == {"hooks": hooks_data}


def test_merge_settings_preserves_other_top_level_keys():
    existing = {"model": "deepseek-reasoner", "theme": "dark", "hooks": {"Stop": []}}
    hooks_data = {"Stop": [{"command": "python3 /hooks/stop.py", "timeout": 30000}]}
    merged = merge_settings(existing, hooks_data)
    assert merged["model"] == "deepseek-reasoner"
    assert merged["theme"] == "dark"
    assert merged["hooks"] == hooks_data


def test_cli_writes_atomically_and_handles_non_dict_existing(tmp_path: Path):
    allowlist = tmp_path / "allowlist.txt"
    allowlist.write_text("Stop:stop-guard.py\n", encoding="utf-8")
    out_file = tmp_path / "settings.json"
    out_file.write_text('["not", "an", "object"]\n', encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--allowlist",
            str(allowlist),
            "--output",
            str(out_file),
            "--reasonix-hooks-dir",
            "/fake/hooks",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "not a JSON object" in proc.stderr
    written = json.loads(out_file.read_text(encoding="utf-8"))
    assert "hooks" in written and "Stop" in written["hooks"]
    assert list(tmp_path.glob("settings.bak.*"))


def test_cli_rejects_traversal_filename(tmp_path: Path):
    allowlist = tmp_path / "allowlist.txt"
    allowlist.write_text("Stop:../evil.py\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--allowlist", str(allowlist), "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert "bare .py" in proc.stderr
