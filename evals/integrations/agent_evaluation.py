#!/usr/bin/env python3
"""
Agent Assessment Integration

Bridges the harness with the agent-assessment skill's 100-point scoring system.
Uses the same rubric structure defined in skills/agent-evaluation/SKILL.md.

The scoring system:
- Structural Validation: 70 points
  - YAML front matter: 10 points
  - Operator Context: 20 points
  - Examples: 10 points
  - Error Handling: 10 points
  - Reference Files: 10 points (skills only)
  - Validation Script: 10 points (skills only)
- Content Depth: 30 points
  - >2000 lines: 30/30 (EXCELLENT)
  - 1000-2000: 25/30 (GOOD)
  - 500-1000: 20/30 (ADEQUATE)
  - 200-500: 10/30 (THIN)
  - <200: 0/30 (INSUFFICIENT)

Usage:
    from integrations import run_agent_eval
    result = run_agent_eval("/path/to/agent.md")

CLI:
    python harness.py grade-agent agents/golang-general-engineer.md
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ScoreComponent:
    """A single scoring component with name, points, and details."""

    name: str
    max_points: int
    earned_points: int
    passed: bool
    details: str


@dataclass
class AgentEvalResult:
    """Complete assessment result for an agent or skill."""

    path: str
    entity_type: str  # "agent" or "skill"
    overall_score: int
    max_score: int
    grade: str
    structural_score: int
    structural_max: int
    depth_score: int
    depth_max: int
    depth_grade: str
    total_lines: int
    components: list[ScoreComponent] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": self.path,
            "entity_type": self.entity_type,
            "overall_score": self.overall_score,
            "max_score": self.max_score,
            "grade": self.grade,
            "structural_score": self.structural_score,
            "structural_max": self.structural_max,
            "depth_score": self.depth_score,
            "depth_max": self.depth_max,
            "depth_grade": self.depth_grade,
            "total_lines": self.total_lines,
            "components": [
                {
                    "name": c.name,
                    "max_points": c.max_points,
                    "earned_points": c.earned_points,
                    "passed": c.passed,
                    "details": c.details,
                }
                for c in self.components
            ],
            "issues": self.issues,
            "recommendations": self.recommendations,
        }


def calculate_grade(score: int, max_score: int = 100) -> str:
    """Calculate letter grade from numeric score."""
    percentage = (score / max_score) * 100 if max_score > 0 else 0
    if percentage >= 90:
        return "A"
    elif percentage >= 80:
        return "B"
    elif percentage >= 70:
        return "C"
    elif percentage >= 60:
        return "D"
    else:
        return "F"


def calculate_depth_grade(total_lines: int) -> tuple[int, str]:
    """
    Calculate depth score and grade based on total lines.

    Returns:
        Tuple of (score, grade_name)
    """
    if total_lines >= 2000:
        return 30, "EXCELLENT"
    elif total_lines >= 1000:
        return 25, "GOOD"
    elif total_lines >= 500:
        return 20, "ADEQUATE"
    elif total_lines >= 200:
        return 10, "THIN"
    else:
        return 0, "INSUFFICIENT"


def parse_yaml_frontmatter(content: str) -> dict | None:
    """Extract and parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return None

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None

    try:
        return yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None


def count_examples(content: str) -> int:
    """Count the number of <example> tags in content."""
    return len(re.findall(r"<example>", content, re.IGNORECASE))


def check_section_exists(content: str, section_name: str) -> tuple[bool, int | None]:
    """
    Check if a markdown section exists.

    Returns:
        Tuple of (exists, line_number or None)
    """
    pattern = rf"^##\s+{re.escape(section_name)}"
    for i, line in enumerate(content.splitlines(), 1):
        if re.match(pattern, line, re.IGNORECASE):
            return True, i
    return False, None


def check_subsection_exists(content: str, subsection_name: str) -> tuple[bool, int | None]:
    """
    Check if a markdown subsection (###) exists.

    Returns:
        Tuple of (exists, line_number or None)
    """
    pattern = rf"^###\s+{re.escape(subsection_name)}"
    for i, line in enumerate(content.splitlines(), 1):
        if re.match(pattern, line, re.IGNORECASE):
            return True, i
    return False, None


