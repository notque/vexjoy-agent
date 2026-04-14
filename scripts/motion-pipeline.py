#!/usr/bin/env python3
"""Motion pipeline CLI for game animation data processing.

Standalone CPU-only implementation of the motion data processing pipeline
inspired by Meta's ai4animationpy framework (CC BY-NC 4.0).

All ai4animationpy modules (Animation, Import, IK, Math) require PyTorch at
import time via Math/Tensor.py -- even the NumPy backend path. This script
replicates the key algorithms using only numpy and scipy so the pipeline
runs on hardware without a GPU.

Usage:
    motion-pipeline import-bvh FILE [--scale S] [--fps FPS]
    motion-pipeline extract-contacts FILE --bones B... [--height H] [--vel V]
    motion-pipeline decompose FILE [--hip JOINT]
    motion-pipeline blend FILE1 FILE2 [--alpha A]
    motion-pipeline solve-ik FILE --chain ROOT:TIP [--target X,Y,Z]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.spatial.transform import Rotation as ScipyRotation

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Hierarchy:
    """Bone hierarchy: names and parent indices."""

    bone_names: list[str]
    parent_indices: list[int]  # -1 for root

    def index(self, name: str) -> int:
        """Return bone index by name, raises ValueError if not found."""
        return self.bone_names.index(name)

    def indices(self, names: list[str]) -> list[int]:
        """Return indices for a list of bone names."""
        return [self.index(n) for n in names]


@dataclass
class Motion:
    """Core motion data structure.

    Attributes:
        name: Clip identifier (typically filename stem).
        hierarchy: Bone names and parent relationships.
        frames: Global transforms [num_frames, num_joints, 4, 4].
        framerate: Frames per second.
    """

    name: str
    hierarchy: Hierarchy
    frames: np.ndarray  # (F, J, 4, 4) float32
    framerate: float

    @property
    def num_frames(self) -> int:
        return self.frames.shape[0]

    @property
    def num_joints(self) -> int:
        return self.frames.shape[1]

    @property
    def total_time(self) -> float:
        return (self.num_frames - 1) / self.framerate

    @property
    def delta_time(self) -> float:
        return 1.0 / self.framerate

    def bone_positions(self, bone_indices: list[int] | None = None) -> np.ndarray:
        """Extract world-space positions for selected bones.

        Returns array of shape (num_frames, num_bones, 3).

        Note: Uses two-step indexing (frames[:, idx][:, :, :3, 3]) rather than
        frames[:, idx, :3, 3] to avoid numpy advanced-indexing axis transposition
        when idx is a list and a scalar index appears on a later axis.
        """
        idx = bone_indices if bone_indices is not None else list(range(self.num_joints))
        return self.frames[:, idx][:, :, :3, 3]

    def bone_velocities(self, bone_indices: list[int] | None = None) -> np.ndarray:
        """Compute per-frame velocities (finite difference of positions).

        Returns array of shape (num_frames, num_bones, 3).
        """
        positions = self.bone_positions(bone_indices)
        velocities = np.zeros_like(positions)
        dt = self.delta_time
        # Central difference for interior frames
        velocities[1:-1] = (positions[2:] - positions[:-2]) / (2.0 * dt)
        # Forward/backward at boundaries
        velocities[0] = (positions[1] - positions[0]) / dt
        velocities[-1] = (positions[-1] - positions[-2]) / dt
        return velocities

    def summary(self) -> dict:
        """Return human-readable summary dict."""
        positions = self.bone_positions()
        root_pos = positions[:, 0, :]  # assume bone[0] is root
        return {
            "name": self.name,
            "num_frames": self.num_frames,
            "num_joints": self.num_joints,
            "framerate": self.framerate,
            "total_time_seconds": round(self.total_time, 3),
            "bones": self.hierarchy.bone_names,
            "root_trajectory": {
                "x_range": [round(float(root_pos[:, 0].min()), 3), round(float(root_pos[:, 0].max()), 3)],
                "y_range": [round(float(root_pos[:, 1].min()), 3), round(float(root_pos[:, 1].max()), 3)],
                "z_range": [round(float(root_pos[:, 2].min()), 3), round(float(root_pos[:, 2].max()), 3)],
            },
        }


# ---------------------------------------------------------------------------
# BVH Parser (adapted from ai4animationpy BVHImporter.py)
# ---------------------------------------------------------------------------

_CHANNELMAP = {"Xrotation": "x", "Yrotation": "y", "Zrotation": "z"}


def _euler_to_rotation_matrix(angles_deg: np.ndarray, order: str) -> np.ndarray:
    """Convert Euler angles (degrees) to 3x3 rotation matrices.

    Args:
        angles_deg: Shape (..., 3) array of Euler angles in degrees.
        order: Axis order string, e.g. 'zyx'.

    Returns:
        Shape (..., 3, 3) rotation matrices.
    """
    orig_shape = angles_deg.shape[:-1]
    flat = angles_deg.reshape(-1, 3)
    rot = ScipyRotation.from_euler(order.upper(), flat, degrees=True)
    matrices = rot.as_matrix().astype(np.float32)
    return matrices.reshape(orig_shape + (3, 3))


def load_bvh(path: str | Path, scale: float = 1.0) -> Motion:
    """Parse a BVH file into a Motion object.

    Implements the same parsing logic as ai4animationpy BVHImporter.BVH,
    but depends only on numpy + scipy (no PyTorch).

    Args:
        path: Path to .bvh file.
        scale: Uniform scale applied to all positions (use 0.01 to convert
               cm mocap data to meters).

    Returns:
        Motion object with global transform matrices.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the BVH file is malformed.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"BVH file not found: {path}")

    names: list[str] = []
    offsets_list: list[list[float]] = []
    parents: list[int] = []
    channel_counts: list[int] = []

    active = -1
    channels: int | None = None
    order: str | None = None
    framerate: float | None = None
    positions: np.ndarray | None = None
    rotations: np.ndarray | None = None
    frame_index = 0

    with open(path) as fh:
        for line in fh:
            if "HIERARCHY" in line or "MOTION" in line:
                continue

            rmatch = re.match(r"\s*ROOT\s+(.+?)\s*$", line)
            if rmatch:
                names.append(rmatch.group(1))
                offsets_list.append([0.0, 0.0, 0.0])
                parents.append(active)
                channel_counts.append(0)
                active = len(parents) - 1
                continue

            if "{" in line:
                continue

            if "}" in line:
                if active != -1:
                    active = parents[active]
                continue

            offmatch = re.match(r"\s*OFFSET\s+([\-\d\.eE\+]+)\s+([\-\d\.eE\+]+)\s+([\-\d\.eE\+]+)", line)
            if offmatch:
                offsets_list[active] = [float(x) for x in offmatch.groups()]
                continue

            chanmatch = re.match(r"\s*CHANNELS\s+(\d+)", line)
            if chanmatch:
                n_channels = int(chanmatch.group(1))
                channel_counts[active] = n_channels
                if order is None:
                    start = 0 if n_channels == 3 else 3
                    parts = line.split()[2 + start : 2 + start + 3]
                    if all(p in _CHANNELMAP for p in parts):
                        order = "".join(_CHANNELMAP[p] for p in parts)
                continue

            jmatch = re.match(r"\s*JOINT\s+(.+?)\s*$", line)
            if jmatch:
                names.append(jmatch.group(1))
                offsets_list.append([0.0, 0.0, 0.0])
                parents.append(active)
                channel_counts.append(0)
                active = len(parents) - 1
                continue

            if "End Site" in line:
                # End sites are leaf markers; skip (no channels to parse)
                parent_name = names[active] if active != -1 else "End"
                site_name = f"{parent_name}Site"
                suffix = 1
                while site_name in names:
                    suffix += 1
                    site_name = f"{parent_name}Site{suffix}"
                names.append(site_name)
                offsets_list.append([0.0, 0.0, 0.0])
                parents.append(active)
                channel_counts.append(0)
                active = len(parents) - 1
                continue

            fmatch = re.match(r"\s*Frames:\s+(\d+)", line)
            if fmatch:
                fnum = int(fmatch.group(1))
                offsets = np.array(offsets_list, dtype=np.float32)
                # positions broadcast: each frame starts from bone offsets
                positions = np.tile(offsets[np.newaxis], (fnum, 1, 1))
                rotations = np.zeros((fnum, len(names), 3), dtype=np.float32)
                continue

            fmatch = re.match(r"\s*Frame Time:\s+([\d\.eE\+\-]+)", line)
            if fmatch:
                framerate = 1.0 / float(fmatch.group(1))
                continue

            dmatch = line.strip().split()
            if dmatch and positions is not None:
                try:
                    data_block = np.array([float(x) for x in dmatch], dtype=np.float32)
                except ValueError:
                    continue

                cursor = 0
                for joint_idx, num_ch in enumerate(channel_counts):
                    if num_ch == 0:
                        continue
                    block = data_block[cursor : cursor + num_ch]
                    if block.size != num_ch:
                        raise ValueError(
                            f"Malformed BVH frame {frame_index}: expected {num_ch} values "
                            f"for joint {names[joint_idx]}, got {block.size}."
                        )
                    if num_ch == 3:
                        rotations[frame_index, joint_idx] = block
                    elif num_ch >= 6:
                        positions[frame_index, joint_idx] = block[:3]
                        rotations[frame_index, joint_idx] = block[3:6]
                    cursor += num_ch

                frame_index += 1

    if order is None:
        raise ValueError(f"Could not detect rotation order from BVH: {path}")
    if framerate is None:
        raise ValueError(f"Could not detect frame time from BVH: {path}")
    if positions is None:
        raise ValueError(f"No frame data found in BVH: {path}")

    num_frames, num_joints = positions.shape[:2]

    # Build local 4x4 transform matrices [F, J, 4, 4]
    rot_matrices = _euler_to_rotation_matrix(rotations, order)  # (F, J, 3, 3)
    local_pos = positions * scale  # (F, J, 3)

    local_matrices = np.zeros((num_frames, num_joints, 4, 4), dtype=np.float32)
    local_matrices[:, :, :3, :3] = rot_matrices
    local_matrices[:, :, :3, 3] = local_pos
    local_matrices[:, :, 3, 3] = 1.0

    # Forward kinematics: accumulate global transforms
    global_matrices = np.zeros_like(local_matrices)
    parents_arr = np.array(parents, dtype=np.int32)
    for j in range(num_joints):
        p = parents_arr[j]
        if p == -1:
            global_matrices[:, j] = local_matrices[:, j]
        else:
            # batched 4x4 matrix multiply: global[j] = global[parent] @ local[j]
            global_matrices[:, j] = np.einsum("fij,fjk->fik", global_matrices[:, p], local_matrices[:, j])

    # Filter to joints that have motion channels (same as ai4animationpy BVH.LoadMotion)
    motion_joints = [i for i, ch in enumerate(channel_counts) if ch > 0]
    motion_names = [names[i] for i in motion_joints]
    motion_frames = global_matrices[:, motion_joints]

    # Build parent index list for motion joints only
    motion_name_set = set(motion_names)
    motion_parent_indices: list[int] = []
    for name in motion_names:
        orig_idx = names.index(name)
        p_idx = parents_arr[orig_idx]
        # Walk up until we find a motion joint parent
        while p_idx != -1 and names[p_idx] not in motion_name_set:
            p_idx = parents_arr[p_idx]
        if p_idx == -1 or names[p_idx] not in motion_names:
            motion_parent_indices.append(-1)
        else:
            motion_parent_indices.append(motion_names.index(names[p_idx]))

    hierarchy = Hierarchy(bone_names=motion_names, parent_indices=motion_parent_indices)
    return Motion(name=path.stem, hierarchy=hierarchy, frames=motion_frames, framerate=framerate)


