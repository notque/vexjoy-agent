import contextlib
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

    assert generate_variant.extract_description(output["variant"]) == "updated"
    assert output["tokens_used"] == 3
    assert output["reasoning"] == "raw result"


def test_generate_variant_only_changes_description_field(monkeypatch):
    generate_variant = load_module(
        "agent_comparison_generate_variant_description_only",
        "skills/agent-comparison/scripts/generate_variant.py",
    )

    current_content = """---
name: example-skill
description: |
  old description
routing:
  triggers:
    - "keep-this-trigger"
---

# Skill

Body stays the same.
"""

    def fake_run_claude_code(prompt, model):
        return (
            "<description>new description line 1\nnew description line 2</description>"
            "<summary>improved description</summary><deletion_justification></deletion_justification>",
            "raw result",
            9,
        )

    monkeypatch.setattr(generate_variant, "_run_claude_code", fake_run_claude_code)

    result = generate_variant.generate_variant(
        target_path="skills/example/SKILL.md",
        goal="improve routing precision",
        current_content=current_content,
        failures=[],
        model=None,
    )

    assert generate_variant.extract_description(result["variant"]) == "new description line 1\nnew description line 2"
    assert '    - "keep-this-trigger"' in result["variant"]
    assert "# Skill" in result["variant"]
    assert "Body stays the same." in result["variant"]
    assert result["deletions"] == []


def test_generate_variant_legacy_full_file_output_is_reduced_to_description_only(monkeypatch):
    generate_variant = load_module(
        "agent_comparison_generate_variant_legacy_variant",
        "skills/agent-comparison/scripts/generate_variant.py",
    )

    current_content = """---
name: example-skill
description: old description
routing:
  triggers:
    - "keep-this-trigger"
---

# Skill

Original body.
"""

    legacy_variant = """---
name: example-skill
description: updated description
routing:
  triggers:
    - "changed-trigger"
---

# Skill

Changed body.
"""

    def fake_run_claude_code(prompt, model):
        return (
            f"<variant>{legacy_variant}</variant><summary>legacy response</summary>"
            "<deletion_justification></deletion_justification>",
            "raw result",
            5,
        )

    monkeypatch.setattr(generate_variant, "_run_claude_code", fake_run_claude_code)

    result = generate_variant.generate_variant(
        target_path="skills/example/SKILL.md",
        goal="improve routing precision",
        current_content=current_content,
        failures=[],
        model=None,
    )

    assert generate_variant.extract_description(result["variant"]) == "updated description"
    assert '    - "keep-this-trigger"' in result["variant"]
    assert '    - "changed-trigger"' not in result["variant"]
    assert "Original body." in result["variant"]
    assert "Changed body." not in result["variant"]


def test_generate_variant_body_only_changes_body_not_frontmatter(monkeypatch):
    generate_variant = load_module(
        "agent_comparison_generate_variant_body_only",
        "skills/agent-comparison/scripts/generate_variant.py",
    )

    current_content = """---
name: example-skill
description: old description
version: 1.0.0
---

# Skill

Original body.
"""

    def fake_run_claude_code(prompt, model):
        assert "<current_body>" in prompt
        return (
            "<body># Skill\n\nImproved body.\n</body><summary>body change</summary>"
            "<deletion_justification></deletion_justification>",
            "raw result",
            7,
        )

    monkeypatch.setattr(generate_variant, "_run_claude_code", fake_run_claude_code)

    result = generate_variant.generate_variant(
        target_path="skills/example/SKILL.md",
        goal="improve behavioral quality",
        current_content=current_content,
        failures=[],
        model=None,
        optimization_scope="body-only",
    )

    assert "description: old description" in result["variant"]
    assert "# Skill\n\nImproved body." in result["variant"]
    assert "Original body." not in result["variant"]


