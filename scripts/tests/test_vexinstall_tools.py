"""vexinstall sources validation, doctor, prune, repair-repo, check-private-leak, validate-skill-names."""

from __future__ import annotations

import importlib.util
import json
import os
import re
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
    gitutil,
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
    assert {c.name for c in pub.commands} == {"cmd-one"}  # commands/alpha.md shadows skill alpha
    assert {h.name for h in pub.hook_items} == {"h1.py", "h2.py", "h3.py"}
    assert pub.allowlists["codex"] == ["h1.py", "h2.py"]
    shutil.rmtree(world.repo / "skills" / "reddit-data")


UNTRACKED = ("agents/z-wip.md", "commands/cmd-wip.md", "hooks/h-wip.py", "hooks/lib/wip.py", "scripts/wip_out.json")


@pytest.mark.parametrize("target", ["claude", "codex", "hermes"])
def test_untracked_top_level_items_never_install(world: Env, target: str) -> None:
    # A skill needs a committed SKILL.md; agents, commands, hooks and scripts follow the same rule, so
    # work in progress (or a stray output file such as scripts/jev2_out.json) never lands in a runtime.
    for rel in UNTRACKED:
        (world.repo / rel).write_text("---\nname: z-wip\ndescription: untracked work in progress\n---\n")
    (world.repo / "skills" / "INDEX.json").write_text("{}\n")  # generated and gitignored, as in the repo
    try:
        pub = sources.load_public(world.repo)
        assert "z-wip.md" not in {a.name for a in pub.agents}
        assert "cmd-wip" not in {c.name for c in pub.commands}
        assert "h-wip.py" not in {h.name for h in pub.hook_items}
        assert "wip.py" not in {h.name for h in pub.hook_lib_items}
        assert "wip_out.json" not in {s.name for s in pub.script_items}
        assert {"s1.py", "s2.py", "tool"} <= {s.name for s in pub.script_items}
        assert world.run("apply", "--target", target).code == 0
        installed = {Path(d).name for d in world.ledger_dests(target)}
        assert not installed & {"z-wip.md", "cmd-wip.md", "h-wip.py", "wip.py", "wip_out.json"}, installed
        index_dir = world.root(target) / "vexjoy" / "index"
        assert set(json.loads((index_dir / "skills.json").read_text())["skills"]) >= {"alpha", "zeta"}
        if ADAPTERS[target].agents:
            assert "z-wip" not in json.loads((index_dir / "agents.json").read_text())["agents"]
    finally:
        for rel in (*UNTRACKED, "skills/INDEX.json"):
            (world.repo / rel).unlink()


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


SKILL_CALL = re.compile(r"(?i)call the Skill tool with `([a-z0-9][a-z0-9-]*)`")


def stale_command_calls(root: Path, skill_dirs: set[str]) -> list[tuple[str, str]]:
    """(command, skill) for each shipped command that calls a skill with no SKILL.md."""
    return [
        (p.name, name)
        for p in sorted((root / "commands").glob("*.md"))
        for name in SKILL_CALL.findall(p.read_text(encoding="utf-8"))
        if name not in skill_dirs
    ]


def retro_unknown_subcommands(root: Path) -> set[str] | None:
    """learning-db.py subcommands commands/retro.md runs that the CLI lacks; None when it runs none."""
    cli = (root / "scripts" / "learning-db.py").read_text(encoding="utf-8")
    known = set(re.findall(r'add_parser\(\s*"([a-z][a-z-]*)"', cli))
    named = set(re.findall(r"learning-db\.py ([a-z][a-z-]*)", (root / "commands" / "retro.md").read_text("utf-8")))
    return (named - known) if named else None


def test_shipped_commands_call_skills_that_exist() -> None:
    # Every runtime gets commands/. /generate-claudemd and /reddit-moderate called skills since folded
    # into toolkit and content; /retro called a skill retired with the learning-capture loop.
    root = SCRIPTS_DIR.parent
    gitutil.clear_cache()
    skill_dirs = {
        Path(rel).parent.name
        for rel in gitutil.tracked_files(root)
        if rel.startswith("skills/") and rel.endswith("/SKILL.md")
    }
    assert stale_command_calls(root, skill_dirs) == []
    assert retro_unknown_subcommands(root) == set()


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


