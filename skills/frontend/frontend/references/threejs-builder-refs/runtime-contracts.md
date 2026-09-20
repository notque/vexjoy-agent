# Three.js runtime contracts

These notes retain failure-prone constraints that change implementation choices. Consult current Three.js docs for ordinary API usage and pin behavior to the repository's installed version.

## Paradigm ownership

- R3F owns renderer, scene, and frame scheduling. Use `useFrame`; a parallel RAF loop causes double renders and lifecycle leaks.
- Exactly one camera controller writes per frame. `OrbitControls` plus a custom follow/cinematic controller silently produces jitter or lockups; conditionally mount one.
- Imperative and WebGPU paths use `setAnimationLoop`. Dispose geometry, materials, textures, render targets, mixers, controls, and listeners when ownership ends.
- Cap DPR at 2 by default. Allocate reusable vectors outside hot loops.

## GLTF and animation

- Cache the loaded source, then clone instances. Animated/skinned models require `SkeletonUtils.clone(gltf.scene)`; ordinary `.clone()` shares/breaks skeleton bindings.
- Make the repository's forward-axis/unit contract explicit at the load boundary. Axis mismatch is the common cause of a model moving backward while its logic is correct.
- Start/fade only actions obtained from the loaded clip set; log clip and bone names before guessing exporter-specific identifiers.
- A progress event may lack `total`; do not turn that into a fake percentage.

## Lighting and postprocessing

- PBR assets that render black usually lack environment/direct light, not color.
- Bloom requires values above its threshold. For emissive-only pickup, use HDR emissive intensity and `toneMapped: false`; otherwise tone mapping clamps the signal before bloom.
- Resize renderer, camera projection, and every composer/render target together.
- No geometry/material creation in the animation loop.

## WebGPU / TSL

Verify the installed Three.js version before copying examples. In versions using the modern path, import renderer APIs from `three/webgpu` and TSL nodes from `three/tsl`. `renderer.init()` is asynchronous and must finish before the first render. Production WebGPU also requires a secure context; retain a WebGL fallback when support is not an explicit product requirement.

TSL nodes compose through node methods (`.mul()`, `.add()`, etc.); JavaScript arithmetic on nodes can yield invalid graphs. GLSL `ShaderMaterial` is not a drop-in WebGPU material. Node symbol names have changed across Three releases, so the lockfile and current docs outrank memorized snippets.

Failure map:

| Symptom | Check first |
|---|---|
| `navigator.gpu` absent | browser support and HTTPS |
| adapter request fails | hardware/browser policy; use fallback |
| TSL type mismatch | node type and installed Three version |
| compute changes nothing | dispatch count, storage-node write, render dependency |
| R3F camera jitters | more than one camera writer |
| clones animate together/break | incorrect skinned clone |
| bloom absent | pre-tone-map intensity and material `toneMapped` |
| mobile GPU stalls | DPR, shadows, post passes, allocations, draw calls |
