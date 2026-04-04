# Rive Character Pipeline Reference
<!-- Loaded by rive-skeletal-animator when task involves: sprite decomposition, Rive Editor rigging, bone hierarchy, vertex weighting, mesh deformation, wrestling proportions, .riv export, file size targets -->

The Rive character pipeline runs from a flat 2D sprite image to a fully rigged, animated `.riv` file ready for `@rive-app/react-canvas`. The Rive Editor is free at rive.app — no license required. This reference covers the full pipeline for bipedal wrestler characters.

## Pipeline Overview

```
1. DECOMPOSE   Sprite → separate body part layers (Photoshop/Figma/Aseprite)
2. IMPORT      Layers → Rive Editor as images
3. RIG         Place bones, build hierarchy, bind meshes
4. WEIGHT      Assign vertex weights at joints
5. ANIMATE     Build animation clips on the timeline
6. STATE MACHINE  Wire clips to a state machine with inputs
7. EXPORT      Save as .riv — target < 100KB per character
```

## Step 1: Sprite Decomposition

The input is a single wrestler sprite (400×400 or 900px). Split it into discrete body part images before importing to Rive.

### Body Parts for a Humanoid Wrestler

| Layer name | Notes |
|------------|-------|
| `head` | Full head including hair/mask |
| `neck` | Short connecting piece |
| `torso` | Upper body, chest, shoulders area |
| `upper_arm_l` / `upper_arm_r` | Shoulder to elbow |
| `lower_arm_l` / `lower_arm_r` | Elbow to wrist |
| `hand_l` / `hand_r` | Fist or open hand |
| `pelvis` | Hip connector between torso and legs |
| `upper_leg_l` / `upper_leg_r` | Hip to knee |
| `lower_leg_l` / `lower_leg_r` | Knee to ankle |
| `foot_l` / `foot_r` | Boot/shoe |

**Overlap tip**: Parts need 5–10px overlap at joints so seams don't appear during rotation. The upper arm overlaps into the shoulder area of the torso; the lower arm overlaps into the upper arm near the elbow.

**Wrestling proportions to maintain**: Wrestlers have exaggerated upper-body mass. The torso layer should be ~40% of total character height. Shoulders and upper arms are wide — preserve this in decomposition, don't trim aggressively.

**Tools**:
- Photoshop: use "Export Layers to Files" (File → Scripts → Export Layers to Files)
- Figma: select each layer group, Ctrl+Shift+E to export as PNG at 2x
- Aseprite (if sprite is pixel art): Layer → Export spritesheet per layer

## Step 2: Import to Rive Editor

1. Open rive.app — create a new file
2. Set artboard size to match your target canvas: 400×400 for PlayerCharacter, 900×900 for EnemyCharacter
3. Import each body part PNG: File → Import Image → repeat for all parts
4. Arrange images in the artboard to reconstruct the original sprite position

**Z-order matters**: Set layer order before rigging. Typical order (back to front):
- foot_r, lower_leg_r, upper_leg_r (back leg)
- pelvis
- lower_arm_r, upper_arm_r (back arm)
- torso
- head, neck
- upper_leg_l, lower_leg_l, foot_l (front leg)
- upper_arm_l, lower_arm_l, hand_l, hand_r (front arm)

## Step 3: Bone Hierarchy

Switch to Rig mode in the Rive Editor (Bones tool). Build the hierarchy from Root down.

### Standard Wrestler Bone Hierarchy

```
Root (at center of mass / hips)
├── Pelvis
│   ├── Spine1
│   │   └── Spine2
│   │       └── Chest
│   │           ├── Neck
│   │           │   └── Head
│   │           ├── Shoulder_L
│   │           │   └── UpperArm_L
│   │           │       └── LowerArm_L
│   │           │           └── Hand_L
│   │           └── Shoulder_R
│   │               └── UpperArm_R
│   │                   └── LowerArm_R
│   │                       └── Hand_R
│   ├── UpperLeg_L
│   │   └── LowerLeg_L
│   │       └── Foot_L
│   └── UpperLeg_R
│       └── LowerLeg_R
│           └── Foot_R
```

**Bone placement rules**:
- Place bone origin at the joint pivot point (not the center of the limb)
- UpperArm_L origin → center of shoulder socket
- LowerArm_L origin → center of elbow
- Hand_L origin → center of wrist
- Same pattern for legs

**Spine chain**: Two spine bones (Spine1 at lumbar, Spine2 at thoracic) allow for the slight lean and chest-out posing that makes wrestlers look imposing. A single spine bone produces stiff, robotic motion.

## Step 4: Mesh Deformation and Vertex Weighting

After placing bones, bind each image layer to the bones that should influence it.

### Binding

Select an image layer → Bones panel → "Bind Bone" → select the controlling bone.

For rigid parts with no deformation (head, hands, feet), bind to a single bone with 100% weight.

For joint areas that need smooth deformation, use mesh binding:
- Select image → Convert to Mesh (creates a vertex grid)
- Set mesh density: 4–6 subdivisions for limbs, more for areas with complex deformation
- Select vertices near the joint and assign weights to both adjacent bones

### Vertex Weighting at Key Joints