# ---------------------------------------------------------------- doctor: legacy post-merge hook

INSTALL_SH = SCRIPTS_DIR.parent / "install.sh"
LEGACY_HEADER = "# Written by vexjoy-agent install.sh — auto-syncs new items after git pull.\n"
# The add-only loop the pre-engine install.sh wrote (5ea20993~1), trimmed.
LEGACY_POST_MERGE = (
    "#!/usr/bin/env bash\n"
    + LEGACY_HEADER
    + """REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
for runtime_dir in "$HOME/.claude" "$HOME/.codex" "$HOME/.gemini"; do
  [ -d "$runtime_dir" ] || continue
  for component in agents skills hooks commands scripts; do
    for item in "$REPO_DIR/$component"/*; do
      dst="$runtime_dir/$component/$(basename "$item")"
      [ -e "$dst" ] && continue  # already present; skip
      ln -s "$item" "$dst"
    done
  done
done
exit 0
"""
)
# Advice for a hook carrying install.sh's marker, and for one without it.
MARKED = "delete it (the SessionStart sync keeps installs current)"
UNMARKED = "remove its ln -s loop"


@pytest.fixture
def hook_world(world: Env, monkeypatch: pytest.MonkeyPatch) -> Env:
    """World whose git reads no system config and an empty global one, so a host core.hooksPath stays out."""
    (world.work / "global.gitconfig").write_text("")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(world.work / "global.gitconfig"))
    return world


def _install_sh_post_merge() -> str:
    """The post-merge body install.sh writes today (its _write_git_hook heredoc)."""
    text = INSTALL_SH.read_text(encoding="utf-8")
    m = re.search(r"_write_git_hook post-merge << 'HOOK'\n(.*?)\nHOOK\n", text, re.DOTALL)
    assert m, "post-merge heredoc not found in install.sh"
    return m.group(1)


def _write_hook(hooks: Path, body: str) -> Path:
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "post-merge"
    hook.write_text(body, encoding="utf-8", newline="\n")
    hook.chmod(0o755)
    return hook


def _hook_findings(env: Env, source: Path | None = None) -> list[dict]:
    res = env.run("doctor", "--target", "claude", source=source)
    return [f for f in res.data["findings"] if f["check"] == "legacy-git-hook"]


def _same(a: str | Path | None, b: Path) -> bool:
    return a is not None and os.path.realpath(a) == os.path.realpath(b)


@pytest.mark.parametrize(
    ("body", "advice"),
    [
        pytest.param(LEGACY_POST_MERGE, MARKED, id="legacy"),
        pytest.param(LEGACY_POST_MERGE.replace(LEGACY_HEADER, ""), UNMARKED, id="header-removed"),
        pytest.param(
            f'#!/bin/sh\n{LEGACY_HEADER}cp -R "$REPO_DIR"/skills/* "$HOME/.claude/skills/"\n',
            MARKED,
            id="header-only",
        ),
        pytest.param(
            LEGACY_POST_MERGE.replace(
                "exit 0\n", 'python3 -m vexinstall sync --target all --source-root "$REPO_DIR"\nexit 0\n'
            ),
            MARKED,
            id="legacy-loop-plus-engine-sync",
        ),
    ],
)
def test_doctor_flags_legacy_post_merge_hook(hook_world: Env, body: str, advice: str) -> None:
    hook = _write_hook(hook_world.repo / ".git" / "hooks", body)
    before = hook.read_bytes()
    res = hook_world.run("doctor", "--target", "claude")
    found = [f for f in res.data["findings"] if f["check"] == "legacy-git-hook"]
    assert [(f["level"], f["target"]) for f in found] == [("error", "repo")]
    assert _same(found[0]["path"], hook)
    assert advice in found[0]["detail"] and "the engine stops updating them" in found[0]["detail"]
    assert any("legacy-git-hook" in line for line in res.out), res.out
    assert hook.read_bytes() == before, "doctor must never rewrite the hook"


