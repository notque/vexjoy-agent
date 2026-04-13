#!/usr/bin/env python3
"""Bake real walking animation from BVH mocap data into ScottHall.glb.

Replaces single-frame bind-pose animations with actual motion:
- Clip 0 (idle): subtle weight-shift from BVH standing pose
- Clip 1 (walk): one full stride cycle extracted from walking BVH

Usage:
    python3 scripts/bake-bvh-to-glb.py [--bvh PATH] [--glb PATH] [--out PATH] [--dry-run]

The script imports motion-pipeline.py via importlib (same pattern as
generate-move-ts.py) to parse BVH data without subprocess overhead.

Bind pose retargeting
---------------------
GLB skeletons from Mixamo/Sketchfab carry non-identity bind pose rotations on
bones such as LeftUpLeg (~180 degrees around Z), shoulders, feet, etc. Writing
raw BVH local rotations directly into those slots causes the skeleton to
deform incorrectly (body drops, legs splay sideways).

The fix: for each bone at each frame, compute the *delta* from the BVH bind
pose (frame 0), then apply that delta to the GLB bind pose rotation:

    bvh_delta = bvh_frame_rot * inv(bvh_bind_rot)
    glb_frame_rot = bvh_delta * glb_bind_rot
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import struct
import sys
import types
from pathlib import Path

import numpy as np
import pygltflib
from scipy.spatial.transform import Rotation as ScipyRotation

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BVH_PATH = Path("/tmp/ai4animationpy/Demos/BVHLoading/WalkingStickLeft_BR.bvh")
_GLB_PATH = Path("/home/feedgen/road-to-aew/public/assets/prototype/models/ScottHall.glb")
_PIPELINE_PATH = Path(__file__).parent / "motion-pipeline.py"

# Scale BVH positions from cm to metres (same convention as generate-move-ts.py)
_BVH_SCALE = 0.01

# Walk cycle: frames 31-134 (one full stride, left foot contact to left foot contact)
_WALK_START = 31
_WALK_END = 135  # exclusive: range [31, 134] = 104 frames

# Idle: frames 31-60 (character in a static stance, slight weight on left foot)
_IDLE_START = 31
_IDLE_END = 61  # exclusive: 30 frames

# Subsample targets (keyframes written into the GLB)
_WALK_KEYFRAMES = 64  # ~1 frame per 1.6 BVH frames — smooth but compact
_IDLE_KEYFRAMES = 30  # 30 frames at ~1fps => 30-second slow bob

# Clip names in the existing GLB (Three.js code references these by name)
_IDLE_CLIP_NAME = "Scott Hall Rigged|Armature"
_WALK_CLIP_NAME = "Scott Hall Rigged|Armature.001"

# glTF accessor component types and element types
_FLOAT = 5126  # GL_FLOAT
_SCALAR = "SCALAR"
_VEC4 = "VEC4"
_VEC3 = "VEC3"

# Animation interpolation
_LINEAR = "LINEAR"


# ---------------------------------------------------------------------------
# Motion pipeline loader (mirrors generate-move-ts.py pattern exactly)
# ---------------------------------------------------------------------------


def _load_pipeline() -> types.ModuleType:
    """Import motion-pipeline.py as a module via importlib.

    The module uses dataclasses, so it must be registered in sys.modules
    before exec_module runs.
    """
    spec = importlib.util.spec_from_file_location("motion_pipeline", _PIPELINE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load motion pipeline from {_PIPELINE_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["motion_pipeline"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Bone name mapping: BVH names -> GLB node indices
# ---------------------------------------------------------------------------

# BVH bones that have no GLB counterpart (extra joints in the BVH rig)
_BVH_SKIP_SUFFIXES = ("End", "Site")


def _build_bone_map(glb: pygltflib.GLTF2, bvh_names: list[str]) -> dict[str, int]:
    """Map BVH bone names to GLB node indices.

    GLB node names follow the pattern: mixamorig:{BASE_NAME}_{NUMBER}
    BVH bone names are the BASE_NAME (e.g. 'Hips', 'LeftUpLeg').

    Some BVH bones have no GLB counterpart (finger tips with 'End' suffix,
    intermediate spine segments, etc.). Those are omitted from the result.

    Args:
        glb: Loaded GLTF2 object.
        bvh_names: Ordered list of bone names from the BVH Hierarchy.

    Returns:
        Dict mapping BVH bone name -> GLB node index. Only includes bones
        that have a match in the GLB.
    """
    # Build reverse lookup: base_name -> node_index for all mixamorig nodes
    glb_base_to_idx: dict[str, int] = {}
    pattern = re.compile(r"^mixamorig:(.+?)_\d+$")
    for node_idx, node in enumerate(glb.nodes):
        if not node.name:
            continue
        m = pattern.match(node.name)
        if m:
            base = m.group(1)
            glb_base_to_idx[base] = node_idx

    # Match BVH bones to GLB bases
    bone_map: dict[str, int] = {}
    for bvh_name in bvh_names:
        # Skip BVH leaf/end bones — they have no animation data
        if any(bvh_name.endswith(s) for s in _BVH_SKIP_SUFFIXES):
            continue
        # Skip multi-word internal names that have no GLB match
        if bvh_name not in glb_base_to_idx:
            continue
        bone_map[bvh_name] = glb_base_to_idx[bvh_name]

    return bone_map


# ---------------------------------------------------------------------------
# Extract local quaternions from global BVH transforms
# ---------------------------------------------------------------------------


def _extract_local_quats(
    motion: object,  # Motion dataclass from motion_pipeline
    frame_range: range,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Compute per-bone LOCAL rotation quaternions for a frame range.

    The BVH frames store global 4x4 transforms. Local rotation for bone j:
        local[j] = inv(parent_global[j]) @ bone_global[j]

    For the root bone (parent index -1), local == global.

    Also returns the BVH bind pose (frame 0 of the BVH, i.e. the absolute
    frame at index frame_range.start) so callers can compute the delta from
    rest to drive GLB-space animation correctly.

    Args:
        motion: Motion object from motion_pipeline.load_bvh.
        frame_range: Range of frame indices to extract.

    Returns:
        Tuple of two dicts, both mapping BVH bone name -> np.ndarray:
        - quats: shape (N, 4) [x, y, z, w] for frames in frame_range.
          N = len(frame_range).
        - bind_quats: shape (4,) [x, y, z, w] quaternion at BVH frame 0
          (the skeleton rest pose used as the reference for delta computation).
    """
    frames_arr = list(frame_range)
    n_frames = len(frames_arr)
    bone_names: list[str] = motion.hierarchy.bone_names
    parent_indices: list[int] = motion.hierarchy.parent_indices

    # Pre-fetch the relevant slice of motion.frames: shape (N, J, 4, 4)
    motion_frames: np.ndarray = motion.frames[np.array(frames_arr)]  # (N, J, 4, 4)

    # Bind pose: BVH frame 0 (absolute rest position of the BVH skeleton)
    bind_frame: np.ndarray = motion.frames[0]  # (J, 4, 4)

    result: dict[str, np.ndarray] = {}
    bind_quats: dict[str, np.ndarray] = {}

    for j, bone_name in enumerate(bone_names):
        p = parent_indices[j]
        if p == -1:
            # Root: local == global rotation
            rot_matrices = motion_frames[:, j, :3, :3]  # (N, 3, 3)
            bind_rot_matrix = bind_frame[j, :3, :3]  # (3, 3)
        else:
            # Local = inv(parent_global) @ bone_global
            parent_global = motion_frames[:, p]  # (N, 4, 4)
            bone_global = motion_frames[:, j]  # (N, 4, 4)

            # Batched inv: since these are rigid transforms, inv = transpose of rot + negated trans
            # But numpy.linalg.inv is safe and clear here; N is small (<=135 frames)
            parent_inv = np.linalg.inv(parent_global)  # (N, 4, 4)
            local_mat = np.einsum("fij,fjk->fik", parent_inv, bone_global)  # (N, 4, 4)
            rot_matrices = local_mat[:, :3, :3]  # (N, 3, 3)

            # Bind pose local rotation for this bone
            bind_parent_inv = np.linalg.inv(bind_frame[p])  # (4, 4)
            bind_local = bind_parent_inv @ bind_frame[j]  # (4, 4)
            bind_rot_matrix = bind_local[:3, :3]  # (3, 3)

        # Convert rotation matrices to quaternions [x, y, z, w] (scipy convention)
        # ScipyRotation.as_quat() returns [x, y, z, w]
        quats = ScipyRotation.from_matrix(rot_matrices).as_quat().astype(np.float32)  # (N, 4)
        result[bone_name] = quats

        bind_q = ScipyRotation.from_matrix(bind_rot_matrix).as_quat().astype(np.float32)  # (4,)
        bind_quats[bone_name] = bind_q

    return result, bind_quats