# ---------------------------------------------------------------------------
# Contact detection
# ---------------------------------------------------------------------------


def extract_contacts(
    motion: Motion,
    bone_names: list[str],
    height_thresholds: list[float] | None = None,
    velocity_thresholds: list[float] | None = None,
) -> dict:
    """Detect contact frames for specified bones.

    A bone is considered in contact when both:
    - Its world Y position is below the height threshold.
    - Its world-space velocity magnitude is below the velocity threshold.

    This replicates ai4animationpy ContactModule.GetContacts().

    Args:
        motion: Motion object from load_bvh.
        bone_names: List of bone names to check (e.g. ['LeftFoot', 'RightFoot']).
        height_thresholds: Per-bone Y thresholds (meters). Default: 0.1 each.
        velocity_thresholds: Per-bone speed thresholds (m/s). Default: 0.5 each.

    Returns:
        Dict with per-bone contact frame lists and summary statistics.
    """
    try:
        indices = motion.hierarchy.indices(bone_names)
    except ValueError as e:
        raise ValueError(f"Bone not found: {e}. Available: {motion.hierarchy.bone_names}") from e

    n = len(bone_names)
    ht = height_thresholds if height_thresholds is not None else [0.1] * n
    vt = velocity_thresholds if velocity_thresholds is not None else [0.5] * n

    positions = motion.bone_positions(indices)  # (F, n, 3)
    velocities = motion.bone_velocities(indices)  # (F, n, 3)
    speeds = np.linalg.norm(velocities, axis=-1)  # (F, n)

    results: dict = {"bones": {}, "total_frames": motion.num_frames}
    for bi, (bone, hi, vi) in enumerate(zip(bone_names, ht, vt)):
        height_ok = positions[:, bi, 1] < hi
        speed_ok = speeds[:, bi] < vi
        contact = height_ok & speed_ok
        contact_frames = np.where(contact)[0].tolist()

        results["bones"][bone] = {
            "contact_frames": contact_frames,
            "contact_count": len(contact_frames),
            "contact_ratio": round(len(contact_frames) / motion.num_frames, 3),
            "height_threshold": hi,
            "velocity_threshold": vi,
        }

    return results


