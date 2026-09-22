"""Installed skill/agent indexes under ``~/.<target>/vexjoy/index/``.

Reuses the entry builders in scripts/generate-skill-index.py and
scripts/generate-agent-index.py as imported functions. Those scripts' ``main``
functions (which default-write into the repo) are never called.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import re
from pathlib import Path
from types import ModuleType

from .adapters import ADAPTERS
from .common import utc_iso
from .fsops import Guard, atomic_write_json
from .ledger import Ledger, LedgerEntry
from .sources import skill_md_of

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_MODULES: dict[str, ModuleType | None] = {}


def _load(filename: str) -> ModuleType | None:
    if filename in _MODULES:
        return _MODULES[filename]
    path = _SCRIPTS_DIR / filename
    mod: ModuleType | None = None
    try:
        spec = importlib.util.spec_from_file_location("_vexinstall_" + filename.replace("-", "_")[:-3], path)
        if spec is not None and spec.loader is not None:
            mod = importlib.util.module_from_spec(spec)
            with contextlib.redirect_stdout(io.StringIO()):
                spec.loader.exec_module(mod)
    except Exception:
        mod = None
    _MODULES[filename] = mod
    return mod


def _mini_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    block = text[3:end] if end != -1 else ""
    out: dict = {}
    for key in ("name", "description"):
        m = re.search(rf"^{key}\s*:\s*(.+)$", block, re.MULTILINE)
        if m:
            out[key] = m.group(1).strip().strip("\"'")
    return out


def _skill_entry(dest: Path, skills_rel: str, owner: str) -> dict | None:
    md = skill_md_of(dest)
    if md is None:
        return None
    try:
        text = md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    mod = _load("generate-skill-index.py")
    fm: dict | None
    if mod is not None:
        with contextlib.redirect_stdout(io.StringIO()):
            fm, _ = mod.extract_frontmatter(text)
    else:
        fm = _mini_frontmatter(text)
    if not fm:
        return None
    if mod is not None:
        entry = mod.build_entry(frontmatter=fm, skill_dir=dest, dir_prefix=skills_rel)
    else:
        entry = {"description": str(fm.get("description", ""))[:200]}
    rel_md = md.relative_to(dest).as_posix()
    entry["file"] = f"{skills_rel}/{dest.name}/{rel_md}"
    entry["owner"] = owner
    return entry


def _agent_entries(agents_dir: Path, runtime_root: Path, owned: dict[str, LedgerEntry]) -> dict:
    mod = _load("generate-agent-index.py")
    names = {Path(d).name for d in owned if d.endswith(".md")}
    agents: dict = {}
    if mod is not None and agents_dir.is_dir():
        with contextlib.redirect_stdout(io.StringIO()):
            raw = mod.generate_index(agents_dir, relative_to=runtime_root, include_private=True)
        for key, entry in raw.get("agents", {}).items():
            if Path(str(entry.get("file", ""))).name in names:
                agents[key] = entry
        return agents
    for name in sorted(names):
        path = agents_dir / name
        try:
            fm = _mini_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        rel = os.path.relpath(path, runtime_root).replace(os.sep, "/")
        agents[fm.get("name", name[:-3])] = {"file": rel, "short_description": fm.get("description", "")[:200]}
    return agents


def build(home: Path, target: str, ledger: Ledger) -> dict[str, dict]:
    """Build {kind: index} for one target from its ledger entries."""
    adapter = ADAPTERS[target]
    root = adapter.root_path(home)
    owned = ledger.for_target(target)
    out: dict[str, dict] = {}
    if adapter.skills:
        skills: dict = {}
        for d, e in sorted(owned.items()):
            if e.kind != "skill":
                continue
            entry = _skill_entry(Path(d), adapter.skills, e.owner)
            if entry is not None:
                skills[Path(d).name] = entry
        out["skills"] = {
            "version": "2.0",
            "generated": utc_iso(),
            "generated_by": "scripts/vexinstall",
            "target": target,
            "skills": skills,
        }
    if adapter.agents:
        agents_owned = {d: e for d, e in owned.items() if e.kind == "agent"}
        out["agents"] = {
            "version": "1.0",
            "generated_by": "scripts/vexinstall",
            "target": target,
            "agents": _agent_entries(root / adapter.agents, root, agents_owned),
        }
    return out


def write(home: Path, target: str, ledger: Ledger, guard: Guard) -> list[str]:
    """Write the installed indexes for *target*; returns written paths."""
    index_dir = ADAPTERS[target].index_dir(home)
    written = []
    for kind, data in build(home, target, ledger).items():
        path = index_dir / f"{kind}.json"
        atomic_write_json(path, data, guard)
        written.append(str(path))
    return written


def newest_source_mtime(ledger: Ledger, target: str) -> float:
    """Newest mtime among the source SKILL.md files of *target*'s skills."""
    newest = 0.0
    for e in ledger.for_target(target).values():
        if e.kind != "skill":
            continue
        md = skill_md_of(Path(e.source))
        if md is not None:
            with contextlib.suppress(OSError):
                newest = max(newest, md.stat().st_mtime)
    return newest
