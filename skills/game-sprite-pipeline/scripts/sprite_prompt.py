#!/usr/bin/env python3
"""
Prompt scaffolding for the game-sprite-pipeline skill.

Composes a slot-structured prompt from style preset + archetype + gimmick +
tier + description. The orchestrator never passes free prose to the backend
directly -- every prompt is a reproducible composition of named slots loaded
from this module.

Subcommands:
    build-character     Phase A reference character (spritesheet mode)
    build-spritesheet   Phase C spritesheet generation prompt
    build-portrait      Portrait-mode prompt

Usage:
    python3 sprite_prompt.py build-portrait \\
        --style slay-the-spire-painted --archetype showman --gimmick heel \\
        --tier act2 --description "Bangkok Belle Nisa, kabuki makeup" \\
        --seed 42 --output prompt.txt --metadata-out prompt.json

The output prompt is a single text file ready to feed to sprite_generate.py.
The metadata JSON sidecar records the seed and the slot fills for reproducibility.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("sprite-pipeline.sprite_prompt")

# ---------------------------------------------------------------------------
# Style preset catalog (mirrors references/style-presets.md)
# ---------------------------------------------------------------------------
STYLE_PRESETS: dict[str, str] = {
    "gameboy-4color": (
        "4-shade green Game Boy palette (#0f380f, #306230, #8bac0f, #9bbc0f), "
        "8x8 tile-aligned, chunky silhouettes, no anti-aliasing, hard pixel edges"
    ),
    "nes-8bit": (
        "8-bit NES palette (54-color hardware), 3-color-per-sprite limit, blocky "
        "pixel style, 16x16 or 32x32 character cells, no shading gradients, hard outlines"
    ),
    "snes-16bit-jrpg": (
        "16-bit SNES JRPG style, saturated colors, character-portrait framing, "
        "anti-aliased 32x32 to 64x64 sprites, dithered shading, dramatic lighting"
    ),
    "genesis-16bit": (
        "16-bit Genesis/Mega Drive style, high-contrast palette, sharp outlines, "
        "fast-action sprite design, slightly desaturated tones, hard shadows"
    ),
    "arcade-cps2": (
        "Capcom CPS-2 arcade style, large expressive sprites (96x128 typical), "
        "dramatic poses, heavy outline, painterly shading on flat colors, hand-animated feel"
    ),
    "gba-16bit-portable": (
        "Game Boy Advance 16-bit style, softer palette than SNES, portable-console "
        "framing, 32x32 sprites with subtle dithering, mid-90s pop aesthetic"
    ),
    "psx-low-poly": (
        "PlayStation 1 low-poly render, ~500-1500 polygons, texture warping (affine "
        "mapping), vertex lighting, no anti-aliasing, slight jitter, 256x256 textures"
    ),
    "modern-hi-bit": (
        "Modern indie hi-bit style: clean outlines, limited 16-32 color palette, "
        "chunky pixels with anti-aliased edges, expressive poses, contemporary indie aesthetic"
    ),
    "slay-the-spire-painted": (
        "Hand-painted illustration style: heavy black ink outlines, saturated rich "
        "colors (deep reds, golds, purples), golden glowing aura around character, "
        "3/4 isometric perspective from slightly above, painterly brushwork visible, "
        "atmospheric rim lighting"
    ),
}

# ---------------------------------------------------------------------------
# Wrestler archetype catalog (mirrors references/wrestler-archetypes.md)
# ---------------------------------------------------------------------------
ARCHETYPES: dict[str, str] = {
    "powerhouse": ("powerhouse build, broad shoulders, heavy musculature, red and black gear, intimidating stance"),
    "technical": ("lean athletic build, technical wrestler frame, purple and silver gear with mat-wrestling boots"),
    "high-flyer": ("wiry agile build, high-flyer frame, green and white gear, lightweight boots, ready stance"),
    "brawler": ("rugged mid-weight build, brawler frame, orange and brown gear, taped wrists, weathered look"),
    "striker": ("sharp athletic build, striker frame, yellow and black gear, kickpads, defined calves"),
    "submission": (
        "lean grappler build, submission specialist frame, teal and navy gear, no-nonsense gear, worn knee pads"
    ),
    "showman": ("theatrical flamboyant build, showman frame, magenta and gold gear with rhinestones, dramatic pose"),
    "giant": ("giant frame (1.2x scale, towering presence), grey and black gear, slow imposing stance"),
    "player": ("hero athletic build, player-character frame, blue and gold gear, championship-aspirant pose"),
}

GIMMICKS: dict[str, str] = {
    "face": "heroic presentation, confident upright posture, polished gear, eye contact with viewer",
    "heel": "villainous presentation, sneering expression, dark accents on gear, intimidating posture",
    "manager": "manager character, suit and tie, clipboard in hand, accompanies wrestler (full-body suit not wrestling gear)",
    "referee": "referee character, black-and-white striped uniform, whistle on lanyard, neutral authoritative posture",
    "valet": "ring-side valet character, glamorous attire, accessories, accompanying-role pose (not wrestling gear)",
    "commentator": "commentator character, headset over ears, suit jacket, ringside-desk framing, mid-call expression",
    "jobber": "low-tier jobber character, plain unmarked gear, generic features, less-defined musculature, indie-show aesthetic",
    "dojo-student": "young dojo-student character, training gear (basic singlet or shorts/shirt), green expression, athletic but unrefined",
    "prospect": "mid-tier prospect character, polished but generic gear, aspiring talent expression, ready-to-prove-it stance",
    "veteran": "weathered veteran character, scar tissue or visible age, well-worn gear, experienced calm expression",
}

TIERS: dict[str, str] = {
    "act1": (
        "basic gear, mass-produced wrestling shorts/boots, no logos or sponsorships. "
        "smaller venue context (lighting suggests bingo-hall or VFW-show backdrop, "
        "no visible audience or background)"
    ),
    "act2": (
        "upgraded gear, custom-fit shorts and boots, mid-tier sponsor logos visible. "
        "mid-tier venue context (lighting suggests theater or small arena, polished production)"
    ),
    "act3": (
        "championship-tier gear, custom embroidery, premium materials, possible title belt "
        "or championship marker. championship-tier venue context (lighting suggests major arena)"
    ),
}

# ---------------------------------------------------------------------------
# Action templates for spritesheet mode
# ---------------------------------------------------------------------------
ACTION_TEMPLATES: dict[str, list[str]] = {
    "walking": [
        "right foot forward, left foot back",
        "mid-step transition with weight on right foot",
        "left foot forward, right foot back",
        "mid-step transition with weight on left foot",
    ],
    "idle": [
        "standing still, breath in (chest expanded)",
        "standing still, breath out (chest neutral)",
    ],
    "attack-punch": [
        "wind-up: right arm pulled back",
        "extending: right arm coming forward",
        "impact: right arm fully extended at peak",
        "recover: right arm returning to ready stance",
    ],
    "attack-kick": [
        "wind-up: leg cocked back",
        "leg-back: weight transferring",
        "extend: leg sweeping forward",
        "impact: leg fully extended at peak",
        "recover: leg returning to neutral stance",
    ],
    "hit-stagger": [
        "recoil: head snapping back from impact",
        "off-balance: torso tilted, arms reaching for balance",
        "recover: returning to upright neutral stance",
    ],
    "death": [
        "stagger: leaning heavily, off-balance",
        "fall-start: feet leaving ground",
        "fall-mid: rotating mid-air",
        "ground: lying on canvas, motionless",
    ],
    "entrance": [
        "standing neutral",
        "raising arms above head",
        "flex pose, arms out wide",
        "arms down, neutral stance",
        "raising arms again",
        "returning to neutral",
    ],
}

# ---------------------------------------------------------------------------
# Universal blocks
# ---------------------------------------------------------------------------
UNIVERSAL_RULES = (
    "RULES:\n"
    "- ONE character only, full body visible from head to feet, centered in frame\n"
    "- solid magenta background color (#FF00FF), filling all space outside the character silhouette\n"
    "- no text, no labels, no UI overlays, no speech bubbles, no watermarks\n"
    "- character occupies approximately 70-85% of vertical canvas (not extending edge-to-edge)\n"
    "- single composition, no panel borders, no comic-strip layout"
)

PORTRAIT_RULES = (
    "PORTRAIT_RULES:\n"
    "- character standing in neutral pose (not crouched, not jumping, not lying down)\n"
    "- aspect ratio approximately 1:1.8 (height:width); character is taller than wide\n"
    "- feet visible at bottom of frame with small margin (~5% of canvas height)\n"
    "- head visible at top with small margin (~5% of canvas height)"
)

# Portrait-loop mode: 2x2 grid of subtle idle variations (breathing + blink)
# Each cell shows the SAME character, SAME pose, SAME framing, with only minor
# breath/blink variation between frames. Played back at ~5fps the result is a
# subtle living-portrait loop (not a new pose cycle).
PORTRAIT_LOOP_RULES_IDLE_BREATH = (
    "PORTRAIT_LOOP_RULES (intensity: idle-breath):\n"
    "- 2x2 grid of FOUR cells; each cell contains the SAME character at the\n"
    "  SAME framing, SAME pose, SAME background, SAME camera angle\n"
    "- the four cells differ ONLY in subtle breath + blink variation:\n"
    "  - frame 0 (top-left):  neutral, eyes open, chest at rest\n"
    "  - frame 1 (top-right): subtle inhale, eyes still open, chest slightly\n"
    "    expanded (2-3 pixel difference, NOT a deep breath)\n"
    "  - frame 2 (bottom-left): blink — eyes CLOSED, body identical to frame 0\n"
    "  - frame 3 (bottom-right): subtle exhale, eyes open, chest slightly\n"
    "    compressed (2-3 pixel difference, NOT a deflated chest)\n"
    "- DO NOT change the pose, the camera angle, the lighting, or the costume\n"
    "  between cells; this is an idle loop, not an action sequence\n"
    "- the four characters must be PIXEL-IDENTICAL except for eye state and\n"
    "  the subtle chest-breath delta — viewers should barely notice the change"
)

# v8: gestural-movement intensity. Visible per-frame change. The user explicitly
# requested this mode after observing that idle-breath loops are "boring — almost
# no change between frames". Distinct gestures with visible body motion.
PORTRAIT_LOOP_RULES_GESTURAL = (
    "PORTRAIT_LOOP_RULES (intensity: gestural-movement):\n"
    "- 2x2 grid of FOUR cells; each cell contains the SAME character at the\n"
    "  SAME framing, SAME camera angle, SAME costume, SAME lighting\n"
    "- the four cells show DIFFERENT GESTURES with VISIBLE per-frame change:\n"
    "  - frame 0 (top-left):  neutral resting pose, hands at sides, looking forward\n"
    "  - frame 1 (top-right): expressive HEAD/FACE gesture (eyebrow raise, smirk,\n"
    "    head tilt 5-10 degrees, OR open mouth mid-word)\n"
    "  - frame 2 (bottom-left): visible HAND/ARM gesture (point at viewer, raise\n"
    "    a hand to chin, gesticulate outward, or rotate-the-wrist tell)\n"
    "  - frame 3 (bottom-right): full POSTURE shift (lean forward, shrug shoulders,\n"
    "    cross arms, or shift weight to one side)\n"
    '- gestures must be CLEARLY visible at thumbnail size — no "barely notice"\n'
    "  variations; viewers should immediately see distinct frames\n"
    "- KEEP same character identity (face, hair, costume, accessories) across all\n"
    "  cells — only the gesture/pose changes\n"
    "- treat the 4 cells as 4 selected key-frames of a personality-driven character\n"
    "  loop, not 4 separate portraits"
)

# v8: action-loop intensity. Strong per-frame motion — character actively doing
# something across the 4 frames (not posing). For wizards casting spells,
# samurai with sword flourishes, dragons breathing fire, etc.
PORTRAIT_LOOP_RULES_ACTION = (
    "PORTRAIT_LOOP_RULES (intensity: action-loop):\n"
    "- 2x2 grid of FOUR cells; each cell contains the SAME character at the\n"
    "  SAME framing, SAME camera angle, SAME costume\n"
    "- the four cells show DISTINCT ACTION FRAMES of a continuous loop motion:\n"
    "  - frame 0 (top-left):  starting state of the action (hands lowered, calm)\n"
    "  - frame 1 (top-right): ramping up — partial gesture, energy gathering,\n"
    "    arms rising, mouth opening, eyes lighting up\n"
    "  - frame 2 (bottom-left): peak of the action — strongest pose, energy\n"
    "    visible (glow, sparks, motion blur), most extreme expression\n"
    "  - frame 3 (bottom-right): release/return — energy fading, posture relaxing,\n"
    "    transitioning back to start state\n"
    '- the action has a CLEAR subject described in the DESCRIPTION (e.g. "casting\n'
    '  a glowing spell", "sword flourish", "flame breath")\n'
    "- the 4 frames loop seamlessly: frame 3 transitions naturally back to frame 0\n"
    "- KEEP same character identity, same costume, same camera; the ACTION is\n"
    "  what changes\n"
    "- treat the 4 cells as a single short action cycle, not 4 separate portraits"
)

# Backwards-compat alias (older callers that don't specify intensity).
PORTRAIT_LOOP_RULES = PORTRAIT_LOOP_RULES_IDLE_BREATH

UNIVERSAL_NEGATIVE = (
    "NEGATIVE:\n"
    "- cropped body, head cut off, legs cut off, arms cut off\n"
    "- multiple characters, group shot, crowd scene\n"
    "- text overlays, captions, signatures, artist watermarks\n"
    "- white background, transparent background, gradient background, photographic background\n"
    "- visible audience, ring announcer, microphone in frame\n"
    "- nudity (wrestlers wear gear; this is a costuming style)"
)


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------
@dataclass
class PromptMetadata:
    """Reproducibility sidecar for any prompt build."""

    mode: str
    style_preset: str
    style_string: str | None = None
    archetype: str | None = None
    gimmick: str | None = None
    tier: str | None = None
    description: str = ""
    action: str | None = None
    grid_cols: int | None = None
    grid_rows: int | None = None
    seed: int = 0
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def resolve_style(preset: str, style_string: str | None) -> str:
    """Return the style fragment for the chosen preset, or the custom string."""
    if preset == "custom":
        if not style_string:
            raise ValueError("--style custom requires --style-string '<fragment>'")
        return style_string
    if preset not in STYLE_PRESETS:
        raise ValueError(
            f"unknown style preset {preset!r}. Choose from {sorted(list(STYLE_PRESETS.keys()) + ['custom'])}"
        )
    return STYLE_PRESETS[preset]


def resolve_archetype(archetype: str | None) -> str:
    """Return the archetype fragment, or empty if not set."""
    if archetype is None:
        return ""
    if archetype not in ARCHETYPES:
        raise ValueError(f"unknown archetype {archetype!r}. Choose from {sorted(ARCHETYPES)}.")
    return ARCHETYPES[archetype]


def resolve_gimmick(gimmick: str | None) -> str:
    """Return the gimmick fragment, or empty if not set."""
    if gimmick is None:
        return ""
    if gimmick not in GIMMICKS:
        raise ValueError(f"unknown gimmick {gimmick!r}. Choose from {sorted(GIMMICKS)}.")
    return GIMMICKS[gimmick]


def resolve_tier(tier: str | None) -> str:
    """Return the tier fragment, or empty if not set."""
    if tier is None:
        return ""
    if tier not in TIERS:
        raise ValueError(f"unknown tier {tier!r}. Choose from {sorted(TIERS)}.")
    return TIERS[tier]


def compose_portrait_prompt(meta: PromptMetadata) -> str:
    """Build the portrait-mode prompt string."""
    art = resolve_style(meta.style_preset, meta.style_string)
    arch = resolve_archetype(meta.archetype)
    gim = resolve_gimmick(meta.gimmick)
    tier = resolve_tier(meta.tier)

    parts: list[str] = []
    parts.append(f"ART_STYLE: {art}")
    if arch or gim:
        char_parts = [p for p in (arch, gim) if p]
        parts.append("CHAR_STYLE: " + ". ".join(char_parts) + ".")
    if tier:
        parts.append(f"TIER: {tier}")
    if meta.description:
        parts.append(f"DESCRIPTION: {meta.description}")
    parts.append(UNIVERSAL_RULES)
    parts.append(PORTRAIT_RULES)
    parts.append(UNIVERSAL_NEGATIVE)
    return "\n\n".join(parts)


def compose_portrait_loop_prompt(
    meta: PromptMetadata,
    loop_intensity: str = "idle-breath",
) -> str:
    """Build a portrait-loop prompt: 2x2 grid of subtle-to-aggressive variations.

    Args:
        meta: PromptMetadata bundle with style/archetype/description.
        loop_intensity: one of "idle-breath" (subtle breath+blink), "gestural-
            movement" (visible head/hand/posture gestures), or "action-loop"
            (full action cycle: cast spell, sword flourish, flame breath).

    Output: a single 1024x1024 image with 2x2 cells (512x512 each), each
    cell showing the same character with the per-intensity variation.
    Downstream extraction treats this as a 4-frame spritesheet.

    The user reported in v8 that pure idle-breath loops show "almost no change
    between frames — boring." Gestural-movement and action-loop modes were
    added for character-loop assets where the motion should be the point.
    """
    art = resolve_style(meta.style_preset, meta.style_string)
    arch = resolve_archetype(meta.archetype)
    gim = resolve_gimmick(meta.gimmick)
    tier = resolve_tier(meta.tier)

    if loop_intensity == "gestural-movement":
        rules_block = PORTRAIT_LOOP_RULES_GESTURAL
    elif loop_intensity == "action-loop":
        rules_block = PORTRAIT_LOOP_RULES_ACTION
    elif loop_intensity == "idle-breath":
        rules_block = PORTRAIT_LOOP_RULES_IDLE_BREATH
    else:
        raise ValueError(
            f"unknown loop_intensity {loop_intensity!r}. Choose: idle-breath, gestural-movement, action-loop."
        )

    parts: list[str] = []
    parts.append(f"ART_STYLE: {art}")
    if arch or gim:
        char_parts = [p for p in (arch, gim) if p]
        parts.append("CHAR_STYLE: " + ". ".join(char_parts) + ".")
    if tier:
        parts.append(f"TIER: {tier}")
    if meta.description:
        parts.append(f"DESCRIPTION: {meta.description}")
    parts.append(UNIVERSAL_RULES)
    parts.append(rules_block)
    parts.append(UNIVERSAL_NEGATIVE)
    return "\n\n".join(parts)


def compose_character_prompt(meta: PromptMetadata) -> str:
    """Phase A: build the reference character prompt (spritesheet mode)."""
    art = resolve_style(meta.style_preset, meta.style_string)
    arch = resolve_archetype(meta.archetype)
    gim = resolve_gimmick(meta.gimmick)

    parts: list[str] = []
    parts.append(f"ART_STYLE: {art}")
    if arch or gim:
        char_parts = [p for p in (arch, gim) if p]
        parts.append("CHAR_STYLE: " + ". ".join(char_parts) + ".")
    if meta.description:
        parts.append(f"DESCRIPTION: {meta.description}")
    parts.append(UNIVERSAL_RULES)
    parts.append(
        "REFERENCE_RULES:\n"
        "- this is a single reference character on a 1024x1024 canvas\n"
        "- the character occupies the central 70% of the canvas, full body\n"
        "- consistent rendering identity (this image will be used to anchor a multi-frame spritesheet)"
    )
    parts.append(UNIVERSAL_NEGATIVE)
    return "\n\n".join(parts)


def compose_spritesheet_prompt(meta: PromptMetadata) -> str:
    """Phase C: build the spritesheet generation prompt."""
    if meta.grid_cols is None or meta.grid_rows is None:
        raise ValueError("spritesheet prompt requires --grid CxR")
    if not meta.action:
        raise ValueError("spritesheet prompt requires --action")

    art = resolve_style(meta.style_preset, meta.style_string)
    arch = resolve_archetype(meta.archetype)
    gim = resolve_gimmick(meta.gimmick)

    frame_descs = ACTION_TEMPLATES.get(meta.action)
    total_frames = meta.grid_cols * meta.grid_rows

    parts: list[str] = []
    parts.append(f"ART_STYLE: {art}")
    if arch or gim:
        char_parts = [p for p in (arch, gim) if p]
        parts.append("CHAR_STYLE: " + ". ".join(char_parts) + ".")
    if meta.description:
        parts.append(f"DESCRIPTION: {meta.description}")

    grid_block = [
        "GRID_RULES:",
        f"- the canvas is divided into a {meta.grid_cols}x{meta.grid_rows} grid of cells",
        f"- place ONE frame of the character in each cell, performing: {meta.action}",
        "- frames must stay within their assigned cell; do not overflow grid lines",
        "- the character should appear at consistent scale across all cells",
    ]
    if frame_descs:
        for i in range(min(total_frames, len(frame_descs))):
            grid_block.append(f"- frame {i}: {frame_descs[i]}")
    parts.append("\n".join(grid_block))

    parts.append(UNIVERSAL_RULES)
    parts.append(UNIVERSAL_NEGATIVE)
    return "\n\n".join(parts)


def write_outputs(prompt: str, meta: PromptMetadata, output: Path, metadata_out: Path | None) -> None:
    """Write prompt text + optional metadata JSON sidecar."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(prompt, encoding="utf-8")
    logger.info("[prompt] %s written (%d chars)", output, len(prompt))

    if metadata_out is not None:
        metadata_out.parent.mkdir(parents=True, exist_ok=True)
        metadata_out.write_text(json.dumps(asdict(meta), indent=2), encoding="utf-8")
        logger.info("[prompt] %s metadata written", metadata_out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Shared flags across all build-* subcommands."""
    parser.add_argument(
        "--style",
        default="slay-the-spire-painted",
        help="Style preset name (or 'custom' with --style-string)",
    )
    parser.add_argument("--style-string", help="Free-form style fragment for --style custom")
    parser.add_argument("--archetype", help="Wrestler archetype (e.g., showman, powerhouse)")
    parser.add_argument("--gimmick", help="Gimmick type (e.g., heel, face, manager)")
    parser.add_argument("--tier", choices=["act1", "act2", "act3"], help="road-to-aew tier modifier")
    parser.add_argument("--description", default="", help="Free-text character description")
    parser.add_argument("--seed", type=int, default=0, help="Reproducibility seed (default 0)")
    parser.add_argument("--output", required=True, help="Path to write the assembled prompt text")
    parser.add_argument(
        "--metadata-out",
        help="Optional path to write a metadata JSON sidecar with slot fills + seed",
    )


def cmd_build_portrait(args: argparse.Namespace) -> int:
    meta = PromptMetadata(
        mode="portrait",
        style_preset=args.style,
        style_string=args.style_string,
        archetype=args.archetype,
        gimmick=args.gimmick,
        tier=args.tier,
        description=args.description,
        seed=args.seed,
    )
    try:
        prompt = compose_portrait_prompt(meta)
    except ValueError as e:
        logger.error("%s", e)
        return 2
    write_outputs(prompt, meta, Path(args.output), Path(args.metadata_out) if args.metadata_out else None)
    return 0


def cmd_build_portrait_loop(args: argparse.Namespace) -> int:
    meta = PromptMetadata(
        mode="portrait-loop",
        style_preset=args.style,
        style_string=args.style_string,
        archetype=args.archetype,
        gimmick=args.gimmick,
        tier=args.tier,
        description=args.description,
        action="idle-breath-blink",
        grid_cols=2,
        grid_rows=2,
        seed=args.seed,
    )
    try:
        prompt = compose_portrait_loop_prompt(meta)
    except ValueError as e:
        logger.error("%s", e)
        return 2
    write_outputs(prompt, meta, Path(args.output), Path(args.metadata_out) if args.metadata_out else None)
    return 0


def cmd_build_character(args: argparse.Namespace) -> int:
    meta = PromptMetadata(
        mode="character",
        style_preset=args.style,
        style_string=args.style_string,
        archetype=args.archetype,
        gimmick=args.gimmick,
        tier=args.tier,
        description=args.description,
        seed=args.seed,
    )
    try:
        prompt = compose_character_prompt(meta)
    except ValueError as e:
        logger.error("%s", e)
        return 2
    write_outputs(prompt, meta, Path(args.output), Path(args.metadata_out) if args.metadata_out else None)
    return 0


def cmd_build_spritesheet(args: argparse.Namespace) -> int:
    cols, rows = parse_grid(args.grid)
    meta = PromptMetadata(
        mode="spritesheet",
        style_preset=args.style,
        style_string=args.style_string,
        archetype=args.archetype,
        gimmick=args.gimmick,
        tier=args.tier,
        description=args.description,
        action=args.action,
        grid_cols=cols,
        grid_rows=rows,
        seed=args.seed,
    )
    try:
        prompt = compose_spritesheet_prompt(meta)
    except ValueError as e:
        logger.error("%s", e)
        return 2
    write_outputs(prompt, meta, Path(args.output), Path(args.metadata_out) if args.metadata_out else None)
    return 0


def parse_grid(grid: str) -> tuple[int, int]:
    """Parse '4x4' into (cols, rows). Validates format."""
    if "x" not in grid:
        raise ValueError(f"grid {grid!r} malformed. Use CxR format like '4x4'.")
    parts = grid.split("x")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"grid {grid!r} malformed. Use CxR format like '4x4'.")
    cols, rows = int(parts[0]), int(parts[1])
    if cols < 1 or rows < 1:
        raise ValueError(f"grid {grid!r} requires positive cols and rows.")
    return cols, rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    bp = sub.add_parser("build-portrait", help="Build portrait-mode prompt")
    _add_common_args(bp)
    bp.set_defaults(func=cmd_build_portrait)

    bpl = sub.add_parser(
        "build-portrait-loop",
        help="Build portrait-loop prompt (2x2 subtle breathing/blink idle)",
    )
    _add_common_args(bpl)
    bpl.set_defaults(func=cmd_build_portrait_loop)

    bc = sub.add_parser("build-character", help="Build Phase A reference character prompt")
    _add_common_args(bc)
    bc.set_defaults(func=cmd_build_character)

    bs = sub.add_parser("build-spritesheet", help="Build Phase C spritesheet prompt")
    _add_common_args(bs)
    bs.add_argument("--grid", required=True, help="Grid spec like '4x4' (cols x rows)")
    bs.add_argument("--action", required=True, help="Action label (walking, idle, attack-punch, etc.)")
    bs.set_defaults(func=cmd_build_spritesheet)

    return parser


def main(argv: list[str] | None = None) -> int:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(name)s] %(levelname)s: %(message)s",
            stream=sys.stderr,
        )
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
