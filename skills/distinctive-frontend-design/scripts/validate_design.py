#!/usr/bin/env python3
"""
Comprehensive design validation script.
Checks for anti-patterns, clichés, and scores overall distinctiveness.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


class DesignValidationError(Exception):
    """Custom exception for validation errors."""

    pass


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Load JSON file with error handling."""
    if not file_path.exists():
        raise DesignValidationError(f"File not found: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise DesignValidationError(f"Invalid JSON in {file_path}: {e}")


def load_anti_patterns() -> Dict[str, Any]:
    """Load anti-patterns database."""
    skill_dir = Path(__file__).parent.parent
    anti_patterns_path = skill_dir / "references" / "anti-patterns.json"

    if not anti_patterns_path.exists():
        # Return default anti-patterns if file doesn't exist
        return {
            "banned_fonts": [
                "Inter",
                "Roboto",
                "Arial",
                "Helvetica",
                "System",
                "-apple-system",
                "BlinkMacSystemFont",
                "Segoe UI",
                "Space Grotesk",
                "sans-serif",
            ],
            "cliche_colors": [
                {"name": "Purple gradient on white", "colors": ["#8B5CF6", "#A855F7", "#667eea", "#764ba2"]},
                {"name": "Generic blue", "colors": ["#3B82F6", "#2563EB"]},
                {"name": "Pure black/white", "colors": ["#000000", "#FFFFFF"]},
            ],
        }

    return load_json_file(anti_patterns_path)


def validate_fonts(fonts: List[str], project_name: str) -> Tuple[int, bool, str, List[str]]:
    """
    Validate font selections against banned list and project history.

    Returns: (score, passed, details, warnings)
    """
    anti_patterns = load_anti_patterns()
    banned_fonts = [f.lower() for f in anti_patterns.get("banned_fonts", [])]

    warnings = []

    # Check for banned fonts
    for font in fonts:
        font_lower = font.lower().strip()
        for banned in banned_fonts:
            if banned in font_lower:
                return (
                    0,
                    False,
                    f"❌ BANNED FONT DETECTED: '{font}' contains '{banned}'. This font is overused and creates generic aesthetics.",
                    [],
                )

    # Check project history for repetition
    skill_dir = Path(__file__).parent.parent
    history_path = skill_dir / "references" / "project-history.json"

    if history_path.exists():
        history = load_json_file(history_path)
        projects = history.get("projects", [])

        # Look for same font pairing in recent projects
        font_pair = ",".join(sorted(fonts))
        recent_projects = [p for p in projects if p.get("name") != project_name][-5:]  # Last 5 projects

        for project in recent_projects:
            project_fonts = project.get("fonts", [])
            project_pair = ",".join(sorted(project_fonts))

            if font_pair == project_pair:
                warnings.append(
                    f"⚠️  Font pairing '{font_pair}' was used in recent project '{project['name']}'. "
                    f"Consider selecting different fonts for variety."
                )
                return (70, True, f"Font pairing is valid but lacks variety. Used in '{project['name']}'.", warnings)

    # All checks passed
    score = 95
    details = f"✅ Excellent font selection. {', '.join(fonts)} pairing is distinctive and unused in recent projects."

    return (score, True, details, warnings)


def validate_palette(palette_path: Path) -> Tuple[int, bool, str, List[str]]:
    """
    Validate color palette for clichés and proper dominance.

    Returns: (score, passed, details, warnings)
    """
    palette = load_json_file(palette_path)
    anti_patterns = load_anti_patterns()
    cliche_colors = anti_patterns.get("cliche_colors", [])

    warnings = []

    # Extract all colors from palette
    all_colors = []
    for category in ["dominant", "secondary", "accent", "functional"]:
        if category in palette:
            cat_colors = palette[category]
            if isinstance(cat_colors, dict):
                all_colors.extend([v for v in cat_colors.values() if isinstance(v, str) and v.startswith("#")])

    # Check for cliché color combinations
    for cliche in cliche_colors:
        cliche_set = set(c.upper() for c in cliche["colors"])
        palette_set = set(c.upper() for c in all_colors)

        # If 50% or more of cliché colors are present
        overlap = len(cliche_set & palette_set)
        if overlap >= len(cliche_set) * 0.5:
            return (
                0,
                False,
                f"❌ CLICHÉ DETECTED: '{cliche['name']}' color scheme. "
                f"Found {overlap}/{len(cliche_set)} cliché colors in palette.",
                [],
            )

    # Check for color dominance structure
    has_dominant = "dominant" in palette and palette["dominant"]
    has_secondary = "secondary" in palette and palette["secondary"]
    has_accent = "accent" in palette and palette["accent"]

    if not (has_dominant and has_secondary and has_accent):
        warnings.append("⚠️  Palette should have clear dominant/secondary/accent structure (60/30/10 rule).")
        return (60, True, "Palette is valid but lacks clear hierarchical structure.", warnings)

    # Check for pure black/white as dominant
    dominant_colors = palette.get("dominant", {})
    if isinstance(dominant_colors, dict):
        for color in dominant_colors.values():
            if isinstance(color, str):
                if color.upper() in ["#000000", "#FFFFFF"]:
                    warnings.append(
                        f"⚠️  Dominant color {color} is pure black/white. "
                        f"Consider using off-black/off-white for more sophisticated aesthetic."
                    )

    # Check for inspiration/context
    has_inspiration = "inspiration" in palette and palette["inspiration"]
    has_rationale = any("rationale" in palette.get(cat, {}) for cat in ["dominant", "secondary", "accent"])

    score = 85
    if has_inspiration and has_rationale:
        score = 90
        details = (
            f"✅ Strong palette with clear dominance and contextual inspiration. "
            f"'{palette.get('palette_name', 'Unnamed')}' theme avoids clichés."
        )
    else:
        details = (
            "✅ Valid palette structure, but consider adding inspiration source and rationale for each color group."
        )

    # Check accent colors for text accessibility
    accent_colors = palette.get("accent", {})
    if isinstance(accent_colors, dict):
        if "primary" in accent_colors and "primary_dark" not in accent_colors:
            warnings.append("⚠️  Consider adding darker accent variant for text on light backgrounds (accessibility).")

    return (score, True, details, warnings)


def calculate_variety_score(project_name: str, fonts: List[str], palette_name: str) -> Tuple[int, str]:
    """
    Calculate variety score based on project history.

    Returns: (score, details)
    """
    skill_dir = Path(__file__).parent.parent
    history_path = skill_dir / "references" / "project-history.json"

    if not history_path.exists():
        return (100, "✅ First project tracked. Excellent start!")

    history = load_json_file(history_path)
    projects = history.get("projects", [])

    if len(projects) == 0:
        return (100, "✅ First project tracked. Excellent start!")

    # Compare with recent projects (last 3)
    recent_projects = [p for p in projects if p.get("name") != project_name][-3:]

    font_pair = ",".join(sorted(fonts))
    similar_fonts = 0
    similar_palette = 0

    for project in recent_projects:
        project_fonts = ",".join(sorted(project.get("fonts", [])))
        if font_pair == project_fonts:
            similar_fonts += 1

        project_palette = project.get("palette_name", "")
        if palette_name and project_palette and palette_name.lower() in project_palette.lower():
            similar_palette += 1

    if similar_fonts > 0:
        return (70, f"⚠️  Font pairing matches {similar_fonts} recent project(s). Aim for more variety.")

    if similar_palette > 0:
        return (80, f"⚠️  Similar palette theme used in {similar_palette} recent project(s).")

    score = 90
    details = f"✅ Aesthetic differs significantly from {len(recent_projects)} recent project(s)."

    return (score, details)


def calculate_distinctiveness_score(
    palette: Dict, has_animation: bool, has_background: bool
) -> Tuple[int, str, List[str]]:
    """
    Calculate overall distinctiveness score.

    Returns: (score, details, suggestions)
    """
    suggestions = []
    score = 70  # Base score

    # Check for strong aesthetic commitment
    has_inspiration = "inspiration" in palette and palette["inspiration"]
    has_rationale = any("rationale" in palette.get(cat, {}) for cat in ["dominant", "secondary", "accent"])

    if has_inspiration and has_rationale:
        score += 10
    else:
        suggestions.append("Add clear inspiration source and rationale for design decisions")

    # Check for animation strategy
    if has_animation:
        score += 5
    else:
        suggestions.append("Define animation strategy for at least one high-impact moment")

    # Check for atmospheric background
    if has_background:
        score += 5
    else:
        suggestions.append("Create atmospheric background (layered gradients, patterns, textures)")

    # Check for unique palette name
    if palette.get("palette_name"):
        score += 5

    # Provide contextual feedback
    if score >= 90:
        details = "✅ Exceptional distinctiveness. Design has strong personality and clear direction."
    elif score >= 80:
        details = "✅ Good distinctiveness. Design avoids generic patterns with commitment to aesthetic."
    elif score >= 70:
        details = "⚠️  Adequate distinctiveness, but could be strengthened with more unique elements."
    else:
        details = "❌ Low distinctiveness. Design needs stronger commitment to unique aesthetic direction."

    return (score, details, suggestions)


def run_validation(
    fonts: List[str], palette_path: Path, project_name: str, has_animation: bool = False, has_background: bool = False
) -> Dict[str, Any]:
    """Run comprehensive validation and return results."""

    results = {"project_name": project_name, "overall_score": 0, "grade": "F", "checks": {}, "recommendations": []}

    # Typography validation
    font_score, font_passed, font_details, font_warnings = validate_fonts(fonts, project_name)
    results["checks"]["typography"] = {
        "score": font_score,
        "passed": font_passed,
        "details": font_details,
        "warnings": font_warnings,
    }

    # Palette validation
    palette = load_json_file(palette_path)
    palette_score, palette_passed, palette_details, palette_warnings = validate_palette(palette_path)
    results["checks"]["color_palette"] = {
        "score": palette_score,
        "passed": palette_passed,
        "details": palette_details,
        "warnings": palette_warnings,
    }

    # Variety check
    palette_name = palette.get("palette_name", "")
    variety_score, variety_details = calculate_variety_score(project_name, fonts, palette_name)
    results["checks"]["variety"] = {"score": variety_score, "passed": variety_score >= 70, "details": variety_details}

    # Distinctiveness check
    distinct_score, distinct_details, distinct_suggestions = calculate_distinctiveness_score(
        palette, has_animation, has_background
    )
    results["checks"]["distinctiveness"] = {
        "score": distinct_score,
        "passed": distinct_score >= 70,
        "details": distinct_details,
        "suggestions": distinct_suggestions,
    }

    # Anti-patterns check (always 100 if we got here, since banned items would fail earlier)
    if font_passed and palette_passed:
        results["checks"]["anti_patterns"] = {
            "score": 100,
            "passed": True,
            "details": "✅ No anti-patterns detected. Design avoids all identified clichés.",
        }

    # Calculate overall score
    scores = [check["score"] for check in results["checks"].values() if "score" in check]
    results["overall_score"] = sum(scores) // len(scores) if scores else 0

    # Assign grade
    if results["overall_score"] >= 90:
        results["grade"] = "A"
    elif results["overall_score"] >= 80:
        results["grade"] = "B"
    elif results["overall_score"] >= 70:
        results["grade"] = "C"
    elif results["overall_score"] >= 60:
        results["grade"] = "D"
    else:
        results["grade"] = "F"

    # Collect all recommendations
    for check in results["checks"].values():
        if "warnings" in check:
            results["recommendations"].extend(check["warnings"])
        if "suggestions" in check:
            results["recommendations"].extend(check["suggestions"])

    return results


def update_project_history(project_name: str, fonts: List[str], palette_name: str):
    """Update project history with new project."""
    skill_dir = Path(__file__).parent.parent
    history_path = skill_dir / "references" / "project-history.json"

    # Load existing history
    if history_path.exists():
        history = load_json_file(history_path)
    else:
        history = {"projects": []}

    # Remove existing entry for this project if present
    history["projects"] = [p for p in history["projects"] if p.get("name") != project_name]

    # Add new entry
    from datetime import datetime

    history["projects"].append(
        {"name": project_name, "fonts": fonts, "palette_name": palette_name, "timestamp": datetime.now().isoformat()}
    )

    # Save updated history
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def print_validation_report(results: Dict[str, Any]):
    """Print formatted validation report."""
    print("\n" + "=" * 70)
    print("DESIGN VALIDATION REPORT")
    print("=" * 70)
    print(f"\nProject: {results['project_name']}")
    print(f"Overall Score: {results['overall_score']}/100")
    print(f"Grade: {results['grade']}")
    print("\n" + "-" * 70)

    for check_name, check_data in results["checks"].items():
        print(f"\n{check_name.upper().replace('_', ' ')}:")
        print(f"  Score: {check_data['score']}/100")
        print(f"  Status: {'✅ PASS' if check_data['passed'] else '❌ FAIL'}")
        print(f"  {check_data['details']}")

        if check_data.get("warnings"):
            for warning in check_data["warnings"]:
                print(f"  {warning}")

        if check_data.get("suggestions"):
            for suggestion in check_data["suggestions"]:
                print(f"  • {suggestion}")

    if results["recommendations"]:
        print("\n" + "-" * 70)
        print("RECOMMENDATIONS:")
        for i, rec in enumerate(results["recommendations"], 1):
            print(f"  {i}. {rec}")

    print("\n" + "=" * 70)

    if results["overall_score"] >= 80:
        print("✅ VALIDATION PASSED - Design is ready for implementation")
    elif results["overall_score"] >= 70:
        print("⚠️  VALIDATION WARNING - Consider addressing recommendations before implementation")
    else:
        print("❌ VALIDATION FAILED - Address critical issues before proceeding")

    print("=" * 70 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate frontend design for distinctiveness and anti-patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--fonts", required=True, help='Comma-separated list of font families (e.g., "Unbounded,Crimson Pro")'
    )
    parser.add_argument("--palette", type=Path, required=True, help="Path to palette JSON file")
    parser.add_argument("--project", required=True, help="Project name for tracking variety")
    parser.add_argument("--output", type=Path, help="Output path for validation report JSON (optional)")
    parser.add_argument("--animation", action="store_true", help="Flag indicating animation strategy is defined")
    parser.add_argument(
        "--background", action="store_true", help="Flag indicating atmospheric background is implemented"
    )

    args = parser.parse_args()

    try:
        # Parse fonts
        fonts = [f.strip() for f in args.fonts.split(",")]

        # Run validation
        results = run_validation(
            fonts=fonts,
            palette_path=args.palette,
            project_name=args.project,
            has_animation=args.animation,
            has_background=args.background,
        )

        # Print report
        print_validation_report(results)

        # Save JSON output if requested
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)
            print(f"Validation report saved to: {args.output}\n")

        # Update project history if validation passed
        if results["overall_score"] >= 70:
            palette = load_json_file(args.palette)
            palette_name = palette.get("palette_name", "")
            update_project_history(args.project, fonts, palette_name)

        # Exit with appropriate code
        sys.exit(0 if results["overall_score"] >= 80 else 1)

    except DesignValidationError as e:
        print(
            json.dumps({"status": "error", "error_type": "DesignValidationError", "message": str(e)}, indent=2),
            file=sys.stderr,
        )
        sys.exit(2)
    except Exception as e:
        print(
            json.dumps({"status": "error", "error_type": type(e).__name__, "message": str(e)}, indent=2),
            file=sys.stderr,
        )
        sys.exit(3)


if __name__ == "__main__":
    main()
