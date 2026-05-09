#!/usr/bin/env python3
"""Assemble slide deck CSS from base + preset.

Combines the mandatory base CSS with a named style preset.
All presets live in templates/presets/*.css.

Usage:
    python3 assemble-styles.py --list
    python3 assemble-styles.py --preset obsidian-gold
    python3 assemble-styles.py --preset arctic-minimal --output styles.css
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPT_DIR.parent / "templates"
PRESETS_DIR = TEMPLATES_DIR / "presets"
BASE_CSS = TEMPLATES_DIR / "base.css"

PRESET_METADATA = {
    "obsidian-gold": {"mood": "impressed, authoritative", "use": "executive briefings, board presentations"},
    "arctic-minimal": {"mood": "focused, clean, technical", "use": "engineering talks, developer conferences"},
    "carbon-ember": {"mood": "energized, bold, startup", "use": "product launches, startup pitches"},
    "sage-paper": {"mood": "inspired, thoughtful, editorial", "use": "thought leadership, narrative-heavy decks"},
    "void-neon": {"mood": "energized, futuristic, tech", "use": "developer tools, AI launches, hackathons"},
    "slate-coral": {"mood": "impressed, contemporary, SaaS", "use": "SaaS demos, sales enablement"},
    "chalk-board": {"mood": "focused, educational", "use": "workshops, onboarding, training"},
    "glacier-blue": {"mood": "focused, trusted, corporate", "use": "financial, legal, healthcare"},
    "rose-noir": {"mood": "impressed, artistic, luxury", "use": "fashion, design portfolios, luxury brands"},
    "solar-sand": {"mood": "inspired, warm, community", "use": "non-profit, community talks, sustainability"},
    "steel-wire": {"mood": "focused, industrial, data-heavy", "use": "data science, infrastructure, DevOps"},
    "lavender-mist": {"mood": "inspired, calm, wellness", "use": "mental health, wellness, meditation apps"},
}

ANIMATION_MAP = {
    "obsidian-gold": {
        "enter": "fade + subtle upward translate",
        "duration": "600ms",
        "easing": "cubic-bezier(0.4, 0, 0.2, 1)",
    },
    "arctic-minimal": {"enter": "fade only", "duration": "300ms", "easing": "ease"},
    "carbon-ember": {
        "enter": "slide from right",
        "duration": "400ms",
        "easing": "cubic-bezier(0.25, 0.46, 0.45, 0.94)",
    },
    "sage-paper": {"enter": "fade + scale from 0.98", "duration": "500ms", "easing": "ease-out"},
    "void-neon": {
        "enter": "fade + scale from 1.02 with glow",
        "duration": "400ms",
        "easing": "cubic-bezier(0, 0, 0.2, 1)",
    },
    "slate-coral": {"enter": "slide from bottom", "duration": "350ms", "easing": "cubic-bezier(0.34, 1.56, 0.64, 1)"},
    "chalk-board": {"enter": "fade + slight rotate from -1deg", "duration": "450ms", "easing": "ease-out"},
    "glacier-blue": {"enter": "fade only", "duration": "250ms", "easing": "ease"},
    "rose-noir": {"enter": "fade + upward translate", "duration": "550ms", "easing": "cubic-bezier(0.4, 0, 0.2, 1)"},
    "solar-sand": {"enter": "fade + scale from 0.97", "duration": "500ms", "easing": "ease-out"},
    "steel-wire": {"enter": "slide from left", "duration": "300ms", "easing": "cubic-bezier(0.25, 0.46, 0.45, 0.94)"},
    "lavender-mist": {"enter": "fade + scale from 0.98", "duration": "600ms", "easing": "ease"},
}

MOOD_MAP = {
    "impressed": ["obsidian-gold", "rose-noir", "glacier-blue"],
    "authoritative": ["obsidian-gold", "glacier-blue", "steel-wire"],
    "energized": ["carbon-ember", "void-neon", "slate-coral"],
    "bold": ["carbon-ember", "void-neon", "steel-wire"],
    "focused": ["arctic-minimal", "steel-wire", "glacier-blue"],
    "technical": ["arctic-minimal", "void-neon", "steel-wire"],
    "inspired": ["sage-paper", "solar-sand", "lavender-mist"],
    "thoughtful": ["sage-paper", "chalk-board", "solar-sand"],
    "warm": ["solar-sand", "chalk-board", "sage-paper"],
    "clean": ["arctic-minimal", "glacier-blue", "slate-coral"],
    "dramatic": ["rose-noir", "obsidian-gold", "void-neon"],
    "calm": ["lavender-mist", "sage-paper", "glacier-blue"],
    "futuristic": ["void-neon", "steel-wire", "carbon-ember"],
    "professional": ["glacier-blue", "obsidian-gold", "slate-coral"],
    "creative": ["rose-noir", "sage-paper", "solar-sand"],
}


def list_presets():
    print("Available style presets:")
    print()
    for name, meta in sorted(PRESET_METADATA.items()):
        path = PRESETS_DIR / f"{name}.css"
        exists = "OK" if path.exists() else "MISSING"
        anim = ANIMATION_MAP.get(name, {})
        print(f"  {name:<18} [{exists}]")
        print(f"    Mood: {meta['mood']}")
        print(f"    Use:  {meta['use']}")
        if anim:
            print(f"    Animation: {anim['enter']} ({anim['duration']}, {anim['easing']})")
        print()

    print("Mood-to-preset mapping:")
    for mood, presets in sorted(MOOD_MAP.items()):
        print(f"  {mood:<15} -> {', '.join(presets)}")


def assemble(preset_name: str, output_path: str = None):
    if not BASE_CSS.exists():
        print(f"Error: base CSS not found at {BASE_CSS}", file=sys.stderr)
        sys.exit(1)

    preset_path = PRESETS_DIR / f"{preset_name}.css"
    if not preset_path.exists():
        print(f"Error: preset '{preset_name}' not found at {preset_path}", file=sys.stderr)
        print(f"Available: {', '.join(p.stem for p in sorted(PRESETS_DIR.glob('*.css')))}", file=sys.stderr)
        sys.exit(1)

    base = BASE_CSS.read_text()
    preset = preset_path.read_text()

    combined = f"{base}\n/* === PRESET: {preset_name} === */\n{preset}"

    if output_path:
        Path(output_path).write_text(combined)
        print(f"Written to {output_path}", file=sys.stderr)
    else:
        print(combined)


def main():
    parser = argparse.ArgumentParser(
        description="Assemble slide deck CSS from base + preset.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list
  %(prog)s --preset obsidian-gold
  %(prog)s --preset arctic-minimal --output styles.css
  %(prog)s --mood focused
        """,
    )
    parser.add_argument("--list", action="store_true", help="List available presets")
    parser.add_argument("--preset", help="Preset name (e.g., obsidian-gold)")
    parser.add_argument("--mood", help="Show presets matching a mood word")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")

    args = parser.parse_args()

    if args.list:
        list_presets()
        return

    if args.mood:
        mood = args.mood.lower()
        if mood in MOOD_MAP:
            print(f"Presets for '{mood}': {', '.join(MOOD_MAP[mood])}")
        else:
            print(f"Unknown mood '{mood}'. Known moods: {', '.join(sorted(MOOD_MAP.keys()))}")
        return

    if not args.preset:
        parser.error("--preset is required (use --list to see available presets)")

    assemble(args.preset, args.output)


if __name__ == "__main__":
    main()