def _extract_root_translations(
    motion: object,
    frame_range: range,
) -> np.ndarray:
    """Extract root (Hips) world-space translations for a frame range.

    Returns shape (N, 3) float32 array in metres (BVH already scaled by _BVH_SCALE).
    The translations are relative to the first frame of the range so the
    character stays at the origin when the clip starts.
    """
    frames_arr = np.array(list(frame_range))
    root_positions = motion.frames[frames_arr, 0, :3, 3]  # (N, 3)
    # Remove root drift: subtract the starting position so clip begins at origin
    root_positions = root_positions - root_positions[0:1]
    return root_positions.astype(np.float32)


# ---------------------------------------------------------------------------
# Bind pose correction: BVH space -> GLB space retargeting
# ---------------------------------------------------------------------------


def _load_glb_bind_rotations(glb: pygltflib.GLTF2, bone_map: dict[str, int]) -> dict[str, np.ndarray]:
    """Read the GLB node default rotations for each mapped bone.

    These are the rotations the skeleton was authored in — the GLB bind pose.
    Animation data must be expressed as deltas from this pose.

    Args:
        glb: Loaded GLTF2 object.
        bone_map: Maps BVH bone name -> GLB node index.

    Returns:
        Dict mapping BVH bone name -> np.ndarray of shape (4,) [x, y, z, w].
        Bones with no rotation set default to identity [0, 0, 0, 1].
    """
    glb_bind: dict[str, np.ndarray] = {}
    for bvh_name, node_idx in bone_map.items():
        node = glb.nodes[node_idx]
        if node.rotation is not None:
            glb_bind[bvh_name] = np.array(node.rotation, dtype=np.float32)
        else:
            glb_bind[bvh_name] = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
    return glb_bind