def test_doctor_passes_the_install_sh_post_merge(hook_world: Env) -> None:
    _write_hook(hook_world.repo / ".git" / "hooks", _install_sh_post_merge())
    assert _hook_findings(hook_world) == []


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(None, id="no-hook"),
        pytest.param('#!/bin/sh\ngit lfs post-merge "$@"\n', id="git-lfs"),
        pytest.param('#!/bin/sh\nln -sf "$PWD/build/out" "$PWD/dist/latest"\n', id="ln-outside-runtime-roots"),
        pytest.param("#!/bin/sh\n# never ln -s into ~/.claude from here\nmake docs\n", id="ln-in-comment"),
        pytest.param("#!/bin/sh\nmake docs  # never ln -s into ~/.claude\n", id="ln-in-trailing-comment"),
        pytest.param(
            '#!/bin/sh\nln -sf "$HOME/dotfiles/CLAUDE.md" "$HOME/.claude/CLAUDE.md"\n', id="own-file-into-runtime-root"
        ),
        pytest.param(
            '#!/bin/sh\nln -sf "$PWD/tools/x" "$HOME/bin/x"\n[ -f "$HOME/.claude/settings.json" ] && echo ok\n',
            id="runtime-file-check",
        ),
        pytest.param(
            f"#!/bin/sh\n{LEGACY_HEADER}python3 -m vexinstall sync --target all\n", id="old-header-engine-body"
        ),
    ],
)
def test_doctor_passes_missing_and_unrelated_post_merge(hook_world: Env, body: str | None) -> None:
    if body is not None:
        _write_hook(hook_world.repo / ".git" / "hooks", body)
    assert _hook_findings(hook_world) == []


@pytest.mark.skipif(os.name == "nt", reason="no exec bit on Windows; git runs any hook that starts with #!")
def test_doctor_skips_non_executable_post_merge(hook_world: Env) -> None:
    _write_hook(hook_world.repo / ".git" / "hooks", LEGACY_POST_MERGE).chmod(0o644)
    assert _hook_findings(hook_world) == []


def test_doctor_reads_the_hooks_dir_core_hooks_path_names(hook_world: Env) -> None:
    """A relative core.hooksPath resolves against the checkout, and .git/hooks is then not run."""
    _write_hook(hook_world.repo / ".git" / "hooks", LEGACY_POST_MERGE)
    hook = _write_hook(hook_world.work / "githooks", LEGACY_POST_MERGE)
    git(hook_world.repo, "config", "core.hooksPath", "../githooks")
    found = _hook_findings(hook_world)
    assert len(found) == 1 and _same(found[0]["path"], hook)
    assert MARKED in found[0]["detail"]


def test_doctor_global_hooks_path_skips_a_source_root_without_git(hook_world: Env) -> None:
    """A global core.hooksPath applies to a checkout, never to a source root that has no .git."""
    hook = _write_hook(hook_world.work / "global-hooks", LEGACY_POST_MERGE)
    (hook_world.work / "global.gitconfig").write_text(f'[core]\n\thooksPath = "{hook.parent.as_posix()}"\n')
    found = _hook_findings(hook_world)
    assert len(found) == 1 and _same(found[0]["path"], hook)
    plain = hook_world.work / "plain"
    shutil.copytree(hook_world.repo, plain, ignore=shutil.ignore_patterns(".git"))
    assert gitutil.hooks_dir(plain) is None
    assert _hook_findings(hook_world, source=plain) == []


def test_doctor_finds_the_hook_from_a_linked_worktree(hook_world: Env) -> None:
    """A linked worktree's .git is a file; git runs its hooks from the common dir."""
    hook = _write_hook(hook_world.repo / ".git" / "hooks", LEGACY_POST_MERGE)
    wt = hook_world.work / "wt"
    git(hook_world.repo, "worktree", "add", "-q", "--detach", str(wt))
    assert (wt / ".git").is_file()
    found = _hook_findings(hook_world, source=wt)
    assert len(found) == 1 and _same(found[0]["path"], hook)
    assert MARKED in found[0]["detail"]


def test_hooks_dir_expands_tilde_and_needs_the_checkout_top(hook_world: Env) -> None:
    repo = hook_world.repo
    assert gitutil.hooks_dir(repo / "skills") is None
    git(repo, "config", "core.hooksPath", "~/my-hooks")
    assert _same(gitutil.hooks_dir(repo), hook_world.home / "my-hooks")


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


