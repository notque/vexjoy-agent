"""Deterministic coverage for the Jev skill-distillation harness."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "jev-skill-distill.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("jev_skill_distill", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def distill():
    return _load_module()


def _write_skill(root: Path, blocks: list[str]) -> Path:
    skill = root / "sample-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("\n\n".join(blocks), encoding="utf-8")
    return skill


def test_review_sends_exactly_50_nonempty_single_question_bundles(tmp_path, monkeypatch, distill):
    skill = _write_skill(tmp_path, ["the only local evidence block"])
    calls = []

    def fake_evaluate(state, questions, *, timeout):
        calls.append((state, questions, timeout))
        question_id = next(iter(questions))
        return {"answers": {question_id: {"noul": 0.5}}}

    monkeypatch.setattr(distill.jev_transport, "evaluate", fake_evaluate)

    result = distill.review(skill)

    assert result["questions"] == 50
    assert len(result["bundles"]) == 50
    assert len(calls) == 50
    assert all(state["bundle"]["files"] for state, _, _ in calls)
    assert all(
        state["bundle"]["files"] == [{"path": "SKILL.md#block-1", "text": "the only local evidence block"}]
        for state, _, _ in calls
    )
    assert all(len(questions) == 1 for _, questions, _ in calls)
    assert all(timeout == 45 for _, _, timeout in calls)
    assert [next(iter(questions)) for _, questions, _ in calls] == [
        f"bundle_{index}_{('general', 'unique', 'duplicate', 'actionable', 'brittle')[(index - 1) % 5]}"
        for index in range(1, 51)
    ]


def test_every_skill_and_reference_block_is_extracted_once_and_bundled(tmp_path, distill):
    skill = _write_skill(tmp_path, ["skill one", "skill two"])
    refs = skill / "references"
    refs.mkdir()
    (refs / "alpha.md").write_text("alpha one\n\nalpha two", encoding="utf-8")
    nested = refs / "nested"
    nested.mkdir()
    (nested / "beta.txt").write_text("beta one\n\nbeta two", encoding="utf-8")

    pieces = distill._pieces(skill)

    assert [(piece["path"], piece["text"]) for piece in pieces] == [
        ("SKILL.md#block-1", "skill one"),
        ("SKILL.md#block-2", "skill two"),
        ("references/alpha.md#block-1", "alpha one"),
        ("references/alpha.md#block-2", "alpha two"),
        ("references/nested/beta.txt#block-1", "beta one"),
        ("references/nested/beta.txt#block-2", "beta two"),
    ]
    bundled_paths = [piece["path"] for bundle in distill._bundles(pieces) for piece in bundle]
    expected_paths = {piece["path"] for piece in pieces}
    assert set(bundled_paths) == expected_paths
    assert all(bundled_paths.count(path) >= 1 for path in expected_paths)


def test_oversized_block_is_split_without_loss_and_each_part_is_bounded(tmp_path, distill):
    oversized = "x" * (distill.MAX_BUNDLE_CHARS * 2 + 17)
    skill = _write_skill(tmp_path, [oversized])

    pieces = distill._pieces(skill)

    assert [piece["path"] for piece in pieces] == [
        "SKILL.md#block-1-part-1",
        "SKILL.md#block-1-part-2",
        "SKILL.md#block-1-part-3",
    ]
    assert all(0 < len(piece["text"]) <= distill.MAX_BUNDLE_CHARS for piece in pieces)
    assert "".join(piece["text"] for piece in pieces) == oversized


def test_only_supported_text_references_are_loaded(tmp_path, distill):
    skill = _write_skill(tmp_path, ["skill"])
    refs = skill / "references"
    refs.mkdir()
    supported = {
        "a.md": "md",
        "b.TXT": "txt",
        "c.json": "json",
        "d.yaml": "yaml",
        "e.yml": "yml",
        "f.toml": "toml",
        "g.csv": "csv",
    }
    for name, content in supported.items():
        (refs / name).write_text(content, encoding="utf-8")
    for name in ("ignored.py", "ignored.html", "ignored.bin", "README"):
        (refs / name).write_bytes(b"ignored")

    pieces = distill._pieces(skill)
    represented = {piece["path"].split("#", 1)[0] for piece in pieces}

    assert represented == {"SKILL.md", *(f"references/{name}" for name in supported)}


def test_review_normalizes_answers_and_main_writes_json_output(tmp_path, monkeypatch, distill):
    skill = _write_skill(tmp_path, [f"block {index}" for index in range(50)])
    call_number = 0

    def fake_evaluate(_state, questions, *, timeout):
        nonlocal call_number
        assert timeout == 45
        call_number += 1
        question_id = next(iter(questions))
        answer = {question_id: {"noul": call_number / 100}}
        return {"answers": answer} if call_number % 2 else answer

    monkeypatch.setattr(distill.jev_transport, "evaluate", fake_evaluate)
    output = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), str(skill), "--output", str(output)])

    assert distill.main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload.keys() == {"bundles", "files_reviewed", "questions", "skill_dir"}
    assert payload["questions"] == 50
    assert payload["files_reviewed"] == 50
    assert payload["skill_dir"] == str(skill.resolve())
    assert len(payload["bundles"]) == 50
    first = payload["bundles"][0]
    assert first.keys() == {"answers", "bundle", "chars", "paths"}
    assert first["answers"] == {"bundle_1_general": {"noul": 0.01}}
    assert first["bundle"] == 1
    assert first["chars"] > 0
    assert len(first["paths"]) == 1
    assert first["paths"][0].startswith("SKILL.md#block-")
    assert payload["bundles"][1]["answers"] == {"bundle_2_unique": {"noul": 0.02}}
    assert output.read_text(encoding="utf-8").endswith("\n")
