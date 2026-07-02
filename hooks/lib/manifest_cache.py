"""Hash-gated routing-manifest cache (ADR router-improvement-program C5).

Keeps a disk copy of `routing-manifest.py` output so /do Phase 2 reads a
file instead of starting Python. Staleness = sha256 over the generator's
inputs: routing-manifest.py, routing_index_merge.py, skills/INDEX.json,
skills/INDEX.local.json, agents/INDEX.json, agents/INDEX.local.json, and
pipeline-index.json — missing files are skipped, so the digest is
byte-identical to the bash check in skills/meta/do/SKILL.md Phase 2:
`cat <inputs> 2>/dev/null | sha256sum`. Keep both sides in step.

Writers: hooks/session-manifest-cache.py (SessionStart) and the two
posttooluse-sync-*-index.py hooks (after INDEX regeneration).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

CACHE_DIR = Path.home() / ".claude" / "cache"
CACHE_FILE = CACHE_DIR / "routing-manifest.txt"
HASH_FILE = CACHE_DIR / "routing-manifest.hash"

# Same search order as the SDIR resolution in skills/meta/do/SKILL.md Phase 2.
_SCRIPT_DIR_CANDIDATES = (".claude", ".hermes", ".factory", ".codex", ".reasonix")

GENERATOR_TIMEOUT = 20  # seconds; full manifest generation completes in ~1s


def resolve_scripts_dir(home: Path | None = None) -> Path | None:
    """First deployed scripts dir containing routing-manifest.py, or None."""
    home = home or Path.home()
    for name in _SCRIPT_DIR_CANDIDATES:
        scripts = home / name / "scripts"
        if (scripts / "routing-manifest.py").is_file():
            return scripts
    return None


def input_paths(scripts_dir: Path) -> list[Path]:
    """Generator inputs in the fixed order the digest concatenates them."""
    base = scripts_dir.parent
    return [
        scripts_dir / "routing-manifest.py",
        scripts_dir / "routing_index_merge.py",
        base / "skills" / "INDEX.json",
        base / "skills" / "INDEX.local.json",
        base / "agents" / "INDEX.json",
        base / "agents" / "INDEX.local.json",
        base / "skills" / "workflow" / "references" / "pipeline-index.json",
    ]


def compute_input_hash(scripts_dir: Path) -> str:
    """sha256 hex over the concatenated input files; missing files skipped."""
    digest = hashlib.sha256()
    for path in input_paths(scripts_dir):
        try:
            digest.update(path.read_bytes())
        except OSError:
            continue
    return digest.hexdigest()


def _stored_hash() -> str:
    try:
        return HASH_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def is_fresh(scripts_dir: Path) -> bool:
    """True when the cache exists and the sidecar matches current inputs."""
    stored = _stored_hash()
    if not stored or not CACHE_FILE.is_file():
        return False
    return stored == compute_input_hash(scripts_dir)


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def refresh(scripts_dir: Path, force: bool = False) -> str:
    """Verify the cache; regenerate only when stale, absent, or forced.

    Returns "fresh" (hash matched, no generator run), "refreshed"
    (generator ran, cache + sidecar rewritten), or "failed: <why>"
    (generator failed; any existing cache is left untouched).

    The input hash is computed BEFORE the generator runs: if an input
    changes mid-generation, the stored sidecar no longer matches and the
    next check regenerates — the race resolves toward regeneration.
    """
    current = compute_input_hash(scripts_dir)
    if not force and CACHE_FILE.is_file() and _stored_hash() == current:
        return "fresh"

    import subprocess  # lazy: the fresh path (every session) never pays for it

    try:
        result = subprocess.run(
            [sys.executable, str(scripts_dir / "routing-manifest.py")],
            capture_output=True,
            text=True,
            timeout=GENERATOR_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"failed: generator did not run ({type(e).__name__})"

    if result.returncode != 0:
        return f"failed: generator exit {result.returncode}"
    if not result.stdout.strip():
        return "failed: generator produced empty output"

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Cache first, sidecar second: a crash between the writes leaves a
    # mismatched sidecar, which reads as stale — never as falsely fresh.
    _atomic_write(CACHE_FILE, result.stdout)
    _atomic_write(HASH_FILE, current + "\n")
    return "refreshed"
