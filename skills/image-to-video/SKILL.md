---
name: image-to-video
description: |
  FFmpeg-based 4-step video creation: Validate, Prepare, Encode, Verify.
  Use when user wants to combine a static image with audio to create an MP4
  video, create a music video from cover art, or produce podcast/YouTube
  video from an image and audio file. Use for "image to video", "static
  video", "mp4 from image", "album art video", or "audio visualization".
  Do NOT use for video editing, live streaming, or generating images.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    - image to video
    - audio visualization
    - static video
    - mp4 from image
    - music video
    - podcast video
    - video from image
    - combine image audio
    - album art video
    - cover art video
  pairs_with:
    - gemini-image-generator
    - workflow-orchestrator
  complexity: simple
  category: video-creation
---

# Image to Video Skill

## Operator Context

This skill operates as an operator for CLI-based video creation, configuring Claude's behavior for deterministic FFmpeg script execution. It implements the **Sequential Pipeline** architectural pattern -- Validate, Prepare, Encode, Verify -- with **Domain Intelligence** embedded in FFmpeg filter selection and resolution matching.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before creating video
- **Over-Engineering Prevention**: Only implement what is directly requested. No extra visualizations, no format conversions beyond MP4
- **FFmpeg Validation**: Always verify FFmpeg is installed before attempting video creation
- **Input Validation**: Check that both image and audio files exist before processing
- **Absolute Paths Only**: Always use absolute paths for image, audio, and output arguments

### Default Behaviors (ON unless disabled)
- **Resolution Default**: Use 1080p (1920x1080) unless user specifies otherwise
- **Static Mode**: No visualization overlay unless user requests one
- **AAC Audio**: Encode audio as 192k AAC for broad compatibility
- **H.264 Video**: Encode with libx264 preset medium, CRF 23, yuv420p pixel format
- **Output Verification**: Run ffprobe on output and report file size after creation

### Optional Behaviors (OFF unless enabled)
- **Waveform Visualization**: Neon waveform overlay with `--visualization waveform`
- **Spectrum Visualization**: Scrolling frequency spectrum with `--visualization spectrum`
- **CQT Visualization**: Piano-roll style bars with `--visualization cqt`
- **Bars Visualization**: Frequency bar graph with `--visualization bars`
- **Custom Resolution**: Override with `--resolution` preset (720p, square, vertical)
- **Workspace Mode**: Batch process paired files with `--process-workspace`

## What This Skill CAN Do
- Combine a static image with audio to produce an MP4 video
- Scale images to target resolution while preserving aspect ratio
- Add audio visualization overlays (waveform, spectrum, cqt, bars)
- Support multiple resolution presets (1080p, 720p, square, vertical)
- Batch process matching image+audio pairs from workspace directory
- Validate FFmpeg availability and report actionable install instructions

## What This Skill CANNOT Do
- Generate images (use `gemini-image-generator` for that)
- Edit existing videos or trim/split audio
- Stream live video or produce non-MP4 formats
- Add text overlays, captions, or transitions
- Work without FFmpeg installed on the system

---

## Instructions

### Phase 1: VALIDATE

**Goal**: Confirm all prerequisites before attempting video creation.

**Step 1: Check FFmpeg installation**

```bash
ffmpeg -version
```

If FFmpeg is not installed, provide platform-specific install instructions and stop.

**Step 2: Verify input files exist**

```bash
ls -la /absolute/path/to/image.png /absolute/path/to/audio.mp3
```

Confirm both files exist and have non-zero size. Supported formats:
- **Images**: PNG, JPG, JPEG, GIF, WEBP, BMP
- **Audio**: MP3, WAV, M4A, OGG, FLAC

**Step 3: Determine parameters**

Resolve resolution preset and visualization mode from user request. If the user did not specify, use defaults (1080p, static).

| Preset | Dimensions | Platform |
|--------|------------|----------|
| `1080p` | 1920x1080 | YouTube HD (default) |
| `720p` | 1280x720 | Standard HD, smaller files |
| `square` | 1080x1080 | Instagram, social media |
| `vertical` | 1080x1920 | Stories, Reels, TikTok |

**Gate**: FFmpeg installed, both input files exist, parameters resolved. Proceed only when gate passes.

### Phase 2: PREPARE

**Goal**: Set up output path and confirm no conflicts.

**Step 1: Determine output path**

Use the path provided by the user. If none given, derive from the audio filename:
```
/same/directory/as/audio/filename.mp4
```

**Step 2: Ensure output directory exists**

The script creates parent directories automatically. Verify the target directory is writable.

**Gate**: Output path determined, directory accessible. Proceed only when gate passes.

