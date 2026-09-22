"""settings.json hook merge: owned entries only, never replace the hooks key (spec 10)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from .common import SETTINGS_BACKUPS_KEEP, is_inside, realpath, utc_ts
from .fsops import Guard, atomic_write_bytes, mkdirs
from .legacy import is_legacy_hook_path

_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def expand_vars(text: str, home: Path, extra: dict[str, str] | None = None) -> str:
    """Expand ``~``, ``$HOME``, ``${HOME}``, and ``${VAR}``-style variables.

    Unknown variables expand from the environment, else stay literal.
    """
    env = {"HOME": str(home), **(extra or {})}

    def sub(m: re.Match[str]) -> str:
        name = m.group(1) or m.group(2)
        if name in env:
            return env[name]
        return os.environ.get(name, m.group(0))

    out = _VAR_RE.sub(sub, text)
    if out.startswith("~/") or out == "~":
        out = str(home) + out[1:]
    return out.replace(" ~/", f" {home}/").replace('"~/', f'"{home}/').replace("'~/", f"'{home}/")


def first_path_token(command: str, home: Path) -> str | None:
    """First shell token of *command* that is a path (contains '/')."""
    expanded = expand_vars(command, home)
    try:
        tokens = shlex.split(expanded)
    except ValueError:
        tokens = expanded.split()
    for tok in tokens:
        if "/" in tok:
            return tok
    return None


@dataclass
class OwnerRule:
    """Decides whether a hook entry is engine-owned."""

    home: Path
    hooks_dir: Path
    source_root: Path

    def owns(self, entry: object) -> bool:
        """Spec 10: first path token realpath inside the installed hooks dir, or legacy."""
        if not isinstance(entry, dict):
            return False
        cmd = entry.get("command")
        if not isinstance(cmd, str):
            return False
        tok = first_path_token(cmd, self.home)
        if tok is None:
            return False
        hooks_real = realpath(self.hooks_dir)
        if is_inside(realpath(tok), hooks_real) or is_inside(os.path.normpath(tok), str(self.hooks_dir)):
            return True
        if is_inside(os.path.normpath(tok), str(self.source_root / "hooks")):
            return True
        return is_legacy_hook_path(os.path.normpath(tok))


def canonical_hash(meta: dict, entry: dict) -> str:
    """Hash of (group meta, entry) in canonical JSON."""
    blob = json.dumps({"group": meta, "entry": entry}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def _meta(group: dict) -> dict:
    return {k: v for k, v in group.items() if k != "hooks"}


@dataclass
class MergeResult:
    """Outcome of a settings merge."""

    settings: dict
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    deduped: list[str] = field(default_factory=list)
    unmanaged: list[str] = field(default_factory=list)
    owned_hashes: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        """True when the merge changed anything."""
        return bool(self.added or self.removed or self.deduped)


def desired_from_repo(source_root: Path) -> dict:
    """The ``hooks`` key of repo ``.claude/settings.json`` (source of desired entries)."""
    path = source_root / ".claude" / "settings.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    hooks = data.get("hooks", {})
    return hooks if isinstance(hooks, dict) else {}


def owned_entries(settings: dict, rule: OwnerRule) -> list[tuple[str, dict, dict]]:
    """(event, group meta, entry) for every owned entry in *settings*."""
    out = []
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return out
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                continue
            for entry in group["hooks"]:
                if rule.owns(entry):
                    out.append((event, _meta(group), entry))
    return out


def merge(current: dict, desired_hooks: dict, rule: OwnerRule) -> MergeResult:
    """Pure merge. Owned entries not desired are removed, missing ones added, dupes collapsed.

    Entries the rule does not own are never touched. The ``hooks`` key is edited in
    place, never replaced.
    """
    result = json.loads(json.dumps(current)) if current else {}
    res = MergeResult(settings=result)
    want: dict[str, list[tuple[dict, dict, str]]] = {}
    for event, groups in (desired_hooks or {}).items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                continue
            for entry in group["hooks"]:
                if not rule.owns(entry):
                    res.unmanaged.append(f"{event}: {entry.get('command') if isinstance(entry, dict) else entry}")
                    continue
                h = canonical_hash(_meta(group), entry)
                bucket = want.setdefault(event, [])
                if all(h != x[2] for x in bucket):
                    bucket.append((_meta(group), entry, h))
    hooks = result.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        result["hooks"] = hooks
    for event in list(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            continue
        wanted = {x[2] for x in want.get(event, [])}
        seen: set[str] = set()
        new_groups = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                new_groups.append(group)
                continue
            kept = []
            for entry in group["hooks"]:
                if rule.owns(entry):
                    h = canonical_hash(_meta(group), entry)
                    label = f"{event}: {entry.get('command')}"
                    if h not in wanted:
                        res.removed.append(label)
                        continue
                    if h in seen:
                        res.deduped.append(label)
                        continue
                    seen.add(h)
                kept.append(entry)
            if group["hooks"] and not kept:
                continue
            new_group = dict(group)
            new_group["hooks"] = kept
            new_groups.append(new_group)
        hooks[event] = new_groups
    for event, items in want.items():
        groups = hooks.setdefault(event, [])
        present = set()
        for group in groups:
            if isinstance(group, dict) and isinstance(group.get("hooks"), list):
                for entry in group["hooks"]:
                    if rule.owns(entry):
                        present.add(canonical_hash(_meta(group), entry))
        for meta, entry, h in items:
            if h in present:
                continue
            target_group = next(
                (g for g in groups if isinstance(g, dict) and isinstance(g.get("hooks"), list) and _meta(g) == meta),
                None,
            )
            if target_group is None:
                target_group = {**meta, "hooks": []}
                groups.append(target_group)
            target_group["hooks"].append(entry)
            present.add(h)
            res.added.append(f"{event}: {entry.get('command')}")
    for event in [e for e, g in hooks.items() if g == []]:
        if event not in want:
            del hooks[event]
    res.owned_hashes = sorted({canonical_hash(m, e) for _, m, e in owned_entries(result, rule)})
    return res


def duplicate_owned(settings: dict, rule: OwnerRule) -> list[str]:
    """Owned (event, group, entry) triples that appear more than once."""
    seen: dict[str, int] = {}
    labels: dict[str, str] = {}
    for event, meta, entry in owned_entries(settings, rule):
        h = canonical_hash(meta, entry)
        seen[h] = seen.get(h, 0) + 1
        labels[h] = f"{event}: {entry.get('command')}"
    return [labels[h] for h, n in seen.items() if n > 1]


def read_settings(path: Path) -> dict:
    """Load settings.json; missing or empty yields {}."""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return {}
    return json.loads(text) if text else {}


def backup(settings_path: Path, backups_dir: Path, guard: Guard) -> str | None:
    """Copy settings.json to ``backups/settings.<ts>.json``; keep the newest 10."""
    if not settings_path.is_file():
        return None
    ts = utc_ts()
    mkdirs(backups_dir, guard)
    atomic_write_bytes(backups_dir / f"settings.{ts}.json", settings_path.read_bytes(), guard, mode=0o600)
    olds = sorted(backups_dir.glob("settings.*.json"))
    for old in olds[:-SETTINGS_BACKUPS_KEEP]:
        old.unlink()
    return ts


def write(settings_path: Path, data: dict, guard: Guard) -> None:
    """Atomic write with mode 600."""
    atomic_write_bytes(settings_path, (json.dumps(data, indent=2) + "\n").encode(), guard, mode=0o600)


def restore(settings_path: Path, backups_dir: Path, ts: str, guard: Guard) -> str:
    """Restore ``settings.<ts>.json``; backs up the current file first."""
    src = backups_dir / f"settings.{ts}.json"
    if not src.is_file():
        raise FileNotFoundError(f"no settings backup {ts}")
    data = src.read_bytes()
    backup(settings_path, backups_dir, guard)
    atomic_write_bytes(settings_path, data, guard, mode=0o600)
    return str(src)