# ---------------------------------------------------------------------------
# Decompose: root trajectory + per-joint local transforms
# ---------------------------------------------------------------------------


def decompose(motion: Motion, hip_name: str | None = None) -> dict:
    """Split motion into root trajectory, per-joint transforms, and velocities.

    Implements the RootModule / MotionModule decomposition pattern from
    ai4animationpy: root captures WHERE and HOW, joints capture the pose.

    Args:
        motion: Motion object.
        hip_name: Name of the hip/root bone. Defaults to first bone.

    Returns:
        Dict with root_trajectory and per_joint_local_transforms.
    """
    hip_idx = 0
    if hip_name is not None:
        try:
            hip_idx = motion.hierarchy.index(hip_name)
        except ValueError as e:
            raise ValueError(f"Hip bone '{hip_name}' not found. Available: {motion.hierarchy.bone_names}") from e

    root_positions = motion.frames[:, hip_idx, :3, 3]  # (F, 3)
    root_rot_matrices = motion.frames[:, hip_idx, :3, :3]  # (F, 3, 3)

    # Root velocity (finite difference)
    root_vel = np.zeros_like(root_positions)
    dt = motion.delta_time
    root_vel[1:-1] = (root_positions[2:] - root_positions[:-2]) / (2.0 * dt)
    root_vel[0] = (root_positions[1] - root_positions[0]) / dt
    root_vel[-1] = (root_positions[-1] - root_positions[-2]) / dt

    # Facing direction: extract forward vector from root rotation (Z column)
    facing = root_rot_matrices[:, :, 2]  # (F, 3) -- Z forward convention

    # Per-joint local transforms: global[j] = global[parent] @ local[j]
    # => local[j] = inv(global[parent]) @ global[j]
    local_transforms = np.zeros_like(motion.frames)
    parents = motion.hierarchy.parent_indices

    for j in range(motion.num_joints):
        p = parents[j]
        if p == -1:
            local_transforms[:, j] = motion.frames[:, j]
        else:
            parent_inv = np.linalg.inv(motion.frames[:, p])  # (F, 4, 4)
            local_transforms[:, j] = np.einsum("fij,fjk->fik", parent_inv, motion.frames[:, j])

    # Extract per-joint Euler angles from local rotation matrices
    local_angles_list = []
    for j in range(motion.num_joints):
        rots = ScipyRotation.from_matrix(local_transforms[:, j, :3, :3])
        euler = rots.as_euler("ZYX", degrees=True)  # (F, 3)
        local_angles_list.append(euler.tolist())

    return {
        "hip_bone": motion.hierarchy.bone_names[hip_idx],
        "num_frames": motion.num_frames,
        "framerate": motion.framerate,
        "root_trajectory": {
            "positions": root_positions.tolist(),
            "velocities": root_vel.tolist(),
            "facing_directions": facing.tolist(),
        },
        "per_joint_euler_zyx_degrees": {
            motion.hierarchy.bone_names[j]: local_angles_list[j] for j in range(motion.num_joints)
        },
    }