def test_generate_variant_prompt_includes_full_failed_query_and_expectation(monkeypatch):
    generate_variant = load_module(
        "agent_comparison_generate_variant_failure_context",
        "skills/agent-comparison/scripts/generate_variant.py",
    )

    current_content = """---
name: example-skill
description: old description
---

# Skill
"""

    captured = {}

    def fake_run_claude_code(prompt, model):
        captured["prompt"] = prompt
        return (
            "<description>updated description</description>"
            "<summary>improved description</summary><deletion_justification></deletion_justification>",
            "raw result",
            4,
        )

    monkeypatch.setattr(generate_variant, "_run_claude_code", fake_run_claude_code)

    generate_variant.generate_variant(
        target_path="skills/example/SKILL.md",
        goal="improve routing precision",
        current_content=current_content,
        failures=[
            {
                "name": "rubber duck this bug with me, don't solv",
                "query": "rubber duck this bug with me, don't solve it yet",
                "should_trigger": True,
                "details": "trigger_rate=0.00",
                "trigger_rate": 0.0,
            }
        ],
        model=None,
    )

    assert "rubber duck this bug with me, don't solve it yet" in captured["prompt"]
    assert "expected: SHOULD trigger" in captured["prompt"]
    assert "raw_trigger_rate=0.00" in captured["prompt"]


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
    assert "2 rounds without ACCEPT" in result["exit_reason"]


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
        content = kwargs.get("candidate_content")
        if content is None:
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


def test_composite_score_uses_weighted_dimensions_only_when_hard_gates_pass():
    optimize_loop = load_module(
        "agent_comparison_optimize_loop_scoring",
        "skills/agent-comparison/scripts/optimize_loop.py",
    )

    scores = {
        "parses": True,
        "compiles": True,
        "tests_pass": True,
        "protected_intact": True,
        "correctness": 7.5,
        "error_handling": 6.0,
        "language_idioms": 5.0,
        "testing": 8.0,
        "efficiency": 4.0,
    }

    assert optimize_loop.composite_score(scores) == 6.55


def test_composite_score_returns_zero_when_hard_gate_fails():
    optimize_loop = load_module(
        "agent_comparison_optimize_loop_hard_gate",
        "skills/agent-comparison/scripts/optimize_loop.py",
    )

    scores = {
        "parses": False,
        "compiles": True,
        "tests_pass": False,
        "protected_intact": True,
        "correctness": 10.0,
        "error_handling": 10.0,
        "language_idioms": 10.0,
        "testing": 10.0,
        "efficiency": 10.0,
    }

    assert optimize_loop.composite_score(scores) == 0.0


def test_assess_target_scores_trigger_rate_results(tmp_path, monkeypatch):
    optimize_loop = load_module(
        "agent_comparison_optimize_loop_trigger_score",
        "skills/agent-comparison/scripts/optimize_loop.py",
    )

    target = tmp_path / "SKILL.md"
    target.write_text("---\ndescription: trigger scoring test\n---\n")
    tasks = [
        {"query": "good query", "should_trigger": True},
        {"query": "bad query", "should_trigger": False},
    ]

    def fake_run_trigger_rate(*args, **kwargs):
        return {
            "summary": {"total": 2, "passed": 1, "failed": 1},
            "results": [
                {"query": "good query", "pass": True, "trigger_rate": 1.0},
                {"query": "bad query", "pass": False, "trigger_rate": 0.0},
            ],
        }

    monkeypatch.setattr(optimize_loop, "_run_trigger_rate", fake_run_trigger_rate)

    scores = optimize_loop.assess_target(
        target,
        tasks,
        "improve routing precision",
        dry_run=False,
    )

    assert scores["correctness"] == 5.0
    assert scores["error_handling"] == 4.0
    assert scores["language_idioms"] == 3.5
    assert scores["testing"] == 4.0
    assert scores["efficiency"] == 3.6
    assert scores["tests_pass"] is False
    assert [item["passed"] for item in scores["task_results"]] == [True, False]
    assert scores["task_results"][0]["query"] == "good query"
    assert scores["task_results"][0]["should_trigger"] is True
    assert scores["task_results"][1]["query"] == "bad query"
    assert scores["task_results"][1]["should_trigger"] is False
    assert optimize_loop.composite_score(scores) == 4.285


