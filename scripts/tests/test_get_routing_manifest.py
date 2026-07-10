"""Tests for scripts/get-routing-manifest.sh — hash-gated manifest cache.

The script prints the cached routing manifest when the cache and hash sidecar
are fresh (hash of generator scripts + INDEX inputs matches), else regenerates
via routing-manifest.py. These tests prove the three paths: cache hit returns
cache content, a stale hash regenerates, and a missing cache regenerates.

Run with: python3 -m pytest scripts/tests/test_get_routing_manifest.py -v
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_SRC = REPO_ROOT / "scripts" / "get-routing-manifest.sh"
DO_SKILL = REPO_ROOT / "skills" / "meta" / "do" / "SKILL.md"


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    """Build a fake scripts dir + repo base + HOME; return (sdir, home)."""
    base = tmp_path / "base"
    sdir = base / "scripts"
    sdir.mkdir(parents=True)
    script = sdir / "get-routing-manifest.sh"
    shutil.copy(SCRIPT_SRC, script)
    # The router invokes this script through bash, so its tracked mode must
    # not determine whether manifest loading works.
    script.chmod(0o644)
    (sdir / "routing-manifest.py").write_text('print("GENERATED")\n', encoding="utf-8")
    (sdir / "routing_index_merge.py").write_text("# merge helper\n", encoding="utf-8")
    (base / "skills").mkdir()
    (base / "skills" / "INDEX.json").write_text('{"skills": {}}', encoding="utf-8")
    (base / "agents").mkdir()
    (base / "agents" / "INDEX.json").write_text('{"agents": {}}', encoding="utf-8")
    wf = base / "skills" / "workflow" / "references"
    wf.mkdir(parents=True)
    (wf / "pipeline-index.json").write_text('{"pipelines": {}}', encoding="utf-8")
    home = tmp_path / "home"
    (home / ".claude" / "cache").mkdir(parents=True)
    return sdir, home


def _input_hash(sdir: Path) -> str:
    """Mirror the script's hash: sha256 over the concatenated existing inputs."""
    base = sdir.parent
    files = [
        sdir / "routing-manifest.py",
        sdir / "routing_index_merge.py",
        base / "skills" / "INDEX.json",
        base / "skills" / "INDEX.local.json",
        base / "agents" / "INDEX.json",
        base / "agents" / "INDEX.local.json",
        base / "skills" / "workflow" / "references" / "pipeline-index.json",
    ]
    h = hashlib.sha256()
    for f in files:
        if f.exists():
            h.update(f.read_bytes())
    return h.hexdigest()


def _run(sdir: Path, home: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, HOME=str(home))
    return subprocess.run(
        ["bash", str(sdir / "get-routing-manifest.sh")],
        capture_output=True,
        text=True,
        env=env,
    )


def test_cache_hit_returns_cache_content(tmp_path: Path) -> None:
    sdir, home = _setup(tmp_path)
    cache_dir = home / ".claude" / "cache"
    (cache_dir / "routing-manifest.txt").write_text("CACHED MANIFEST\n", encoding="utf-8")
    (cache_dir / "routing-manifest.hash").write_text(_input_hash(sdir), encoding="utf-8")
    result = _run(sdir, home)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "CACHED MANIFEST\n"


def test_stale_hash_regenerates(tmp_path: Path) -> None:
    sdir, home = _setup(tmp_path)
    cache_dir = home / ".claude" / "cache"
    (cache_dir / "routing-manifest.txt").write_text("CACHED MANIFEST\n", encoding="utf-8")
    (cache_dir / "routing-manifest.hash").write_text("deadbeef", encoding="utf-8")
    result = _run(sdir, home)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "GENERATED\n"


def test_missing_cache_regenerates(tmp_path: Path) -> None:
    sdir, home = _setup(tmp_path)
    result = _run(sdir, home)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "GENERATED\n"


def test_do_invokes_manifest_through_bash() -> None:
    """The router must not depend on the manifest script executable bit."""
    lines = DO_SKILL.read_text(encoding="utf-8").splitlines()
    assert 'bash "$SDIR/get-routing-manifest.sh"' in lines
