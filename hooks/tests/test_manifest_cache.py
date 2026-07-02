"""Tests for the hash-gated routing-manifest cache (ADR router-improvement-program C5).

Covers hooks/lib/manifest_cache.py and hooks/session-manifest-cache.py:
- cache hit: no generator run when inputs are unchanged
- cache miss: changed input hash triggers regeneration
- corrupted sidecar triggers regeneration (never falsely fresh)
- absent cache triggers regeneration
- generator failure keeps the old cache
- python digest == bash `cat <inputs> | sha256sum` (guards the SKILL.md
  Phase 2 freshness check)
- SessionStart hook exits 0 and emits valid JSON on all paths

Run with: python3 -m pytest hooks/tests/test_manifest_cache.py -v
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR / "lib"))

import manifest_cache as mc

HOOK_PATH = HOOKS_DIR / "session-manifest-cache.py"

# Stub generator: bumps a run counter, prints a manifest derived from
# skills/INDEX.json so regeneration is observable in the cache content.
STUB_GENERATOR = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import sys
    from pathlib import Path

    base = Path(__file__).resolve().parent.parent
    counter = base / "gen-count.txt"
    n = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(n + 1))
    print("AGENTS:\\n  demo\\n\\nSKILLS:")
    print("marker: " + (base / "skills" / "INDEX.json").read_text().strip())
    sys.exit(0)
    """
)