# ---------------------------------------------------------------------------
# Motion blending (SLERP rotations, LERP positions)
# ---------------------------------------------------------------------------


def blend_motions(motion_a: Motion, motion_b: Motion, alpha: float = 0.5) -> Motion:
    """Blend two motion clips at a fixed alpha.

    Both clips must have the same bone hierarchy. Frame counts may differ;
    the shorter clip is resampled to match the longer.

    Uses SLERP for rotation components and linear interpolation for positions,
    matching the intended behavior of ai4animationpy Tensor.Interpolate.

    Args:
        motion_a: First motion clip.
        motion_b: Second motion clip.
        alpha: Blend weight (0.0 = all A, 1.0 = all B).

    Returns:
        New Motion with blended transforms.
    """
    if motion_a.hierarchy.bone_names != motion_b.hierarchy.bone_names:
        raise ValueError("Cannot blend motions with different hierarchies.")
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"Alpha must be in [0, 1], got {alpha}.")

    target_frames = max(motion_a.num_frames, motion_b.num_frames)
    target_fps = motion_a.framerate

    def resample(frames: np.ndarray, from_n: int, to_n: int) -> np.ndarray:
        """Resample frames array to a different frame count via linear interpolation."""
        if from_n == to_n:
            return frames
        src_t = np.linspace(0, 1, from_n)
        dst_t = np.linspace(0, 1, to_n)
        # Vectorised: reshape to (from_n, -1), interp each column, reshape back
        flat = frames.reshape(from_n, -1)
        out = np.zeros((to_n, flat.shape[1]), dtype=np.float32)
        for col in range(flat.shape[1]):
            out[:, col] = np.interp(dst_t, src_t, flat[:, col])
        return out.reshape(to_n, frames.shape[1], frames.shape[2], frames.shape[3])

    frames_a = resample(motion_a.frames, motion_a.num_frames, target_frames)
    frames_b = resample(motion_b.frames, motion_b.num_frames, target_frames)

    blended = np.zeros_like(frames_a)

    # LERP positions: vectorised over all joints and frames at once
    blended[:, :, :3, 3] = (1.0 - alpha) * frames_a[:, :, :3, 3] + alpha * frames_b[:, :, :3, 3]
    blended[:, :, 3, 3] = 1.0

    # SLERP rotations: per-joint vectorised over all frames using quaternion lerp.
    # scipy Rotation supports batched from_matrix and vectorised slerp via
    # linear quaternion interpolation (nlerp) which is nearly identical to slerp
    # for small angular differences and much faster than per-frame Slerp calls.
    for j in range(motion_a.num_joints):
        rot_a = ScipyRotation.from_matrix(frames_a[:, j, :3, :3])  # batch (F,)
        rot_b = ScipyRotation.from_matrix(frames_b[:, j, :3, :3])  # batch (F,)

        # Vectorised quaternion nlerp: q = normalize((1-a)*qa + a*qb)
        qa = rot_a.as_quat()  # (F, 4) xyzw
        qb = rot_b.as_quat()  # (F, 4) xyzw

        # Ensure shortest-path interpolation by flipping qb if dot product < 0
        dot = np.sum(qa * qb, axis=-1, keepdims=True)
        qb = np.where(dot < 0, -qb, qb)

        q_blend = (1.0 - alpha) * qa + alpha * qb
        norms = np.linalg.norm(q_blend, axis=-1, keepdims=True)
        q_blend = q_blend / np.maximum(norms, 1e-8)

        blended[:, j, :3, :3] = ScipyRotation.from_quat(q_blend).as_matrix().astype(np.float32)

    return Motion(
        name=f"{motion_a.name}_x_{motion_b.name}_a{alpha:.2f}",
        hierarchy=motion_a.hierarchy,
        frames=blended,
        framerate=target_fps,
    )


