"""vexinstall safety: write-through, guard, mass-removal cap, trash, user edits, corrupt ledger,
concurrency, rollback.

Layout, idempotency, and write-through run for all five targets; the rest run on the
targets whose adapter row takes a distinct branch (target logic lives in the adapter table).
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pytest

from scripts.tests.vexinstall_support import (
    ADAPTERS,
    BULK_SKILLS,
    SCRIPTS_DIR,
    TARGETS,
    Env,
    bulk_world,
    commit_all,
    common,
    fsops,
    git,
    repo_hash,
    tree_hash,
    world,
)

MODES = ("symlink", "copy")
LOCK = (".claude/vexjoy/lock",)


def _ok(res) -> None:
    assert res.code == 0, f"exit {res.code}\nout={res.out}\nerr={res.err}"


def _state(env: Env) -> Path:
    return env.home / ".claude" / "vexjoy"


def _last_report(env: Env) -> dict:
    reports = sorted((_state(env) / "reports").glob("*.json"))
    return json.loads(reports[-1].read_text())


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("mode", MODES)
def test_write_through_never_changes_repo(world: Env, target: str, mode: str) -> None:
    adapter = ADAPTERS[target]
    root = world.root(target)
    root.mkdir(parents=True, exist_ok=True)
    # Whole-dir container links into the repo (legacy installs).
    os.symlink(str(world.repo / "skills" / "meta"), root / "skills")
    if adapter.agents:
        os.symlink(str(world.repo / "agents"), root / adapter.agents)
    before = repo_hash(world.repo)
    _ok(world.run("apply", "--target", target, "--mode", mode))
    assert repo_hash(world.repo) == before
    assert not (root / "skills").is_symlink()
    # Dest-level link into another repo skill; apply must replace the link, never write through it.
    dest = world.skills(target) / "alpha"
    if dest.is_symlink():
        dest.unlink()
    else:
        shutil.rmtree(dest)
    os.symlink(str(world.repo / "skills" / "meta" / "beta"), dest)
    _ok(world.run("apply", "--target", target, "--mode", mode))
    assert repo_hash(world.repo) == before
    assert (dest / "SKILL.md").read_text().startswith("---\nname: alpha")


def test_guard_unit_raises_for_parent_resolving_into_repo(world: Env) -> None:
    link = world.home / "sneaky"
    os.symlink(str(world.repo / "skills"), link)
    guard = fsops.Guard.for_roots([world.repo])
    with pytest.raises(common.GuardError):
        guard.check(link / "x.json")
    with pytest.raises(common.GuardError):
        fsops.atomic_write_bytes(link / "x.json", b"{}", guard)
    assert not (world.repo / "skills" / "x.json").exists()
    guard.check(world.home / "ok.json")


@pytest.mark.parametrize("target", ["claude", "codex"])
def test_guard_trip_aborts_with_exit_4(world: Env, target: str) -> None:
    before = repo_hash(world.repo)
    if target == "claude":
        state = _state(world)
        shutil.rmtree(state)
        os.symlink(str(world.repo / "skills" / "kb"), state)
    else:
        root = world.root(target)
        root.mkdir(parents=True)
        os.symlink(str(world.repo / "skills" / "kb"), root / "vexjoy")
    res = world.run("apply", "--target", target)
    assert res.code == 4, (res.out, res.err)
    assert "guard:" in res.err[0] and str(world.repo) in res.err[0]
    assert ("state root" if target == "claude" else "skills.json") in res.err[0]
    assert repo_hash(world.repo) == before
    if target != "claude":
        assert _last_report(world)["guard"].endswith("skills.json")


@pytest.mark.parametrize("target", ["claude", "codex"])
def test_mass_removal_cap_trash_and_restore(bulk_world: Env, target: str) -> None:
    env = bulk_world
    _ok(env.run("apply", "--target", target))
    bulk_dests = [env.skills(target) / n for n in BULK_SKILLS]
    snapshot = {str(d): (os.readlink(d) if d.is_symlink() else tree_hash(d)) for d in bulk_dests}
    git(env.repo, "rm", "-r", "-q", "skills/bulk")
    commit_all(env.repo, "drop bulk")
    before = tree_hash(env.home, exclude=LOCK)
    res = env.run("apply", "--target", target)
    assert res.code == 5 and "mass-removal cap" in res.err[0]
    assert tree_hash(env.home, exclude=LOCK) == before
    sync = env.run("sync", "--target", target, "--allow-mass-remove")
    assert sync.code == 0 and "mass-removal cap" in sync.err[0]
    assert tree_hash(env.home, exclude=LOCK) == before
    _ok(env.run("apply", "--target", target, "--allow-mass-remove"))
    assert not any(os.path.lexists(d) for d in bulk_dests)
    trash_dir = Path(_last_report(env)["trash"])
    ts = trash_dir.name
    manifest = json.loads((trash_dir / "manifest.json").read_text())
    assert {i["original"] for i in manifest["items"]} >= set(snapshot)
    _ok(env.run("restore-trash", ts))
    for d in bulk_dests:
        assert (os.readlink(d) if d.is_symlink() else tree_hash(d)) == snapshot[str(d)]


@pytest.mark.parametrize("target", ["claude"])
def test_user_edited_copy_is_skipped(world: Env, target: str) -> None:
    _ok(world.run("apply", "--target", target, "--mode", "copy"))
    dest = world.skills(target) / "beta" / "SKILL.md"
    dest.write_text(dest.read_text() + "\nmy local note\n")
    src = world.repo / "skills" / "meta" / "beta" / "SKILL.md"
    src.write_text(src.read_text() + "\nupstream change\n")
    commit_all(world.repo, "change beta")
    res = world.run("sync", "--target", target)
    _ok(res)
    assert "my local note" in dest.read_text() and "upstream change" not in dest.read_text()
    skipped = json.dumps(_last_report(world)["diff"][target]["skipped"])
    assert "beta" in skipped and "user-edited" in skipped
    git(world.repo, "rm", "-r", "-q", "skills/meta/beta")
    commit_all(world.repo, "drop beta")
    _ok(world.run("sync", "--target", target))
    assert dest.is_file(), "user-edited copy must never be removed"


@pytest.mark.parametrize(("target", "mode"), [("claude", "symlink"), ("claude", "copy"), ("codex", "symlink")])
def test_corrupt_ledger_rebuilt_by_adoption(world: Env, target: str, mode: str) -> None:
    _ok(world.run("apply", "--target", target, "--mode", mode))
    dests = world.ledger_dests(target)
    root = world.root(target)
    before = tree_hash(root, exclude=("vexjoy",))
    (_state(world) / "ledger.json").write_text("{not json")
    res = world.run("apply", "--target", target, "--mode", mode)
    _ok(res)
    assert any("corrupt" in line for line in res.err)
    assert list(_state(world).glob("ledger.corrupt.*"))
    assert world.ledger_dests(target) == dests
    assert tree_hash(root, exclude=("vexjoy",)) == before
    assert res.out[0].startswith(f"[apply] {target}: +0 ~0 -0")


@pytest.mark.parametrize("target", ["claude"])
def test_sync_exits_zero_when_lock_held(world: Env, target: str) -> None:
    lock = _state(world) / "lock"
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        before = tree_hash(world.home, exclude=LOCK)
        t0 = time.monotonic()
        proc = world.cli("sync", "--target", target)
        assert proc.returncode == 0 and proc.stdout == "" and time.monotonic() - t0 < 20
        assert tree_hash(world.home, exclude=LOCK) == before
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@pytest.mark.parametrize("target", ["claude"])
def test_two_concurrent_syncs_leave_valid_state(world: Env, target: str) -> None:
    env = {
        **os.environ,
        "PYTHONPATH": str(SCRIPTS_DIR),
        "HOME": str(world.home),
    }
    argv = [
        sys.executable,
        "-m",
        "vexinstall",
        "sync",
        "--target",
        target,
        "--home",
        str(world.home),
        "--source-root",
        str(world.repo),
    ]
    procs = [subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
    codes = [p.wait(timeout=120) for p in procs]
    assert codes == [0, 0]
    res = world.run("plan", "--target", target, "--json")
    s = res.data["targets"][target]["summary"]
    assert (s["add"], s["replace"], s["remove"]) == (0, 0, 0)
    leftovers = [p for p in world.home.rglob(".*vexinstall-*")]
    assert leftovers == []


def _legacy_tree(env: Env, target: str) -> None:
    adapter = ADAPTERS[target]
    root = env.root(target)
    skills = root / "skills"
    skills.mkdir(parents=True)
    os.symlink(str(env.repo / "skills" / "meta"), skills / "meta")
    os.symlink(str(env.repo / "skills" / "meta" / "alpha"), skills / "alpha")
    os.symlink(str(env.repo / "skills" / "gone"), skills / "ghost-legacy")
    (skills / "user-own").mkdir()
    (skills / "user-own" / "SKILL.md").write_text("---\nname: user-own\n---\n")
    if adapter.agents:
        os.symlink(str(env.repo / "agents"), root / adapter.agents)
    if target == "claude":
        settings = {
            "theme": "dark",
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": f"python3 {env.repo}/hooks/h1.py"}]},
                    {"hooks": [{"type": "command", "command": "python3 /opt/user/hook.py"}]},
                ]
            },
        }
        (root / "settings.json").write_text(json.dumps(settings, indent=2))


def _entry_state(path: Path) -> str:
    """Link target, file bytes, or dir listing (recursive) of one path; never follows links."""
    if os.path.islink(path):
        return "L " + os.readlink(path)
    if path.is_file():
        return "F " + path.read_bytes().hex()
    if path.is_dir():
        return "D " + tree_hash(path)
    return "absent"


def _legacy_paths(env: Env, target: str) -> list[Path]:
    adapter = ADAPTERS[target]
    root = env.root(target)
    paths = [root / "skills" / n for n in ("meta", "alpha", "ghost-legacy", "user-own")]
    if adapter.agents:
        paths.append(root / adapter.agents)
    if target == "claude":
        paths.append(root / "settings.json")
    return paths


def _extract(tar_path: Path, dest: Path) -> None:
    with tarfile.open(tar_path) as tf:
        if hasattr(tarfile, "fully_trusted_filter"):
            tf.extractall(dest, filter="fully_trusted")
        else:  # pragma: no cover - python < 3.12
            tf.extractall(dest)


@pytest.mark.parametrize("target", ["claude", "hermes"])
def test_rollback_restores_pre_switch_tree(world: Env, target: str) -> None:
    _legacy_tree(world, target)
    root = world.root(target)
    pre_entries = {str(p): _entry_state(p) for p in _legacy_paths(world, target)}
    pre_exact = tree_hash(root, exclude=("vexjoy",))
    backups = _state(world) / "backups"
    backups.mkdir(parents=True)
    snap = backups / "pre-migration.tar"
    with tarfile.open(snap, "w") as tf:
        tf.add(root, arcname=root.name, filter=lambda ti: None if ti.name.split("/")[1:2] == ["vexjoy"] else ti)
    os.chmod(snap, 0o600)

    plan = world.run("plan", "--target", target, "--json")
    assert plan.data["targets"][target]["summary"]["adopt"] >= 3
    _ok(world.run("apply", "--target", target, "--allow-mass-remove"))
    apply_ts = Path(_last_report(world)["trash"]).name
    assert (root / "skills" / "user-own" / "SKILL.md").is_file()
    assert not os.path.lexists(root / "skills" / "meta")
    assert not os.path.lexists(root / "skills" / "ghost-legacy")

    # Rollback 1 (spec 15, phase 3a): restore-trash <ts> plus restore-settings <ts>.
    _ok(world.run("restore-trash", apply_ts))
    if target == "claude":
        first = sorted(backups.glob("settings.*.json"))[0].name[len("settings.") : -len(".json")]
        _ok(world.run("restore-settings", first))
    assert {str(p): _entry_state(p) for p in _legacy_paths(world, target)} == pre_entries

    # Rollback 2: the pre-migration tar restores the tree byte for byte.
    _ok(world.run("apply", "--target", target, "--allow-mass-remove", "--adopt-source"))
    for child in list(root.iterdir()):
        if child.name == "vexjoy":
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    staging = world.work / "restore"
    _extract(snap, staging)
    for child in (staging / root.name).iterdir():
        os.rename(child, root / child.name)
    assert tree_hash(root, exclude=("vexjoy",)) == pre_exact
