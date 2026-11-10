"""Tests for scripts/audit-tool-restrictions.py: which agents count as missing allowed-tools."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "audit-tool-restrictions.py"
_spec = importlib.util.spec_from_file_location("audit_tool_restrictions", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
audit = importlib.util.module_from_spec(_spec)
sys.modules["audit_tool_restrictions"] = audit
_spec.loader.exec_module(audit)

REPO_AGENTS = SCRIPT_PATH.parent.parent / "agents"


def write_agent(agents: Path, name: str, *, tools: bool, named: bool = True) -> Path:
    lines = ["---"]
    if named:
        lines.append(f"name: {name}")
    lines.append("description: test agent")
    if tools:
        lines += ["allowed-tools:", "  - Read"]
    lines += ["---", "", "Body.", ""]
    path = agents / f"{name}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_agent_outside_the_role_table_passes_when_it_declares_tools(tmp_path: Path, capsys) -> None:
    write_agent(tmp_path, "brand-new-engineer", tools=True)

    assert "brand-new-engineer" not in audit.AGENT_ROLES
    assert audit.audit(tmp_path) == 0
    assert "OK: brand-new-engineer" in capsys.readouterr().out


def test_agent_without_tools_is_reported_whether_or_not_it_has_a_role(tmp_path: Path, capsys) -> None:
    write_agent(tmp_path, "brand-new-engineer", tools=False)
    write_agent(tmp_path, "golang-general-engineer", tools=False)

    assert audit.audit(tmp_path) == 2
    out = capsys.readouterr().out
    assert "MISSING: brand-new-engineer — no allowed-tools and no role in AGENT_ROLES" in out
    assert "MISSING: golang-general-engineer — needs code-modifier tools" in out


def test_file_without_a_frontmatter_name_is_skipped(tmp_path: Path, capsys) -> None:
    (tmp_path / "base-instructions.md").write_text("# Shared instructions\n", encoding="utf-8")
    write_agent(tmp_path, "nameless", tools=False, named=False)

    assert audit.audit(tmp_path) == 0
    assert "SKIP: base-instructions" in capsys.readouterr().out


def test_fix_adds_tools_for_a_known_role_and_leaves_an_unknown_agent(tmp_path: Path) -> None:
    known = write_agent(tmp_path, "golang-general-engineer", tools=False)
    unknown = write_agent(tmp_path, "brand-new-engineer", tools=False)
    before = unknown.read_text(encoding="utf-8")

    assert audit.audit(tmp_path, fix=True) == 1
    assert audit.has_allowed_tools(known.read_text(encoding="utf-8"))
    assert unknown.read_text(encoding="utf-8") == before


def test_every_repo_agent_passes_the_audit() -> None:
    assert audit.audit(REPO_AGENTS) == 0


def test_every_role_lists_the_skill_tool() -> None:
    # Agents load their paired skills through the Skill tool, so --fix must add it.
    assert [role for role, tools in audit.ROLE_TOOLS.items() if "Skill" not in tools] == []


def test_fix_adds_the_skill_tool(tmp_path: Path) -> None:
    agent = write_agent(tmp_path, "golang-general-engineer", tools=False)

    assert audit.audit(tmp_path, fix=True) == 1
    assert "  - Skill\n" in agent.read_text(encoding="utf-8")


def test_role_table_names_only_agents_on_disk_and_known_roles() -> None:
    on_disk = {path.stem for path in REPO_AGENTS.glob("*.md")}

    assert sorted(set(audit.AGENT_ROLES) - on_disk) == []
    assert sorted(set(audit.AGENT_ROLES.values()) - set(audit.ROLE_TOOLS)) == []
