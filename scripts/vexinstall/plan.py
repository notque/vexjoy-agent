"""Desired state plus diff against disk and ledger. Pure: never writes."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import gitutil
from .adapters import ADAPTERS, Adapter, Collision, DesiredEntry, desired_for, effective_adapter
from .common import (
    DATA_DIRS,
    MASS_REMOVE_FRACTION,
    MASS_REMOVE_MAX,
    file_sha256,
    is_inside,
    iter_tree_files,
    realpath,
    tree_sha256,
)
from .ledger import STATUS_STALE, Ledger, LedgerEntry
from .profile import EMPTY, Profile
from .sources import OverlayConfig, PublicSources, SourceItem

# Ops that change disk.
WRITE_OPS = frozenset({"add", "replace", "remove", "container"})
PROFILE_REASON = "disabled by install profile"
COLLAPSE_REASON = "folded into whole-dir entry"
TAKEOVER_REASON = "takeover: unowned entry moved to trash and replaced"


@dataclass
class Action:
    """One planned step."""

    op: str  # add|replace|keep|adopt|remove|container|forget|stale|skip|blocked|collision
    target: str
    dest: str
    kind: str | None = None
    source: str | None = None
    owner: str | None = None
    mode: str | None = None
    sha256: str | None = None
    adopt: bool = False
    takeover: bool = False
    reason: str = ""
    files: tuple[str, ...] | None = None

    def to_json(self) -> dict:
        """Serializable form (drops the copy file list)."""
        d = asdict(self)
        d.pop("files", None)
        return {k: v for k, v in d.items() if v not in (None, "", False)}


@dataclass
class TargetPlan:
    """Plan for one target."""

    target: str
    actions: list[Action] = field(default_factory=list)
    collisions: list[Collision] = field(default_factory=list)
    owned_before: int = 0
    cap_tripped: bool = False
    profile_removals: int = 0  # removals the install profile asked for; exempt from the cap

    def count(self, *ops: str) -> int:
        """Number of actions with any of *ops*."""
        return sum(1 for a in self.actions if a.op in ops)

    @property
    def removals(self) -> int:
        """Removals and container swaps (takeover included)."""
        return self.count("remove", "container")

    @property
    def takeovers(self) -> int:
        """Unowned entries replaced by ``apply --takeover``."""
        return sum(1 for a in self.actions if a.takeover)

    @property
    def adoptions(self) -> int:
        """Entries adopted into the ledger."""
        return sum(1 for a in self.actions if a.adopt)

    def summary(self) -> dict:
        """Counts per op."""
        return {
            "add": self.count("add"),
            "replace": self.count("replace"),
            "remove": self.removals,
            "adopt": self.adoptions,
            "takeover": self.takeovers,
            "keep": self.count("keep", "adopt"),
            "skip": self.count("skip"),
            "blocked": self.count("blocked"),
            "stale": self.count("stale"),
            "collisions": len(self.collisions),
            "cap_tripped": self.cap_tripped,
        }


@dataclass
class Plan:
    """Whole plan."""

    source_root: str
    mode: str
    ledger_state: str
    full_adoption: bool
    targets: dict[str, TargetPlan] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def collisions(self) -> list[Collision]:
        """Collisions across targets."""
        return [c for tp in self.targets.values() for c in tp.collisions]

    @property
    def cap_tripped(self) -> list[str]:
        """Targets whose removals exceed the cap."""
        return [t for t, tp in self.targets.items() if tp.cap_tripped]

    def to_json(self) -> dict:
        """Serializable form."""
        return {
            "source_root": self.source_root,
            "mode": self.mode,
            "ledger_state": self.ledger_state,
            "full_adoption": self.full_adoption,
            "notes": self.notes,
            "targets": {
                t: {
                    "summary": tp.summary(),
                    "owned_before": tp.owned_before,
                    "collisions": [c.describe() for c in tp.collisions],
                    "actions": [a.to_json() for a in tp.actions if a.op not in ("keep",)],
                }
                for t, tp in self.targets.items()
            },
        }


@dataclass
class Context:
    """Inputs shared by plan, apply, and doctor."""

    home: Path
    source_root: Path
    state_dir: Path
    mode: str
    public: PublicSources
    overlays: OverlayConfig
    ledger: Ledger
    ledger_state: str
    profile: Profile = EMPTY

    def adapter(self, target: str) -> Adapter:
        """Layout for *target* adjusted for the install profile."""
        return effective_adapter(ADAPTERS[target], self.profile)

    def known_roots(self) -> list[str]:
        """Realpaths that make a symlink adoptable."""
        roots = [realpath(self.source_root)]
        if self.ledger.source_root:
            roots.append(os.path.normpath(self.ledger.source_root))
            roots.append(realpath(self.ledger.source_root))
        roots.extend(realpath(o.root) for o in self.overlays.overlays)
        roots.extend(os.path.normpath(str(o.root)) for o in self.overlays.overlays)
        return list(dict.fromkeys(roots))


class _Hashes:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, tuple[str, ...] | None], str | None] = {}

    def of(self, path: Path, files: tuple[str, ...] | None = None) -> str | None:
        key = (str(path), files)
        if key not in self._cache:
            self._cache[key] = tree_sha256(path, files)
        return self._cache[key]


def _link_target(path: Path) -> str:
    raw = os.readlink(path)
    if not os.path.isabs(raw):
        raw = os.path.join(os.path.dirname(str(path)), raw)
    return os.path.normpath(raw)


def link_points_into(path: Path, roots: list[str]) -> bool:
    """True when the link text or its realpath lies inside a known root."""
    try:
        literal = _link_target(path)
    except OSError:
        return False
    resolved = realpath(path)
    return any(is_inside(literal, r) or is_inside(resolved, r) for r in roots)


def copy_matches_source(dest: Path, src: Path) -> bool:
    """Every file in the *dest* copy exists in *src* with identical bytes."""
    try:
        if dest.is_file():
            return src.is_file() and file_sha256(dest) == file_sha256(src)
        if not dest.is_dir() or not src.is_dir():
            return False
        rels = list(iter_tree_files(dest))
        if not rels:
            return False
        for rel in rels:
            s = src / rel
            if not s.is_file() or file_sha256(dest / rel) != file_sha256(s):
                return False
        return True
    except OSError:
        return False


def candidate_sources(adapter: Adapter, home: Path, pub: PublicSources, cfg: OverlayConfig) -> dict[str, list[Path]]:
    """Known source paths by dest path, used to prove ownership of copies."""
    root = adapter.root_path(home)
    out: dict[str, list[Path]] = {}

    def add(dest: Path, src: Path) -> None:
        out.setdefault(str(dest), []).append(src)

    overlay_skills: list[SourceItem] = []
    overlay_agents: list[SourceItem] = []
    for ov in cfg.overlays:
        overlay_skills += ov.skills + ov.data
        overlay_agents += ov.agents
    if adapter.skills:
        sk = root / adapter.skills
        for item in pub.skills + pub.promoted + pub.support + pub.data + overlay_skills:
            add(sk / item.name, item.source)
        for name, path in pub.categories.items():
            add(sk / name, path)
    if adapter.agents:
        for item in pub.agents + overlay_agents:
            add(root / adapter.agents / item.name, item.source)
    if adapter.commands:
        for item in pub.commands:
            add(root / adapter.commands / f"{item.name}.md", item.source)
    if pub.hooks_dir is not None:
        add(root / "hooks", pub.hooks_dir)
        for item in pub.hook_items:
            add(root / "hooks" / item.name, item.source)
        add(root / "hooks" / "lib", pub.hooks_dir / "lib")
        for item in pub.hook_lib_items:
            add(root / "hooks" / "lib" / item.name, item.source)
    if pub.scripts_dir is not None:
        add(root / "scripts", pub.scripts_dir)
        for item in pub.script_items:
            add(root / "scripts" / item.name, item.source)
    return out


def symlink_below(path: Path, stop: Path) -> Path | None:
    """First symlinked dir strictly between *stop* and *path* (parents only)."""
    stop_s = os.path.normpath(str(stop))
    current = path.parent
    while is_inside(current, stop_s) and os.path.normpath(str(current)) != stop_s:
        if os.path.islink(current):
            return current
        current = current.parent
    return None


def _matches(dest: Path, de: DesiredEntry, hashes: _Hashes) -> bool:
    if de.mode == "symlink":
        try:
            return os.path.islink(dest) and _link_target(dest) == os.path.normpath(str(de.source))
        except OSError:
            return False
    if os.path.islink(dest):
        return False
    return hashes.of(dest) == hashes.of(de.source, de.files)


def _user_edited(dest: Path, led: LedgerEntry, hashes: _Hashes) -> bool:
    if led.mode != "copy" or not led.sha256 or os.path.islink(dest):
        return False
    return hashes.of(dest) != led.sha256


def _action(op: str, de: DesiredEntry, hashes: _Hashes, **kw: object) -> Action:
    sha = hashes.of(de.source, de.files) if de.mode == "copy" else None
    return Action(
        op=op,
        target=de.target,
        dest=str(de.dest),
        kind=de.kind,
        source=str(de.source),
        owner=de.owner,
        mode=de.mode,
        sha256=sha,
        files=de.files,
        **kw,  # type: ignore[arg-type]
    )


def plan_target(
    ctx: Context,
    target: str,
    full_adoption: bool,
    hashes: _Hashes | None = None,
    *,
    takeover: bool = False,
) -> TargetPlan:
    """Diff desired state for one target against disk and ledger.

    *takeover* (``apply --takeover``, never sync): an unowned entry at a desired
    dest, or an unowned symlink/file where a container dir belongs, is moved to
    trash and replaced. Unowned entries at undesired paths are never touched.
    A target with no ledger entries gets a full adoption scan (its first run).
    """
    hashes = hashes or _Hashes()
    adapter = ctx.adapter(target)
    home = ctx.home
    root = adapter.root_path(home)
    desire = desired_for(adapter, home, ctx.public, ctx.overlays, ctx.mode, ctx.profile)
    led_entries = ctx.ledger.for_target(target)
    full_adoption = full_adoption or not led_entries
    roots = ctx.known_roots()
    cands = candidate_sources(adapter, home, ctx.public, ctx.overlays)
    tp = TargetPlan(target=target, collisions=list(desire.collisions))

    def adoptable(dest: Path) -> bool:
        if os.path.islink(dest):
            return link_points_into(dest, roots)
        return any(copy_matches_source(dest, src) for src in cands.get(str(dest), []))

    # Containers: must be real dirs. Owned or adoptable whole-dir links become dirs.
    replaced: set[str] = set()
    blocked: dict[str, str] = {}
    for container in adapter.containers(home):
        c = str(container)
        above = symlink_below(container, root)
        if above is not None and str(above) not in replaced:
            blocked[c] = f"parent {above} is a symlink"
            continue
        if any(is_inside(c, r) and c != r for r in replaced):
            continue
        if os.path.islink(container):
            if c in led_entries or link_points_into(container, roots):
                replaced.add(c)
                tp.actions.append(
                    Action(
                        op="container",
                        target=target,
                        dest=c,
                        kind="container",
                        adopt=c not in led_entries,
                        reason="whole-dir symlink replaced by a real directory",
                    )
                )
            elif takeover:
                replaced.add(c)
                tp.actions.append(
                    Action(
                        op="container", target=target, dest=c, kind="container", takeover=True, reason=TAKEOVER_REASON
                    )
                )
            else:
                blocked[c] = "container is an unowned symlink"
        elif os.path.lexists(container) and not os.path.isdir(container):
            if takeover:
                replaced.add(c)
                tp.actions.append(
                    Action(
                        op="container", target=target, dest=c, kind="container", takeover=True, reason=TAKEOVER_REASON
                    )
                )
            else:
                blocked[c] = "container path is not a directory"

    def container_status(dest: Path) -> tuple[str | None, bool]:
        """(blocked reason, under replaced container)."""
        d = str(dest)
        for c, why in blocked.items():
            if is_inside(d, c) and d != c:
                return why, False
        for c in replaced:
            if is_inside(d, c) and d != c:
                return None, True
        above = symlink_below(dest, root)
        if above is not None and not any(is_inside(str(above), c) for c in replaced):
            return f"parent {above} is a symlink", False
        return None, False

    collision_dests = {str(c.dest) for c in desire.collisions}
    for col in desire.collisions:
        tp.actions.append(
            Action(op="collision", target=target, dest=str(col.dest), reason=col.describe(), kind=col.claims[0].kind)
        )
    for item in desire.shadowed_commands:
        tp.actions.append(
            Action(
                op="skip",
                target=target,
                dest=item.name,
                kind="command",
                source=str(item.source),
                reason=f"command '{item.name}' shadowed by skill of the same name",
            )
        )

    adopted = 0
    for d, de in sorted(desire.entries.items()):
        dest = de.dest
        why, fresh = container_status(dest)
        if why:
            tp.actions.append(_action("blocked", de, hashes, reason=why))
            continue
        led = led_entries.get(d)
        if fresh or not os.path.lexists(dest):
            tp.actions.append(_action("add", de, hashes))
            continue
        if led is not None:
            if _matches(dest, de, hashes):
                tp.actions.append(_action("keep", de, hashes))
            elif _user_edited(dest, led, hashes):
                tp.actions.append(_action("skip", de, hashes, reason="user-edited copy; not replaced"))
            else:
                tp.actions.append(_action("replace", de, hashes, reason=_why_replace(dest, de, led)))
            continue
        if adoptable(dest):
            adopted += 1
            if _matches(dest, de, hashes):
                tp.actions.append(_action("adopt", de, hashes, adopt=True))
            else:
                tp.actions.append(_action("replace", de, hashes, adopt=True, reason="adopted; differs from source"))
            continue
        if takeover:
            tp.actions.append(_action("replace", de, hashes, takeover=True, reason=TAKEOVER_REASON))
        else:
            tp.actions.append(_action("blocked", de, hashes, reason="unowned entry occupies dest"))

    stale_ids = {o.id for o in ctx.overlays.overlays if not o.available}
    for d, led in sorted(led_entries.items()):
        if d in desire.entries or d in collision_dests:
            continue
        if any(is_inside(d, c) and d != c for c in replaced):
            # Entries recorded under a replaced container move with it.
            continue
        if d in replaced:
            # A whole-dir entry that is now a container (profile per-entry hooks):
            # the container op already trashed the link; only drop the record.
            tp.actions.append(
                Action(op="forget", target=target, dest=d, kind=led.kind, reason="whole-dir entry became a container")
            )
            continue
        ov_id = led.owner.split(":", 1)[1] if led.owner.startswith("overlay:") else None
        base = Action(
            op="remove",
            target=target,
            dest=d,
            kind=led.kind,
            source=led.source,
            owner=led.owner,
            mode=led.mode,
        )
        dest = Path(d)
        if ov_id is not None and ov_id in stale_ids:
            base.op, base.reason = "stale", STATUS_STALE
        elif not os.path.lexists(dest):
            base.op, base.reason = "forget", "missing on disk"
        elif _user_edited(dest, led, hashes):
            base.op, base.reason = "skip", "user-edited copy; not removed"
        elif d in desire.filtered:
            base.reason = PROFILE_REASON
        elif any(is_inside(d, e) and d != e for e in desire.entries):
            # Per-entry hooks going back to one whole-dir link (hook profile cleared).
            base.reason = COLLAPSE_REASON
        else:
            base.reason = "dangling link" if os.path.islink(dest) and not os.path.exists(dest) else "no longer desired"
        tp.actions.append(base)

    if full_adoption:
        skip = set(desire.entries) | collision_dests
        tp.actions.extend(_adopt_scan(adapter, home, skip, led_entries, replaced, adoptable, target))
        adopted += sum(1 for a in tp.actions if a.op == "remove" and a.adopt)

    tp.owned_before = len(led_entries) + adopted + sum(1 for a in tp.actions if a.op == "container" and a.adopt)
    # Fraction base: owned entries, or the desired count when larger (a first install
    # that fixes one legacy link is not a mass removal; a shrinking repo still is).
    cap_base = max(tp.owned_before, len(desire.entries))
    # Profile removals are explicit user config (install.sh removes them uncapped),
    # as are containers the profile forces (whole-dir hooks -> per-entry) and
    # per-entry links folded back into a whole-dir entry.
    profile_containers = {str(c) for c in adapter.containers(home)} - {
        str(c) for c in ADAPTERS[target].containers(home)
    }
    tp.profile_removals = sum(
        1 for a in tp.actions if a.op == "remove" and a.reason in (PROFILE_REASON, COLLAPSE_REASON)
    ) + sum(1 for a in tp.actions if a.op == "container" and a.dest in profile_containers)
    # Takeover swaps replace an entry in place; they are not removals.
    removals = tp.removals - tp.profile_removals - sum(1 for a in tp.actions if a.op == "container" and a.takeover)
    tp.cap_tripped = removals > MASS_REMOVE_MAX or (cap_base > 0 and removals > MASS_REMOVE_FRACTION * cap_base)
    return tp


def _why_replace(dest: Path, de: DesiredEntry, led: LedgerEntry) -> str:
    if led.mode != de.mode:
        return f"mode {led.mode} -> {de.mode}"
    if os.path.normpath(led.source) != os.path.normpath(str(de.source)):
        return "source moved"
    if os.path.islink(dest) and not os.path.exists(dest):
        return "dangling link"
    return "content differs"


def _adopt_scan(
    adapter: Adapter,
    home: Path,
    desired: set[str],
    led_entries: dict[str, LedgerEntry],
    replaced: set[str],
    adoptable: object,
    target: str,
) -> list[Action]:
    """First run / recovery: adopt undesired engine-shaped entries for removal."""
    out: list[Action] = []
    for container in adapter.containers(home):
        c = str(container)
        if c in replaced or os.path.islink(container) or not os.path.isdir(container):
            continue
        for child in sorted(os.listdir(container)):
            if child.startswith(".") or child in DATA_DIRS:
                continue
            dest = container / child
            d = str(dest)
            if d in desired or d in led_entries:
                continue
            if any(is_inside(str(o), d) for o in adapter.containers(home)):
                continue  # a container (hooks/lib) is not an entry
            if adoptable(dest):  # type: ignore[operator]
                out.append(
                    Action(
                        op="remove",
                        target=target,
                        dest=d,
                        kind="adopted",
                        adopt=True,
                        mode="symlink" if os.path.islink(dest) else "copy",
                        reason="adopted legacy entry; not desired",
                    )
                )
    return out


def build_plan(ctx: Context, targets: list[str], full_adoption: bool, *, takeover: bool = False) -> Plan:
    """Plan every requested target."""
    plan = Plan(
        source_root=str(ctx.source_root),
        mode=ctx.mode,
        ledger_state=ctx.ledger_state,
        full_adoption=full_adoption,
    )
    dups = ctx.public.duplicate_skill_names()
    for name, items in sorted(dups.items()):
        plan.notes.append(f"public skill name '{name}' defined twice: " + ", ".join(str(i.source) for i in items))
    prof = ctx.profile
    if prof.active:
        plan.notes.append(
            f"install profile {prof.path}: disabled {len(prof.skills)} skills, "
            f"{len(prof.agents)} agents, {len(prof.hooks)} hooks"
        )
    hashes = _Hashes()
    for t in targets:
        plan.targets[t] = plan_target(ctx, t, full_adoption, hashes, takeover=takeover)
    for ov in ctx.overlays.overlays:
        if not ov.available:
            plan.notes.append(f"overlay '{ov.id}' root {ov.root} missing; its entries kept as {STATUS_STALE}")
    return plan


def default_mode(source_root: Path) -> str:
    """symlink for a main git checkout outside ephemeral paths, else copy."""
    if gitutil.is_git_checkout(source_root) and not gitutil.is_worktree(source_root):
        if not gitutil.is_ephemeral(source_root):
            return "symlink"
    return "copy"


def source_refusal(ctx: Context, adopt_source: bool) -> str | None:
    """Why this run must not touch installs (spec 6.4), or None."""
    if adopt_source:
        return None
    if ctx.mode == "symlink":
        if gitutil.is_worktree(ctx.source_root):
            return f"source {ctx.source_root} is a git worktree"
        if gitutil.is_ephemeral(ctx.source_root):
            return f"source {ctx.source_root} is under an ephemeral path"
    old = ctx.ledger.source_root
    if old and realpath(old) != realpath(ctx.source_root) and os.path.isdir(old):
        return f"source {ctx.source_root} is not the ledger source_root {old} (still present)"
    return None
