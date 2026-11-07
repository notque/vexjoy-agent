"""Read-only health checks (spec 12). Exit 1 when any error-level finding exists."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from . import accounts as accounts_mod
from . import gitutil, interp
from . import index as index_mod
from . import settings as settings_mod
from .adapters import ADAPTERS, resolve_targets
from .apply import is_category_entry
from .common import DATA_DIRS, SUPPORT_DIRS, ExitCode, OverlayConfigError, is_dangling, realpath
from .context import Options, Result, load_context
from .leak import find_leaks
from .ledger import STATUS_STALE
from .plan import Context, build_plan
from .sources import skill_md_of

ERROR = "error"
WARN = "warn"


@dataclass
class Finding:
    """One doctor finding."""

    level: str
    check: str
    target: str
    path: str
    detail: str = ""


def _skill_names(skills_root: Path) -> set[str]:
    names: set[str] = set()
    if not skills_root.is_dir():
        return names
    for child in skills_root.iterdir():
        if child.is_dir() and skill_md_of(child) is not None:
            names.add(child.name)
    return names


def _plugin_skill_names(home: Path) -> dict[str, str]:
    """Bare skill name -> plugin id for enabled plugins."""
    out: dict[str, str] = {}
    try:
        settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
        installed = json.loads((home / ".claude" / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return out
    enabled = settings.get("enabledPlugins", {}) if isinstance(settings, dict) else {}
    plugins = installed.get("plugins", {}) if isinstance(installed, dict) else {}
    for pid, on in (enabled or {}).items():
        if not on:
            continue
        for inst in plugins.get(pid, []) or []:
            path = Path(str(inst.get("installPath", "")))
            skills = path / "skills"
            if skills.is_dir():
                for child in skills.iterdir():
                    if (child / "SKILL.md").is_file():
                        out.setdefault(child.name, pid)
    return out


def _check_target(ctx: Context, target: str, findings: list[Finding]) -> None:
    adapter = ctx.adapter(target)
    home = ctx.home
    root = adapter.root_path(home)
    owned = ctx.ledger.for_target(target)
    add = findings.append
    if adapter.agents:
        agents = root / adapter.agents
        if os.path.islink(agents):
            add(Finding(ERROR, "whole-dir-agents-symlink", target, str(agents), os.readlink(agents)))
    for container in adapter.containers(home):
        if os.path.islink(container) or not os.path.isdir(container):
            continue
        is_skills = adapter.skills is not None and container == root / adapter.skills
        for child in sorted(os.listdir(container)):
            path = container / child
            if child.startswith("."):
                continue
            d = str(path)
            if is_dangling(path):
                add(Finding(ERROR, "dangling-link", target, d, os.readlink(path)))
                continue
            if any(str(c) == d for c in adapter.containers(home)):
                continue
            if is_skills:
                if is_category_entry(path):
                    add(Finding(ERROR, "category-in-flat-root", target, d))
                    continue
                if (
                    path.is_dir()
                    and skill_md_of(path) is None
                    and child not in SUPPORT_DIRS
                    and not (d in owned and owned[d].kind == "data")
                ):
                    what = "runtime data dir" if child in DATA_DIRS else "non-skill dir"
                    add(Finding(WARN, "non-skill-dir", target, d, what))
                    continue
            if d not in owned:
                add(Finding(WARN, "unowned", target, d))
    for d, e in sorted(owned.items()):
        if e.status == STATUS_STALE:
            add(Finding(WARN, "stale-source", target, d, e.source))
    idx = adapter.index_dir(home) / "skills.json"
    if adapter.skills and owned:
        if not idx.is_file():
            add(Finding(WARN, "index-missing", target, str(idx)))
        elif idx.stat().st_mtime < index_mod.newest_source_mtime(ctx.ledger, target):
            add(Finding(WARN, "index-stale", target, str(idx), "older than newest source SKILL.md"))


def _check_scan_roots(ctx: Context, findings: list[Finding]) -> None:
    home = ctx.home
    personal = _skill_names(home / ".claude" / "skills")
    project_root = ctx.source_root / ".claude"
    project = _skill_names(project_root / "skills")
    for name in sorted(personal & project):
        findings.append(
            Finding(
                ERROR, "duplicate-skill-name", "claude", name, "personal ~/.claude/skills and project .claude/skills"
            )
        )
    commands = home / ".claude" / "commands"
    if commands.is_dir():
        for f in sorted(commands.glob("*.md")):
            if f.stem in personal:
                findings.append(Finding(ERROR, "duplicate-skill-name", "claude", str(f), "command shadowed by skill"))
    for name, pid in sorted(_plugin_skill_names(home).items()):
        if name in personal:
            findings.append(Finding(WARN, "plugin-bare-name", "claude", name, f"also provided by plugin {pid}"))
    installed_agents = {p.name for p in (home / ".claude" / "agents").glob("*.md")}
    installed_cmds = {p.name for p in commands.glob("*.md")} if commands.is_dir() else set()
    hooks_dir = home / ".claude" / "hooks"
    installed_hooks = {p.name for p in hooks_dir.iterdir()} if hooks_dir.is_dir() else set()
    _check_nested_project_roots(ctx, findings, personal)
    for sub, names in (
        ("agents", installed_agents),
        ("commands", installed_cmds),
        ("skills", personal),
        ("hooks", installed_hooks),
    ):
        pdir = project_root / sub
        if not pdir.is_dir():
            continue
        for child in sorted(pdir.iterdir()):
            if child.name in names:
                findings.append(
                    Finding(WARN, "project-scope-duplicate", "claude", str(child), f"duplicates installed {sub} name")
                )


_WALK_PRUNE = frozenset({".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache", ".ruff_cache"})


def nested_project_roots(repo: Path) -> list[Path]:
    """``.claude/{skills,agents}`` dirs under *repo* other than the repo's own.

    Claude Code discovers nested ``<subdir>/.claude/skills`` and scans agents
    dirs recursively, so each of these is an extra project-scope source when a
    session works in the repo. Includes ``.claude/worktrees/*/.claude/...``.
    Symlinked dirs are not followed.
    """
    out: list[Path] = []
    top = repo / ".claude"
    for dirpath, dirnames, _ in os.walk(repo, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in _WALK_PRUNE)
        if ".claude" not in dirnames:
            continue
        claude = Path(dirpath) / ".claude"
        if claude == top:
            continue
        for sub in ("skills", "agents"):
            if (claude / sub).is_dir():
                out.append(claude / sub)
    return out


def _check_nested_project_roots(ctx: Context, findings: list[Finding], personal: set[str]) -> None:
    for root in nested_project_roots(ctx.source_root):
        findings.append(
            Finding(WARN, "project-scope-nested-source", "claude", str(root), "extra project-scope scan root")
        )
        if root.name != "skills":
            continue
        for name in sorted(_skill_names(root) & personal):
            findings.append(
                Finding(ERROR, "duplicate-skill-name", "claude", name, f"personal ~/.claude/skills and project {root}")
            )


def _check_settings(ctx: Context, findings: list[Finding]) -> None:
    home = ctx.home
    spath = home / ".claude" / "settings.json"
    try:
        current = settings_mod.read_settings(spath)
    except ValueError as exc:
        findings.append(Finding(ERROR, "settings-unreadable", "claude", str(spath), str(exc)))
        return
    rule = settings_mod.OwnerRule(home=home, hooks_dir=home / ".claude" / "hooks", source_root=ctx.source_root)
    for label in settings_mod.duplicate_owned(current, rule):
        findings.append(Finding(WARN, "settings-duplicate-owned", "claude", str(spath), label))
    recorded = set(ctx.ledger.settings.get("claude", []))
    actual = {settings_mod.canonical_hash(m, e) for _, m, e in settings_mod.owned_entries(current, rule)}
    if recorded or ctx.ledger.entries:
        extra = len(actual - recorded)
        missing = len(recorded - actual)
        if extra or missing:
            findings.append(
                Finding(
                    WARN,
                    "settings-drift",
                    "claude",
                    str(spath),
                    f"{extra} owned entries not in ledger, {missing} ledger entries absent",
                )
            )


def _check_python(ctx: Context, findings: list[Finding]) -> None:
    """Interpreter drift: the hook python link is missing, dangling, or older than 3.10."""
    link = str(interp.link_path(ctx.home))
    for check, detail in interp.drift(ctx.home):
        findings.append(Finding(ERROR, check, "claude", link, detail))
    if not interp.drift(ctx.home):
        missing = interp.missing_modules(ctx.home)
        if missing:
            detail = (
                f"hook python cannot import {', '.join(missing)}; rerun ./install.sh or pip install -r requirements.txt"
            )
            findings.append(Finding(WARN, "python-deps-missing", "claude", link, detail))


def _check_accounts(ctx: Context, findings: list[Finding]) -> None:
    for plan in accounts_mod.plan_all(ctx):
        spath = str(plan.settings_path)
        for entry in plan.links_add:
            findings.append(Finding(ERROR, "account-link-missing", "claude", str(plan.config_dir / entry), plan.name))
        for problem in plan.problems:
            findings.append(Finding(ERROR, "account-link-conflict", "claude", str(plan.config_dir), problem))
        if plan.settings_error:
            findings.append(Finding(ERROR, "account-settings-unreadable", "claude", spath, plan.settings_error))
        elif plan.merge is not None and plan.merge.changed:
            m = plan.merge
            detail = f"{plan.name}: missing={len(m.added)} stale={len(m.removed) + len(m.deduped)}"
            findings.append(Finding(ERROR, "account-hooks-drift", "claude", spath, detail))


def _check_repo(ctx: Context, findings: list[Finding]) -> None:
    repo = ctx.source_root
    for line in gitutil.status_porcelain(repo):
        if line.startswith("??"):
            continue
        findings.append(Finding(ERROR, "repo-tracked-modified", "repo", line[3:], line[:2].strip()))
    for leak in find_leaks(repo, ctx.ledger, ctx.overlays, ctx.public):
        findings.append(Finding(ERROR, "repo-private-leak", "repo", leak.path, f"{leak.how}: {leak.name}"))
    for sub in ("skills/INDEX.local.json", "agents/INDEX.local.json"):
        if sub in set(gitutil.tracked_files(repo)):
            findings.append(Finding(ERROR, "repo-tracked-local-index", "repo", sub))


# The pre-engine install.sh wrote a post-merge that ran an add-only `ln -s` loop
# over $HOME/.claude and the other runtime roots; Git Bash without symlink
# privilege made copies. The current hook only runs `-m vexinstall sync --target all`.
LEGACY_HOOK_HEADER = "auto-syncs new items after git pull"
INSTALL_HOOK_MARKER = "Written by vexjoy-agent"
_HOOK_SCAN_BYTES = 64 * 1024
_LN_SYMLINK = re.compile(r"\bln(?:\s+-[-\w]+)*?\s+(?:-[A-Za-z]*s[A-Za-z]*|--symbolic)(?=\s)")
_ROOT_NAMES = "|".join(sorted(re.escape(a.root) for a in ADAPTERS.values()))
_RUNTIME_ROOT = re.compile(r"(?:\$HOME|\$\{HOME\}|~)\"?/(?:" + _ROOT_NAMES + r")(?![\w.-])")
_ENGINE_SYNC = re.compile(r"-m\s+vexinstall\s+sync\b[^\n]*?--target(?:\s+|=)all\b")


def is_legacy_post_merge(text: str) -> bool:
    """True for a post-merge that links repo items into runtime roots itself.

    Signs: the legacy header, or ``ln -s`` plus a ``$HOME``-anchored runtime
    root. A hook that runs ``-m vexinstall sync --target all`` never matches.
    Full-line comments are ignored for everything but the header.
    """
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    if _ENGINE_SYNC.search(code):
        return False
    links = _LN_SYMLINK.search(code) is not None and _RUNTIME_ROOT.search(code) is not None
    return links or LEGACY_HOOK_HEADER in text


def _legacy_hook_fix(root: Path, hooks: Path, text: str) -> str:
    """Fix advice. install.sh writes only <main checkout>/.git/hooks/post-merge, and only over its marker."""
    what = "links repo items into runtime roots after every pull"
    body = "replace the file with the install.sh post-merge body"
    default = gitutil.default_hooks_dir(root)
    in_dot_git = default is not None and default.parent.name == ".git" and realpath(hooks) == realpath(default)
    if in_dot_git and INSTALL_HOOK_MARKER in text:
        return (
            f"{what}; run ./install.sh from the main checkout (it replaces a hook marked"
            f" '{INSTALL_HOOK_MARKER}', even when apply fails) or {body}"
        )
    return (
        f"{what}; {body} (./install.sh replaces only .git/hooks/post-merge in the main checkout,"
        f" and only when it carries '{INSTALL_HOOK_MARKER}')"
    )


def _check_git_hooks(ctx: Context, findings: list[Finding]) -> None:
    """Legacy post-merge in the hooks dir git uses. Report only: the repo guard forbids rewriting it."""
    hooks = gitutil.hooks_dir(ctx.source_root)
    if hooks is None:
        return
    hook = hooks / "post-merge"
    # git skips a hook without the exec bit; Windows has none, so X_OK always passes there.
    if not hook.is_file() or not os.access(hook, os.X_OK):
        return
    try:
        with open(hook, "rb") as fh:
            text = fh.read(_HOOK_SCAN_BYTES).decode("utf-8", "replace")
    except OSError:
        return
    if is_legacy_post_merge(text):
        detail = _legacy_hook_fix(ctx.source_root, hooks, text)
        findings.append(Finding(ERROR, "legacy-git-hook", "repo", str(hook), detail))


def run_doctor(opts: Options) -> Result:
    """Run every check. Never writes."""
    try:
        ctx = load_context(opts)
    except OverlayConfigError as exc:
        return Result(code=int(ExitCode.ERROR), err=[str(exc)])
    targets = resolve_targets(opts.target, ctx.home)
    findings: list[Finding] = []
    if ctx.ledger_state == "corrupt":
        findings.append(Finding(ERROR, "ledger-corrupt", "all", str(ctx.state_dir / "ledger.json")))
    plan = build_plan(ctx, targets, full_adoption=ctx.ledger_state != "ok")
    for col in plan.collisions:
        findings.append(Finding(ERROR, "collision", col.target, str(col.dest), col.describe()))
    for note in plan.notes:
        if "defined twice" in note:
            findings.append(Finding(ERROR, "duplicate-public-skill", "repo", "", note))
    for t in targets:
        _check_target(ctx, t, findings)
    if "claude" in targets:
        _check_scan_roots(ctx, findings)
        _check_settings(ctx, findings)
        _check_python(ctx, findings)
        _check_accounts(ctx, findings)
    _check_repo(ctx, findings)
    _check_git_hooks(ctx, findings)
    errors = sum(1 for f in findings if f.level == ERROR)
    warns = sum(1 for f in findings if f.level == WARN)
    out = [f"[doctor] {errors} error(s), {warns} warning(s) across {', '.join(targets)}"]
    out.extend(f"  {f.level:5} {f.check:26} {f.target:8} {f.path}  {f.detail}".rstrip() for f in findings)
    data = {"errors": errors, "warnings": warns, "findings": [asdict(f) for f in findings]}
    return Result(code=int(ExitCode.ERROR) if errors else 0, out=out, data=data)
