#!/usr/bin/env python3
"""
Agent/Skill Evaluation Validation Script

Runs comprehensive quality checks on Claude Code agents and skills.
Returns structured results suitable for automated processing.

Usage:
    python validate.py                    # Evaluate all
    python validate.py --agents           # Evaluate agents only
    python validate.py --skills           # Evaluate skills only
    python validate.py --target NAME      # Evaluate specific item
    python validate.py --summary          # Collection summary only
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class EvaluationResult:
    """Result of evaluating a single agent or skill."""

    name: str
    item_type: str  # 'agent' or 'skill'
    structural_score: int = 0
    structural_max: int = 70
    depth_score: int = 0
    depth_max: int = 30
    total_lines: int = 0
    issues: list = field(default_factory=list)

    @property
    def total_score(self) -> int:
        return self.structural_score + self.depth_score

    @property
    def grade(self) -> str:
        score = self.total_score
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.item_type,
            "structural_score": self.structural_score,
            "depth_score": self.depth_score,
            "total_score": self.total_score,
            "total_lines": self.total_lines,
            "grade": self.grade,
            "issues": self.issues,
        }


def find_repo_root() -> Path:
    """Find the agents repository root."""
    current = Path.cwd()
    while current != current.parent:
        if (current / "agents").is_dir() and (current / "skills").is_dir():
            return current
        current = current.parent
    # Fallback: try ~/.claude or current directory
    claude_dir = Path.home() / ".claude"
    if (claude_dir / "agents").is_dir():
        return claude_dir
    # Last resort: assume current directory is repo root
    return Path.cwd()


def check_yaml_frontmatter(content: str, item_type: str) -> tuple[int, list]:
    """Check YAML front matter completeness. Returns (score, issues)."""
    score = 0
    issues = []

    # Check for YAML delimiters
    if not content.startswith("---"):
        issues.append(("HIGH", "Missing YAML front matter"))
        return 0, issues

    # Extract YAML block
    yaml_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not yaml_match:
        issues.append(("HIGH", "Malformed YAML front matter"))
        return 0, issues

    yaml_content = yaml_match.group(1)

    # Check required fields
    has_name = "name:" in yaml_content
    has_description = "description:" in yaml_content

    if item_type == "agent":
        has_color = "color:" in yaml_content
        if has_name and has_description and has_color:
            score = 10
        elif has_name and has_description:
            score = 7
            issues.append(("LOW", "Missing color field in YAML"))
        else:
            score = 3
            if not has_name:
                issues.append(("HIGH", "Missing name field in YAML"))
            if not has_description:
                issues.append(("HIGH", "Missing description field in YAML"))
    else:  # skill
        has_version = "version:" in yaml_content
        has_tools = "allowed-tools:" in yaml_content or "allowed_tools:" in yaml_content
        if has_name and has_description and has_version and has_tools:
            score = 10
        elif has_name and has_description:
            score = 5
            if not has_version:
                issues.append(("LOW", "Missing version field in YAML"))
            if not has_tools:
                issues.append(("MEDIUM", "Missing allowed-tools field in YAML"))
        else:
            score = 3
            issues.append(("HIGH", "Missing required YAML fields"))

    return score, issues


def check_operator_context(content: str) -> tuple[int, list]:
    """Check Operator Context section. Returns (score, issues)."""
    score = 0
    issues = []

    if "## Operator Context" not in content:
        issues.append(("HIGH", "Missing Operator Context section"))
        return 0, issues

    has_hardcoded = "### Hardcoded Behaviors" in content
    has_default = "### Default Behaviors" in content
    has_optional = "### Optional Behaviors" in content

    behavior_count = sum([has_hardcoded, has_default, has_optional])

    if behavior_count == 3:
        score = 20
    elif behavior_count == 2:
        score = 13
        issues.append(("MEDIUM", f"Missing behavior section (has {behavior_count}/3)"))
    elif behavior_count == 1:
        score = 7
        issues.append(("HIGH", f"Missing behavior sections (has {behavior_count}/3)"))
    else:
        issues.append(("HIGH", "Operator Context has no behavior sections"))

    return score, issues


def check_examples(content: str) -> tuple[int, list]:
    """Check examples in agent description. Returns (score, issues)."""
    score = 0
    issues = []

    example_count = content.count("<example>")

    if example_count >= 3:
        score = 10
    elif example_count == 2:
        score = 7
        issues.append(("LOW", f"Only {example_count} examples (3 recommended)"))
    elif example_count == 1:
        score = 4
        issues.append(("MEDIUM", "Only 1 example in description"))
    else:
        score = 0
        issues.append(("MEDIUM", "No examples in agent description"))

    return score, issues


def check_error_handling(content: str) -> tuple[int, list]:
    """Check Error Handling section. Returns (score, issues)."""
    score = 0
    issues = []

    if "## Error Handling" not in content and "## Error" not in content:
        issues.append(("MEDIUM", "Missing Error Handling section"))
        return 0, issues

    # Count error entries
    error_pattern = r'###\s+Error:|Error:\s*"'
    error_count = len(re.findall(error_pattern, content))

    if error_count >= 3:
        score = 10
    elif error_count >= 1:
        score = 6
        issues.append(("LOW", f"Only {error_count} errors documented"))
    else:
        score = 3
        issues.append(("MEDIUM", "Error Handling section is minimal"))

    return score, issues


def check_reference_files(skill_path: Path) -> tuple[int, list]:
    """Check skill reference files. Returns (score, issues)."""
    score = 0
    issues = []

    refs_dir = skill_path / "references"
    if not refs_dir.is_dir():
        issues.append(("MEDIUM", "Missing references directory"))
        return 0, issues

    ref_files = list(refs_dir.glob("*.md")) + list(refs_dir.glob("*.txt"))

    if len(ref_files) >= 2:
        # Check content
        total_lines = sum(len(f.read_text().splitlines()) for f in ref_files)
        if total_lines > 200:
            score = 10
        else:
            score = 7
            issues.append(("LOW", f"Reference files thin ({total_lines} lines)"))
    elif len(ref_files) == 1:
        score = 5
        issues.append(("MEDIUM", "Only 1 reference file"))
    else:
        issues.append(("MEDIUM", "No reference files in directory"))

    return score, issues


def check_validation_script(skill_path: Path) -> tuple[int, list]:
    """Check skill validation script. Returns (score, issues)."""
    score = 0
    issues = []

    script_path = skill_path / "scripts" / "validate.py"
    if not script_path.is_file():
        issues.append(("MEDIUM", "Missing validate.py script"))
        return 0, issues

    # Check Python syntax
    try:
        result = subprocess.run(
            ["python3", "-m", "py_compile", str(script_path)],
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            score = 10
        else:
            score = 3
            issues.append(("HIGH", "validate.py has syntax errors"))
    except Exception as e:
        score = 5
        issues.append(("MEDIUM", f"Could not check validate.py: {e}"))

    return score, issues


def calculate_depth_score(lines: int, item_type: str) -> tuple[int, str]:
    """Calculate depth score based on line count."""
    if item_type == "agent":
        if lines > 2500:
            return 30, "EXCELLENT"
        elif lines > 2000:
            return 27, "EXCELLENT"
        elif lines > 1500:
            return 24, "GOOD"
        elif lines > 1000:
            return 20, "GOOD"
        elif lines > 500:
            return 15, "ADEQUATE"
        elif lines > 300:
            return 10, "THIN"
        else:
            return 5, "INSUFFICIENT"
    else:  # skill
        if lines > 1500:
            return 30, "EXCELLENT"
        elif lines > 1000:
            return 27, "EXCELLENT"
        elif lines > 500:
            return 22, "GOOD"
        elif lines > 300:
            return 17, "ADEQUATE"
        elif lines > 150:
            return 12, "THIN"
        else:
            return 5, "INSUFFICIENT"


def evaluate_agent(agent_path: Path) -> EvaluationResult:
    """Evaluate a single agent."""
    name = agent_path.stem
    result = EvaluationResult(name=name, item_type="agent")

    try:
        content = agent_path.read_text()
    except Exception as e:
        result.issues.append(("HIGH", f"Cannot read file: {e}"))
        return result

    # Structural checks
    yaml_score, yaml_issues = check_yaml_frontmatter(content, "agent")
    result.structural_score += yaml_score
    result.issues.extend(yaml_issues)

    operator_score, operator_issues = check_operator_context(content)
    result.structural_score += operator_score
    result.issues.extend(operator_issues)

    example_score, example_issues = check_examples(content)
    result.structural_score += example_score
    result.issues.extend(example_issues)

    error_score, error_issues = check_error_handling(content)
    result.structural_score += error_score
    result.issues.extend(error_issues)

    # Depth check
    result.total_lines = len(content.splitlines())
    depth_score, _ = calculate_depth_score(result.total_lines, "agent")
    result.depth_score = depth_score

    # Adjust max for agents (no ref files or validate script)
    result.structural_max = 50

    return result


def evaluate_skill(skill_path: Path) -> EvaluationResult:
    """Evaluate a single skill."""
    name = skill_path.name
    result = EvaluationResult(name=name, item_type="skill")

    skill_file = skill_path / "SKILL.md"
    if not skill_file.is_file():
        result.issues.append(("HIGH", "Missing SKILL.md file"))
        return result

    try:
        content = skill_file.read_text()
    except Exception as e:
        result.issues.append(("HIGH", f"Cannot read SKILL.md: {e}"))
        return result

    # Structural checks
    yaml_score, yaml_issues = check_yaml_frontmatter(content, "skill")
    result.structural_score += yaml_score
    result.issues.extend(yaml_issues)

    operator_score, operator_issues = check_operator_context(content)
    result.structural_score += operator_score
    result.issues.extend(operator_issues)

    error_score, error_issues = check_error_handling(content)
    result.structural_score += error_score
    result.issues.extend(error_issues)

    ref_score, ref_issues = check_reference_files(skill_path)
    result.structural_score += ref_score
    result.issues.extend(ref_issues)

    validate_score, validate_issues = check_validation_script(skill_path)
    result.structural_score += validate_score
    result.issues.extend(validate_issues)

    # Depth check (include reference files)
    skill_lines = len(content.splitlines())
    ref_lines = 0
    refs_dir = skill_path / "references"
    if refs_dir.is_dir():
        for ref_file in refs_dir.glob("*.md"):
            ref_lines += len(ref_file.read_text().splitlines())

    result.total_lines = skill_lines + ref_lines
    depth_score, _ = calculate_depth_score(result.total_lines, "skill")
    result.depth_score = depth_score

    # Adjust max for skills (no examples section)
    result.structural_max = 60

    return result


def main():
    parser = argparse.ArgumentParser(description="Evaluate Claude Code agents and skills")
    parser.add_argument("--agents", action="store_true", help="Evaluate agents only")
    parser.add_argument("--skills", action="store_true", help="Evaluate skills only")
    parser.add_argument("--target", type=str, help="Evaluate specific item by name")
    parser.add_argument("--summary", action="store_true", help="Show collection summary only")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    repo_root = find_repo_root()
    agents_dir = repo_root / "agents"
    skills_dir = repo_root / "skills"

    results = []

    # Evaluate agents
    if not args.skills:
        for agent_file in sorted(agents_dir.glob("*.md")):
            if args.target and args.target not in agent_file.stem:
                continue
            result = evaluate_agent(agent_file)
            results.append(result)

    # Evaluate skills
    if not args.agents:
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            if args.target and args.target not in skill_dir.name:
                continue
            result = evaluate_skill(skill_dir)
            results.append(result)

    # Output results
    if args.json:
        output = {
            "timestamp": datetime.now().isoformat(),
            "results": [r.to_dict() for r in results],
            "summary": {
                "total": len(results),
                "agents": len([r for r in results if r.item_type == "agent"]),
                "skills": len([r for r in results if r.item_type == "skill"]),
                "average_score": sum(r.total_score for r in results) / len(results) if results else 0,
                "grade_distribution": {
                    "A": len([r for r in results if r.grade == "A"]),
                    "B": len([r for r in results if r.grade == "B"]),
                    "C": len([r for r in results if r.grade == "C"]),
                    "D": len([r for r in results if r.grade == "D"]),
                    "F": len([r for r in results if r.grade == "F"]),
                },
            },
        }
        print(json.dumps(output, indent=2))
    else:
        # Text output
        print("Agent/Skill Evaluation Report")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)
        print()

        if args.summary:
            # Summary only
            agents = [r for r in results if r.item_type == "agent"]
            skills = [r for r in results if r.item_type == "skill"]

            print(f"Agents: {len(agents)}")
            print(f"Skills: {len(skills)}")
            print(f"Average Score: {sum(r.total_score for r in results) / len(results):.1f}/100")
            print()

            print("Grade Distribution:")
            for grade in ["A", "B", "C", "D", "F"]:
                count = len([r for r in results if r.grade == grade])
                print(f"  {grade}: {count}")
        else:
            # Full results
            for result in results:
                # Normalize score to 100
                if result.item_type == "agent":
                    normalized = int((result.structural_score / 50 * 70) + result.depth_score)
                else:
                    normalized = int((result.structural_score / 60 * 70) + result.depth_score)

                print(f"{result.name} ({result.item_type})")
                print(f"  Score: {normalized}/100 ({result.grade})")
                print(f"  Lines: {result.total_lines}")

                if result.issues:
                    high_issues = [i for i in result.issues if i[0] == "HIGH"]
                    if high_issues:
                        print(f"  Issues: {len(high_issues)} HIGH priority")
                        for _priority, issue in high_issues[:2]:
                            print(f"    - {issue}")
                print()

        # Final summary
        print("=" * 60)
        passed = len([r for r in results if r.grade in ["A", "B"]])
        print(f"Quality Check: {passed}/{len(results)} passed (A or B grade)")

        return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
