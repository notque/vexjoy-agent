"""repair-repo (spec 8): tracked files whose content matches an overlay file."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from . import gitutil
from .common import ExitCode, OverlayConfigError, file_sha256, iter_tree_files
from .context import Options, Result, load_context

MIN_BYTES = 32


def _overlay_index(ctx_overlays: list[tuple[str, Path]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for oid, root in ctx_overlays:
        if not root.is_dir():
            continue
        for rel in iter_tree_files(root):
            f = root / rel
            try:
                if f.stat().st_size >= MIN_BYTES:
                    out.setdefault(file_sha256(f), f"overlay:{oid}:{rel}")
            except OSError:
                continue
    return out


def _modified_vs_head(repo: Path, rel: str) -> bool:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "diff", "--quiet", "HEAD", "--", rel],
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 1


def run_repair(opts: Options) -> Result:
    """List matches; with --confirm, ``git checkout HEAD -- <file>`` for modified ones. Never commits."""
    try:
        ctx = load_context(opts)
    except OverlayConfigError as exc:
        return Result(code=int(exc.exit_code), err=[str(exc)])
    repo = ctx.source_root
    roots = [(o.id, o.root) for o in ctx.overlays.overlays if o.available]
    for e in ctx.ledger.entries.values():
        if e.owner.startswith("overlay:") and os.path.isdir(e.source):
            roots.append((e.owner.split(":", 1)[1], Path(e.source)))
    index = _overlay_index(roots)
    out: list[str] = []
    matches: list[dict] = []
    for rel in gitutil.tracked_files(repo):
        full = repo / rel
        try:
            if not full.is_file() or full.stat().st_size < MIN_BYTES:
                continue
            h = file_sha256(full)
        except OSError:
            continue
        if h not in index:
            continue
        modified = _modified_vs_head(repo, rel)
        matches.append({"path": rel, "overlay": index[h].split(":", 2)[1], "modified": modified})
        out.append(
            f"match: {rel} (overlay {index[h].split(':', 2)[1]}; {'modified vs HEAD' if modified else 'committed'})"
        )
        if modified:
            out.append(gitutil.diff_head(repo, rel, stat_only=not opts.show_diff).rstrip())
    unresolved = 0
    for m in matches:
        if not m["modified"]:
            out.append(f"  {m['path']}: content is committed; history decision is the owner's (spec 8)")
            unresolved += 1
            continue
        if opts.confirm and not opts.dry_run:
            ok = gitutil.checkout_head(repo, m["path"])
            out.append(f"  {m['path']}: {'restored to HEAD' if ok else 'checkout FAILED'}")
            if not ok:
                unresolved += 1
        else:
            out.append(f"  {m['path']}: pass --confirm to run git checkout HEAD -- {m['path']}")
            unresolved += 1
    out.insert(0, f"[repair-repo] {len(matches)} tracked file(s) match overlay content")
    return Result(code=int(ExitCode.ERROR) if unresolved else 0, out=out, data={"matches": matches})
