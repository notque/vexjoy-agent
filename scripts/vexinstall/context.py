"""CLI options and context loading shared by every command."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from . import gitutil
from . import ledger as ledger_mod
from .fsops import Guard
from .ledger import Ledger
from .plan import Context, default_mode
from .profile import load_profile, profile_path
from .sources import default_overlays_path, load_overlays, load_public

SOURCE_ENV = "VEXINSTALL_SOURCE_ROOT"


@dataclass
class Options:
    """Parsed command-line options."""

    command: str
    target: str = "all"
    dry_run: bool = False
    json: bool = False
    home: Path = field(default_factory=Path.home)
    source_root: Path | None = None
    mode: str | None = None
    allow_mass_remove: bool = False
    adopt_source: bool = False
    index_only: bool = False
    confirm: bool = False
    unowned: bool = False
    overlays_file: Path | None = None
    show_diff: bool = False
    takeover: bool = False
    ts: str | None = None


@dataclass
class Result:
    """Command outcome: exit code, stdout lines, stderr lines, JSON payload."""

    code: int = 0
    out: list[str] = field(default_factory=list)
    err: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)


def state_dir(home: Path) -> Path:
    """Engine state dir (always under ~/.claude)."""
    return home / ".claude" / "vexjoy"


def looks_like_repo(path: Path) -> bool:
    """True for a toolkit-shaped checkout (skills/, agents/, hooks/)."""
    return all((path / d).is_dir() for d in ("skills", "agents", "hooks"))


def resolve_source_root(opts: Options, ledger: Ledger | None) -> Path:
    """--source-root > $VEXINSTALL_SOURCE_ROOT > this package's repo > ledger source_root."""
    if opts.source_root is not None:
        return opts.source_root.absolute()
    env = os.environ.get(SOURCE_ENV)
    if env:
        return Path(env).absolute()
    pkg_repo = Path(__file__).resolve().parents[2]
    if looks_like_repo(pkg_repo):
        return pkg_repo
    if ledger is not None and ledger.source_root and looks_like_repo(Path(ledger.source_root)):
        return Path(ledger.source_root)
    return pkg_repo


def load_context(opts: Options) -> Context:
    """Read ledger (read-only), overlays, and public sources. Never writes."""
    gitutil.clear_cache()
    home = opts.home
    sdir = state_dir(home)
    led, led_state = ledger_mod.load(ledger_mod.ledger_path(sdir))
    source_root = resolve_source_root(opts, led)
    overlays = load_overlays(opts.overlays_file or default_overlays_path(home), source_root, home)
    public = load_public(source_root)
    ledger = led or Ledger()
    mode = opts.mode or ledger.mode or default_mode(source_root)
    return Context(
        home=home,
        source_root=Path(os.path.realpath(source_root)),
        state_dir=sdir,
        mode=mode,
        public=public,
        overlays=overlays,
        ledger=ledger,
        ledger_state=led_state,
        profile=load_profile(profile_path(source_root)),
    )


def guard_for(ctx: Context) -> Guard:
    """Guard protecting the repo, the ledger's old repo, and every overlay root."""
    roots = [ctx.source_root]
    if ctx.ledger.source_root and os.path.isdir(ctx.ledger.source_root):
        roots.append(Path(ctx.ledger.source_root))
    roots.extend(o.root for o in ctx.overlays.overlays)
    return Guard.for_roots(roots)
