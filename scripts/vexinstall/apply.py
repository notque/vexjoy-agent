"""apply / sync / uninstall / prune / restore commands (all writes happen here)."""

from __future__ import annotations

import contextlib
import os
import time
from collections.abc import Callable
from pathlib import Path

from . import accounts as accounts_mod
from . import external, interp
from . import index as index_mod
from . import ledger as ledger_mod
from . import rollback as rollback_mod
from . import settings as settings_mod
from .adapters import ADAPTERS, resolve_targets
from .common import (
    APPLY_LOCK_TIMEOUT_S,
    DATA_DIRS,
    SETTINGS_BACKUPS_KEEP,
    SUPPORT_DIRS,
    TARGET_NAMES,
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
from .fsops import (
    CarryLog,
    Guard,
    Trash,
    atomic_symlink,
    carry_node_modules,
    copy_entry,
    discard_staged,
    is_busy,
    mkdirs,
    place_staged,
    prune_trash,
    restore_trash,
    stage_copy,
    stage_link,
)
from .ledger import STATUS_OK, STATUS_STALE, Ledger, LedgerEntry
from .lock import LockHeld, engine_lock
from .plan import (
    Action,
    Context,
    Plan,
    TargetPlan,
    build_plan,
    dir_of_adoptable_links,
    link_points_into,
    source_refusal,
)
from .profile import filter_settings_hooks
from .report import plan_diff, summary_line, write_report
from .sources import skill_md_of


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
    if "claude" in targets:
        res.out.append(_python_plan_line(ctx.home))
        acct = accounts_mod.plan_all(ctx)
        res.out.extend(a.summary() for a in acct)
        res.data["accounts"] = [a.to_json() for a in acct]
    if plan.collisions or ctx.public.duplicate_skill_names():
        res.code = int(ExitCode.COLLISION)
        res.err.extend(f"collision: {c.describe()}" for c in plan.collisions)
    return res


def _python_plan_line(home: Path) -> str:
    link = interp.link_path(home)
    try:
        found = interp.resolve()
    except interp.InterpreterError as exc:
        return f"python: apply would fail: {exc}"
    return f"python: {link} -> {found.label}"


def _resolve_python(home: Path, sync: bool) -> tuple[interp.Interpreter | None, str | None]:
    """(interpreter to link, error), decided before any write.

    Sync re-resolves only a link that is missing, dangling, broken, or older than 3.10.
    """
    blocker = interp.link_blocker(home)
    if blocker:
        return None, blocker
    if sync and interp.link_ok(home):
        return None, None
    try:
        return interp.resolve(), None
    except interp.InterpreterError as exc:
        return None, str(exc)


def _install(a: Action, guard: Guard) -> None:
    dest = Path(a.dest)
    mkdirs(dest.parent, guard)
    src = Path(str(a.source))
    if a.mode == "symlink":
        atomic_symlink(dest, src, guard)
    else:
        copy_entry(src, dest, guard, a.files)


def _replace(a: Action, trash: Trash, home: Path, guard: Guard, carry: CarryLog) -> None:
    """Move the entry at ``a.dest`` to trash and install *a* there.

    The new copy or link is staged before the old entry moves. A live dir such as
    ~/.claude/hooks is then missing only between two renames, and stays in place when
    Windows keeps it busy or refuses the link. When the staged entry cannot be placed, the
    old entry comes back out of trash. Once a new copy is in place, the node_modules dirs
    of the old copy move into it (``carry_node_modules``): the engine never copies them,
    and the Jev gateway needs the ones ``./install.sh`` installed.
    """
    dest = Path(a.dest)
    reason = a.reason if a.takeover else f"replaced ({a.reason})"
    src = Path(str(a.source))
    mkdirs(dest.parent, guard)
    staged = stage_link(src, dest, guard) if a.mode == "symlink" else stage_copy(src, dest, guard, a.files)
    trashed: Path | None = None
    try:
        if os.path.lexists(dest):
            trashed = trash.move(dest, home, reason)
        place_staged(staged, dest)
    except BaseException:
        try:
            if trashed is not None and not os.path.lexists(dest):
                trash.put_back(trashed, dest)
        finally:
            discard_staged(staged)
        raise
    if trashed is not None and a.mode == "copy":
        carry_node_modules(trashed, dest, guard, carry)


_NOT_DONE = {"remove": "not removed", "add": "not installed"}
_FAILED_SHOWN = 5


def _failure(a: Action, exc: OSError) -> str:
    """One line for an entry left as it was. A busy Windows path names the usual cause."""
    line = f"{a.dest} {_NOT_DONE.get(a.op, 'not updated')}: {exc}"
    if is_busy(exc):
        line += " (Windows refused: close any terminal, editor, or program working in it, then run again)"
    return line


def _forget_inside(ledger: Ledger, dest: str) -> None:
    """Drop records strictly inside *dest*, which this run just installed whole.

    Their files went to trash with the old entry. A record left behind would make a later
    run trash that path out of the new copy, which then reads as a user edit for good.
    """
    inside = dest + os.sep
    for d in [d for d in ledger.entries if d.startswith(inside)]:
        del ledger.entries[d]


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


def execute_target(
    tp: TargetPlan,
    ctx: Context,
    trash: Trash,
    guard: Guard,
    ledger: Ledger,
    skip: set[str],
    failed: list[str],
    carry: CarryLog,
) -> None:
    """Carry out one target's plan. Ops are atomic per file; ledger updated in memory.

    An entry whose op fails with an OSError (a dir Windows keeps busy, a full disk) stays as
    it was and keeps its ledger record. Its line goes to *failed*, and the other entries run.
    Replaced copies log the node_modules dirs they carried over to *carry*.

    A removal inside a dir this run installs whole is not moved first: placing that dir moves
    the old one to trash with the entry inside, and ``_forget_inside`` drops the record. Moving
    the entries first emptied a live dir such as ~/.claude/hooks, and a failed install left it so.
    """
    now = utc_iso()
    home = ctx.home
    whole = {a.dest for a in tp.actions if a.op in ("replace", "add") and a.dest not in skip}
    for a in tp.actions:
        if a.op == "container":
            trash.move(Path(a.dest), home, "whole-dir symlink replaced by real dir")
            mkdirs(Path(a.dest), guard)
    for a in tp.actions:
        if a.dest in skip:
            continue
        if a.op == "remove":
            if any(str(p) in whole for p in Path(a.dest).parents):
                continue
            try:
                trash.move(Path(a.dest), home, a.reason or "removed")
            except OSError as exc:
                failed.append(_failure(a, exc))
                continue
            ledger.entries.pop(a.dest, None)
        elif a.op == "forget":
            ledger.entries.pop(a.dest, None)
        elif a.op == "stale" and a.dest in ledger.entries:
            ledger.entries[a.dest].status = STATUS_STALE
    for a in tp.actions:
        if a.dest in skip or a.op not in ("replace", "add", "keep", "adopt"):
            continue
        dest = Path(a.dest)
        try:
            if a.op == "replace" and a.mode == "symlink" and os.path.islink(dest) and not a.takeover:
                atomic_symlink(dest, Path(str(a.source)), guard)
            elif a.op == "replace":
                _replace(a, trash, home, guard, carry)
            elif a.op == "add":
                _install(a, guard)
        except OSError as exc:
            failed.append(_failure(a, exc))
            continue
        _record(ledger, a, now)
        if a.op in ("replace", "add"):
            _forget_inside(ledger, a.dest)


def _save_ledger(path: Path, ledger: Ledger, ctx: Context, guard: Guard) -> None:
    """Save the ledger of this run. It holds only finished steps, so a partial run saves it too.

    Without that save, an entry replaced before the failure keeps its old hash, reads as a
    user edit after the next source change, and stops updating.
    """
    ledger.source_root = str(ctx.source_root)
    ledger.mode = ctx.mode
    ledger.overlays_mtime = ctx.overlays.mtime
    ledger_mod.save(path, ledger, guard)


def apply_settings(ctx: Context, ledger: Ledger, guard: Guard, *, desired: dict | None) -> dict:
    """Merge owned hook entries and the repo's env vars and attribution into ~/.claude/settings.json.

    Env vars and attribution are added only on install (``desired`` is None) and never removed on
    uninstall. A user value is never overwritten, except an env var still holding an old shipped
    default listed in ``SUPERSEDED_ENV``, once per install (recorded in the ledger as
    ``env_migrated``). Returns a report dict.
    """
    home = ctx.home
    spath = home / ".claude" / "settings.json"
    install = desired is None
    if install:
        repo_settings = ctx.source_root / ".claude" / "settings.json"
        if not repo_settings.is_file():
            return {"skipped": "repo .claude/settings.json missing"}
        desired = filter_settings_hooks(settings_mod.desired_from_repo(ctx.source_root), ctx.profile)
    try:
        current = settings_mod.read_settings(spath)
    except ValueError as exc:
        return {"skipped": f"settings.json unreadable: {exc}"}
    rule = settings_mod.OwnerRule(home=home, hooks_dir=home / ".claude" / "hooks", source_root=ctx.source_root)
    res = settings_mod.merge(current, desired, rule)
    migrated = set(ledger.settings.get("env_migrated", []))
    keys = settings_mod.merge_repo_keys(res.settings, ctx.source_root, migrated) if install else None
    backup_ts = None
    if res.changed or (keys is not None and keys.changed):
        backup_ts = settings_mod.backup(spath, state_dir(home) / "backups", guard)
        settings_mod.write(spath, res.settings, guard)
    if keys is not None and keys.env_marked:  # only after a successful write, so a failed write retries
        ledger.settings["env_migrated"] = sorted(migrated | set(keys.env_marked))
    ledger.settings["claude"] = res.owned_hashes
    return {
        "added": res.added,
        "removed": res.removed,
        "deduped": res.deduped,
        "env_added": keys.env_added if keys else [],
        "env_updated": keys.env_updated if keys else [],
        "env_removed": keys.env_removed if keys else [],
        "attribution_added": keys.attribution_added if keys else False,
        "unmanaged_in_repo": res.unmanaged,
        "backup": backup_ts,
    }


def _write_indexes(ctx: Context, ledger: Ledger, targets: list[str], guard: Guard) -> list[str]:
    written: list[str] = []
    for t in targets:
        written.extend(index_mod.write(ctx.home, t, ledger, guard))
    return written


def _keep_failed_run(sdir: Path, guard: Guard, ledger: Ledger | None, record_point: Callable[[], None]) -> None:
    """Save *ledger* and record the rollback point of a run that an error is ending; never raises.

    The run has already moved entries to trash or rewritten settings.json, so ``--rollback`` must
    undo this run and not the one before it, and the ledger must list what the run installed, so
    the restore can move those entries aside. The caller re-raises the run's own error.
    """
    if ledger is not None:
        with contextlib.suppress(Exception):
            ledger_mod.save(ledger_mod.ledger_path(sdir), ledger, guard)
    with contextlib.suppress(Exception):
        record_point()


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
    if sync:
        gone = [t for t in targets if t in ledger.uninstalled]
        if gone:
            targets = [t for t in targets if t not in gone]
            res.err.append(
                f"[sync] warning: skipped uninstalled target(s) {', '.join(gone)}; "
                f"run apply --target <name> (or ./install.sh) to install again"
            )
        if not targets:
            return res
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

    python: interp.Interpreter | None = None
    if "claude" in targets:
        python, python_err = _resolve_python(ctx.home, sync)
        if python_err and not sync:
            return Result(code=int(ExitCode.ERROR), err=[f"[apply] {python_err}"])
        if python_err:
            res.err.append(f"[sync] warning: {python_err}")

    if not sync:
        # An install undoes an uninstall: sync may update these targets again.
        cleared = list(ledger.uninstalled) if opts.target == "all" else [t for t in targets if t in ledger.uninstalled]
        for t in cleared:
            del ledger.uninstalled[t]

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
    pin_error: str | None = None
    failed: list[str] = []
    held_back: list[str] = []
    carry = CarryLog()

    def record_point() -> None:
        rollback_mod.record(
            sdir,
            guard,
            run=opts.run_id or ts,
            command=label,
            trash=ts if trash.items else None,
            settings_backup=(report.get("settings") or {}).get("backup"),
        )

    try:
        try:
            for t in targets:
                before = len(failed)
                execute_target(plan.targets[t], ctx, trash, guard, ledger, skip, failed, carry)
                if len(failed) > before:
                    held_back.append(t)
            if python is not None:
                link = interp.link_path(ctx.home)
                # A pin that cannot be written must not strand the copies above without settings or a ledger.
                try:
                    changed = interp.write_link(ctx.home, python, guard)
                    kind = interp.read_pin(link).kind
                except OSError as exc:
                    pin_error = f"python pin {link} not written: {exc}; hooks fall back to python3 on PATH"
                    report["python"] = {"link": str(link), "target": python.label, "error": str(exc)}
                else:
                    report["python"] = {"link": str(link), "target": python.label, "changed": changed, "kind": kind}
            # A target with a failed entry keeps its settings and hook configs as they are: a new
            # registration could name a hook whose file did not install, and a PreToolUse hook that
            # exits 2 (python on a missing script) blocks the tool call.
            if "claude" in targets and "claude" not in held_back:
                report["settings"] = apply_settings(ctx, ledger, guard, desired=None)
                report["accounts"] = accounts_mod.apply_all(ctx, guard)
            ext: list[external.ExternalFile] = []
            for t in targets:
                if t not in held_back:
                    ext.extend(external.desired(t, ADAPTERS[t].root_path(ctx.home), ctx.source_root, ctx.profile))
            report["external"] = external.write(ext, sdir / "backups", guard)
            res.err.extend(f"[{label}] warning: external {e}" for e in report["external"]["errors"])
        except GuardError as exc:
            guard_hit = exc
        except OSError as exc:
            failed.append(f"run stopped early: {exc}")
        try:
            _save_ledger(lpath, ledger, ctx, guard)
        except GuardError as exc:
            guard_hit = guard_hit or exc
        if guard_hit is None:
            try:
                report["index"] = _write_indexes(ctx, ledger, targets, guard)
            except GuardError as exc:
                guard_hit = exc
    except BaseException:
        # Ctrl-C or a bug: keep what finished, then stop. An apply that dies partway is still
        # the run --rollback undoes; a sync never records a point.
        with contextlib.suppress(Exception):
            _save_ledger(lpath, ledger, ctx, guard)
        if not sync:
            _keep_failed_run(sdir, guard, None, record_point)
        raise
    if not sync:  # a session-start sync must never become what --rollback restores
        try:
            record_point()
        except GuardError as exc:
            guard_hit = guard_hit or exc
    report["timings_ms"] = int((time.monotonic() - t0) * 1000)
    report["trash"] = str(trash.dir) if trash.items else None
    report["failed"] = failed
    report["held_back"] = held_back
    report["node_modules"] = {"carried": carry.carried, "warnings": carry.warnings}
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
    py = report.get("python", {})
    if py.get("changed") and not sync:
        how = " (script pin: this host refuses symlinks)" if py.get("kind") == "script" else ""
        res.out.append(f"[{label}] python: {py['link']} -> {py['target']}{how}")
    if pin_error and sync:
        res.err.append(f"[{label}] warning: {pin_error}")
    elif pin_error:
        res.code = int(ExitCode.ERROR)
        res.err.append(f"[{label}] {pin_error}")
    if failed:
        tag = f"[{label}] warning:" if sync else f"[{label}]"
        res.err.extend(f"{tag} {line}" for line in failed[:_FAILED_SHOWN])
        if len(failed) > _FAILED_SHOWN:
            res.err.append(
                f"{tag} {len(failed) - _FAILED_SHOWN} more not done; the report in {sdir / 'reports'} lists all"
            )
        res.err.extend(
            f"{tag} {t}: settings and hook registrations not updated until every {t} entry installs" for t in held_back
        )
        if os.name == "nt" and ctx.mode == "symlink":
            res.err.append(f"{tag} Windows installs need copy mode: run ./install.sh --copy")
        if not sync:
            res.code = int(ExitCode.ERROR)
    res.err.extend(f"[{label}] warning: {line}" for line in carry.warnings)
    res.out.extend(accounts_mod.report_lines(report.get("accounts", [])))
    for a in report.get("accounts", []):
        if a.get("error"):
            res.err.append(f"[{label}] warning: account {a['name']}: {a['error']}")
    if not sync:
        res.out.extend(_plan_lines(plan)[1:])
    return res


def run_uninstall(opts: Options) -> Result:
    """Move every ledger entry of the chosen targets to trash; remove owned hook registrations.

    Owned entries leave ~/.claude/settings.json, account profiles, and the runtime configs
    apply writes through ``external``. The targets are recorded in the ledger so ``sync``
    leaves them alone until an ``apply`` for that target.
    """
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
        out = [f"would remove {e.dest}" for e in owned] + [f"{len(owned)} entries"]
        for t in targets:
            for f in external.removal(t, ADAPTERS[t].root_path(ctx.home), ctx.home, ctx.source_root):
                if f.error:
                    out.append(f"external {f.path}: {f.error}")
                elif f.content is not None:
                    out.append(f"would remove owned hook entries from {f.path}")
        return Result(out=out)
    guard = guard_for(ctx)
    sdir = state_dir(ctx.home)
    try:
        with engine_lock(sdir / "lock", guard, blocking=True, timeout=APPLY_LOCK_TIMEOUT_S):
            ts = utc_ts()
            trash = Trash(root=sdir / "trash", ts=ts, guard=guard)
            removed, skipped = [], []
            settings_report = None

            def record_point() -> None:
                rollback_mod.record(
                    sdir,
                    guard,
                    run=opts.run_id or ts,
                    command="uninstall",
                    trash=ts if trash.items else None,
                    settings_backup=(settings_report or {}).get("backup"),
                )

            try:
                # sync skips recorded targets until an apply installs them again. An "all" uninstall
                # records every target, so a runtime dir created later is not picked up either.
                # Recorded first, so an uninstall that dies partway still keeps sync from undoing it.
                stamp = utc_iso()
                for t in TARGET_NAMES if opts.target == "all" else targets:
                    ctx.ledger.uninstalled[t] = stamp
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
                accounts_report: list[dict] = []
                if "claude" in targets:
                    settings_report = apply_settings(ctx, ctx.ledger, guard, desired={})
                    accounts_report = accounts_mod.apply_all(ctx, guard, desired={}, links=False)
                    ctx.ledger.settings.pop("claude", None)
                    link = interp.link_path(ctx.home)
                    if interp.read_pin(link).kind in ("link", "script"):
                        trash.move(link, ctx.home, "uninstall")
                        removed.append(str(link))
                ext: list[external.ExternalFile] = []
                for t in targets:
                    ext.extend(external.removal(t, ADAPTERS[t].root_path(ctx.home), ctx.home, ctx.source_root))
                external_report = external.write(ext, sdir / "backups", guard)
                ledger_mod.save(ledger_mod.ledger_path(sdir), ctx.ledger, guard)
                report = {
                    "ts": ts,
                    "command": "uninstall",
                    "removed": removed,
                    "skipped_user_edited": skipped,
                    "settings": settings_report,
                    "accounts": accounts_report,
                    "external": external_report,
                    "uninstalled": sorted(ctx.ledger.uninstalled),
                    "trash": str(trash.dir) if trash.items else None,
                }
                write_report(sdir / "reports", ts, report, guard)
            except BaseException:  # an uninstall that dies partway is still the run --rollback undoes
                _keep_failed_run(sdir, guard, ctx.ledger, record_point)
                raise
            record_point()
    except GuardError as exc:
        return Result(code=int(ExitCode.GUARD), err=[f"[uninstall] ABORT {exc}"])
    except LockTimeoutError as exc:
        return Result(code=int(exc.exit_code), err=[str(exc)])
    out = [f"[uninstall] removed {len(removed)}, skipped {len(skipped)} user-edited; trash {ts}"]
    out.extend(f"  skipped (user-edited): {s}" for s in skipped)
    out.extend(f"  hook registrations removed: {p}" for p in external_report["written"])
    out.append(f"  sync skips {', '.join(sorted(ctx.ledger.uninstalled))} until an apply for that target")
    err = [f"[uninstall] warning: external {e}" for e in external_report["errors"]]
    return Result(out=out, err=err, data=report)


def unowned_prunable(ctx: Context, targets: list[str]) -> list[tuple[str, str]]:
    """(path, reason) for unowned dangling links, category entries, shadowed commands, and legacy toolkit entries."""
    out: list[tuple[str, str]] = []
    owned = set(ctx.ledger.entries)
    roots = ctx.known_roots()
    for t in targets:
        adapter = ctx.adapter(t)
        containers = adapter.containers(ctx.home)
        for container in containers:
            if os.path.islink(container) or not os.path.isdir(container):
                continue
            root = adapter.root_path(ctx.home)
            is_skills = adapter.skills is not None and container == root / adapter.skills
            skills_root = root / adapter.skills if adapter.skills else None
            is_commands = adapter.commands is not None and container == root / adapter.commands
            for child in sorted(os.listdir(container)):
                path = container / child
                if str(path) in owned or child.startswith("."):
                    continue
                if any(is_inside(str(o), str(path)) for o in containers):
                    continue
                if is_dangling(path):
                    out.append((str(path), "dangling link"))
                elif is_skills and is_category_entry(path):
                    out.append((str(path), "category entry in flat skills root"))
                elif (
                    is_commands
                    and skills_root is not None
                    and child.endswith(".md")
                    and skill_md_of(skills_root / child[:-3]) is not None
                ):
                    out.append((str(path), "command shadows a skill of the same name"))
                elif (os.path.islink(path) and link_points_into(path, roots)) or dir_of_adoptable_links(path, roots):
                    out.append((str(path), "legacy toolkit entry"))
    return out


def is_category_entry(path: Path) -> bool:
    """A skills-root entry without SKILL.md that holds nested skills (not a support dir)."""
    if path.name in SUPPORT_DIRS or path.name in DATA_DIRS or not path.is_dir():
        return False
    if skill_md_of(path) is not None:
        return False
    try:
        return any(skill_md_of(child) is not None for child in path.iterdir() if child.is_dir())
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
    if not items:
        return Result(out=["[prune] 0 unowned candidate(s); nothing to trash"])
    guard = guard_for(ctx)
    sdir = state_dir(ctx.home)
    try:
        with engine_lock(sdir / "lock", guard, blocking=True, timeout=APPLY_LOCK_TIMEOUT_S):
            ts = utc_ts()
            trash = Trash(root=sdir / "trash", ts=ts, guard=guard)

            def record_point() -> None:
                rollback_mod.record(
                    sdir,
                    guard,
                    run=opts.run_id or ts,
                    command="prune",
                    trash=ts if trash.items else None,
                    settings_backup=None,
                )

            try:
                for p, why in items:
                    trash.move(Path(p), ctx.home, f"prune --unowned: {why}")
                write_report(sdir / "reports", ts, {"ts": ts, "command": "prune", "trashed": trash.items}, guard)
            except BaseException:  # a prune that dies partway is still the run --rollback undoes
                _keep_failed_run(sdir, guard, None, record_point)
                raise
            record_point()
    except GuardError as exc:
        return Result(code=int(ExitCode.GUARD), err=[f"[prune] ABORT {exc}"])
    return Result(out=[f"[prune] moved {len(items)} to trash {ts}", *lines])


def _restore_session(
    ctx: Context, sdir: Path, ledger: Ledger, ts: str, displaced: Trash, reason: str, carry: CarryLog
) -> tuple[list[str], list[str]]:
    """Put trash session *ts* back. An engine-owned occupant moves to *displaced* and leaves *ledger*.

    The occupant's node_modules dirs then move into the entry restored in its place: the
    replace that trashed that entry moved its node_modules into the occupant.
    """
    moved: dict[str, Path] = {}

    def clear(path: Path) -> bool:
        p = str(path)
        owned_here = p in ledger.entries
        if not owned_here and os.path.isdir(path) and not os.path.islink(path):
            children = os.listdir(path)
            owned_here = bool(children) and all(os.path.join(p, c) in ledger.entries for c in children)
        if not owned_here:
            return False
        moved[p] = displaced.move(path, ctx.home, reason)
        for d in [d for d in ledger.entries if d == p or d.startswith(p + os.sep)]:
            ledger.entries.pop(d)
        return True

    restored, skipped = restore_trash(sdir / "trash", ts, displaced.guard, clear)
    for orig in restored:
        if orig in moved:
            carry_node_modules(moved[orig], Path(orig), displaced.guard, carry)
    return restored, skipped


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
            reason = f"displaced by restore-trash {opts.ts}"
            carry = CarryLog()
            restored, skipped = _restore_session(ctx, sdir, ledger, opts.ts, displaced, reason, carry)
            ledger_mod.save(ledger_mod.ledger_path(sdir), ledger, guard)
    except FileNotFoundError:
        return Result(code=int(ExitCode.USAGE), err=[f"no trash session {opts.ts}"])
    except GuardError as exc:
        return Result(code=int(ExitCode.GUARD), err=[f"[restore-trash] ABORT {exc}"])
    out = [f"[restore-trash] restored {len(restored)}, skipped {len(skipped)} (dest occupied or missing)"]
    if displaced.items:
        out.append(f"  displaced {len(displaced.items)} engine entries to trash {displaced.ts}")
    out.extend(f"  skipped: {s}" for s in skipped)
    data = {
        "restored": restored,
        "skipped": skipped,
        "displaced_ts": displaced.ts,
        "node_modules": {"carried": carry.carried, "warnings": carry.warnings},
    }
    return Result(out=out, err=[f"[restore-trash] warning: {w}" for w in carry.warnings], data=data)


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


def _rollback_point(sdir: Path) -> tuple[rollback_mod.Point | None, str]:
    """The point to restore, or (None, why there is none)."""
    point = rollback_mod.load(sdir)
    if point is None:
        path = rollback_mod.point_path(sdir)
        if os.path.lexists(path):
            return None, f"[rollback] {path} is unreadable; nothing to roll back (restore-trash <ts> still works)"
        return None, "[rollback] nothing to roll back: no apply, uninstall or prune --confirm has recorded a run"
    if point.restored_at:
        return None, f"[rollback] run {point.run} was already rolled back at {point.restored_at}"
    return point, ""


def _point_lines(point: rollback_mod.Point) -> list[str]:
    lines = [f"  trash session {ts}" for ts in reversed(point.trash)]
    if point.settings_backup:
        lines.append(f"  settings.json backup {point.settings_backup}")
    else:
        lines.append("  settings.json: no backup from that run (unchanged, or there was none); left as is")
    return lines


def run_rollback(opts: Options) -> Result:
    """Restore the last recorded run: its trash sessions, newest first, then its settings.json backup.

    apply, uninstall and ``prune --confirm`` record the point (``rollback.json``); sync never does,
    so a later sync's trash or backup never stands in for the run's. A point is restored once.
    Engine-owned entries a restore displaces go to a new trash session.
    """
    try:
        ctx = load_context(opts)
    except OverlayConfigError as exc:
        return Result(code=int(exc.exit_code), err=[str(exc)])
    sdir = state_dir(ctx.home)
    guard_msg = repo_root_refusal(ctx, [])
    if guard_msg:
        return Result(code=int(ExitCode.GUARD), err=[f"[rollback] ABORT {guard_msg}"])
    if opts.dry_run:
        point, why = _rollback_point(sdir)
        if point is None:
            return Result(out=[why])
        head = f"[rollback] would restore run {point.run} ({' + '.join(point.commands)}):"
        return Result(out=[head, *_point_lines(point)])
    guard = guard_for(ctx)
    out: list[str] = []
    err: list[str] = []
    carry = CarryLog()
    data: dict = {
        "restored": [],
        "skipped": [],
        "missing": [],
        "failed": [],
        "node_modules": {"carried": carry.carried, "warnings": carry.warnings},
    }
    try:
        with engine_lock(sdir / "lock", guard, blocking=True, timeout=APPLY_LOCK_TIMEOUT_S):
            point, why = _rollback_point(sdir)
            if point is None:
                return Result(out=[why])
            out.append(f"[rollback] run {point.run} ({' + '.join(point.commands)})")
            data["run"] = point.run
            led, _ = ledger_mod.load(ledger_mod.ledger_path(sdir))
            ledger = led or Ledger()
            displaced = Trash(root=sdir / "trash", ts=utc_ts(), guard=guard)
            reason = f"displaced by rollback of run {point.run}"
            try:
                for ts in reversed(point.trash):
                    if not (sdir / "trash" / ts / "manifest.json").is_file():
                        data["missing"].append(ts)
                        err.append(f"[rollback] trash session {ts} is gone (trash is kept {TRASH_RETENTION_DAYS} days)")
                        continue
                    try:
                        restored, skipped = _restore_session(ctx, sdir, ledger, ts, displaced, reason, carry)
                    except (OSError, ValueError, LookupError, TypeError, AttributeError) as exc:
                        data["failed"].append(ts)
                        err.append(
                            f"[rollback] trash session {ts} not fully restored ({type(exc).__name__}: {exc});"
                            f" finish with restore-trash {ts}"
                        )
                        continue
                    data["restored"].extend(restored)
                    data["skipped"].extend(skipped)
                    out.append(f"  trash {ts}: restored {len(restored)}, skipped {len(skipped)} (occupied or missing)")
                    out.extend(f"    skipped: {s}" for s in skipped)
            finally:  # entries already displaced must leave the ledger even when a session fails
                ledger_mod.save(ledger_mod.ledger_path(sdir), ledger, guard)
            if point.settings_backup:
                spath = ctx.home / ".claude" / "settings.json"
                try:
                    settings_mod.restore(spath, sdir / "backups", point.settings_backup, guard)
                    out.append(f"  settings.json: restored backup {point.settings_backup}")
                except FileNotFoundError:
                    data["missing"].append(f"settings.{point.settings_backup}.json")
                    err.append(
                        f"[rollback] settings backup {point.settings_backup} is gone"
                        f" (the newest {SETTINGS_BACKUPS_KEEP} are kept); settings.json left as is"
                    )
            else:
                out.append(_point_lines(point)[-1])
            if displaced.items:
                out.append(f"  displaced {len(displaced.items)} engine entries to trash {displaced.ts}")
                data["displaced_ts"] = displaced.ts
            point.restored_at = utc_iso()
            rollback_mod.save(sdir, point, guard)
    except GuardError as exc:
        return Result(code=int(ExitCode.GUARD), err=[f"[rollback] ABORT {exc}"])
    except LockTimeoutError as exc:
        return Result(code=int(exc.exit_code), err=[str(exc)])
    code = int(ExitCode.ERROR) if err else 0  # a node_modules left in trash only warns
    err.extend(f"[rollback] warning: {w}" for w in carry.warnings)
    return Result(code=code, out=out, err=err, data=data)
