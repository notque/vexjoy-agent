---
name: video-editing
description: "Cut and assemble footage with an EDL, FFmpeg, and optional Remotion overlays; also extracts online-video subtitles."
user-invocable: false
agent: python-general-engineer
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task, Skill]
routing:
  category: video-creation
  triggers: [edit video, cut footage, ffmpeg, remotion, assemble clips, video transcript, youtube transcript]
  pairs_with: [typescript-frontend-engineer, research]
---

# Video editing

Preserve sources: write every cut and render to new files. Use `cuts.txt` as the edit contract (`START_TIME,END_TIME,LABEL`); generate cuts and the concat list from it. Never build concat order from a glob.

## Workflow

1. Inventory and `ffprobe` inputs; write `source-inventory.txt`. For long footage, make proxies but render from sources.
2. Transcribe when editorial selection needs speech. Run scene/silence detection as evidence, then write and check a non-overlapping EDL.
3. Batch-cut into `segments/`, build `concat-list.txt` in EDL order, and write `assembled/rough-cut.mp4`.
4. Use Remotion only for programmatic titles, captions, transitions, or overlays. Its composition ID must exactly match the render command, and durations are frames, not seconds.
5. Generate missing voice/music/b-roll only when the user authorizes the provider and cost. Prefer cutting around a gap. Save generated assets before assembling them.
6. Probe the delivered file. Report its path, duration, dimensions, and remaining subjective work.

Read only the needed reference:

- `references/ffmpeg-commands.md` — exact EDL cutting, concat, detection, and normalization commands.
- `references/remotion-scaffold.md` — the non-obvious Remotion timing and registration contracts.
- `references/image-to-video.md` — the repository CLI for a still image plus audio.
- `references/ffmpeg-filters.md` — maintained visualization filter graphs.

## Subtitle extraction

Prefer uploader subtitles, then retry with auto-generated subtitles:

```bash
yt-dlp --skip-download --write-subs --sub-langs en --sub-format vtt -o '<work-dir>/%(id)s' '<URL>'
yt-dlp --skip-download --write-auto-subs --sub-langs en --sub-format vtt -o '<work-dir>/%(id)s' '<URL>'
python3 skills/research/video-transcript/scripts/vtt_to_paragraph.py <work-dir>/<id>.en.vtt
```

If no VTT appears, inspect `yt-dlp --list-subs`. The converter accepts `--timestamps`, `--keep-brackets`, and `-o FILE`.

## Failure boundaries

- Stream-copy cuts are keyframe-bound; re-encode for frame accuracy.
- Concat stream-copy requires matching stream layouts/codecs; re-encode when they differ.
- `ffmpeg` success alone is insufficient: verify nonzero duration and expected streams with `ffprobe`.
- Treat color matching, music ducking, caption styling, transition taste, and final mix as explicit editorial choices, not silent defaults.
