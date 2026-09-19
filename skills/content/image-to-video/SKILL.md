---
name: image-to-video
promoted_to: video-editing
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
    - workflow
  complexity: simple
  category: video-creation
---

# Image to Video Skill

Combine a static image with an audio file to produce an MP4 via FFmpeg. Supports resolution presets, audio visualization overlays, and batch processing. For image generation, use `image-gen`.

## Deep References

| Signal | Load | Why |
|---|---|---|
| FFmpeg filter graphs for visualization modes | `references/ffmpeg-filters.md` | Scale/pad, showwaves, showspectrum, overlay filters |

## Phase 1: VALIDATE

1. Check FFmpeg: `ffmpeg -version`. If missing, stop with install instructions.
2. Verify both input files exist with absolute paths and non-zero size. Supported: PNG/JPG/JPEG/GIF/WEBP/BMP (image), MP3/WAV/M4A/OGG/FLAC (audio).
3. Determine parameters from the user's request -- do not default to static when the user requested a visualization.

| Preset | Dimensions | Platform |
|--------|------------|----------|
| `1080p` | 1920x1080 | YouTube HD (default) |
| `720p` | 1280x720 | Standard HD |
| `square` | 1080x1080 | Instagram, social |
| `vertical` | 1080x1920 | Stories, Reels, TikTok |

Visualization modes (off unless requested): `waveform`, `spectrum`, `cqt`, `bars`.

**Gate**: FFmpeg installed, both files exist, parameters resolved.

## Phase 2: PREPARE

Use the user's output path or derive from audio filename (`/same/dir/filename.mp4`). Verify directory is writable.

## Phase 3: ENCODE

Defaults: libx264 preset medium, CRF 23, yuv420p, 192k AAC.

```bash
python3 $HOME/vexjoy-agent/skills/content/image-to-video/scripts/image_to_video.py \
  --image /path/to/image.png --audio /path/to/audio.mp3 \
  --output /path/to/output.mp4 --resolution 1080p --visualization static
```

Batch mode (matched pairs in `workspace/input/`):

```bash
python3 $HOME/vexjoy-agent/skills/content/image-to-video/scripts/image_to_video.py \
  --process-workspace --visualization waveform
```

**Gate**: Script exits 0.

## Phase 4: VERIFY

FFmpeg can exit 0 but produce a corrupt file. Always probe:

```bash
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height \
  -of default=noprint_wrappers=1 /path/to/output.mp4
```

Confirm video duration matches audio (within 1s). Report: file path, size, duration, resolution, visualization mode.

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| FFmpeg not found | Not installed | `apt install ffmpeg` or `brew install ffmpeg` |
| Image/audio not found | Wrong or relative path | Use absolute paths; check with `ls -la` |
| FFmpeg filter errors | Minimal build lacks showwaves/showcqt | Install full FFmpeg; fall back to `--visualization static` |
| Cannot determine audio duration | Corrupted audio file | Test with `ffprobe`; convert: `ffmpeg -i input -acodec pcm_s16le output.wav` |

