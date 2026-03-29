import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_load_optimization_data_ignores_unrelated_results_json(tmp_path):
    eval_compare = load_module(
        "skill_creator_eval_compare",
        "skills/skill-creator/scripts/eval_compare.py",
    )
    (tmp_path / "results.json").write_text(json.dumps({"status": "not-optimization"}))
    (tmp_path / "evals" / "iterations").mkdir(parents=True)
    expected = {
        "target": "skills/example/SKILL.md",
        "baseline_score": {"train": 1.0, "test": 1.0},
        "iterations": [],
    }
    (tmp_path / "evals" / "iterations" / "results.json").write_text(json.dumps(expected))

    loaded = eval_compare.load_optimization_data(tmp_path)

    assert loaded == expected
