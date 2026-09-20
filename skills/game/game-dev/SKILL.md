---
name: game-dev
description: "Use the repository's sprite-generation, Road to AEW, and game-specific asset integration contracts. Use for local game pipelines; ordinary game design and engine work needs no skill."
agent: project-coordinator-engineer
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Task, Skill]
routing:
  force_route: true
  not_for: "generic game design, generic Phaser help, or non-game frontend work"
  triggers: [game sprite pipeline, generate spritesheet, road to aew, wrestler sprite, portrait loop, sprite extraction, sprite anchoring]
  pairs_with: [frontend, workflow]
  complexity: Comprehensive
  category: game-development
---

# Game development

This skill carries only local knowledge that changes game-pipeline actions. For ordinary design, Phaser, canvas, audio, QA, or deployment work, rely on normal model competence and repository evidence.

## Route by artifact

| Request | Load |
|---|---|
| Run or repair the sprite pipeline | `references/game-sprite-pipeline.md` |
| Choose generation backend | `references/backend-chain.md` |
| Construct a prompt | `references/prompt-rules.md`; add `references/style-presets.md` only for a named house style |
| Remove a generated background | `references/bg-removal-local.md` |
| Detect or slice frames | `references/frame-detection.md`, `references/grid-shapes.md` |
| Align frames | `references/anchor-alignment.md` |
| Validate outputs or diagnose a known failure | `references/error-catalog.md`, `references/output-formats.md` |
| Integrate with Road to AEW | `references/road-to-aew-integration.md`; add `references/wrestler-archetypes.md` only for its procedural roster rules |
| Contain state-specific effects | `references/vfx-containment.md` |
| Delegate per-row generation | `references/subagent-delegation.md` |

Read only selected references. Scripts in `scripts/` are authoritative for flags, defaults, and output shapes; inspect `--help` or source rather than copying commands from memory.

## Failure-derived invariants

- Never report a row, frame, or sheet successful from process exit alone. Run the matching verifier and preserve its artifact receipt.
- Keep raw generation separate from deterministic post-processing. Regeneration is not a repair for slicing, chroma, anchoring, or assembly defects.
- Slice cells before content-aware extraction; whole-sheet connected components can merge adjacent poses.
- Preserve strict grid pitch unless the caller explicitly accepts inferred spacing. Silent correction launders malformed sheets into plausible output.
- Use mass-centroid anchoring by default; use ground-line only when foot contact must remain fixed.
- Despill before upscale; the reverse spreads chroma contamination into harder-to-classify pixels.
- Compare cell parity and frame distinctness, not merely dimensions and alpha presence.
- Do not hand-edit artifacts to make validation pass. Change the recorded prompt or deterministic stage and rerun.

## Completion

Return stable output paths, generation metadata, verification results, and retained failure artifacts. For Road to AEW, also run the integration checker in its reference; a valid standalone sheet is not proof that the live game loads it.
