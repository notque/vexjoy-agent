"""apply / sync / uninstall / prune / restore commands (all writes happen here)."""

from __future__ import annotations

import os
import time
from pathlib import Path

from . import external
from . import index as index_mod
from . import ledger as ledger_mod
from . import settings as settings_mod
from .adapters import ADAPTERS, resolve_targets
from .common import (
    APPLY_LOCK_TIMEOUT_S,
    DATA_DIRS,
    SUPPORT_DIRS,
    TRASH_RETENTION_DAYS,
    ExitCode,
    GuardError,
    LockTimeoutError,
    OverlayConfigError,
    is_dangling,
    is_inside,
    realpath,
    tree_sha256,
    utc_iso,
    utc_ts,
)
from .context import Options, Result, guard_for, load_context, state_dir
from .fsops import Guard, Trash, atomic_symlink, copy_entry, mkdirs, prune_trash, restore_trash
from .ledger import STATUS_OK, STATUS_STALE, Ledger, LedgerEntry
from .lock import LockHeld, engine_lock
from .plan import Action, Context, Plan, TargetPlan, build_plan, source_refusal
from .profile import filter_settings_hooks
from .report import plan_diff, summary_line, write_report


def repo_root_refusal(ctx: Context, targets: list[str]) -> str | None:
    """Why no command may touch these targets: a runtime or state root inside a protected root.

    HOME pointing at (or into) the repo makes ``~/.claude`` resolve inside the
    working tree; every write would land in ``repo/.claude`` (spec 7.4, 11).
    """
    protected = guard_for(ctx).protected
    roots = [("state", state_dir(ctx.home))] + [(t, ADAPTERS[t].root_path(ctx.home)) for t in targets]
    for label, root in roots:
        rp = realpath(root)
        for prot in protected:
            if is_inside(rp, prot):
                return f"guard: {label} root {root} resolves inside {prot}; refusing (is HOME set to the repo?)"
    return None


def _plan_lines(plan: Plan) -> list[str]:
    lines = [f"source_root: {plan.source_root}  mode: {plan.mode}  ledger: {plan.ledger_state}"]
    if plan.full_adoption:
        lines.append("adoption: ledger missing or corrupt; adoptable entries on disk will be adopted")
    for t, tp in plan.targets.items():
        s = tp.summary()
        lines.append(
            f"{t}: +{s['add']} ~{s['replace']} -{s['remove']} adopt={s['adopt']} keep={s['keep']} "
            f"skip={s['skip']} blocked={s['blocked']} stale={s['stale']} collisions={s['collisions']}"
            + (f" takeover={s['takeover']}" if s["takeover"] else "")
            + (" CAP-TRIPPED" if s["cap_tripped"] else "")
        )
        for a in tp.actions:
            if a.op in ("keep", "adopt"):
                continue
            tag = "adopt+" if a.adopt else "takeover+" if a.takeover else ""
            reason = f"  ({a.reason})" if a.reason else ""
            lines.append(f"  {tag}{a.op:9} {a.dest}{reason}")
    lines.extend(f"note: {n}" for n in plan.notes)
    return lines


def run_plan(opts: Options) -> Result:
    """Pure plan; exit 3 on collisions."""
    try:
        ctx = load_context(opts)
    except OverlayConfigError as exc:
        return Result(code=int(exc.exit_code), err=[str(exc)])
    targets = resolve_targets(opts.target, ctx.home)
    guard_msg = repo_root_refusal(ctx, targets)
    if guard_msg:
        return Result(code=int(ExitCode.GUARD), err=[f"[plan] {guard_msg}"])
    plan = build_plan(ctx, targets, full_adoption=ctx.ledger_state != "ok", takeover=opts.takeover)
    refusal = source_refusal(ctx, opts.adopt_source)
    if refusal:
        plan.notes.append(f"apply/sync would refuse: {refusal}")
    for t in targets:
        for f in external.desired(t, ADAPTERS[t].root_path(ctx.home), ctx.source_root, ctx.profile):
            if f.error:
                plan.notes.append(f"external {f.path}: {f.error}")
            elif f.changed():
                plan.notes.append(f"external {f.path}: would write")
    res = Result(data=plan.to_json(), out=_plan_lines(plan))
    if plan.collisions or ctx.public.duplicate_skill_names():
        res.code = int(ExitCode.COLLISION)
        res.err.extend(f"collision: {c.describe()}" for c in plan.collisions)
    return res


