---
name: video-editing
description: |
  Video editing workflow: 6-layer pipeline for cutting footage, assembling
  demo videos, vlogs, screen recordings, and social media clips using FFmpeg
  and Remotion. Handles EDL generation from transcripts, deterministic FFmpeg
  cuts, Remotion TSX composition, and final polish handoff.
  Triggered by "edit video", "cut footage", "make vlog", "screen recording",
  "video workflow", "ffmpeg", "remotion", "demo video", "make a clip".
  Do NOT use for audio-only tasks (no video track), static image generation,
  or live streaming configuration.
version: 1.0.0
user-invocable: true
agent: python-general-engineer
model: sonnet
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

## Operator Context

This skill operates as an operator for video editing workflows, configuring Claude's behavior for
structured, deterministic video production. It implements a **6-layer pipeline** where AI handles
judgment tasks (what to keep, what to cut, highlight selection) and FFmpeg/Remotion handle
mechanical execution deterministically.

### Hardcoded Behaviors (Always Apply)

- **Preflight before anything**: Run all three preflight checks before Phase 1. No work begins on a
  missing binary.
- **Artifacts before proceeding**: Every phase writes its output to disk. No phase runs on memory
  of a previous phase's output.
- **cuts.txt is the contract**: The EDL file (`cuts.txt`) is the only source of truth for Layer 3.
  Do not hand-edit FFmpeg commands -- generate them from the EDL.
- **Layer 6 is human territory**: Final color grading, music timing, and caption style are human
  taste decisions. The skill assembles; the human finishes.
- **Generate only what doesn't exist**: Before calling ElevenLabs or any generative API, check
  whether adequate source material already covers the gap.

### Default Behaviors (ON unless disabled)

- **Proxy-first for long footage**: Generate proxy files before editing long source material
  (>10 min). Edit proxy; swap to source for final render.
- **Scene detection before manual EDL**: Run FFmpeg scene/silence detection before writing the
  EDL by hand. Detection output informs judgment, not replaces it.
- **Preserve source files**: FFmpeg commands write to new files only. Source footage is never
  overwritten.

### Optional Behaviors (OFF unless enabled)

- **ElevenLabs voiceover**: Only when source audio has unacceptable gaps and user authorizes API cost.
- **Social reframe variants**: Generate 9:16 and 1:1 crops only when explicitly requested.
- **Remotion composition**: Layer 4 is optional if the assembled MP4 from Layer 3 is sufficient.

---

## Preflight Check

Run before Phase 1.

**Hard requirements** (BLOCK if missing — halt immediately):
- `ffmpeg`: required for all phases
- `node`: required for Remotion and npx tooling

**Soft requirements** (WARN if missing — continue unless Layer 4 is needed):
- `remotion`: only required for Phase 4 (Remotion composition)

```bash
# Hard requirements — exit 1 if missing
which ffmpeg >/dev/null 2>&1 || {
  echo "ERROR: ffmpeg not found. Cannot continue."
  echo "Install: brew install ffmpeg  (macOS)  |  apt install ffmpeg  (Linux)"
  exit 1
}
which node >/dev/null 2>&1 || {
  echo "ERROR: node not found. Cannot continue."
  echo "Install: https://nodejs.org or via nvm"
  exit 1
}

# Soft requirement — warn only; continue unless Phase 4 is needed
npx remotion --version >/dev/null 2>&1 || {
  echo "WARNING: remotion CLI not found."
  echo "Layers 1-3 and 5-6 will proceed normally."
  echo "Phase 4 (Remotion composition) will be unavailable."
  echo "Install when needed: npm install @remotion/cli  (in your project directory)"
}

echo "Preflight: ffmpeg OK, node OK. (remotion optional — see above if warned)"
```

---

## Pipeline Overview

