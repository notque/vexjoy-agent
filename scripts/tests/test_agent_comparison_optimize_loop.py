import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_assess_target_rejects_missing_frontmatter(tmp_path):
    optimize_loop = load_module(
        "agent_comparison_optimize_loop",
        "skills/agent-comparison/scripts/optimize_loop.py",
    )
    target = tmp_path / "SKILL.md"
    target.write_text("# no frontmatter\nbody\n")

    scores = optimize_loop.assess_target(
        target,
        [{"query": "write tests", "should_trigger": True}],
        "improve routing precision",
        dry_run=True,
    )

    assert scores["parses"] is False
    assert optimize_loop.composite_score(scores) == 0.0


def test_check_protected_sections_rejects_missing_blocks():
    optimize_loop = load_module(
        "agent_comparison_optimize_loop",
        "skills/agent-comparison/scripts/optimize_loop.py",
    )
    original = "alpha\n<!-- DO NOT OPTIMIZE -->\nkeep me\n<!-- END DO NOT OPTIMIZE -->\nomega\n"
    relocated = "alpha\nomega\n"

    assert optimize_loop.check_protected_sections(original, relocated) is False


def test_restore_protected_does_not_silently_reinsert_missing_blocks():
    generate_variant = load_module(
        "agent_comparison_generate_variant",
        "skills/agent-comparison/scripts/generate_variant.py",
    )
    original = "alpha\n<!-- DO NOT OPTIMIZE -->\nkeep me\n<!-- END DO NOT OPTIMIZE -->\nomega\n"
    variant = "alpha\nomega\n"

    restored = generate_variant.restore_protected(original, variant)

    assert restored == variant


def test_generate_variant_main_reads_current_content_from_file(tmp_path, monkeypatch, capsys):
    generate_variant = load_module(
        "agent_comparison_generate_variant",
        "skills/agent-comparison/scripts/generate_variant.py",
    )

    content_file = tmp_path / "current.md"
    content_file.write_text("---\ndescription: current\n---\n")

    def fake_run(cmd, capture_output, text, cwd, env, timeout):
        assert cmd[:2] == ["claude", "-p"]
        payload = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": "<variant>---\ndescription: updated\n---</variant>"
                            "<summary>updated</summary><deletion_justification></deletion_justification>",
                        }
                    ]
                },
            },
            {
                "type": "result",
                "result": "raw result",
                "usage": {"input_tokens": 1, "output_tokens": 2},
            },
        ]
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(generate_variant.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_variant.py",
            "--target",
            "skills/example/SKILL.md",
            "--goal",
            "improve routing precision",
            "--current-content-file",
            str(content_file),
            "--model",
            "fake-model",
        ],
    )

    generate_variant.main()
    output = json.loads(capsys.readouterr().out)

    assert output["variant"] == "---\ndescription: updated\n---"
    assert output["tokens_used"] == 3
    assert output["reasoning"] == "raw result"


def test_optimize_loop_omits_model_flag_when_not_provided(tmp_path, monkeypatch):
    optimize_loop = load_module(
        "agent_comparison_optimize_loop_nomodel",
        "skills/agent-comparison/scripts/optimize_loop.py",
    )

    target = tmp_path / "SKILL.md"
    target.write_text("---\nname: test-skill\ndescription: test description\nversion: 1.0.0\n---\n\n# Skill\n")
    tasks = [
        {"name": "train-positive", "query": "write go tests", "should_trigger": True, "split": "train"},
        {"name": "test-negative", "query": "debug kubernetes", "should_trigger": False, "split": "test"},
    ]
    tasks_file = tmp_path / "tasks.json"
    tasks_file.write_text(json.dumps({"tasks": tasks}))

    seen_cmds = []

    def fake_assess_target(*args, **kwargs):
        return {
            "parses": True,
            "correctness": 1.0,
            "conciseness": 1.0,
            "clarity": 1.0,
            "task_results": [{"name": "train-positive", "passed": False}],
        }

    def fake_run(cmd, capture_output, text, timeout, cwd=None, env=None):
        seen_cmds.append(cmd)
        payload = {
            "variant": target.read_text(),
            "summary": "no-op",
            "reasoning": "ok",
            "tokens_used": 0,
            "deletion_justification": "",
        }
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(optimize_loop, "assess_target", fake_assess_target)
    monkeypatch.setattr(optimize_loop.subprocess, "run", fake_run)

    optimize_loop.run_optimization_loop(
        target_path=target,
        goal="improve routing precision",
        benchmark_tasks_path=tasks_file,
        max_iterations=1,
        min_gain=0.02,
        train_split=0.6,
        model=None,
        output_dir=tmp_path / "out",
        report_path=tmp_path / "out" / "report.html",
        verbose=False,
        dry_run=False,
    )

    assert seen_cmds
    assert "--model" not in seen_cmds[0]


