"""Private-leak detection: overlay names and content hashes vs tracked repo files (spec 7.5).

Findings carry only the tracked path and the matched overlay name. File
contents are never returned or printed.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from . import gitutil
from .common import file_sha256, iter_tree_files
from .ledger import Ledger
from .sources import OverlayConfig, PublicSources

MIN_NAME_LEN = 4
MIN_HASH_BYTES = 32
MAX_SCAN_BYTES = 2 * 1024 * 1024

# Harness built-in commands and slash commands (never private overlay names).
BUILTIN_COMMANDS: frozenset[str] = frozenset(
    {
        "goal",
        "compact",
        "schedule",
        "browser",
        "plan",
        "grill-me",
        "teamwork",
        "learn",
        "boost",
        "help",
        "clear",
        "cost",
        "doctor",
        "init",
        "login",
        "logout",
        "review",
        "pr-comments",
        "bug",
    }
)

# Common/normal words that may be overlay skill names but must not be flagged
# as content-name leaks when they appear in normal tracked documentation or code.
COMMON_WORDS: frozenset[str] = frozenset(
    {
        "anti",
        "auto",
        "base",
        "blog",
        "check",
        "code",
        "content",
        "core",
        "data",
        "deep",
        "deploy",
        "docs",
        "draft",
        "edit",
        "editor",
        "file",
        "five",
        "full",
        "game",
        "image",
        "images",
        "main",
        "news",
        "open",
        "pipeline",
        "post",
        "quick",
        "research",
        "review",
        "social",
        "story",
        "teach",
        "test",
        "text",
        "tool",
        "tools",
        "user",
        "video",
        "voice",
        "wizard",
        "write",
        "writer",
        "writing",
    }
)


def load_common_words(cfg: OverlayConfig | None = None) -> frozenset[str]:
    """Base COMMON_WORDS plus optional host-local words from <overlays_dir>/common-words.txt."""
    words = set(COMMON_WORDS)
    if cfg is not None and cfg.path is not None:
        ignore_file = cfg.path.parent / "common-words.txt"
        if ignore_file.is_file():
            try:
                for line in ignore_file.read_text(encoding="utf-8").splitlines():
                    w = line.strip().lower()
                    if w and not w.startswith("#"):
                        words.add(w)
            except OSError:
                pass
    return frozenset(words)


@dataclass(frozen=True)
class Leak:
    """One finding: tracked path, overlay name, how it matched."""

    path: str
    name: str
    how: str  # path | content-name | content-hash


def overlay_names(ledger: Ledger, cfg: OverlayConfig, pub: PublicSources) -> set[str]:
    """Deployed overlay names from the ledger (plus configured overlays), minus public homonyms."""
    names: set[str] = set()
    for e in ledger.entries.values():
        if e.owner.startswith("overlay:"):
            n = Path(e.dest).name
            names.add(n[:-3] if n.endswith(".md") else n)
    for ov in cfg.overlays:
        for item in ov.skills + ov.data + ov.agents:
            names.add(item.name[:-3] if item.name.endswith(".md") else item.name)
    public = {i.name for i in pub.skills + pub.promoted + pub.support + pub.data}
    public |= {i.name[:-3] if i.name.endswith(".md") else i.name for i in pub.agents}
    public |= {i.name for i in pub.commands}
    public |= BUILTIN_COMMANDS
    return {n for n in names if len(n) >= MIN_NAME_LEN and n not in public}


def overlay_hashes(ledger: Ledger, cfg: OverlayConfig) -> dict[str, str]:
    """sha256 -> overlay entry name for every overlay source file (from ledger and config)."""
    sources: dict[str, str] = {}
    for e in ledger.entries.values():
        if e.owner.startswith("overlay:"):
            sources[e.source] = Path(e.dest).name
    for ov in cfg.overlays:
        for item in ov.skills + ov.data + ov.agents:
            sources[str(item.source)] = item.name
    out: dict[str, str] = {}
    for src, name in sources.items():
        p = Path(src)
        files = [p] if p.is_file() else [p / r for r in iter_tree_files(p)] if p.is_dir() else []
        for f in files:
            try:
                if f.stat().st_size >= MIN_HASH_BYTES:
                    out.setdefault(file_sha256(f), name)
            except OSError:
                continue
    return out


def find_leaks(repo: Path, ledger: Ledger, cfg: OverlayConfig, pub: PublicSources) -> list[Leak]:
    """Scan ``git ls-files`` for overlay names (path or content) and overlay content hashes."""
    names = overlay_names(ledger, cfg, pub)
    hashes = overlay_hashes(ledger, cfg)
    if not names and not hashes:
        return []
    common = load_common_words(cfg)
    content_names = names - common
    pattern = (
        re.compile(
            r"(?<![A-Za-z0-9_-])("
            + "|".join(sorted(map(re.escape, content_names), key=len, reverse=True))
            + r")(?![A-Za-z0-9_-])"
        )
        if content_names
        else None
    )
    leaks: list[Leak] = []
    for rel in gitutil.tracked_files(repo):
        full = repo / rel
        parts = rel.split("/")
        for part in parts:
            stem = part[:-3] if part.endswith(".md") else part
            if stem in names:
                leaks.append(Leak(rel, stem, "path"))
                break
        try:
            st = os.stat(full)
        except OSError:
            continue
        if not os.path.isfile(full) or st.st_size > MAX_SCAN_BYTES:
            continue
        if st.st_size >= MIN_HASH_BYTES and hashes:
            h = file_sha256(full)
            if h in hashes:
                leaks.append(Leak(rel, hashes[h], "content-hash"))
        if pattern is not None:
            try:
                text = full.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            m = pattern.search(text)
            if m:
                leaks.append(Leak(rel, m.group(1), "content-name"))
    return leaks