| Layer | Name | Mechanism | Primary Tool |
|-------|------|-----------|-------------|
| 1 | CAPTURE | Inventory source footage | Bash + Glob |
| 2 | AI STRUCTURE | Transcript to EDL | LLM judgment |
| 3 | FFMPEG CUTS | EDL to segment files | FFmpeg (deterministic) |
| 4 | REMOTION COMPOSITION | Segments to TSX composition | Remotion + TypeScript |
| 5 | AI GENERATION | Fill gaps with generated assets | ElevenLabs / fal.ai (conditional) |
| 6 | FINAL POLISH | Human taste layer | Human + NLE |

---

## Phase 1: CAPTURE

**Goal**: Inventory all source footage and confirm files exist on disk before any processing.

### Step 1: Locate source files

```bash
find . -type f \( -name "*.mp4" -o -name "*.mov" -o -name "*.mkv" -o -name "*.webm" -o -name "*.avi" \) | sort
```

### Step 2: Inspect each file

```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,codec_name,duration \
  -of csv=p=0 input.mp4
```

### Step 3: Generate proxy (optional, recommended for files >10 min)

See `references/ffmpeg-commands.md` -> **Proxy Generation** section.

### Step 4: Create working directory

```bash
mkdir -p segments assembled
```

**Gate**: Source files confirmed on disk. File list written to `source-inventory.txt`. Proceed only when gate passes.

```bash
find . -maxdepth 2 -type f \( -name "*.mp4" -o -name "*.mov" -o -name "*.mkv" \) > source-inventory.txt
cat source-inventory.txt
```

---

## Phase 2: AI STRUCTURE

**Goal**: Analyze content and produce a written EDL (`cuts.txt`) that drives all downstream cutting.

### Step 1: Transcribe (if not already done)

Use whisper, AssemblyAI, or any transcription source. Write transcript to `transcript.txt`.

```bash
whisper input.mp4 --output_format txt --output_dir . --task transcribe
```

### Step 2: Generate EDL from transcript

Read `transcript.txt` and apply judgment:
- What sections advance the narrative or demonstrate the feature?
- What is filler, repetition, dead air, or off-topic?
- What is the target duration? (Default: 60-90 sec for demo, 3-8 min for tutorial)

Write `cuts.txt` in EDL format:

```
# cuts.txt - Edit Decision List
# Format: START_TIME,END_TIME,LABEL
# Times in HH:MM:SS or seconds (decimal OK)

00:00:05,00:00:18,intro
00:01:32,00:02:45,feature-demo
00:03:10,00:03:55,closing
```

### Step 3: Review EDL

Read back `cuts.txt` and verify:
- Total assembled duration matches target
- No overlapping segments
- Labels are descriptive (no spaces, hyphens OK)

**Gate**: `transcript.txt` exists. `cuts.txt` written to disk. Proceed only when both files exist.

```bash
test -f transcript.txt && echo "transcript.txt: OK" || echo "ERROR: transcript.txt missing"
test -f cuts.txt && echo "cuts.txt: OK" || echo "ERROR: cuts.txt missing"
```

---

## Phase 3: FFMPEG CUTS

**Goal**: Execute the EDL deterministically -- one FFmpeg cut per segment in `cuts.txt`.

### Step 1: Batch cut from EDL

See `references/ffmpeg-commands.md` -> **Batch Cutting from cuts.txt** for the full bash loop.

```bash
while IFS=',' read -r start end label; do
  [[ "$start" == \#* ]] && continue
  [[ -z "$start" ]] && continue
  ffmpeg -ss "$start" -to "$end" -i input.mp4 \
    -c:v libx264 -c:a aac -avoid_negative_ts make_zero \
    "segments/${label}.mp4"
done < cuts.txt
```

### Step 2: Verify segments

```bash
ls -lh segments/
```

### Step 3: Concatenate in EDL order

```bash
while IFS=',' read -r start end label; do
  [[ "$start" == \#* ]] && continue
  [[ -z "$start" ]] && continue
  echo "file 'segments/${label}.mp4'"
done < cuts.txt > concat-list.txt

ffmpeg -f concat -safe 0 -i concat-list.txt -c copy assembled/rough-cut.mp4
```

