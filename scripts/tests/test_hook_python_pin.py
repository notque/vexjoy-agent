"""Hooks never fail open under python <3.10: installer link, launcher, in-file guard, doctor drift."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import shlex
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
PYRUN = HOOKS / "lib" / "pyrun.sh"
GUARD_MSG = re.compile(
    r"^\[vexjoy\] hook \S+ needs Python 3\.10\+, got 3\.\d+\.\d+ \(.+\); "
    r"run ./install.sh in vexjoy-agent from a terminal outside Claude Code"
)
EVENT = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}})
NO_REEXEC = {"VEXJOY_PYGUARD_REEXEC": "1"}
# Run a hook as if under 3.9.6: the guard reads sys.version_info, everything else is the real interpreter.
SIMULATE_39 = (
    "import sys, runpy; p = sys.argv[1]; sys.argv = sys.argv[1:]; "
    "sys.version_info = (3, 9, 6, 'final', 0); runpy.run_path(p, run_name='__main__')"
)

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


def _fake_python(path: Path, version: str, venv: bool = False) -> Path:
    """A script that answers the engine's version probe (``<maj.min> <venv>``)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\necho {version} {int(venv)}\n")
    path.chmod(0o755)
    return path


def _env(tmp_path: Path, path_dirs: list[str], extra: dict[str, str] | None = None) -> dict[str, str]:
    """Hermetic hook env: temp HOME, chosen PATH."""
    home = tmp_path / "hookhome"
    home.mkdir(exist_ok=True)
    return {"HOME": str(home), "PATH": os.pathsep.join(path_dirs), **(extra or {})}


def _run(argv: list[str], tmp_path: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, input=EVENT, capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=60)


def _simulated(hook: str, *args: str) -> list[str]:
    return [sys.executable, "-c", SIMULATE_39, str(HOOKS / hook), *args]


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
    info = interp.probe_info(str(link))
    assert info is not None and info[0] >= (3, 10) and not info[1], (target, info)
    assert interp.LINK_SH.replace("$HOME", str(world.home)) == str(link)
    assert '"$HOME/.claude/vexjoy/bin/python3"' in PYRUN.read_text()

    for settings_path in (world.home / ".claude" / "settings.json", cfg / "settings.json"):
        cmds = _commands(settings_path)
        assert cmds and all(c.startswith(interp.LAUNCHER) for c in cmds), (settings_path, cmds)

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


def test_launcher_is_owned_by_engines_that_read_the_first_path_token(tmp_path: Path) -> None:
    """Older engines own an entry when its first '/' token is inside hooks/; the launcher must pass that."""
    home = _home_with_hooks(tmp_path)
    for name in ("pretool-branch-safety.py", "session-context.py"):
        raw = sm.expand_vars(interp.hook_command(name), home)
        first = next(tok for tok in shlex.split(raw) if "/" in tok)
        assert first == str(home / ".claude" / "hooks" / "lib" / "pyrun.sh"), first
        assert os.path.realpath(first).startswith(os.path.realpath(HOOKS))


