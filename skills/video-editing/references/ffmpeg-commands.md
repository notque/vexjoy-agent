# FFmpeg Commands Reference

All commands are tested with FFmpeg 6.x. Flags are exact — do not paraphrase.

---

## Timestamp Extraction

### Get duration and basic metadata

```bash
ffprobe -v error -show_entries format=duration,size,bit_rate \
  -of default=noprint_wrappers=1 input.mp4
```

### Get video stream info (resolution, codec, frame rate)

```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,codec_name,r_frame_rate,duration \
  -of csv=p=0 input.mp4
```

### Get audio stream info

```bash
ffprobe -v error -select_streams a:0 \
  -show_entries stream=codec_name,sample_rate,channels,duration \
  -of csv=p=0 input.mp4
```

### Extract all keyframe timestamps (useful for finding clean cut points)

```bash
ffprobe -v error -select_streams v:0 \
  -show_entries packet=pts_time,flags \
  -of csv=p=0 input.mp4 | grep -E ',K' | cut -d',' -f1
```

---

## Batch Cutting from cuts.txt EDL

### cuts.txt format

```
# cuts.txt - Edit Decision List
# Format: START_TIME,END_TIME,LABEL
# Times: HH:MM:SS, HH:MM:SS.mmm, or decimal seconds
# Labels: no spaces (use hyphens)

00:00:05,00:00:18,intro
00:01:32,00:02:45,feature-demo
00:03:10,00:03:55,closing
```

### Batch cut loop (re-encode to H.264/AAC)

```bash
mkdir -p segments
while IFS=',' read -r start end label; do
  [[ "$start" == \#* ]] && continue  # skip comment lines
  [[ -z "$start" ]] && continue       # skip blank lines
  ffmpeg -ss "$start" -to "$end" -i input.mp4 \
    -c:v libx264 -preset fast -crf 23 \
    -c:a aac -b:a 128k \
    -avoid_negative_ts make_zero \
    "segments/${label}.mp4"
done < cuts.txt
```

### Batch cut loop (stream copy — faster, no re-encode)

Use when source is already H.264/AAC and frame-accurate cuts are not critical.

```bash
mkdir -p segments
while IFS=',' read -r start end label; do
  [[ "$start" == \#* ]] && continue
  [[ -z "$start" ]] && continue
  ffmpeg -ss "$start" -to "$end" -i input.mp4 \
    -c copy \
    -avoid_negative_ts make_zero \
    "segments/${label}.mp4"
done < cuts.txt
```

### Single cut (one-off)

```bash
ffmpeg -ss 00:01:30 -to 00:02:45 -i input.mp4 \
  -c:v libx264 -c:a aac -avoid_negative_ts make_zero \
  output-segment.mp4
```

---

## Concatenation

### Generate concat list in EDL order (preserves cuts.txt sequence)

```bash
while IFS=',' read -r start end label; do
  [[ "$start" == \#* ]] && continue
  [[ -z "$start" ]] && continue
  echo "file 'segments/${label}.mp4'"
done < cuts.txt > concat-list.txt
```

### Concatenate (stream copy — requires matching codecs across all segments)

```bash
ffmpeg -f concat -safe 0 -i concat-list.txt -c copy assembled/rough-cut.mp4
```

### Concatenate with re-encode (handles mismatched resolutions/codecs)

```bash
ffmpeg -f concat -safe 0 -i concat-list.txt \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 128k \
  assembled/rough-cut.mp4
```

### Manual concat list (alternative — no cuts.txt dependency)

```bash
# concat-list.txt contents:
file 'segments/intro.mp4'
file 'segments/feature-demo.mp4'
file 'segments/closing.mp4'
```

---

## Proxy Generation

Generate low-resolution proxy for fast editing. Edit proxy; swap to source for final render.

### Generate proxy (720p, fast encode)

```bash
ffmpeg -i input.mp4 \
  -vf scale=1280:720 \
  -c:v libx264 -preset ultrafast -crf 28 \
  -c:a aac -b:a 96k \
  proxy-720p.mp4
```

### Generate proxy (480p, minimum for 16:9 work)

```bash
ffmpeg -i input.mp4 \
  -vf scale=854:480 \
  -c:v libx264 -preset ultrafast -crf 32 \
  -c:a aac -b:a 64k \
  proxy-480p.mp4
```

### Swap proxy back to source (replace proxy path in concat-list.txt)

```bash
sed -i 's|proxy-720p|input|g' concat-list.txt
```

---

## Audio Extraction

### Extract audio track only (AAC)

```bash
ffmpeg -i input.mp4 -vn -c:a aac -b:a 192k audio.aac
```

### Extract audio as WAV (for normalization tools)

```bash
ffmpeg -i input.mp4 -vn -c:a pcm_s16le audio.wav
```

### Extract audio as MP3

```bash
ffmpeg -i input.mp4 -vn -c:a libmp3lame -b:a 192k audio.mp3
```

---

## Audio Normalization

### Two-pass loudness normalization (EBU R128, broadcast standard)