def test_assess_target_forwards_parallel_workers_for_behavioral_eval(tmp_path, monkeypatch):
    optimize_loop = load_module(
        "agent_comparison_optimize_loop_behavioral_parallel",
        "skills/agent-comparison/scripts/optimize_loop.py",
    )

    target = tmp_path / "SKILL.md"
    target.write_text("---\ndescription: behavioral scoring test\n---\n")
    tasks = [
        {"query": "make a skill", "should_trigger": True, "eval_mode": "behavioral"},
    ]
    seen = {}

    def fake_run_behavioral_eval(*args, **kwargs):
        seen["parallel_workers"] = kwargs["parallel_workers"]
        return [{"query": "make a skill", "pass": True, "triggered": True, "new_artifacts": ["skills/x/SKILL.md"]}]

    monkeypatch.setattr(optimize_loop, "_run_behavioral_eval", fake_run_behavioral_eval)

    scores = optimize_loop.assess_target(
        target,
        tasks,
        "improve routing precision",
        parallel_eval_workers=3,
    )

    assert seen["parallel_workers"] == 3
    assert scores["tests_pass"] is True
    assert scores["correctness"] == 10.0
    assert scores["task_results"][0]["query"] == "make a skill"
    assert scores["task_results"][0]["should_trigger"] is True
    assert optimize_loop.composite_score(scores) == 8.45


def test_assess_target_scores_blind_compare_results(tmp_path, monkeypatch):
    optimize_loop = load_module(
        "agent_comparison_optimize_loop_blind_compare",
        "skills/agent-comparison/scripts/optimize_loop.py",
    )

    target = tmp_path / "SKILL.md"
    target.write_text("---\ndescription: blind compare test\n---\n")
    tasks = [{"query": "help me debug this", "eval_mode": "blind_compare", "judge": "socratic_question_only"}]

    def fake_run_blind_compare_eval(
        target_path, candidate_content, tasks, baseline_content=None, timeout=180, verbose=False
    ):
        assert baseline_content == "---\ndescription: baseline\n---\n"
        return [
            {
                "query": "help me debug this",
                "winner": "candidate",
                "candidate_score": 0.8,
                "baseline_score": 0.5,
                "candidate_output": "What changed recently?",
                "baseline_output": "The issue is probably your env var rename.",
                "passed": True,
            }
        ]

    monkeypatch.setattr(optimize_loop, "_run_blind_compare_eval", fake_run_blind_compare_eval)

    scores = optimize_loop.assess_target(
        target,
        tasks,
        "improve behavioral quality",
        candidate_content="---\ndescription: candidate\n---\n",
        baseline_content="---\ndescription: baseline\n---\n",
    )

    assert scores["correctness"] == 8.0
    assert scores["testing"] == 8.0
    assert scores["tests_pass"] is True
    assert scores["task_results"][0]["winner"] == "candidate"


def test_socratic_question_only_heuristic_penalizes_preamble():
    optimize_loop = load_module(
        "agent_comparison_optimize_loop_socratic_heuristic",
        "skills/agent-comparison/scripts/optimize_loop.py",
    )

    clean_score, _ = optimize_loop._score_socratic_question_only_output("What did you expect the test to do?")
    preamble_score, _ = optimize_loop._score_socratic_question_only_output(
        "Let me read the skill first. What did you expect the test to do?"
    )

    assert clean_score > preamble_score


def test_contains_fallback_contamination_detects_tool_blocked_text():
    optimize_loop = load_module(
        "agent_comparison_optimize_loop_contamination",
        "skills/agent-comparison/scripts/optimize_loop.py",
    )

    contaminated, reasons = optimize_loop._contains_fallback_contamination(
        "The Skill tool was blocked in this session, so I'll guide you through this directly."
    )

    assert contaminated is True
    assert "mentioned blocked skill tool" in reasons
    assert "fell back to direct guidance" in reasons


