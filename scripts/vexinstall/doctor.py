"""Read-only health checks (spec 12). Exit 1 when any error-level finding exists."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from . import gitutil
from . import index as index_mod
from . import settings as settings_mod
from .adapters import resolve_targets
from .apply import is_category_entry
from .common import DATA_DIRS, SUPPORT_DIRS, ExitCode, OverlayConfigError, is_dangling
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
    _check_repo(ctx, findings)
    errors = sum(1 for f in findings if f.level == ERROR)
    warns = sum(1 for f in findings if f.level == WARN)
    out = [f"[doctor] {errors} error(s), {warns} warning(s) across {', '.join(targets)}"]
    out.extend(f"  {f.level:5} {f.check:26} {f.target:8} {f.path}  {f.detail}".rstrip() for f in findings)
    data = {"errors": errors, "warnings": warns, "findings": [asdict(f) for f in findings]}
    return Result(code=int(ExitCode.ERROR) if errors else 0, out=out, data=data)
