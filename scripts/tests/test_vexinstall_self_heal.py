"""The install repairs what stranded a session on 2026-11-17, without a terminal outside Claude Code.

B: a hook registered ahead of its file. C: dangling links left by older installs, counted
toward the mass-removal cap. D: old-layout category entries in flat skills roots. E: a ledger
clone that was never pulled, with nothing saying so. (A, pyrun.sh, is in hooks/tests.)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

# vexinstall_support puts scripts/ on sys.path, so vexinstall comes through it, never imported first.
from scripts.tests.vexinstall_support import (
    GIT_ENV,
    Env,
    Result,
    commit_all,
    git,
    plan,
    world,
)

CATEGORY_DIR_REASON = plan.CATEGORY_DIR_REASON
CATEGORY_LINK_REASON = plan.CATEGORY_LINK_REASON
DANGLING_REASON = plan.DANGLING_REASON

GATE = "pretool-commit-verification-gate.py"
GATE_CMD = f'sh "$HOME/.claude/hooks/lib/pyrun.sh" "$HOME/.claude/hooks/{GATE}"'

__all__ = ["world"]


def _ok(res: Result) -> None:
    assert res.code == 0, (res.out, res.err)


def _trash_items(env: Env) -> list[dict]:
    items: list[dict] = []
    for manifest in sorted((env.home / ".claude" / "vexjoy" / "trash").glob("*/manifest.json")):
        items.extend(json.loads(manifest.read_text())["items"])
    return items


def _last_report(env: Env) -> dict:
    reports = sorted((env.home / ".claude" / "vexjoy" / "reports").glob("*.json"))
    return json.loads(reports[-1].read_text())


def _register_gate(settings_path: Path) -> None:
    data = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    data.setdefault("hooks", {}).setdefault("PreToolUse", []).append(
        {"matcher": "Bash", "hooks": [{"type": "command", "command": GATE_CMD}]}
    )
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2))


def _commands(settings_path: Path) -> list[str]:
    hooks = json.loads(settings_path.read_text()).get("hooks", {})
    return [e["command"] for groups in hooks.values() for g in groups for e in g["hooks"]]


def _add_account(env: Env, name: str) -> Path:
    cfg = env.home / ".claude-accounts" / name
    cfg.mkdir(parents=True)
    reg = env.home / ".claude-accounts" / "accounts.json"
    reg.write_text(json.dumps({name: {"alias": f"c-{name}", "config_dir": str(cfg)}}))
    return cfg


def _clone(src: Path, dest: Path) -> Path:
    subprocess.run(["git", "clone", "-q", str(src), str(dest)], check=True, env={**os.environ, **GIT_ENV})
    return dest


# B: never register a hook whose file is not deployed


def test_apply_leaves_out_a_registration_whose_hook_file_is_not_deployed(world: Env) -> None:
    """The repo registers the gate but its hooks/ lacks the file: neither ~/.claude nor a profile gets it."""
    _register_gate(world.repo / ".claude" / "settings.json")
    commit_all(world.repo, "register gate without its file")
    cfg = _add_account(world, "max2")

    res = world.run("apply", "--target", "claude")

    _ok(res)
    assert not any(GATE in c for c in _commands(world.home / ".claude" / "settings.json"))
    assert not any(GATE in c for c in _commands(cfg / "settings.json"))
    assert any('"$HOME/.claude/hooks/h1.py"' in c for c in _commands(cfg / "settings.json")), "deployed hooks stay"
    report = _last_report(world)
    assert any(GATE in x for x in report["settings"]["not_registered"])
    assert any("left out because the hook file is not deployed" in e for e in res.err), res.err


def test_apply_removes_an_existing_registration_whose_hook_file_is_gone(world: Env) -> None:
    _ok(world.run("apply", "--target", "claude"))
    _register_gate(world.repo / ".claude" / "settings.json")
    commit_all(world.repo, "register gate without its file")
    _register_gate(world.home / ".claude" / "settings.json")

    _ok(world.run("apply", "--target", "claude"))

    assert not any(GATE in c for c in _commands(world.home / ".claude" / "settings.json"))


def test_apply_registers_the_hook_once_its_file_ships(world: Env) -> None:
    _register_gate(world.repo / ".claude" / "settings.json")
    (world.repo / "hooks" / GATE).write_text("# gate\n")
    commit_all(world.repo, "gate with its file")

    _ok(world.run("apply", "--target", "claude"))

    assert any(GATE in c for c in _commands(world.home / ".claude" / "settings.json"))


def test_doctor_errors_on_a_registered_hook_whose_file_is_missing(world: Env) -> None:
    _ok(world.run("apply", "--target", "claude"))
    _register_gate(world.home / ".claude" / "settings.json")

    res = world.run("doctor", "--target", "claude")

    hits = [f for f in res.data["findings"] if f["check"] == "hook-file-missing"]
    assert res.code != 0
    assert hits and hits[0]["level"] == "error" and GATE in hits[0]["detail"]
    assert "pull --ff-only" in hits[0]["detail"]


def test_doctor_errors_when_the_session_checkout_registers_a_hook_the_ledger_clone_lacks(
    world: Env, tmp_path: Path
) -> None:
    """Today's root cause: the checkout's project settings ran ahead of the installed clone's hooks."""
    clone = _clone(world.repo, tmp_path / "share" / "vexjoy-agent")
    _ok(world.run("apply", "--target", "claude", source=clone))
    _register_gate(world.repo / ".claude" / "settings.json")
    (world.repo / "hooks" / GATE).write_text("# gate\n")
    commit_all(world.repo, "add gate")

    res = world.run("doctor", "--target", "claude")

    hits = [f for f in res.data["findings"] if f["check"] == "hook-file-missing"]
    assert [h["path"] for h in hits] == [str(world.repo / ".claude" / "settings.json")]
    sync = world.run("sync", "--target", "claude")
    assert any("registered hook file(s) not deployed" in line for line in sync.out), sync.out


