"""vexinstall spec 16 matrix: idempotency, layout, shape, collisions, dangling, move, worktree,
missing overlay, uninstall.

Layout, idempotency, and write-through run for all five targets; the rest run on the
targets whose adapter row takes a distinct branch (target logic lives in the adapter table).
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from scripts.tests.vexinstall_support import (
    ADAPTERS,
    TARGETS,
    Env,
    bulk_world,
    commit_all,
    expected_skill_names,
    find_named,
    git,
    make_world,
    skill_md,
    tree_hash,
    world,
    write_overlays,
)

MODES = ("symlink", "copy")
LOCK = (".claude/vexjoy/lock",)


def _ok(res) -> None:
    assert res.code == 0, f"exit {res.code}\nout={res.out}\nerr={res.err}"


def _summary(env: Env, target: str) -> dict:
    res = env.run("plan", "--target", target, "--json")
    return res.data["targets"][target]["summary"]


def _entries(path: Path) -> set[str]:
    return {p for p in os.listdir(path) if not p.startswith(".")} if path.is_dir() else set()


@pytest.mark.parametrize(("target", "mode"), [*((t, "symlink") for t in TARGETS), ("claude", "copy")])
def test_apply_is_idempotent(world: Env, target: str, mode: str) -> None:
    _ok(world.run("apply", "--target", target, "--mode", mode))
    s = _summary(world, target)
    assert (s["add"], s["replace"], s["remove"], s["blocked"]) == (0, 0, 0, 0), s
    second = world.run("apply", "--target", target, "--mode", mode)
    _ok(second)
    assert second.out[0].startswith(f"[apply] {target}: +0 ~0 -0,"), second.out[0]


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("mode", MODES)
def test_layout_matches_adapter_table(world: Env, target: str, mode: str) -> None:
    _ok(world.run("apply", "--target", target, "--mode", mode))
    adapter = ADAPTERS[target]
    root = world.root(target)
    skills = world.skills(target)
    assert not skills.is_symlink()
    assert _entries(skills) == expected_skill_names(target)
    for category in ("meta", "process", "content", "old-thing"):
        assert not os.path.lexists(skills / category), f"category/promoted entry {category} installed"
    forced_copy = adapter.skills_mode == "copy"
    for name in ("alpha", "delta", "private-one", "voice-v1"):
        dest = skills / name
        if mode == "symlink" and not forced_copy:
            assert dest.is_symlink() and os.path.isabs(os.readlink(dest))
        else:
            assert dest.is_dir() and not dest.is_symlink()
        assert (dest / "SKILL.md").is_file() or (dest / "skill" / "SKILL.md").is_file()
    assert (skills / "delta" / "references" / "ref.md").is_file()
    if adapter.agents:
        agents = root / adapter.agents
        assert agents.is_dir() and not agents.is_symlink()
        assert _entries(agents) == {"a-eng.md", "b-eng.md", "c-eng.md", "a-eng", "p-agent.md"}
    if adapter.commands:
        assert _entries(root / adapter.commands) == {"cmd-one.md"}  # alpha.md shadowed by skill alpha
    hooks = root / "hooks"
    if adapter.hooks == "whole":
        assert hooks.is_symlink() if mode == "symlink" else (hooks.is_dir() and not hooks.is_symlink())
        assert (hooks / "h1.py").is_file()
    elif adapter.hooks == "per-entry":
        assert not hooks.is_symlink() and _entries(hooks) == {"h1.py", "h2.py", "h3.py", "lib"}
        assert _entries(hooks / "lib") == {"util.py", "more.py"}
    elif adapter.hooks == "allowlist":
        assert _entries(hooks) == {"h1.py", "lib"}
    else:
        assert not os.path.lexists(hooks)
    scripts = root / "scripts"
    if adapter.scripts == "whole":
        assert (scripts / "tool" / "x.py").is_file()
    elif adapter.scripts == "per-entry":
        assert not scripts.is_symlink()
        assert {"s1.py", "s2.py", "tool"} <= _entries(scripts)
    else:
        assert adapter.scripts is None, f"unhandled adapter.scripts={adapter.scripts!r}"
        assert not os.path.lexists(scripts)
    index = json.loads((root / "vexjoy" / "index" / "skills.json").read_text())
    assert set(index["skills"]) == expected_skill_names(target, skills_only=True)


@pytest.mark.parametrize("target", ["claude", "reasonix"])
def test_copy_and_symlink_modes_have_same_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str) -> None:
    a = make_world(tmp_path / "a", monkeypatch)
    b = make_world(tmp_path / "b", monkeypatch)
    _ok(a.run("apply", "--target", target, "--mode", "symlink"))
    _ok(b.run("apply", "--target", target, "--mode", "copy"))
    root_a, root_b = a.root(target), b.root(target)

    def shape(root: Path) -> set[str]:
        out = set()
        for container in ADAPTERS[target].containers(root.parent):
            if container.is_dir():
                out |= {f"{container.relative_to(root)}/{n}" for n in _entries(container)}
        return out

    assert shape(root_a) == shape(root_b)
    for name in ("alpha", "private-one"):
        assert (a.skills(target) / name / "SKILL.md").read_bytes() == (
            b.skills(target) / name / "SKILL.md"
        ).read_bytes()


def _add_clash(env: Env) -> Path:
    clash = env.work / "clash"
    (clash / "cat" / "alpha").mkdir(parents=True)
    (clash / "cat" / "alpha" / "SKILL.md").write_text("---\nname: alpha\ndescription: clash\n---\n")
    cfg = json.loads((env.home / ".claude" / "vexjoy" / "overlays.json").read_text())
    cfg["overlays"].append({"id": "clash", "root": str(clash), "layout": "category"})
    write_overlays(env.home, cfg)
    return clash


@pytest.mark.parametrize("target", ["claude"])
def test_collision_is_error_in_plan_and_apply(world: Env, target: str) -> None:
    clash = _add_clash(world)
    plan = world.run("plan", "--target", target)
    assert plan.code == 3
    msg = "\n".join(plan.err)
    assert str(world.repo / "skills" / "meta" / "alpha") in msg and str(clash / "cat" / "alpha") in msg
    before = tree_hash(world.home, exclude=LOCK)
    res = world.run("apply", "--target", target)
    assert res.code == 3
    assert tree_hash(world.home, exclude=LOCK) == before, "apply wrote despite a collision"


@pytest.mark.parametrize("target", ["claude"])
def test_collision_in_sync_keeps_dest_as_is(world: Env, target: str) -> None:
    _ok(world.run("apply", "--target", target))
    dest = world.skills(target) / "alpha"
    before = tree_hash(dest) if not dest.is_symlink() else os.readlink(dest)
    _add_clash(world)
    (world.repo / "skills" / "meta" / "eta").mkdir()
    (world.repo / "skills" / "meta" / "eta" / "SKILL.md").write_text("---\nname: eta\ndescription: eta\n---\n")
    commit_all(world.repo, "add eta")
    res = world.run("sync", "--target", target)
    assert res.code == 0
    assert any("collision" in line for line in res.err)
    after = tree_hash(dest) if not dest.is_symlink() else os.readlink(dest)
    assert after == before
    assert (world.skills(target) / "eta").exists(), "sync must still apply other entries"


@pytest.mark.parametrize("target", ["claude", "codex"])
def test_overrides_key_rejected(world: Env, target: str) -> None:
    cfg = json.loads((world.home / ".claude" / "vexjoy" / "overlays.json").read_text())
    cfg["overrides"] = {"alpha": "private"}
    write_overlays(world.home, cfg)
    for cmd in ("plan", "apply"):
        res = world.run(cmd, "--target", target)
        assert res.code == 2 and "overrides" in res.err[0]
    sync = world.run("sync", "--target", target)
    assert sync.code == 0 and "overrides" in sync.err[0]
    assert not world.root(target).exists() or target == "claude"


@pytest.mark.parametrize(("target", "mode"), [("claude", "symlink"), ("claude", "copy"), ("codex", "symlink")])
def test_dangling_owned_pruned_unowned_kept(world: Env, target: str, mode: str) -> None:
    _ok(world.run("apply", "--target", target, "--mode", mode))
    git(world.repo, "rm", "-r", "-q", "skills/content/zeta")
    commit_all(world.repo, "drop zeta")
    ghost = world.skills(target) / "ghost"
    os.symlink(str(world.work / "nowhere"), ghost)
    res = world.run("sync", "--target", target)
    _ok(res)
    assert not os.path.lexists(world.skills(target) / "zeta")
    assert os.path.islink(ghost), "unowned dangling link must be left for prune --unowned"
    trash = world.home / ".claude" / "vexjoy" / "trash"
    moved = [p for p in find_named(trash, "zeta") if "files" in p.parts]
    assert moved, "removal must land in trash"


@pytest.mark.parametrize(("target", "mode"), [("claude", "symlink"), ("claude", "copy"), ("reasonix", "symlink")])
def test_repo_move_repoints_links(world: Env, target: str, mode: str) -> None:
    _ok(world.run("apply", "--target", target, "--mode", mode))
    old = world.repo
    new = world.work / "repo-moved"
    os.rename(old, new)
    world.repo = new
    _ok(world.run("sync", "--target", target, source=new))
    for dest in world.ledger_dests(target):
        p = Path(dest)
        assert os.path.exists(p), f"dangling after move: {p}"
        if os.path.islink(p):
            assert not os.readlink(p).startswith(str(old) + os.sep)
    led = world.ledger()
    assert led["source_root"] == str(new)
    assert all(not e["source"].startswith(str(old) + os.sep) for e in led["entries"])


@pytest.mark.parametrize(("target", "mode"), [("claude", "symlink"), ("codex", "copy")])
def test_worktree_sync_makes_no_changes(world: Env, target: str, mode: str) -> None:
    _ok(world.run("apply", "--target", target, "--mode", mode))
    wt = world.work / "wt"
    git(world.repo, "worktree", "add", "-q", "-b", "wt-branch", str(wt))
    try:
        before = tree_hash(world.home)
        res = world.run("sync", "--target", target, source=wt)
        assert res.code == 0 and any("skipped" in line for line in res.out)
        assert tree_hash(world.home) == before
        assert world.run("apply", "--target", target, source=wt).code == 6
    finally:
        git(world.repo, "worktree", "remove", "--force", str(wt))
        git(world.repo, "branch", "-q", "-D", "wt-branch")


@pytest.mark.parametrize("target", ["claude"])
def test_ephemeral_source_refused_in_symlink_mode(world: Env, target: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VEXINSTALL_EPHEMERAL_PREFIXES", str(world.work))
    assert world.run("apply", "--target", target, "--mode", "symlink").code == 6
    assert not (world.home / ".claude" / "vexjoy" / "ledger.json").exists()
    sync = world.run("sync", "--target", target, "--mode", "symlink")
    assert sync.code == 0 and "skipped" in sync.out[0]
    _ok(world.run("apply", "--target", target, "--mode", "symlink", "--adopt-source"))


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("target", ["claude"])
def test_missing_overlay_root_keeps_entries_stale(world: Env, target: str, mode: str) -> None:
    _ok(world.run("apply", "--target", target, "--mode", mode))
    os.rename(world.priv, world.work / "private-skills.unmounted")
    res = world.run("sync", "--target", target)
    _ok(res)
    led = {e["dest"]: e for e in world.ledger()["entries"]}
    for name in ("private-one", "voice-v1"):
        dest = str(world.skills(target) / name)
        assert dest in led and led[dest]["status"] == "stale-source"
        assert os.path.lexists(dest)
    doctor = world.run("doctor", "--target", target)
    assert any("stale-source" in line for line in doctor.out)


@pytest.mark.parametrize(
    ("target", "mode"),
    [("claude", "symlink"), ("claude", "copy"), ("codex", "symlink"), ("reasonix", "symlink"), ("cline", "symlink")],
)
def test_uninstall_removes_owned_leaves_unowned(world: Env, target: str, mode: str) -> None:
    root = world.root(target)
    user = world.skills(target) / "user-skill"
    user.mkdir(parents=True)
    (user / "SKILL.md").write_text("---\nname: user-skill\ndescription: mine\n---\n")
    _ok(world.run("apply", "--target", target, "--mode", mode))
    owned = world.ledger_dests(target)
    assert owned
    _ok(world.run("uninstall", "--target", target))
    for dest in owned:
        assert not os.path.lexists(dest), dest
    assert (user / "SKILL.md").is_file()
    assert world.ledger_dests(target) == set()
    assert root.is_dir()


@pytest.mark.parametrize("target", ["claude"])
def test_report_and_summary_line(world: Env, target: str) -> None:
    res = world.run("sync", "--target", target)
    _ok(res)
    line = res.out[0]
    assert line.startswith(f"[sync] {target}: +"), line
    assert " skills, 0 collisions" in line
    reports = sorted((world.home / ".claude" / "vexjoy" / "reports").glob("*.json"))
    data = json.loads(reports[-1].read_text())
    assert data["command"] == "sync" and data["source_root"] == str(world.repo)
    assert set(data["diff"][target]) >= {"added", "replaced", "removed", "skipped", "collisions"}


@pytest.mark.parametrize("target", ["claude", "codex"])
def test_index_only_writes_runtime_dir_only(world: Env, target: str) -> None:
    _ok(world.run("apply", "--target", target))
    idx = world.root(target) / "vexjoy" / "index" / "skills.json"
    idx.unlink()
    before = tree_hash(world.repo, exclude=(".git",))
    _ok(world.run("sync", "--target", target, "--index-only"))
    assert idx.is_file()
    assert tree_hash(world.repo, exclude=(".git",)) == before
    assert not (world.repo / "skills" / "INDEX.local.json").exists()


def test_all_targets_resolve_to_present_runtimes(world: Env) -> None:
    (world.home / ".hermes").mkdir()
    res = world.run("apply", "--target", "all")
    _ok(res)
    assert "claude:" in res.out[0] and "hermes:" in res.out[0] and "codex:" not in res.out[0]


def test_data_dirs_are_never_touched(world: Env) -> None:
    data = world.skills("claude") / "reddit-data" / "sap"
    data.mkdir(parents=True)
    (data / "log.txt").write_text("x")
    _ok(world.run("apply", "--target", "claude"))
    _ok(world.run("uninstall", "--target", "claude"))
    assert (data / "log.txt").read_text() == "x"


def test_source_root_change_needs_adopt_source(world: Env) -> None:
    _ok(world.run("apply", "--target", "claude"))
    clone = world.work / "clone"
    shutil.copytree(world.repo, clone, symlinks=True)
    assert world.run("apply", "--target", "claude", source=clone).code == 6
    _ok(world.run("apply", "--target", "claude", "--adopt-source", source=clone))
    assert os.readlink(world.skills("claude") / "alpha").startswith(str(clone))


def _uninstalled(env: Env) -> set[str]:
    return set(env.ledger().get("uninstalled", {}))


def _add_public_skill(env: Env, name: str) -> None:
    (env.repo / "skills" / "meta" / name).mkdir(parents=True)
    (env.repo / "skills" / "meta" / name / "SKILL.md").write_text(skill_md(name))
    commit_all(env.repo, f"add {name}")


def test_uninstall_then_sync_reinstalls_nothing(world: Env) -> None:
    world.root("codex").mkdir()
    _ok(world.run("apply", "--target", "all", "--mode", "copy"))
    _ok(world.run("uninstall"))
    assert _uninstalled(world) == set(TARGETS)
    (world.home / ".hermes").mkdir()  # a runtime dir created after the uninstall stays alone too
    res = world.run("sync", "--target", "all")
    _ok(res)
    assert any("skipped uninstalled target(s) claude, codex, hermes" in e for e in res.err), res.err
    assert [e for e in world.ledger()["entries"]] == []
    for t in ("claude", "codex", "hermes"):
        assert _entries(world.skills(t)) == set(), t


def test_target_uninstall_survives_sync_all(world: Env) -> None:
    world.root("codex").mkdir()
    _ok(world.run("apply", "--target", "all", "--mode", "copy"))
    _ok(world.run("uninstall", "--target", "codex"))
    assert _uninstalled(world) == {"codex"}
    _add_public_skill(world, "fresh")
    res = world.run("sync", "--target", "all")
    _ok(res)
    assert any("skipped uninstalled target(s) codex;" in e for e in res.err), res.err
    assert (world.skills("claude") / "fresh" / "SKILL.md").is_file()
    assert world.ledger_dests("codex") == set()
    assert _entries(world.skills("codex")) == set()
    _ok(world.run("sync", "--target", "codex"))
    assert world.ledger_dests("codex") == set()


def test_apply_after_uninstall_clears_record(world: Env) -> None:
    world.root("codex").mkdir()
    _ok(world.run("apply", "--target", "all", "--mode", "copy"))
    _ok(world.run("uninstall", "--target", "codex"))
    _ok(world.run("apply", "--target", "codex", "--mode", "copy"))
    assert _uninstalled(world) == set()
    assert world.ledger_dests("codex")
    _add_public_skill(world, "fresh")
    sync = world.run("sync", "--target", "all")
    _ok(sync)
    assert not any("uninstalled" in e for e in sync.err), sync.err
    assert (world.skills("codex") / "fresh" / "SKILL.md").is_file()
    _ok(world.run("uninstall"))
    _ok(world.run("apply", "--target", "claude", "--mode", "copy"))
    assert _uninstalled(world) == set(TARGETS) - {"claude"}
    _ok(world.run("apply", "--target", "all", "--mode", "copy"))
    assert _uninstalled(world) == set()


def _add_runtime_adapters(env: Env) -> None:
    (env.repo / "hooks" / "codex-hook-adapter.py").write_text("# adapter\n")
    (env.repo / "hooks" / "agy-hook-adapter.py").write_text("# adapter\n")
    (env.repo / "scripts" / "codex-hooks-allowlist.txt").write_text(
        "SessionStart:h1.py matcher=startup class=native mode=native failure=open\n"
        "Stop:h2.py class=native mode=native failure=open\n"
    )
    commit_all(env.repo, "adapters")


USER_HOOK = {"type": "command", "command": "python3 /opt/mine/hook.py"}


def test_uninstall_removes_only_owned_external_hook_entries(world: Env) -> None:
    _add_runtime_adapters(world)
    for t in ("codex", "factory", "reasonix", "antigravity"):
        world.root(t).mkdir()
    (world.root("codex") / "config.toml").write_text('model = "x"\n')
    agy = world.root("antigravity") / "config" / "hooks.json"
    agy.parent.mkdir()
    agy.write_text(json.dumps({"mine": {"enabled": True, "Stop": [USER_HOOK]}}))
    _ok(world.run("apply", "--target", "all", "--mode", "copy"))
    factory = world.root("factory") / "settings.json"
    reasonix = world.root("reasonix") / "settings.json"
    codex = world.root("codex") / "hooks.json"
    for path in (factory, reasonix, codex):
        data = json.loads(path.read_text())
        data["model"] = "keep-me"
        data["hooks"].setdefault("Stop", []).append(
            {"matcher": "", "hooks": [USER_HOOK]} if path != reasonix else USER_HOOK
        )
        path.write_text(json.dumps(data))
    assert "vexjoy-agent" in json.loads(agy.read_text())
    config_before = (world.root("codex") / "config.toml").read_bytes()
    backups = world.home / ".claude" / "vexjoy" / "backups"
    before = {p.name for p in backups.iterdir()}

    res = world.run("uninstall")
    _ok(res)
    for path in (factory, reasonix, codex):
        data = json.loads(path.read_text())
        assert data["model"] == "keep-me", path
        blob = json.dumps(data["hooks"])
        assert "/opt/mine/hook.py" in blob, path
        assert f"{path.parent}/hooks/" not in blob and "/.claude/hooks/" not in blob, (path, blob)
    assert json.loads(agy.read_text()) == {"mine": {"enabled": True, "Stop": [USER_HOOK]}}
    assert (world.root("codex") / "config.toml").read_bytes() == config_before
    new = {p.name for p in backups.iterdir()} - before
    assert {n.rsplit(".", 1)[0] for n in new if not n.startswith("settings.")} == {
        "codex-hooks.json",
        "factory-settings.json",
        "reasonix-settings.json",
        "antigravity-hooks.json",
    }
    mtimes = {p: p.stat().st_mtime_ns for p in (factory, reasonix, codex, agy)}
    _ok(world.run("uninstall"))
    assert {p: p.stat().st_mtime_ns for p in mtimes} == mtimes, "a clean config is not rewritten"


def test_uninstall_dry_run_names_runtime_configs_and_writes_nothing(world: Env) -> None:
    _add_runtime_adapters(world)
    world.root("factory").mkdir()
    _ok(world.run("apply", "--target", "all", "--mode", "copy"))
    factory = world.root("factory") / "settings.json"
    before = (factory.read_bytes(), world.ledger())
    res = world.run("uninstall", "--dry-run")
    _ok(res)
    assert any(f"would remove owned hook entries from {factory}" in line for line in res.out), res.out
    assert (factory.read_bytes(), world.ledger()) == before
