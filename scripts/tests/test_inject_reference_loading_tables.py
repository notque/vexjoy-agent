from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "inject_reference_loading_tables",
    _SCRIPTS_DIR / "inject_reference_loading_tables.py",
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["inject_reference_loading_tables"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]


def test_inject_table_from_routing_table() -> None:
    source = """# Demo Skill

## Routing

| Intent | Trigger phrases | Reference |
|---|---|---|
| Sync | "push", "ship" | `${CLAUDE_SKILL_DIR}/references/sync.md` |
| Fix | "fix review" | `${CLAUDE_SKILL_DIR}/references/fix.md` |

## Instructions

1. Do the work
"""

    rows = _mod.parse_existing_reference_table_candidates(source)
    assert [row.files for row in rows] == ["`sync.md`", "`fix.md`"]

    updated = _mod.inject_table(source, rows)

    assert "## Reference Loading Table" in updated
    assert "| \"push\", \"ship\" | `sync.md` | Sync |" in updated
    assert updated.index("## Reference Loading Table") < updated.index("## Instructions")


def test_inject_table_from_reference_bullets() -> None:
    source = """# Demo Agent

## References

- [python-errors.md](demo-agent/references/python-errors.md) — Error catalog for async and import failures
- [testing.md](demo-agent/references/testing.md) — Test setup and assertions
"""

    rows = _mod.parse_reference_bullets(source, "demo-agent")
    assert len(rows) == 2
    assert rows[0].files == "`python-errors.md`"
    assert "errors" in rows[0].signal

    updated = _mod.inject_table(source, rows)
    assert "## Reference Loading Table" in updated
    assert "`python-errors.md`" in updated
    assert updated.index("## Reference Loading Table") < updated.index("## References")


def test_inject_table_is_idempotent() -> None:
    source = """# Demo

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tests | `testing.md` | Loads testing guide |

## References
"""

    rows = [_mod.TableRow(signal="tests", files="`testing.md`", why="Loads testing guide")]

    assert _mod.inject_table(source, rows) == source


def test_do_skill_is_exempt_from_injection(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    skill_dir = repo / "skills" / "do"
    refs_dir = skill_dir / "references"
    refs_dir.mkdir(parents=True)
    (refs_dir / "routing-tables.md").write_text("# Routing\n", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text("# /do\n", encoding="utf-8")

    targets = _mod.iter_targets(repo, ["skill"])

    assert targets == []
