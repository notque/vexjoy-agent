---
name: video-editing
description: "Video editing pipeline: cut footage, assemble clips via FFmpeg and Remotion."
user-invocable: false
agent: python-general-engineer
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
routing:
  category: video-creation
  triggers:
    - edit video
    - cut footage
    - make vlog
    - screen recording
    - video workflow
    - ffmpeg
    - remotion
    - demo video
    - make a clip
    - assemble clips
    - video editing
  pairs_with:
    - typescript-frontend-engineer
---

# Video Editing Skill

6-layer pipeline: AI handles judgment (what to keep, what to cut, highlight selection); FFmpeg/Remotion handle mechanical execution deterministically.

| Layer | Name | Mechanism | Primary Tool |
|-------|------|-----------|-------------|
| 1 | CAPTURE | Inventory source footage | Bash + Glob |
| 2 | AI STRUCTURE | Transcript to EDL | LLM judgment |
| 3 | FFMPEG CUTS | EDL to segment files | FFmpeg (deterministic) |
| 4 | REMOTION COMPOSITION | Segments to TSX composition | Remotion + TypeScript |
| 5 | AI GENERATION | Fill gaps with generated assets | ElevenLabs / fal.ai (conditional) |
| 6 | FINAL POLISH | Human taste layer | Human + NLE |

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| `references/preflight.md` | `preflight.md` | Before Phase 1 |
| `references/phase-commands.md` | `phase-commands.md` | Each phase |
| `references/errors.md` | `errors.md` | Error Handling |
| `references/ffmpeg-commands.md` | `ffmpeg-commands.md` | Phase 3, Proxy |
| `references/remotion-scaffold.md` | `remotion-scaffold.md` | Phase 4 |

## Instructions

### Preflight (Run before Phase 1)

**Hard requirements** (BLOCK if missing): `ffmpeg` (all phases), `node` (Remotion / npx).
**Soft requirements** (WARN if missing): `remotion` (Phase 4 only).

Preflight script: `references/preflight.md`.

---

## Phase 1: CAPTURE

**Goal**: Inventory all source footage, confirm files exist on disk.

**Constraint**: Source files are read-only. All FFmpeg commands write to new files only.

Steps: locate sources (find), inspect with `ffprobe`, generate proxies for files >10 min (see `references/ffmpeg-commands.md` Proxy Generation), create working directories (`segments/`, `assembled/`). Full commands: `references/phase-commands.md` Phase 1.

**Gate**: Source files confirmed on disk. `source-inventory.txt` written. Proceed only when gate passes.

---

## Phase 2: AI STRUCTURE

**Goal**: Analyze content and produce EDL (`cuts.txt`) for downstream cutting.

**Constraint**: `cuts.txt` is the contract -- only source of truth for downstream phases. Do not hand-edit FFmpeg commands; generate from EDL.

**Constraint**: Run FFmpeg scene/silence detection before writing EDL manually. Detection informs judgment, does not replace it.

Steps: transcribe (whisper/AssemblyAI), run scene/silence detection, apply judgment (narrative value, filler, target duration), write `cuts.txt` as `START_TIME,END_TIME,LABEL`, check for overlap and total duration. Full commands: `references/phase-commands.md` Phase 2.

**Gate**: `transcript.txt` and `cuts.txt` exist on disk. Proceed only when both present.

---

## Phase 3: FFMPEG CUTS

**Goal**: Execute EDL deterministically -- one FFmpeg cut per segment.

**Constraint**: Batch-cut from EDL using a loop. Do not create individual commands per cut.

**Constraint**: Generate `concat-list.txt` from `cuts.txt` order, not shell glob. Glob sorts alphabetically, not by EDL order.

Steps: batch-cut with while loop (libx264/aac, `-avoid_negative_ts make_zero`), verify segments, generate `concat-list.txt` in EDL order, concat with `-f concat -safe 0 -c copy`. Full commands: `references/phase-commands.md` Phase 3 and `references/ffmpeg-commands.md` Batch Cutting.

**Gate**: All segment files exist. `assembled/rough-cut.mp4` written. Proceed only when gate passes.

---

## Phase 4: REMOTION COMPOSITION

**Goal**: Wrap segments in Remotion TSX for programmatic overlays, titles, or transitions.

**When to use**: Only when rough-cut.mp4 requires programmatic elements (animated titles, lower thirds, captions, brand overlays). If rough-cut is sufficient, skip to Phase 6.

**Constraint**: Requires TypeScript/React. Hand off to `typescript-frontend-engineer` for TSX; return to `python-general-engineer` for Phase 5+.

Steps: init Remotion (`npm create video@latest` or `npm install @remotion/cli @remotion/player remotion`), scaffold composition (see `references/remotion-scaffold.md`), render with `npx remotion render`. Full commands: `references/phase-commands.md` Phase 4.

**Gate**: `assembled/remotion-output.mp4` exists. Proceed only when gate passes.

---

## Phase 5: AI GENERATION

**Goal**: Fill genuine gaps in source material with generated assets -- only when needed.

**Constraint**: Check existing footage first. Generate only what doesn't exist.

Decision tree: cut around gap -> update cuts.txt, re-run Phase 3; voiceover -> ElevenLabs (authorization required); music/b-roll -> fal.ai (defer to fal-ai-media). Commands: `references/phase-commands.md` Phase 5.

**Gate**: All required generated assets saved to `assets/`.

---

## Phase 6: FINAL POLISH

**Goal**: Deliver assembled output, hand off taste-layer to human.

**Constraint**: Layer 6 is human territory. Do not attempt programmatically:
- Color grading and matching between clips
- Music timing and volume ducking
- Caption style, font, positioning
- Transition timing and style
- Final audio mix levels

Handoff template (`handoff-notes.txt`): `references/phase-commands.md` Phase 6.

**Gate**: `assembled/rough-cut.mp4` (or `assembled/remotion-output.mp4`) exists. `handoff-notes.txt` written.

---

## Error Handling

Common errors (missing sources, codec errors, composition-not-found, concat-order bugs, ElevenLabs 401) and fixes: `references/errors.md`.

---

## References

| Reference | When to Load | Content |
|-----------|-------------|---------|
| `references/preflight.md` | Before Phase 1 | Dependency checks: ffmpeg, node, remotion |
| `references/phase-commands.md` | Each phase | Shell commands for Phases 1-6 and gate checks |
| `references/errors.md` | Error Handling | Error matrix with causes and fixes |
| `references/ffmpeg-commands.md` | Phase 3, Proxy | FFmpeg recipes: timestamps, batch cutting, concat, proxy, audio normalization, scene/silence detection, social reframing |
| `references/remotion-scaffold.md` | Phase 4 | TSX scaffold, render command, reuse patterns |

- [Remotion docs](https://www.remotion.dev/docs) -- TSX composition API
- [FFmpeg docs](https://ffmpeg.org/documentation.html) -- Flag reference