def test_run_blind_compare_zeroes_untriggered_or_contaminated_runs(tmp_path, monkeypatch):
    optimize_loop = load_module(
        "agent_comparison_optimize_loop_blind_compare_guardrails",
        "skills/agent-comparison/scripts/optimize_loop.py",
    )

    target = tmp_path / "skills" / "socratic-debugging" / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("---\nname: socratic-debugging\ndescription: test\n---\n")

    monkeypatch.setattr(optimize_loop, "_find_project_root", lambda: tmp_path)

    @contextlib.contextmanager
    def fake_worktree(_project_root, _relpath, content):
        worktree = tmp_path / ("candidate" if "candidate" in content else "baseline")
        worktree.mkdir(exist_ok=True)
        yield worktree

    monkeypatch.setattr(optimize_loop, "_candidate_worktree", fake_worktree)

    def fake_capture(query, cwd, accepted_skill_ids, timeout=180):
        if cwd.name == "baseline":
            return {
                "output": "What changed recently?",
                "triggered": False,
                "contaminated": False,
                "contamination_reasons": [],
            }
        return {
            "output": "The Skill tool was blocked in this session, so I'll guide you through this directly. What changed recently?",
            "triggered": True,
            "contaminated": True,
            "contamination_reasons": ["mentioned blocked skill tool", "fell back to direct guidance"],
        }

    monkeypatch.setattr(optimize_loop, "_run_query_capture_output", fake_capture)

    results = optimize_loop._run_blind_compare_eval(
        target,
        "---\nname: socratic-debugging\ndescription: candidate\n# candidate\n",
        [{"query": "help me debug", "eval_mode": "blind_compare", "judge": "socratic_question_only"}],
        baseline_content="---\nname: socratic-debugging\ndescription: baseline\n# baseline\n",
    )

    assert results[0]["baseline_score"] == 0.0
    assert results[0]["candidate_score"] == 0.0
    assert results[0]["baseline_triggered"] is False
    assert results[0]["candidate_contaminated"] is True
    assert results[0]["winner"] == "tie"
    assert results[0]["baseline_reasons"][0] == "target skill did not trigger"
    assert results[0]["candidate_reasons"][0] == "mentioned blocked skill tool"


def test_run_optimization_loop_forwards_parallel_eval_to_assessments(tmp_path, monkeypatch):
    optimize_loop = load_module(
        "agent_comparison_optimize_loop_parallel_forwarding",
        "skills/agent-comparison/scripts/optimize_loop.py",
    )

    target = tmp_path / "SKILL.md"
    target.write_text("---\nname: test-skill\ndescription: test description\nversion: 1.0.0\n---\n")
    tasks_file = tmp_path / "tasks.json"
    tasks_file.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "name": "train-positive",
                        "query": "make a skill",
                        "should_trigger": True,
                        "eval_mode": "behavioral",
                        "split": "train",
                    },
                    {
                        "name": "test-negative",
                        "query": "debug kubernetes",
                        "should_trigger": False,
                        "eval_mode": "behavioral",
                        "split": "test",
                    },
                ]
            }
        )
    )

    calls = []

    def fake_assess_target(
        path,
        tasks,
        goal,
        verbose=False,
        dry_run=False,
        behavioral_runs_per_task=1,
        behavioral_trigger_threshold=0.5,
        parallel_eval_workers=0,
        candidate_content=None,
        baseline_content=None,
        eval_mode="auto",
    ):
        calls.append(
            {
                "path": str(path),
                "task_count": len(tasks),
                "parallel_eval_workers": parallel_eval_workers,
                "candidate_content": candidate_content,
                "baseline_content": baseline_content,
                "eval_mode": eval_mode,
            }
        )
        return {
            "parses": True,
            "compiles": True,
            "tests_pass": True,
            "protected_intact": True,
            "correctness": 10.0,
            "error_handling": 8.0,
            "language_idioms": 7.0,
            "testing": 8.0,
            "efficiency": 6.0,
            "task_results": [{"name": "task", "passed": True}],
        }

    monkeypatch.setattr(optimize_loop, "assess_target", fake_assess_target)

    result = optimize_loop.run_optimization_loop(
        target_path=target,
        goal="improve routing precision",
        benchmark_tasks_path=tasks_file,
        max_iterations=1,
        min_gain=0.0,
        train_split=0.6,
        model=None,
        output_dir=tmp_path / "out",
        report_path=tmp_path / "out" / "report.html",
        verbose=False,
        dry_run=True,
        parallel_eval=2,
    )

    assert result["status"] in {"COMPLETE", "CONVERGED"}
    assert calls
    assert all(call["parallel_eval_workers"] == 2 for call in calls)
    assert all(call["candidate_content"] is not None for call in calls)
    assert any(call["baseline_content"] is not None for call in calls[1:])
    assert all(call["eval_mode"] == "auto" for call in calls)


