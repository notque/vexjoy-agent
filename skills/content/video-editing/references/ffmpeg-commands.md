# FFmpeg contracts

These commands encode repository workflow choices; adjust paths and target quality, not their ordering semantics.

## Inspect and detect

```bash
ffprobe -v error -show_entries format=duration,size,bit_rate -show_entries stream=index,codec_type,codec_name,width,height,r_frame_rate -of json input.mp4
ffmpeg -i input.mp4 -vf "select='gt(scene,0.3)',showinfo" -f null - 2>&1
ffmpeg -i input.mp4 -af "silencedetect=noise=-30dB:duration=0.5" -f null - 2>&1
```

Detection proposes boundaries; it does not choose edits.

## EDL-driven cut and concat

`cuts.txt` uses `START_TIME,END_TIME,LABEL`; labels must be unique and path-safe.

```bash
mkdir -p segments assembled
while IFS=',' read -r start end label; do
  [[ "$start" == \#* || -z "$start" ]] && continue
  ffmpeg -ss "$start" -to "$end" -i input.mp4 \
    -c:v libx264 -preset fast -crf 23 -c:a aac -b:a 128k \
    -avoid_negative_ts make_zero "segments/${label}.mp4"
done < cuts.txt

while IFS=',' read -r start end label; do
  [[ "$start" == \#* || -z "$start" ]] && continue
  printf "file '%s'\n" "segments/${label}.mp4"
done < cuts.txt > concat-list.txt

ffmpeg -f concat -safe 0 -i concat-list.txt -c copy assembled/rough-cut.mp4
```

Use `-c copy` for cutting only when keyframe-aligned cuts are acceptable. If concat rejects mismatched streams, replace final `-c copy` with `-c:v libx264 -preset fast -crf 23 -c:a aac -b:a 128k`.

## Proxy and loudness

```bash
ffmpeg -i input.mp4 -vf 'scale=1280:-2' -c:v libx264 -preset ultrafast -crf 28 -c:a aac -b:a 96k proxy.mp4
ffmpeg -i input.mp4 -af loudnorm=print_format=json -f null -
```

Two-pass `loudnorm` requires copying the measured `input_i`, `input_tp`, `input_lra`, `input_thresh`, and `target_offset` values into pass two. Do not reuse example measurements across files.