**Gate**: All segment files exist. `assembled/rough-cut.mp4` written to disk. Proceed only when gate passes.

```bash
while IFS=',' read -r start end label; do
  [[ "$start" == \#* ]] && continue
  [[ -z "$start" ]] && continue
  test -f "segments/${label}.mp4" && echo "OK: ${label}.mp4" || echo "MISSING: ${label}.mp4"
done < cuts.txt
test -f assembled/rough-cut.mp4 && echo "rough-cut.mp4: OK" || echo "ERROR: rough-cut.mp4 missing"
```

---

## Phase 4: REMOTION COMPOSITION

**Goal**: Wrap segments in a Remotion TSX composition for programmatic overlays, titles, or transitions.

**When to use**: Only when rough-cut.mp4 requires programmatic elements (animated titles, lower thirds,
caption tracks, brand overlays). If rough-cut.mp4 is sufficient, skip to Phase 6.

**Agent handoff**: Layer 4 requires TypeScript/React. Hand off to `typescript-frontend-engineer`
for TSX work; return to `python-general-engineer` for Phase 5 onward.

### Step 1: Initialize Remotion (first time only)

```bash
npm create video@latest
# or add to existing project:
npm install @remotion/cli @remotion/player remotion
```

### Step 2: Scaffold composition

See `references/remotion-scaffold.md` for the complete TSX template with `AbsoluteFill`,
`Sequence`, and `Video` components.

### Step 3: Render

```bash
npx remotion render src/index.ts VideoComposition assembled/remotion-output.mp4
```

**Gate**: `assembled/remotion-output.mp4` exists. Proceed only when gate passes.

```bash
test -f assembled/remotion-output.mp4 && echo "remotion-output.mp4: OK" || echo "ERROR: render output missing"
```

---

## Phase 5: AI GENERATION

**Goal**: Fill genuine gaps in source material with generated assets -- only when needed.

**Hard rule**: Check whether existing footage covers the gap before generating anything.

### Decision tree

```
Gap in source material?
├── Can it be cut around? -> Update cuts.txt, re-run Phase 3
├── Need voiceover narration? -> ElevenLabs API (see below)
├── Need background music? -> fal.ai (deferred to fal-ai-media skill)
└── Need b-roll? -> fal.ai (deferred to fal-ai-media skill)
```

### ElevenLabs voiceover (when authorized)

```python
import requests, os

def generate_voiceover(text: str, voice_id: str, output_path: str) -> None:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": os.environ["ELEVENLABS_API_KEY"],
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(response.content)
```

**Gate**: All required generated assets saved to `assets/` directory before proceeding.

```bash
ls -lh assets/ 2>/dev/null || echo "No assets directory (Phase 5 was skipped)"
```

---

## Phase 6: FINAL POLISH

**Goal**: Deliver assembled output and hand off taste-layer work to human.

**This layer is human territory.** The skill assembles; the human finishes. The following require
human judgment and should not be attempted programmatically:

- Color grading and color matching between clips
- Music timing and volume ducking
- Caption style, font, positioning
- Transition timing and style
- Final audio mix levels

### Handoff (write to `handoff-notes.txt`)

```
Video Editing Handoff Notes
===========================
Source files: [list from source-inventory.txt]
EDL: cuts.txt
Rough cut: assembled/rough-cut.mp4
Remotion output: assembled/remotion-output.mp4 (if Phase 4 ran)
Generated assets: assets/ (if Phase 5 ran)
Total assembled duration: [ffprobe output]

Remaining for human:
- [ ] Color grade
- [ ] Music timing / ducking
- [ ] Caption style
- [ ] Final audio mix
- [ ] Export settings for target platform
```

**Gate**: `assembled/rough-cut.mp4` (or `assembled/remotion-output.mp4`) exists.
`handoff-notes.txt` written to disk.

---

## Deterministic vs. LLM Division

