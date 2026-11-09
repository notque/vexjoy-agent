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
from .interp import is_repo_only, strip_launcher
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
    """First shell token of *command* that is a path (contains '/').

    The interpreter launcher prefix is skipped, so a launcher command yields its hook path.
    """
    expanded = expand_vars(strip_launcher(command), home)
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


# Entry keys that never make two registrations different hooks. A writer that rewrote an account's
# settings.json without ``description`` made all 74 owned entries read as stale plus missing.
_COSMETIC_KEYS = frozenset({"description"})


def canonical_hash(meta: dict, entry: dict) -> str:
    """Hash of (group meta, entry) in canonical JSON; cosmetic entry keys are left out."""
    core = {k: v for k, v in entry.items() if k not in _COSMETIC_KEYS}
    blob = json.dumps({"group": meta, "entry": core}, sort_keys=True, separators=(",", ":"))
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


def drop_repo_only(hooks: dict) -> dict:
    """*hooks* without the repo-only bootstrap entry; groups it empties are dropped."""
    out: dict = {}
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            out[event] = groups
            continue
        kept_groups = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                kept_groups.append(group)
                continue
            entries = [e for e in group["hooks"] if not (isinstance(e, dict) and is_repo_only(e.get("command")))]
            if entries:
                kept_groups.append({**group, "hooks": entries})
        if kept_groups:
            out[event] = kept_groups
    return out


def desired_from_repo(source_root: Path) -> dict:
    """The ``hooks`` key of repo ``.claude/settings.json`` (source of desired entries), minus repo-only entries."""
    path = source_root / ".claude" / "settings.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    hooks = data.get("hooks", {})
    return drop_repo_only(hooks) if isinstance(hooks, dict) else {}


def desired_env_from_repo(source_root: Path) -> dict[str, str]:
    """The ``env`` key of repo ``.claude/settings.json`` (string values only)."""
    path = source_root / ".claude" / "settings.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    env = data.get("env", {})
    if not isinstance(env, dict):
        return {}
    return {k: v for k, v in env.items() if isinstance(k, str) and isinstance(v, str)}


RETIRED_ENV: dict[str, str] = {
    # name -> value the installer used to ship; removed only while it still has that value
    "CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING": "1",
}


def remove_retired_env(settings: dict, retired: dict[str, str] = RETIRED_ENV) -> list[str]:
    """Remove retired env vars in place when they still hold the shipped value; keep user-changed ones."""
    env = settings.get("env")
    if not isinstance(env, dict):
        return []
    removed = []
    for key, shipped in retired.items():
        if env.get(key) == shipped:
            del env[key]
            removed.append(key)
    return removed


SUPERSEDED_ENV: dict[str, tuple[str, ...]] = {
    # name -> values the installer used to ship; moved to the repo value once per install while it
    # still holds one. Reverting a default needs its own entry here (new value -> old value).
    "CLAUDE_CODE_AUTO_COMPACT_WINDOW": ("400000",),
}


def update_superseded_env(
    settings: dict,
    desired_env: dict[str, str],
    done: set[str],
    superseded: dict[str, tuple[str, ...]] = SUPERSEDED_ENV,
) -> tuple[list[str], list[str]]:
    """Move env vars still on an old shipped default to the repo value in place, once per install.

    *done* holds ``KEY=old`` markers from earlier runs; those are skipped, so a value the user sets
    after the migration (even an old default) is kept. Returns (``KEY=new`` updates, new markers).
    """
    env = settings.get("env")
    if not isinstance(env, dict):
        return [], []
    updated: list[str] = []
    marked: list[str] = []
    for key, old_values in superseded.items():
        new = desired_env.get(key)
        if new is None:
            continue
        pending = [old for old in old_values if f"{key}={old}" not in done]
        if not pending:
            continue
        if env.get(key) in pending and env[key] != new:
            env[key] = new
            updated.append(f"{key}={new}")
        marked.extend(f"{key}={old}" for old in pending)
    return updated, marked


def merge_env(settings: dict, desired_env: dict[str, str]) -> list[str]:
    """Add desired env vars missing from *settings* in place; never overwrite a user value."""
    if not desired_env:
        return []
    env = settings.get("env")
    if not isinstance(env, dict):
        env = {}
        settings["env"] = env
    added = []
    for key, value in desired_env.items():
        if key not in env:
            env[key] = value
            added.append(f"{key}={value}")
    return added


def desired_attribution_from_repo(source_root: Path) -> dict | None:
    """The ``attribution`` key of repo ``.claude/settings.json``, or None when it has none."""
    path = source_root / ".claude" / "settings.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = data.get("attribution")
    return value if isinstance(value, dict) else None


def merge_attribution(settings: dict, desired: dict | None) -> bool:
    """Add the repo ``attribution`` key when *settings* has none; never overwrite a user value."""
    if desired is None or "attribution" in settings:
        return False
    settings["attribution"] = dict(desired)
    return True


@dataclass
class RepoKeysResult:
    """Outcome of merging the repo's non-hook keys (env, attribution) into one settings.json."""

    env_added: list[str] = field(default_factory=list)
    env_updated: list[str] = field(default_factory=list)
    env_marked: list[str] = field(default_factory=list)
    env_removed: list[str] = field(default_factory=list)
    attribution_added: bool = False

    @property
    def changed(self) -> bool:
        """True when the merge changed the settings."""
        return bool(self.env_added or self.env_updated or self.env_removed or self.attribution_added)


def merge_repo_keys(settings: dict, source_root: Path, migrated: set[str]) -> RepoKeysResult:
    """Merge the repo's env vars and attribution into *settings* in place, as an install does.

    Missing env vars are added, an old shipped default in ``SUPERSEDED_ENV`` is moved once (*migrated*
    holds the markers of earlier runs), retired values are removed, and ``attribution`` is added when
    absent. A user value is never overwritten otherwise.
    """
    desired_env = desired_env_from_repo(source_root)
    res = RepoKeysResult()
    res.env_added = merge_env(settings, desired_env)
    res.env_updated, res.env_marked = update_superseded_env(settings, desired_env, migrated)
    res.env_removed = remove_retired_env(settings) if desired_env else []
    res.attribution_added = merge_attribution(settings, desired_attribution_from_repo(source_root))
    return res


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