# ---------------------------------------------------------------------------
# FABRIK IK solver (standalone, mirrors ai4animationpy IK/FABRIK.py)
# ---------------------------------------------------------------------------


def solve_ik_fabrik(
    chain_positions: np.ndarray,
    target: np.ndarray,
    max_iterations: int = 30,
    threshold: float = 0.001,
) -> np.ndarray:
    """FABRIK inverse kinematics solver.

    Forward And Backward Reaching Inverse Kinematics.
    Mirrors the algorithm in ai4animationpy IK/FABRIK.py.

    Args:
        chain_positions: Bone positions (N, 3) from root to end effector.
        target: Target position (3,).
        max_iterations: Maximum solver iterations.
        threshold: Convergence threshold (meters).

    Returns:
        Solved bone positions (N, 3).
    """
    positions = chain_positions.copy().astype(np.float64)
    n = len(positions)
    lengths = np.linalg.norm(positions[1:] - positions[:-1], axis=-1)  # (N-1,)
    root = positions[0].copy()

    total_length = lengths.sum()
    dist_to_target = np.linalg.norm(target - root)

    if dist_to_target > total_length:
        # Target unreachable: fully extend chain toward target
        direction = (target - root) / (dist_to_target + 1e-8)
        for i in range(1, n):
            positions[i] = positions[i - 1] + direction * lengths[i - 1]
        return positions.astype(np.float32)

    for _ in range(max_iterations):
        # Backward pass: pull end effector to target
        positions[-1] = target
        for i in range(n - 2, -1, -1):
            direction = positions[i] - positions[i + 1]
            norm = np.linalg.norm(direction)
            if norm > 1e-8:
                positions[i] = positions[i + 1] + direction / norm * lengths[i]

        # Forward pass: restore root
        positions[0] = root
        for i in range(1, n):
            direction = positions[i] - positions[i - 1]
            norm = np.linalg.norm(direction)
            if norm > 1e-8:
                positions[i] = positions[i - 1] + direction / norm * lengths[i - 1]

        if np.linalg.norm(positions[-1] - target) < threshold:
            break

    return positions.astype(np.float32)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="motion-pipeline",
        description="CPU-only motion data processing pipeline for game animation.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # import-bvh
    p_import = sub.add_parser("import-bvh", help="Parse BVH file and print motion summary.")
    p_import.add_argument("file", type=Path, help="Path to .bvh file.")
    p_import.add_argument("--scale", type=float, default=1.0, help="Position scale factor (default 1.0).")
    p_import.add_argument(
        "--fps",
        type=float,
        default=None,
        help="Override output framerate (resampling not implemented, informational only).",
    )

    # extract-contacts
    p_contact = sub.add_parser("extract-contacts", help="Detect ground contact frames per bone.")
    p_contact.add_argument("file", type=Path, help="Path to .bvh file.")
    p_contact.add_argument("--bones", nargs="+", required=True, help="Bone names to analyse.")
    p_contact.add_argument("--height", type=float, default=0.1, help="Height threshold in metres (default 0.1).")
    p_contact.add_argument("--vel", type=float, default=0.5, help="Velocity threshold in m/s (default 0.5).")
    p_contact.add_argument("--scale", type=float, default=1.0)

    # decompose
    p_decompose = sub.add_parser("decompose", help="Split motion into root trajectory and per-joint transforms.")
    p_decompose.add_argument("file", type=Path, help="Path to .bvh file.")
    p_decompose.add_argument("--hip", type=str, default=None, help="Hip/root bone name.")
    p_decompose.add_argument("--scale", type=float, default=1.0)

    # blend
    p_blend = sub.add_parser("blend", help="Blend two BVH clips at a fixed alpha.")
    p_blend.add_argument("file_a", type=Path, help="First .bvh file.")
    p_blend.add_argument("file_b", type=Path, help="Second .bvh file (must share skeleton).")
    p_blend.add_argument("--alpha", type=float, default=0.5, help="Blend weight (0=A, 1=B).")
    p_blend.add_argument("--scale", type=float, default=1.0)

    # solve-ik
    p_ik = sub.add_parser("solve-ik", help="Run FABRIK IK solver on a bone chain.")
    p_ik.add_argument("file", type=Path, help="Path to .bvh file.")
    p_ik.add_argument(
        "--chain", required=True, metavar="ROOT:TIP", help="Colon-separated bone names forming the IK chain."
    )
    p_ik.add_argument("--target", required=True, metavar="X,Y,Z", help="Target position as comma-separated floats.")
    p_ik.add_argument("--frame", type=int, default=0, help="Frame index to solve (default 0).")
    p_ik.add_argument("--scale", type=float, default=1.0)

    return parser