def check_placeholders(content: str) -> list[tuple[int, str]]:
    """Find placeholder text in content."""
    placeholders = []
    pattern = r"\[(?:TODO|TBD|PLACEHOLDER|INSERT)[^\]]*\]"
    for i, line in enumerate(content.splitlines(), 1):
        matches = re.findall(pattern, line, re.IGNORECASE)
        for match in matches:
            placeholders.append((i, match))
    return placeholders


def validate_python_syntax(script_path: Path) -> tuple[bool, str]:
    """Check if a Python script has valid syntax."""
    try:
        result = subprocess.run(
            ["python3", "-m", "py_compile", str(script_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, "Syntax valid"
        else:
            return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "Syntax check timed out"
    except FileNotFoundError:
        return False, "Python not found"
    except Exception as e:
        return False, str(e)


def assess_agent(agent_path: Path) -> AgentEvalResult:
    """
    Assess an agent file against the agent-assessment skill rubric.

    Agent scoring (70 points structural):
    - YAML front matter: 10 points
    - Operator Context section: 20 points (with all 3 behavior types)
    - Examples in description: 10 points (3+ examples)
    - Error Handling section: 10 points
    - Reference files: N/A for agents (adjusted scoring)
    - Validation script: N/A for agents (adjusted scoring)

    For agents, structural max is 50 points, depth max is 30 points = 80 total
    We scale to 100 for consistency.
    """
    content = agent_path.read_text()
    lines = content.splitlines()
    total_lines = len(lines)

    components: list[ScoreComponent] = []
    issues: list[dict] = []
    recommendations: list[str] = []

    # 1. YAML Front Matter (10 points)
    frontmatter = parse_yaml_frontmatter(content)
    if frontmatter is None:
        components.append(
            ScoreComponent(
                name="YAML Front Matter",
                max_points=10,
                earned_points=0,
                passed=False,
                details="No valid YAML frontmatter found",
            )
        )
        issues.append({"priority": "HIGH", "description": "Missing or invalid YAML frontmatter", "line": 1})
        recommendations.append("Add valid YAML frontmatter with --- delimiters")
    else:
        required_fields = ["name", "description"]
        missing = [f for f in required_fields if f not in frontmatter]
        if missing:
            points = max(0, 10 - len(missing) * 5)
            components.append(
                ScoreComponent(
                    name="YAML Front Matter",
                    max_points=10,
                    earned_points=points,
                    passed=False,
                    details=f"Missing required fields: {missing}",
                )
            )
            issues.append({"priority": "HIGH", "description": f"Missing frontmatter fields: {missing}", "line": 1})
        else:
            components.append(
                ScoreComponent(
                    name="YAML Front Matter",
                    max_points=10,
                    earned_points=10,
                    passed=True,
                    details="All required fields present",
                )
            )

    # 2. Operator Context Section (20 points)
    op_context_exists, op_line = check_section_exists(content, "Operator Context")
    if not op_context_exists:
        components.append(
            ScoreComponent(
                name="Operator Context",
                max_points=20,
                earned_points=0,
                passed=False,
                details="Operator Context section not found",
            )
        )
        issues.append({"priority": "HIGH", "description": "Missing Operator Context section"})
        recommendations.append("Add ## Operator Context section with behavior definitions")
    else:
        # Check for all 3 behavior types
        hardcoded, _ = check_subsection_exists(content, "Hardcoded Behaviors")
        default, _ = check_subsection_exists(content, "Default Behaviors")
        optional, _ = check_subsection_exists(content, "Optional Behaviors")

        behavior_count = sum([hardcoded, default, optional])
        points = int((behavior_count / 3) * 20)

        missing_behaviors = []
        if not hardcoded:
            missing_behaviors.append("Hardcoded Behaviors")
        if not default:
            missing_behaviors.append("Default Behaviors")
        if not optional:
            missing_behaviors.append("Optional Behaviors")

        if behavior_count == 3:
            components.append(
                ScoreComponent(
                    name="Operator Context",
                    max_points=20,
                    earned_points=20,
                    passed=True,
                    details=f"All 3 behavior types present (line {op_line})",
                )
            )
        else:
            components.append(
                ScoreComponent(
                    name="Operator Context",
                    max_points=20,
                    earned_points=points,
                    passed=False,
                    details=f"Missing: {', '.join(missing_behaviors)}",
                )
            )
            issues.append(
                {"priority": "MEDIUM", "description": f"Incomplete Operator Context: missing {missing_behaviors}"}
            )

    # 3. Examples (10 points)
    example_count = count_examples(content)
    if example_count >= 3:
        components.append(
            ScoreComponent(
                name="Examples",
                max_points=10,
                earned_points=10,
                passed=True,
                details=f"Found {example_count} examples (3+ required)",
            )
        )
    elif example_count > 0:
        points = int((example_count / 3) * 10)
        components.append(
            ScoreComponent(
                name="Examples",
                max_points=10,
                earned_points=points,
                passed=False,
                details=f"Found {example_count} examples (need 3+)",
            )
        )
        issues.append({"priority": "MEDIUM", "description": f"Only {example_count} examples, need at least 3"})
        recommendations.append("Add more realistic usage examples")
    else:
        components.append(
            ScoreComponent(
                name="Examples",
                max_points=10,
                earned_points=0,
                passed=False,
                details="No examples found",
            )
        )
        issues.append({"priority": "HIGH", "description": "No examples in description"})
        recommendations.append("Add at least 3 <example> blocks showing realistic usage")

    # 4. Error Handling Section (10 points)
    error_section_exists, error_line = check_section_exists(content, "Error Handling")
    # Also check for common variants
    if not error_section_exists:
        error_section_exists, error_line = check_section_exists(content, "Common Errors")

    if error_section_exists:
        components.append(
            ScoreComponent(
                name="Error Handling",
                max_points=10,
                earned_points=10,
                passed=True,
                details=f"Error handling section found (line {error_line})",
            )
        )
    else:
        components.append(
            ScoreComponent(
                name="Error Handling",
                max_points=10,
                earned_points=0,
                passed=False,
                details="No error handling section found",
            )
        )
        issues.append({"priority": "MEDIUM", "description": "Missing Error Handling section"})
        recommendations.append("Add ## Error Handling section with common errors and solutions")

    # 5. Check for placeholders
    placeholders = check_placeholders(content)
    if placeholders:
        for line_num, placeholder in placeholders[:5]:  # Report first 5
            issues.append({"priority": "LOW", "description": f"Placeholder found: {placeholder}", "line": line_num})
        recommendations.append("Replace placeholder text with actual content")

    # Calculate structural score (for agents: 50 points max from components)
    structural_score = sum(c.earned_points for c in components)
    structural_max = sum(c.max_points for c in components)

    # Calculate depth score
    depth_score, depth_grade = calculate_depth_grade(total_lines)

    # For agents, we have 50 structural + 30 depth = 80 points
    # Scale to 100 for consistency
    raw_total = structural_score + depth_score
    raw_max = structural_max + 30

    # Scale to 100
    overall_score = int((raw_total / raw_max) * 100) if raw_max > 0 else 0
    grade = calculate_grade(overall_score)

    return AgentEvalResult(
        path=str(agent_path),
        entity_type="agent",
        overall_score=overall_score,
        max_score=100,
        grade=grade,
        structural_score=structural_score,
        structural_max=structural_max,
        depth_score=depth_score,
        depth_max=30,
        depth_grade=depth_grade,
        total_lines=total_lines,
        components=components,
        issues=issues,
        recommendations=recommendations,
    )


def assess_skill(skill_path: Path) -> AgentEvalResult:
    """
    Assess a skill file against the agent-assessment skill rubric.

    Skill scoring (70 points structural):
    - YAML front matter: 10 points (with allowed-tools)
    - Operator Context section: 20 points (with all 3 behavior types)
    - Examples: 10 points
    - Error Handling section: 10 points
    - Reference Files: 10 points
    - Validation Script: 10 points
    """
    content = skill_path.read_text()
    lines = content.splitlines()
    skill_lines = len(lines)

    # Get skill directory for checking references and scripts
    skill_dir = skill_path.parent

    components: list[ScoreComponent] = []
    issues: list[dict] = []
    recommendations: list[str] = []

    # 1. YAML Front Matter (10 points)
    frontmatter = parse_yaml_frontmatter(content)
    if frontmatter is None:
        components.append(
            ScoreComponent(
                name="YAML Front Matter",
                max_points=10,
                earned_points=0,
                passed=False,
                details="No valid YAML frontmatter found",
            )
        )
        issues.append({"priority": "HIGH", "description": "Missing or invalid YAML frontmatter", "line": 1})
    else:
        required_fields = ["name", "description", "allowed-tools"]
        missing = [f for f in required_fields if f not in frontmatter]
        if missing:
            points = max(0, 10 - len(missing) * 3)
            components.append(
                ScoreComponent(
                    name="YAML Front Matter",
                    max_points=10,
                    earned_points=points,
                    passed=False,
                    details=f"Missing required fields: {missing}",
                )
            )
            issues.append({"priority": "HIGH", "description": f"Missing frontmatter fields: {missing}", "line": 1})
        else:
            components.append(
                ScoreComponent(
                    name="YAML Front Matter",
                    max_points=10,
                    earned_points=10,
                    passed=True,
                    details="All required fields present (including allowed-tools)",
                )
            )

    # 2. Operator Context Section (20 points)
    op_context_exists, op_line = check_section_exists(content, "Operator Context")
    if not op_context_exists:
        components.append(
            ScoreComponent(
                name="Operator Context",
                max_points=20,
                earned_points=0,
                passed=False,
                details="Operator Context section not found",
            )
        )
        issues.append({"priority": "HIGH", "description": "Missing Operator Context section"})
        recommendations.append("Add ## Operator Context section with behavior definitions")
    else:
        hardcoded, _ = check_subsection_exists(content, "Hardcoded Behaviors")
        default, _ = check_subsection_exists(content, "Default Behaviors")
        optional, _ = check_subsection_exists(content, "Optional Behaviors")

        behavior_count = sum([hardcoded, default, optional])
        points = int((behavior_count / 3) * 20)

        missing_behaviors = []
        if not hardcoded:
            missing_behaviors.append("Hardcoded Behaviors")
        if not default:
            missing_behaviors.append("Default Behaviors")
        if not optional:
            missing_behaviors.append("Optional Behaviors")

        if behavior_count == 3:
            components.append(
                ScoreComponent(
                    name="Operator Context",
                    max_points=20,
                    earned_points=20,
                    passed=True,
                    details=f"All 3 behavior types present (line {op_line})",
                )
            )
        else:
            components.append(
                ScoreComponent(
                    name="Operator Context",
                    max_points=20,
                    earned_points=points,
                    passed=False,
                    details=f"Missing: {', '.join(missing_behaviors)}",
                )
            )
            issues.append(
                {"priority": "MEDIUM", "description": f"Incomplete Operator Context: missing {missing_behaviors}"}
            )

    # 3. Examples (10 points) - For skills, check code blocks and step-by-step examples
    example_count = count_examples(content)
    code_blocks = len(re.findall(r"```[a-z]+", content))

    if example_count >= 3 or code_blocks >= 5:
        components.append(
            ScoreComponent(
                name="Examples",
                max_points=10,
                earned_points=10,
                passed=True,
                details=f"Found {example_count} examples, {code_blocks} code blocks",
            )
        )
    elif example_count > 0 or code_blocks >= 3:
        points = 6
        components.append(
            ScoreComponent(
                name="Examples",
                max_points=10,
                earned_points=points,
                passed=False,
                details=f"Found {example_count} examples, {code_blocks} code blocks (need more)",
            )
        )
        issues.append({"priority": "MEDIUM", "description": "Limited examples/code blocks"})
    else:
        components.append(
            ScoreComponent(
                name="Examples",
                max_points=10,
                earned_points=0,
                passed=False,
                details="Insufficient examples",
            )
        )
        issues.append({"priority": "HIGH", "description": "No examples or code blocks"})
        recommendations.append("Add examples and code blocks demonstrating skill usage")

    # 4. Error Handling Section (10 points)
    error_section_exists, error_line = check_section_exists(content, "Error Handling")
    if error_section_exists:
        components.append(
            ScoreComponent(
                name="Error Handling",
                max_points=10,
                earned_points=10,
                passed=True,
                details=f"Error handling section found (line {error_line})",
            )
        )
    else:
        components.append(
            ScoreComponent(
                name="Error Handling",
                max_points=10,
                earned_points=0,
                passed=False,
                details="No error handling section found",
            )
        )
        issues.append({"priority": "MEDIUM", "description": "Missing Error Handling section"})
        recommendations.append("Add ## Error Handling section with common errors and solutions")

    # 5. Reference Files (10 points)
    refs_dir = skill_dir / "references"
    if refs_dir.exists() and refs_dir.is_dir():
        ref_files = list(refs_dir.glob("*.md"))
        if ref_files:
            components.append(
                ScoreComponent(
                    name="Reference Files",
                    max_points=10,
                    earned_points=10,
                    passed=True,
                    details=f"Found {len(ref_files)} reference files",
                )
            )
        else:
            components.append(
                ScoreComponent(
                    name="Reference Files",
                    max_points=10,
                    earned_points=5,
                    passed=False,
                    details="References directory exists but is empty",
                )
            )
            issues.append({"priority": "LOW", "description": "Empty references directory"})
            recommendations.append("Add reference documentation files")
    else:
        components.append(
            ScoreComponent(
                name="Reference Files",
                max_points=10,
                earned_points=0,
                passed=False,
                details="No references directory found",
            )
        )
        issues.append({"priority": "MEDIUM", "description": "Missing references directory"})
        recommendations.append("Create references/ directory with supporting documentation")

    # 6. Validation Script (10 points)
    scripts_dir = skill_dir / "scripts"
    validate_script = scripts_dir / "validate.py"

    if validate_script.exists():
        is_valid, syntax_msg = validate_python_syntax(validate_script)
        if is_valid:
            components.append(
                ScoreComponent(
                    name="Validation Script",
                    max_points=10,
                    earned_points=10,
                    passed=True,
                    details="validate.py exists and has valid syntax",
                )
            )
        else:
            components.append(
                ScoreComponent(
                    name="Validation Script",
                    max_points=10,
                    earned_points=5,
                    passed=False,
                    details=f"validate.py has syntax errors: {syntax_msg[:50]}",
                )
            )
            issues.append({"priority": "HIGH", "description": f"Syntax error in validate.py: {syntax_msg}"})
    else:
        components.append(
            ScoreComponent(
                name="Validation Script",
                max_points=10,
                earned_points=0,
                passed=False,
                details="No validate.py script found",
            )
        )
        issues.append({"priority": "MEDIUM", "description": "Missing scripts/validate.py"})
        recommendations.append("Create scripts/validate.py for automated validation")

    # Calculate total lines (skill + references)
    total_lines = skill_lines
    refs_dir = skill_dir / "references"
    if refs_dir.exists():
        for ref_file in refs_dir.glob("*.md"):
            try:
                total_lines += len(ref_file.read_text().splitlines())
            except Exception:
                pass

    # Calculate structural score
    structural_score = sum(c.earned_points for c in components)
    structural_max = sum(c.max_points for c in components)

    # Calculate depth score
    depth_score, depth_grade = calculate_depth_grade(total_lines)

    # Total score
    overall_score = structural_score + depth_score
    grade = calculate_grade(overall_score)

    return AgentEvalResult(
        path=str(skill_path),
        entity_type="skill",
        overall_score=overall_score,
        max_score=100,
        grade=grade,
        structural_score=structural_score,
        structural_max=structural_max,
        depth_score=depth_score,
        depth_max=30,
        depth_grade=depth_grade,
        total_lines=total_lines,
        components=components,
        issues=issues,
        recommendations=recommendations,
    )


def run_agent_eval(path: str) -> dict:
    """
    Main entry point for agent/skill assessment.

    Determines whether the path points to an agent or skill and runs
    the appropriate assessment.

    Args:
        path: Path to agent file (.md) or skill directory/SKILL.md

    Returns:
        Dictionary with assessment results including:
        - overall_score: 0-100
        - grade: A-F
        - structural_score: Points from structural checks
        - depth_score: Points from content depth
        - components: List of individual check results
        - issues: List of problems found
        - recommendations: List of improvement suggestions
    """
    file_path = Path(path)

    if not file_path.exists():
        return {
            "error": f"Path not found: {path}",
            "path": path,
            "overall_score": 0,
            "grade": "F",
        }

    # Determine if this is an agent or skill
    if file_path.is_dir():
        # Assume it's a skill directory
        skill_file = file_path / "SKILL.md"
        if skill_file.exists():
            result = assess_skill(skill_file)
        else:
            return {
                "error": f"No SKILL.md found in directory: {path}",
                "path": path,
                "overall_score": 0,
                "grade": "F",
            }
    elif file_path.name == "SKILL.md":
        result = assess_skill(file_path)
    elif file_path.suffix == ".md":
        # Check if it's in agents/ directory or is clearly an agent
        if "agents/" in str(file_path) or file_path.parent.name == "agents":
            result = assess_agent(file_path)
        elif "skills/" in str(file_path):
            result = assess_skill(file_path)
        else:
            # Default to agent assessment for .md files
            result = assess_agent(file_path)
    else:
        return {
            "error": f"Unsupported file type: {path}",
            "path": path,
            "overall_score": 0,
            "grade": "F",
        }

    return result.to_dict()


def format_report(result: dict, verbose: bool = True) -> str:
    """
    Format assessment result as a human-readable report.

    Args:
        result: Assessment result dictionary
        verbose: Include detailed component breakdown

    Returns:
        Formatted report string
    """
    if "error" in result:
        return f"ERROR: {result['error']}"

    lines = [
        f"# Assessment Report: {Path(result['path']).name}",
        "",
        f"**Type**: {result['entity_type'].title()}",
        f"**Overall Score**: {result['overall_score']}/{result['max_score']} ({result['grade']})",
        "",
        "## Score Breakdown",
        f"- Structural: {result['structural_score']}/{result['structural_max']}",
        f"- Content Depth: {result['depth_score']}/{result['depth_max']} ({result['depth_grade']})",
        f"- Total Lines: {result['total_lines']}",
        "",
    ]

    if verbose and result.get("components"):
        lines.extend(["## Component Scores", ""])
        lines.append("| Component | Score | Status | Details |")
        lines.append("|-----------|-------|--------|---------|")
        for comp in result["components"]:
            status = "PASS" if comp["passed"] else "FAIL"
            lines.append(
                f"| {comp['name']} | {comp['earned_points']}/{comp['max_points']} | {status} | {comp['details'][:50]} |"
            )
        lines.append("")

    if result.get("issues"):
        lines.extend(["## Issues Found", ""])
        for issue in result["issues"]:
            priority = issue.get("priority", "")
            desc = issue.get("description", "")
            line_num = issue.get("line", "")
            loc = f" (line {line_num})" if line_num else ""
            lines.append(f"- **[{priority}]** {desc}{loc}")
        lines.append("")

    if result.get("recommendations"):
        lines.extend(["## Recommendations", ""])
        for i, rec in enumerate(result["recommendations"], 1):
            lines.append(f"{i}. {rec}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python agent_evaluation.py <agent_or_skill_path>")
        sys.exit(1)

    result = run_agent_eval(sys.argv[1])
    print(format_report(result))
