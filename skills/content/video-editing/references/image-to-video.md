# Repository image-to-video CLI

Use the maintained sibling script instead of reconstructing filter graphs:

```bash
python3 skills/content/image-to-video/scripts/image_to_video.py \
  --image /absolute/image.png --audio /absolute/audio.mp3 \
  --output /absolute/output.mp4 --resolution 1080p --visualization static
```

Presets are `1080p`, `720p`, `square`, and `vertical`; visualizations are `static`, `waveform`, `spectrum`, `cqt`, and `bars`. Do not substitute `static` when the user requested a visualization. Workspace batch mode uses `--process-workspace` and pairs input basenames.

The script exit contract is `0` success, `1` FFmpeg unavailable, `2` encode failure, `3` missing arguments. After exit 0, probe duration and streams; expected duration is within one second of the audio. Filter failures usually mean a minimal FFmpeg build. Conversion to PCM WAV can isolate unsupported/corrupt audio.
