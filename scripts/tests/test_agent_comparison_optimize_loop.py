import importlib.util
import json
from pathlib import Path
import sys


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
    original = (
        "alpha\n"
        "<!-- DO NOT OPTIMIZE -->\n"
        "keep me\n"
        "<!-- END DO NOT OPTIMIZE -->\n"
        "omega\n"
    )
    relocated = "alpha\nomega\n"

    assert optimize_loop.check_protected_sections(original, relocated) is False


def test_restore_protected_does_not_silently_reinsert_missing_blocks():
    generate_variant = load_module(
        "agent_comparison_generate_variant",
        "skills/agent-comparison/scripts/generate_variant.py",
    )
    original = (
        "alpha\n"
        "<!-- DO NOT OPTIMIZE -->\n"
        "keep me\n"
        "<!-- END DO NOT OPTIMIZE -->\n"
        "omega\n"
    )
    variant = "alpha\nomega\n"

    restored = generate_variant.restore_protected(original, variant)

    assert restored == variant


def test_generate_variant_main_reads_current_content_from_file(tmp_path, monkeypatch, capsys):
    generate_variant = load_module(
        "agent_comparison_generate_variant",
        "skills/agent-comparison/scripts/generate_variant.py",
    )

    class FakeBlock:
        def __init__(self, block_type: str, text: str):
            self.type = block_type
            if block_type == "thinking":
                self.thinking = text
            else:
                self.text = text

    class FakeResponse:
        def __init__(self):
            self.content = [
                FakeBlock("thinking", "reasoning"),
                FakeBlock(
                    "text",
                    "<variant>---\ndescription: updated\n---</variant>"
                    "<summary>updated</summary><deletion_justification></deletion_justification>",
                ),
            ]
            self.usage = type("Usage", (), {"input_tokens": 1, "output_tokens": 2})()

    class FakeClient:
        def __init__(self):
            self.messages = type("Messages", (), {"create": lambda self, **kwargs: FakeResponse()})()

    class FakeAnthropicModule:
        class Anthropic:
            def __new__(cls):
                return FakeClient()

    content_file = tmp_path / "current.md"
    content_file.write_text("---\ndescription: current\n---\n")

    monkeypatch.setattr(generate_variant, "anthropic", FakeAnthropicModule)
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