def test_tiny_end_to_end_autoresearch_improves_real_weak_skill_copy(tmp_path, monkeypatch):
    optimize_loop = load_module(
        "agent_comparison_optimize_loop_e2e",
        "skills/agent-comparison/scripts/optimize_loop.py",
    )
    generate_variant = load_module(
        "agent_comparison_generate_variant_e2e",
        "skills/agent-comparison/scripts/generate_variant.py",
    )

    source_skill = REPO_ROOT / "skills" / "socratic-debugging" / "SKILL.md"
    target = tmp_path / "SKILL.md"
    target.write_text(source_skill.read_text())

    trigger_query = "help me think through this bug step by step"
    tasks_file = tmp_path / "tasks.json"
    tasks_file.write_text(
        json.dumps({"tasks": [{"name": "positive", "query": trigger_query, "should_trigger": True, "split": "train"}]})
    )

    def fake_generate_variant_output(
        current_content,
        target_path,
        goal,
        last_failures,
        history,
        model,
        dry_run,
        iteration_number,
        optimization_scope,
        diversification_note=None,
    ):
        improved_description = (
            "Question-only debugging mode that guides users to find root causes through structured questions. "
            f'Use when: "{trigger_query}", "rubber duck debug with me", "help me think through this bug".'
        )
        return {
            "variant": generate_variant.replace_description(current_content, improved_description),
            "summary": "Added exact positive trigger phrase to the description.",
            "reasoning": "Deterministic test variant",
            "tokens_used": 0,
            "deletions": [],
            "deletion_justification": "",
        }

    def fake_run_trigger_rate(
        target_path,
        description,
        tasks,
        candidate_content=None,
        eval_mode="auto",
        num_workers=5,
        timeout=30,
        verbose=False,
    ):
        passed = trigger_query in description
        return {
            "results": [
                {
                    "query": trigger_query,
                    "pass": passed,
                    "trigger_rate": 1.0 if passed else 0.0,
                }
            ],
            "summary": {
                "total": 1,
                "passed": 1 if passed else 0,
                "failed": 0 if passed else 1,
            },
        }

    monkeypatch.setattr(optimize_loop, "_generate_variant_output", fake_generate_variant_output)
    monkeypatch.setattr(optimize_loop, "_run_trigger_rate", fake_run_trigger_rate)

    out_dir = tmp_path / "out"
    result = optimize_loop.run_optimization_loop(
        target_path=target,
        goal="improve routing precision",
        benchmark_tasks_path=tasks_file,
        max_iterations=1,
        min_gain=0.0,
        train_split=0.6,
        model=None,
        output_dir=out_dir,
        report_path=out_dir / "report.html",
        verbose=False,
        dry_run=False,
    )

    assert result["best_iteration"] == 1
    assert result["improvements_found"] == 1
    assert result["baseline_train_score"] == 0.06
    assert result["best_score"] == 8.45

    results_json = json.loads((out_dir / "results.json").read_text())
    assert results_json["best_iteration"] == 1
    assert results_json["iterations"][0]["verdict"] == "ACCEPT"

    best_variant = (out_dir / "best_variant.md").read_text()
    assert trigger_query in generate_variant.extract_description(best_variant)

    verdict_json = json.loads((out_dir / "001" / "verdict.json").read_text())
    assert verdict_json["verdict"] == "ACCEPT"
    assert verdict_json["composite_score"] == 8.45