def test_apply_fails_clearly_and_writes_nothing_without_python_310(
    world: Env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = _fake_python(tmp_path / "old" / "python3", "3.9")
    monkeypatch.setenv(interp.OVERRIDE_ENV, str(old))
    res = world.run("apply", "--target", "claude")
    assert res.code == 1
    assert any("must be an absolute path to a non-venv python 3.10+" in line for line in res.err), res.err
    assert not os.path.lexists(interp.link_path(world.home))
    assert not (world.home / ".claude" / "settings.json").exists()


def test_regular_file_at_link_path_fails_apply_before_any_write(world: Env) -> None:
    link = interp.link_path(world.home)
    link.parent.mkdir(parents=True)
    link.write_text('#!/bin/sh\nexec python3 "$@"\n')
    res = world.run("apply", "--target", "claude")
    assert res.code == 1
    assert any("is a regular file, not a symlink" in line for line in res.err), res.err
    assert not (world.home / ".claude" / "settings.json").exists()
    assert not (world.home / ".claude" / "vexjoy" / "ledger.json").exists()
    sync = world.run("sync", "--target", "claude")
    assert sync.code == 0
    assert any("is a regular file" in line for line in sync.err), sync.err


def test_resolve_skips_shims_venvs_and_prefers_stable_paths(tmp_path: Path) -> None:
    shim = _fake_python(tmp_path / "pyenv" / "shims" / "python3", "3.12")
    venv = _fake_python(tmp_path / "venv" / "bin" / "python3", "3.14", venv=True)
    cellar = _fake_python(tmp_path / "Cellar" / "python@3.13" / "bin" / "python3", "3.13")
    old = _fake_python(tmp_path / "usr" / "bin" / "python3", "3.9")
    stable = _fake_python(tmp_path / "opt" / "bin" / "python3.12", "3.12")
    dirs = (shim, venv, cellar, old, stable)
    found = interp.resolve(env={"PATH": os.pathsep.join(str(p.parent) for p in dirs)}, well_known=(), extra=())
    assert found.path == str(stable)
    only_cellar = interp.resolve(env={"PATH": f"{shim.parent}{os.pathsep}{cellar.parent}"}, well_known=(), extra=())
    assert only_cellar.path == str(cellar)
    with pytest.raises(interp.InterpreterError, match=r"no python 3\.10\+ found"):
        interp.resolve(
            env={"PATH": f"{shim.parent}{os.pathsep}{venv.parent}{os.pathsep}{old.parent}"}, well_known=(), extra=()
        )


def test_link_into_a_versioned_store_counts_as_unstable(tmp_path: Path) -> None:
    store = _fake_python(tmp_path / "uv" / "python" / "cpython-3.12" / "bin" / "python3.12", "3.12")
    stable = _fake_python(tmp_path / "sys" / "bin" / "python3.11", "3.11")
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    os.symlink(store, fakebin / "python3.12")
    assert interp.is_unstable(str(fakebin / "python3.12"))
    assert not interp.is_unstable("/opt/homebrew/bin/python3")
    found = interp.resolve(env={"PATH": f"{fakebin}{os.pathsep}{stable.parent}"}, well_known=(), extra=())
    assert found.path == str(stable)


def test_owner_rule_reads_the_hook_path_after_the_launcher(tmp_path: Path) -> None:
    home = _home_with_hooks(tmp_path)
    rule = sm.OwnerRule(home=home, hooks_dir=home / ".claude" / "hooks", source_root=REPO)
    assert rule.owns({"command": interp.hook_command("pretool-branch-safety.py")})
    assert not rule.owns({"command": "sh /opt/user/run.sh /opt/user/hook.py"})


def test_factory_gets_the_launcher_with_factory_paths(tmp_path: Path) -> None:
    files = external.desired("factory", tmp_path / ".factory", REPO, Profile())
    data = json.loads(files[0].content.decode())
    cmds = [e["command"] for groups in data["hooks"].values() for g in groups for e in g["hooks"]]
    pattern = r'sh "\$HOME/\.factory/hooks/lib/pyrun\.sh" "\$HOME/\.factory/hooks/[\w.-]+\.py"'
    assert cmds and all(re.fullmatch(pattern, c) for c in cmds), cmds[:3]


# (b) under <3.10: gates exit 2, advisory exit 0, adapter follows its policy; no traceback.
# Simulated runs work in CI (patched sys.version_info); the real-3.9 runs need a local 3.9.


@pytest.mark.parametrize("hook", ["pretool-branch-safety.py", "ci-merge-gate.py", "pretool-unified-gate.py"])
def test_simulated_39_gate_exits_2_with_message(hook: str, tmp_path: Path) -> None:
    proc = _run(_simulated(hook), tmp_path, _env(tmp_path, ["/usr/bin", "/bin"], NO_REEXEC))
    assert proc.returncode == 2, proc.stderr
    assert GUARD_MSG.match(proc.stderr) and len(proc.stderr.strip().splitlines()) == 1, proc.stderr
    assert proc.stdout == ""


@pytest.mark.parametrize("hook", ["session-context.py", "suggest-compact.py", "routing-decision-recorder.py"])
def test_simulated_39_advisory_exits_0_with_warning(hook: str, tmp_path: Path) -> None:
    proc = _run(_simulated(hook), tmp_path, _env(tmp_path, ["/usr/bin", "/bin"], NO_REEXEC))
    assert proc.returncode == 0, proc.stderr
    assert GUARD_MSG.match(proc.stderr), proc.stderr


@pytest.mark.parametrize(("policy", "code"), [("closed", 2), ("open", 0)])
def test_simulated_39_codex_adapter_follows_failure_policy(policy: str, code: int, tmp_path: Path) -> None:
    args = ["--hook", str(HOOKS / "suggest-compact.py"), "--event", "PreToolUse", "--matcher", "Bash"]
    args += ["--mode", "native", "--failure-policy", policy]
    proc = _run(_simulated("codex-hook-adapter.py", *args), tmp_path, _env(tmp_path, ["/usr/bin", "/bin"], NO_REEXEC))
    assert proc.returncode == code, proc.stderr
    assert GUARD_MSG.match(proc.stderr), proc.stderr


def test_simulated_39_every_registered_hook_exits_by_mode(tmp_path: Path) -> None:
    env = _env(tmp_path, ["/usr/bin", "/bin"], NO_REEXEC)
    for name in pyguard.registered():
        proc = _run(_simulated(name, "--failure-policy", "open"), tmp_path, env)
        want = 2 if pyguard.mode_for(name) == "gate" else 0
        assert proc.returncode == want, (name, proc.returncode, proc.stderr)
        assert GUARD_MSG.match(proc.stderr), (name, proc.stderr)


def test_simulated_39_reexecs_under_python31x_and_runs_the_hook(tmp_path: Path) -> None:
    """Upgrade window: settings still say bare python3 (3.9 first on PATH), a python3.1x exists elsewhere."""
    bindir = tmp_path / "newbin"
    bindir.mkdir()
    os.symlink(sys.executable, bindir / "python3.12")
    proc = _run(_simulated("pretool-branch-safety.py"), tmp_path, _env(tmp_path, [str(bindir), "/usr/bin", "/bin"]))
    assert proc.returncode == 0, proc.stderr
    assert "[vexjoy]" not in proc.stderr and "Traceback" not in proc.stderr


@needs_old
@pytest.mark.parametrize("hook", ["pretool-branch-safety.py", "ci-merge-gate.py", "pretool-unified-gate.py"])
def test_real_39_gate_exits_2_with_message(hook: str, tmp_path: Path) -> None:
    proc = _run([OLD, str(HOOKS / hook)], tmp_path, _env(tmp_path, ["/usr/bin", "/bin"], NO_REEXEC))
    assert proc.returncode == 2, proc.stderr
    assert GUARD_MSG.match(proc.stderr) and len(proc.stderr.strip().splitlines()) == 1, proc.stderr
    assert "Traceback" not in proc.stderr and proc.stdout == ""


@needs_old
def test_real_39_every_registered_hook_exits_by_mode(tmp_path: Path) -> None:
    env = _env(tmp_path, ["/usr/bin", "/bin"], NO_REEXEC)
    for name in pyguard.registered():
        proc = _run([OLD, str(HOOKS / name), "--failure-policy", "open"], tmp_path, env)
        want = 2 if pyguard.mode_for(name) == "gate" else 0
        assert proc.returncode == want, (name, proc.returncode, proc.stderr)
        assert GUARD_MSG.match(proc.stderr), (name, proc.stderr)


@needs_old
def test_real_39_bare_python3_settings_reexec_and_run(tmp_path: Path) -> None:
    """The upgrade case: bare python3 is 3.9 and first on PATH; the guard re-execs under python3.1x."""
    oldbin = tmp_path / "oldbin"
    oldbin.mkdir()
    os.symlink(OLD, oldbin / "python3")
    newbin = tmp_path / "newbin"
    newbin.mkdir()
    os.symlink(sys.executable, newbin / "python3.12")
    env = _env(tmp_path, [str(oldbin), str(newbin), "/usr/bin", "/bin"])
    home = _home_with_hooks(tmp_path)
    env["HOME"] = str(home)
    cmd = 'python3 "$HOME/.claude/hooks/pretool-unified-gate.py"'
    proc = _run(["/bin/sh", "-c", cmd], tmp_path, env)
    assert proc.returncode == 0, proc.stderr
    assert "[vexjoy]" not in proc.stderr and "Traceback" not in proc.stderr


# (c) the linked python vanishes or is replaced: the launcher still finds a python, never exit 127


def _fake_runner(path: Path, tag: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'#!/bin/sh\necho "{tag} $*"\n')
    path.chmod(0o755)
    return path


def _pyrun(home: Path, path_dirs: list[Path]) -> subprocess.CompletedProcess[str]:
    # Only sh on PATH besides the fakes: /usr/bin or /bin would expose the
    # runner's real python3.1x (Ubuntu ships /usr/bin/python3.12).
    tools = home.parent / "tools"
    tools.mkdir(exist_ok=True)
    if not (tools / "sh").exists():
        os.symlink("/bin/sh", tools / "sh")
    env = {"HOME": str(home), "PATH": os.pathsep.join([*map(str, path_dirs), str(tools)])}
    cmd = interp.hook_command("x.py")
    return subprocess.run(["/bin/sh", "-c", cmd], capture_output=True, text=True, env=env, timeout=30)


def test_pyrun_runs_the_link_first(tmp_path: Path) -> None:
    home = _home_with_hooks(tmp_path)
    link = interp.link_path(home)
    link.parent.mkdir(parents=True)
    os.symlink(_fake_runner(tmp_path / "pinned" / "python3", "pinned"), link)
    other = _fake_runner(tmp_path / "bin" / "python3.12", "path312").parent
    proc = _pyrun(home, [other])
    assert proc.returncode == 0 and proc.stdout.startswith("pinned "), proc
    assert proc.stdout.strip().endswith("/.claude/hooks/x.py")


def test_pyrun_falls_back_to_python31x_when_the_link_dangles_and_skips_shims(tmp_path: Path) -> None:
    home = _home_with_hooks(tmp_path)
    link = interp.link_path(home)
    link.parent.mkdir(parents=True)
    os.symlink(tmp_path / "gone" / "python3", link)
    shims = _fake_runner(tmp_path / "pyenv" / "shims" / "python3.13", "shim").parent
    real = _fake_runner(tmp_path / "bin" / "python3.11", "path311").parent
    proc = _pyrun(home, [shims, real])
    assert proc.returncode == 0 and proc.stdout.startswith("path311 "), proc


def test_link_missing_still_runs_the_hook_through_the_launcher(tmp_path: Path) -> None:
    home = _home_with_hooks(tmp_path)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    os.symlink(sys.executable, bindir / "python3.12")
    env = _env(tmp_path, [str(bindir), "/usr/bin", "/bin"])
    env["HOME"] = str(home)
    proc = _run(["/bin/sh", "-c", interp.hook_command("pretool-branch-safety.py")], tmp_path, env)
    assert proc.returncode == 0, proc.stderr
    assert "[vexjoy]" not in proc.stderr


@needs_old
def test_link_replaced_by_old_python_reexecs_or_blocks(tmp_path: Path) -> None:
    home = _home_with_hooks(tmp_path)
    link = interp.link_path(home)
    link.parent.mkdir(parents=True)
    os.symlink(OLD, link)
    env = _env(tmp_path, ["/nonexistent", "/bin"], NO_REEXEC)
    env["HOME"] = str(home)
    blocked = _run(["/bin/sh", "-c", interp.hook_command("ci-merge-gate.py")], tmp_path, env)
    assert blocked.returncode == 2, blocked.stderr
    assert GUARD_MSG.match(blocked.stderr), blocked.stderr


# (d) doctor reports drift; sync repairs it


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


@pytest.mark.parametrize("setup", ["dangling", "old"])
def test_sync_repairs_a_bad_link_and_uninstall_removes_it(world: Env, tmp_path: Path, setup: str) -> None:
    assert world.run("apply", "--target", "claude").code == 0
    link = interp.link_path(world.home)
    os.unlink(link)
    bad = tmp_path / "gone" / "python3" if setup == "dangling" else _fake_python(tmp_path / "o" / "python3", "3.9")
    os.symlink(bad, link)
    assert world.run("sync", "--target", "claude").code == 0
    assert interp.link_ok(world.home)
    assert os.readlink(link) != str(bad)
    assert world.run("uninstall", "--target", "claude").code == 0
    assert not os.path.lexists(link)


# (e) every registered hook carries the right guard, and gates are classified honestly

_DENY = re.compile(
    r"deny_tool_use\(|sys\.exit\(\s*2\s*\)|[\"']permissionDecision[\"']\s*:\s*[\"']deny|[\"']decision[\"']\s*:\s*[\"']block"
)


def _misclassified(gates: frozenset[str]) -> list[str]:
    """Hooks whose guard mode contradicts what their own code (guard excluded) does."""
    data = json.loads((REPO / ".claude" / "settings.json").read_text())
    events: dict[str, set[str]] = {}
    for event, groups in data["hooks"].items():
        for g in groups:
            for e in g["hooks"]:
                events.setdefault(e["command"].rstrip('"').rsplit("/", 1)[-1], set()).add(event)
    bad = []
    for name, evs in events.items():
        body = pyguard._strip((HOOKS / name).read_text(encoding="utf-8"))
        if "PreToolUse" in evs and _DENY.search(body) and name not in gates:
            bad.append(f"{name} can deny on PreToolUse; add it to GATES in scripts/hook-pyguard.py")
        if evs <= {"Stop", "SubagentStop"} and name in gates:
            bad.append(f"{name}: exit 2 on {sorted(evs)} loops the model")
    return bad


def test_hooks_that_deny_on_pretooluse_are_gates_and_stop_hooks_are_not() -> None:
    assert _misclassified(pyguard.GATES) == []


def test_classification_catches_a_dropped_gate() -> None:
    bad = _misclassified(pyguard.GATES - {"pretool-unified-gate.py"})
    assert bad == ["pretool-unified-gate.py can deny on PreToolUse; add it to GATES in scripts/hook-pyguard.py"]


def test_every_registered_hook_is_guarded() -> None:
    names = pyguard.registered()
    settings_hooks = set(re.findall(r"hooks/([\w.-]+\.py)", (REPO / ".claude" / "settings.json").read_text()))
    assert settings_hooks and settings_hooks <= set(names)
    bad = [p for name in names for p in pyguard.problems(name, (HOOKS / name).read_text(encoding="utf-8"))]
    assert bad == [], "run: python3 scripts/hook-pyguard.py --apply\n" + "\n".join(bad)
    assert pyguard.main(["--check"]) == 0


def test_every_repo_hook_command_uses_the_launcher() -> None:
    data = json.loads((REPO / ".claude" / "settings.json").read_text())
    cmds = [e["command"] for groups in data["hooks"].values() for g in groups for e in g["hooks"]]
    for cmd in cmds:
        name = cmd.rstrip('"').rsplit("/", 1)[-1]
        assert cmd == interp.hook_command(name), cmd


def test_guard_block_parses_on_old_grammar() -> None:
    for mode in ("gate", "advisory", "adapter"):
        ast.parse(pyguard.guard_block(mode), feature_version=(3, 8))


def test_check_rejects_310_only_syntax_after_the_guard() -> None:
    src = pyguard.stamp('"""Doc."""\n\nimport os\n', "advisory") + "\nmatch os.name:\n    case _:\n        pass\n"
    assert any("3.8 grammar" in p for p in pyguard.problems("x.py", src)), pyguard.problems("x.py", src)


def test_stamp_is_idempotent_and_keeps_docstring_and_future_import() -> None:
    src = '#!/usr/bin/env python3\n"""Doc."""\n\nfrom __future__ import annotations\n\nimport os\n'
    once = pyguard.stamp(src, "advisory")
    assert pyguard.stamp(once, "advisory") == once
    assert once.index("from __future__") < once.index("import sys  # vexjoy-pyguard") < once.index("import os")
    assert pyguard.problems("x.py", once) == []
    switched = pyguard.stamp(once, "gate")
    assert switched.count("# vexjoy-pyguard gate") == 1 and "advisory" not in switched
    assert pyguard.problems("x.py", switched) == ["x.py: guard mode gate, want advisory"]


def test_register_hook_refuses_an_unguarded_hook(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text('{"hooks": {"PreToolUse": [{"hooks": []}]}}')
    hook = tmp_path / "new-hook.py"
    hook.write_text("import sys\n\nprint(sys.argv)\n")
    env = {**os.environ, "HOME": str(home)}
    argv = [sys.executable, str(REPO / "scripts" / "register-hook.py"), "add", "--file", str(hook)]
    argv += ["--event", "PreToolUse", "--description", "x"]
    refused = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=60)
    assert refused.returncode == 1 and "lacks the python version guard" in refused.stderr, refused.stderr
    assert not (home / ".claude" / "hooks" / "new-hook.py").exists()
    assert pyguard.main(["--apply", "--file", str(hook)]) == 0
    added = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=60)
    assert added.returncode == 0, added.stderr
    assert _commands(home / ".claude" / "settings.json") == [interp.hook_command("new-hook.py")]