**Elbow (UpperArm ↔ LowerArm)**:
- Upper arm vertices: 100% UpperArm weight
- Lower arm vertices: 100% LowerArm weight
- Joint area (3–5px radius): blend 50/50

**Shoulder (Chest ↔ UpperArm)**:
- Torso/chest vertices near shoulder: 80% Chest, 20% UpperArm
- Upper arm vertices: 100% UpperArm (or 90/10 blend near shoulder cap)

**Knee**: Same pattern as elbow — 50/50 blend in the 5px radius around the joint pivot

**Hip**: 60% Pelvis / 40% UpperLeg blend at the hip crease

**Wrestler note**: The wide shoulder silhouette needs the shoulder cap mesh to blend between Chest and Shoulder_L/R bones — otherwise rotating the arm leaves a hard seam where the shoulder meets the torso.

## Step 5: Animation Clips

Switch to Animate mode. Build each clip on the timeline. See `rive-animation-library.md` for the full clip list and exact durations.

### Timeline basics

- Each clip is a separate "animation" in the Animations panel
- Key the starting pose on frame 0
- Key each intermediate pose
- Key the end pose (for looping clips, end pose = start pose)
- Set loop mode: Loop (endless), One-Shot (plays once and stops), or Ping-Pong

### Idle: the foundation clip

The idle animation is the most important — characters spend most of their time in it. For wrestlers:

1. **Chest rise** (breathing): Chest bone Y translates +3px over 1s, returns to 0 over 1s. Loop.
2. **Weight shift**: Root bone X translates ±4px on a 3s sine curve. Subtle.
3. **Head bob**: Head bone rotates ±2° on a 4s curve. Very subtle.
4. **Fist pump**: Lower arm bones rotate slightly (±5°) on a 2s curve.

All idle curves should be eased (ease-in-out), never linear — linear motion looks mechanical.

**Matching original Framer Motion**: The current `y: [0, -3, 0]` over 4s is a simple vertical float. The Rive idle should replace this with bone-driven motion at the same visual amplitude. The Root bone Y translation of -3px on a 4s loop matches the original exactly.

### Hit react: the impact clip

1. Frame 0: Idle pose
2. Frame 4 (~0.07s at 60fps): Head snaps back (Head rotate -20°), torso leans back (Spine1 rotate -10°), arms fly up slightly
3. Frame 12 (~0.2s): Stagger peak — feet shift back, full body lean
4. Frame 24 (~0.4s): Return to near-idle pose
5. Loop mode: One-Shot

The red flash from the original Framer Motion implementation was a CSS overlay — if the game needs that visual, it can be a separate CSS element layered over the RiveComponent canvas, since Rive doesn't do CSS effects.

## Step 6: Exporting .riv Files

File → Export → Rive File (`.riv`)

### File size checklist

| Factor | Impact | Target |
|--------|--------|--------|
| Image resolution per layer | High | Each part max 256×256px |
| Mesh vertex count | Medium | ≤ 100 vertices per mesh |
| Number of animation clips | Low | 10–12 clips is fine |
| Keyframe count per clip | Low | Use sparse keyframes, not every frame |

Target: **< 100KB per character .riv file**.

If over budget:
1. Reduce image dimensions — 2x PNG often has more resolution than needed
2. Compress embedded images in Rive: Artboard → Image → Quality slider (70% is usually invisible)
3. Reduce mesh density on non-deforming parts (convert back to rigid images)

### Asset placement

Save `.riv` files to:
```
src/assets/characters/player.riv
src/assets/characters/enemy-[name].riv
```

Import with `?url` suffix in components:
```tsx
import playerRiv from '../assets/characters/player.riv?url';
```

## Rive Editor Workflow Tips

**Keyboard shortcuts**:
- `V` — Select tool
- `B` — Bone tool
- `M` — Mesh tool
- `A` — Animate mode
- `Ctrl+Z` — Undo (generous undo history)
- `Space+drag` — Pan canvas

**Rig testing before animating**: Before building any animation clips, test the rig by manually rotating bones in Rig mode. Every joint should deform cleanly. Fix vertex weighting issues now — they're much harder to fix after you have keyframes.

**Artboard origin**: Place the character's foot baseline at the artboard's bottom center. This makes `Alignment.BottomCenter` in the React component keep the character grounded regardless of canvas scaling.

**Saving .riv locally**: The Rive Editor autosaves to your account. Use File → Download to save a local `.riv` copy that goes into version control alongside the source code.

## Wrestler-Specific Considerations

**Muscular builds**: Exaggerated shoulder width and chest depth. Keep Shoulder_L/R bones wide-set and make the Chest bone heavy. Don't trim the torso silhouette — the bulk is intentional.

**Mask/face designs**: Some wrestlers wear masks with complex geometry. Treat the mask as part of the `head` layer — don't decompose it further. Bone rigging for a mask is just the head bone rotation.

**Belt/championship prop**: If a character has a title belt, add it as a child of the Pelvis or Spine1 bone so it moves with the body. Separate layer, bound to Pelvis.

**Entrance robe**: A ring entrance robe needs its own bones — add "Cape_L" and "Cape_R" as children of the Chest bone, with mesh deformation for flowing fabric. This is for the `entrance` animation only; other animations don't need the robe visible.
