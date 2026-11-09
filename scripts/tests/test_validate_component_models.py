from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "validate_component_models",
    _SCRIPTS_DIR / "validate_component_models.py",
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["validate_component_models"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "agents").mkdir(parents=True)
    (repo / "skills" / "process" / "workflow" / "references").mkdir(parents=True)
    return repo


def _agent(repo: Path, name: str, frontmatter: str) -> None:
    (repo / "agents" / f"{name}.md").write_text(f"---\nname: {name}\n{frontmatter}---\n", encoding="utf-8")


def _flagged(repo: Path, monkeypatch) -> dict[str, str]:
    monkeypatch.setattr(_mod, "REPO_ROOT", repo)
    return {v.component: v.issue for v in _mod.validate_models()}


def test_haiku_skill_is_flagged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    skill_dir = repo / "skills" / "demo" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nmodel: haiku\n---\n", encoding="utf-8")
    (repo / "agents").mkdir(parents=True)
    (repo / "skills" / "process" / "workflow" / "references").mkdir(parents=True)

    original_root = _mod.REPO_ROOT
    _mod.REPO_ROOT = repo
    try:
        violations = _mod.validate_models()
    finally:
        _mod.REPO_ROOT = original_root

    assert len(violations) == 1
    assert violations[0].component == "demo-skill"


