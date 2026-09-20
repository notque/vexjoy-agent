---
name: game-asset-generator
promoted_to: game-dev
description: "Generate game assets through this repository's Meshy, World Labs, and fal.ai scripts and preserve their local download, metadata, and integration contracts."
agent: typescript-frontend-engineer
user-invocable: false
command: /game-assets
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit]
routing:
  triggers: [meshy, text to 3d, world labs, gaussian splat, fal ai game asset, rig game model]
  not_for: "generic asset search, hand-authored pixel art, or game-engine programming"
  pairs_with: [frontend, typescript-frontend-engineer]
  complexity: Medium
  category: game-development
---

# Game asset generator

Use this only for the repository's external generation integrations. Load one reference:

| Output | Reference | Local executable |
|---|---|---|
| Meshy GLB, rig, or animation | `references/meshyai.md` | `scripts/meshy-generate.mjs` |
| World Labs splat environment | `references/worldlabs.md` | API procedure in the reference |
| fal.ai image or texture | `references/fal-ai-image.md` | `scripts/fal_queue_image_run.py` |

Inspect script help/source before running it; scripts, not prose examples, define current arguments.

## Durable contract

1. Confirm the corresponding key exists without printing its value (`MESHY_API_KEY`, `WLT_API_KEY`, or `FAL_KEY`). A missing key is a blocker, not permission to switch providers silently.
2. Generate into a temporary or raw path. Download remote outputs immediately; provider URLs expire.
3. Save a sidecar containing provider, model/endpoint, prompt, task/asset ID, generation time, and source URL. Secrets never enter the sidecar.
4. Validate nonzero size and parseability, then optimize GLBs with `scripts/optimize-glb.mjs` when the consumer supports its compression.
5. Copy only validated artifacts to the stable game asset path.

## Integration facts that commonly fail

- Meshy is preview then refine. Auto-rig only a clearly humanoid, textured biped with distinct limbs.
- A Draco-compressed GLB requires a configured `DRACOLoader` before `GLTFLoader` loads it.
- Clone a rigged scene with `SkeletonUtils.clone()`. `scene.clone()` breaks skeleton bindings and commonly produces a T-pose.
- World Labs splats require the orientation and raycast corrections documented in `worldlabs.md`; visual orientation and collision direction must be fixed together.
- fal.ai authentication uses `Key <FAL_KEY>`, not Bearer authentication.
- A zero-byte or unparsable download is regenerated from sidecar data; do not attempt repair.

Completion means a durable local file, sidecar, validation result, and a consumer smoke test—not merely a completed provider task.
