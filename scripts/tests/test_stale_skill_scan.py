#!/usr/bin/env python3
"""Tests for scripts/stale-skill-scan.py — ranked pruning-candidate report.

ADR: skill-scaffold-pruning. The scanner ranks skills/agents by a staleness
score built from three signals already in the toolkit: git mtime, routing-row
frequency, and orphaned INDEX entries. Report-only: it never edits, deletes, or
blocks; exit is always 0.

Fixtures: a temp repo-root tree with skills/INDEX.json + agents/INDEX.json and
SKILL.md / agent .md files. Routing rows seeded in a throwaway learning.db via
CLAUDE_LEARNING_DIR. git mtime mocked by monkeypatching the scanner's mtime
function, so tests need no real git history.

Run with: python3 -m pytest scripts/tests/test_stale_skill_scan.py -v
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent
LIB_DIR = REPO_ROOT / "hooks" / "lib"
SCAN_PATH = SCRIPTS_DIR / "stale-skill-scan.py"

NOW = 1_700_000_000  # fixed epoch for determinism
DAY = 86400


@pytest.fixture()
def db_env(tmp_path, monkeypatch):
    """Throwaway learning.db; reset init cache."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    yield ldb


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _seed_route(ldb, *, agent, skill, count=1):
    """Seed a routing row keyed agent:skill with observation_count=count.

    record_learning upserts observation_count += 1 per call, so call `count`
    times to reach the target count.
    """
    key = f"{agent}:{skill}"
    for _ in range(count):
        ldb.record_learning(
            topic="routing",
            key=key,
            value=f"routing-decision: agent={agent} skill={skill} request: do work",
            category="effectiveness",
            source="hook:routing-decision-recorder",
            session_id="s1",
        )


def _make_tree(root: Path, *, skills=None, agents=None, on_disk=None):
    """Build a fixture repo-root with INDEX.json files + component files.

    skills/agents: {name: file_field}. on_disk: set of names whose file is
    actually written (others are orphaned INDEX entries).
    """
    skills = skills or {}
    agents = agents or {}
    on_disk = on_disk if on_disk is not None else set(skills) | set(agents)

    (root / "skills").mkdir(parents=True, exist_ok=True)
    (root / "agents").mkdir(parents=True, exist_ok=True)

    skills_index = {"version": "2.0", "skills": {n: {"file": f} for n, f in skills.items()}}
    agents_index = {"version": "1.0", "agents": {n: {"file": f} for n, f in agents.items()}}
    (root / "skills" / "INDEX.json").write_text(json.dumps(skills_index), encoding="utf-8")
    (root / "agents" / "INDEX.json").write_text(json.dumps(agents_index), encoding="utf-8")

    for name, file_field in {**skills, **agents}.items():
        if name in on_disk:
            p = root / file_field
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("body\n", encoding="utf-8")
    return root


def _scan(mod, root, *, mtimes, top=15, kind="all", min_age_days=180):
    """Run the scanner with a fixed now and mocked per-file git mtimes."""
    return mod.scan(
        repo_root=root,
        top=top,
        kind=kind,
        min_age_days=min_age_days,
        now_epoch=NOW,
        mtime_fn=lambda path: mtimes.get(Path(path).name, NOW),
    )


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def test_orphan_ranks_first(db_env):
    """An INDEX entry whose file is missing scores +100 and ranks first."""
    mod = _load(SCAN_PATH, "stale_skill_scan")
    root = _make_tree(
        Path(db_env.get_db_path()).parent.parent / "tree_orphan",
        skills={"legacy-foo": "skills/legacy/legacy-foo/SKILL.md", "fresh": "skills/x/fresh/SKILL.md"},
        on_disk={"fresh"},  # legacy-foo file absent -> orphan
    )
    _seed_route(db_env, agent="a", skill="fresh", count=20)
    results = _scan(mod, root, mtimes={"SKILL.md": NOW}, kind="skills")

    top = results[0]
    assert top["name"] == "legacy-foo"
    assert top["orphaned"] is True
    assert top["score"] >= 100
    assert any("orphan" in r.lower() for r in top["reasons"])


def test_never_routed(db_env):
    """An old, on-disk skill with zero routing rows scores +20, reason 'never routed'."""
    mod = _load(SCAN_PATH, "stale_skill_scan")
    root = _make_tree(
        Path(db_env.get_db_path()).parent.parent / "tree_never",
        skills={"lonely": "skills/x/lonely/SKILL.md"},
    )
    # no routing rows at all
    mtimes = {"SKILL.md": NOW - 400 * DAY}
    results = _scan(mod, root, mtimes=mtimes, kind="skills")

    lonely = next(r for r in results if r["name"] == "lonely")
    assert lonely["routes"] == 0
    assert any("never routed" in r.lower() for r in lonely["reasons"])
    assert lonely["score"] >= 20


def test_rarely_routed(db_env):
    """Routing observation_count summing to <=2 scores +10 with the count in the reason."""
    mod = _load(SCAN_PATH, "stale_skill_scan")
    root = _make_tree(
        Path(db_env.get_db_path()).parent.parent / "tree_rare",
        skills={"design": "skills/x/design/SKILL.md"},
    )
    _seed_route(db_env, agent="ui", skill="design", count=2)
    mtimes = {"SKILL.md": NOW - 400 * DAY}
    results = _scan(mod, root, mtimes=mtimes, kind="skills")

    design = next(r for r in results if r["name"] == "design")
    assert design["routes"] == 2
    assert any("rarely routed (2)" in r.lower() for r in design["reasons"])


