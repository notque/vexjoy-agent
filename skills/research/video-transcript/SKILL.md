---
name: video-transcript
promoted_to: video-editing
description: "Extract uploader or automatic video subtitles and clean VTT rolling captions into paragraphs."
user_invocable: false
agent: python-general-engineer
allowed-tools: [Bash, Read]
routing:
  triggers: [video transcript, youtube transcript, extract transcript, download subtitles, what does this video say, get transcript, transcribe video, transcribe this video, pull subtitles, captions from video]
  category: research
  pairs_with: [research]
---

# Video Transcript

Try uploader subtitles, then automatic captions only if no VTT was written:

```bash
yt-dlp --skip-download --write-subs --sub-langs en --sub-format vtt -o '<work-dir>/%(id)s' '<URL>'
yt-dlp --skip-download --write-auto-subs --sub-langs en --sub-format vtt -o '<work-dir>/%(id)s' '<URL>'
python3 skills/research/video-transcript/scripts/vtt_to_paragraph.py <work-dir>/<id>.en.vtt
```

Cleaner options: `--timestamps`, `--keep-brackets`, `-o FILE`. Use `yt-dlp --list-subs` when neither path writes a file. For rate limiting, reduce volume and retry with `--sleep-requests 2`. Preserve a failing VTT fixture when extending deduplication for a new cue shape.