def _install(a: Action, guard: Guard) -> None:
    dest = Path(a.dest)
    mkdirs(dest.parent, guard)
    src = Path(str(a.source))
    if a.mode == "symlink":
        atomic_symlink(dest, src, guard)
    else:
        copy_entry(src, dest, guard, a.files)


def _record(ledger: Ledger, a: Action, now: str) -> None:
    prev = ledger.entries.get(a.dest)
    ledger.entries[a.dest] = LedgerEntry(
        target=a.target,
        dest=a.dest,
        kind=str(a.kind),
        source=str(a.source),
        owner=str(a.owner),
        mode=str(a.mode),
        created_at=prev.created_at if prev else now,
        sha256=a.sha256 if a.mode == "copy" else None,
        status=STATUS_OK,
    )


def execute_target(tp: TargetPlan, ctx: Context, trash: Trash, guard: Guard, ledger: Ledger, skip: set[str]) -> None:
    """Carry out one target's plan. Ops are atomic per file; ledger updated in memory."""
    now = utc_iso()
    home = ctx.home
    for a in tp.actions:
        if a.op == "container":
            trash.move(Path(a.dest), home, "whole-dir symlink replaced by real dir")
            mkdirs(Path(a.dest), guard)
    for a in tp.actions:
        if a.dest in skip:
            continue
        if a.op == "remove":
            trash.move(Path(a.dest), home, a.reason or "removed")
            ledger.entries.pop(a.dest, None)
        elif a.op == "forget":
            ledger.entries.pop(a.dest, None)
        elif a.op == "stale" and a.dest in ledger.entries:
            ledger.entries[a.dest].status = STATUS_STALE
    for a in tp.actions:
        if a.dest in skip:
            continue
        dest = Path(a.dest)
        if a.op == "replace":
            if a.mode == "symlink" and os.path.islink(dest) and not a.takeover:
                atomic_symlink(dest, Path(str(a.source)), guard)
            else:
                if os.path.lexists(dest):
                    trash.move(dest, home, a.reason if a.takeover else f"replaced ({a.reason})")
                _install(a, guard)
            _record(ledger, a, now)
        elif a.op == "add":
            _install(a, guard)
            _record(ledger, a, now)
        elif a.op in ("keep", "adopt"):
            _record(ledger, a, now)


def apply_settings(ctx: Context, ledger: Ledger, guard: Guard, *, desired: dict | None) -> dict:
    """Merge owned hook entries and missing repo env vars into ~/.claude/settings.json.

    Env vars are added only on install (``desired`` is None), never overwritten, and
    never removed on uninstall. Returns a report dict.
    """
    home = ctx.home
    spath = home / ".claude" / "settings.json"
    desired_env: dict[str, str] = {}
    if desired is None:
        repo_settings = ctx.source_root / ".claude" / "settings.json"
        if not repo_settings.is_file():
            return {"skipped": "repo .claude/settings.json missing"}
        desired = filter_settings_hooks(settings_mod.desired_from_repo(ctx.source_root), ctx.profile)
        desired_env = settings_mod.desired_env_from_repo(ctx.source_root)
    try:
        current = settings_mod.read_settings(spath)
    except ValueError as exc:
        return {"skipped": f"settings.json unreadable: {exc}"}
    rule = settings_mod.OwnerRule(home=home, hooks_dir=home / ".claude" / "hooks", source_root=ctx.source_root)
    res = settings_mod.merge(current, desired, rule)
    env_added = settings_mod.merge_env(res.settings, desired_env)
    env_removed = settings_mod.remove_retired_env(res.settings) if desired_env else []
    backup_ts = None
    if res.changed or env_added or env_removed:
        backup_ts = settings_mod.backup(spath, state_dir(home) / "backups", guard)
        settings_mod.write(spath, res.settings, guard)
    ledger.settings["claude"] = res.owned_hashes
    return {
        "added": res.added,
        "removed": res.removed,
        "deduped": res.deduped,
        "env_added": env_added,
        "env_removed": env_removed,
        "unmanaged_in_repo": res.unmanaged,
        "backup": backup_ts,
    }


