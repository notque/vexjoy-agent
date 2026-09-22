"""Opt-in install profile (``.local/profile.yaml``), same config as install.sh.

install.sh reads ``$VEXJOY_INSTALL_PROFILE`` or ``<repo>/.local/profile.yaml``
through ``scripts/load-profile.py`` and skips disabled items. The engine uses the
same file and the same parser, so a filtered item is simply not desired:

* skills: skill dir name as-is (public and overlay, prefix included, e.g. ``voice-x``).
* agents: stem (``foo.md`` and ``foo/`` both match ``foo``).
* hooks: hook filename (``foo.py``). A whole-dir hooks install cannot exclude
  items, so a target with ``hooks="whole"`` installs hooks per-entry while any
  hook is disabled (install.sh ``install_component`` does the same).

Absent profile, missing PyYAML, or a malformed file = no filtering.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

PROFILE_ENV = "VEXJOY_INSTALL_PROFILE"
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_PARSER: list[ModuleType | None] = []


@dataclass(frozen=True)
class Profile:
    """Disabled item names per category."""

    path: Path | None = None
    skills: frozenset[str] = frozenset()
    agents: frozenset[str] = frozenset()
    hooks: frozenset[str] = frozenset()

    @property
    def active(self) -> bool:
        """True when anything is disabled."""
        return bool(self.skills or self.agents or self.hooks)

    def skill_disabled(self, name: str) -> bool:
        """Skill (or skill-root data/support) *name* is disabled."""
        return name in self.skills

    def agent_disabled(self, name: str) -> bool:
        """Agent entry *name* (``foo.md`` or ``foo``) is disabled by stem."""
        return (name[:-3] if name.endswith(".md") else name) in self.agents

    def hook_disabled(self, name: str) -> bool:
        """Hook filename *name* is disabled."""
        return name in self.hooks


EMPTY = Profile()


def profile_path(source_root: Path) -> Path:
    """``$VEXJOY_INSTALL_PROFILE`` else ``<source_root>/.local/profile.yaml`` (install.sh:1728)."""
    env = os.environ.get(PROFILE_ENV)
    return Path(env).expanduser() if env else source_root / ".local" / "profile.yaml"


def _parser() -> ModuleType | None:
    if _PARSER:
        return _PARSER[0]
    mod: ModuleType | None = None
    try:
        spec = importlib.util.spec_from_file_location("_vexinstall_load_profile", _SCRIPTS_DIR / "load-profile.py")
        if spec is not None and spec.loader is not None:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
    except Exception:  # PyYAML missing: install.sh's `|| DISABLED_*=""` means no filtering
        mod = None
    _PARSER.append(mod)
    return mod


def load_profile(path: Path) -> Profile:
    """Parse *path* with scripts/load-profile.py; never raises."""
    if not path.is_file():
        return EMPTY
    mod = _parser()
    if mod is None:
        return EMPTY
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            lists = mod.load(path)
    except Exception:
        return EMPTY
    return Profile(
        path=path,
        skills=frozenset(lists.get("skills", [])),
        agents=frozenset(lists.get("agents", [])),
        hooks=frozenset(lists.get("hooks", [])),
    )


def _hook_filename(command: str) -> str | None:
    """Filename after ``/hooks/`` (the legacy settings filter semantics)."""
    marker = "/hooks/"
    if marker not in command:
        return None
    tail = command.split(marker, 1)[1]
    parts = tail.split('"', 1)[0].split("'", 1)[0].split()
    return parts[0] if parts else None


def filter_settings_hooks(hooks: dict, profile: Profile) -> dict:
    """Drop desired settings.json hook entries whose hook file is disabled.

    Empty groups and events are dropped.
    """
    if not profile.hooks or not isinstance(hooks, dict):
        return hooks
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
            kept = []
            for entry in group["hooks"]:
                cmd = entry.get("command", "") if isinstance(entry, dict) else ""
                name = _hook_filename(cmd) if isinstance(cmd, str) else None
                if name and profile.hook_disabled(name):
                    continue
                kept.append(entry)
            if kept:
                kept_groups.append({**group, "hooks": kept})
        if kept_groups:
            out[event] = kept_groups
    return out