# C: dangling links into a toolkit source are cleaned up, outside the cap


def _dangling(dest_dir: Path, names: list[str], into: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for n in names:
        link = dest_dir / n
        os.symlink(into / n, link)
        out.append(link)
    return out


def test_apply_cleans_dangling_toolkit_links_without_tripping_the_cap(world: Env, tmp_path: Path) -> None:
    """12 links into an old checkout path that no longer exists: before, the cap stopped the install (exit 5)."""
    old_checkout = tmp_path / "pgh" / "vexjoy-agent" / "skills" / "meta"
    links = _dangling(world.skills("antigravity"), [f"gone-{i:02d}" for i in range(12)], old_checkout)
    foreign = _dangling(world.skills("antigravity"), ["user-link"], tmp_path / "elsewhere")[0]

    res = world.run("apply", "--target", "antigravity", "--takeover")

    _ok(res)
    assert not any(os.path.lexists(p) for p in links)
    assert os.path.islink(foreign), "a dangling link outside every toolkit root stays"
    trashed = {i["original"]: i["reason"] for i in _trash_items(world)}
    assert all(trashed[str(p)] == DANGLING_REASON for p in links)
    cleaned = _last_report(world)["diff"]["antigravity"]["cleaned"]
    assert {c["dest"] for c in cleaned} >= {str(p) for p in links}
    assert any("cleaned" in line and "restore-trash" in line for line in res.out), res.out


def test_sync_cleans_dangling_links_into_the_source_and_restore_trash_undoes_it(world: Env) -> None:
    _ok(world.run("apply", "--target", "claude"))
    links = _dangling(world.skills("claude"), ["retired-a", "retired-b"], world.repo / "skills" / "meta")

    _ok(world.run("sync", "--target", "claude"))

    assert not any(os.path.lexists(p) for p in links)
    ts = _last_report(world)["ts"]
    _ok(world.run("restore-trash", ts))
    assert all(os.path.islink(p) for p in links)


def test_sync_cleans_links_into_a_past_source_root(world: Env, tmp_path: Path) -> None:
    """A root the ledger used before --adopt-source counts as toolkit, whatever its name."""
    old = tmp_path / "old-root"
    _ok(world.run("apply", "--target", "claude"))
    ledger_path = world.home / ".claude" / "vexjoy" / "ledger.json"
    data = json.loads(ledger_path.read_text())
    data["past_roots"] = [str(old)]
    ledger_path.write_text(json.dumps(data))
    link = _dangling(world.skills("claude"), ["from-old-root"], old / "skills" / "x")[0]

    _ok(world.run("sync", "--target", "claude"))

    assert not os.path.lexists(link)


def test_adopt_source_records_the_old_root(world: Env, tmp_path: Path) -> None:
    clone = _clone(world.repo, tmp_path / "share" / "vexjoy-agent")
    _ok(world.run("apply", "--target", "claude", source=clone))
    _ok(world.run("apply", "--target", "claude", "--adopt-source"))
    ledger = world.ledger()
    assert ledger["source_root"] == str(world.repo.resolve())
    assert ledger["past_roots"] == [str(clone.resolve())]


# D: legacy category entries in flat skills roots


def _category_dir(root: Path, name: str, skill: str) -> Path:
    """A user-authored skill inside a dir named *name*."""
    d = root / name / skill
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {skill}\ndescription: my own skill\n---\n")
    return root / name


def _source_copy(world: Env, root: Path, cat: str, skill: str) -> Path:
    """A byte-identical copy of ``<repo>/skills/<cat>/<skill>`` at ``<root>/<cat>/<skill>``."""
    shutil.copytree(world.repo / "skills" / cat / skill, root / cat / skill)
    return root / cat


def test_apply_removes_category_links_and_trashes_source_identical_category_dirs(world: Env) -> None:
    codex = world.skills("codex")
    codex.mkdir(parents=True)
    link = codex / "meta"
    os.symlink(world.repo / "skills" / "meta", link)
    real = _source_copy(world, codex, "process", "gamma")
    user_dir = _category_dir(codex, "my-own-stuff", "mine")

    res = world.run("apply", "--target", "codex", "--takeover")

    _ok(res)
    assert not os.path.lexists(link) and not os.path.lexists(real)
    assert (user_dir / "mine" / "SKILL.md").is_file(), "a category name the source never had stays"
    trashed = {i["original"]: i for i in _trash_items(world)}
    assert trashed[str(link)]["reason"] == CATEGORY_LINK_REASON
    assert trashed[str(real)]["reason"] == CATEGORY_DIR_REASON
    assert (Path(trashed[str(real)]["trashed"]) / "gamma" / "SKILL.md").is_file()
    doctor = world.run("doctor", "--target", "codex")
    flagged = {f["path"] for f in doctor.data["findings"] if f["check"] == "category-in-flat-root"}
    assert flagged == {str(user_dir)}

    _ok(world.run("restore-trash", _last_report(world)["ts"]))
    assert (real / "gamma" / "SKILL.md").is_file()


def test_apply_keeps_a_user_skill_in_a_dir_named_like_a_category(world: Env) -> None:
    """``content`` is a source category, but my-own-skill is not in the source: nothing moves."""
    codex = world.skills("codex")
    codex.mkdir(parents=True)
    user_dir = _category_dir(codex, "content", "my-own-skill")
    shutil.copytree(world.repo / "skills" / "content" / "epsilon", user_dir / "epsilon")

    _ok(world.run("apply", "--target", "codex", "--takeover"))

    assert (user_dir / "my-own-skill" / "SKILL.md").read_text().endswith("my own skill\n---\n")
    assert (user_dir / "epsilon" / "SKILL.md").is_file()
    assert str(user_dir) not in {i["original"] for i in _trash_items(world)}
    prune = world.run("prune", "--unowned", "--target", "codex")
    assert any(str(user_dir) in line for line in prune.out), "still reported for a manual prune"


def test_apply_keeps_a_category_copy_with_one_modified_file(world: Env) -> None:
    codex = world.skills("codex")
    codex.mkdir(parents=True)
    real = _source_copy(world, codex, "process", "delta")
    ref = real / "delta" / "references" / "ref.md"
    ref.write_text("my notes\n")

    _ok(world.run("apply", "--target", "codex", "--takeover"))

    assert ref.read_text() == "my notes\n"
    assert str(real) not in {i["original"] for i in _trash_items(world)}


def test_sync_keeps_a_live_category_link_into_another_clone(world: Env, tmp_path: Path) -> None:
    """A deliberate link to a second dev clone matches the legacy pattern but no ledger root."""
    other = _clone(world.repo, tmp_path / "dev2" / "vexjoy-agent")
    _ok(world.run("apply", "--target", "codex"))
    link = world.skills("codex") / "meta"
    os.symlink(other / "skills" / "meta", link)

    _ok(world.run("sync", "--target", "codex"))
    _ok(world.run("apply", "--target", "codex"))

    assert os.readlink(link) == str(other / "skills" / "meta")


def test_sync_removes_category_links_but_leaves_real_category_dirs(world: Env) -> None:
    _ok(world.run("apply", "--target", "codex"))
    codex = world.skills("codex")
    link = codex / "meta"
    os.symlink(world.repo / "skills" / "meta", link)
    real = _source_copy(world, codex, "process", "gamma")

    _ok(world.run("sync", "--target", "codex"))

    assert not os.path.lexists(link)
    assert (real / "gamma" / "SKILL.md").is_file(), "sync never moves a real dir"


def test_many_category_entries_do_not_trip_the_cap(world: Env) -> None:
    _ok(world.run("apply", "--target", "codex"))
    codex = world.skills("codex")
    for cat in ("meta", "process", "content"):
        os.symlink(world.repo / "skills" / cat, codex / f"{cat}")
    for i in range(10):
        os.symlink(world.repo / "skills" / "meta" / f"gone-{i}", codex / f"gone-{i}")

    res = world.run("apply", "--target", "codex")

    _ok(res)
    assert not any(os.path.lexists(codex / c) for c in ("meta", "process", "content"))


# E: a ledger clone that is behind says so, with the fix


def test_sync_warns_when_the_ledger_clone_is_behind_the_session_checkout(world: Env, tmp_path: Path) -> None:
    """The session checkout pulled merged work; the ledger clone did not."""
    clone = _clone(world.repo, tmp_path / "share" / "vexjoy-agent")
    checkout = _clone(world.repo, tmp_path / "pgh" / "vexjoy-agent")
    _ok(world.run("apply", "--target", "claude", source=clone))
    (world.repo / "hooks" / "h4.py").write_text("# new\n")
    commit_all(world.repo, "new hook")
    git(checkout, "pull", "-q", "--ff-only")

    res = world.run("sync", "--target", "claude", source=checkout)

    assert any("skipped" in line and "ledger source_root" in line for line in res.out), res.out
    want = f"git -C {clone.resolve()} pull --ff-only && {clone.resolve()}/install.sh"
    stale = [line for line in res.out if "behind the checkout" in line]
    assert len(stale) == 1 and want in stale[0], res.out


def test_no_stale_warning_for_a_feature_branch_ahead_of_a_current_clone(world: Env, tmp_path: Path) -> None:
    """Unmerged work in a feature branch or worktree is not news the installed clone missed."""
    clone = _clone(world.repo, tmp_path / "share" / "vexjoy-agent")
    checkout = _clone(world.repo, tmp_path / "pgh" / "vexjoy-agent")
    _ok(world.run("apply", "--target", "claude", source=clone))
    git(checkout, "checkout", "-q", "-b", "feature")
    (checkout / "hooks" / "h4.py").write_text("# wip\n")
    commit_all(checkout, "wip")

    res = world.run("sync", "--target", "claude", source=checkout)

    assert not [line for line in res.out if "behind" in line], res.out
    git(checkout, "push", "-q", "-u", "origin", "feature")  # pushed but not merged: still no warning
    res = world.run("sync", "--target", "claude", source=checkout)
    assert not [line for line in res.out if "behind" in line], res.out


def test_sync_and_doctor_warn_when_the_ledger_clone_is_behind_its_upstream(world: Env, tmp_path: Path) -> None:
    clone = _clone(world.repo, tmp_path / "share" / "vexjoy-agent")
    _ok(world.run("apply", "--target", "claude", source=clone))
    (world.repo / "hooks" / "h4.py").write_text("# new\n")
    commit_all(world.repo, "new hook")
    git(clone, "fetch", "-q")  # the tracking ref moves; the sync itself never fetches

    res = world.run("sync", "--target", "claude", source=clone)

    stale = [line for line in res.out if "behind its upstream" in line]
    assert len(stale) == 1 and "pull --ff-only" in stale[0], res.out
    doctor = world.run("doctor", "--target", "claude", source=clone)
    assert [f for f in doctor.data["findings"] if f["check"] == "stale-source-root"]


def test_no_stale_warning_when_the_clone_is_current(world: Env, tmp_path: Path) -> None:
    clone = _clone(world.repo, tmp_path / "share" / "vexjoy-agent")
    _ok(world.run("apply", "--target", "claude", source=clone))
    res = world.run("sync", "--target", "claude", source=clone)
    assert not [line for line in res.out if "behind" in line], res.out


# F: agents retired by plans/009 leave dangling links that sync cleans, outside the cap


def test_sync_cleans_retired_agent_links_without_tripping_the_cap(world: Env) -> None:
    """Before: sync refused the whole plan ('mass-removal cap exceeded') and synced nothing."""
    from routing_index_merge import RETIRED_AGENTS

    names = sorted(RETIRED_AGENTS)[:12]
    for n in names:
        (world.repo / "agents" / f"{n}.md").write_text(f"---\nname: {n}\ndescription: {n}\n---\n# {n}\n")
    commit_all(world.repo, "add agents")
    _ok(world.run("apply", "--target", "claude"))
    links = [world.root("claude") / "agents" / f"{n}.md" for n in names]
    assert all(os.path.islink(p) for p in links)

    git(world.repo, "rm", "-q", *[f"agents/{n}.md" for n in names])
    commit_all(world.repo, "retire agents")
    res = world.run("sync", "--target", "claude")

    _ok(res)
    assert not any("mass-removal cap" in line for line in res.err), res.err
    assert not any(os.path.lexists(p) for p in links)
    trashed = {i["original"]: i["reason"] for i in _trash_items(world)}
    assert all(trashed[str(p)] == plan.RETIRED_REASON for p in links)
