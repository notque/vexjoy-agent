"""Contracts for repository-specific Go guidance and protected routing."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "programming" / "programming"


def test_programming_skill_scopes_sapcc_guidance_to_go_bits_repositories() -> None:
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    assert "references/sapcc-go.md" in skill
    assert "only when `go.mod` contains" in skill
    assert "`github.com/sapcc/go-bits`" in skill
    assert "Do not impose a universal command set" in skill


def test_sapcc_reference_preserves_version_specific_library_contracts() -> None:
    reference = (SKILL_DIR / "references" / "sapcc-go.md").read_text(encoding="utf-8")
    normalized = " ".join(reference.split())

    assert "go-bits commit `8b79638`" in reference
    assert "`assert.HTTPRequest{}.Check`" in reference
    assert "Migrate to `go-bits/httptest`" in normalized
    assert "commit `90af602`" in reference
    assert "`go-bits/assert` forwards to" in reference


def test_programming_skill_links_version_boundaries_and_requires_manifest_check() -> None:
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    boundaries = (SKILL_DIR / "references" / "version-boundaries.md").read_text(encoding="utf-8")
    normalized_skill = " ".join(skill.split())
    normalized_boundaries = " ".join(boundaries.split())

    assert "references/version-boundaries.md" in skill
    assert "Confirm the target version from the repository" in normalized_skill
    for version, feature in (
        ("1.22+", "iteration variables are per-iteration"),
        ("1.24+", "`testing.T.Context`"),
        ("1.25+", "`sync.WaitGroup.Go`"),
        ("1.26+", "`errors.AsType[T]`"),
    ):
        assert version in boundaries
        assert feature in boundaries
    assert "run tests under the minimum supported toolchain" in normalized_boundaries


def test_go_agent_requires_companion_skill_and_version_detection() -> None:
    agent = (ROOT / "agents" / "golang-general-engineer.md").read_text(encoding="utf-8")

    assert "Call the Skill tool with `programming`." in agent
    assert "Detect Go version from `go.mod`" in agent
    frontmatter = yaml.safe_load(agent.split("---", 2)[1])
    assert "Skill" in frontmatter["allowed-tools"]


def test_do_preserves_programming_stack_for_protected_go_operands() -> None:
    do_skill = (ROOT / "skills" / "meta" / "do" / "SKILL.md").read_text(encoding="utf-8")

    assert "protected git/security force routes" in do_skill
    assert "Keep stacks returned for protected language/domain\noperands." in do_skill
