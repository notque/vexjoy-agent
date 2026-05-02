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
  pairs_with:
    - game-sprite-pipeline
    - phaser-gamedev
  agents:
    - rive-skeletal-animator
    - pixijs-combat-renderer
    - game-asset-generator
---

# Motion Pipeline Skill

CPU-only motion data processing for game animation, inspired by Meta's ai4animationpy (CC BY-NC 4.0). All operations use numpy and scipy -- no GPU or PyTorch required.

## Why standalone implementations?

ai4animationpy's `Math/Tensor.py` imports `torch` unconditionally at the top level, propagating through every module. Zero ai4animationpy modules are importable without PyTorch. The standalone implementations in `scripts/motion-pipeline.py` replicate key algorithms using only numpy + scipy.

## Environment setup

```bash
# Create venv (one-time)
python3 -m venv /home/feedgen/vexjoy-agent/motion-pipeline-env/

# Install CPU-only deps
motion-pipeline-env/bin/pip install numpy scipy pygltflib Pillow

# Verify
motion-pipeline-env/bin/python -c "import numpy; import scipy; import pygltflib; print('OK')"
```

The venv is gitignored.

## Commands

All commands output JSON to stdout. Errors go to stderr with exit code 1.

### import-bvh

Parse a BVH mocap file and print a motion summary.

```bash
motion-pipeline-env/bin/python scripts/motion-pipeline.py import-bvh FILE \
  [--scale 0.01]   # scale cm->m for CMU/Mixamo files
```

Output: `name`, `num_frames`, `num_joints`, `framerate`, `total_time_seconds`, `bones[]`, `root_trajectory` (x/y/z range).

### extract-contacts

Detect ground contact frames per bone using height + velocity thresholds. Replicates `ContactModule.GetContacts()`.

```bash
motion-pipeline-env/bin/python scripts/motion-pipeline.py extract-contacts FILE \
  --bones LeftFoot RightFoot \
  --height 0.1 \
  --vel 0.5
```

Output: `{ "bones": { "<name>": { "contact_frames": [...] } }, "total_frames": N }`.

### decompose

Split motion into root trajectory (WHERE + HOW) and per-joint local Euler angles (POSE). Implements RootModule / MotionModule decomposition.

```bash
motion-pipeline-env/bin/python scripts/motion-pipeline.py decompose FILE \
  --hip Hips
```

Output: `root_trajectory.positions[]`, `root_trajectory.velocities[]`, `root_trajectory.facing_directions[]`, `per_joint_euler_zyx_degrees{}`.

First 5 frames shown in stdout; full data requires piping to a file.

### blend

Blend two BVH clips at fixed alpha using SLERP rotations and LERP positions. Clips must share the same bone hierarchy.

```bash
motion-pipeline-env/bin/python scripts/motion-pipeline.py blend FILE_A FILE_B \
  --alpha 0.5
```

### solve-ik

Run FABRIK inverse kinematics on a bone chain at a single frame.

```bash
motion-pipeline-env/bin/python scripts/motion-pipeline.py solve-ik FILE \
  --chain Hips:LeftFoot \
  --target 0.2,0.05,0.3 \
  --frame 10
```

Output: `chain[]`, `target[]`, `initial_positions[]`, `solved_positions[]`, `end_effector_error` (metres).

### generate-move-ts

Convert BVH mocap into a TypeScript `MoveFrame` function for road-to-aew's `wrestlingMoves.ts` interface. Outputs keyframe-interpolated TypeScript.

```bash
motion-pipeline-env/bin/python scripts/generate-move-ts.py BVH MOVE_NAME \
  [--scale 0.01] \
  [--contact-bones LeftToeBase RightToeBase LeftHand RightHand] \
  [--num-keyframes 12] \
  [--hip-bone Hips] \
  [--output path/to/output.ts]
```

| Argument | Default | Purpose |
|---|---|---|
| `BVH` | -- | Path to .bvh mocap file |
| `MOVE_NAME` | -- | Kebab-case name (e.g. `roundhouse-kick`) for TS identifiers |
| `--scale` | `0.01` | Position scale; 0.01 converts cm->m |
| `--contact-bones` | `LeftToeBase RightToeBase LeftHand RightHand` | Bones for impact window detection |
| `--num-keyframes` | `12` | Keyframe count in output array (min 2) |
| `--hip-bone` | `Hips` | Root bone name for trajectory extraction |
| `--output` | stdout only | Write TS to this file path |

The script imports `motion-pipeline.py` via `importlib` (not subprocess), bypassing the 5-frame CLI truncation for full frame access.

**Output structure:**

```typescript
// Generated from roundhouse-kick.bvh on 2026-04-13
// Keyframes: 12, Impact window: 0.45-0.55
const ROUNDHOUSE_KICK_KEYFRAMES = [...] as const;

export function getRoundhouseKick(progress: number): MoveFrame {
  // keyframe lookup + linear interpolation
  // isImpact based on detected contact window
  return { attacker, defender, isImpact };
}
```

Attacker `offsetX/Y/Z` are root trajectory positions normalized to origin. Rotations in radians (converted from BVH Euler ZYX degrees). Defender reaction computed procedurally: pushed backward at impact, eases to mat post-impact.

**Impact detection:** Finds the first run of 3+ consecutive contact frames across specified bones. For walking/idle clips (feet always down), the window is frame-0 and `isImpact` is nearly never true -- correct behavior.

**Validation:** Prints summary to stderr (trajectory range, impact window, syntax check). Exit code 1 on failure.

## Data architecture pattern

```
Animation State
  root_trajectory   -- WHERE (position, velocity, facing direction)
  per_joint_euler   -- HOW (local pose in ZYX Euler degrees)
  contact_frames    -- WHAT (contact states for feet, hands)
  [guidance]        -- WHY (intent; handled at game engine layer)
```

This separation enables: different movement speeds without distorting pose, contact-driven game events (damage, sound, VFX), and AI/input guidance independent of motion playback.

## Source reference: ai4animationpy modules adopted

| ai4animationpy module | This script equivalent | Notes |
|-----------------------|------------------------|-------|
| `Import/BVHImporter.BVH` | `load_bvh()` | Same parsing; scipy replaces torch |
| `Animation/Motion` | `Motion` dataclass | numpy-only |
| `Animation/ContactModule` | `extract_contacts()` | Identical height + velocity criterion |
| `Animation/RootModule` | `decompose()` root section | FK decomposition via matrix inverse |
| `Animation/MotionModule` | `decompose()` joint section | Local Euler extraction via scipy |
| `IK/FABRIK` | `solve_ik_fabrik()` | Same algorithm; no Actor dependency |

## Integration points

| Downstream agent | Data consumed |
|------------------|---------------|
| `rive-skeletal-animator` | `per_joint_euler_zyx_degrees` from decompose |
| `pixijs-combat-renderer` | `contact_frames` from extract-contacts |
| `combat-effects-upgrade` | `contact_frames` (impact timing) |
| `game-asset-generator` | Produces source BVH files for this pipeline |

## Sample BVH for testing

```
/tmp/ai4animationpy/Demos/BVHLoading/WalkingStickLeft_BR.bvh
```

Full-body biped walking clip from the Geno character rig.

## Reference: ai4animationpy

- Source: `/tmp/ai4animationpy` (cloned locally)
- License: CC BY-NC 4.0 (non-commercial)
- GitHub: https://github.com/facebookresearch/ai4animationpy
- ALL modules require torch at import time via `Math/Tensor.py` line 5. No conditional import path exists.
