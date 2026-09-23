#!/usr/bin/env python3
"""
Advisory design validation script.

Scores a brand-page design spec and warns about reflexive picks (popular default
fonts, common default palettes). Warnings are signals, not failures: the right
choice depends on the surface (see skills/shared-patterns/ui-design-judgment.md).
A neutral sans is correct for a product tool; the same face picked by reflex on a
brand page reads as a template. Exit code is 0 unless --strict is passed and the
score is below 80.
"""

import argparse
import json
import re
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


# Popular faces that are fine for product tools but read as a template when picked
# by reflex on a brand page. Matched as whole words, case-insensitive.
REFLEXIVE_FONTS = [
    "Inter",
    "Roboto",
    "Arial",
    "Helvetica",
    "Space Grotesk",
    "system-ui",
    "-apple-system",
    "BlinkMacSystemFont",
    "Segoe UI",
]

# Palettes that match a generic default rather than a brand. Legitimate when the
# brand color really is one of these; the warning asks for that reason.
COMMON_DEFAULT_PALETTES = [
    {"name": "Purple gradient on white", "colors": ["#8B5CF6", "#A855F7", "#667EEA", "#764BA2"]},
    {"name": "Stock Tailwind blue", "colors": ["#3B82F6", "#2563EB"]},
]


def validate_fonts(fonts: List[str], project_name: str) -> Tuple[int, bool, str, List[str]]:
    """
    Check font selections for reflexive picks and repetition across projects.

    Reflexive picks produce a warning, never a failure.

    Returns: (score, passed, details, warnings)
    """
    warnings = []

    for font in fonts:
        for common in REFLEXIVE_FONTS:
            if re.search(rf"(?<![\w-]){re.escape(common)}(?![\w-])", font, re.IGNORECASE):
                warnings.append(
                    f"⚠️  reflexive font pick: '{font}'. Right for product tools; on a brand page, "
                    f"choose a face for the brand or state why this one fits."
                )
                break
    if warnings:
        return (80, True, "Font selection is valid; review the reflexive-pick warnings for the surface.", warnings)

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
    Check a color palette for common default schemes and a clear structure.

    Common defaults produce a warning, never a failure.

    Returns: (score, passed, details, warnings)
    """
    palette = load_json_file(palette_path)

    warnings = []

    # Extract all colors from palette
    all_colors = []
    for category in ["dominant", "secondary", "accent", "functional"]:
        if category in palette:
            cat_colors = palette[category]
            if isinstance(cat_colors, dict):
                all_colors.extend([v for v in cat_colors.values() if isinstance(v, str) and v.startswith("#")])

    # Check for common default schemes (50% or more of a scheme's colors present)
    palette_set = set(c.upper() for c in all_colors)
    for default in COMMON_DEFAULT_PALETTES:
        default_set = set(c.upper() for c in default["colors"])
        overlap = len(default_set & palette_set)
        if overlap >= len(default_set) * 0.5:
            warnings.append(
                f"⚠️  common default palette: '{default['name']}' ({overlap}/{len(default_set)} colors). "
                f"Source the accent from the brand, or state why this is the brand color."
            )

    # Check for color dominance structure
    has_dominant = "dominant" in palette and palette["dominant"]
    has_secondary = "secondary" in palette and palette["secondary"]
    has_accent = "accent" in palette and palette["accent"]

    if not (has_dominant and has_secondary and has_accent):
        warnings.append(
            "⚠️  Palette has no dominant/secondary/accent groups. A rough 60/30/10 split "
            "(neutral, secondary, accent) is a useful starting point."
        )
        return (60, True, "Palette is valid but lacks clear hierarchical structure.", warnings)

    # Pure black surfaces under light text are harsh in dark mode; pure white is fine.
    dominant_colors = palette.get("dominant", {})
    if isinstance(dominant_colors, dict):
        for color in dominant_colors.values():
            if isinstance(color, str) and color.upper() == "#000000":
                warnings.append(
                    f"⚠️  Dominant color {color} is pure black. Under light text, a near-black "
                    f"surface (for example #0f1115) is easier to read."
                )

    # Check for inspiration/context
    has_inspiration = "inspiration" in palette and palette["inspiration"]
    has_rationale = any("rationale" in palette.get(cat, {}) for cat in ["dominant", "secondary", "accent"])

    score = 85
    if has_inspiration and has_rationale:
        score = 90
        details = (
            f"✅ Strong palette with clear dominance and a stated source. "
            f"'{palette.get('palette_name', 'Unnamed')}' theme."
        )
    else:
        details = (
            "✅ Valid palette structure, but consider adding inspiration source and rationale for each color group."
        )

    if any("common default palette" in w for w in warnings):
        score = 70

    # Check accent colors for text accessibility
    accent_colors = palette.get("accent", {})
    if isinstance(accent_colors, dict):
        if "primary" in accent_colors and "primary_dark" not in accent_colors:
            warnings.append("⚠️  Consider adding darker accent variant for text on light backgrounds (accessibility).")

    return (score, True, details, warnings)


def calculate_variety_score(
    project_name: str, fonts: List[str], palette_name: str, macrostructure: str = ""
) -> Tuple[int, str]:
    """
    Calculate variety score based on project history.

    Penalizes reuse of fonts, palette theme, or page macrostructure versus recent
    projects. Macrostructure mirrors the font/palette step-down: a match against the
    last 1-2 projects drops the score to the same 70 threshold, because structural
    sameness reads as templated just as font/palette sameness does.

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

    # Macrostructure repetition: penalize a match against the last 1-2 projects.
    # Back-compat: old entries lack the field; .get("macrostructure", "") yields "".
    similar_macro = 0
    if macrostructure:
        for project in recent_projects[-2:]:
            if project.get("macrostructure", "") == macrostructure:
                similar_macro += 1

    if similar_fonts > 0:
        return (70, f"⚠️  Font pairing matches {similar_fonts} recent project(s). Aim for more variety.")

    if similar_macro > 0:
        return (
            70,
            f"⚠️  Macrostructure '{macrostructure}' matches {similar_macro} recent project(s). "
            f"Pick a different macro:* page structure for variety.",
        )

    if similar_palette > 0:
        return (80, f"⚠️  Similar palette theme used in {similar_palette} recent project(s).")

    score = 90
    details = f"✅ Aesthetic is distinct across the {len(recent_projects)} most recent project(s)."

    return (score, details)