def _write_indexes(ctx: Context, ledger: Ledger, targets: list[str], guard: Guard) -> list[str]:
    written: list[str] = []
    for t in targets:
        written.extend(index_mod.write(ctx.home, t, ledger, guard))
    return written


def run_apply(opts: Options, *, sync: bool) -> Result:
    """apply (sync=False) or sync (sync=True)."""
    label = "sync" if sync else "apply"
    if opts.dry_run:
        return run_plan(opts)
    try:
        ctx = load_context(opts)
    except OverlayConfigError as exc:
        if sync:
            return Result(code=0, err=[f"[sync] warning: {exc}"])
        return Result(code=int(exc.exit_code), err=[str(exc)])
    guard = guard_for(ctx)
    guard_msg = repo_root_refusal(ctx, resolve_targets(opts.target, ctx.home))
    if guard_msg:
        return Result(code=int(ExitCode.GUARD), err=[f"[{label}] ABORT {guard_msg}"])
    lock_path = state_dir(ctx.home) / "lock"
    try:
        with engine_lock(lock_path, guard, blocking=not sync, timeout=APPLY_LOCK_TIMEOUT_S):
            return _apply_locked(ctx, opts, sync, guard, label)
    except LockHeld:
        return Result(code=0)
    except LockTimeoutError as exc:
        return Result(code=int(exc.exit_code), err=[str(exc)])
    except GuardError as exc:
        return Result(code=int(ExitCode.GUARD), err=[f"[{label}] ABORT {exc}"], data={"guard": exc.path})
    except Exception as exc:
        if sync:
            return Result(code=0, err=[f"[sync] warning: engine error {type(exc).__name__}: {exc}"])
        raise