def cmd_import_bvh(args: argparse.Namespace) -> None:
    motion = load_bvh(args.file, scale=args.scale)
    result = motion.summary()
    print(json.dumps(result, indent=2))


def cmd_extract_contacts(args: argparse.Namespace) -> None:
    motion = load_bvh(args.file, scale=args.scale)
    result = extract_contacts(
        motion,
        bone_names=args.bones,
        height_thresholds=[args.height] * len(args.bones),
        velocity_thresholds=[args.vel] * len(args.bones),
    )
    print(json.dumps(result, indent=2))


def cmd_decompose(args: argparse.Namespace) -> None:
    motion = load_bvh(args.file, scale=args.scale)
    result = decompose(motion, hip_name=args.hip)
    # Truncate large arrays for readability: show first 5 frames
    if result["num_frames"] > 5:
        result["root_trajectory"]["positions"] = result["root_trajectory"]["positions"][:5]
        result["root_trajectory"]["velocities"] = result["root_trajectory"]["velocities"][:5]
        result["root_trajectory"]["facing_directions"] = result["root_trajectory"]["facing_directions"][:5]
        result["note"] = f"Truncated to first 5 frames of {result['num_frames']} total for display."
        for bone in result["per_joint_euler_zyx_degrees"]:
            result["per_joint_euler_zyx_degrees"][bone] = result["per_joint_euler_zyx_degrees"][bone][:5]
    print(json.dumps(result, indent=2))


