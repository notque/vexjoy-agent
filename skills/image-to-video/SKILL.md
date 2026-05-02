---
name: image-to-video
description: "FFmpeg-based video creation from image and audio."
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
    - workflow
  complexity: simple
  category: video-creation
---

# Image to Video Skill

Combine a static image with an audio file to produce an MP4 using FFmpeg. Supports resolution presets (1080p, 720p, square, vertical), optional audio visualization overlays (waveform, spectrum, cqt, bars), and batch processing. For image generation, use `gemini-image-generator`.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `ffmpeg-filters.md` | Loads detailed guidance from `ffmpeg-filters.md`. |

## Instructions

### Phase 1: VALIDATE

**Step 1: Check FFmpeg**

```bash
ffmpeg -version
```

If not installed, provide platform-specific install instructions and stop.

**Step 2: Verify inputs exist**

Use absolute paths for all arguments — relative paths break silently when the script executes from a different working directory.

```bash
ls -la /absolute/path/to/image.png /absolute/path/to/audio.mp3
```

Confirm both exist with non-zero size. Supported formats:
- **Images**: PNG, JPG, JPEG, GIF, WEBP, BMP
- **Audio**: MP3, WAV, M4A, OGG, FLAC

**Step 3: Determine parameters**

Re-read the user's request before selecting defaults. Only apply defaults (1080p, static) when the user did not specify.

| Preset | Dimensions | Platform |
|--------|------------|----------|
| `1080p` | 1920x1080 | YouTube HD (default) |
| `720p` | 1280x720 | Standard HD, smaller files |
| `square` | 1080x1080 | Instagram, social media |
| `vertical` | 1080x1920 | Stories, Reels, TikTok |

Visualization modes (off unless requested):
- `--visualization waveform` — Neon waveform overlay
- `--visualization spectrum` — Scrolling frequency spectrum
- `--visualization cqt` — Piano-roll style bars
- `--visualization bars` — Frequency bar graph

**Gate**: FFmpeg installed, both inputs exist, parameters resolved.

### Phase 2: PREPARE

Determine output path. If none given, derive from audio filename: `/same/directory/as/audio/filename.mp4`. The script creates parent directories automatically. Verify the target directory is writable.

**Gate**: Output path determined, directory accessible.

### Phase 3: ENCODE

Only implement what the user requested — no extra visualizations or format conversions.

Encoding defaults: libx264 preset medium, CRF 23, yuv420p, 192k AAC audio.

```bash
python3 $HOME/vexjoy-agent/skills/image-to-video/scripts/image_to_video.py \
  --image /absolute/path/to/image.png \
  --audio /absolute/path/to/audio.mp3 \
  --output /absolute/path/to/output.mp4 \
  --resolution 1080p \
  --visualization static
```

Workspace batch mode (processes all matched pairs in `workspace/input/`):

```bash
python3 $HOME/vexjoy-agent/skills/image-to-video/scripts/image_to_video.py \
  --process-workspace \
  --visualization waveform
```

Watch for ERROR lines in output.

**Gate**: Script exits with code 0.

### Phase 4: VERIFY

Do not report success based on exit code alone — FFmpeg can exit 0 but produce a corrupt or zero-duration file.

**Step 1: Check file exists with reasonable size**
```bash
ls -la /absolute/path/to/output.mp4
```

**Step 2: Probe video metadata**
```bash
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height \
  -of default=noprint_wrappers=1 /absolute/path/to/output.mp4
```

Confirm video duration matches audio duration (within 1 second tolerance).

**Step 3: Report** — output file path, file size, duration, resolution, visualization mode used.

**Gate**: Output exists, duration matches audio, metadata valid. Task complete.

## Error Handling

### Error: "FFmpeg is not installed or not in PATH"
Install: `brew install ffmpeg` (macOS), `sudo apt install ffmpeg` (Ubuntu). Verify with `ffmpeg -version`.

### Error: "Image file not found" or "Audio file not found"
Verify path is absolute. Check permissions with `ls -la`. Confirm file extension matches a supported format.

### Error: "FFmpeg failed" with filter errors
FFmpeg build lacks filter support. Install full FFmpeg package. Fall back to `--visualization static` (requires no special filters).

### Error: "Could not determine audio duration"
Audio file is corrupted or unsupported. Test with `ffprobe /path/to/audio.mp3`. Convert: `ffmpeg -i input.audio -acodec pcm_s16le output.wav`.

## References

- `${CLAUDE_SKILL_DIR}/references/ffmpeg-filters.md`: FFmpeg filter documentation for visualization modes
- `${CLAUDE_SKILL_DIR}/scripts/image_to_video.py`: Python CLI (exit codes: 0=success, 1=no FFmpeg, 2=encode failed, 3=missing args)
