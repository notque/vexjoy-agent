"""A sync that changes nothing rewrites no index and no ledger (lane C, C-04).

Every session start runs ``sync``. It used to rewrite all ten installed indexes and the ledger
each time, only to move the ``generated`` and ``updated_at`` stamps, and the new index bytes
invalidated the routing-manifest cache on every session. It also parsed the same frontmatter
once per target.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest
import yaml

from scripts.tests.vexinstall_support import Env, commit_all, skill_md, world

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vexinstall import index as index_mod
from vexinstall import ledger as ledger_mod

__all__ = ["world"]

LATER = "2099-01-01T00:00:00Z"
OLD = 1_000_000_000  # 2001, as an mtime
TARGETS = ("claude", "codex", "hermes")


def _ok(res) -> None:
    assert res.code == 0, f"exit {res.code}\nout={res.out}\nerr={res.err}"


def _state_files(env: Env) -> list[Path]:
    files = [env.home / ".claude" / "vexjoy" / "ledger.json"]
    for t in TARGETS:
        files.extend(sorted((env.root(t) / "vexjoy" / "index").glob("*.json")))
    return files


def _apply_all(env: Env) -> None:
    for t in TARGETS[1:]:
        env.root(t).mkdir()
    _ok(env.run("apply", "--target", "all"))


def _later_stamps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every stamp written from now on differs from the apply's, so a rewrite always shows in the bytes."""
    monkeypatch.setattr(index_mod, "utc_iso", lambda: LATER)
    monkeypatch.setattr(ledger_mod, "utc_iso", lambda: LATER)


def test_idle_sync_rewrites_no_index_and_no_ledger(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    _apply_all(world)
    files = _state_files(world)
    assert len(files) == 6  # ledger + claude and codex skills/agents + hermes skills
    before = {p: p.read_bytes() for p in files}
    for p in files:
        os.utime(p, (OLD, OLD))
    _later_stamps(monkeypatch)
    res = world.run("sync", "--target", "all")
    _ok(res)
    assert {p: p.read_bytes() for p in files} == before
    # An unchanged index still gets a fresh mtime, as a rewrite gave it: the doctor's index-stale
    # check and the PostToolUse index refresh read the mtime.
    assert all(p.stat().st_mtime > OLD for p in files)
    assert res.data["index"], "the report still lists every current index"
    assert res.out[0].startswith("[sync] claude: +0 ~0 -0,"), res.out[0]


def test_sync_rewrites_an_index_whose_content_changed(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    _apply_all(world)
    agents = world.root("claude") / "vexjoy" / "index" / "agents.json"
    agents_before = agents.read_bytes()
    md = world.repo / "skills" / "meta" / "alpha" / "SKILL.md"
    md.write_text(skill_md("alpha").replace("alpha skill for tests", "alpha skill, now reworded"))
    commit_all(world.repo, "reword alpha")
    _later_stamps(monkeypatch)
    _ok(world.run("sync", "--target", "all"))
    for t in TARGETS:
        data = json.loads((world.root(t) / "vexjoy" / "index" / "skills.json").read_text())
        assert "now reworded" in data["skills"]["alpha"]["description"], t
        assert data["generated"] == LATER, t
    assert agents.read_bytes() == agents_before


def test_doctor_sees_a_fresh_index_after_a_body_only_edit(world: Env) -> None:
    _apply_all(world)
    idx = world.root("claude") / "vexjoy" / "index" / "skills.json"
    before = idx.read_bytes()
    os.utime(idx, (OLD, OLD))
    md = world.repo / "skills" / "meta" / "alpha" / "SKILL.md"
    md.write_text(md.read_text() + "\nA body edit that leaves the frontmatter alone.\n")
    commit_all(world.repo, "alpha body")
    _ok(world.run("sync", "--target", "claude"))
    assert idx.read_bytes() == before
    doctor = world.run("doctor", "--target", "claude")
    assert not any("index-stale" in line for line in doctor.out), doctor.out


def test_index_only_refresh_moves_the_mtime_even_when_unchanged(world: Env) -> None:
    # hooks/lib/installed_index.py reports "no installed index written" unless the mtime moves.
    _apply_all(world)
    idx = world.root("codex") / "vexjoy" / "index" / "skills.json"
    before = idx.read_bytes()
    os.utime(idx, (OLD, OLD))
    _ok(world.run("sync", "--index-only", "--target", "codex"))
    assert idx.read_bytes() == before
    assert idx.stat().st_mtime_ns != OLD * 1_000_000_000


def test_unchanged_ledger_still_gets_mode_600(world: Env) -> None:
    _apply_all(world)
    ledger = world.home / ".claude" / "vexjoy" / "ledger.json"
    ledger.chmod(0o644)
    _ok(world.run("sync", "--target", "all"))
    assert stat.S_IMODE(ledger.stat().st_mode) == 0o600


def test_a_symlinked_index_is_replaced_not_followed(world: Env, tmp_path: Path) -> None:
    _apply_all(world)
    idx = world.root("claude") / "vexjoy" / "index" / "agents.json"
    outside = tmp_path / "outside.json"
    outside.write_bytes(idx.read_bytes())
    os.utime(outside, (OLD, OLD))
    idx.unlink()
    idx.symlink_to(outside)
    _ok(world.run("sync", "--target", "claude"))
    assert not idx.is_symlink() and json.loads(idx.read_text())["agents"]
    assert outside.stat().st_mtime == OLD, "the engine must never touch a file a symlink points at"


def _parse_count(env: Env, monkeypatch: pytest.MonkeyPatch, target: str) -> int:
    """yaml.safe_load calls one ``sync --index-only`` makes with freshly loaded generator modules."""
    calls = 0
    real = yaml.safe_load

    def counting(text):
        nonlocal calls
        calls += 1
        return real(text)

    monkeypatch.setattr(yaml, "safe_load", counting)
    monkeypatch.setattr(index_mod, "_MODULES", {})
    _ok(env.run("sync", "--index-only", "--target", target))
    monkeypatch.setattr(yaml, "safe_load", real)
    return calls


def test_each_frontmatter_is_parsed_once_across_targets(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    _apply_all(world)
    one = _parse_count(world, monkeypatch, "claude")
    assert one > 0
    assert _parse_count(world, monkeypatch, "all") == one  # codex and hermes reuse claude's parses


def test_memoized_parse_builds_the_same_indexes(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    _apply_all(world)

    def built() -> dict:
        monkeypatch.setattr(index_mod, "_MODULES", {})
        led, _ = ledger_mod.load(world.home / ".claude" / "vexjoy" / "ledger.json")
        assert led is not None
        out = {t: index_mod.build(world.home, t, led) for t in TARGETS}
        for kinds in out.values():
            for data in kinds.values():
                data.pop("generated", None)
        return out

    memoized = built()
    monkeypatch.setattr(index_mod, "_memoize_frontmatter", lambda _mod: None)
    assert built() == memoized
