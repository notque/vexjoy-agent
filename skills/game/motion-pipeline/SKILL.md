---
name: motion-pipeline
promoted_to: game-dev
user-invocable: false
description: "Run this repository's CPU-only BVH processing and Road to AEW move conversion: contacts, root/pose decomposition, blending, FABRIK, and MoveFrame output."
allowed-tools: [Read, Bash, Write, Edit, Glob, Grep]
routing:
  triggers: [BVH import, contact detection, motion decomposition, motion blend, FABRIK, generate move ts]
  category: game-animation
  pairs_with: [game-dev]
---

# Motion pipeline

The implementation is `scripts/motion-pipeline.py`; Road to AEW conversion is `scripts/generate-move-ts.py`. Inspect their `--help` before use. They intentionally reimplement the required ai4animationpy algorithms with NumPy/SciPy because importing ai4animationpy pulls PyTorch through `Math/Tensor.py` even for CPU-only modules.

Use the repository venv when present (`motion-pipeline-env/bin/python`). Required packages are `numpy`, `scipy`, `pygltflib`, and `Pillow`; do not commit the venv.

## Commands and outputs

| Command | Decision-changing contract |
|---|---|
| `import-bvh FILE [--scale 0.01]` | Summary includes frames, joints, framerate, duration, bones, and root ranges. `0.01` converts common CMU/Mixamo centimetres to metres. |
| `extract-contacts FILE --bones ... --height H --vel V` | Contact requires both low height and low velocity. Output is per-bone frame indices. |
| `decompose FILE --hip Hips` | Separates root position/velocity/facing from local joint Euler ZYX degrees. CLI previews five frames; import the module for full arrays. |
| `blend A B --alpha X` | Uses SLERP for rotations and LERP for positions; hierarchies must match. |
| `solve-ik FILE --chain Root:End --target x,y,z --frame N` | FABRIK output includes initial/solved positions and end-effector error in metres. |
| `generate-move-ts.py BVH MOVE_NAME ...` | Emits keyframe-interpolated `MoveFrame` TypeScript; kebab-case move name, default 12 keyframes, default scale `0.01`. |

All command results are JSON on stdout; diagnostics/errors use stderr, and failure exits nonzero.

## Data contract

Keep these channels separate:

- `root_trajectory`: where the actor moves—position, velocity, facing.
- `per_joint_euler_zyx_degrees`: local pose.
- `contact_frames`: event timing for feet/hands.
- intent/guidance: game-engine state, never inferred from the clip by this pipeline.

The split allows speed changes without distorting pose and lets contact drive damage, sound, or VFX independently.

## Move conversion edge cases

- `generate-move-ts.py` imports the motion module directly to avoid the CLI's five-frame preview truncation.
- Attacker offsets are root positions normalized to the first frame; output rotations are radians even though decomposition returns degrees.
- Impact is the first run of at least three consecutive contact frames across configured bones. Walking/idle can therefore produce a frame-zero window and almost no `isImpact`; do not relabel it as a strike.
- The generated defender reaction is procedural, not recovered from BVH evidence.

Completion requires parseable output, stderr validation summary, and a consumer-level check of scale, bone names, hierarchy compatibility, and impact timing.
