---
name: image-to-video
promoted_to: video-editing
description: "Create an H.264/AAC MP4 from one image and one audio file with this repository's FFmpeg wrapper."
user-invocable: false
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit]
routing:
  triggers: [image to video, audio visualization, static video, mp4 from image, music video, podcast video, video from image, combine image audio, album art video, cover art video]
  pairs_with: [workflow]
  complexity: simple
  category: video-creation
---

# Image to Video

Use `scripts/image_to_video.py`; use `image-gen` when the source image must first be created. Load `references/ffmpeg-filters.md` only when selecting or debugging a visualization.

## Contract

- Inputs: image `.png/.jpg/.jpeg/.gif/.webp/.bmp`; audio `.mp3/.wav/.m4a/.ogg/.flac`.
- Resolutions: `1080p` (default, 1920x1080), `720p` (1280x720), `square` (1080x1080), `vertical` (1080x1920).
- Visualizations: `static` (default), `waveform`, `spectrum`, `cqt`, `bars`. Preserve an explicitly requested visualization.
- Output: H.264 (`libx264`, medium, CRF 23; CQT/bars use CRF 20), `yuv420p`, AAC 192k, ending with the audio via `-shortest`.

Single-file mode requires all three paths:

```bash
python3 skills/content/image-to-video/scripts/image_to_video.py \
  --image /abs/cover.png --audio /abs/audio.mp3 --output /abs/video.mp4 \
  --resolution 1080p --visualization static
```

Workspace mode matches image/audio by case-insensitive stem in `workspace/input/`, writes `workspace/output/<image-stem>.mp4`, then moves both successful inputs to `workspace/completed/`:

```bash
python3 skills/content/image-to-video/scripts/image_to_video.py \
  --process-workspace --visualization waveform
```

Because workspace mode moves inputs, confirm the user intends archival processing before running it. A no-pairs run exits 0; any failed pair makes the batch exit 2.

## Verification

The wrapper only checks that FFmpeg returned success and the output path exists. Independently run:

```bash
ffprobe -v error \
  -show_entries format=duration,size -show_entries stream=codec_name,width,height \
  -of default=noprint_wrappers=1 /abs/video.mp4
```

Require a non-empty H.264/AAC output, requested dimensions (except the CQT caveat in the reference), and duration within one second of the audio. If a visualization filter is absent, report that build limitation and offer `static`; do not silently change modes.