def _apply_locked(ctx: Context, opts: Options, sync: bool, guard: Guard, label: str) -> Result:
    t0 = time.monotonic()
    res = Result()
    sdir = state_dir(ctx.home)
    lpath = ledger_mod.ledger_path(sdir)
    led, state = ledger_mod.load(lpath)
    if state == "corrupt":
        moved = ledger_mod.quarantine(lpath, guard)
        res.err.append(f"[{label}] ledger corrupt; moved to {moved}; running adoption")
    ledger = led or Ledger()
    ctx.ledger = ledger
    ctx.ledger_state = state
    refusal = source_refusal(ctx, opts.adopt_source)
    if refusal:
        if sync:
            return Result(code=0, out=[f"[sync] skipped: {refusal} (pass --adopt-source to re-point)"])
        return Result(code=int(ExitCode.SOURCE_REFUSED), err=[f"[apply] refused: {refusal}; pass --adopt-source"])
    targets = resolve_targets(opts.target, ctx.home)
    if opts.index_only:
        # A target with no owned entries has never been applied: writing its
        # index would publish an empty catalog that shadows the repo fallback.
        written = _write_indexes(ctx, ledger, [t for t in targets if ledger.for_target(t)], guard)
        return Result(code=0, out=[] if sync else [f"[{label}] indexes: {len(written)} written"])
    plan = build_plan(ctx, targets, full_adoption=state != "ok", takeover=opts.takeover and not sync)
    skip: set[str] = set()
    if plan.collisions or ctx.public.duplicate_skill_names():
        lines = [f"collision: {c.describe()}" for c in plan.collisions] + [f"collision: {n}" for n in plan.notes]
        if not sync:
            return Result(code=int(ExitCode.COLLISION), err=lines, data=plan.to_json())
        skip = {str(c.dest) for c in plan.collisions}
        res.err.append(f"[sync] warning: {len(plan.collisions)} collision(s) left as-is: " + "; ".join(lines))
    tripped = plan.cap_tripped
    if tripped and (sync or not opts.allow_mass_remove):
        detail = ", ".join(f"{t} removes {plan.targets[t].removals} of {plan.targets[t].owned_before}" for t in tripped)
        msg = f"[{label}] mass-removal cap exceeded ({detail}); no changes made"
        if sync:
            return Result(code=0, err=[msg + "; run apply --allow-mass-remove after review"], data=plan.to_json())
        return Result(code=int(ExitCode.MASS_REMOVE), err=[msg + "; review with plan, then --allow-mass-remove"])

    ts = utc_ts()
    trash = Trash(root=sdir / "trash", ts=ts, guard=guard)
    report: dict = {
        "ts": ts,
        "command": label,
        "source_root": str(ctx.source_root),
        "mode": ctx.mode,
        "targets": targets,
        "diff": plan_diff(plan),
        "notes": plan.notes,
    }
    guard_hit: GuardError | None = None
    try:
        for t in targets:
            execute_target(plan.targets[t], ctx, trash, guard, ledger, skip)
        if "claude" in targets:
            report["settings"] = apply_settings(ctx, ledger, guard, desired=None)
        ext: list[external.ExternalFile] = []
        for t in targets:
            ext.extend(external.desired(t, ADAPTERS[t].root_path(ctx.home), ctx.source_root, ctx.profile))
        report["external"] = external.write(ext, sdir / "backups", guard)
        res.err.extend(f"[{label}] warning: external {e}" for e in report["external"]["errors"])
    except GuardError as exc:
        guard_hit = exc
    ledger.source_root = str(ctx.source_root)
    ledger.mode = ctx.mode
    ledger.overlays_mtime = ctx.overlays.mtime
    try:
        ledger_mod.save(lpath, ledger, guard)
    except GuardError as exc:
        guard_hit = guard_hit or exc
    if guard_hit is None:
        try:
            report["index"] = _write_indexes(ctx, ledger, targets, guard)
        except GuardError as exc:
            guard_hit = exc
    report["timings_ms"] = int((time.monotonic() - t0) * 1000)
    report["trash"] = str(trash.dir) if trash.items else None
    if guard_hit is not None:
        report["guard"] = guard_hit.path
    try:
        report["report"] = str(write_report(sdir / "reports", ts, report, guard))
    except GuardError:
        pass
    if guard_hit is not None:
        return Result(code=int(ExitCode.GUARD), err=[f"[{label}] ABORT {guard_hit}"], data=report)
    prune_trash(sdir / "trash", TRASH_RETENTION_DAYS)
    res.data = report
    line = summary_line(label, plan, ledger)
    res.out.append(line)
    if not sync:
        res.out.extend(_plan_lines(plan)[1:])
    return res


