# Rive Character Pipeline Reference
<!-- Loaded by rive-skeletal-animator when task involves: sprite decomposition, Rive Editor rigging, bone hierarchy, vertex weighting, mesh deformation, wrestling proportions, .riv export, file size targets -->

Pipeline from flat 2D sprite to fully rigged, animated `.riv` file for `@rive-app/react-canvas`. Rive Editor is free at rive.app.

## Pipeline Overview

```
1. DECOMPOSE   Sprite → separate body part layers (Photoshop/Figma/Aseprite)
2. IMPORT      Layers → Rive Editor as images
3. RIG         Place bones, build hierarchy, bind meshes
4. WEIGHT      Assign vertex weights at joints
5. ANIMATE     Build clips on timeline
6. STATE MACHINE  Wire clips to state machine with inputs
7. EXPORT      Save as .riv — target < 100KB per character
```

## Step 1: Sprite Decomposition

Input: single wrestler sprite (400x400 or 900px). Split into discrete body part images.

### Body Parts

| Layer name | Notes |
|------------|-------|
| `head` | Full head including hair/mask |
| `neck` | Short connector |
| `torso` | Upper body, chest, shoulders |
| `upper_arm_l` / `upper_arm_r` | Shoulder to elbow |
| `lower_arm_l` / `lower_arm_r` | Elbow to wrist |
| `hand_l` / `hand_r` | Fist or open hand |
| `pelvis` | Hip connector |
| `upper_leg_l` / `upper_leg_r` | Hip to knee |
| `lower_leg_l` / `lower_leg_r` | Knee to ankle |
| `foot_l` / `foot_r` | Boot/shoe |

**Overlap**: 5-10px at joints to prevent seams during rotation.

**Wrestling proportions**: Exaggerated upper-body mass. Torso ~40% of total height. Wide shoulders — don't trim aggressively.

**Tools**: Photoshop (Export Layers to Files), Figma (Ctrl+Shift+E per layer at 2x), Aseprite (layer export).

## Step 2: Import to Rive Editor

1. Create new file at rive.app
2. Artboard size: 400x400 (Player) or 900x900 (Enemy)
3. Import each body part PNG
4. Arrange to reconstruct original position

**Z-order** (back to front): foot_r, lower_leg_r, upper_leg_r → pelvis → lower_arm_r, upper_arm_r → torso → head, neck → front leg → front arm

## Step 3: Bone Hierarchy

Switch to Rig mode (Bones tool).

```
Root (center of mass / hips)
├── Pelvis
│   ├── Spine1
│   │   └── Spine2
│   │       └── Chest
│   │           ├── Neck → Head
│   │           ├── Shoulder_L → UpperArm_L → LowerArm_L → Hand_L
│   │           └── Shoulder_R → UpperArm_R → LowerArm_R → Hand_R
│   ├── UpperLeg_L → LowerLeg_L → Foot_L
��   └── UpperLeg_R → LowerLeg_R → Foot_R
```

**Placement**: Bone origin at joint pivot (not limb center). Two spine bones (Spine1 lumbar, Spine2 thoracic) for lean and chest-out posing.

## Step 4: Mesh Deformation and Vertex Weighting

Bind each image layer to controlling bones.

**Rigid parts** (head, hands, feet): single bone, 100% weight.

**Joint areas**: Convert to mesh (4-6 subdivisions for limbs), assign blended weights.

### Vertex Weighting

| Joint | Weighting |
|-------|-----------|
| Elbow | 50/50 UpperArm/LowerArm in 3-5px radius |
| Shoulder | 80% Chest / 20% UpperArm near shoulder cap |
| Knee | 50/50 like elbow |
| Hip | 60% Pelvis / 40% UpperLeg at crease |

Wide shoulder silhouette needs shoulder cap mesh to blend between Chest and Shoulder bones — otherwise arm rotation leaves a hard seam.

## Step 5: Animation Clips

Switch to Animate mode. See `rive-animation-library.md` for full clip list and durations.

### Timeline basics
- Each clip is a separate "animation" in the Animations panel
- Key start pose on frame 0, intermediates, end pose
- Loop modes: Loop, One-Shot, Ping-Pong

### Idle: the foundation clip

1. **Chest rise** (breathing): Chest Y +3px over 1s, return over 1s
2. **Weight shift**: Root X ±4px on 3s sine
3. **Head bob**: Head ±2° on 4s curve
4. **Fist pump**: Lower arm ±5° on 2s curve

All curves ease-in-out. The Root Y translation of -3px on 4s loop matches the original Framer Motion `y: [0, -3, 0]`.

### Hit react

1. Frame 0: Idle pose
2. Frame 4: Head snap back (-20°), torso lean (-10°), arms fly up
3. Frame 12: Stagger peak
4. Frame 24: Near-idle
5. One-Shot

Red flash from Framer Motion: implement as CSS element over RiveComponent canvas.

## Step 6: Exporting .riv Files

File → Export → Rive File (`.riv`)

### File size checklist

| Factor | Impact | Target |
|--------|--------|--------|
| Image resolution per layer | High | Max 256x256px each |
| Mesh vertex count | Medium | ≤ 100 per mesh |
| Animation clips | Low | 10-12 is fine |
| Keyframes per clip | Low | Sparse, not every frame |

Target: **< 100KB per character**.

If over budget: reduce image dimensions, compress embedded images (70% quality), reduce mesh density on non-deforming parts.

### Asset placement

```
src/assets/characters/player.riv
src/assets/characters/enemy-[name].riv
```

Import: `import playerRiv from '../assets/characters/player.riv?url';`

## Rive Editor Tips

**Shortcuts**: V (Select), B (Bone), M (Mesh), A (Animate), Ctrl+Z (Undo), Space+drag (Pan)

**Test rig before animating**: Manually rotate bones in Rig mode. Fix vertex weighting before adding keyframes.

**Artboard origin**: Foot baseline at bottom center. `Alignment.BottomCenter` in React keeps character grounded.

**Local save**: File → Download for version-controlled `.riv`.

## Wrestler-Specific Considerations

**Muscular builds**: Wide Shoulder bones, heavy Chest bone. Don't trim torso silhouette.

**Masks**: Treat as part of `head` layer. Single head bone rotation.

**Belt/championship**: Add as Pelvis or Spine1 child bone. Separate layer.

**Entrance robe**: Needs own bones (Cape_L/R as Chest children) with mesh deformation. `entrance` animation only.
