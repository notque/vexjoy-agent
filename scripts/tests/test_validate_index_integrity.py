"""CLI positive and negative tests for scripts/validate-index-integrity.py.

Every test builds a synthetic repository under ``tmp_path`` with an isolated
``HOME`` so host ``~/.claude`` overlays never leak in.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "validate-index-integrity.py"
INDEX_FRESHNESS = REPO_ROOT / "scripts" / "lib" / "index_freshness.py"


def _make_repo(tmp_path: Path) -> Path:
    """Create a minimal passing repository fixture with all pinned core triggers."""
    repo = tmp_path / "repo"
    (repo / "scripts" / "lib").mkdir(parents=True)
    shutil.copy2(SCRIPT, repo / "scripts" / "validate-index-integrity.py")
    shutil.copy2(INDEX_FRESHNESS, repo / "scripts" / "lib" / "index_freshness.py")

    skills = {
        "pr-workflow": {
            "file": "skills/process/pr-workflow/SKILL.md",
            "triggers": [
                "create pull request",
                "push my changes",
                "stage and commit",
                "open pull request",
                "commit changes",
            ],
        },
        "workflow-help": {
            "file": "skills/process/workflow-help/SKILL.md",
            "triggers": [
                "I am stuck",
                "workflow help",
                "next step",
                "help me choose",
                "guide me",
            ],
        },
        "systematic-debugging": {
            "file": "skills/process/systematic-debugging/SKILL.md",
            "triggers": [
                "why is this broken",
                "debug",
                "root cause analysis",
                "investigate failure",
                "trace bug",
            ],
        },
        "systematic-refactoring": {
            "file": "skills/process/systematic-refactoring/SKILL.md",
            "triggers": [
                "simplify this",
                "refactor code",
                "clean up module",
                "reduce complexity",
                "extract helper",
            ],
        },
    }

    for name, entry in skills.items():
        skill_md = repo / entry["file"]
        skill_md.parent.mkdir(parents=True, exist_ok=True)
        skill_md.write_text(f"---\nname: {name}\n---\n# {name}\n", encoding="utf-8")

    (repo / "skills" / "INDEX.json").write_text(
        json.dumps({"skills": skills}, indent=2),
        encoding="utf-8",
    )

    (repo / "agents").mkdir(parents=True, exist_ok=True)
    (repo / "agents" / "INDEX.json").write_text(
        json.dumps({"agents": {}}, indent=2),
        encoding="utf-8",
    )

    pipeline_path = repo / "skills" / "process" / "workflow" / "references" / "pipeline-index.json"
    pipeline_path.parent.mkdir(parents=True, exist_ok=True)
    pipeline_path.write_text(
        json.dumps(
            {
                "pipelines": {
                    "comprehensive-review": {
                        "triggers": [
                            "full code review",
                            "deep code audit",
                            "full repo review",
                            "comprehensive audit",
                            "multi-agent review",
                        ]
                    }
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return repo


def _run(repo: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    script = repo / "scripts" / "validate-index-integrity.py"
    fake_home = tmp_path / "home"
    fake_home.mkdir(exist_ok=True)
    env = {**os.environ, "HOME": str(fake_home), "USERPROFILE": str(fake_home)}
    return subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(repo),
        env=env,
        timeout=60,
    )


def test_valid_index_exits_zero(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    result = _run(repo, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "VERDICT: PASS" in result.stdout


def test_promoted_husk_not_in_index_exits_zero(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    husk = repo / "skills" / "process" / "retired-husk" / "SKILL.md"
    husk.parent.mkdir(parents=True)
    husk.write_text("---\nname: retired-husk\npromoted_to: pr-workflow\n---\n", encoding="utf-8")

    result = _run(repo, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_skill_file_exits_one(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "skills" / "process" / "pr-workflow" / "SKILL.md").unlink()

    result = _run(repo, tmp_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "[skill missing file]" in result.stdout


def test_unindexed_skill_on_disk_exits_one(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    orphan = repo / "skills" / "process" / "orphan-skill" / "SKILL.md"
    orphan.parent.mkdir(parents=True)
    orphan.write_text("---\nname: orphan-skill\n---\n# Orphan\n", encoding="utf-8")

    result = _run(repo, tmp_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "[skill not indexed]" in result.stdout


def test_zero_and_duplicate_triggers_exit_one(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    idx_path = repo / "skills" / "INDEX.json"
    data = json.loads(idx_path.read_text(encoding="utf-8"))
    data["skills"]["workflow-help"]["triggers"] = []
    data["skills"]["pr-workflow"]["triggers"].append("create pull request")
    idx_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    result = _run(repo, tmp_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "[zero triggers]" in result.stdout
    assert "[duplicate triggers]" in result.stdout


def test_missing_pinned_trigger_exits_one(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    idx_path = repo / "skills" / "INDEX.json"
    data = json.loads(idx_path.read_text(encoding="utf-8"))
    data["skills"]["systematic-debugging"]["triggers"] = [
        "root cause analysis",
        "investigate failure",
        "trace bug",
        "diagnose crash",
        "fix regression",
    ]
    idx_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    result = _run(repo, tmp_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "pinned core route" in result.stdout


def test_agent_rename_damage_exits_one(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    agent_md = repo / "agents" / "bad-agent.md"
    agent_md.write_text("# Bad Agent\n", encoding="utf-8")
    (repo / "agents" / "INDEX.json").write_text(
        json.dumps(
            {
                "agents": {
                    "bad-agent": {
                        "file": "agents/bad-agent.md",
                        "triggers": [
                            "programming-python",
                            "write code",
                            "review patch",
                            "fix test",
                            "build tool",
                        ],
                    }
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = _run(repo, tmp_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "[rename damage]" in result.stdout
