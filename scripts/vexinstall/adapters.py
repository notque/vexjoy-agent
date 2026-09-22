"""Per-target layout tables and desired-state derivation.

Each adapter is the one layout vexinstall writes for a runtime: flat names, no
category dirs, per-entry agents links. ``external`` settings come from
external.py.

| target   | skills (+support, data) | agents        | commands     | hooks                    | scripts   | settings |
|----------|-------------------------|---------------|--------------|--------------------------|-----------|----------|
| claude   | skills/<n>, mode        | agents/<e>    | commands/<n> | hooks (whole dir)        | whole dir | merge    |
| codex    | skills/<n>, copy        | agents/<e>,   | -            | hooks/<e> + hooks/lib/<e>| per entry | external |
|          |                         | copy          |              |                          |           |          |
| factory  | skills/<n>, mode        | droids/<e>    | commands/<n> | hooks (whole dir)        | whole dir | external |
| hermes   | skills/<n>, mode        | -             | -            | -                        | per entry | -        |
| reasonix | skills/<n>, mode;       | -             | -            | hooks/<allowlisted> +    | per entry | external |
|          | support copy            |               |              | hooks/lib                |           |          |

"external" settings files (codex hooks.json, factory/reasonix settings.json)
stay with their existing generator scripts; the engine does not write them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from .profile import EMPTY, Profile
from .sources import OverlayConfig, PublicSources, SourceItem

SKILL_KINDS = frozenset({"skill", "data", "support"})


@dataclass(frozen=True)
class Adapter:
    """Layout table for one runtime target."""

    name: str
    root: str
    skills: str | None = "skills"
    skills_mode: str | None = None
    support_mode: str | None = None
    agents: str | None = None
    agents_mode: str | None = None
    commands: str | None = None
    hooks: str | None = None  # "whole" | "per-entry" | "allowlist"
    scripts: str | None = None  # "whole" | "per-entry"
    settings: bool = False

    def root_path(self, home: Path) -> Path:
        """Runtime root under *home*."""
        return home / self.root

    def containers(self, home: Path) -> list[Path]:
        """Dirs that must be real directories holding per-entry installs."""
        root = self.root_path(home)
        out = []
        for rel in (self.skills, self.agents, self.commands):
            if rel:
                out.append(root / rel)
        if self.hooks in ("per-entry", "allowlist"):
            out.append(root / "hooks")
        if self.hooks == "per-entry":
            out.append(root / "hooks" / "lib")
        if self.scripts == "per-entry":
            out.append(root / "scripts")
        return out

    def index_dir(self, home: Path) -> Path:
        """Installed index location for this target."""
        return self.root_path(home) / "vexjoy" / "index"


ADAPTERS: dict[str, Adapter] = {
    "claude": Adapter(
        name="claude",
        root=".claude",
        agents="agents",
        commands="commands",
        hooks="whole",
        scripts="whole",
        settings=True,
    ),
    "codex": Adapter(
        name="codex",
        root=".codex",
        skills_mode="copy",
        support_mode="copy",
        agents="agents",
        agents_mode="copy",
        hooks="per-entry",
        scripts="per-entry",
    ),
    "factory": Adapter(
        name="factory",
        root=".factory",
        agents="droids",
        commands="commands",
        hooks="whole",
        scripts="whole",
    ),
    "hermes": Adapter(
        name="hermes",
        root=".hermes",
        scripts="per-entry",
    ),
    "reasonix": Adapter(
        name="reasonix",
        root=".reasonix",
        support_mode="copy",
        hooks="allowlist",
        scripts="per-entry",
    ),
}


@dataclass(frozen=True)
class DesiredEntry:
    """One entry of desired state: (target, dest, kind, source, owner, mode)."""

    target: str
    dest: Path
    kind: str
    source: Path
    owner: str
    mode: str
    files: tuple[str, ...] | None = None  # copy file list (relative), None = walk


@dataclass
class Collision:
    """A dest claimed by more than one source."""

    target: str
    dest: Path
    claims: list[SourceItem]

    def describe(self) -> str:
        """One line naming every source."""
        parts = [f"{c.owner}:{c.source}" for c in self.claims]
        return f"{self.target}: {self.dest.name} claimed by " + " and ".join(parts)


@dataclass
class TargetDesire:
    """Desired state for one target."""

    adapter: Adapter
    entries: dict[str, DesiredEntry] = field(default_factory=dict)
    collisions: list[Collision] = field(default_factory=list)
    shadowed_commands: list[SourceItem] = field(default_factory=list)
    stale_overlays: list[str] = field(default_factory=list)
    filtered: dict[str, SourceItem] = field(default_factory=dict)  # dest -> item disabled by the profile


def effective_adapter(adapter: Adapter, profile: Profile = EMPTY) -> Adapter:
    """*adapter* adjusted for the install profile.

    A whole-dir hooks link cannot exclude items, so while any hook is disabled
    ``hooks="whole"`` becomes ``per-entry`` (install.sh ``install_component``).
    """
    if profile.hooks and adapter.hooks == "whole":
        return replace(adapter, hooks="per-entry")
    return adapter


def _profile_skip(item: SourceItem, profile: Profile) -> bool:
    if item.kind in SKILL_KINDS:
        return profile.skill_disabled(item.name)
    if item.kind == "agent":
        return profile.agent_disabled(item.name)
    if item.kind == "hook":
        return profile.hook_disabled(item.name)
    return False


def desired_for(
    adapter: Adapter,
    home: Path,
    pub: PublicSources,
    cfg: OverlayConfig,
    mode: str,
    profile: Profile = EMPTY,
) -> TargetDesire:
    """Derive the desired entries for one target.

    Items the install profile disables are not desired (spec 5.2 plus
    install.sh profile filtering); pass the adapter from ``effective_adapter``.
    """
    out = TargetDesire(adapter=adapter)
    root = adapter.root_path(home)
    claims: dict[Path, list[tuple[SourceItem, str | None]]] = {}

    def claim(dest: Path, item: SourceItem, forced: str | None) -> None:
        if _profile_skip(item, profile):
            out.filtered[str(dest)] = item
            return
        claims.setdefault(dest, []).append((item, forced))

    if adapter.skills:
        sk = root / adapter.skills
        for item in pub.skills + pub.data:
            claim(sk / item.name, item, adapter.skills_mode)
        for item in pub.support:
            claim(sk / item.name, item, adapter.support_mode or adapter.skills_mode)
        for ov in cfg.overlays:
            if not ov.available:
                out.stale_overlays.append(ov.id)
                continue
            for item in ov.skills + ov.data:
                claim(sk / item.name, item, adapter.skills_mode)
    if adapter.agents:
        ag = root / adapter.agents
        for item in pub.agents:
            claim(ag / item.name, item, adapter.agents_mode)
        for ov in cfg.overlays:
            if ov.available:
                for item in ov.agents:
                    claim(ag / item.name, item, adapter.agents_mode)
    if adapter.commands:
        skill_names = {d.name for d in claims if adapter.skills and d.parent == root / adapter.skills}
        cm = root / adapter.commands
        for item in pub.commands:
            if item.name in skill_names:
                out.shadowed_commands.append(item)
                continue
            claim(cm / f"{item.name}.md", item, None)
    if pub.hooks_dir is not None:
        if adapter.hooks == "whole":
            claim(root / "hooks", SourceItem("hooks", "hooks", pub.hooks_dir, "public"), None)
        elif adapter.hooks == "per-entry":
            for item in pub.hook_items:
                claim(root / "hooks" / item.name, item, None)
            for item in pub.hook_lib_items:
                claim(root / "hooks" / "lib" / item.name, item, None)
        elif adapter.hooks == "allowlist":
            names = pub.allowlists.get(adapter.name, [])
            by_name = {i.name: i for i in pub.hook_items}
            for name in names:
                if name in by_name:
                    claim(root / "hooks" / name, by_name[name], None)
            if names and (pub.hooks_dir / "lib").is_dir():
                claim(root / "hooks" / "lib", SourceItem("hook", "lib", pub.hooks_dir / "lib", "public"), None)
    if pub.scripts_dir is not None:
        if adapter.scripts == "whole":
            claim(root / "scripts", SourceItem("scripts", "scripts", pub.scripts_dir, "public"), None)
        elif adapter.scripts == "per-entry":
            for item in pub.script_items:
                claim(root / "scripts" / item.name, item, None)

    for dest, items in claims.items():
        if len(items) > 1:
            out.collisions.append(Collision(adapter.name, dest, [i for i, _ in items]))
            continue
        item, forced = items[0]
        entry_mode = forced or mode
        files = None
        if entry_mode == "copy" and item.owner == "public":
            listed = pub.files_for(item.source) if item.source.is_dir() else None
            files = tuple(listed) if listed is not None else None
        out.entries[str(dest)] = DesiredEntry(
            target=adapter.name,
            dest=dest,
            kind=item.kind,
            source=item.source,
            owner=item.owner,
            mode=entry_mode,
            files=files,
        )
    return out


def resolve_targets(spec: str, home: Path) -> list[str]:
    """Expand ``--target``. ``all`` = claude plus every runtime dir present."""
    if spec != "all":
        return [spec]
    out = ["claude"]
    for name in ("codex", "factory", "hermes", "reasonix"):
        if ADAPTERS[name].root_path(home).is_dir():
            out.append(name)
    return out