### Phase 3: ENCODE

**Goal**: Execute FFmpeg to produce the video.

**Step 1: Run the script**

```bash
python3 $HOME/claude-code-toolkit/skills/image-to-video/scripts/image_to_video.py \
  --image /absolute/path/to/image.png \
  --audio /absolute/path/to/audio.mp3 \
  --output /absolute/path/to/output.mp4 \
  --resolution 1080p \
  --visualization static
```

For workspace batch mode (processes all matched pairs in `workspace/input/`):

```bash
python3 $HOME/claude-code-toolkit/skills/image-to-video/scripts/image_to_video.py \
  --process-workspace \
  --visualization waveform
```

**Step 2: Monitor output**

The script prints progress including input paths, resolution, visualization mode, and duration. Watch for ERROR lines in output.

**Gate**: Script exits with code 0. Proceed only when gate passes.

### Phase 4: VERIFY

**Goal**: Confirm the output video is valid and report results.

**Step 1: Check file exists and has reasonable size**

```bash
ls -la /absolute/path/to/output.mp4
```

**Step 2: Probe video metadata**

```bash
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height \
  -of default=noprint_wrappers=1 /absolute/path/to/output.mp4
```

Confirm video duration matches audio duration (within 1 second tolerance).

**Step 3: Report to user**

Provide: output file path, file size, duration, resolution, and visualization mode used.

**Gate**: Output file exists, duration matches audio, metadata is valid. Task complete.

---

## Error Handling

### Error: "FFmpeg is not installed or not in PATH"
Cause: FFmpeg binary not found on system
Solution:
1. Install via package manager: `brew install ffmpeg` (macOS), `sudo apt install ffmpeg` (Ubuntu)
2. Verify with `ffmpeg -version` after install
3. Ensure FFmpeg is in system PATH

### Error: "Image file not found" or "Audio file not found"
Cause: Path is incorrect, relative, or file does not exist
Solution:
1. Verify the path is absolute, not relative
2. Check file permissions with `ls -la`
3. Confirm the file extension matches a supported format

### Error: "FFmpeg failed" with filter errors
Cause: FFmpeg build lacks filter support (showwaves, showspectrum, showcqt)
Solution:
1. Install the full FFmpeg build, not a minimal variant
2. On Ubuntu: `sudo apt install ffmpeg` (full package)
3. Fall back to `--visualization static` which requires no special filters

### Error: "Could not determine audio duration"
Cause: Audio file is corrupted or uses an unsupported container format
Solution:
1. Test the audio independently: `ffprobe /path/to/audio.mp3`
2. Convert to a known format: `ffmpeg -i input.audio -acodec pcm_s16le output.wav`
3. Re-run with the converted file

---

## Anti-Patterns

### Anti-Pattern 1: Using Relative Paths
**What it looks like**: `python3 image_to_video.py -i ../cover.png -a song.mp3`
**Why wrong**: The script may execute from a different working directory, breaking all paths silently.
**Do instead**: Always use absolute paths for every argument.

### Anti-Pattern 2: Skipping FFmpeg Verification
**What it looks like**: Running the script directly without checking `ffmpeg -version` first.
**Why wrong**: Produces confusing subprocess errors instead of clear install instructions.
**Do instead**: Complete Phase 1 validation before any encoding attempt.

### Anti-Pattern 3: Wrong Resolution for Target Platform
**What it looks like**: Using 1080p landscape for TikTok, or vertical for YouTube.
**Why wrong**: Content gets cropped or displays with large black bars on the target platform.
**Do instead**: Ask the user what platform the video targets, then select the matching preset.

### Anti-Pattern 4: Skipping Output Verification
**What it looks like**: Reporting success based on script exit code alone without probing the output.
**Why wrong**: FFmpeg can exit 0 but produce a corrupt or zero-duration file.
**Do instead**: Complete Phase 4 -- probe the output, confirm duration matches audio.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It Is Wrong | Required Action |
|-----------------|-----------------|-----------------|
| "FFmpeg is always installed" | Many systems lack it or have minimal builds | Run `ffmpeg -version` every time |
| "The script handles everything" | Script can fail silently with bad inputs | Validate inputs in Phase 1 |
| "File size looks right" | Size alone does not prove video integrity | Probe with ffprobe, check duration |
| "Static mode is fine" | User may have requested visualization | Re-read the request before defaulting |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/ffmpeg-filters.md`: FFmpeg filter documentation for visualization modes
- `${CLAUDE_SKILL_DIR}/scripts/image_to_video.py`: Python CLI script (exit codes: 0=success, 1=no FFmpeg, 2=encode failed, 3=missing args)
