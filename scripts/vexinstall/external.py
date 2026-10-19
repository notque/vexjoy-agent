"""Runtime settings files the engine generates for non-claude targets.

| target   | file                     | source                                                  |
|----------|--------------------------|---------------------------------------------------------|
| codex    | ``hooks.json``           | ``scripts/codex-hooks-allowlist.txt`` via generate-codex-hooks-json.py |
| codex    | ``config.toml``          | ensure-codex-feature-flag.py (hooks + subagent routing) |
| factory  | ``settings.json`` hooks  | repo ``.claude/settings.json`` hooks, ``~/.claude/`` -> ``~/.factory/`` |
| reasonix | ``settings.json`` hooks  | ``scripts/reasonix-hooks-allowlist.txt`` via generate-reasonix-settings-hooks.py |

Builders come from the generator scripts as imported functions; the engine does
every write itself (guarded, atomic, mode 600), only when bytes change, and
backs up the old file to ``~/.claude/vexjoy/backups/<target>-<file>.<ts>``.
Profile-disabled hooks are dropped. Keys other than ``hooks`` are kept.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from .common import SETTINGS_BACKUPS_KEEP, utc_ts
from .fsops import Guard, atomic_write_bytes, mkdirs
from .profile import Profile, filter_settings_hooks

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_MODULES: dict[str, ModuleType | None] = {}


@dataclass
class ExternalFile:
    """One generated file: where, what, or why not."""

    target: str
    path: Path
    content: bytes | None = None
    error: str | None = None

    def changed(self) -> bool:
        """True when *content* differs from the file on disk."""
        if self.content is None:
            return False
        try:
            return self.path.read_bytes() != self.content
        except OSError:
            return True


def _load(filename: str) -> ModuleType | None:
    if filename in _MODULES:
        return _MODULES[filename]
    mod: ModuleType | None = None
    try:
        spec = importlib.util.spec_from_file_location(
            "_vexinstall_ext_" + filename[:-3].replace("-", "_"), _SCRIPTS_DIR / filename
        )
        if spec is not None and spec.loader is not None:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
    except Exception:
        mod = None
    _MODULES[filename] = mod
    return mod


def _dump(obj: object) -> bytes:
    return (json.dumps(obj, indent=2) + "\n").encode()


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _allowlist_entries(mod: ModuleType, allowlist: Path, profile: Profile) -> list[dict]:
    entries = mod.parse_allowlist(allowlist.read_text(encoding="utf-8"))
    return [e for e in entries if not profile.hook_disabled(e["filename"])]


def _codex(root: Path, source_root: Path, profile: Profile) -> list[ExternalFile]:
    out: list[ExternalFile] = []
    allow = source_root / "scripts" / "codex-hooks-allowlist.txt"
    hooks_json = ExternalFile("codex", root / "hooks.json")
    mod = _load("generate-codex-hooks-json.py")
    if not allow.is_file():
        hooks_json.error = "no codex-hooks-allowlist.txt"
    elif mod is None:
        hooks_json.error = "generate-codex-hooks-json.py not importable"
    else:
        try:
            data = mod.build_hooks_json(
                _allowlist_entries(mod, allow, profile),
                codex_hooks_dir=str(root / "hooks"),
                source_hooks_dir=source_root / "hooks",
            )
            hooks_json.content = _dump(data)
        except (ValueError, OSError) as exc:
            hooks_json.error = str(exc)
    out.append(hooks_json)
    cfg = ExternalFile("codex", root / "config.toml")
    flag = _load("ensure-codex-feature-flag.py")
    if flag is None:
        cfg.error = "ensure-codex-feature-flag.py not importable"
    else:
        try:
            exists = cfg.path.is_file()
            text = cfg.path.read_text(encoding="utf-8") if exists else ""
            with contextlib.redirect_stderr(io.StringIO()):
                needed, _ = flag._classify_content(text, exists)
            cfg.content = flag.apply_update(text).encode() if needed else text.encode()
        except SystemExit:
            cfg.error = "hooks disabled on purpose in config.toml; left as is"
        except (OSError, ValueError) as exc:
            cfg.error = str(exc)
    out.append(cfg)
    return out


def _factory(root: Path, source_root: Path, profile: Profile) -> list[ExternalFile]:
    f = ExternalFile("factory", root / "settings.json")
    repo = _read_json(source_root / ".claude" / "settings.json")
    if not repo:
        f.error = "repo .claude/settings.json missing or invalid"
        return [f]
    text = json.dumps(repo.get("hooks", {}))
    for form in ("$HOME", "${HOME}", "~"):
        text = text.replace(f"{form}/.claude/", f"{form}/.factory/")
    merged = _read_json(f.path)
    merged["hooks"] = filter_settings_hooks(json.loads(text), profile)
    merged.setdefault("attribution", repo.get("attribution", {"commit": "", "pr": ""}))
    f.content = _dump(merged)
    return [f]


def _reasonix(root: Path, source_root: Path, profile: Profile) -> list[ExternalFile]:
    f = ExternalFile("reasonix", root / "settings.json")
    allow = source_root / "scripts" / "reasonix-hooks-allowlist.txt"
    mod = _load("generate-reasonix-settings-hooks.py")
    if not allow.is_file():
        f.error = "no reasonix-hooks-allowlist.txt"
    elif mod is None:
        f.error = "generate-reasonix-settings-hooks.py not importable"
    else:
        try:
            hooks = mod.build_hooks(_allowlist_entries(mod, allow, profile), reasonix_hooks_dir=str(root / "hooks"))
            f.content = _dump(mod.merge_settings(_read_json(f.path), hooks))
        except (ValueError, OSError) as exc:
            f.error = str(exc)
    return [f]


_BUILDERS = {"codex": _codex, "factory": _factory, "reasonix": _reasonix}


def desired(target: str, root: Path, source_root: Path, profile: Profile) -> list[ExternalFile]:
    """Generated files for *target* (empty for claude and hermes)."""
    builder = _BUILDERS.get(target)
    return builder(root, source_root, profile) if builder else []


def _backup(f: ExternalFile, backups: Path, guard: Guard) -> None:
    if not f.path.is_file():
        return
    mkdirs(backups, guard)
    stem = f"{f.target}-{f.path.name}"
    atomic_write_bytes(backups / f"{stem}.{utc_ts()}", f.path.read_bytes(), guard, mode=0o600)
    olds = sorted(backups.glob(f"{stem}.*"))
    for old in olds[:-SETTINGS_BACKUPS_KEEP]:
        old.unlink()


def write(files: list[ExternalFile], backups: Path, guard: Guard) -> dict:
    """Write changed files; returns {"written": [...], "errors": [...]}."""
    written: list[str] = []
    errors: list[str] = []
    for f in files:
        if f.error:
            errors.append(f"{f.path}: {f.error}")
            continue
        if not f.changed() or f.content is None:
            continue
        _backup(f, backups, guard)
        atomic_write_bytes(f.path, f.content, guard, mode=0o600)
        written.append(str(f.path))
    return {"written": written, "errors": errors}