def test_do_skill_is_exempt(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    do_dir = repo / "skills" / "meta" / "do"
    do_dir.mkdir(parents=True)
    (do_dir / "SKILL.md").write_text("---\nmodel: haiku\n---\n", encoding="utf-8")
    (repo / "agents").mkdir(parents=True)
    (repo / "skills" / "process" / "workflow" / "references").mkdir(parents=True)

    original_root = _mod.REPO_ROOT
    _mod.REPO_ROOT = repo
    try:
        violations = _mod.validate_models()
    finally:
        _mod.REPO_ROOT = original_root

    assert violations == []


def test_opus_and_inherit_are_allowed(tmp_path: Path, monkeypatch) -> None:
    repo = _make_repo(tmp_path)
    _agent(repo, "demo-agent", "model: opus\n")
    skill_dir = repo / "skills" / "demo" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nmodel: inherit\n---\n", encoding="utf-8")
    workflow_dir = repo / "skills" / "process" / "workflow" / "references"
    (workflow_dir / "demo-pipeline.md").write_text("---\nmodel: opus\n---\n", encoding="utf-8")

    assert _flagged(repo, monkeypatch) == {}


def test_fable_is_allowed(tmp_path: Path, monkeypatch) -> None:
    # Fable is the tier above Opus; it needs no read-only tool list.
    repo = _make_repo(tmp_path)
    _agent(repo, "lead", "model: fable\n")
    _agent(repo, "lead-writer", "model: fable\ntools: Read, Edit, Bash\n")

    assert _flagged(repo, monkeypatch) == {}


def test_sonnet_is_flagged_everywhere(tmp_path: Path, monkeypatch) -> None:
    # Owner policy 2026-11-01: Sonnet is no task's default, in any component class.
    repo = _make_repo(tmp_path)
    _agent(repo, "demo-agent", "model: sonnet\n")
    skill_dir = repo / "skills" / "demo" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nmodel: sonnet\n---\n", encoding="utf-8")
    workflow_dir = repo / "skills" / "process" / "workflow" / "references"
    (workflow_dir / "demo-pipeline.md").write_text("---\nmodel: sonnet\n---\n", encoding="utf-8")

    flagged = _flagged(repo, monkeypatch)

    assert set(flagged) == {"demo-agent", "demo-skill", "demo-pipeline"}
    assert all("sonnet" in issue for issue in flagged.values())


def test_haiku_is_allowed_on_a_read_only_agent(tmp_path: Path, monkeypatch) -> None:
    repo = _make_repo(tmp_path)
    _agent(repo, "scout-csv", "model: haiku\ntools: Read, Grep, Glob, WebFetch\n")
    _agent(repo, "scout-list", "model: haiku\ntools:\n  - Read\n  - Grep\n  - WebSearch\n")

    assert _flagged(repo, monkeypatch) == {}


def test_haiku_is_flagged_when_only_allowed_tools_lists_read_only_tools(tmp_path: Path, monkeypatch) -> None:
    # Claude Code ignores allowed-tools on agents and treats it as a grant on skills,
    # so a read-only allowed-tools list leaves Edit, Write, and Bash available.
    repo = _make_repo(tmp_path)
    _agent(repo, "scout-advisory", "model: haiku\nallowed-tools:\n  - Read\n  - Grep\n  - WebSearch\n")
    skill_dir = repo / "skills" / "demo" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nmodel: haiku\nallowed-tools: Read, Grep\n---\n", encoding="utf-8")

    flagged = _flagged(repo, monkeypatch)

    assert set(flagged) == {"scout-advisory", "demo-skill"}
    assert all("allowed-tools" in issue for issue in flagged.values())


def test_haiku_is_flagged_on_an_agent_that_can_write(tmp_path: Path, monkeypatch) -> None:
    repo = _make_repo(tmp_path)
    _agent(repo, "editor", "model: haiku\ntools: Read, Edit\n")
    _agent(repo, "writer", "model: haiku\ntools:\n  - Read\n  - Write\n")
    _agent(repo, "shell", "model: haiku\ntools: Read, Bash(git diff:*)\n")
    _agent(repo, "notebook", "model: haiku\ntools: [Read, NotebookEdit]\n")
    # A subagent started through Agent or Task can write, so those count too.
    _agent(repo, "delegator", "model: haiku\ntools: Read, Agent\n")
    _agent(repo, "tasker", "model: haiku\ntools: Read, Task\n")

    flagged = _flagged(repo, monkeypatch)

    assert set(flagged) == {"editor", "writer", "shell", "notebook", "delegator", "tasker"}
    assert "read-only" in flagged["editor"]
    assert "Agent" in flagged["delegator"]


def test_haiku_is_flagged_when_no_tool_list_limits_the_agent(tmp_path: Path, monkeypatch) -> None:
    # No tools list means the agent inherits every tool, including Edit and Write.
    repo = _make_repo(tmp_path)
    _agent(repo, "inherits-all", "model: haiku\n")

    assert set(_flagged(repo, monkeypatch)) == {"inherits-all"}


def test_unknown_model_is_flagged(tmp_path: Path, monkeypatch) -> None:
    repo = _make_repo(tmp_path)
    _agent(repo, "odd", "model: gpt-4o\n")

    assert set(_flagged(repo, monkeypatch)) == {"odd"}


def test_exempt_component_may_pin_any_model(tmp_path: Path, monkeypatch) -> None:
    repo = _make_repo(tmp_path)
    _agent(repo, "legacy", "model: sonnet\n")
    monkeypatch.setattr(_mod, "EXEMPT_COMPONENTS", {("agent", "legacy")})

    assert _flagged(repo, monkeypatch) == {}


def test_image_gen_skill_is_exempt(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    skill_dir = repo / "skills" / "content" / "image-gen"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nmodel: gemini-3-pro-image-preview\n---\n", encoding="utf-8")

    original_root = _mod.REPO_ROOT
    _mod.REPO_ROOT = repo
    try:
        violations = _mod.validate_models()
    finally:
        _mod.REPO_ROOT = original_root

    assert violations == []


def test_main_fails_when_a_target_class_finds_no_files(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    (repo / "agents").mkdir(parents=True)
    (repo / "skills").mkdir()
    monkeypatch.setattr(_mod, "REPO_ROOT", repo)
    monkeypatch.setattr(sys, "argv", ["validate_component_models.py"])

    assert _mod.main() == 2


_WORKFLOW_DIR = Path("skills") / "process" / "workflow" / "references"


def _script(repo: Path, relative: str, body: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _script_hits(repo: Path, monkeypatch) -> list[tuple[str, int | None, str]]:
    monkeypatch.setattr(_mod, "REPO_ROOT", repo)
    return [(v.file, v.line, v.issue) for v in _mod.validate_models() if v.component_type == "dispatch_script"]


def test_workflow_script_literal_model_is_flagged_with_its_line(tmp_path: Path, monkeypatch) -> None:
    # The frontmatter-only scan passed six workflow scripts that held 32 `model: "sonnet"`.
    repo = _make_repo(tmp_path)
    _script(
        repo,
        str(_WORKFLOW_DIR / "demo-workflow.js"),
        'export async function run() {\n  await agent({\n    prompt: "p",\n    model: "sonnet",\n  });\n}\n',
    )

    hits = _script_hits(repo, monkeypatch)

    assert [(file, line) for file, line, _ in hits] == [(str(_WORKFLOW_DIR / "demo-workflow.js"), 4)]
    assert "'sonnet'" in hits[0][2]
    assert "modelFor" in hits[0][2]


def test_every_literal_model_form_is_flagged_even_an_allowed_model(tmp_path: Path, monkeypatch) -> None:
    # The rule is "no literal", not "no sonnet": opus and fable literals fail too.
    repo = _make_repo(tmp_path)
    _script(
        repo,
        str(_WORKFLOW_DIR / "forms.mjs"),
        "\n".join(
            [
                'agent({ model: "opus" });',
                "agent({ model: 'fable' });",
                "agent({ model: `haiku` });",
                'const model = "inherit";',
                'agent({ model: deep ? "opus" : "haiku" });',
                'const TIERS = ["sonnet", "claude-opus-5-5", "opus[1m]"];',
                'agent({ model: "gpt-4o" });',
            ]
        )
        + "\n",
    )

    found = {(line, issue.split("'")[1]) for _, line, issue in _script_hits(repo, monkeypatch)}

    assert found == {
        (1, "opus"),
        (2, "fable"),
        (3, "haiku"),
        (4, "inherit"),
        (5, "opus"),
        (5, "haiku"),
        (6, "sonnet"),
        (6, "claude-opus-5-5"),
        (6, "opus[1m]"),
        (7, "gpt-4o"),
    }


def test_model_from_helper_and_prose_are_not_flagged(tmp_path: Path, monkeypatch) -> None:
    repo = _make_repo(tmp_path)
    _script(
        repo,
        str(_WORKFLOW_DIR / "clean.js"),
        "\n".join(
            [
                'import { modelFor } from "./workflow-helpers.js";',
                '// gather runs on "haiku"; model: "sonnet" was the old pin',
                '/* work -> "opus"',
                '   lead -> model: "fable" */',
                "export async function run({ modelOverride }) {",
                '  await agent({ prompt: "Use opus-grade care; see https://example.test/x", model: modelFor("work", modelOverride) });',
                '  await agent({ prompt: `magnum opus // not a comment`, model: modelFor("gather", modelOverride) });',
                '  const model = modelFor("lead", modelOverride);',
                "  await agent({ model });",
                "}",
            ]
        )
        + "\n",
    )

    assert _script_hits(repo, monkeypatch) == []


def test_literal_after_a_comment_keeps_its_line_number(tmp_path: Path, monkeypatch) -> None:
    repo = _make_repo(tmp_path)
    _script(
        repo,
        str(_WORKFLOW_DIR / "late.js"),
        '/* two\n   lines */\nconst url = "https://example.test"; // note\nagent({ model: "sonnet" });\n',
    )

    assert [line for _, line, _ in _script_hits(repo, monkeypatch)] == [4]


def test_workflow_helpers_is_the_one_script_that_may_name_models(tmp_path: Path, monkeypatch) -> None:
    repo = _make_repo(tmp_path)
    table = 'const MODELS = { gather: "haiku", work: "opus" };\n'
    _script(repo, str(_WORKFLOW_DIR / "workflow-helpers.js"), table)
    # The same file name elsewhere gets no pass.
    _script(repo, "skills/demo/demo-skill/scripts/workflow-helpers.js", table + "agent({});\n")

    hits = _script_hits(repo, monkeypatch)

    assert {file for file, _, _ in hits} == {"skills/demo/demo-skill/scripts/workflow-helpers.js"}


def test_scripts_outside_the_workflow_dir_are_scanned_only_when_they_dispatch(tmp_path: Path, monkeypatch) -> None:
    repo = _make_repo(tmp_path)
    _script(repo, "skills/demo/demo-skill/scripts/dispatch.mjs", 'await agent({ model: "sonnet" });\n')
    _script(repo, "agents/demo-agent/scripts/dispatch.js", "await agent ({ model: 'haiku' });\n")
    # No agent() call: an image or 3D model name is not a Claude dispatch.
    _script(repo, "skills/demo/demo-skill/scripts/render.mjs", 'fetch(url, { model: "meshy-5" });\n')
    _script(repo, "skills/demo/demo-skill/node_modules/dep/index.js", 'agent({ model: "sonnet" });\n')

    hits = _script_hits(repo, monkeypatch)

    assert {file for file, _, _ in hits} == {
        "skills/demo/demo-skill/scripts/dispatch.mjs",
        "agents/demo-agent/scripts/dispatch.js",
    }


def test_main_exits_1_and_prints_file_and_line_for_a_script_literal(tmp_path: Path, monkeypatch, capsys) -> None:
    repo = _make_repo(tmp_path)
    _agent(repo, "demo-agent", "model: opus\n")
    skill_dir = repo / "skills" / "demo" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo-skill\n---\n", encoding="utf-8")
    (repo / _WORKFLOW_DIR / "demo-pipeline.md").write_text("---\nname: demo-pipeline\n---\n", encoding="utf-8")
    _script(repo, str(_WORKFLOW_DIR / "demo-workflow.js"), 'agent({\n  model: "sonnet",\n});\n')
    monkeypatch.setattr(_mod, "REPO_ROOT", repo)
    monkeypatch.setattr(sys, "argv", ["validate_component_models.py"])

    assert _mod.main() == 1
    assert f"{_WORKFLOW_DIR / 'demo-workflow.js'}:2: literal model string 'sonnet'" in capsys.readouterr().out

    _script(repo, str(_WORKFLOW_DIR / "demo-workflow.js"), 'agent({\n  model: modelFor("work", modelOverride),\n});\n')

    assert _mod.main() == 0


def test_main_fails_when_no_dispatch_script_is_found(tmp_path: Path, monkeypatch, capsys) -> None:
    # A moved workflow directory must not turn the script scan into a silent pass.
    repo = _make_repo(tmp_path)
    _agent(repo, "demo-agent", "model: opus\n")
    skill_dir = repo / "skills" / "demo" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo-skill\n---\n", encoding="utf-8")
    (repo / _WORKFLOW_DIR / "demo-pipeline.md").write_text("---\nname: demo-pipeline\n---\n", encoding="utf-8")
    monkeypatch.setattr(_mod, "REPO_ROOT", repo)
    monkeypatch.setattr(sys, "argv", ["validate_component_models.py"])

    assert _mod.main() == 2
    assert "dispatch_script" in capsys.readouterr().err
