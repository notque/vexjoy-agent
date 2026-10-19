"""Hooks never fail open under python <3.10: installer link, launcher fallback, in-file guard, doctor drift."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.tests.vexinstall_support import Env, git, world
from scripts.tests.vexinstall_support import settings_mod as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vexinstall import external, interp
from vexinstall.profile import Profile

REPO = Path(__file__).resolve().parents[2]
HOOKS = REPO / "hooks"
GUARD_MSG = re.compile(r"^\[vexjoy\] hook \S+ needs Python 3\.10\+, got 3\.\d+\.\d+ \(.+\); rerun ./install.sh")
EVENT = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}})

_spec = importlib.util.spec_from_file_location("hook_pyguard", REPO / "scripts" / "hook-pyguard.py")
assert _spec and _spec.loader
pyguard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pyguard)


def _old_python() -> str | None:
    """A real interpreter older than 3.10 on this machine, else None."""
    for cand in ("/usr/bin/python3", shutil.which("python3.9"), shutil.which("python3.8")):
        if cand and os.path.isfile(cand):
            version = interp.probe(cand)
            if version is not None and version < (3, 10):
                return cand
    return None


OLD = _old_python()
needs_old = pytest.mark.skipif(OLD is None, reason="no python <3.10 on this machine")


def _fake_python(path: Path, version: str) -> Path:
    """A script that answers the version probe with *version* (doctor only probes)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\necho {version}\n")
    path.chmod(0o755)
    return path


def _launcher_repo(world: Env) -> None:
    """Switch the fixture repo settings to the launcher form, like the real repo."""
    settings_path = world.repo / ".claude" / "settings.json"
    data = json.loads(settings_path.read_text())
    for groups in data["hooks"].values():
        for group in groups:
            for entry in group["hooks"]:
                name = entry["command"].rstrip('"').rsplit("/", 1)[-1]
                entry["command"] = interp.hook_command(name)
    settings_path.write_text(json.dumps(data, indent=2))
    git(world.repo, "add", "-A")
    git(world.repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "launcher")


def _add_account(world: Env, name: str) -> Path:
    cfg = world.home / ".claude-accounts" / name
    cfg.mkdir(parents=True)
    reg = world.home / ".claude-accounts" / "accounts.json"
    data = json.loads(reg.read_text()) if reg.exists() else {}
    data[name] = {"alias": f"c-{name}", "config_dir": str(cfg)}
    reg.write_text(json.dumps(data))
    return cfg


def _commands(settings_path: Path) -> list[str]:
    hooks = json.loads(settings_path.read_text()).get("hooks", {})
    return [e["command"] for groups in hooks.values() for g in groups for e in g["hooks"]]


