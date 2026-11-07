"""scripts/session-bootstrap.sh: install the toolkit into a home that has no launcher, never block."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from scripts.tests.vexinstall_support import settings_mod as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vexinstall import external, interp
from vexinstall.profile import Profile

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "session-bootstrap.sh"


def _run(home: Path, project: Path | str, *, remote: bool = True, payload: str = "") -> subprocess.CompletedProcess:
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(home), "CLAUDE_PROJECT_DIR": str(project)}
    if remote:
        env["CLAUDE_CODE_REMOTE"] = "true"
    return subprocess.run(["sh", str(SCRIPT)], env=env, input=payload, capture_output=True, text=True, timeout=60)


INSTALLS_LAUNCHER = 'mkdir -p "$HOME/.claude/hooks/lib" && touch "$HOME/.claude/hooks/lib/pyrun.sh"\n'


def _fake_repo(tmp_path: Path, body: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "install.sh").write_text("#!/bin/bash\n" + body)
    return repo


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    return home


def test_installed_home_is_a_silent_no_op(tmp_path: Path) -> None:
    home = _home(tmp_path)
    (home / ".claude" / "hooks" / "lib").mkdir(parents=True)
    (home / ".claude" / "hooks" / "lib" / "pyrun.sh").write_text("")
    proc = _run(home, _fake_repo(tmp_path, 'touch "$HOME/ran"\n'))
    assert proc.returncode == 0 and proc.stdout == "" and not (home / "ran").exists()


def test_cloud_session_without_launcher_runs_the_repo_installer(tmp_path: Path) -> None:
    home = _home(tmp_path)
    proc = _run(home, _fake_repo(tmp_path, INSTALLS_LAUNCHER))
    assert proc.returncode == 0 and proc.stdout.startswith("[session-bootstrap] installed")
    assert (home / ".claude" / "hooks" / "lib" / "pyrun.sh").is_file()


def test_local_home_is_told_and_never_installed_even_with_a_ledger(tmp_path: Path) -> None:
    home = _home(tmp_path)
    (home / ".claude" / "vexjoy").mkdir(parents=True)
    (home / ".claude" / "vexjoy" / "ledger.json").write_text("{}")
    proc = _run(home, _fake_repo(tmp_path, INSTALLS_LAUNCHER), remote=False)
    assert proc.returncode == 0 and "run ./install.sh" in proc.stdout
    assert not (home / ".claude" / "hooks").exists()


def test_local_home_never_installed_is_told_and_left_alone(tmp_path: Path) -> None:
    home = _home(tmp_path)
    proc = _run(home, _fake_repo(tmp_path, INSTALLS_LAUNCHER), remote=False)
    assert proc.returncode == 0 and "run ./install.sh" in proc.stdout
    assert not any(home.iterdir())


def test_failed_install_reports_and_never_blocks(tmp_path: Path) -> None:
    home = _home(tmp_path)
    proc = _run(home, _fake_repo(tmp_path, "echo boom >&2\nexit 1\n"))
    assert proc.returncode == 0 and "install failed" in proc.stdout
    assert "boom" in (home / ".claude" / "vexjoy" / "bootstrap.log").read_text()


def test_no_checkout_exits_zero_and_writes_nothing(tmp_path: Path) -> None:
    home = _home(tmp_path)
    proc = _run(home, tmp_path / "nowhere")
    assert proc.returncode == 0 and proc.stdout == "" and not any(home.iterdir())


def test_repo_settings_run_it_first() -> None:
    settings = json.loads((REPO / ".claude" / "settings.json").read_text())
    first = settings["hooks"]["SessionStart"][0]["hooks"][0]
    assert first["command"] == interp.REPO_BOOTSTRAP and first.get("once") is True


def _commands(hooks: dict) -> list[str]:
    return [e["command"] for groups in hooks.values() for g in groups for e in g["hooks"]]


def test_installs_never_copy_it_into_user_or_account_settings() -> None:
    cmds = _commands(sm.desired_from_repo(REPO))
    assert cmds and not any(interp.is_repo_only(c) for c in cmds)
    assert all(c.startswith(interp.LAUNCHER) for c in cmds)


def test_factory_mirror_never_gets_it(tmp_path: Path) -> None:
    files = external.desired("factory", tmp_path / ".factory", REPO, Profile())
    cmds = _commands(json.loads(files[0].content.decode())["hooks"])
    assert cmds and not any("session-bootstrap" in c for c in cmds)


def test_drop_repo_only_removes_groups_it_empties() -> None:
    hooks = {
        "SessionStart": [{"hooks": [{"type": "command", "command": interp.REPO_BOOTSTRAP}]}],
        "Stop": [{"hooks": [{"type": "command", "command": interp.hook_command("x.py")}]}],
    }
    assert sm.drop_repo_only(hooks) == {"Stop": hooks["Stop"]}


def test_health_check_exempts_the_same_command() -> None:
    spec = importlib.util.spec_from_file_location("hook_health", REPO / "scripts" / "validate-hook-health.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.REPO_BOOTSTRAP == interp.REPO_BOOTSTRAP


REPLAY = REPO / "scripts" / "session-bootstrap-replay.py"
# A launcher that runs the real interpreter, as the real pyrun.sh would.
REAL_LAUNCHER = (
    'mkdir -p "$HOME/.claude/hooks/lib" && printf \'#!/bin/sh\\nexec python3 "$@"\\n\' '
    '> "$HOME/.claude/hooks/lib/pyrun.sh"\n'
)


def _replay_repo(tmp_path: Path, session_start: list[dict]) -> Path:
    repo = _fake_repo(tmp_path, REAL_LAUNCHER)
    (repo / "scripts").symlink_to(REPO / "scripts")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"SessionStart": session_start}}))
    return repo


def _context(stdout: str) -> str:
    return json.loads(stdout)["hookSpecificOutput"]["additionalContext"]


def test_cloud_install_replays_session_start_hooks_as_one_context(tmp_path: Path) -> None:
    hooks = [
        {"type": "command", "command": interp.REPO_BOOTSTRAP},
        {"type": "command", "command": 'cat > "$HOME/seen.json"; echo plain-context'},
        {
            "type": "command",
            "command": 'echo \'{"hookSpecificOutput": {"hookEventName": "SessionStart", '
            '"additionalContext": "json-context"}}\'',
        },
        {"type": "command", "command": "echo should-not-appear; exit 2"},
    ]
    repo = _replay_repo(tmp_path, [{"hooks": hooks}])
    home = _home(tmp_path)
    proc = _run(home, repo, payload='{"source": "startup", "session_id": "s1"}')
    assert proc.returncode == 0, proc.stderr
    ctx = _context(proc.stdout)
    assert ctx.startswith("[session-bootstrap] installed")
    assert "plain-context" in ctx and "json-context" in ctx and "should-not-appear" not in ctx
    assert json.loads((home / "seen.json").read_text())["session_id"] == "s1"


def test_replay_respects_matchers_and_skips_the_bootstrap() -> None:
    spec = importlib.util.spec_from_file_location("replay", REPLAY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    settings = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": interp.REPO_BOOTSTRAP}, {"command": "a"}]},
                {"matcher": "resume", "hooks": [{"command": "b"}]},
                {"matcher": "startup|clear", "hooks": [{"command": "c"}]},
            ]
        }
    }
    assert mod.commands(settings, "startup") == ["a", "c"]
    assert mod.commands(settings, "resume") == ["a", "b"]
    settings["hooks"]["SessionStart"].append({"matcher": "[", "hooks": [{"command": "bad"}]})
    assert mod.commands(settings, "startup") == ["a", "c"]
    assert mod.run("echo late", b"", deadline=0) == ""
    assert mod.context_of("") == "" and mod.context_of("text") == "text"
    assert mod.context_of('{"hookSpecificOutput": {"additionalContext": " x "}}') == "x"
    assert mod.context_of('{"hookSpecificOutput": {"hookEventName": "SessionStart"}}') == ""
