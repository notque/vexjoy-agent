# Blender in a headless asset pipeline

Load when a game asset pipeline builds, bakes or previews models with Blender from scripts.

## Run it headless
- `blender -b --factory-startup -P script.py -- <args>`: background mode, no user prefs or add-ons leaking in,
  script arguments after `--` (`sys.argv[sys.argv.index("--") + 1:]`).
- Grep its output for `Error|Traceback|Saved` rather than trusting the exit code; Blender often exits 0 after a
  Python exception inside `-P`.
- One heavy Blender job at a time on a shared machine; builds that also render previews compete with browsers
  doing frame QA.

## Upgrading Blender safely (proven on 5.2.2 -> 5.3.0, Nov 2026)
1. Read the release notes per area (`developer.blender.org/docs/release_notes/<ver>/`: python_api, pipeline_io,
   cycles, modeling, sculpt, animation_rigging, geometry_nodes). Breaking changes are listed under Python API
   and the Compatibility block.
2. Download the official portable zip from `download.blender.org/release/BlenderX.Y/` together with its `.sha256`
   and verify the hash before unpacking.
3. Install side by side (portable folder); keep the old version as a fallback.
4. Render the same input with both versions and diff pixels. Identical or near-identical output means scripts
   can move; anything else gets investigated before switching.
5. Repoint scripts (search script files only, not generated data), back up each edited file, syntax-check
   (`py_compile`, `bash -n`), then run one real script on the new version.
6. Never switch a running build mid-run. Leave provenance strings inside hashed/pinned data files untouched:
   editing them changes their hash.

## Blender 5.3 features worth using in game pipelines
- Cycles texture-bake quality improved for small or thin triangles and near UV margins: re-bake thin gear
  (laces, tape, straps, stitching) and compare against the old bake.
- glTF exporter writes KTX2 via `KHR_texture_basisu`: GPU-compressed textures for web/mobile, smaller downloads,
  less GPU memory, faster first draw. three.js reads them with `KTX2Loader` plus the Basis transcoder.
- glTF import/export fixes for bone parenting to skinned meshes, vertex colours and custom properties.
- Python API: no removals; `PropertyGroup.name` default is read-only, `bpy.data.all_ids` order changed (do not
  depend on it). New: `Object/PoseBone.convert_rotation_mode`, `constraints.new(type, name=...)`,
  `gpu.types.GPUStorageBuf`, 2D `mathutils.kdtree`.
- Editor-only gains (manual work, not scripts): weight-paint auto-masking, Add Weight default brush, curves
  Cut brush for hair, quad-sphere primitive, duplicate multiple shape keys.
