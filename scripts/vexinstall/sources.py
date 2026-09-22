"""Read install sources: the public repo and overlays from overlays.json."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import gitutil
from .common import (
    DATA_DIRS,
    SUPPORT_DIRS,
    OverlayConfigError,
    expand_home,
    is_ignored_name,
    is_inside,
    iter_tree_files,
    realpath,
)

PUBLIC = "public"
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_OVERLAY_KEYS = frozenset({"id", "root", "layout", "prefix", "kinds", "exclude"})
_LAYOUTS = frozenset({"category", "flat"})
_KINDS = frozenset({"skills", "agents"})
_PROMOTED_RE = re.compile(r"^promoted_to\s*:\s*(.+)$", re.MULTILINE)
_AGENT_SKIP = frozenset({"INDEX.json", "INDEX.local.json", "README.md"})


@dataclass(frozen=True)
class SourceItem:
    """One installable source path.

    kind: skill | data | support | agent | command | hooks | hook | hook-lib |
    scripts | script.
    """

    kind: str
    name: str
    source: Path
    owner: str
    category: str | None = None


@dataclass
class PublicSources:
    """Everything the public repo offers for install."""

    root: Path
    skills: list[SourceItem] = field(default_factory=list)
    support: list[SourceItem] = field(default_factory=list)
    data: list[SourceItem] = field(default_factory=list)
    promoted: list[SourceItem] = field(default_factory=list)
    categories: dict[str, Path] = field(default_factory=dict)
    agents: list[SourceItem] = field(default_factory=list)
    commands: list[SourceItem] = field(default_factory=list)
    hooks_dir: Path | None = None
    hook_items: list[SourceItem] = field(default_factory=list)
    hook_lib_items: list[SourceItem] = field(default_factory=list)
    scripts_dir: Path | None = None
    script_items: list[SourceItem] = field(default_factory=list)
    allowlists: dict[str, list[str]] = field(default_factory=dict)

    def duplicate_skill_names(self) -> dict[str, list[SourceItem]]:
        """Public skill names defined in more than one category."""
        seen: dict[str, list[SourceItem]] = {}
        for item in self.skills:
            seen.setdefault(item.name, []).append(item)
        return {name: items for name, items in seen.items() if len(items) > 1}

    def files_for(self, path: Path) -> list[str] | None:
        """git-visible files under *path* (relative to it), or None outside git."""
        listing = gitutil.ls_files(self.root)
        if listing is None:
            return None
        try:
            rel = path.relative_to(self.root).as_posix()
        except ValueError:
            return None
        prefix = rel.rstrip("/") + "/"
        out = []
        for f in listing:
            if f.startswith(prefix):
                sub = f[len(prefix) :]
                if any(is_ignored_name(part) for part in sub.split("/")):
                    continue
                if (path / sub).is_file():
                    out.append(sub)
        return out


@dataclass
class Overlay:
    """One overlay root from overlays.json."""

    id: str
    root: Path
    layout: str
    prefix: str = ""
    kinds: tuple[str, ...] = ("skills",)
    exclude: tuple[str, ...] = ()
    available: bool = True
    skills: list[SourceItem] = field(default_factory=list)
    data: list[SourceItem] = field(default_factory=list)
    agents: list[SourceItem] = field(default_factory=list)

    @property
    def owner(self) -> str:
        """Ledger owner tag."""
        return f"overlay:{self.id}"


@dataclass
class OverlayConfig:
    """Parsed overlays.json."""

    path: Path
    overlays: list[Overlay] = field(default_factory=list)
    mtime: float | None = None

    def by_id(self) -> dict[str, Overlay]:
        """Overlays keyed by id."""
        return {o.id: o for o in self.overlays}

    def roots(self) -> list[Path]:
        """Every configured overlay root, available or not."""
        return [o.root for o in self.overlays]


def read_frontmatter_text(skill_md: Path) -> str:
    """Return the raw frontmatter block of a SKILL.md, or ''."""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[3:end] if end != -1 else ""


def promoted_target(skill_dir: Path) -> str | None:
    """The ``promoted_to:`` value of a skill, if any."""
    m = _PROMOTED_RE.search(read_frontmatter_text(skill_dir / "SKILL.md"))
    return m.group(1).strip().strip("\"'") if m else None


def skill_md_of(path: Path) -> Path | None:
    """SKILL.md for a skill dir: ``<dir>/SKILL.md`` or ``<dir>/skill/SKILL.md``."""
    for candidate in (path / "SKILL.md", path / "skill" / "SKILL.md"):
        if candidate.is_file():
            return candidate
    return None


def _visible_dirs(path: Path) -> list[Path]:
    try:
        children = sorted(path.iterdir())
    except OSError:
        return []
    return [c for c in children if c.is_dir() and not c.name.startswith(".") and not is_ignored_name(c.name)]


def _top_level_items(root: Path, sub: str, lister: tuple[str, ...] | None, skip: frozenset[str]) -> list[str]:
    base = root / sub
    if not base.is_dir():
        return []
    if lister is not None:
        prefix = sub + "/"
        names = {f[len(prefix) :].split("/", 1)[0] for f in lister if f.startswith(prefix)}
    else:
        names = {p.name for p in base.iterdir()}
    return sorted(n for n in names if n not in skip and not n.startswith(".") and not is_ignored_name(n))


def load_public(root: Path) -> PublicSources:
    """Scan the public repo at *root*."""
    root = Path(realpath(root))
    pub = PublicSources(root=root)
    lister = gitutil.ls_files(root)
    skills_dir = root / "skills"
    candidates: list[SourceItem] = []
    for top in _visible_dirs(skills_dir):
        if top.name in DATA_DIRS:
            continue
        if top.name in SUPPORT_DIRS:
            pub.support.append(SourceItem("support", top.name, top, PUBLIC))
            continue
        if (top / "SKILL.md").is_file():
            candidates.append(SourceItem("skill", top.name, top, PUBLIC))
            continue
        nested = False
        for child in _visible_dirs(top):
            if (child / "SKILL.md").is_file():
                nested = True
                candidates.append(SourceItem("skill", child.name, child, PUBLIC, top.name))
            elif (child / "profile.json").is_file():
                pub.data.append(SourceItem("data", child.name, child, PUBLIC, top.name))
        if nested:
            pub.categories[top.name] = top
    names = {c.name for c in candidates}
    for item in candidates:
        target = promoted_target(item.source)
        if target and target in names and target != item.name:
            pub.promoted.append(item)
        else:
            pub.skills.append(item)

    agents_dir = root / "agents"
    for name in _top_level_items(root, "agents", lister, _AGENT_SKIP):
        path = agents_dir / name
        if path.is_dir() or name.endswith(".md"):
            pub.agents.append(SourceItem("agent", name, path, PUBLIC))

    commands_dir = root / "commands"
    for name in _top_level_items(root, "commands", lister, frozenset()):
        if name.endswith(".md") and (commands_dir / name).is_file():
            pub.commands.append(SourceItem("command", name[:-3], commands_dir / name, PUBLIC))

    hooks_dir = root / "hooks"
    if hooks_dir.is_dir():
        pub.hooks_dir = hooks_dir
        for name in _top_level_items(root, "hooks", lister, frozenset({"tests", "lib"})):
            pub.hook_items.append(SourceItem("hook", name, hooks_dir / name, PUBLIC))
        for name in _top_level_items(root, "hooks/lib", lister, frozenset({"tests"})):
            pub.hook_lib_items.append(SourceItem("hook-lib", name, hooks_dir / "lib" / name, PUBLIC))

    scripts_dir = root / "scripts"
    if scripts_dir.is_dir():
        pub.scripts_dir = scripts_dir
        for name in _top_level_items(root, "scripts", lister, frozenset()):
            pub.script_items.append(SourceItem("script", name, scripts_dir / name, PUBLIC))

    for key, fname in (("codex", "codex-hooks-allowlist.txt"), ("reasonix", "reasonix-hooks-allowlist.txt")):
        allow = scripts_dir / fname
        if allow.is_file():
            pub.allowlists[key] = parse_allowlist(allow)
    return pub


def parse_allowlist(path: Path) -> list[str]:
    """Hook filenames from an ``EVENT:filename [k=v ...]`` allowlist."""
    names: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        name = line.split(":", 1)[1].split()[0] if line.split(":", 1)[1].split() else ""
        if name and "/" not in name and name not in names:
            names.append(name)
    return names


def default_overlays_path(home: Path) -> Path:
    """Location of overlays.json."""
    return home / ".claude" / "vexjoy" / "overlays.json"


def _excluded(rel: str, exclude: tuple[str, ...]) -> bool:
    return any(rel == e or rel.startswith(e.rstrip("/") + "/") for e in exclude)


def _scan_overlay(ov: Overlay) -> None:
    def add_entry(path: Path, rel: str) -> None:
        if _excluded(rel, ov.exclude):
            return
        name = ov.prefix + path.name
        if skill_md_of(path) is not None:
            ov.skills.append(SourceItem("skill", name, path, ov.owner))
        elif (path / "profile.json").is_file():
            ov.data.append(SourceItem("data", name, path, ov.owner))

    def add_agents(agents_dir: Path, rel: str) -> None:
        if "agents" not in ov.kinds or _excluded(rel, ov.exclude) or not agents_dir.is_dir():
            return
        for f in sorted(agents_dir.glob("*.md")):
            if f.is_file() and f.name not in _AGENT_SKIP:
                ov.agents.append(SourceItem("agent", ov.prefix + f.name, f, ov.owner))

    add_agents(ov.root / "agents", "agents")
    if "skills" not in ov.kinds:
        tops: list[Path] = []
    else:
        tops = _visible_dirs(ov.root)
    for top in tops:
        if top.name == "agents":
            continue
        if ov.layout == "flat":
            add_entry(top, top.name)
            continue
        if _excluded(top.name, ov.exclude):
            continue
        for child in _visible_dirs(top):
            if child.name == "agents":
                add_agents(child, f"{top.name}/agents")
                continue
            add_entry(child, f"{top.name}/{child.name}")
    if ov.layout == "category" and "skills" not in ov.kinds:
        for top in _visible_dirs(ov.root):
            add_agents(top / "agents", f"{top.name}/agents")


def load_overlays(path: Path, repo_root: Path, home: Path) -> OverlayConfig:
    """Parse and validate overlays.json. A missing file yields no overlays."""
    cfg = OverlayConfig(path=path)
    try:
        raw_text = path.read_text(encoding="utf-8")
        cfg.mtime = path.stat().st_mtime
    except FileNotFoundError:
        return cfg
    except OSError as exc:
        raise OverlayConfigError(f"overlays: cannot read {path}: {exc}") from exc
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise OverlayConfigError(f"overlays: invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise OverlayConfigError("overlays: top level must be an object")
    if "overrides" in data:
        raise OverlayConfigError("overlays: 'overrides' is not supported; overlays never replace public entries")
    unknown = set(data) - {"overlays"}
    if unknown:
        raise OverlayConfigError(f"overlays: unknown top-level keys {sorted(unknown)}")
    items = data.get("overlays", [])
    if not isinstance(items, list):
        raise OverlayConfigError("overlays: 'overlays' must be a list")
    repo_real = realpath(repo_root)
    seen: set[str] = set()
    for raw in items:
        if not isinstance(raw, dict):
            raise OverlayConfigError("overlays: each overlay must be an object")
        if "overrides" in raw:
            raise OverlayConfigError(
                f"overlays: 'overrides' is not supported (overlay {raw.get('id')!r}); "
                "overlays never replace public entries"
            )
        extra = set(raw) - _OVERLAY_KEYS
        if extra:
            raise OverlayConfigError(f"overlays: overlay {raw.get('id')!r} has unknown keys {sorted(extra)}")
        oid = raw.get("id")
        if not isinstance(oid, str) or not _ID_RE.match(oid) or oid in seen:
            raise OverlayConfigError(f"overlays: invalid or duplicate id {oid!r}")
        seen.add(oid)
        root_raw = raw.get("root")
        if not isinstance(root_raw, str) or not root_raw:
            raise OverlayConfigError(f"overlays: overlay {oid!r} needs a root")
        root = expand_home(root_raw, home)
        if not root.is_absolute():
            raise OverlayConfigError(f"overlays: overlay {oid!r} root must be absolute or start with ~")
        layout = raw.get("layout", "category")
        if layout not in _LAYOUTS:
            raise OverlayConfigError(f"overlays: overlay {oid!r} layout must be one of {sorted(_LAYOUTS)}")
        kinds = raw.get("kinds", ["skills"])
        if not isinstance(kinds, list) or not kinds or not set(kinds) <= _KINDS:
            raise OverlayConfigError(f"overlays: overlay {oid!r} kinds must be a subset of {sorted(_KINDS)}")
        exclude = raw.get("exclude", [])
        if not isinstance(exclude, list) or not all(isinstance(e, str) and e for e in exclude):
            raise OverlayConfigError(f"overlays: overlay {oid!r} exclude must be a list of relative paths")
        prefix = raw.get("prefix", "")
        if not isinstance(prefix, str) or "/" in prefix:
            raise OverlayConfigError(f"overlays: overlay {oid!r} prefix must be a string without '/'")
        if is_inside(realpath(root), repo_real) or is_inside(os.path.normpath(str(root)), repo_real):
            raise OverlayConfigError(f"overlays: overlay {oid!r} root {root} is inside the repo; rejected")
        ov = Overlay(
            id=oid,
            root=root,
            layout=layout,
            prefix=prefix,
            kinds=tuple(kinds),
            exclude=tuple(e.strip("/") for e in exclude),
        )
        cfg.overlays.append(ov)
    _check_overlap(cfg.overlays)
    for ov in cfg.overlays:
        ov.available = ov.root.is_dir() and os.access(ov.root, os.R_OK | os.X_OK)
        if ov.available:
            _scan_overlay(ov)
    return cfg


def _check_overlap(overlays: list[Overlay]) -> None:
    for outer in overlays:
        for inner in overlays:
            if outer is inner:
                continue
            o_path = realpath(outer.root)
            i_path = realpath(inner.root)
            if o_path == i_path:
                raise OverlayConfigError(f"overlays: {outer.id!r} and {inner.id!r} share root {outer.root}")
            if is_inside(i_path, o_path):
                rel = os.path.relpath(i_path, o_path).replace(os.sep, "/")
                if not _excluded(rel, outer.exclude):
                    raise OverlayConfigError(
                        f"overlays: {inner.id!r} root is inside {outer.id!r}; add {rel!r} to {outer.id!r} exclude"
                    )


def overlay_files(ov: Overlay) -> list[Path]:
    """Every regular file under an available overlay root (for leak/repair scans)."""
    if not ov.available:
        return []
    return [ov.root / rel for rel in iter_tree_files(ov.root)]