def test_prune_lists_command_that_shadows_a_skill(world: Env) -> None:
    assert world.run("apply", "--target", "claude").code == 0
    shim = world.home / ".claude" / "commands" / "alpha.md"
    shim.write_text("---\ndescription: stale shim\n---\n")
    listing = world.run("prune", "--unowned", "--target", "claude")
    assert f"  {shim}  (command shadows a skill of the same name)" in listing.out


def test_adopt_and_prune_legacy_checkout_links_and_dir_of_links(world: Env) -> None:
    """Legacy category dirs holding symlinks and links to a prior vexjoy-agent checkout are adopted/prunable."""
    old_repo = world.work / "old" / "vexjoy-agent"
    (old_repo / "skills" / "business" / "biz-one").mkdir(parents=True)
    (old_repo / "skills" / "business" / "biz-one" / "SKILL.md").write_text(skill_md("biz-one"))
    (old_repo / "agents" / "retired-agent").mkdir(parents=True)
    (old_repo / "agents" / "retired-agent" / "references").mkdir(parents=True)
    (old_repo / "agents" / "retired-agent.md").write_text("---\nname: retired-agent\n---\n")

    # Real category dir populated with symlinks to the old checkout on first apply.
    cat_dir = world.skills("claude") / "business"
    cat_dir.mkdir(parents=True)
    os.symlink(old_repo / "skills" / "business" / "biz-one", cat_dir / "biz-one")
    assert world.run("apply", "--target", "claude").code == 0
    assert not os.path.lexists(cat_dir)

    # After ledger exists, leftover links/dirs pointing to old vexjoy-agent checkout are prunable.
    agents_dir = world.home / ".claude" / "agents"
    legacy_md = agents_dir / "retired-agent.md"
    legacy_dir = agents_dir / "retired-agent"
    os.symlink(old_repo / "agents" / "retired-agent.md", legacy_md)
    legacy_dir.mkdir()
    os.symlink(old_repo / "agents" / "retired-agent" / "references", legacy_dir / "references")
    foreign = world.work / "foreign-tool"
    foreign.mkdir()
    user_link = agents_dir / "user-custom.md"
    os.symlink(foreign, user_link)

    listing = "\n".join(world.run("prune", "--unowned", "--target", "claude").out)
    assert f"{legacy_md}  (legacy toolkit entry)" in listing
    assert f"{legacy_dir}  (legacy toolkit entry)" in listing
    assert str(user_link) not in listing

    assert world.run("prune", "--unowned", "--confirm", "--target", "claude").code == 0
    assert not os.path.lexists(legacy_md)
    assert not os.path.lexists(legacy_dir)
    assert os.path.islink(user_link)
    noop = world.run("prune", "--unowned", "--confirm", "--target", "claude")
    assert noop.code == 0 and "nothing to trash" in noop.out[0]


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


def test_check_private_leak_common_words_and_builtin_commands(world: Env, capsys: pytest.CaptureFixture[str]) -> None:
    teach_dir = world.priv / "priv" / "teach"
    teach_dir.mkdir(parents=True)
    (teach_dir / "SKILL.md").write_text(skill_md("teach"))
    grill_dir = world.priv / "priv" / "grill-me"
    grill_dir.mkdir(parents=True)
    (grill_dir / "SKILL.md").write_text(skill_md("grill-me"))

    assert world.run("apply", "--target", "claude").code == 0
    leak = _load_script("check-private-leak")

    # Mentioning common word 'teach', 'wizard', or built-in command 'grill-me' in content does not leak.
    (world.repo / "docs").mkdir(exist_ok=True)
    (world.repo / "docs" / "guide.md").write_text("We teach users how to use the setup wizard and /grill-me.\n")
    commit_all(world.repo, "test-common-words")
    capsys.readouterr()
    assert leak.main(["--repo", str(world.repo), "--home", str(world.home)]) == 0

    # However, tracking a path matching 'teach' still triggers a path leak.
    (world.repo / "skills" / "teach").mkdir(parents=True)
    (world.repo / "skills" / "teach" / "other.md").write_text("not the skill body\n")
    commit_all(world.repo, "test-path-leak")
    capsys.readouterr()
    assert leak.main(["--repo", str(world.repo), "--home", str(world.home)]) == 1
    out = capsys.readouterr().out
    assert "skills/teach/other.md: path 'teach'" in out

    git(world.repo, "rm", "-r", "-q", "skills/teach")

    # Built-in commands (like grill-me) are filtered in overlay_names() and must NOT cause a path leak,
    # unlike common words which intentionally trigger path leaks.
    (world.repo / "skills" / "grill-me").mkdir(parents=True)
    (world.repo / "skills" / "grill-me" / "other.md").write_text("not the skill body\n")
    commit_all(world.repo, "test-builtin-path")
    capsys.readouterr()
    assert leak.main(["--repo", str(world.repo), "--home", str(world.home)]) == 0

    git(world.repo, "rm", "-r", "-q", "skills/grill-me")
    git(world.repo, "rm", "-r", "-q", "docs/guide.md")
    commit_all(world.repo, "cleanup")


