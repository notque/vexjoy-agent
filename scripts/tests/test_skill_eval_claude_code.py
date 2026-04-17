from __future__ import annotations

import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path


def test_improve_description_uses_claude_code_and_shortens(monkeypatch, tmp_path):
    from scripts.skill_eval import improve_description as mod

    calls: list[list[str]] = []

    def fake_run(cmd, capture_output, text, cwd, env, timeout):
        calls.append(cmd)
        if len(calls) == 1:
            text_out = "<new_description>" + ("a" * 1030) + "</new_description>"
        else:
            text_out = "<new_description>short and valid</new_description>"
        payload = [
            {"type": "assistant", "message": {"content": [{"type": "text", "text": text_out}]}},
            {"type": "result", "result": "raw result"},
        ]
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    description = mod.improve_description(
        skill_name="skill-eval",
        skill_content="# Skill",
        current_description="old",
        eval_results={
            "results": [
                {"query": "improve this skill", "should_trigger": True, "pass": False, "triggers": 0, "runs": 1}
            ],
            "summary": {"passed": 0, "failed": 1, "total": 1},
        },
        history=[],
        model=None,
        log_dir=tmp_path,
        iteration=1,
    )

    assert description == "short and valid"
    assert calls
    assert calls[0][:2] == ["claude", "-p"]
    transcript = json.loads((tmp_path / "improve_iter_1.json").read_text())
    assert transcript["raw_result_text"] == "raw result"
    assert transcript["rewrite_raw_result_text"] == "raw result"


class _FakeUUID:
    hex = "deadbeefcafebabe"


class _FakePopen:
    def __init__(self, stdout_bytes: bytes):
        read_fd, write_fd = os.pipe()
        os.write(write_fd, stdout_bytes)
        os.close(write_fd)
        self.stdout = os.fdopen(read_fd, "rb", buffering=0)
        self._returncode = None

    def poll(self):
        return self._returncode

    def kill(self):
        self._returncode = -9

    def wait(self):
        return self._returncode


def test_run_single_query_ignores_unrelated_stream_tool_use_before_matching_read(monkeypatch, tmp_path):
    from scripts.skill_eval import run_eval as mod

    clean_name = "demo-skill-skill-deadbeef"
    stream_lines = [
        {
            "type": "stream_event",
            "event": {"type": "content_block_start", "content_block": {"type": "tool_use", "name": "Bash"}},
        },
        {
            "type": "stream_event",
            "event": {"type": "content_block_start", "content_block": {"type": "tool_use", "name": "Read"}},
        },
        {
            "type": "stream_event",
            "event": {
                "type": "content_block_delta",
                "delta": {
                    "type": "input_json_delta",
                    "partial_json": f'{{"file_path":"/tmp/project/.claude/commands/{clean_name}.md"}}',
                },
            },
        },
        {"type": "stream_event", "event": {"type": "content_block_stop"}},
        {"type": "result"},
    ]
    payload = ("\n".join(json.dumps(line) for line in stream_lines) + "\n").encode()

    monkeypatch.setattr(mod.uuid, "uuid4", lambda: _FakeUUID())
    monkeypatch.setattr(mod.subprocess, "Popen", lambda *_args, **_kwargs: _FakePopen(payload))
    monkeypatch.setattr(mod.select, "select", lambda readables, *_args: (readables, [], []))

    triggered = mod.run_single_query(
        query="help me debug this",
        skill_name="demo-skill",
        skill_description="demo description",
        timeout=5,
        project_root=str(tmp_path),
        eval_mode="registered",
    )

    assert triggered is True


def test_run_single_query_scans_all_assistant_tool_uses_before_returning(monkeypatch, tmp_path):
    from scripts.skill_eval import run_eval as mod

    clean_name = "demo-skill-skill-deadbeef"
    assistant_lines = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Bash", "input": {"command": "echo hi"}},
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {"file_path": f"/tmp/project/.claude/commands/{clean_name}.md"},
                    },
                ]
            },
        },
        {"type": "result"},
    ]
    payload = ("\n".join(json.dumps(line) for line in assistant_lines) + "\n").encode()

    monkeypatch.setattr(mod.uuid, "uuid4", lambda: _FakeUUID())
    monkeypatch.setattr(mod.subprocess, "Popen", lambda *_args, **_kwargs: _FakePopen(payload))
    monkeypatch.setattr(mod.select, "select", lambda readables, *_args: (readables, [], []))

    triggered = mod.run_single_query(
        query="help me debug this",
        skill_name="demo-skill",
        skill_description="demo description",
        timeout=5,
        project_root=str(tmp_path),
        eval_mode="registered",
    )

    assert triggered is True


