"""vexinstall sources validation, doctor, prune, repair-repo, check-private-leak, validate-skill-names."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest

from scripts.tests.vexinstall_support import (
    ADAPTERS,
    SCRIPTS_DIR,
    TARGETS,
    Env,
    commit_all,
    common,
    find_named,
    git,
    skill_md,
    sources,
    tree_hash,
    world,
    write_overlays,
)


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SCRIPTS_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- sources


def test_public_scan_flattens_and_skips_promoted_support_data(world: Env) -> None:
    (world.repo / "skills" / "reddit-data" / "sap").mkdir(parents=True)
    pub = sources.load_public(world.repo)
    assert {s.name for s in pub.skills} == {"alpha", "beta", "gamma", "delta", "epsilon", "zeta"}
    assert {s.name for s in pub.promoted} == {"old-thing"}
    assert {s.name for s in pub.support} == {"shared-patterns", "kb", "voice-shared"}
    assert set(pub.categories) == {"meta", "process", "content"}
    assert {c.name for c in pub.commands} == {"cmd-one", "alpha"}
    assert {h.name for h in pub.hook_items} == {"h1.py", "h2.py", "h3.py"}
    assert pub.allowlists["codex"] == ["h1.py", "h2.py"]
    shutil.rmtree(world.repo / "skills" / "reddit-data")


def test_allowlist_parsing(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("# c\n\nPre:a.py k=v\nPost:b.py\nPre:a.py\nbad-line\n")
    assert sources.parse_allowlist(f) == ["a.py", "b.py"]


@pytest.mark.parametrize(
    ("cfg", "message"),
    [
        ({"overlays": [], "overrides": {}}, "overrides"),
        ({"overlays": [{"id": "x", "root": "/nonexistent-x", "overrides": ["a"]}]}, "overrides"),
        ({"overlays": [{"id": "x", "root": "/nonexistent-x", "layout": "tree"}]}, "layout"),
        ({"overlays": [{"id": "x", "root": "/n1"}, {"id": "x", "root": "/n2"}]}, "duplicate"),
        ({"overlays": [{"id": "x", "root": "rel/path"}]}, "absolute"),
        ({"overlays": [{"id": "x", "root": "/n1", "bogus": 1}]}, "unknown keys"),
    ],
)
def test_overlay_config_rejections(world: Env, cfg: dict, message: str) -> None:
    write_overlays(world.home, cfg)
    with pytest.raises(common.OverlayConfigError, match=message):
        sources.load_overlays(world.home / ".claude" / "vexjoy" / "overlays.json", world.repo, world.home)


def test_overlapping_roots_need_exclude(world: Env) -> None:
    cfg = {
        "overlays": [
            {"id": "outer", "root": str(world.priv)},
            {"id": "inner", "root": str(world.priv / "voice"), "layout": "flat"},
        ]
    }
    write_overlays(world.home, cfg)
    with pytest.raises(common.OverlayConfigError, match="exclude"):
        sources.load_overlays(world.home / ".claude" / "vexjoy" / "overlays.json", world.repo, world.home)


def test_overlay_root_inside_repo_rejected(world: Env) -> None:
    write_overlays(world.home, {"overlays": [{"id": "in", "root": str(world.repo / "skills")}]})
    res = world.run("plan", "--target", "claude")
    assert res.code == 2 and "inside the repo" in res.err[0]


def test_overlay_tilde_root_expands_against_home(world: Env) -> None:
    dest = world.home / "private-skills"
    shutil.copytree(world.priv, dest)
    write_overlays(world.home, {"overlays": [{"id": "p", "root": "~/private-skills", "exclude": ["voice"]}]})
    cfg = sources.load_overlays(world.home / ".claude" / "vexjoy" / "overlays.json", world.repo, world.home)
    assert cfg.overlays[0].root == dest
    assert {s.name for s in cfg.overlays[0].skills} == {"private-one", "private-two"}


def test_duplicate_public_names_fail_plan_and_validator(world: Env) -> None:
    (world.repo / "skills" / "content" / "alpha").mkdir()
    (world.repo / "skills" / "content" / "alpha" / "SKILL.md").write_text(skill_md("alpha"))
    commit_all(world.repo, "dup alpha")
    res = world.run("plan", "--target", "claude")
    assert res.code == 3
    validator = _load_script("validate-skill-names")
    assert validator.main(["--repo", str(world.repo)]) == 1
    git(world.repo, "rm", "-r", "-q", "skills/content/alpha")
    commit_all(world.repo, "undup")
    assert validator.main(["--repo", str(world.repo)]) == 0


def test_validate_skill_names_on_real_repo() -> None:
    validator = _load_script("validate-skill-names")
    assert validator.main(["--repo", str(SCRIPTS_DIR.parent)]) == 0


# ---------------------------------------------------------------- doctor


@pytest.mark.parametrize("target", ["claude", "codex"])
def test_doctor_clean_after_apply(world: Env, target: str) -> None:
    assert world.run("apply", "--target", target).code == 0
    res = world.run("doctor", "--target", target)
    assert res.code == 0, res.out


@pytest.mark.parametrize("target", ["claude", "hermes"])
def test_doctor_flags_dangling_category_agents_and_nonskill(world: Env, target: str) -> None:
    assert world.run("apply", "--target", target).code == 0
    skills = world.skills(target)
    os.symlink(str(world.work / "gone"), skills / "dangler")
    os.symlink(str(world.repo / "skills" / "meta"), skills / "meta")
    (skills / "reddit-data").mkdir()
    adapter = ADAPTERS[target]
    if adapter.agents:
        agents = world.root(target) / adapter.agents
        os.rename(agents, world.work / f"agents-{target}")
        os.symlink(str(world.repo / "agents"), agents)
    res = world.run("doctor", "--target", target)
    out = "\n".join(res.out)
    assert res.code == 1
    assert "dangling-link" in out and "category-in-flat-root" in out and "non-skill-dir" in out
    if adapter.agents:
        assert "whole-dir-agents-symlink" in out


def test_doctor_flags_duplicate_scan_roots_and_repo_changes(world: Env) -> None:
    assert world.run("apply", "--target", "claude").code == 0
    project = world.repo / ".claude" / "skills" / "alpha"
    project.mkdir(parents=True)
    (project / "SKILL.md").write_text(skill_md("alpha"))
    (world.home / ".claude" / "commands" / "beta.md").write_text("# stale command\n")
    tracked = world.repo / "skills" / "meta" / "beta" / "SKILL.md"
    original = tracked.read_text()
    tracked.write_text(original + "\nlocal edit\n")
    try:
        out = "\n".join(world.run("doctor", "--target", "claude").out)
        assert "duplicate-skill-name" in out and "project .claude/skills" in out
        assert "command shadowed by skill" in out
        assert "repo-tracked-modified" in out
    finally:
        tracked.write_text(original)
        shutil.rmtree(world.repo / ".claude" / "skills")


def test_doctor_flags_nested_project_scope_sources(world: Env) -> None:
    """Worktree and nested .claude/{skills,agents} dirs are extra project-scope roots."""
    assert world.run("apply", "--target", "claude").code == 0
    wt = world.repo / ".claude" / "worktrees" / "wt1" / ".claude"
    (wt / "skills" / "alpha").mkdir(parents=True)
    (wt / "skills" / "alpha" / "SKILL.md").write_text(skill_md("alpha"))
    (wt / "agents").mkdir(parents=True)
    nested = world.repo / "sub" / "pkg" / ".claude" / "skills" / "unique-nested"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text(skill_md("unique-nested"))
    try:
        res = world.run("doctor", "--target", "claude")
        found = [(f["level"], f["check"], f["path"]) for f in res.data["findings"]]
        assert ("warn", "project-scope-nested-source", str(wt / "skills")) in found
        assert ("warn", "project-scope-nested-source", str(wt / "agents")) in found
        assert ("warn", "project-scope-nested-source", str(nested.parent)) in found
        assert ("error", "duplicate-skill-name", "alpha") in found
        assert not any(c == "duplicate-skill-name" and p == "unique-nested" for _, c, p in found)
        assert res.code == 1
    finally:
        shutil.rmtree(world.repo / ".claude" / "worktrees")
        shutil.rmtree(world.repo / "sub")


def test_doctor_is_read_only(world: Env) -> None:
    assert world.run("apply", "--target", "claude").code == 0
    before = tree_hash(world.home)
    world.run("doctor", "--target", "all")
    world.run("plan", "--target", "all")
    assert tree_hash(world.home) == before


# ---------------------------------------------------------------- prune


@pytest.mark.parametrize("target", ["claude", "codex"])
def test_prune_unowned_requires_confirm(world: Env, target: str) -> None:
    assert world.run("apply", "--target", target).code == 0
    ghost = world.skills(target) / "ghost"
    os.symlink(str(world.work / "nothing"), ghost)
    listing = world.run("prune", "--unowned", "--target", target)
    assert listing.code == 0 and str(ghost) in "\n".join(listing.out)
    assert os.path.islink(ghost)
    assert world.run("prune", "--target", target).code == 2
    assert world.run("prune", "--unowned", "--confirm", "--target", target).code == 0
    assert not os.path.lexists(ghost)
    assert find_named(world.home / ".claude" / "vexjoy" / "trash", "ghost")


# ---------------------------------------------------------------- leak + repair


def test_check_private_leak_reports_path_and_name_only(world: Env, capsys: pytest.CaptureFixture[str]) -> None:
    assert world.run("apply", "--target", "claude").code == 0
    leak = _load_script("check-private-leak")
    assert leak.main(["--repo", str(world.repo), "--home", str(world.home)]) == 0
    secret_body = "PRIVATE-BODY-" + "x" * 64
    (world.priv / "priv" / "private-one" / "notes.md").write_text(secret_body)
    (world.repo / "docs").mkdir()
    (world.repo / "docs" / "copy.md").write_text(secret_body)
    (world.repo / "docs" / "mention.md").write_text("see private-two for details\n")
    commit_all(world.repo, "leak")
    capsys.readouterr()
    assert leak.main(["--repo", str(world.repo), "--home", str(world.home)]) == 1
    out = capsys.readouterr().out
    assert "docs/copy.md: content-hash 'private-one'" in out
    assert "docs/mention.md: content-name 'private-two'" in out
    assert "PRIVATE-BODY" not in out
    doctor = "\n".join(world.run("doctor", "--target", "claude").out)
    assert "repo-private-leak" in doctor and "PRIVATE-BODY" not in doctor
    git(world.repo, "rm", "-r", "-q", "docs")
    commit_all(world.repo, "unleak")


def test_repair_repo_restores_contaminated_tracked_file(world: Env) -> None:
    tracked = world.repo / "skills" / "meta" / "beta" / "SKILL.md"
    private_copy = world.priv / "priv" / "private-one" / "SKILL.md"
    tracked.write_bytes(private_copy.read_bytes())
    res = world.run("repair-repo")
    assert res.code == 1
    text = "\n".join(res.out)
    assert "skills/meta/beta/SKILL.md" in text and "modified vs HEAD" in text and "--confirm" in text
    assert tracked.read_bytes() == private_copy.read_bytes()
    fixed = world.run("repair-repo", "--confirm")
    assert fixed.code == 0, fixed.out
    assert tracked.read_bytes() != private_copy.read_bytes()
    assert git(world.repo, "log", "--oneline").count("\n") == 1, "repair-repo must never commit"


def test_plan_json_is_serializable(world: Env) -> None:
    res = world.run("plan", "--target", "all", "--json")
    json.dumps(res.data)
    assert res.data["full_adoption"] is True