def test_age_threshold_excludes_young(db_env):
    """A young, well-routed skill accrues no age points and is omitted (score 0)."""
    mod = _load(SCAN_PATH, "stale_skill_scan")
    root = _make_tree(
        Path(db_env.get_db_path()).parent.parent / "tree_young",
        skills={"newish": "skills/x/newish/SKILL.md"},
    )
    _seed_route(db_env, agent="a", skill="newish", count=10)
    mtimes = {"SKILL.md": NOW - 30 * DAY}  # 30d < min_age_days 180
    results = _scan(mod, root, mtimes=mtimes, kind="skills", min_age_days=180)

    assert all(r["name"] != "newish" for r in results)


def test_age_points_capped(db_env):
    """An old never-routed skill accrues +1 per stale month, capped at 24."""
    mod = _load(SCAN_PATH, "stale_skill_scan")
    root = _make_tree(
        Path(db_env.get_db_path()).parent.parent / "tree_capped",
        skills={"ancient": "skills/x/ancient/SKILL.md"},
    )
    # 3000 days -> 100 months, capped at 24; plus 20 for never-routed = 44.
    mtimes = {"SKILL.md": NOW - 3000 * DAY}
    results = _scan(mod, root, mtimes=mtimes, kind="skills")

    ancient = next(r for r in results if r["name"] == "ancient")
    assert ancient["score"] == 24 + 20


def test_healthy_omitted(db_env):
    """A recent, well-routed, on-disk skill scores 0 and never appears."""
    mod = _load(SCAN_PATH, "stale_skill_scan")
    root = _make_tree(
        Path(db_env.get_db_path()).parent.parent / "tree_healthy",
        skills={"healthy": "skills/x/healthy/SKILL.md"},
    )
    _seed_route(db_env, agent="a", skill="healthy", count=15)
    mtimes = {"SKILL.md": NOW - 10 * DAY}
    results = _scan(mod, root, mtimes=mtimes, kind="skills")

    assert results == []


def test_rank_order_and_top(db_env):
    """Mixed candidates sort by score desc; --top truncates."""
    mod = _load(SCAN_PATH, "stale_skill_scan")
    root = _make_tree(
        Path(db_env.get_db_path()).parent.parent / "tree_rank",
        skills={
            "orphaned-one": "skills/x/orphaned-one/SKILL.md",
            "old-unrouted": "skills/x/old-unrouted/SKILL.md",
            "old-rare": "skills/x/old-rare/SKILL.md",
        },
        on_disk={"old-unrouted", "old-rare"},  # orphaned-one missing
    )
    _seed_route(db_env, agent="a", skill="old-rare", count=2)
    mtimes = {"SKILL.md": NOW - 400 * DAY}
    results = _scan(mod, root, mtimes=mtimes, kind="skills")

    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0]["name"] == "orphaned-one"  # +100 orphan dominates

    truncated = _scan(mod, root, mtimes=mtimes, kind="skills", top=1)
    assert len(truncated) == 1


def test_json_schema_keys(db_env):
    """Each result row carries the documented keys."""
    mod = _load(SCAN_PATH, "stale_skill_scan")
    root = _make_tree(
        Path(db_env.get_db_path()).parent.parent / "tree_keys",
        skills={"lonely": "skills/x/lonely/SKILL.md"},
    )
    mtimes = {"SKILL.md": NOW - 400 * DAY}
    results = _scan(mod, root, mtimes=mtimes, kind="skills")

    row = results[0]
    for key in ("kind", "name", "file", "age_days", "routes", "orphaned", "score", "reasons"):
        assert key in row


def test_determinism(db_env):
    """Same fixtures + mocked now/mtime -> identical output across runs."""
    mod = _load(SCAN_PATH, "stale_skill_scan")
    root = _make_tree(
        Path(db_env.get_db_path()).parent.parent / "tree_det",
        skills={"a-skill": "skills/x/a-skill/SKILL.md", "b-skill": "skills/x/b-skill/SKILL.md"},
    )
    _seed_route(db_env, agent="a", skill="a-skill", count=1)
    mtimes = {"SKILL.md": NOW - 300 * DAY}
    r1 = _scan(mod, root, mtimes=mtimes, kind="skills")
    r2 = _scan(mod, root, mtimes=mtimes, kind="skills")
    assert r1 == r2


def test_agents_scanned(db_env):
    """--kind agents scores agent components by the agent segment of routing keys."""
    mod = _load(SCAN_PATH, "stale_skill_scan")
    root = _make_tree(
        Path(db_env.get_db_path()).parent.parent / "tree_agents",
        agents={"old-bar-engineer": "agents/old-bar-engineer.md"},
    )
    _seed_route(db_env, agent="old-bar-engineer", skill="something", count=1)
    mtimes = {"old-bar-engineer.md": NOW - 300 * DAY}
    results = _scan(mod, root, mtimes=mtimes, kind="agents")

    bar = next(r for r in results if r["name"] == "old-bar-engineer")
    assert bar["kind"] == "agent"
    assert bar["routes"] == 1
    assert any("rarely routed (1)" in r.lower() for r in bar["reasons"])
