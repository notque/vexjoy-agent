"""Install into CLAUDE_CONFIG_DIR account profiles (``~/.claude-accounts/accounts.json``).

Claude Code reads hooks only from the settings.json of the config dir it runs
with. A profile with no hook registrations runs no toolkit hooks outside the
repo checkout. For every profile in the registry (``scripts/manage-accounts.py``)
this module:

* links ``skills``, ``agents``, ``commands``, ``hooks``, and ``scripts`` to the
  default ``~/.claude`` entries when the profile has none (a real dir or a link
  elsewhere is reported, never replaced);
* merges the toolkit-owned hook registrations into the profile's
  ``settings.json`` with the same owner rule as ``~/.claude/settings.json``.
  Every other key (env, auth, model, permissions, plugins, MCP) and every
  non-owned hook entry stays as it is.

The old file is copied to ``<state>/backups/<name>-settings.<ts>.json`` before
a write. Hook commands use ``$HOME/.claude/hooks/...``, so one hooks dir serves
every profile.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import settings as settings_mod
from .common import SETTINGS_BACKUPS_KEEP, utc_ts
from .context import state_dir
from .fsops import Guard, atomic_symlink, atomic_write_bytes
from .plan import Context
from .profile import filter_settings_hooks

LINKED = ("skills", "agents", "commands", "hooks", "scripts")
REGISTRY_REL = (".claude-accounts", "accounts.json")


@dataclass
class AccountPlan:
    """What one profile needs: links to add, links to report, and the settings merge."""

    name: str
    config_dir: Path
    links_add: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    merge: settings_mod.MergeResult | None = None
    settings_error: str | None = None

    @property
    def settings_path(self) -> Path:
        """The profile's settings.json."""
        return self.config_dir / "settings.json"

    @property
    def changed(self) -> bool:
        """True when apply would write anything."""
        return bool(self.links_add) or bool(self.merge is not None and self.merge.changed)

    def summary(self) -> str:
        """One line for plan, apply, and doctor output."""
        m = self.merge
        added = len(m.added) if m else 0
        stale = (len(m.removed) + len(m.deduped)) if m else 0
        line = f"account {self.name}: links +{len(self.links_add)}, hooks missing={added} stale={stale}"
        if self.problems:
            line += f", problems={len(self.problems)}"
        if self.settings_error:
            line += f", settings error: {self.settings_error}"
        return line

    def to_json(self) -> dict:
        """Serializable form (no settings values)."""
        m = self.merge
        return {
            "name": self.name,
            "config_dir": str(self.config_dir),
            "links_add": self.links_add,
            "problems": self.problems,
            "hooks_added": list(m.added) if m else [],
            "hooks_removed": list(m.removed) if m else [],
            "hooks_deduped": list(m.deduped) if m else [],
            "settings_error": self.settings_error,
        }


def registry(home: Path) -> dict[str, Path]:
    """Profile name -> existing config dir, from ``<home>/.claude-accounts/accounts.json``.

    Missing or unreadable registry, a missing dir, and the default ``~/.claude`` are skipped.
    """
    path = home.joinpath(*REGISTRY_REL)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    default = os.path.realpath(home / ".claude")
    out: dict[str, Path] = {}
    for name, info in sorted(data.items()):
        raw = info.get("config_dir") if isinstance(info, dict) else None
        if not isinstance(name, str) or not isinstance(raw, str) or not raw:
            continue
        cfg = Path(raw).expanduser()
        if cfg.is_dir() and os.path.realpath(cfg) != default:
            out[name] = cfg
    return out


def _plan_links(home: Path, cfg: Path, plan: AccountPlan) -> None:
    for entry in LINKED:
        src = home / ".claude" / entry
        dest = cfg / entry
        if os.path.islink(dest):
            if os.readlink(dest) != str(src):
                plan.problems.append(f"{dest} links to {os.readlink(dest)}, not {src}")
        elif os.path.lexists(dest):
            plan.problems.append(f"{dest} is not a link; move it aside to share {src}")
        elif os.path.lexists(src):
            plan.links_add.append(entry)


def plan_account(ctx: Context, name: str, cfg: Path, desired: dict | None, *, links: bool = True) -> AccountPlan:
    """Read-only plan for one profile. *desired* None means the repo's registrations."""
    plan = AccountPlan(name=name, config_dir=cfg)
    if links:
        _plan_links(ctx.home, cfg, plan)
    if desired is None:
        desired = filter_settings_hooks(settings_mod.desired_from_repo(ctx.source_root), ctx.profile)
    try:
        current = settings_mod.read_settings(plan.settings_path)
    except ValueError as exc:
        plan.settings_error = f"unreadable ({exc})"
        return plan
    if not isinstance(current, dict):
        plan.settings_error = "not a JSON object"
        return plan
    rule = settings_mod.OwnerRule(home=ctx.home, hooks_dir=ctx.home / ".claude" / "hooks", source_root=ctx.source_root)
    plan.merge = settings_mod.merge(current, desired, rule)
    return plan


def plan_all(ctx: Context, desired: dict | None = None, *, links: bool = True) -> list[AccountPlan]:
    """Plans for every registered profile."""
    return [plan_account(ctx, n, c, desired, links=links) for n, c in registry(ctx.home).items()]


def _backup(plan: AccountPlan, backups: Path, guard: Guard) -> str | None:
    if not plan.settings_path.is_file():
        return None
    ts = utc_ts()
    atomic_write_bytes(backups / f"{plan.name}-settings.{ts}.json", plan.settings_path.read_bytes(), guard, mode=0o600)
    for old in sorted(backups.glob(f"{plan.name}-settings.*.json"))[:-SETTINGS_BACKUPS_KEEP]:
        old.unlink()
    return ts


def apply_account(ctx: Context, plan: AccountPlan, guard: Guard) -> dict:
    """Write one profile's links and settings. Returns its report entry."""
    report = plan.to_json()
    report["backup"] = None
    for entry in plan.links_add:
        atomic_symlink(plan.config_dir / entry, ctx.home / ".claude" / entry, guard)
    if plan.merge is not None and plan.merge.changed:
        report["backup"] = _backup(plan, state_dir(ctx.home) / "backups", guard)
        settings_mod.write(plan.settings_path, plan.merge.settings, guard)
    return report


def apply_all(ctx: Context, guard: Guard, desired: dict | None = None, *, links: bool = True) -> list[dict]:
    """Plan and write every profile. A profile that fails with an OS error is reported, not fatal."""
    out = []
    for plan in plan_all(ctx, desired, links=links):
        try:
            out.append(apply_account(ctx, plan, guard))
        except (OSError, ValueError) as exc:
            entry = plan.to_json()
            entry["error"] = f"{type(exc).__name__}: {exc}"
            out.append(entry)
    return out


def report_lines(reports: list[dict]) -> list[str]:
    """Summary lines for apply output: only profiles that changed or failed."""
    lines = []
    for r in reports:
        if r.get("error"):
            lines.append(f"account {r['name']}: ERROR {r['error']}")
        elif r["links_add"] or r["hooks_added"] or r["hooks_removed"] or r["hooks_deduped"]:
            lines.append(
                f"account {r['name']}: links +{len(r['links_add'])}, hooks +{len(r['hooks_added'])} "
                f"-{len(r['hooks_removed'])} dedup {len(r['hooks_deduped'])}, backup {r['backup']}"
            )
    return lines
