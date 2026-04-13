---
name: motion-pipeline
user-invocable: true
description: "CPU-only motion data processing pipeline for game animation: BVH import, contact detection, root decomposition, motion blending, FABRIK IK. No GPU required."
allowed-tools:
  - Read
  - Bash
  - Write
  - Edit
  - Glob
  - Grep
version: 1.0.0
routing:
  triggers:
    - "mocap"
    - "motion data"
    - "animation pipeline"
    - "BVH import"
    - "contact detection"
    - "IK solve"
    - "motion blend"
    - "bone trajectory"
    - "root extraction"
    - "FABRIK"
    - "skeletal animation data"
  category: game-animation
  agents:
    - rive-skeletal-animator
    - pixijs-combat-renderer
    - game-asset-generator
---

# Motion Pipeline Skill

CPU-only motion data processing pipeline for game animation, inspired by Meta's
ai4animationpy framework (CC BY-NC 4.0). All operations run on numpy and scipy
with no GPU or PyTorch required.

## Why standalone implementations?

ai4animationpy's `Math/Tensor.py` imports `torch` unconditionally at the top
level, which propagates through every module (Animation, Import, IK, Math).
This means zero ai4animationpy modules are importable without PyTorch installed.
The standalone implementations in `scripts/motion-pipeline.py` replicate the
key algorithms from their source code using only numpy + scipy.

## Environment setup

```bash
# Create venv (one-time)
python3 -m venv /home/feedgen/claude-code-toolkit/motion-pipeline-env/

# Install CPU-only deps
motion-pipeline-env/bin/pip install numpy scipy pygltflib Pillow

# Verify
motion-pipeline-env/bin/python -c "import numpy; import scipy; import pygltflib; print('OK')"
```

The venv is gitignored. The skill documents setup; it does not commit the venv.

## Commands

All commands output JSON to stdout. Errors go to stderr with exit code 1.

### import-bvh

Parse a BVH mocap file and print a motion summary.

```bash
motion-pipeline-env/bin/python scripts/motion-pipeline.py import-bvh FILE \
  [--scale 0.01]   # scale cm->m for CMU/Mixamo files
```

Output fields: `name`, `num_frames`, `num_joints`, `framerate`,
`total_time_seconds`, `bones[]`, `root_trajectory` (x/y/z range).

### extract-contacts

Detect ground contact frames per bone (foot, hand) using height + velocity
thresholds. Replicates `ContactModule.GetContacts()` from ai4animationpy.

```bash
motion-pipeline-env/bin/python scripts/motion-pipeline.py extract-contacts FILE \
  --bones LeftFoot RightFoot \
  --height 0.1 \
  --vel 0.5
```

Output: per-bone `contact_frames[]`, `contact_count`, `contact_ratio`.

### decompose

Split motion into root trajectory (WHERE + HOW) and per-joint local Euler
angles (POSE). Implements the RootModule / MotionModule decomposition pattern.

```bash
motion-pipeline-env/bin/python scripts/motion-pipeline.py decompose FILE \
  --hip Hips
```

Output: `root_trajectory.positions[]`, `root_trajectory.velocities[]`,
`root_trajectory.facing_directions[]`, `per_joint_euler_zyx_degrees{}`.

First 5 frames shown in stdout; full data requires piping to a file.

### blend

Blend two BVH clips at a fixed alpha using SLERP rotations and LERP positions.
Clips must share the same bone hierarchy.

```bash
motion-pipeline-env/bin/python scripts/motion-pipeline.py blend FILE_A FILE_B \
  --alpha 0.5
```

Output: summary of the blended motion.

### solve-ik

Run FABRIK inverse kinematics on a bone chain at a single frame.

```bash
motion-pipeline-env/bin/python scripts/motion-pipeline.py solve-ik FILE \
  --chain Hips:LeftFoot \
  --target 0.2,0.05,0.3 \
  --frame 10
```

Output: `chain[]`, `target[]`, `initial_positions[]`, `solved_positions[]`,
`end_effector_error` (metres).

## Data architecture pattern

The decomposition from ai4animationpy becomes a design contract for all
game animation work:

```
Animation State
  root_trajectory   -- WHERE (position, velocity, facing direction)
  per_joint_euler   -- HOW (local pose in ZYX Euler degrees)
  contact_frames    -- WHAT (contact states for feet, hands)
  [guidance]        -- WHY (intent; handled at game engine layer)
```

This separation enables:
- Different movement speeds without distorting body pose
- Contact-driven game events (damage triggers, sound, VFX)
- AI/input guidance independent of motion playback

## Source reference: ai4animationpy modules adopted

| ai4animationpy module | This script equivalent | Notes |
|-----------------------|------------------------|-------|
| `Import/BVHImporter.BVH` | `load_bvh()` | Same parsing logic; scipy replaces torch |
| `Animation/Motion` | `Motion` dataclass | numpy-only; no torch backend |
| `Animation/ContactModule` | `extract_contacts()` | Height + velocity criterion identical |
| `Animation/RootModule` | `decompose()` root section | FK decomposition via matrix inverse |
| `Animation/MotionModule` | `decompose()` joint section | Local Euler extraction via scipy |
| `IK/FABRIK` | `solve_ik_fabrik()` | Algorithm identical; no Actor dependency |

## Integration points

| Downstream agent | Data consumed |
|------------------|---------------|
| `rive-skeletal-animator` | `per_joint_euler_zyx_degrees` from decompose |
| `pixijs-combat-renderer` | `contact_frames` from extract-contacts |
| `combat-effects-upgrade` | `contact_frames` (impact timing) |
| `game-asset-generator` | Produces source BVH files for this pipeline |

## Sample BVH for testing

A walking cycle from ai4animationpy demos is available at:
```
/tmp/ai4animationpy/Demos/BVHLoading/WalkingStickLeft_BR.bvh
```

This is a full-body biped walking clip from the Geno character rig.

## Reference: ai4animationpy

- Source: `/tmp/ai4animationpy` (cloned locally)
- License: CC BY-NC 4.0 (non-commercial; aligned with hobby game projects)
- GitHub: https://github.com/facebookresearch/ai4animationpy
- Key finding: ALL modules require torch at import time via `Math/Tensor.py` line 5.
  No conditional import path exists. Standalone implementations are the correct approach.
