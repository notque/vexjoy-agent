---
name: game-dev
description: "Game development: design, asset pipelines, Phaser, vanilla JS frontend, GM mode, match booking."
agent: project-coordinator-engineer
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - Task
  - Skill
routing:
  force_route: true
  not_for: "non-game frontend (use frontend), non-game backend (use workflow)"
  triggers:
    - game design
    - game design audit
    - game improvement
    - core loop
    - game feel
    - game balance
    - game economy
    - make game
    - game pipeline
    - game audio
    - deploy game
    - phaser
    - 2d game
    - platformer
    - arcade physics
    - tilemap
    - AI sprite
    - generate sprite
    - spritesheet pipeline
    - animated spritesheet
    - large GM implementation
    - GM systems overhaul
    - pixel art
    - screen shake
    - game qa
  pairs_with:
    - frontend
    - workflow
  complexity: Comprehensive
  category: game-development
---

# Game Development

Five modes: **Design** (diagnosis, auditing, improvement), **Pipeline** (full
lifecycle orchestration), **Sprite** (AI sprite generation), **Phaser** (2D
engine builds), **GM** (large multi-system implementations). Cross-cutting
concerns (audio, QA, deploy) load as needed. Classify the request and follow
the matching section.

## Mode Selection

| Mode | Signals |
|------|---------|
| **Design** | game design, improve game, retention, churn, core loop, audit, game feel, balance, economy |
| **Pipeline** | make game, scaffold, game lifecycle, game audio, deploy game, game QA |
| **Sprite** | AI sprite, generate character, portrait, spritesheet, animated sheet, pixel art |
| **Phaser** | Phaser, 2D game, platformer, arcade physics, tilemap, side scroller |
| **GM** | large GM implementation, multi-system GM, CPU systems, multi-wave overhaul |

If the request spans modes, load both primary references. Design + Pipeline is
common (design an improvement then implement it). Sprite + Phaser is common
(generate assets then wire into a Phaser game).

---

## Design Mode

Evidence-led game design diagnosis with 61 runnable capabilities. Start from
repository evidence; never guess when the repo can answer.

### Workflow

1. **Intake.** Read target repository's governing files. Search for game, product, UI, analytics, and research guidance. Use file search to find design docs, player copy, rules, UI, config, tests, analytics, issues. Separate facts into: observed, documented, measured, inferred.
2. **Ask only what the repo cannot answer.** Which player moment matters? What external evidence exists (playtests, telemetry, reviews)? Which constraints bind (platform, phase, team, time)?
3. **Load references.** Route greedily -- load every module that could change the recommendation:

| Signal | Load |
|--------|------|
| Promise, fantasy, loops, goals | `references/core-loop-and-pillars.md` |
| Ideation, novelty, removal, reuse | `references/creative-and-options.md` |
| Player motives, personas, values | `references/player-and-social.md` |
| Information, bias, randomness | `references/cognition-and-choice.md` |
| Failure, difficulty, fairness | `references/fairness-and-failure.md` |
| FTUE, flow, friction, session | `references/pacing-and-return.md` |
| Co-op, competition, social | `references/social-and-competitive.md` |
| Rewards, currencies, passes | `references/progression-and-economy.md` |
| Pitch, mood, prototype | `references/emotion-and-presentation.md` |
| Scope, sequence, estimates | `references/planning-and-production.md` |
| Full health report | All modules + `references/full-diagnostic.md` |

4. **Diagnose.** Trace the player path: cue -> interpretation -> choice -> response -> cost/reward -> feedback -> next intention. State player consequence, evidence, competing explanations, confidence, severity.
5. **Decide.** Offer 2-5 distinct options. For each: player-visible change, pillar fit, scope, dependencies, effort, reversibility, success metric, stop rule. Prefer reversible experiments. Reject dark patterns.
6. **Completion gate.** Every finding has evidence or is marked as inference. Every recommendation has a validation plan.

### Discovery Mode

When request is bare "game design" or "what reviews are available": load `references/capability-catalog.md` and present the full domain-organized catalog of 61 capabilities.

### Autonomous Improvement

When asked to improve a game's retention, churn, or engagement: load `references/autonomous-improvement.md`. Inspect the real game, run relevant capabilities, make the smallest safe reversible improvement, verify, leave a measurement plan.

---

## Pipeline Mode

Full lifecycle orchestration: SCAFFOLD -> ASSETS -> DESIGN -> AUDIO -> QA ->
DEPLOY. Each phase can be entered independently.

### Entry Detection

| Request | Entry Phase |
|---------|-------------|
| make a game, new game | SCAFFOLD |
| generate assets, add sprites | ASSETS |
| add juice, particles, screen shake | DESIGN |
| add audio, background music | AUDIO |
| test game, visual regression | QA |
| deploy, ship, publish, iOS | DEPLOY |

### Phase 1: SCAFFOLD

Detect engine (Three.js, Phaser, or vanilla canvas). Delegate to the appropriate engine skill or scaffold from template.

### Phase 2: ASSETS

Route by asset type:

| Asset | Reference |
|-------|-----------|
| 3D model, GLB, mesh | `references/game-asset-generator.md` + `references/meshyai.md` |
| Sprite, pixel art, tile | Load Sprite mode below |
| Image, texture, concept art | `references/fal-ai-image.md` |
| Environment, gaussian splat | `references/worldlabs.md` |
| Free assets, Sketchfab | `references/asset-sources.md` |
| Motion data, BVH, mocap | `references/motion-pipeline.md` |

### Phase 3: DESIGN

