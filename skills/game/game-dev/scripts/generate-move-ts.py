#!/usr/bin/env python3
"""Generate TypeScript wrestling move functions from BVH mocap data.

Converts motion-pipeline JSON output (root trajectory + contact frames) into
keyframe-interpolated TypeScript MoveFrame functions compatible with
road-to-aew's wrestlingMoves.ts interface.

Usage:
    generate-move-ts.py BVH MOVE_NAME [--scale S] [--contact-bones B...] \\
        [--num-keyframes N] [--hip-bone NAME] [--tracking-bone NAME]

When --tracking-bone is specified (e.g. RightHand), the generator tracks that
bone's world-space position for attacker offsets instead of the root/hip bone.
Root orientation (hip Euler angles) is always sourced from --hip-bone.
Impact detection becomes velocity-based: the strike impact is the moment the
tracking bone's velocity magnitude peaks and then rapidly decelerates.

The script imports motion-pipeline.py as a module directly to avoid the
5-frame stdout truncation applied by the decompose CLI command.
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import sys
import types
from datetime import date
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Motion pipeline import (importlib to avoid CLI 5-frame truncation)
# ---------------------------------------------------------------------------

_PIPELINE_PATH = Path(__file__).parent / "motion-pipeline.py"


def _load_pipeline() -> types.ModuleType:
    """Import motion-pipeline.py as a module via importlib.

    The module uses dataclasses, so it must be registered in sys.modules
    before exec_module runs, or the dataclass decorator cannot resolve
    the module's __dict__.
    """
    spec = importlib.util.spec_from_file_location("motion_pipeline", _PIPELINE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load motion pipeline from {_PIPELINE_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["motion_pipeline"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Move name helpers
# ---------------------------------------------------------------------------


def kebab_to_pascal(name: str) -> str:
    """Convert kebab-case to PascalCase: 'roundhouse-kick' -> 'RoundhouseKick'."""
    return "".join(word.capitalize() for word in name.split("-"))


def kebab_to_upper_snake(name: str) -> str:
    """Convert kebab-case to UPPER_SNAKE: 'roundhouse-kick' -> 'ROUNDHOUSE_KICK'."""
    return name.upper().replace("-", "_")


# ---------------------------------------------------------------------------
# Keyframe extraction
# ---------------------------------------------------------------------------


def _find_contact_window(
    contact_data: dict,
    bone_names: list[str],
    total_frames: int,
) -> tuple[float, float] | None:
    """Detect the first sustained contact window across all requested bones.

    Returns (start_progress, end_progress) or None if no contact found.

    A "sustained" window requires at least 3 consecutive contact frames on
    any of the specified bones — single-frame spikes are ignored.
    """
    bones_info = contact_data.get("bones", {})

    best_start: int | None = None
    best_end: int | None = None

    for bone in bone_names:
        if bone not in bones_info:
            continue
        frames: list[int] = bones_info[bone]["contact_frames"]
        if len(frames) < 3:
            continue

        # Find first run of 3+ consecutive frames
        run_start = frames[0]
        prev = frames[0]
        run_len = 1

        for f in frames[1:]:
            if f == prev + 1:
                run_len += 1
                if run_len >= 3:
                    run_end = f
                    if best_start is None or run_start < best_start:
                        best_start = run_start
                        best_end = run_end
                    break
            else:
                run_start = f
                run_len = 1
            prev = f

    if best_start is None or best_end is None:
        return None

    return (best_start / total_frames, best_end / total_frames)


def _find_velocity_impact_window(
    velocities: np.ndarray,
    num_frames: int,
    window_fraction: float = 0.05,
) -> tuple[float, float]:
    """Detect impact window from bone velocity magnitude.

    The impact moment for a strike is where the tracking limb peaks in velocity
    and then rapidly decelerates (collision). The window spans from just before
    peak deceleration for window_fraction of the total clip.

    Algorithm:
      1. Compute per-frame velocity magnitude.
      2. Find the frame with maximum magnitude (peak of the strike).
      3. After the peak, find where speed drops by >50% — that is the impact
         contact frame.
      4. If no clear drop exists, fall back to the midpoint.

    Args:
        velocities: Shape (num_frames, 1, 3) velocity array from bone_velocities.
        num_frames: Total frame count of the clip.
        window_fraction: Width of impact window as fraction of total clip (default 5%).

    Returns:
        (start_progress, end_progress) tuple, both in [0, 1].
    """
    # Shape: (num_frames, 1, 3) -> (num_frames,)
    speed = np.linalg.norm(velocities[:, 0, :], axis=-1)

    peak_frame = int(np.argmax(speed))
    peak_speed = float(speed[peak_frame])

    # Search for >50% deceleration after peak
    impact_frame = peak_frame
    if peak_frame < num_frames - 1:
        threshold = peak_speed * 0.5
        for f in range(peak_frame + 1, min(peak_frame + max(int(num_frames * 0.2), 5), num_frames)):
            if float(speed[f]) < threshold:
                impact_frame = f
                break
        else:
            # No clear drop found: use a few frames after peak
            impact_frame = min(peak_frame + max(int(num_frames * 0.03), 2), num_frames - 1)

    # Fallback: if peak is at very start or no meaningful velocity, use midpoint
    if peak_speed < 1e-4 or peak_frame == 0:
        impact_frame = num_frames // 2

    window_frames = max(int(num_frames * window_fraction), 3)
    start = impact_frame / num_frames
    end = min((impact_frame + window_frames) / num_frames, 1.0)
    return (start, end)


def _extract_bone_positions(
    motion: object,
    bone_name: str,
) -> tuple[list[list[float]], np.ndarray]:
    """Extract world-space positions and velocities for a named bone.

    Args:
        motion: Motion object from motion-pipeline (has hierarchy, bone_positions,
                bone_velocities methods).
        bone_name: Bone name to track (e.g. 'RightHand').

    Returns:
        Tuple of (positions as list[list[float]], velocities as np.ndarray shape (F,1,3)).

    Raises:
        ValueError: If bone_name is not found in the skeleton.
    """
    bone_idx = motion.hierarchy.index(bone_name)  # raises ValueError if missing
    # bone_positions returns (num_frames, num_bones, 3)
    pos_array = motion.bone_positions([bone_idx])  # (F, 1, 3)
    vel_array = motion.bone_velocities([bone_idx])  # (F, 1, 3)
    positions: list[list[float]] = pos_array[:, 0, :].tolist()
    return positions, vel_array


def _sample_keyframes(
    positions: list[list[float]],
    hip_euler: list[list[float]],
    num_keyframes: int,
) -> list[tuple[float, list[float], list[float]]]:
    """Sample motion arrays at N evenly-spaced progress values.

    Args:
        positions: Root trajectory positions [[x,y,z], ...] — full frame count.
        hip_euler: Hip Euler ZYX degrees [[z,y,x], ...] — full frame count.
        num_keyframes: Number of keyframes to sample (including 0.0 and 1.0).

    Returns:
        List of (progress, [x,y,z], [rot_z,rot_y,rot_x]) tuples.
    """
    total_frames = len(positions)

    # Normalize: subtract initial position so the move starts at origin
    origin = positions[0]
    ox, oy, oz = origin[0], origin[1], origin[2]

    keyframes: list[tuple[float, list[float], list[float]]] = []

    for i in range(num_keyframes):
        progress = i / (num_keyframes - 1) if num_keyframes > 1 else 0.0
        # Map progress [0,1] -> frame index [0, total_frames-1]
        frame_idx = min(round(progress * (total_frames - 1)), total_frames - 1)

        pos = positions[frame_idx]
        euler = hip_euler[frame_idx]

        # Normalised offsets (origin at first frame)
        att_x = pos[0] - ox
        att_y = pos[1] - oy
        att_z = pos[2] - oz

        # Convert degrees to radians for Three.js
        rot_z = math.radians(euler[0])
        rot_y = math.radians(euler[1])
        rot_x = math.radians(euler[2])

        keyframes.append((progress, [att_x, att_y, att_z], [rot_x, rot_y, rot_z]))

    return keyframes


def _compute_defender_keyframes(
    attacker_keyframes: list[tuple[float, list[float], list[float]]],
    impact_window: tuple[float, float] | None,
    impact_direction: list[float] | None = None,
    impact_magnitude: float | None = None,
) -> list[list[float]]:
    """Compute defender reaction offsets/rotations for each keyframe.

    Two reaction models are available:

    Throw model (impact_direction is None):
      - Before impact: slight lean-in tracking attacker approach
      - At impact: sharp backward displacement + backward rotation
      - Post-impact: ease down to mat level

    Strike model (impact_direction provided):
      - Pre-impact: defender is stationary (waiting to be hit)
      - At impact: sharp displacement along the strike direction
      - Post-impact: ease recovery
      The push magnitude scales with impact_magnitude, capped at 1.5m backward
      and 0.8m upward.

    Args:
        attacker_keyframes: Output from _sample_keyframes.
        impact_window: (start_progress, end_progress) or None.
        impact_direction: Normalised XYZ push direction for strike moves, or None.
        impact_magnitude: Velocity magnitude at impact (m/s) for strike scaling.

    Returns:
        List of [defOffX, defOffY, defOffZ, defRotX, defRotY, defRotZ] per keyframe.
    """
    imp_start = impact_window[0] if impact_window else 0.5
    imp_end = impact_window[1] if impact_window else 0.55

    is_strike = impact_direction is not None

    if is_strike:
        # Strike: scale push with velocity magnitude, capped at max values
        MAX_BACKWARD = 1.5
        MAX_UPWARD = 0.8
        ROT_PEAK = 0.35

        # Use velocity magnitude to set scale (normalised: 10 m/s = full push)
        scale = min((impact_magnitude or 5.0) / 10.0, 1.0)
        dx, dy, dz = impact_direction[0], impact_direction[1], impact_direction[2]

        # Backward push: along strike direction, capped
        push_x = dx * MAX_BACKWARD * scale
        push_y = abs(dy) * MAX_UPWARD * scale  # upward component always positive
        push_z = dz * MAX_BACKWARD * scale
    else:
        # Throw model: fixed amplitudes
        push_x = 0.0
        push_y = 0.8
        push_z = -1.2
        ROT_PEAK = 0.4

    results: list[list[float]] = []

    for progress, att_pos, _att_rot in attacker_keyframes:
        if is_strike:
            if progress < imp_start:
                # Pre-impact: defender stationary
                def_x = 0.0
                def_y = 0.0
                def_z = 0.0
                def_rot_x = 0.0
                def_rot_y = 0.0
                def_rot_z = 0.0
            elif progress <= imp_end:
                # Impact window: ramp up to peak push
                window = max(imp_end - imp_start, 1e-6)
                t = (progress - imp_start) / window
                ease = math.sin(t * math.pi / 2)
                def_x = push_x * ease
                def_y = push_y * ease
                def_z = push_z * ease
                def_rot_x = -ROT_PEAK * ease  # backward lean
                def_rot_y = 0.0
                def_rot_z = 0.0
            else:
                # Post-impact: ease recovery
                t = (progress - imp_end) / max(1.0 - imp_end, 1e-6)
                ease = 1.0 - (t * t)
                def_x = push_x * ease
                def_y = push_y * ease * 0.3
                def_z = push_z * ease
                def_rot_x = -ROT_PEAK * ease
                def_rot_y = 0.0
                def_rot_z = 0.0
        else:
            if progress < imp_start:
                # Pre-impact: subtle backward lean tracking attacker Z
                t = progress / max(imp_start, 1e-6)
                ease = t * t
                def_z = -abs(att_pos[2]) * 0.1 * ease
                def_y = 0.0
                def_x = 0.0
                def_rot_x = 0.05 * ease
                def_rot_y = 0.0
                def_rot_z = 0.0
            elif progress <= imp_end:
                # Impact window: ramp up to peak then hold
                window = max(imp_end - imp_start, 1e-6)
                t = (progress - imp_start) / window
                ease = math.sin(t * math.pi / 2)
                def_z = push_z * ease
                def_y = push_y * ease
                def_x = 0.0
                def_rot_x = -ROT_PEAK * ease
                def_rot_y = 0.0
                def_rot_z = 0.0
            else:
                # Post-impact: ease down to mat
                t = (progress - imp_end) / max(1.0 - imp_end, 1e-6)
                ease = 1.0 - (t * t)
                def_z = push_z * ease
                def_y = push_y * ease * 0.3
                def_x = 0.0
                def_rot_x = -ROT_PEAK * ease
                def_rot_y = 0.0
                def_rot_z = 0.0

        results.append([def_x, def_y, def_z, def_rot_x, def_rot_y, def_rot_z])

    return results


# ---------------------------------------------------------------------------
# TypeScript code generation
# ---------------------------------------------------------------------------

_TS_HEADER = """\
// Generated from {bvh_name} on {today}
// Keyframes: {num_keyframes}, Impact window: {impact_start:.3f}-{impact_end:.3f}
//
// Attacker columns: offsetX, offsetY, offsetZ (metres), rotationX, rotationY, rotationZ (radians)
// Defender columns: offsetX, offsetY, offsetZ (metres), rotationX, rotationY, rotationZ (radians)
//
// Generated by scripts/generate-move-ts.py — do not hand-edit; re-run generator for changes.

