# Building rigged characters, creatures and weapons with an agent in Blender

Load when an agent builds, rigs or animates a character, creature, prop or weapon in Blender, from a generated mesh
(Tripo and similar), a parametric base (MakeHuman) or a sculpt. Each rule says what goes wrong without it.

## Before the first bone
1. **Generate or pose the body arms-away, legs-apart (A-pose).** A relaxed pose hides the armpits and inner thighs,
   and the rig tears there. If the project's rig standard is a T-pose, rebind to it after rigging.
2. **One concept sheet per thing.** Body, head and each weapon or prop get their own sheet, with the views that
   matter (a weapon: front, back and its working state, such as a bow strung or a chair folded). One picture of
   everything is not enough to build from.
3. **Clean the mesh first.** Scale to real size in metres, weld loose vertices, and cut out or seal parts that will
   tear when skinned (tongue, inner mouth, loose straps). Report vertex counts before and after.

## The skeleton
4. **Measure joints on the mesh; never guess.** Shoulders, elbows, wrists, knees, ankles and all 15 finger joints
   per hand are located on the model itself (cross-sections, narrowest rings, crease lines) and written to a file
   the rig is built from.
5. **Measure each limb on its own.** Left and right are never identical on a sculpted or generated mesh. Measure
   both sides (a 5 cm grid of cross-sections works) and place joints per side. Do not mirror by assumption.
6. **Render the skeleton coloured by body part** over the mesh before skinning: spine yellow, left arm blue, right
   arm red, legs green. A wrong bone shows in one second. Make this sheet part of every rig report.
7. **Add helper bones where volume collapses.** A bend that folds flat needs extra bones to hold the round: flanks
   on a creature that curls, shoulders, elbows, knees, hips, belly and neck on a human. Twist and corrective bones
   are part of the rig, not a later fix.

## Skinning
8. **Weights on a voxel copy when the mesh is in pieces.** Generated models arrive as dozens of separate shells,
   and gear sits on bodies; automatic weights tear them. Solve weights on a voxel-remeshed copy of the body and
   transfer them. Hard gear stays rigid to one bone.

## Weapons and props
9. **A weapon is its own rigged object**, with bones for what really moves: a bow's limbs bend and its string
   keeps its length, a chair folds, a ladder hinges, a table breaks at a seam. It attaches to hand sockets and is
   never baked into a body.
10. **One mesh, many states, no visible switch.** Standing to curled, open to folded, whole to broken: a state is a
    pose of the same rigged mesh wherever possible, not a swap that pops on screen.

## Animation
11. **Two-bone IK on every leg and arm, with the foot rolling.** The foot stays flat while planted, the heel lifts
    last on push-off and lands first on a step. That is where weight comes from.
12. **Tie motion to distance travelled.** Stride length drives walk and run playback, so feet never skate. A rolling
    thing turns by the distance it covers.
13. **A base clip set per model** (idle, walk, run, turn, hit, fall, get-up, death) before special moves.
14. **Check every frame before showing anything.** Scan every clip at full frame rate for pops, limbs through
    bodies and the weapon cutting through its holder. Sampled frames miss one-frame faults.

## Working with the agent
15. **Routine work goes to subagents.** Measuring, frame checks and renders run in subagents with their own
    context, so the main session stays for decisions and the job costs far fewer tokens.
16. **Every frame is computed.** No mocap or stock animation library is required for this method; that also keeps
    the result free of third-party data.