def cmd_blend(args: argparse.Namespace) -> None:
    motion_a = load_bvh(args.file_a, scale=args.scale)
    motion_b = load_bvh(args.file_b, scale=args.scale)
    blended = blend_motions(motion_a, motion_b, alpha=args.alpha)
    result = blended.summary()
    result["blend_alpha"] = args.alpha
    result["source_a"] = str(args.file_a)
    result["source_b"] = str(args.file_b)
    print(json.dumps(result, indent=2))


def cmd_solve_ik(args: argparse.Namespace) -> None:
    motion = load_bvh(args.file, scale=args.scale)

    chain_parts = args.chain.split(":")
    if len(chain_parts) < 2:
        print("Error: --chain must be ROOT:TIP (at least two bones)", file=sys.stderr)
        sys.exit(1)

    # Find bone chain between root and tip names
    root_name, tip_name = chain_parts[0], chain_parts[-1]
    try:
        root_idx = motion.hierarchy.index(root_name)
        tip_idx = motion.hierarchy.index(tip_name)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Build chain by walking from tip to root via parent indices
    chain_indices: list[int] = []
    current = tip_idx
    while current != -1 and current != root_idx:
        chain_indices.append(current)
        current = motion.hierarchy.parent_indices[current]
    if current == root_idx:
        chain_indices.append(root_idx)
    else:
        print(f"Error: {root_name} is not an ancestor of {tip_name}.", file=sys.stderr)
        sys.exit(1)
    chain_indices.reverse()

    frame = min(args.frame, motion.num_frames - 1)
    chain_positions = motion.frames[frame, chain_indices, :3, 3]  # (N, 3)

    try:
        target_xyz = [float(x) for x in args.target.split(",")]
        if len(target_xyz) != 3:
            raise ValueError("Need exactly 3 values")
    except ValueError as e:
        print(f"Error parsing --target: {e}", file=sys.stderr)
        sys.exit(1)

    target = np.array(target_xyz, dtype=np.float32)
    solved = solve_ik_fabrik(chain_positions, target)

    result = {
        "frame": frame,
        "chain": [motion.hierarchy.bone_names[i] for i in chain_indices],
        "target": target_xyz,
        "initial_positions": chain_positions.tolist(),
        "solved_positions": solved.tolist(),
        "end_effector_error": round(float(np.linalg.norm(solved[-1] - target)), 5),
    }
    print(json.dumps(result, indent=2))


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        "import-bvh": cmd_import_bvh,
        "extract-contacts": cmd_extract_contacts,
        "decompose": cmd_decompose,
        "blend": cmd_blend,
        "solve-ik": cmd_solve_ik,
    }

    try:
        dispatch[args.command](args)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