def test_run_single_query_accepts_real_skill_name_not_just_temporary_alias(monkeypatch, tmp_path):
    from scripts.skill_eval import run_eval as mod

    assistant_lines = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Skill",
                        "input": {"skill": "demo-skill"},
                    }
                ]
            },
        },
        {"type": "result"},
    ]
    payload = ("\n".join(json.dumps(line) for line in assistant_lines) + "\n").encode()

    monkeypatch.setattr(mod.uuid, "uuid4", lambda: _FakeUUID())
    monkeypatch.setattr(mod.subprocess, "Popen", lambda *_args, **_kwargs: _FakePopen(payload))
    monkeypatch.setattr(mod.select, "select", lambda readables, *_args: (readables, [], []))

    triggered = mod.run_single_query(
        query="help me debug this",
        skill_name="demo-skill",
        skill_description="demo description",
        timeout=5,
        project_root=str(tmp_path),
        eval_mode="registered",
    )

    assert triggered is True


def test_resolve_registered_skill_relpath_accepts_repo_skill(tmp_path):
    from scripts.skill_eval import run_eval as mod

    project_root = tmp_path
    skill_dir = project_root / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo-skill\ndescription: demo\n---\n")

    relpath = mod.resolve_registered_skill_relpath(skill_dir, project_root)

    assert relpath == Path("skills/demo-skill/SKILL.md")


def test_replace_description_in_skill_md_rewrites_frontmatter_block_scalar():
    from scripts.skill_eval import run_eval as mod

    original = """---
name: demo-skill
description: |
  old description
version: 1.0.0
---

# Skill
"""

    updated = mod.replace_description_in_skill_md(original, "new description line 1\nnew description line 2")

    assert "description: |\n  new description line 1\n  new description line 2\nversion: 1.0.0" in updated
    assert "# Skill" in updated


def test_load_eval_set_accepts_common_wrapped_formats(tmp_path):
    from scripts.skill_eval import run_eval as mod

    tasks_path = tmp_path / "tasks.json"
    tasks_path.write_text(json.dumps({"tasks": [{"query": "q1", "should_trigger": True}]}))
    queries_path = tmp_path / "queries.json"
    queries_path.write_text(json.dumps({"queries": [{"query": "q2", "should_trigger": False}]}))
    split_path = tmp_path / "split.json"
    split_path.write_text(
        json.dumps(
            {
                "train": [{"query": "q3", "should_trigger": True}],
                "test": [{"query": "q4", "should_trigger": False}],
            }
        )
    )

    assert mod.load_eval_set(tasks_path) == [{"query": "q1", "should_trigger": True}]
    assert mod.load_eval_set(queries_path) == [{"query": "q2", "should_trigger": False}]
    assert mod.load_eval_set(split_path) == [
        {"query": "q3", "should_trigger": True},
        {"query": "q4", "should_trigger": False},
    ]