import type {{ MoveFrame, WrestlerTransform }} from "./wrestlingMoves";

"""

_KEYFRAME_CONST = """\
const {const_name}_KEYFRAMES = [
  // prettier-ignore
  // [progress, attOffX, attOffY, attOffZ, attRotX, attRotY, attRotZ, defOffX, defOffY, defOffZ, defRotX, defRotY, defRotZ]
{rows}
] as const;

"""

_FUNCTION_BODY = """\
export function get{pascal_name}(progress: number): MoveFrame {{
  // Find the two surrounding keyframes by scanning for the bracket pair.
  const kf = {const_name}_KEYFRAMES;
  let lo = 0;
  let hi = kf.length - 1;

  for (let i = 0; i < kf.length - 1; i++) {{
    if (kf[i][0] <= progress && progress <= kf[i + 1][0]) {{
      lo = i;
      hi = i + 1;
      break;
    }}
  }}

  const t0 = kf[lo][0] as number;
  const t1 = kf[hi][0] as number;
  const span = t1 - t0;
  const t = span > 0 ? (progress - t0) / span : 0;

  function lerp(a: number, b: number): number {{
    return a + (b - a) * t;
  }}

  const attacker: WrestlerTransform = {{
    offsetX: lerp(kf[lo][1] as number, kf[hi][1] as number),
    offsetY: lerp(kf[lo][2] as number, kf[hi][2] as number),
    offsetZ: lerp(kf[lo][3] as number, kf[hi][3] as number),
    rotationX: lerp(kf[lo][4] as number, kf[hi][4] as number),
    rotationY: lerp(kf[lo][5] as number, kf[hi][5] as number),
    rotationZ: lerp(kf[lo][6] as number, kf[hi][6] as number),
  }};

  const defender: WrestlerTransform = {{
    offsetX: lerp(kf[lo][7] as number, kf[hi][7] as number),
    offsetY: lerp(kf[lo][8] as number, kf[hi][8] as number),
    offsetZ: lerp(kf[lo][9] as number, kf[hi][9] as number),
    rotationX: lerp(kf[lo][10] as number, kf[hi][10] as number),
    rotationY: lerp(kf[lo][11] as number, kf[hi][11] as number),
    rotationZ: lerp(kf[lo][12] as number, kf[hi][12] as number),
  }};

  const isImpact = progress >= {impact_start:.4f} && progress <= {impact_end:.4f};

  return {{ attacker, defender, isImpact }};
}}
"""


def _fmt_float(v: float) -> str:
    """Format a float for TypeScript keyframe arrays: 4 significant digits, no trailing zeros."""
    if v == 0.0:
        return "0"
    return f"{v:.4f}".rstrip("0").rstrip(".")


def generate_typescript(
    bvh_name: str,
    move_name: str,
    attacker_keyframes: list[tuple[float, list[float], list[float]]],
    defender_frames: list[list[float]],
    impact_window: tuple[float, float] | None,
) -> str:
    """Render the full TypeScript source for one wrestling move function.

    Args:
        bvh_name: Source BVH filename stem (for header comment).
        move_name: Kebab-case move name (e.g. 'roundhouse-kick').
        attacker_keyframes: [(progress, [x,y,z], [rx,ry,rz]), ...]
        defender_frames: [[defX,defY,defZ,defRx,defRy,defRz], ...] — same length.
        impact_window: (start, end) progress or None.

    Returns:
        Valid TypeScript source string.
    """
    pascal_name = kebab_to_pascal(move_name)
    const_name = kebab_to_upper_snake(move_name)
    today = date.today().isoformat()
    imp_start = impact_window[0] if impact_window else 0.5
    imp_end = impact_window[1] if impact_window else 0.55

    header = _TS_HEADER.format(
        bvh_name=bvh_name,
        today=today,
        num_keyframes=len(attacker_keyframes),
        impact_start=imp_start,
        impact_end=imp_end,
    )

    rows: list[str] = []
    for (progress, att_pos, att_rot), def_vals in zip(attacker_keyframes, defender_frames):
        vals = [progress] + att_pos + att_rot + def_vals
        row_str = ", ".join(_fmt_float(v) for v in vals)
        rows.append(f"  [{row_str}],")

    const_block = _KEYFRAME_CONST.format(
        const_name=const_name,
        rows="\n".join(rows),
    )

    func_block = _FUNCTION_BODY.format(
        pascal_name=pascal_name,
        const_name=const_name,
        impact_start=imp_start,
        impact_end=imp_end,
    )

    return header + const_block + func_block


# ---------------------------------------------------------------------------
# Validation: minimal TypeScript syntax checks
# ---------------------------------------------------------------------------


def _validate_typescript(ts_source: str, output_path: Path) -> list[str]:
    """Run basic structural checks on generated TypeScript source.

    Returns list of error strings (empty = valid).
    """
    errors: list[str] = []

    # Must have required structural elements
    required = [
        "as const;",
        "export function get",
        "(progress: number): MoveFrame",
        "const attacker: WrestlerTransform",
        "const defender: WrestlerTransform",
        "return { attacker, defender, isImpact };",
    ]
    for req in required:
        if req not in ts_source:
            errors.append(f"Missing required element: {req!r}")

    # Balanced braces
    opens = ts_source.count("{")
    closes = ts_source.count("}")
    if opens != closes:
        errors.append(f"Unbalanced braces: {{ count={opens}, }} count={closes}")

    # Balanced brackets
    sq_opens = ts_source.count("[")
    sq_closes = ts_source.count("]")
    if sq_opens != sq_closes:
        errors.append(f"Unbalanced brackets: [ count={sq_opens}, ] count={sq_closes}")

    return errors


# ---------------------------------------------------------------------------
# Summary output
# ---------------------------------------------------------------------------


def _print_summary(
    bvh_path: Path,
    move_name: str,
    num_keyframes: int,
    impact_window: tuple[float, float] | None,
    attacker_keyframes: list[tuple[float, list[float], list[float]]],
    output_path: Path,
    validation_errors: list[str],
    tracking_bone: str | None = None,
    impact_mode: str = "height",
) -> None:
    """Print a human-readable summary to stderr."""
    positions = [kf[1] for kf in attacker_keyframes]
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    zs = [p[2] for p in positions]

    print("\n=== generate-move-ts summary ===", file=sys.stderr)
    print(f"  BVH source   : {bvh_path}", file=sys.stderr)
    print(f"  Move name    : {move_name}", file=sys.stderr)
    print(f"  Keyframes    : {num_keyframes}", file=sys.stderr)
    print(f"  Tracking bone: {tracking_bone or 'root (hip)'}", file=sys.stderr)
    print(f"  Impact mode  : {impact_mode}", file=sys.stderr)
    if impact_window:
        print(f"  Impact window: {impact_window[0]:.3f} - {impact_window[1]:.3f}", file=sys.stderr)
    else:
        print("  Impact window: none detected (using default 0.500-0.550)", file=sys.stderr)
    print(f"  Traj X range : [{min(xs):.4f}, {max(xs):.4f}] m", file=sys.stderr)
    print(f"  Traj Y range : [{min(ys):.4f}, {max(ys):.4f}] m", file=sys.stderr)
    print(f"  Traj Z range : [{min(zs):.4f}, {max(zs):.4f}] m", file=sys.stderr)
    print(f"  Output       : {output_path}", file=sys.stderr)
    if validation_errors:
        print(f"  VALIDATION   : FAILED ({len(validation_errors)} error(s))", file=sys.stderr)
        for e in validation_errors:
            print(f"    - {e}", file=sys.stderr)
    else:
        print("  Validation   : OK", file=sys.stderr)
    print(file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate-move-ts",
        description="Convert BVH mocap to TypeScript MoveFrame function for road-to-aew.",
    )
    parser.add_argument("bvh", type=Path, help="Path to .bvh mocap file.")
    parser.add_argument(
        "move_name",
        metavar="MOVE_NAME",
        help="Kebab-case move name (e.g. roundhouse-kick). Used in TS identifiers.",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=0.01,
        help="Position scale factor (default 0.01 for cm-to-metre conversion).",
    )
    parser.add_argument(
        "--contact-bones",
        nargs="+",
        default=["LeftToeBase", "RightToeBase", "LeftHand", "RightHand"],
        metavar="BONE",
        help="Bone names used for impact detection (default: LeftToeBase RightToeBase LeftHand RightHand).",
    )
    parser.add_argument(
        "--num-keyframes",
        type=int,
        default=12,
        metavar="N",
        help="Number of sampled keyframes in the TS output (default 12).",
    )
    parser.add_argument(
        "--hip-bone",
        default="Hips",
        metavar="NAME",
        help="Name of the hip/root bone for trajectory extraction (default: Hips).",
    )
    parser.add_argument(
        "--tracking-bone",
        default=None,
        metavar="NAME",
        help=(
            "Bone name for limb tracking (e.g. RightHand). When specified, the attacker's "
            "offsetX/Y/Z follows this bone's world-space trajectory instead of the root. "
            "Impact detection switches to velocity-based mode. Root bone still drives rotations."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write TypeScript to FILE in addition to printing to stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for generate-move-ts.

    Returns:
        0 on success, 1 on error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    bvh_path: Path = args.bvh
    if not bvh_path.is_file():
        print(f"Error: BVH file not found: {bvh_path}", file=sys.stderr)
        return 1

    if args.num_keyframes < 2:
        print("Error: --num-keyframes must be at least 2.", file=sys.stderr)
        return 1

    # Load motion pipeline module
    try:
        pipeline = _load_pipeline()
    except ImportError as e:
        print(f"Error loading motion pipeline: {e}", file=sys.stderr)
        return 1

    # Load and decompose BVH
    try:
        motion = pipeline.load_bvh(bvh_path, scale=args.scale)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading BVH: {e}", file=sys.stderr)
        return 1

    try:
        decomp = pipeline.decompose(motion, hip_name=args.hip_bone)
    except ValueError as e:
        print(f"Error in decompose: {e}", file=sys.stderr)
        return 1

    # Full-resolution hip Euler (always from root/hip bone, drives rotations)
    hip_euler: list[list[float]] = decomp["per_joint_euler_zyx_degrees"][args.hip_bone]

    # Determine position source and impact detection mode
    impact_window: tuple[float, float] | None = None
    impact_direction: list[float] | None = None
    impact_magnitude: float | None = None
    impact_mode = "height"

    if args.tracking_bone:
        # Limb tracking: use the specified bone's world-space position
        tracking_name = args.tracking_bone
        available_bones = set(motion.hierarchy.bone_names)
        if tracking_name not in available_bones:
            print(
                f"Error: --tracking-bone '{tracking_name}' not found in skeleton. "
                f"Available bones: {sorted(available_bones)}",
                file=sys.stderr,
            )
            return 1

        try:
            positions, vel_array = _extract_bone_positions(motion, tracking_name)
        except ValueError as e:
            print(f"Error extracting tracking bone positions: {e}", file=sys.stderr)
            return 1

        # Velocity-based impact detection
        impact_mode = "velocity"
        impact_window = _find_velocity_impact_window(vel_array, motion.num_frames)

        # Compute impact direction from velocity vector at impact frame
        impact_frame = int(impact_window[0] * motion.num_frames)
        vel_at_impact = vel_array[impact_frame, 0, :]  # (3,)
        speed_at_impact = float(np.linalg.norm(vel_at_impact))
        if speed_at_impact > 1e-6:
            norm_dir = (vel_at_impact / speed_at_impact).tolist()
            impact_direction = [float(v) for v in norm_dir]
            impact_magnitude = speed_at_impact
        else:
            # Zero-velocity fallback: push straight back
            impact_direction = [0.0, 0.0, -1.0]
            impact_magnitude = 1.0
    else:
        # Default: track root/hip bone trajectory
        positions = decomp["root_trajectory"]["positions"]

        # Height-based contact detection
        available_bones = set(motion.hierarchy.bone_names)
        contact_bones = [b for b in args.contact_bones if b in available_bones]
        missing = [b for b in args.contact_bones if b not in available_bones]
        if missing:
            print(
                f"Warning: contact bones not found in skeleton, skipping: {missing}",
                file=sys.stderr,
            )
        if not contact_bones:
            print("Warning: no contact bones available; impact window will use default.", file=sys.stderr)

        contact_data: dict = {"bones": {}, "total_frames": motion.num_frames}
        if contact_bones:
            try:
                contact_data = pipeline.extract_contacts(motion, bone_names=contact_bones)
            except ValueError as e:
                print(f"Warning: contact extraction failed: {e}", file=sys.stderr)

        impact_window = _find_contact_window(contact_data, contact_bones, motion.num_frames)

    # Sample keyframes from resolved positions + hip rotations
    attacker_keyframes = _sample_keyframes(positions, hip_euler, args.num_keyframes)

    # Compute defender reaction (strike model if tracking bone used)
    defender_frames = _compute_defender_keyframes(
        attacker_keyframes,
        impact_window,
        impact_direction=impact_direction,
        impact_magnitude=impact_magnitude,
    )

    # Generate TypeScript
    ts_source = generate_typescript(
        bvh_name=bvh_path.name,
        move_name=args.move_name,
        attacker_keyframes=attacker_keyframes,
        defender_frames=defender_frames,
        impact_window=impact_window,
    )

    # Validate
    output_path = args.output or Path("/dev/stdout")
    validation_errors = _validate_typescript(ts_source, output_path)

    # Print TypeScript to stdout
    print(ts_source)

    # Optionally write to file
    if args.output is not None:
        args.output.write_text(ts_source)

    # Print summary to stderr
    _print_summary(
        bvh_path=bvh_path,
        move_name=args.move_name,
        num_keyframes=args.num_keyframes,
        impact_window=impact_window,
        attacker_keyframes=attacker_keyframes,
        output_path=output_path,
        validation_errors=validation_errors,
        tracking_bone=args.tracking_bone,
        impact_mode=impact_mode,
    )

    return 1 if validation_errors else 0


if __name__ == "__main__":
    sys.exit(main())
