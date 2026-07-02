"""Tests pinning the `not_for` render contract in routing-manifest.py (audit defect D5).

Formatters prepend "NOT: " to every not_for value. Three skills shipped
frontmatter values already starting with "NOT: ", so the manifest rendered
"NOT: NOT:". load_entries now strips a source-side prefix defensively;
this test pins both the clean and the legacy-prefixed input.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "routing-manifest.py"

_spec = importlib.util.spec_from_file_location("routing_manifest", SCRIPT)
assert _spec and _spec.loader
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)


def _write_index(tmp_path: Path, not_for: str) -> Path:
    """Write a minimal skills INDEX.json with one not_for-carrying entry."""
    index = {
        "skills": {
            "sample-skill": {
                "file": "skills/sample-skill/SKILL.md",
                "description": "A sample skill.",
                "triggers": ["sample"],
                "category": "testing",
                "not_for": not_for,
            }
        }
    }
    path = tmp_path / "INDEX.json"
    path.write_text(json.dumps(index), encoding="utf-8")
    return path


def _entries_for(tmp_path: Path, not_for: str, monkeypatch) -> list[dict]:
    """Load entries through the module with INDEX_PATHS pointed at a fixture."""
    tracked = _write_index(tmp_path, not_for)
    monkeypatch.setattr(rm, "INDEX_PATHS", {"skills": (tracked, None)})
    return rm.load_entries()


class TestNotForSingleprefix:
    """Every render path emits exactly one 'NOT: ' prefix."""

    def test_clean_value_renders_single_prefix(self, tmp_path, monkeypatch) -> None:
        entries = _entries_for(tmp_path, "empirical testing (use skill-eval).", monkeypatch)
        out = rm.format_compact(entries)
        assert "NOT: empirical testing (use skill-eval)." in out
        assert "NOT: NOT:" not in out

    def test_legacy_prefixed_value_is_stripped(self, tmp_path, monkeypatch) -> None:
        entries = _entries_for(tmp_path, "NOT: empirical testing (use skill-eval).", monkeypatch)
        out = rm.format_compact(entries)
        assert "NOT: empirical testing (use skill-eval)." in out
        assert "NOT: NOT:" not in out

    def test_stub_line_never_doubles_prefix(self, tmp_path, monkeypatch) -> None:
        entries = _entries_for(tmp_path, "NOT: full-repo scans.", monkeypatch)
        stub = rm._stub_line(entries[0])
        assert "NOT: full-repo scans." in stub
        assert "NOT: NOT:" not in stub

    def test_compact_mode_never_doubles_prefix(self, tmp_path, monkeypatch) -> None:
        entries = _entries_for(tmp_path, "NOT: full-repo scans.", monkeypatch)
        out = rm.format_compact_mode(entries)
        assert "NOT: NOT:" not in out