def run_uninstall(opts: Options) -> Result:
    """Move every ledger entry of the chosen targets to trash; remove owned settings entries."""
    try:
        ctx = load_context(opts)
    except OverlayConfigError as exc:
        return Result(code=int(exc.exit_code), err=[str(exc)])
    targets = resolve_targets(opts.target, ctx.home)
    guard_msg = repo_root_refusal(ctx, targets)
    if guard_msg:
        return Result(code=int(ExitCode.GUARD), err=[f"[uninstall] ABORT {guard_msg}"])
    owned = [e for e in ctx.ledger.entries.values() if e.target in targets]
    if opts.dry_run:
        return Result(out=[f"would remove {e.dest}" for e in owned] + [f"{len(owned)} entries"])
    guard = guard_for(ctx)
    sdir = state_dir(ctx.home)
    try:
        with engine_lock(sdir / "lock", guard, blocking=True, timeout=APPLY_LOCK_TIMEOUT_S):
            ts = utc_ts()
            trash = Trash(root=sdir / "trash", ts=ts, guard=guard)
            removed, skipped = [], []
            for e in sorted(owned, key=lambda x: x.dest, reverse=True):
                dest = Path(e.dest)
                if (
                    e.mode == "copy"
                    and e.sha256
                    and os.path.lexists(dest)
                    and not os.path.islink(dest)
                    and tree_sha256(dest) != e.sha256
                ):
                    skipped.append(e.dest)
                    continue
                if os.path.lexists(dest):
                    trash.move(dest, ctx.home, "uninstall")
                    removed.append(e.dest)
                ctx.ledger.entries.pop(e.dest, None)
            settings_report = None
            if "claude" in targets:
                settings_report = apply_settings(ctx, ctx.ledger, guard, desired={})
                ctx.ledger.settings.pop("claude", None)
            ledger_mod.save(ledger_mod.ledger_path(sdir), ctx.ledger, guard)
            report = {
                "ts": ts,
                "command": "uninstall",
                "removed": removed,
                "skipped_user_edited": skipped,
                "settings": settings_report,
                "trash": str(trash.dir) if trash.items else None,
            }
            write_report(sdir / "reports", ts, report, guard)
    except GuardError as exc:
        return Result(code=int(ExitCode.GUARD), err=[f"[uninstall] ABORT {exc}"])
    except LockTimeoutError as exc:
        return Result(code=int(exc.exit_code), err=[str(exc)])
    out = [f"[uninstall] removed {len(removed)}, skipped {len(skipped)} user-edited; trash {ts}"]
    out.extend(f"  skipped (user-edited): {s}" for s in skipped)
    return Result(out=out, data=report)


def unowned_prunable(ctx: Context, targets: list[str]) -> list[tuple[str, str]]:
    """(path, reason) for unowned dangling links and category entries in managed containers."""
    out: list[tuple[str, str]] = []
    owned = set(ctx.ledger.entries)
    for t in targets:
        adapter = ctx.adapter(t)
        for container in adapter.containers(ctx.home):
            if os.path.islink(container) or not os.path.isdir(container):
                continue
            is_skills = adapter.skills is not None and container == adapter.root_path(ctx.home) / adapter.skills
            for child in sorted(os.listdir(container)):
                path = container / child
                if str(path) in owned or child.startswith("."):
                    continue
                if is_dangling(path):
                    out.append((str(path), "dangling link"))
                elif is_skills and is_category_entry(path):
                    out.append((str(path), "category entry in flat skills root"))
    return out


def is_category_entry(path: Path) -> bool:
    """A skills-root entry without SKILL.md that holds nested skills (not a support dir)."""
    if path.name in SUPPORT_DIRS or path.name in DATA_DIRS or not path.is_dir():
        return False
    if (path / "SKILL.md").exists() or (path / "skill" / "SKILL.md").exists():
        return False
    try:
        return any((child / "SKILL.md").is_file() for child in path.iterdir() if child.is_dir())
    except OSError:
        return False


def run_prune(opts: Options) -> Result:
    """``prune --unowned``: list; with ``--confirm`` move each to trash."""
    if not opts.unowned:
        return Result(code=int(ExitCode.USAGE), err=["prune requires --unowned"])
    try:
        ctx = load_context(opts)
    except OverlayConfigError as exc:
        return Result(code=int(exc.exit_code), err=[str(exc)])
    targets = resolve_targets(opts.target, ctx.home)
    guard_msg = repo_root_refusal(ctx, targets)
    if guard_msg:
        return Result(code=int(ExitCode.GUARD), err=[f"[prune] ABORT {guard_msg}"])
    items = unowned_prunable(ctx, targets)
    lines = [f"  {p}  ({why})" for p, why in items]
    if not opts.confirm or opts.dry_run:
        return Result(out=[f"[prune] {len(items)} unowned candidate(s); pass --confirm to trash them", *lines])
    guard = guard_for(ctx)
    sdir = state_dir(ctx.home)
    try:
        with engine_lock(sdir / "lock", guard, blocking=True, timeout=APPLY_LOCK_TIMEOUT_S):
            ts = utc_ts()
            trash = Trash(root=sdir / "trash", ts=ts, guard=guard)
            for p, why in items:
                trash.move(Path(p), ctx.home, f"prune --unowned: {why}")
            write_report(sdir / "reports", ts, {"ts": ts, "command": "prune", "trashed": trash.items}, guard)
    except GuardError as exc:
        return Result(code=int(ExitCode.GUARD), err=[f"[prune] ABORT {exc}"])
    return Result(out=[f"[prune] moved {len(items)} to trash {ts}", *lines])