def test_optimize_loop_respects_revert_streak_limit(tmp_path, monkeypatch):
    optimize_loop = load_module(
        "agent_comparison_optimize_loop_revert_limit",
        "skills/agent-comparison/scripts/optimize_loop.py",
    )

    target = tmp_path / "SKILL.md"
    target.write_text("---\nname: test-skill\ndescription: test description\nversion: 1.0.0\n---\n\n# Skill\n")
    tasks_file = tmp_path / "tasks.json"
    tasks_file.write_text(
        json.dumps(
            {
                "tasks": [
                    {"name": "train-positive", "query": "write go tests", "should_trigger": True, "split": "train"},
                    {"name": "test-negative", "query": "debug kubernetes", "should_trigger": False, "split": "test"},
                ]
            }
        )
    )

    def fake_assess_target(*args, **kwargs):
        return {
            "parses": True,
            "correctness": 0.0,
            "conciseness": 1.0,
            "clarity": 1.0,
            "task_results": [{"name": "train-positive", "passed": False}],
        }

    def fake_run(cmd, capture_output, text, timeout, cwd=None, env=None):
        payload = {
            "variant": target.read_text(),
            "summary": "no-op",
            "reasoning": "ok",
            "tokens_used": 0,
            "deletion_justification": "",
        }
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(optimize_loop, "assess_target", fake_assess_target)
    monkeypatch.setattr(optimize_loop.subprocess, "run", fake_run)

    result = optimize_loop.run_optimization_loop(
        target_path=target,
        goal="improve routing precision",
        benchmark_tasks_path=tasks_file,
        max_iterations=10,
        min_gain=0.02,
        train_split=0.6,
        revert_streak_limit=2,
        model=None,
        output_dir=tmp_path / "out",
        report_path=tmp_path / "out" / "report.html",
        verbose=False,
        dry_run=False,
    )

    assert result["status"] == "CONVERGED"
    assert "2 rounds without KEEP" in result["exit_reason"]


def test_optimize_loop_beam_search_retains_top_k_candidates(tmp_path, monkeypatch):
    optimize_loop = load_module(
        "agent_comparison_optimize_loop_beam",
        "skills/agent-comparison/scripts/optimize_loop.py",
    )

    target = tmp_path / "SKILL.md"
    target.write_text("---\nname: test-skill\ndescription: test description\nversion: 1.0.0\n---\n\n# Skill\n")
    tasks_file = tmp_path / "tasks.json"
    tasks_file.write_text(
        json.dumps(
            {
                "tasks": [
                    {"name": "train-positive", "query": "write go tests", "should_trigger": True, "split": "train"},
                    {"name": "test-negative", "query": "debug kubernetes", "should_trigger": False, "split": "test"},
                ]
            }
        )
    )

    generated = iter(["alpha", "beta"])

    def fake_run(cmd, capture_output, text, timeout, cwd=None, env=None):
        label = next(generated)
        payload = {
            "variant": target.read_text() + f"\n<!-- {label} -->\n",
            "summary": f"candidate-{label}",
            "reasoning": "ok",
            "tokens_used": 10,
            "deletion_justification": "",
        }
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    def fake_assess_target(path, *args, **kwargs):
        content = Path(path).read_text()
        score = 0.0
        if "<!-- alpha -->" in content:
            score = 1.2
        elif "<!-- beta -->" in content:
            score = 2.4
        return {
            "parses": True,
            "compiles": True,
            "tests_pass": True,
            "protected_intact": True,
            "correctness": score,
            "error_handling": 0.0,
            "language_idioms": 0.0,
            "testing": 0.0,
            "efficiency": 0.0,
            "task_results": [],
        }

    monkeypatch.setattr(optimize_loop.subprocess, "run", fake_run)
    monkeypatch.setattr(optimize_loop, "assess_target", fake_assess_target)

    result = optimize_loop.run_optimization_loop(
        target_path=target,
        goal="improve routing precision",
        benchmark_tasks_path=tasks_file,
        max_iterations=1,
        min_gain=0.0,
        train_split=0.6,
        beam_width=2,
        candidates_per_parent=2,
        model=None,
        output_dir=tmp_path / "out",
        report_path=tmp_path / "out" / "report.html",
        verbose=False,
        dry_run=False,
    )

    assert result["search_strategy"] == "beam"
    assert result["beam_width"] == 2
    assert result["candidates_per_parent"] == 2
    assert result["improvements_found"] == 2
    selected = [it for it in result["iterations"] if it.get("selected_for_frontier")]
    assert len(selected) == 2
    assert selected[0]["frontier_rank"] == 1 or selected[1]["frontier_rank"] == 1