def calculate_distinctiveness_score(palette: Dict, has_animation: bool) -> Tuple[int, str, List[str]]:
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
    fonts: List[str],
    palette_path: Path,
    project_name: str,
    has_animation: bool = False,
    macrostructure: str = "",
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
    variety_score, variety_details = calculate_variety_score(project_name, fonts, palette_name, macrostructure)
    results["checks"]["variety"] = {"score": variety_score, "passed": variety_score >= 70, "details": variety_details}

    # Distinctiveness check
    distinct_score, distinct_details, distinct_suggestions = calculate_distinctiveness_score(palette, has_animation)
    results["checks"]["distinctiveness"] = {
        "score": distinct_score,
        "passed": distinct_score >= 70,
        "details": distinct_details,
        "suggestions": distinct_suggestions,
    }

    # Reflexive-pick summary: advisory, lowers the score but never fails.
    reflexive = [
        w for w in font_warnings + palette_warnings if "reflexive font pick" in w or "common default palette" in w
    ]
    results["checks"]["anti_patterns"] = {
        "score": max(60, 100 - 20 * len(reflexive)),
        "passed": True,
        "details": (
            f"⚠️  {len(reflexive)} reflexive pick(s); keep them only with a stated reason."
            if reflexive
            else "✅ No reflexive picks detected."
        ),
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


def update_project_history(project_name: str, fonts: List[str], palette_name: str, macrostructure: str = ""):
    """Update project history with new project.

    Writes the macrostructure axis alongside fonts/palette so the next run's variety
    check can penalize structural repetition. Old entries lacking the field still load.
    """
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
        {
            "name": project_name,
            "fonts": fonts,
            "palette_name": palette_name,
            "macrostructure": macrostructure,
            "timestamp": datetime.now().isoformat(),
        }
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
        print("✅ No major signals. Render the page and run the look-then-fix loop.")
    else:
        print("⚠️  Review the recommendations: fix what applies, state reasons for the rest.")
    print("Advisory only: exit code is 0 unless --strict is passed.")

    print("=" * 70 + "\n")


def read_macro_from_stamp(css_text: str) -> str:
    """Recover the macro id from a vexjoy-design stamp comment, or "" if absent.

    The stamp is the first CSS comment in generated output:
        /* vexjoy-design: macro=<id> theme=<name> contrast=<pass|fail> ... */
    Never trusted blindly — the slop rules verify the rendered CSS independently.
    """
    import re

    m = re.search(r"vexjoy-design:.*?\bmacro=(\S+)", css_text)
    return m.group(1) if m else ""


def scan_emitted_css(css_path: Path) -> List[Dict[str, Any]]:
    """Route emitted CSS/HTML through the slop rules. Returns finding dicts.

    Warnings are advisory. Error-severity findings (contrast-canary below 1.2:1)
    make the CLI exit 1 even without --strict.
    """
    import sys as _sys
    from importlib import import_module

    _sys.path.insert(0, str(Path(__file__).parent))
    slop = import_module("css_slop_rules")

    text = css_path.read_text(encoding="utf-8")
    findings = slop.scan_css(text)
    return [{"rule_id": f.rule_id, "severity": f.severity, "message": f.message, "line": f.line} for f in findings]


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
        "--strict", action="store_true", help="Exit 1 when the overall score is below 80 (default: advisory, exit 0)"
    )
    parser.add_argument(
        "--macrostructure",
        default="",
        help="Chosen macro:* page structure id (e.g. macro:stat-led) for structural variety tracking",
    )
    parser.add_argument(
        "--emitted-css",
        type=Path,
        help="Path to generated CSS/HTML to scan for rendered-CSS slop (warnings advisory; errors exit 1)",
    )

    args = parser.parse_args()

    try:
        # Parse fonts
        fonts = [f.strip() for f in args.fonts.split(",")]

        # If a macro id was not passed but emitted CSS carries a stamp, recover it.
        macrostructure = args.macrostructure
        if not macrostructure and args.emitted_css and args.emitted_css.exists():
            macrostructure = read_macro_from_stamp(args.emitted_css.read_text(encoding="utf-8"))

        # Run validation
        results = run_validation(
            fonts=fonts,
            palette_path=args.palette,
            project_name=args.project,
            has_animation=args.animation,
            macrostructure=macrostructure,
        )

        # Print report
        print_validation_report(results)

        # Scan emitted CSS for rendered-CSS slop: warnings are advisory, errors fail the run.
        slop_errors = 0
        if args.emitted_css:
            if not args.emitted_css.exists():
                raise DesignValidationError(f"Emitted CSS file not found: {args.emitted_css}")
            slop_findings = scan_emitted_css(args.emitted_css)
            results["css_slop"] = slop_findings
            print("-" * 70)
            print(f"RENDERED-CSS SLOP SCAN: {args.emitted_css}")
            if slop_findings:
                for f in slop_findings:
                    label = "ERROR" if f["severity"] == "error" else "warning"
                    print(f"  {label} [{f['rule_id']}] line {f['line']}: {f['message']}")
                slop_errors = sum(1 for f in slop_findings if f["severity"] == "error")
                print("  (warnings are advisory; errors fail the run)")
            else:
                print("  ✅ No slop patterns detected.")
            print("-" * 70 + "\n")

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
            update_project_history(args.project, fonts, palette_name, macrostructure)

        # Advisory by default; --strict turns a low score into exit 1.
        # Blocking slop errors (invisible text) exit 1 regardless of --strict.
        sys.exit(1 if slop_errors or (args.strict and results["overall_score"] < 80) else 0)

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