def _home_with_hooks(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    os.symlink(HOOKS, home / ".claude" / "hooks")
    return home


def _run_launcher(home: Path, hook: str, path_dirs: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the canonical command exactly as Claude Code does: /bin/sh -c."""
    env = {"HOME": str(home), "PATH": os.pathsep.join(path_dirs), "CLAUDE_HOOKS_DEBUG": ""}
    return subprocess.run(
        ["/bin/sh", "-c", interp.hook_command(hook)],
        input=EVENT,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(home),
        timeout=60,
    )


# (a) installer writes the launcher into every managed profile and links a verified 3.10+ python


def test_apply_links_python_and_writes_launcher_into_every_profile(world: Env) -> None:
    _launcher_repo(world)
    cfg = _add_account(world, "max1")
    res = world.run("apply", "--target", "claude")
    assert res.code == 0, res.err

    link = interp.link_path(world.home)
    target = os.readlink(link)
    assert os.path.isabs(target), target
    assert not interp.is_shim(target)
    version = interp.probe(str(link))
    assert version is not None and version >= (3, 10), (target, version)

    for settings_path in (world.home / ".claude" / "settings.json", cfg / "settings.json"):
        cmds = _commands(settings_path)
        assert cmds and all(c.startswith(interp.LAUNCHER) for c in cmds), (settings_path, cmds)
        assert interp.LINK_SH.replace("$HOME", str(world.home)) == str(link)

    again = world.run("apply", "--target", "claude")
    assert again.code == 0, again.err
    assert _commands(cfg / "settings.json") == _commands(world.home / ".claude" / "settings.json")
    findings = world.run("doctor", "--target", "claude").data["findings"]
    assert [f for f in findings if f["check"].startswith("python-")] == []


def test_apply_replaces_old_bare_entries_without_duplicates(world: Env) -> None:
    assert world.run("apply", "--target", "claude").code == 0
    bare = _commands(world.home / ".claude" / "settings.json")
    assert bare and all(c.startswith("python3 ") for c in bare)
    _launcher_repo(world)
    res = world.run("apply", "--target", "claude")
    assert res.code == 0, res.err
    cmds = _commands(world.home / ".claude" / "settings.json")
    assert len(cmds) == len(bare)
    assert all(c.startswith(interp.LAUNCHER) for c in cmds), cmds


def test_apply_fails_clearly_and_writes_nothing_without_python_310(
    world: Env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = _fake_python(tmp_path / "old" / "python3", "3.9")
    monkeypatch.setenv(interp.OVERRIDE_ENV, str(old))
    res = world.run("apply", "--target", "claude")
    assert res.code == 1
    assert any("must be an absolute path to python 3.10+" in line for line in res.err), res.err
    assert not os.path.lexists(interp.link_path(world.home))
    assert not (world.home / ".claude" / "settings.json").exists()


def test_resolve_skips_shims_and_prefers_stable_paths(tmp_path: Path) -> None:
    shim = _fake_python(tmp_path / "pyenv" / "shims" / "python3", "3.12")
    cellar = _fake_python(tmp_path / "Cellar" / "python@3.13" / "bin" / "python3", "3.13")
    old = _fake_python(tmp_path / "usr" / "bin" / "python3", "3.9")
    stable = _fake_python(tmp_path / "opt" / "bin" / "python3.12", "3.12")
    env = {"PATH": os.pathsep.join(str(p.parent) for p in (shim, cellar, old, stable))}
    found = interp.resolve(env=env, well_known=(), extra=())
    assert found.path == str(stable)
    only_cellar = interp.resolve(env={"PATH": f"{shim.parent}{os.pathsep}{cellar.parent}"}, well_known=(), extra=())
    assert only_cellar.path == str(cellar)
    with pytest.raises(interp.InterpreterError, match=r"no python 3\.10\+ found"):
        interp.resolve(env={"PATH": f"{shim.parent}{os.pathsep}{old.parent}"}, well_known=(), extra=())


def test_owner_rule_reads_the_hook_path_after_the_launcher(tmp_path: Path) -> None:
    home = _home_with_hooks(tmp_path)
    rule = sm.OwnerRule(home=home, hooks_dir=home / ".claude" / "hooks", source_root=REPO)
    assert rule.owns({"command": interp.hook_command("pretool-branch-safety.py")})
    assert not rule.owns({"command": 'p="/x"; exec "$p" /opt/user/hook.py'})


def test_factory_gets_bare_python3_with_factory_paths(tmp_path: Path) -> None:
    files = external.desired("factory", tmp_path / ".factory", REPO, Profile())
    text = files[0].content.decode()
    data = json.loads(text)
    cmds = [e["command"] for groups in data["hooks"].values() for g in groups for e in g["hooks"]]
    assert cmds and all(re.fullmatch(r'python3 "\$HOME/\.factory/hooks/[\w.-]+\.py"', c) for c in cmds), cmds[:3]


# (b) gates exit 2, advisory exit 0, under a real python <3.10, with no traceback


@needs_old
@pytest.mark.parametrize("hook", ["pretool-branch-safety.py", "ci-merge-gate.py", "pretool-unified-gate.py"])
def test_gate_hook_under_old_python_exits_2_with_message(hook: str) -> None:
    proc = subprocess.run([OLD, str(HOOKS / hook)], input=EVENT, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 2, proc.stderr
    assert GUARD_MSG.match(proc.stderr), proc.stderr
    assert len(proc.stderr.strip().splitlines()) == 1
    assert "Traceback" not in proc.stderr and proc.stdout == ""


@needs_old
@pytest.mark.parametrize("hook", ["session-context.py", "suggest-compact.py", "routing-decision-recorder.py"])
def test_advisory_hook_under_old_python_exits_0_with_warning(hook: str) -> None:
    proc = subprocess.run([OLD, str(HOOKS / hook)], input=EVENT, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert GUARD_MSG.match(proc.stderr), proc.stderr
    assert "Traceback" not in proc.stderr


@needs_old
@pytest.mark.parametrize(("policy", "code"), [("closed", 2), ("open", 0)])
def test_codex_adapter_under_old_python_follows_failure_policy(policy: str, code: int) -> None:
    argv = [OLD, str(HOOKS / "codex-hook-adapter.py"), "--hook", str(HOOKS / "suggest-compact.py")]
    argv += ["--event", "PreToolUse", "--matcher", "Bash", "--mode", "native", "--failure-policy", policy]
    proc = subprocess.run(argv, input=EVENT, capture_output=True, text=True, timeout=30)
    assert proc.returncode == code, proc.stderr
    assert GUARD_MSG.match(proc.stderr), proc.stderr


@needs_old
def test_every_registered_hook_is_guarded_under_old_python() -> None:
    for name in pyguard.registered():
        proc = subprocess.run(
            [OLD, str(HOOKS / name), "--failure-policy", "open"],
            input="{}",
            capture_output=True,
            text=True,
            timeout=30,
        )
        want = 2 if pyguard.mode_for(name) == "gate" else 0
        assert proc.returncode == want, (name, proc.returncode, proc.stderr)
        assert GUARD_MSG.match(proc.stderr), (name, proc.stderr)


# (c) the linked python vanishes or is replaced: still guarded, never exit 1 or 127


def test_link_missing_falls_back_to_python3_and_the_hook_runs(tmp_path: Path) -> None:
    home = _home_with_hooks(tmp_path)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    os.symlink(sys.executable, bindir / "python3")
    proc = _run_launcher(home, "pretool-branch-safety.py", [str(bindir), "/usr/bin", "/bin"])
    assert proc.returncode == 0, proc.stderr
    assert "[vexjoy]" not in proc.stderr


@needs_old
def test_link_dangling_with_old_python3_on_path_blocks_gates(tmp_path: Path) -> None:
    home = _home_with_hooks(tmp_path)
    link = interp.link_path(home)
    link.parent.mkdir(parents=True)
    os.symlink(tmp_path / "gone" / "python3", link)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    os.symlink(OLD, bindir / "python3")
    gate = _run_launcher(home, "pretool-branch-safety.py", [str(bindir), "/usr/bin", "/bin"])
    assert gate.returncode == 2, gate.stderr
    assert GUARD_MSG.match(gate.stderr), gate.stderr
    advisory = _run_launcher(home, "suggest-compact.py", [str(bindir), "/usr/bin", "/bin"])
    assert advisory.returncode == 0, advisory.stderr
    assert GUARD_MSG.match(advisory.stderr), advisory.stderr


@needs_old
def test_link_replaced_by_old_python_blocks_gates(tmp_path: Path) -> None:
    home = _home_with_hooks(tmp_path)
    link = interp.link_path(home)
    link.parent.mkdir(parents=True)
    os.symlink(OLD, link)
    proc = _run_launcher(home, "ci-merge-gate.py", ["/nonexistent"])
    assert proc.returncode == 2, proc.stderr
    assert GUARD_MSG.match(proc.stderr), proc.stderr


def test_link_present_runs_the_linked_python(tmp_path: Path) -> None:
    home = _home_with_hooks(tmp_path)
    link = interp.link_path(home)
    link.parent.mkdir(parents=True)
    os.symlink(sys.executable, link)
    proc = _run_launcher(home, "pretool-branch-safety.py", ["/nonexistent"])
    assert proc.returncode == 0, proc.stderr


# (d) doctor reports drift


@pytest.mark.parametrize(
    ("setup", "check"),
    [("missing", "python-pin-missing"), ("dangling", "python-pin-dangling"), ("old", "python-pin-old")],
)
def test_doctor_flags_python_drift(world: Env, tmp_path: Path, setup: str, check: str) -> None:
    assert world.run("apply", "--target", "claude").code == 0
    link = interp.link_path(world.home)
    os.unlink(link)
    if setup == "dangling":
        os.symlink(tmp_path / "gone" / "python3", link)
    elif setup == "old":
        os.symlink(_fake_python(tmp_path / "old" / "python3", "3.9"), link)
    res = world.run("doctor", "--target", "claude")
    found = [f for f in res.data["findings"] if f["check"].startswith("python-")]
    assert [f["check"] for f in found] == [check], found
    assert found[0]["level"] == "error" and "rerun ./install.sh" in found[0]["detail"]
    assert res.code == 1


def test_sync_recreates_a_dangling_link_and_uninstall_removes_it(world: Env, tmp_path: Path) -> None:
    assert world.run("apply", "--target", "claude").code == 0
    link = interp.link_path(world.home)
    os.unlink(link)
    os.symlink(tmp_path / "gone" / "python3", link)
    assert world.run("sync", "--target", "claude").code == 0
    assert interp.link_ok(world.home)
    assert world.run("uninstall", "--target", "claude").code == 0
    assert not os.path.lexists(link)


# (e) every registered hook carries the right guard


def test_every_registered_hook_is_guarded() -> None:
    names = pyguard.registered()
    settings_hooks = set(re.findall(r"hooks/([\w.-]+\.py)", (REPO / ".claude" / "settings.json").read_text()))
    assert settings_hooks and settings_hooks <= set(names)
    bad = [p for name in names for p in pyguard.problems(name, (HOOKS / name).read_text(encoding="utf-8"))]
    assert bad == [], "run: python3 scripts/hook-pyguard.py --apply\n" + "\n".join(bad)


def test_every_repo_hook_command_uses_the_launcher() -> None:
    data = json.loads((REPO / ".claude" / "settings.json").read_text())
    cmds = [e["command"] for groups in data["hooks"].values() for g in groups for e in g["hooks"]]
    for cmd in cmds:
        name = cmd.rstrip('"').rsplit("/", 1)[-1]
        assert cmd == interp.hook_command(name), cmd


def test_hooks_that_deny_on_pretooluse_are_gates_and_stop_hooks_are_not() -> None:
    data = json.loads((REPO / ".claude" / "settings.json").read_text())
    events: dict[str, set[str]] = {}
    for event, groups in data["hooks"].items():
        for g in groups:
            for e in g["hooks"]:
                events.setdefault(e["command"].rstrip('"').rsplit("/", 1)[-1], set()).add(event)
    denies = re.compile(r"deny_tool_use\(|sys\.exit\(\s*2\s*\)")
    for name, evs in events.items():
        text = (HOOKS / name).read_text(encoding="utf-8")
        if "PreToolUse" in evs and denies.search(text):
            assert name in pyguard.GATES, f"{name} can deny on PreToolUse; add it to GATES in scripts/hook-pyguard.py"
        if evs <= {"Stop", "SubagentStop"}:
            assert name not in pyguard.GATES, f"{name}: exit 2 on {evs} loops the model"


def test_guard_block_parses_on_old_grammar() -> None:
    import ast

    for mode in ("gate", "advisory", "adapter"):
        ast.parse(pyguard.guard_block(mode), feature_version=(3, 8))


def test_stamp_is_idempotent_and_keeps_docstring_and_future_import() -> None:
    src = '#!/usr/bin/env python3\n"""Doc."""\n\nfrom __future__ import annotations\n\nimport os\n'
    once = pyguard.stamp(src, "advisory")
    assert pyguard.stamp(once, "advisory") == once
    assert once.index("from __future__") < once.index("import sys  # vexjoy-pyguard") < once.index("import os")
    assert pyguard.problems("x.py", once) == []
    switched = pyguard.stamp(once, "gate")
    assert switched.count("# vexjoy-pyguard gate") == 1 and "advisory" not in switched
    assert pyguard.problems("x.py", switched) == ["x.py: guard mode gate, want advisory"]
