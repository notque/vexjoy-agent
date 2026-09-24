"""Phase 4 engine behavior: apply --takeover, the repo-root guard, external settings, migrate-overlays."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from scripts.tests.vexinstall_support import TARGETS, Env, commit_all, repo_hash, world

MODES = ("symlink", "copy")


def _trash_items(env: Env) -> list[dict]:
    items: list[dict] = []
    trash = env.home / ".claude" / "vexjoy" / "trash"
    for manifest in sorted(trash.glob("*/manifest.json")):
        items.extend(json.loads(manifest.read_text())["items"])
    return items


def _stale_copy(dest: Path) -> None:
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("---\nname: alpha\ndescription: stale legacy copy\n---\n")


def _last_report(env: Env) -> dict:
    reports = sorted((env.home / ".claude" / "vexjoy" / "reports").glob("*.json"))
    return json.loads(reports[-1].read_text())


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("mode", MODES)
def test_takeover_replaces_stale_copy_at_desired_dest(world: Env, target: str, mode: str) -> None:
    dest = world.skills(target) / "alpha"
    _stale_copy(dest)
    plan = world.run("plan", "--target", target, "--mode", mode)
    assert any(a["op"] == "blocked" and a["dest"] == str(dest) for a in plan.data["targets"][target]["actions"])

    res = world.run("apply", "--target", target, "--mode", mode, "--takeover")
    assert res.code == 0, res.err
    assert (dest / "SKILL.md").read_text() == (world.repo / "skills/meta/alpha/SKILL.md").read_text()
    assert str(dest) in world.ledger_dests(target)
    assert str(dest) in _last_report(world)["diff"][target]["taken_over"]
    trashed = [i for i in _trash_items(world) if i["original"] == str(dest)]
    assert len(trashed) == 1 and "takeover" in trashed[0]["reason"]
    assert "stale legacy copy" in (Path(trashed[0]["trashed"]) / "SKILL.md").read_text()


@pytest.mark.parametrize("target", TARGETS)
def test_takeover_replaces_foreign_link_and_leaves_undesired_unowned(world: Env, target: str) -> None:
    foreign = world.work / "foreign-alpha"
    _stale_copy(foreign)
    skills = world.skills(target)
    skills.mkdir(parents=True)
    os.symlink(foreign, skills / "alpha")
    stray = skills / "user-own-skill"
    _stale_copy(stray)
    stray_link = skills / "user-link"
    os.symlink(foreign, stray_link)

    res = world.run("apply", "--target", target, "--takeover")
    assert res.code == 0, res.err
    assert os.path.realpath(skills / "alpha") != os.path.realpath(foreign)
    assert (foreign / "SKILL.md").is_file(), "the link target itself is never touched"
    assert stray.is_dir() and os.readlink(stray_link) == str(foreign), "unowned entries elsewhere stay"
    assert str(stray) not in world.ledger_dests(target)


@pytest.mark.parametrize("target", TARGETS)
def test_takeover_replaces_foreign_container_link(world: Env, target: str) -> None:
    foreign = world.work / "foreign-skills"
    foreign.mkdir()
    (foreign / "keep.txt").write_text("user data\n")
    world.root(target).mkdir(parents=True, exist_ok=True)
    os.symlink(foreign, world.skills(target))

    blocked = world.run("apply", "--target", target)
    assert blocked.code == 0 and os.path.islink(world.skills(target)), "without takeover the container stays"
    res = world.run("apply", "--target", target, "--takeover")
    assert res.code == 0, res.err
    assert world.skills(target).is_dir() and not world.skills(target).is_symlink()
    assert (world.skills(target) / "alpha").exists()
    assert (foreign / "keep.txt").read_text() == "user data\n"


@pytest.mark.parametrize("target", TARGETS)
def test_sync_never_takes_over(world: Env, target: str) -> None:
    dest = world.skills(target) / "alpha"
    _stale_copy(dest)
    res = world.run("sync", "--target", target, "--takeover")
    assert res.code == 0
    assert "stale legacy copy" in (dest / "SKILL.md").read_text()
    assert _trash_items(world) == []


@pytest.mark.parametrize("target", TARGETS)
def test_takeover_is_restorable(world: Env, target: str) -> None:
    dest = world.skills(target) / "alpha"
    _stale_copy(dest)
    assert world.run("apply", "--target", target, "--takeover", "--mode", "copy").code == 0
    ts = sorted((world.home / ".claude" / "vexjoy" / "trash").iterdir())[-1].name
    res = world.run("restore-trash", ts)
    assert res.code == 0, res.err
    assert "stale legacy copy" in (dest / "SKILL.md").read_text()


# --------------------------------------------------------------------------
# Repo-root guard: HOME inside the repo never produces a single write.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("command", ["plan", "apply", "sync", "uninstall", "prune"])
def test_home_inside_repo_is_refused(world: Env, command: str) -> None:
    before = repo_hash(world.repo)
    world.home = world.repo
    extra = ["--unowned", "--confirm"] if command == "prune" else []
    res = world.run(command, "--target", "all", *extra)
    assert res.code == 4, (res.out, res.err)
    assert "HOME" in res.err[0] and "inside" in res.err[0]
    assert repo_hash(world.repo) == before
    assert not (world.repo / ".claude" / "vexjoy").exists()


@pytest.mark.parametrize("target", [t for t in TARGETS if t != "claude"])
def test_runtime_root_linked_into_repo_is_refused(world: Env, target: str) -> None:
    before = repo_hash(world.repo)
    os.symlink(world.repo / "skills", world.root(target))
    res = world.run("apply", "--target", "all")
    assert res.code == 4, (res.out, res.err)
    assert f"{target} root" in res.err[0]
    assert repo_hash(world.repo) == before


# --------------------------------------------------------------------------
# External settings (codex hooks.json + config.toml, factory/reasonix settings.json)
# --------------------------------------------------------------------------


def _add_codex_adapter(env: Env) -> None:
    (env.repo / "hooks" / "codex-hook-adapter.py").write_text("# adapter\n")
    (env.repo / "scripts" / "codex-hooks-allowlist.txt").write_text(
        "SessionStart:h1.py matcher=startup class=native mode=native failure=open\n"
        "Stop:h2.py class=native mode=native failure=open\n"
    )
    commit_all(env.repo, "adapter")


@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib requires Python 3.11+")
def test_codex_external_files_generated_and_idempotent(world: Env) -> None:
    import tomllib

    _add_codex_adapter(world)
    root = world.root("codex")
    root.mkdir()
    (root / "config.toml").write_text('model = "x"\n')
    assert world.run("apply", "--target", "codex").code == 0
    hooks = json.loads((root / "hooks.json").read_text())
    cmds = [h["command"] for groups in hooks["hooks"].values() for g in groups for h in g["hooks"]]
    assert any(f"{root}/hooks/h1.py" in c for c in cmds) and any(f"{root}/hooks/h2.py" in c for c in cmds)
    cfg = tomllib.loads((root / "config.toml").read_text())
    assert cfg["model"] == "x" and cfg["features"]["hooks"] is True
    assert oct((root / "hooks.json").stat().st_mode & 0o777) == "0o600"
    mtimes = {p: p.stat().st_mtime_ns for p in (root / "hooks.json", root / "config.toml")}
    assert world.run("apply", "--target", "codex").code == 0
    assert {p: p.stat().st_mtime_ns for p in mtimes} == mtimes, "unchanged files are not rewritten"
    assert _last_report(world)["external"]["written"] == []


def test_codex_missing_adapter_is_a_warning_not_a_failure(world: Env) -> None:
    _add_codex_adapter(world)
    (world.repo / "hooks" / "codex-hook-adapter.py").unlink()
    commit_all(world.repo, "drop adapter")
    world.root("codex").mkdir()
    res = world.run("apply", "--target", "codex")
    assert res.code == 0
    assert any("codex-hook-adapter.py" in e for e in res.err)
    assert not (world.root("codex") / "hooks.json").exists()


def test_factory_settings_rewrites_paths_and_keeps_user_keys(world: Env) -> None:
    root = world.root("factory")
    root.mkdir()
    (root / "settings.json").write_text(json.dumps({"model": "keep-me", "hooks": {"Old": []}}))
    assert world.run("apply", "--target", "factory").code == 0
    data = json.loads((root / "settings.json").read_text())
    assert data["model"] == "keep-me"
    blob = json.dumps(data["hooks"])
    assert "/.factory/hooks/h1.py" in blob and "/.claude/" not in blob and "Old" not in data["hooks"]
    backups = list((world.home / ".claude" / "vexjoy" / "backups").glob("factory-settings.json.*"))
    assert len(backups) == 1 and json.loads(backups[0].read_text())["model"] == "keep-me"


def test_reasonix_settings_from_allowlist_honors_profile(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    root = world.root("reasonix")
    root.mkdir()
    assert world.run("apply", "--target", "reasonix").code == 0
    data = json.loads((root / "settings.json").read_text())
    assert f"{root}/hooks/h1.py" in json.dumps(data["hooks"])
    profile = world.work / "profile.yaml"
    profile.write_text("disabled:\n  hooks:\n    - h1.py\n")
    monkeypatch.setenv("VEXJOY_INSTALL_PROFILE", str(profile))
    assert world.run("apply", "--target", "reasonix").code == 0
    assert "h1.py" not in json.dumps(json.loads((root / "settings.json").read_text())["hooks"])


def test_plan_reports_external_changes_without_writing(world: Env) -> None:
    root = world.root("factory")
    root.mkdir()
    res = world.run("plan", "--target", "factory")
    assert any("external" in n and "would write" in n for n in res.data["notes"])
    assert not (root / "settings.json").exists()


# --------------------------------------------------------------------------
# migrate-overlays (install.sh --migrate-overlays)
# --------------------------------------------------------------------------


def test_migrate_overlays_writes_config_from_legacy_roots(world: Env) -> None:
    (world.home / ".claude" / "vexjoy" / "overlays.json").unlink()
    (world.home / "private-skills" / "voice" / "v").mkdir(parents=True)
    (world.home / "private-skills-jev-workbench").mkdir()
    dry = world.run("migrate-overlays", "--dry-run")
    assert dry.code == 0 and not (world.home / ".claude" / "vexjoy" / "overlays.json").exists()
    res = world.run("migrate-overlays")
    assert res.code == 0, res.err
    cfg = json.loads((world.home / ".claude" / "vexjoy" / "overlays.json").read_text())
    assert [o["id"] for o in cfg["overlays"]] == ["private", "voices", "workbench"]
    assert "overrides" not in cfg
    assert world.run("migrate-overlays").out[0].startswith("[migrate-overlays] unchanged")


@pytest.mark.parametrize("has_existing_config", [False, True])
def test_migrate_overlays_validates_before_replacing_config(
    world: Env, monkeypatch: pytest.MonkeyPatch, has_existing_config: bool
) -> None:
    path = world.home / ".claude" / "vexjoy" / "overlays.json"
    prior = b'{"overlays": []}\n'
    if has_existing_config:
        path.write_bytes(prior)
    else:
        path.unlink(missing_ok=True)

    outer = world.home / "private-skills"
    inner = outer / "workbench"
    inner.mkdir(parents=True)
    invalid = {
        "overlays": [
            {"id": "private", "root": str(outer), "layout": "category"},
            {"id": "workbench", "root": str(inner), "layout": "flat"},
        ]
    }
    monkeypatch.setattr("vexinstall.migrate.build_overlays", lambda *_: (invalid, []))
    backups = world.home / ".claude" / "vexjoy" / "backups"
    backups_before = set(backups.glob("overlays.*.json")) if backups.exists() else set()

    result = world.run("migrate-overlays")

    assert result.code != 0 and any("inside" in message for message in result.err)
    if has_existing_config:
        assert path.read_bytes() == prior
    else:
        assert not path.exists()
    backups_after = set(backups.glob("overlays.*.json")) if backups.exists() else set()
    assert backups_after == backups_before
    assert not list(path.parent.glob(".overlays-validation-*"))


def test_tree_hash_is_order_independent(tmp_path: Path) -> None:
    """A walk yields a dir's files before its subdirs ("b.md" then "a/x.md"); the hash must not care."""
    from scripts.vexinstall.common import iter_tree_files, tree_sha256

    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.md").write_text("x")
    (tmp_path / "b.md").write_text("y")
    files = list(iter_tree_files(tmp_path))
    assert files != sorted(files), "fixture must hit the walk/sort mismatch"
    assert tree_sha256(tmp_path) == tree_sha256(tmp_path, files)