FAILING_GENERATOR = "#!/usr/bin/env python3\nimport sys\nsys.exit(1)\n"


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """A fake $HOME with a deployed ~/.claude tree and isolated cache paths."""
    home = tmp_path / "home"
    scripts = home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "routing-manifest.py").write_text(STUB_GENERATOR, encoding="utf-8")
    (scripts / "routing_index_merge.py").write_text("# merge lib v1\n", encoding="utf-8")

    base = home / ".claude"
    (base / "skills").mkdir()
    (base / "skills" / "INDEX.json").write_text('{"skills": {"a": {}}}', encoding="utf-8")
    (base / "agents").mkdir()
    (base / "agents" / "INDEX.json").write_text('{"agents": {"x": {}}}', encoding="utf-8")
    pipeline_dir = base / "skills" / "workflow" / "references"
    pipeline_dir.mkdir(parents=True)
    (pipeline_dir / "pipeline-index.json").write_text('{"pipelines": {}}', encoding="utf-8")

    cache_dir = base / "cache"
    monkeypatch.setattr(mc, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(mc, "CACHE_FILE", cache_dir / "routing-manifest.txt")
    monkeypatch.setattr(mc, "HASH_FILE", cache_dir / "routing-manifest.hash")
    return home


def gen_count(home: Path) -> int:
    counter = home / ".claude" / "gen-count.txt"
    return int(counter.read_text()) if counter.exists() else 0


def scripts_dir(home: Path) -> Path:
    return home / ".claude" / "scripts"


def test_absent_cache_regenerates(fake_home):
    sdir = scripts_dir(fake_home)
    assert not mc.is_fresh(sdir)
    assert mc.refresh(sdir) == "refreshed"
    assert gen_count(fake_home) == 1
    assert "AGENTS:" in mc.CACHE_FILE.read_text(encoding="utf-8")
    assert mc.HASH_FILE.read_text(encoding="utf-8").strip() == mc.compute_input_hash(sdir)
    assert mc.is_fresh(sdir)


def test_cache_hit_runs_no_generator(fake_home):
    sdir = scripts_dir(fake_home)
    assert mc.refresh(sdir) == "refreshed"
    before = mc.CACHE_FILE.read_text(encoding="utf-8")

    assert mc.refresh(sdir) == "fresh"
    assert gen_count(fake_home) == 1  # generator ran exactly once
    assert mc.CACHE_FILE.read_text(encoding="utf-8") == before


def test_changed_input_hash_regenerates(fake_home):
    sdir = scripts_dir(fake_home)
    mc.refresh(sdir)

    index = fake_home / ".claude" / "skills" / "INDEX.json"
    index.write_text('{"skills": {"a": {}, "brand-new": {}}}', encoding="utf-8")

    assert not mc.is_fresh(sdir)
    assert mc.refresh(sdir) == "refreshed"
    assert gen_count(fake_home) == 2
    assert "brand-new" in mc.CACHE_FILE.read_text(encoding="utf-8")


def test_corrupted_hash_sidecar_regenerates(fake_home):
    sdir = scripts_dir(fake_home)
    mc.refresh(sdir)

    mc.HASH_FILE.write_text("deadbeef-corrupted\n", encoding="utf-8")

    assert not mc.is_fresh(sdir)
    assert mc.refresh(sdir) == "refreshed"
    assert gen_count(fake_home) == 2
    assert mc.is_fresh(sdir)


def test_input_presence_changes_hash(fake_home):
    sdir = scripts_dir(fake_home)
    without_local = mc.compute_input_hash(sdir)

    local = fake_home / ".claude" / "skills" / "INDEX.local.json"
    local.write_text('{"skills": {"local-only": {}}}', encoding="utf-8")
    assert mc.compute_input_hash(sdir) != without_local

    local.unlink()
    assert mc.compute_input_hash(sdir) == without_local


def test_generator_failure_keeps_old_cache(fake_home):
    sdir = scripts_dir(fake_home)
    mc.refresh(sdir)
    old_cache = mc.CACHE_FILE.read_text(encoding="utf-8")

    (sdir / "routing-manifest.py").write_text(FAILING_GENERATOR, encoding="utf-8")

    status = mc.refresh(sdir)
    assert status.startswith("failed")
    assert mc.CACHE_FILE.read_text(encoding="utf-8") == old_cache
    assert not mc.is_fresh(sdir)  # stale sidecar: next check retries


@pytest.mark.skipif(shutil.which("sha256sum") is None, reason="sha256sum not available")
def test_python_digest_matches_bash_check(fake_home):
    """The SKILL.md Phase 2 bash freshness check must equal the python digest."""
    sdir = scripts_dir(fake_home)
    # Include one missing input (INDEX.local.json) to prove skip parity.
    quoted = " ".join(f'"{p}"' for p in mc.input_paths(sdir))
    bash_digest = subprocess.run(
        ["bash", "-c", f"cat {quoted} 2>/dev/null | sha256sum | cut -d' ' -f1"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert bash_digest == mc.compute_input_hash(sdir)


def run_hook(home: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, HOME=str(home))
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="",
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def test_hook_cold_then_fresh(fake_home):
    """Hook exits 0, populates the cache, then reports fresh on rerun."""
    result = run_hook(fake_home)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert "[manifest-cache] refreshed:" in context
    assert (fake_home / ".claude" / "cache" / "routing-manifest.txt").is_file()
    assert (fake_home / ".claude" / "cache" / "routing-manifest.hash").is_file()

    result = run_hook(fake_home)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "[manifest-cache] fresh:" in payload["hookSpecificOutput"]["additionalContext"]
    assert gen_count(fake_home) == 1  # second run hit the cache


def test_hook_without_deployed_scripts_is_silent_exit_0(tmp_path):
    """No ~/.claude/scripts: hook must emit empty JSON and exit 0."""
    home = tmp_path / "empty-home"
    home.mkdir()
    result = run_hook(home)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload.get("hookSpecificOutput", {}).get("additionalContext") is None


def test_hook_generator_failure_is_silent_exit_0(fake_home):
    (scripts_dir(fake_home) / "routing-manifest.py").write_text(FAILING_GENERATOR, encoding="utf-8")
    result = run_hook(fake_home)
    assert result.returncode == 0
    assert "falls back" in result.stderr
    payload = json.loads(result.stdout)
    assert payload.get("hookSpecificOutput", {}).get("additionalContext") is None