| Task | Mechanism | Where |
|------|-----------|-------|
| FFmpeg cut commands | Deterministic -- exact flags in references | `references/ffmpeg-commands.md` |
| Remotion TSX scaffold | Deterministic -- template in references | `references/remotion-scaffold.md` |
| EDL generation from transcript | LLM judgment | Phase 2 |
| Highlight extraction for social | LLM judgment | Phase 2 variant |
| Final color, audio, captions | Human judgment | Phase 6 |
| ElevenLabs voiceover text | LLM generation | Phase 5 (conditional) |

---

## Error Handling

### Error: "No such file or directory" on source file
**Cause**: Path in cuts.txt or command doesn't match actual filename.
**Solution**: Run `cat source-inventory.txt`. Check for spaces in filenames -- quote all paths.

### Error: FFmpeg "Invalid option" or codec errors
**Cause**: Codec unavailable in this FFmpeg build, or flag syntax error.
**Solution**: Run `ffmpeg -codecs | grep libx264`. Fall back to `-c:v copy` if re-encoding not needed. See `references/ffmpeg-commands.md`.

### Error: Remotion "Could not find composition"
**Cause**: Composition ID in render command doesn't match the `id` prop in TSX.
**Solution**: Check `src/index.ts` for registered composition ID. Match exactly in render command. See `references/remotion-scaffold.md`.

### Error: Segments exist but concat produces wrong order
**Cause**: Shell glob `segments/*.mp4` sorts alphabetically, not by EDL order.
**Solution**: Generate concat-list.txt from cuts.txt order -- Phase 3 Step 3 in this skill always reads from cuts.txt.

### Error: ElevenLabs API 401
**Cause**: `ELEVENLABS_API_KEY` not set.
**Solution**: `export ELEVENLABS_API_KEY=your_key` before running Phase 5.

---

## Anti-Patterns

### Anti-Pattern 1: Generate the whole thing from AI
**What it looks like**: Skipping source footage; asking AI to generate all content.
**Why wrong**: No authentic footage; result is synthetic and uncanny.
**Do instead**: Start with real source material. Generate only genuine gaps (Phase 5).

### Anti-Pattern 2: Skip the structure phase
**What it looks like**: Running FFmpeg cuts without first writing cuts.txt.
**Why wrong**: Without a written EDL, cuts are not reproducible and can't be reviewed.
**Do instead**: Always write cuts.txt before any FFmpeg execution.

### Anti-Pattern 3: Treat Layer 6 as optional
**What it looks like**: Delivering rough-cut.mp4 as final without noting what remains.
**Why wrong**: Rough cuts have unmatched color, unmixed audio, no captions.
**Do instead**: Always write handoff-notes.txt.

### Anti-Pattern 4: Overwrite source files
**What it looks like**: `ffmpeg -i input.mp4 ... input.mp4`
**Why wrong**: Source destroyed. No recovery without re-capture.
**Do instead**: Always write to new paths. Source files are read-only.

### Anti-Pattern 5: Hand-edit FFmpeg per cut
**What it looks like**: Individual ffmpeg commands for each segment instead of EDL loop.
**Why wrong**: Error-prone, not reproducible, can't be reviewed as a list.
**Do instead**: Maintain cuts.txt. Batch-cut from the EDL.

### Anti-Pattern 6: Skip preflight
**What it looks like**: Assuming FFmpeg/node/remotion are installed.
**Why wrong**: Missing binary produces cryptic mid-workflow errors.
**Do instead**: Always run preflight before Phase 1.

---

## References

- [`references/ffmpeg-commands.md`](references/ffmpeg-commands.md) -- All FFmpeg commands: timestamp extraction, batch cutting, concatenation, proxy generation, audio normalization, scene/silence detection, social reframing
- [`references/remotion-scaffold.md`](references/remotion-scaffold.md) -- TSX composition scaffold, render command, reuse patterns
- [Remotion docs](https://www.remotion.dev/docs) -- TSX composition API
- [FFmpeg docs](https://ffmpeg.org/documentation.html) -- Flag reference
