"""Keep the generated routing indexes current before a script reads them.

``skills/INDEX.json`` and ``agents/INDEX.json`` are generated and untracked.
A copy that exists but predates its sources makes a local check disagree with
CI, and makes a write-mode generator render old text. A consumer calls
``ensure_fresh_indexes`` first:

- Index missing: run the generator. Raise ``RuntimeError`` if it is absent or
  does not create the index.
- Index older than a source: run the generator. Raise if it exits non-zero.
- Index older than a source and no generator in this root (a test fixture):
  keep the index.

Sources are the generator, ``scripts/lib/frontmatter.py``, the component files
(``SKILL.md`` or ``agents/*.md``), and the directories that hold them. A
directory's mtime changes when a component is added, removed, or renamed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

SURFACES = ("skills", "agents")

#: Environment variable set when a consumer (e.g. ``ensure_fresh_indexes``)
#: starts a generator.  The generator should skip its own drift gate to
#: avoid an unbounded regeneration cycle.
REGEN_ENV_VAR = "VEXJOY_INDEX_REGEN"

_GENERATORS = {
    "skills": "generate-skill-index.py",
    "agents": "generate-agent-index.py",
}
_GENERATOR_TIMEOUT = 120  # seconds; a full regeneration takes under one


def index_path(repo_root: Path, surface: str) -> Path:
    """Path of the generated index for ``surface``."""
    return repo_root / surface / "INDEX.json"


def generator_path(repo_root: Path, surface: str) -> Path:
    """Path of the script that generates the index for ``surface``."""
    return repo_root / "scripts" / _GENERATORS[surface]


def _sources(repo_root: Path, surface: str) -> Iterator[Path]:
    """Yield every path whose change makes the ``surface`` index out of date."""
    yield generator_path(repo_root, surface)
    yield repo_root / "scripts" / "lib" / "frontmatter.py"
    root = repo_root / surface
    if surface == "agents":
        yield root
        yield from root.glob("*.md")
        return
    for dirpath, _dirnames, filenames in os.walk(root):
        yield Path(dirpath)
        if "SKILL.md" in filenames:
            yield Path(dirpath) / "SKILL.md"


def local_index_path(repo_root: Path, surface: str) -> Path:
    """Path of the optional local overlay index for ``surface``."""
    return repo_root / surface / "INDEX.local.json"


def _newer_source_than(repo_root: Path, surface: str, target: Path) -> Path | None:
    """Return one source newer than ``target``, or None when it is current."""
    target_mtime = target.stat().st_mtime_ns
    for source in _sources(repo_root, surface):
        try:
            if source.stat().st_mtime_ns > target_mtime:
                return source
        except OSError:
            continue
    return None


def newer_source(repo_root: Path, surface: str) -> Path | None:
    """Return one source newer than the ``surface`` index, or None when it is current.

    Call only when the index exists.
    """
    return _newer_source_than(repo_root, surface, index_path(repo_root, surface))


def _run_generator(generator: Path, repo_root: Path, extra_args: tuple[str, ...] = ()) -> None:
    env = {**os.environ, REGEN_ENV_VAR: "1"}
    try:
        proc = subprocess.run(
            [sys.executable, str(generator), *extra_args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=_GENERATOR_TIMEOUT,
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"{generator.name} could not run: {exc}") from exc
    if proc.returncode != 0:
        raise RuntimeError(f"{generator.name} exited {proc.returncode}: {proc.stderr.strip()}")


def ensure_fresh_indexes(repo_root: Path, surfaces: Iterable[str] = SURFACES) -> list[str]:
    """Regenerate each missing or stale index. Return the surfaces regenerated.

    If ``agents/INDEX.local.json`` exists and is older than ``agents/`` or
    ``generate-agent-index.py``, refreshes it with ``--include-private`` so
    retired repo agents do not linger in the local overlay.

    Raises:
        RuntimeError: An index is missing and cannot be generated, or its
            generator failed.
    """
    regenerated: list[str] = []
    for surface in surfaces:
        index = index_path(repo_root, surface)
        generator = generator_path(repo_root, surface)
        missing = not index.is_file()
        needs_public = missing or newer_source(repo_root, surface) is not None
        if needs_public:
            if not generator.is_file():
                if missing:
                    raise RuntimeError(f"required {surface} index missing and cannot be generated: {index}")
            else:
                _run_generator(generator, repo_root)
                if not index.is_file():
                    raise RuntimeError(f"{generator.name} did not create required index: {index}")
                regenerated.append(surface)
        if surface == "agents":
            local = local_index_path(repo_root, surface)
            if local.is_file() and generator.is_file() and _newer_source_than(repo_root, surface, local) is not None:
                _run_generator(generator, repo_root, ("--include-private",))
                # Refreshing INDEX.local.json updates agents/ dir mtime; bump INDEX.json's
                # mtime so it does not look stale on the next check.
                if index.is_file():
                    try:
                        os.utime(index)
                    except OSError:
                        pass
                if surface not in regenerated:
                    regenerated.append(surface)
    return regenerated