**Pass 1** — measure loudness:

```bash
ffmpeg -i input.mp4 -af loudnorm=print_format=json -f null - 2>&1 | tail -12
```

**Pass 2** — apply measured values (substitute values from Pass 1 output):

```bash
ffmpeg -i input.mp4 \
  -af "loudnorm=I=-16:TP=-1.5:LRA=11:measured_I=-23.5:measured_TP=-2.1:measured_LRA=7.3:measured_thresh=-33.6:offset=0.58:linear=true" \
  -c:v copy \
  normalized.mp4
```

### Simple volume boost/cut (quick, not loudness-aware)

```bash
# Boost by 6dB
ffmpeg -i input.mp4 -af "volume=6dB" -c:v copy output.mp4

# Cut by 3dB
ffmpeg -i input.mp4 -af "volume=-3dB" -c:v copy output.mp4
```

---

## Scene Detection

Detect scene changes (cuts) automatically. Output is a list of timestamps.

### Scene detection — print timestamps to stdout

```bash
ffmpeg -i input.mp4 \
  -vf "select='gt(scene,0.3)',showinfo" \
  -f null - 2>&1 | grep "pts_time" | awk -F'pts_time:' '{print $2}' | awk '{print $1}'
```

`0.3` = scene change threshold (0.0-1.0). Lower = more sensitive. Typical range: 0.2-0.4.

### Scene detection — write thumbnail at each scene change

```bash
ffmpeg -i input.mp4 \
  -vf "select='gt(scene,0.3)',scale=320:180" \
  -vsync vfr \
  scene-thumbs/thumb-%04d.jpg
```

---

## Silence Detection

Detect silent sections for auto-cutting dead air.

### Detect silence (prints START and END timestamps to stderr)

```bash
ffmpeg -i input.mp4 \
  -af "silencedetect=noise=-30dB:duration=0.5" \
  -f null - 2>&1 | grep "silence_"
```

- `noise=-30dB` — silence threshold (adjust for noisy environments: -40dB to -20dB)
- `duration=0.5` — minimum silence duration in seconds to report

### Parse silence output to generate cut candidates

```bash
ffmpeg -i input.mp4 \
  -af "silencedetect=noise=-30dB:duration=0.5" \
  -f null - 2>&1 \
  | grep "silence_end" \
  | awk '{print $5}' \
  | while read ts; do echo "Candidate cut at: $ts"; done
```

---

## Social Media Reframing

### Platform aspect ratios

| Platform | Ratio | Dimensions | Use Case |
|----------|-------|------------|----------|
| YouTube, standard | 16:9 | 1920x1080 | Horizontal video |
| Instagram Reels, TikTok | 9:16 | 1080x1920 | Vertical video |
| Instagram square | 1:1 | 1080x1080 | Feed posts |
| Twitter/X | 16:9 | 1280x720 | Native |
| LinkedIn | 16:9 or 1:1 | varies | Feed |

### 16:9 to 9:16 (crop center for vertical)

```bash
ffmpeg -i input.mp4 \
  -vf "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920" \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 128k \
  output-9x16.mp4
```

### 16:9 to 1:1 (crop center square)

```bash
ffmpeg -i input.mp4 \
  -vf "crop=ih:ih:(iw-ih)/2:0,scale=1080:1080" \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 128k \
  output-1x1.mp4
```

### 16:9 to 9:16 with blur background (no crop — full frame + blurred pillarbox)

```bash
ffmpeg -i input.mp4 \
  -vf "split[original][copy];[copy]scale=1080:1920,boxblur=20:5[blurred];[original]scale=1080:-2[scaled];[blurred][scaled]overlay=(W-w)/2:(H-h)/2" \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 128k \
  output-9x16-blurred.mp4
```

### Scale to specific resolution (maintain aspect ratio, pad to exact dimensions)

```bash
# Pad to 1920x1080 with black bars
ffmpeg -i input.mp4 \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black" \
  -c:v libx264 -preset fast -crf 23 \
  output-padded.mp4
```

---

## Useful Utility Commands

### Add subtitles/captions (from SRT file)

```bash
ffmpeg -i input.mp4 -vf "subtitles=captions.srt" \
  -c:v libx264 -preset fast -crf 23 \
  -c:a copy \
  output-captioned.mp4
```

### Mute audio track

```bash
ffmpeg -i input.mp4 -an -c:v copy output-muted.mp4
```

### Replace audio track

```bash
ffmpeg -i input.mp4 -i new-audio.mp3 \
  -map 0:v -map 1:a \
  -c:v copy -c:a aac \
  -shortest \
  output-new-audio.mp4
```

### Generate thumbnail at timestamp

```bash
ffmpeg -ss 00:00:10 -i input.mp4 -vframes 1 -q:v 2 thumbnail.jpg
```

### Speed up video (2x, no audio pitch change)

```bash
ffmpeg -i input.mp4 \
  -vf "setpts=0.5*PTS" \
  -af "atempo=2.0" \
  -c:v libx264 -preset fast \
  output-2x.mp4
```