def _retarget_quats(
    bvh_quats: dict[str, np.ndarray],
    bvh_bind_quats: dict[str, np.ndarray],
    glb_bind_quats: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """Correct BVH-space quaternions to GLB-space by applying bind pose delta.

    For each bone at each frame:
        bvh_delta = bvh_frame_rot * inv(bvh_bind_rot)
        glb_frame_rot = bvh_delta * glb_bind_rot

    This maps the BVH motion (expressed as change-from-BVH-rest) into the
    GLB skeleton (expressed as change-from-GLB-rest), so the mesh deforms
    correctly regardless of the GLB's non-identity bind pose.

    Args:
        bvh_quats: Dict bone_name -> (N, 4) float32 BVH local quaternions.
        bvh_bind_quats: Dict bone_name -> (4,) float32 BVH rest pose quaternion.
        glb_bind_quats: Dict bone_name -> (4,) float32 GLB node default rotation.

    Returns:
        Dict bone_name -> (N, 4) float32 corrected quaternions ready for GLB.
    """
    retargeted: dict[str, np.ndarray] = {}
    for bone_name, bvh_q in bvh_quats.items():
        bvh_bind = ScipyRotation.from_quat(bvh_bind_quats[bone_name])
        glb_bind = ScipyRotation.from_quat(glb_bind_quats.get(bone_name, np.array([0.0, 0.0, 0.0, 1.0])))

        bvh_frames = ScipyRotation.from_quat(bvh_q)  # (N,) rotation object
        # delta = frame * inv(bind): change relative to BVH rest
        bvh_delta = bvh_frames * bvh_bind.inv()
        # Apply delta to GLB bind pose
        glb_frames = bvh_delta * glb_bind

        retargeted[bone_name] = glb_frames.as_quat().astype(np.float32)  # (N, 4)
    return retargeted


# ---------------------------------------------------------------------------
# GLB binary blob helpers
# ---------------------------------------------------------------------------


def _append_binary(
    glb: pygltflib.GLTF2,
    data: bytes,
) -> int:
    """Append bytes to the GLB binary blob and return the byte offset.

    Args:
        glb: GLTF2 object (mutated in place).
        data: Raw bytes to append.

    Returns:
        Byte offset of the appended data within the blob.
    """
    blob = glb.binary_blob() or b""
    offset = len(blob)
    glb.set_binary_blob(blob + data)
    return offset


def _add_buffer_view(
    glb: pygltflib.GLTF2,
    byte_offset: int,
    byte_length: int,
) -> int:
    """Add a BufferView entry and return its index."""
    bv = pygltflib.BufferView(
        buffer=0,
        byteOffset=byte_offset,
        byteLength=byte_length,
        target=None,  # animation data has no GPU target
    )
    glb.bufferViews.append(bv)
    return len(glb.bufferViews) - 1


def _add_accessor_scalar(
    glb: pygltflib.GLTF2,
    buffer_view_idx: int,
    count: int,
    min_val: float,
    max_val: float,
) -> int:
    """Add a SCALAR float32 accessor (used for timestamps) and return its index."""
    acc = pygltflib.Accessor(
        bufferView=buffer_view_idx,
        byteOffset=0,
        componentType=_FLOAT,
        count=count,
        type=_SCALAR,
        min=[float(min_val)],
        max=[float(max_val)],
    )
    glb.accessors.append(acc)
    return len(glb.accessors) - 1


def _add_accessor_vec4(
    glb: pygltflib.GLTF2,
    buffer_view_idx: int,
    count: int,
) -> int:
    """Add a VEC4 float32 accessor (used for quaternions) and return its index."""
    acc = pygltflib.Accessor(
        bufferView=buffer_view_idx,
        byteOffset=0,
        componentType=_FLOAT,
        count=count,
        type=_VEC4,
    )
    glb.accessors.append(acc)
    return len(glb.accessors) - 1


def _add_accessor_vec3(
    glb: pygltflib.GLTF2,
    buffer_view_idx: int,
    count: int,
) -> int:
    """Add a VEC3 float32 accessor (used for translations) and return its index."""
    acc = pygltflib.Accessor(
        bufferView=buffer_view_idx,
        byteOffset=0,
        componentType=_FLOAT,
        count=count,
        type=_VEC3,
    )
    glb.accessors.append(acc)
    return len(glb.accessors) - 1


def _sync_buffer_length(glb: pygltflib.GLTF2) -> None:
    """Update buffer[0].byteLength to match the actual binary blob size."""
    blob = glb.binary_blob() or b""
    if glb.buffers:
        glb.buffers[0].byteLength = len(blob)


# ---------------------------------------------------------------------------
# Build one animation clip
# ---------------------------------------------------------------------------


def _build_animation(
    glb: pygltflib.GLTF2,
    clip_name: str,
    timestamps: np.ndarray,
    local_quats: dict[str, np.ndarray],
    root_translations: np.ndarray | None,
    bone_map: dict[str, int],
) -> pygltflib.Animation:
    """Construct a pygltflib Animation object from pre-computed data.

    Writes binary data into the GLB blob and creates the accessor/bufferView
    entries needed to reference it. Returns a fully-wired Animation object
    ready to assign to glb.animations.

    Args:
        glb: GLTF2 to mutate with new binary data, accessors, and buffer views.
        clip_name: Name for this animation clip.
        timestamps: Float32 array of shape (N,) — keyframe times in seconds.
        local_quats: Dict BVH_name -> (N, 4) float32 quaternion array [x,y,z,w].
        root_translations: Optional (N, 3) float32 root position array (metres).
            When provided, a translation channel is added for the Hips bone.
        bone_map: Maps BVH bone name -> GLB node index.

    Returns:
        pygltflib.Animation ready to append to glb.animations.
    """
    n_frames = len(timestamps)
    channels: list[pygltflib.AnimationChannel] = []
    samplers: list[pygltflib.AnimationSampler] = []

    def _add_sampler_and_channel(
        input_acc_idx: int,
        output_acc_idx: int,
        node_idx: int,
        path: str,
    ) -> None:
        sampler_idx = len(samplers)
        samplers.append(
            pygltflib.AnimationSampler(
                input=input_acc_idx,
                output=output_acc_idx,
                interpolation=_LINEAR,
            )
        )
        channels.append(
            pygltflib.AnimationChannel(
                sampler=sampler_idx,
                target=pygltflib.AnimationChannelTarget(
                    node=node_idx,
                    path=path,
                ),
            )
        )

    # --- Shared timestamps accessor (all channels share the same input accessor) ---
    ts_bytes = timestamps.astype(np.float32).tobytes()
    ts_offset = _append_binary(glb, ts_bytes)
    ts_bv_idx = _add_buffer_view(glb, ts_offset, len(ts_bytes))
    ts_acc_idx = _add_accessor_scalar(
        glb,
        ts_bv_idx,
        count=n_frames,
        min_val=float(timestamps.min()),
        max_val=float(timestamps.max()),
    )

    # --- Root translation channel (Hips only, if provided) ---
    if root_translations is not None and "Hips" in bone_map:
        hips_node_idx = bone_map["Hips"]
        trans_bytes = root_translations.astype(np.float32).tobytes()
        trans_offset = _append_binary(glb, trans_bytes)
        trans_bv_idx = _add_buffer_view(glb, trans_offset, len(trans_bytes))
        trans_acc_idx = _add_accessor_vec3(glb, trans_bv_idx, count=n_frames)
        _add_sampler_and_channel(ts_acc_idx, trans_acc_idx, hips_node_idx, "translation")

    # --- Rotation channels for each mapped bone ---
    for bvh_name, node_idx in bone_map.items():
        if bvh_name not in local_quats:
            continue
        quats = local_quats[bvh_name]  # (N, 4) [x, y, z, w]

        # Ensure shortest-path: flip quaternions that are in the wrong hemisphere
        # relative to their predecessor to avoid 360-degree snaps
        for i in range(1, len(quats)):
            if np.dot(quats[i - 1], quats[i]) < 0:
                quats[i] = -quats[i]

        q_bytes = quats.tobytes()
        q_offset = _append_binary(glb, q_bytes)
        q_bv_idx = _add_buffer_view(glb, q_offset, len(q_bytes))
        q_acc_idx = _add_accessor_vec4(glb, q_bv_idx, count=n_frames)
        _add_sampler_and_channel(ts_acc_idx, q_acc_idx, node_idx, "rotation")

    return pygltflib.Animation(
        name=clip_name,
        channels=channels,
        samplers=samplers,
    )


# ---------------------------------------------------------------------------
# Subsample helpers
# ---------------------------------------------------------------------------


def _subsample_frames(total_frames: int, n_samples: int) -> np.ndarray:
    """Return evenly-spaced frame indices within [0, total_frames).

    Args:
        total_frames: Total number of available frames.
        n_samples: Desired number of output samples.

    Returns:
        Int array of shape (n_samples,) with frame indices.
    """
    return np.round(np.linspace(0, total_frames - 1, n_samples)).astype(int)


def _subsample_quats(
    quats: dict[str, np.ndarray],
    sample_indices: np.ndarray,
) -> dict[str, np.ndarray]:
    """Subsample quaternion arrays to the given frame indices.

    Args:
        quats: Dict BVH_name -> (N, 4) full-frame quaternion array.
        sample_indices: Int array of indices into axis-0 of each array.

    Returns:
        New dict with arrays subsampled to shape (len(sample_indices), 4).
    """
    return {name: arr[sample_indices] for name, arr in quats.items()}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def bake(
    bvh_path: Path,
    glb_path: Path,
    out_path: Path,
    dry_run: bool = False,
) -> None:
    """Load BVH, extract animations, and write enhanced GLB.

    Args:
        bvh_path: Path to the walking BVH file.
        glb_path: Path to the source ScottHall.glb.
        out_path: Destination for the enhanced GLB.
        dry_run: If True, perform all computation but skip file writes.

    Raises:
        FileNotFoundError: If bvh_path or glb_path do not exist.
        ValueError: If bone mapping yields no common bones.
    """
    # --- Validate inputs ---
    if not bvh_path.is_file():
        raise FileNotFoundError(f"BVH not found: {bvh_path}")
    if not glb_path.is_file():
        raise FileNotFoundError(f"GLB not found: {glb_path}")

    # --- Load BVH ---
    print(f"Loading BVH: {bvh_path}")
    pipeline = _load_pipeline()
    motion = pipeline.load_bvh(bvh_path, scale=_BVH_SCALE)
    print(
        f"  {motion.num_frames} frames @ {motion.framerate:.1f} fps  "
        f"({motion.total_time:.1f}s)  {motion.num_joints} joints"
    )

    # --- Load GLB (binary format) ---
    print(f"Loading GLB: {glb_path}")
    glb = pygltflib.GLTF2().load_binary(str(glb_path))
    print(f"  {len(glb.nodes)} nodes  {len(glb.animations)} animations  {len(glb.buffers)} buffers")

    # --- Build bone map ---
    bone_map = _build_bone_map(glb, motion.hierarchy.bone_names)
    print(f"Bone mapping: {len(bone_map)} BVH bones mapped to GLB nodes")
    if not bone_map:
        raise ValueError("No bones mapped. Check BVH and GLB bone name patterns.")

    # --- Load GLB bind pose rotations for retargeting ---
    # The GLB skeleton has non-identity bind pose rotations on many bones
    # (e.g. LeftUpLeg ~180 degrees around Z). We must express animation as
    # delta-from-GLB-bind, not raw BVH local rotations.
    glb_bind_quats = _load_glb_bind_rotations(glb, bone_map)
    non_identity = sum(
        1 for q in glb_bind_quats.values() if np.linalg.norm(q - np.array([0, 0, 0, 1], dtype=np.float32)) > 0.01
    )
    print(f"GLB bind pose: {non_identity}/{len(glb_bind_quats)} bones have non-identity rotations")

    # --- Extract walk cycle (frames 31-134, 104 BVH frames) ---
    walk_range = range(_WALK_START, _WALK_END)
    print(f"\nExtracting walk cycle: frames {_WALK_START}-{_WALK_END - 1} ({len(walk_range)} frames)")
    walk_quats_full, walk_bvh_bind = _extract_local_quats(motion, walk_range)
    walk_root_full = _extract_root_translations(motion, walk_range)

    # Apply bind pose retargeting: convert BVH-space rotations to GLB-space
    walk_quats_full = _retarget_quats(walk_quats_full, walk_bvh_bind, glb_bind_quats)

    # Subsample to _WALK_KEYFRAMES
    walk_sample_idx = _subsample_frames(len(walk_range), _WALK_KEYFRAMES)
    walk_quats = _subsample_quats(walk_quats_full, walk_sample_idx)
    walk_root = walk_root_full[walk_sample_idx]

    # Timestamps: 0 to duration of the original segment, spaced evenly
    walk_duration = (len(walk_range) - 1) / motion.framerate
    walk_timestamps = np.linspace(0.0, walk_duration, _WALK_KEYFRAMES, dtype=np.float32)
    print(f"  Subsampled to {_WALK_KEYFRAMES} keyframes  duration={walk_duration:.3f}s")

    # Validate: leg bones should have meaningful rotation range
    for leg_bone in ("LeftUpLeg", "RightUpLeg", "LeftLeg", "RightLeg"):
        if leg_bone in walk_quats:
            q = walk_quats[leg_bone]
            # Convert to euler to get degrees
            angles = ScipyRotation.from_quat(q).as_euler("xyz", degrees=True)
            ranges = angles.max(axis=0) - angles.min(axis=0)
            print(f"  {leg_bone} rotation range (deg): x={ranges[0]:.1f} y={ranges[1]:.1f} z={ranges[2]:.1f}")

    # --- Extract idle pose (frames 31-60, 30 BVH frames) ---
    idle_range = range(_IDLE_START, _IDLE_END)
    print(f"\nExtracting idle pose: frames {_IDLE_START}-{_IDLE_END - 1} ({len(idle_range)} frames)")
    idle_quats_full, idle_bvh_bind = _extract_local_quats(motion, idle_range)

    # Apply bind pose retargeting for idle clip
    idle_quats_full = _retarget_quats(idle_quats_full, idle_bvh_bind, glb_bind_quats)

    # Subsample to _IDLE_KEYFRAMES (use full range, 30 frames -> 30 keyframes directly)
    idle_sample_idx = _subsample_frames(len(idle_range), _IDLE_KEYFRAMES)
    idle_quats = _subsample_quats(idle_quats_full, idle_sample_idx)

    # Idle: slow loop, 4 seconds total (30 frames spread over 4s)
    idle_duration = 4.0
    idle_timestamps = np.linspace(0.0, idle_duration, _IDLE_KEYFRAMES, dtype=np.float32)
    print(f"  Subsampled to {_IDLE_KEYFRAMES} keyframes  duration={idle_duration:.1f}s")

    # --- Replace animations in the GLB ---
    # Clear existing animation data: we replace clips 0 and 1 in-place by name.
    # Find the target clip indices.
    idle_clip_idx: int | None = None
    walk_clip_idx: int | None = None
    for i, anim in enumerate(glb.animations):
        if anim.name == _IDLE_CLIP_NAME:
            idle_clip_idx = i
        elif anim.name == _WALK_CLIP_NAME:
            walk_clip_idx = i

    if idle_clip_idx is None:
        print(f"WARNING: Idle clip '{_IDLE_CLIP_NAME}' not found. Will append as new.")
    if walk_clip_idx is None:
        print(f"WARNING: Walk clip '{_WALK_CLIP_NAME}' not found. Will append as new.")

    print("\nBuilding idle animation...")
    idle_anim = _build_animation(
        glb=glb,
        clip_name=_IDLE_CLIP_NAME,
        timestamps=idle_timestamps,
        local_quats=idle_quats,
        root_translations=None,  # idle keeps the character stationary
        bone_map=bone_map,
    )

    print("Building walk animation...")
    walk_anim = _build_animation(
        glb=glb,
        clip_name=_WALK_CLIP_NAME,
        timestamps=walk_timestamps,
        local_quats=walk_quats,
        root_translations=walk_root,
        bone_map=bone_map,
    )

    # Replace or append animations
    if idle_clip_idx is not None:
        glb.animations[idle_clip_idx] = idle_anim
        print(f"  Replaced idle clip at index {idle_clip_idx}")
    else:
        glb.animations.append(idle_anim)
        print("  Appended idle clip")

    if walk_clip_idx is not None:
        glb.animations[walk_clip_idx] = walk_anim
        print(f"  Replaced walk clip at index {walk_clip_idx}")
    else:
        glb.animations.append(walk_anim)
        print("  Appended walk clip")

    # Sync buffer byte length
    _sync_buffer_length(glb)

    # --- Validation ---
    print("\nValidation:")
    for anim in [idle_anim, walk_anim]:
        total_keyframes = sum(glb.accessors[anim.samplers[ch.sampler].input].count for ch in anim.channels)
        keyframes_per_channel = (
            glb.accessors[anim.samplers[anim.channels[0].sampler].input].count if anim.channels else 0
        )
        print(
            f"  {anim.name!r}: {len(anim.channels)} channels  "
            f"{keyframes_per_channel} keyframes/channel  "
            f"{len(anim.samplers)} samplers"
        )
        if keyframes_per_channel <= 1:
            print(f"  ERROR: {anim.name!r} still has <=1 keyframe! Baking failed.")
            sys.exit(1)

    if dry_run:
        print("\nDry run — no files written.")
        return

    # --- Backup and write ---
    backup_path = glb_path.with_suffix(".glb.bak")
    if not backup_path.exists():
        shutil.copy2(glb_path, backup_path)
        print(f"\nBackup: {backup_path}")
    else:
        print(f"\nBackup already exists, skipping: {backup_path}")

    glb.save_binary(str(out_path))
    out_size_mb = out_path.stat().st_size / 1_048_576
    print(f"Saved: {out_path}  ({out_size_mb:.2f} MB)")


# ---------------------------------------------------------------------------
# Validation: reload and spot-check the saved GLB
# ---------------------------------------------------------------------------


def validate_saved_glb(out_path: Path) -> bool:
    """Reload the saved GLB and verify animations have real keyframes.

    Args:
        out_path: Path to the enhanced GLB file.

    Returns:
        True if validation passes, False otherwise.
    """
    print("\nReloading saved GLB for validation...")
    glb = pygltflib.GLTF2().load_binary(str(out_path))

    all_ok = True
    for anim in glb.animations:
        if anim.name not in (_IDLE_CLIP_NAME, _WALK_CLIP_NAME):
            continue

        if not anim.channels:
            print(f"  FAIL: {anim.name!r} has no channels")
            all_ok = False
            continue

        ch = anim.channels[0]
        sampler = anim.samplers[ch.sampler]
        keyframe_count = glb.accessors[sampler.input].count
        print(f"  {anim.name!r}: {len(anim.channels)} channels  {keyframe_count} keyframes/channel")

        if keyframe_count <= 1:
            print(f"  FAIL: {anim.name!r} only has {keyframe_count} keyframe(s)")
            all_ok = False

    # Spot-check: read leg rotation data for walk clip
    for anim in glb.animations:
        if anim.name != _WALK_CLIP_NAME:
            continue

        # Find a rotation channel for LeftUpLeg (node 73)
        for ch in anim.channels:
            if ch.target.node == 73 and ch.target.path == "rotation":
                sampler = anim.samplers[ch.sampler]
                acc_out = glb.accessors[sampler.output]
                bv = glb.bufferViews[acc_out.bufferView]
                blob = glb.binary_blob()
                if blob is None:
                    print("  FAIL: binary blob is None after reload")
                    all_ok = False
                    break
                raw = blob[bv.byteOffset : bv.byteOffset + bv.byteLength]
                quats = np.frombuffer(raw, dtype=np.float32).reshape(-1, 4)  # (N, 4) [x,y,z,w]
                angles = ScipyRotation.from_quat(quats).as_euler("xyz", degrees=True)
                ranges = angles.max(axis=0) - angles.min(axis=0)
                print(
                    f"  LeftUpLeg rotation range (deg) in saved GLB: "
                    f"x={ranges[0]:.1f} y={ranges[1]:.1f} z={ranges[2]:.1f}"
                )
                if ranges.max() < 1.0:
                    print("  FAIL: LeftUpLeg shows <1 degree total rotation — bake likely failed")
                    all_ok = False
                else:
                    print("  OK: LeftUpLeg has meaningful rotation range")
                break

    return all_ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build argument parser for bake-bvh-to-glb."""
    parser = argparse.ArgumentParser(
        prog="bake-bvh-to-glb",
        description="Bake BVH mocap animations into ScottHall.glb.",
    )
    parser.add_argument(
        "--bvh",
        type=Path,
        default=_BVH_PATH,
        help=f"Path to the walking BVH file (default: {_BVH_PATH})",
    )
    parser.add_argument(
        "--glb",
        type=Path,
        default=_GLB_PATH,
        help=f"Path to the source GLB (default: {_GLB_PATH})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output GLB path (default: overwrites --glb in-place)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute animations but skip file writes.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for bake-bvh-to-glb.

    Returns:
        0 on success, 1 on error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    out_path: Path = args.out if args.out is not None else args.glb

    try:
        bake(
            bvh_path=args.bvh,
            glb_path=args.glb,
            out_path=out_path,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not args.dry_run:
        ok = validate_saved_glb(out_path)
        if not ok:
            print("\nValidation FAILED", file=sys.stderr)
            return 1
        print("\nValidation PASSED")

    return 0


if __name__ == "__main__":
    sys.exit(main())