def run_restore_trash(opts: Options) -> Result:
    """Put a trash session back; engine-owned occupants move to a new trash session."""
    if not opts.ts:
        return Result(code=int(ExitCode.USAGE), err=["restore-trash needs a <ts>"])
    try:
        ctx = load_context(opts)
    except OverlayConfigError as exc:
        return Result(code=int(exc.exit_code), err=[str(exc)])
    guard = guard_for(ctx)
    sdir = state_dir(ctx.home)
    guard_msg = repo_root_refusal(ctx, [])
    if guard_msg:
        return Result(code=int(ExitCode.GUARD), err=[f"[restore-trash] ABORT {guard_msg}"])
    try:
        with engine_lock(sdir / "lock", guard, blocking=True, timeout=APPLY_LOCK_TIMEOUT_S):
            led, _ = ledger_mod.load(ledger_mod.ledger_path(sdir))
            ledger = led or Ledger()
            displaced = Trash(root=sdir / "trash", ts=utc_ts(), guard=guard)

            def clear(path: Path) -> bool:
                p = str(path)
                owned_here = p in ledger.entries
                if not owned_here and os.path.isdir(path) and not os.path.islink(path):
                    children = os.listdir(path)
                    owned_here = bool(children) and all(os.path.join(p, c) in ledger.entries for c in children)
                if not owned_here:
                    return False
                displaced.move(path, ctx.home, f"displaced by restore-trash {opts.ts}")
                for d in [d for d in ledger.entries if d == p or d.startswith(p + os.sep)]:
                    ledger.entries.pop(d)
                return True

            restored, skipped = restore_trash(sdir / "trash", opts.ts, guard, clear)
            ledger_mod.save(ledger_mod.ledger_path(sdir), ledger, guard)
    except FileNotFoundError:
        return Result(code=int(ExitCode.USAGE), err=[f"no trash session {opts.ts}"])
    except GuardError as exc:
        return Result(code=int(ExitCode.GUARD), err=[f"[restore-trash] ABORT {exc}"])
    out = [f"[restore-trash] restored {len(restored)}, skipped {len(skipped)} (dest occupied or missing)"]
    if displaced.items:
        out.append(f"  displaced {len(displaced.items)} engine entries to trash {displaced.ts}")
    out.extend(f"  skipped: {s}" for s in skipped)
    return Result(out=out, data={"restored": restored, "skipped": skipped, "displaced_ts": displaced.ts})


def run_restore_settings(opts: Options) -> Result:
    """Restore ``backups/settings.<ts>.json``."""
    if not opts.ts:
        return Result(code=int(ExitCode.USAGE), err=["restore-settings needs a <ts>"])
    try:
        ctx = load_context(opts)
    except OverlayConfigError as exc:
        return Result(code=int(exc.exit_code), err=[str(exc)])
    guard = guard_for(ctx)
    sdir = state_dir(ctx.home)
    guard_msg = repo_root_refusal(ctx, [])
    if guard_msg:
        return Result(code=int(ExitCode.GUARD), err=[f"[restore-settings] ABORT {guard_msg}"])
    try:
        with engine_lock(sdir / "lock", guard, blocking=True, timeout=APPLY_LOCK_TIMEOUT_S):
            src = settings_mod.restore(ctx.home / ".claude" / "settings.json", sdir / "backups", opts.ts, guard)
    except FileNotFoundError as exc:
        return Result(code=int(ExitCode.USAGE), err=[str(exc)])
    except GuardError as exc:
        return Result(code=int(ExitCode.GUARD), err=[f"[restore-settings] ABORT {exc}"])
    return Result(out=[f"[restore-settings] restored backup {src}"])