def test_check_private_leak_custom_common_words_file(world: Env, capsys: pytest.CaptureFixture[str]) -> None:
    custom_dir = world.priv / "priv" / "customterm"
    custom_dir.mkdir(parents=True)
    (custom_dir / "SKILL.md").write_text(skill_md("customterm"))
    assert world.run("apply", "--target", "claude").code == 0
    leak = _load_script("check-private-leak")

    (world.repo / "docs").mkdir(exist_ok=True)
    (world.repo / "docs" / "mention.md").write_text("mention customterm here\n")
    commit_all(world.repo, "leak-custom")
    capsys.readouterr()
    assert leak.main(["--repo", str(world.repo), "--home", str(world.home)]) == 1

    # Adding customterm to common-words.txt suppresses content-name leak
    common_file = world.home / ".claude" / "vexjoy" / "common-words.txt"
    common_file.write_text("# comments allowed\ncustomterm\n")
    capsys.readouterr()
    assert leak.main(["--repo", str(world.repo), "--home", str(world.home)]) == 0

    git(world.repo, "rm", "-r", "-q", "docs/mention.md")
    commit_all(world.repo, "cleanup")


def test_private_leak_sets_parity_with_pretool_hook() -> None:
    """Ensure BUILTIN_COMMANDS and COMMON_WORDS sets in leak.py and the pretool hook stay identical."""
    from vexinstall import leak

    hook_path = SCRIPTS_DIR.parent / "hooks" / "pretool-private-name-leak-gate.py"
    spec = importlib.util.spec_from_file_location("_leak_gate", hook_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert leak.BUILTIN_COMMANDS == mod._BUILTIN_COMMANDS
    assert leak.COMMON_WORDS == mod._COMMON_WORDS


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


def test_overlay_category_descends_into_project_skills_dir(world: Env) -> None:
    root = world.home / "proj-private"
    (root / "game-proj" / "skills" / "proj-mod").mkdir(parents=True)
    (root / "game-proj" / "skills" / "proj-mod" / "SKILL.md").write_text(skill_md("proj-mod"))
    (root / "game-proj" / "docs").mkdir()
    write_overlays(world.home, {"overlays": [{"id": "p", "root": str(root)}]})
    cfg = sources.load_overlays(world.home / ".claude" / "vexjoy" / "overlays.json", world.repo, world.home)
    assert {s.name for s in cfg.overlays[0].skills} == {"proj-mod"}


def test_migrate_finds_pgh_private_skills(world: Env) -> None:
    from vexinstall.migrate import build_overlays

    shutil.copytree(world.priv, world.home / "pgh" / "private-skills")
    cfg, _ = build_overlays(world.home, world.repo)
    by_id = {o["id"]: o for o in cfg["overlays"]}
    assert by_id["pgh-private"]["root"] == "~/pgh/private-skills"
    assert by_id["pgh-voices"]["prefix"] == "voice-"

    shutil.copytree(world.priv, world.home / "private-skills")
    cfg, _ = build_overlays(world.home, world.repo)
    roots = {o["id"]: o["root"] for o in cfg["overlays"]}
    assert roots["private"] == "~/private-skills"
    assert roots["pgh-private"] == "~/pgh/private-skills"
    assert roots["pgh-voices"] == "~/pgh/private-skills/voice"