Add game feel: screen shake, particles, hit-stop, juice. Load `references/game-feel-patterns.md`.

### Phase 4: AUDIO

Web Audio API patterns, AudioManager, AudioBridge. Load `references/game-audio.md`.

### Phase 5: QA

Automated testing, visual regression, Playwright, canvas seams. Load `references/game-qa.md`.

### Phase 6: DEPLOY

| Target | Reference |
|--------|-----------|
| GitHub Pages, Vercel, general | `references/deploy.md` |
| iOS via Capacitor | `references/capacitor-ios.md` |
| Promo video | `references/promo-video.md` |

---

## Sprite Mode

AI sprite generation: portrait, portrait-loop, spritesheet, per-row animated
sheets. Load `references/game-sprite-pipeline.md` for the full pipeline.

### Quick Steps

1. **Detect format.** Portrait (single image), portrait-loop (idle animation), spritesheet (action set), per-row (multiple animations in rows).
2. **Select backend.** Load `references/backend-chain.md` for dispatch: Codex CLI primary, Gemini fallback.
3. **Select style.** Load `references/style-presets.md` for 9 era/hardware presets.
4. **Generate.** Follow the pipeline for the detected format.
5. **Post-process.** Background removal, palette quantization, sheet assembly.
6. **Validate.** Check dimensions, frame counts, transparency, color consistency.

---

## Phaser Mode

Phaser 3 2D game engine builds. Load `references/phaser-gamedev.md` for the
full methodology.

### Core Patterns

Load `references/core-patterns.md` for scene lifecycle, transitions, and input handling.

| Task | Reference |
|------|-----------|
| Scene lifecycle, transitions | `references/core-patterns.md` |
| TypeScript entry, Boot/Game skeletons | `references/build-scaffolds.md` |
| Arcade physics, collision | `references/arcade-physics.md` |
| Tilemaps, tile layers | `references/tilemaps.md`, `references/tilemaps-and-physics.md` |
| Screen shake, particles, hit-stop | `references/game-feel-patterns.md` |
| Polish scaffolds | `references/polish-scaffolds.md` |
| Animate scaffolds | `references/animate-scaffolds.md` |

---

## GM Mode

Evidence-to-live implementation for large GM programs (multi-system, multi-wave,
CPU-intensive). Load `references/gm-brilliant-implementation.md` for the full
methodology.

### Applicability Gate

GM mode applies only when: multiple interconnected game systems change, CPU
performance is a concern, or the implementation spans multiple deployment waves.
If the gate fails, route to quick, workflow, or the target project's skill.

### Key References

| Signal | Reference |
|--------|-----------|
| Stage contracts, checkpoints | `references/stage-contracts.md` |
| CPU systems harmony | `references/cpu-systems-harmony.md` |
| Quality gates | `references/quality-gates.md` |
| Workflow DAG (34 stages) | `references/workflow-dag.md` |

---

## Deep References

Load when the task needs detailed patterns, catalogs, or specifications.

### Design

| Signal | Reference |
|--------|-----------|
| 61 runnable capabilities | `references/capability-catalog.md` |
| Capability coverage matrix | `references/capability-matrix.md` |
| Full diagnostic report format | `references/full-diagnostic.md` |
| Individual capability specs | `references/capabilities/*.md` (61 files) |
| VFX containment rules | `references/vfx-containment.md` |
| Menus, HUD, shop, settings, or other screen UI (load first) | `skills/shared-patterns/ui-design-judgment.md` (game genre conventions win over web defaults), then `skills/frontend/frontend/references/distinctive-frontend-design-refs/game-ui-polish.md` |

### Pipeline

| Signal | Reference |
|--------|-----------|
| Game asset generator | `references/game-asset-generator.md` |
| Meshy AI 3D models | `references/meshyai.md` |
| Fal.ai image generation | `references/fal-ai-image.md` |
| WorldLabs environments | `references/worldlabs.md` |
| Asset sources catalog | `references/asset-sources.md` |
| Motion pipeline | `references/motion-pipeline.md` |
| Game audio | `references/game-audio.md` |
| Game QA | `references/game-qa.md` |
| Deploy targets | `references/deploy.md` |
| Capacitor iOS | `references/capacitor-ios.md` |

### Sprite

| Signal | Reference |
|--------|-----------|
| Full sprite pipeline | `references/game-sprite-pipeline.md` |
| Backend dispatch | `references/backend-chain.md` |
| Style presets | `references/style-presets.md` |
| Pixel art patterns | `references/pixel-art-sprites.md` |
| Output formats | `references/output-formats.md` |
| Prompt rules | `references/prompt-rules.md` |
| Background removal | `references/bg-removal-local.md` |
| Frame detection | `references/frame-detection.md` |
| Error catalog | `references/error-catalog.md` |

### Phaser

| Signal | Reference |
|--------|-----------|
| Full Phaser methodology | `references/phaser-gamedev.md` |
| Core patterns, scene lifecycle | `references/core-patterns.md` |
| Arcade physics | `references/arcade-physics.md` |
| Tilemaps and physics | `references/tilemaps-and-physics.md` |
| Game feel patterns | `references/game-feel-patterns.md` |
| Performance patterns | `references/performance.md` |

### GM

| Signal | Reference |
|--------|-----------|
| Full GM methodology | `references/gm-brilliant-implementation.md` |
| Stage contracts | `references/stage-contracts.md` |
| CPU systems harmony | `references/cpu-systems-harmony.md` |
| Quality gates | `references/quality-gates.md` |
| Workflow DAG | `references/workflow-dag.md` |
| Anchor alignment | `references/anchor-alignment.md` |