def test_run_eval_auto_uses_registered_worktree_for_repo_skill(monkeypatch, tmp_path):
    from scripts.skill_eval import run_eval as mod

    skill_dir = tmp_path / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo-skill\ndescription: demo\n---\n")
    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()

    seen = {"candidate_content": None, "submitted": []}

    @contextmanager
    def fake_candidate_worktree(project_root, registered_skill_relpath, candidate_content):
        seen["candidate_content"] = candidate_content
        seen["registered_skill_relpath"] = registered_skill_relpath
        yield worktree_root

    class _FakeFuture:
        def __init__(self, value):
            self._value = value

        def result(self):
            return self._value

    class _FakeExecutor:
        def __init__(self, max_workers):
            self.max_workers = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, *args):
            seen["submitted"].append(args)
            return _FakeFuture(True)

    monkeypatch.setattr(mod, "candidate_worktree", fake_candidate_worktree)
    monkeypatch.setattr(mod, "ProcessPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(mod, "as_completed", lambda futures: list(futures))

    result = mod.run_eval(
        eval_set=[{"query": "help me debug this", "should_trigger": True}],
        skill_name="demo-skill",
        description="demo description",
        num_workers=1,
        timeout=5,
        project_root=tmp_path,
        eval_mode="auto",
        skill_path=skill_dir,
        candidate_content="candidate body",
    )

    assert seen["candidate_content"] == "candidate body"
    assert seen["registered_skill_relpath"] == Path("skills/demo-skill/SKILL.md")
    assert seen["submitted"]
    _, _, _, _, submitted_project_root, submitted_eval_mode, _ = seen["submitted"][0]
    assert submitted_project_root == str(worktree_root)
    assert submitted_eval_mode == "registered"
    assert result["summary"]["passed"] == 1


def test_run_eval_registered_mode_patches_candidate_from_description_override(monkeypatch, tmp_path):
    from scripts.skill_eval import run_eval as mod

    skill_dir = tmp_path / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    original_content = """---
name: demo-skill
description: old description
version: 1.0.0
---

# Skill
"""
    (skill_dir / "SKILL.md").write_text(original_content)
    seen = {"candidate_content": None}

    @contextmanager
    def fake_candidate_worktree(project_root, registered_skill_relpath, candidate_content):
        seen["candidate_content"] = candidate_content
        yield tmp_path / "worktree"

    class _FakeFuture:
        def __init__(self, value):
            self._value = value

        def result(self):
            return self._value

    class _FakeExecutor:
        def __init__(self, max_workers):
            self.max_workers = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, *args):
            return _FakeFuture(True)

    monkeypatch.setattr(mod, "candidate_worktree", fake_candidate_worktree)
    monkeypatch.setattr(mod, "ProcessPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(mod, "as_completed", lambda futures: list(futures))

    mod.run_eval(
        eval_set=[{"query": "help me debug this", "should_trigger": True}],
        skill_name="demo-skill",
        description="new description",
        num_workers=1,
        timeout=5,
        project_root=tmp_path,
        eval_mode="registered",
        skill_path=skill_dir,
        candidate_content=None,
    )

    assert seen["candidate_content"] is not None
    assert "description: |\n  new description\nversion: 1.0.0" in seen["candidate_content"]


def test_run_eval_registered_mode_patches_current_working_copy_when_no_override(monkeypatch, tmp_path):
    from scripts.skill_eval import run_eval as mod

    skill_dir = tmp_path / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    original_content = """---
name: demo-skill
description: current working copy description
version: 1.0.0
---

# Skill
"""
    (skill_dir / "SKILL.md").write_text(original_content)
    seen = {"candidate_content": None}

    @contextmanager
    def fake_candidate_worktree(project_root, registered_skill_relpath, candidate_content):
        seen["candidate_content"] = candidate_content
        yield tmp_path / "worktree"

    class _FakeFuture:
        def __init__(self, value):
            self._value = value

        def result(self):
            return self._value

    class _FakeExecutor:
        def __init__(self, max_workers):
            self.max_workers = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, *args):
            return _FakeFuture(True)

    monkeypatch.setattr(mod, "candidate_worktree", fake_candidate_worktree)
    monkeypatch.setattr(mod, "ProcessPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(mod, "as_completed", lambda futures: list(futures))

    mod.run_eval(
        eval_set=[{"query": "help me debug this", "should_trigger": True}],
        skill_name="demo-skill",
        description="current working copy description",
        num_workers=1,
        timeout=5,
        project_root=tmp_path,
        eval_mode="registered",
        skill_path=skill_dir,
        candidate_content=None,
    )

    assert seen["candidate_content"] == original_content


def test_run_eval_auto_falls_back_to_alias_for_non_registered_skill(monkeypatch, tmp_path):
    from scripts.skill_eval import run_eval as mod

    skill_dir = tmp_path / "scratch" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo-skill\ndescription: demo\n---\n")

    seen_submissions = []

    class _FakeFuture:
        def __init__(self, value):
            self._value = value

        def result(self):
            return self._value

    class _FakeExecutor:
        def __init__(self, max_workers):
            self.max_workers = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, *args):
            seen_submissions.append(args)
            return _FakeFuture(False)

    monkeypatch.setattr(mod, "ProcessPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(mod, "as_completed", lambda futures: list(futures))

    result = mod.run_eval(
        eval_set=[{"query": "help me debug this", "should_trigger": True}],
        skill_name="demo-skill",
        description="demo description",
        num_workers=1,
        timeout=5,
        project_root=tmp_path,
        eval_mode="auto",
        skill_path=skill_dir,
    )

    assert seen_submissions
    _, _, _, _, submitted_project_root, submitted_eval_mode, _ = seen_submissions[0]
    assert submitted_project_root == str(tmp_path)
    assert submitted_eval_mode == "alias"
    assert result["summary"]["passed"] == 0
