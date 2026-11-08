"""Negative-control tests for scripts/validate-pipeline-index.py.

Proves the validator rejects every defect class (P1, P2, P3) and accepts
a clean pipeline-index.json. Tests the check() function directly with
explicit repo_root so file paths resolve inside the temp tree.

Run with: python3 -m pytest scripts/tests/test_validate_pipeline_index.py -v
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

# Import the script's check() function by path (script name has hyphens).
_spec = importlib.util.spec_from_file_location(
    "validate_pipeline_index",
    Path(__file__).resolve().parent.parent / "validate-pipeline-index.py",
)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
check = _mod.check


def _write_index(path: Path, pipelines: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pipelines": pipelines}), encoding="utf-8")


def _write_doc(repo: Path, relpath: str, headings: list[str]) -> None:
    p = repo / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(f"## {h}" for h in headings) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Positive: clean pipeline -> no failures
# ---------------------------------------------------------------------------


def test_clean_pipeline_passes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    doc = "docs/my-pipeline.md"
    _write_doc(repo, doc, ["Phase 1: Setup", "Phase 2: Execute"])
    index = repo / "pipeline-index.json"
    _write_index(index, {"my-pipeline": {"file": doc, "phases": ["Setup", "Execute"]}})
    failures = check(index, repo)
    assert failures == [], failures


# ---------------------------------------------------------------------------
# NEGATIVE P1: missing file -> failure with MISSING-FILE
# ---------------------------------------------------------------------------


def test_p1_missing_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    index = repo / "pipeline-index.json"
    _write_index(index, {"ghost": {"file": "docs/nonexistent.md", "phases": ["Build"]}})
    failures = check(index, repo)
    assert len(failures) == 1, failures
    assert "MISSING-FILE" in failures[0], failures[0]
    assert "ghost" in failures[0], failures[0]


def test_p1_no_file_key(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    index = repo / "pipeline-index.json"
    _write_index(index, {"nofile": {"phases": ["Build"]}})
    failures = check(index, repo)
    assert len(failures) == 1, failures
    assert "MISSING-FILE" in failures[0], failures[0]


# ---------------------------------------------------------------------------
# NEGATIVE P2: phantom phase -> failure with PHANTOM-PHASE
# ---------------------------------------------------------------------------


def test_p2_phantom_phase(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    doc = "docs/real-pipeline.md"
    _write_doc(repo, doc, ["Phase 1: Setup"])
    index = repo / "pipeline-index.json"
    _write_index(index, {"real": {"file": doc, "phases": ["Setup", "Deploy"]}})
    failures = check(index, repo)
    assert len(failures) == 1, failures
    assert "PHANTOM-PHASE" in failures[0], failures[0]
    assert "Deploy" in failures[0], failures[0]


# ---------------------------------------------------------------------------
# NEGATIVE P3: no phases -> failure with NO-PHASES
# ---------------------------------------------------------------------------


def test_p3_empty_phases(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    doc = "docs/empty-pipeline.md"
    _write_doc(repo, doc, ["Overview"])
    index = repo / "pipeline-index.json"
    _write_index(index, {"empty": {"file": doc, "phases": []}})
    failures = check(index, repo)
    assert len(failures) == 1, failures
    assert "NO-PHASES" in failures[0], failures[0]


def test_p3_missing_phases_key(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    doc = "docs/nophases.md"
    _write_doc(repo, doc, ["Overview"])
    index = repo / "pipeline-index.json"
    _write_index(index, {"nophases": {"file": doc}})
    failures = check(index, repo)
    assert len(failures) == 1, failures
    assert "NO-PHASES" in failures[0], failures[0]


# ---------------------------------------------------------------------------
# P4 FRONTMATTER-DRIFT and P5 DUPLICATE: the doc's frontmatter is the source
# ---------------------------------------------------------------------------


def _write_fm_doc(repo: Path, relpath: str, pairs: list[str], triggers: list[str] | None = None) -> None:
    p = repo / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", "name: x", "routing:"]
    if triggers is not None:
        lines += ["  triggers:"] + [f"    - {t}" for t in triggers]
    lines += ["  pairs_with:"] + [f"    - {n}" for n in pairs]
    lines += ["---", "## Phase 1: Setup", ""]
    p.write_text("\n".join(lines), encoding="utf-8")


def _fm_index(tmp_path: Path, entry: dict, pairs: list[str], triggers: list[str] | None = None) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    doc = "docs/p.md"
    _write_fm_doc(repo, doc, pairs, triggers)
    index = repo / "pipeline-index.json"
    _write_index(index, {"p": {"file": doc, "phases": ["Setup"], **entry}})
    return index, repo


def test_p4_pairs_with_matching_frontmatter_passes(tmp_path: Path) -> None:
    index, repo = _fm_index(tmp_path, {"pairs_with": ["joy-check", "content"]}, ["joy-check", "content"])
    assert check(index, repo) == []


def test_p4_pairs_with_drift_fails(tmp_path: Path) -> None:
    # The live case: game-dev's index entry paired with itself and workflow
    # while its frontmatter says [frontend, workflow].
    index, repo = _fm_index(tmp_path, {"pairs_with": ["game-dev", "workflow"]}, ["frontend", "workflow"])
    failures = check(index, repo)
    assert len(failures) == 1 and "P4 FRONTMATTER-DRIFT" in failures[0], failures
    assert "frontend" in failures[0]


def test_p4_retired_frontmatter_names_map_to_their_successor(tmp_path: Path) -> None:
    index, repo = _fm_index(
        tmp_path,
        {"pairs_with": ["toolkit", "system-upgrade"]},
        ["agent-evaluation", "system-upgrade", "routing-table-updater"],
    )
    assert check(index, repo) == []


def test_p4_triggers_drift_fails(tmp_path: Path) -> None:
    index, repo = _fm_index(
        tmp_path, {"pairs_with": ["review"], "triggers": ["full review"]}, ["review"], ["full review", "deep review"]
    )
    failures = check(index, repo)
    assert len(failures) == 1 and "P4 FRONTMATTER-DRIFT" in failures[0] and "triggers" in failures[0], failures


def test_p4_doc_without_frontmatter_is_not_compared(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write_doc(repo, "docs/p.md", ["Phase 1: Setup"])
    index = repo / "pipeline-index.json"
    _write_index(index, {"p": {"file": "docs/p.md", "phases": ["Setup"], "pairs_with": ["anything"]}})
    assert check(index, repo) == []


def test_p5_duplicate_pairs_with_fails(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write_doc(repo, "docs/p.md", ["Phase 1: Setup"])
    index = repo / "pipeline-index.json"
    _write_index(index, {"p": {"file": "docs/p.md", "phases": ["Setup"], "pairs_with": ["toolkit", "toolkit"]}})
    failures = check(index, repo)
    assert len(failures) == 1 and "P5 DUPLICATE" in failures[0] and "toolkit" in failures[0], failures


def test_retired_map_has_no_stale_names() -> None:
    # A retired name no pipeline frontmatter uses any more must leave the map,
    # so the map shrinks as the docs are cleaned.
    assert _mod.stale_retired_names(_mod.DEFAULT_INDEX, _mod.REPO_ROOT) == []


def test_live_index_passes() -> None:
    assert check(_mod.DEFAULT_INDEX, _mod.REPO_ROOT) == []
