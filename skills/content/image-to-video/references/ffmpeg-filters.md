# FFmpeg Filters for Image-to-Video

Reference documentation for FFmpeg filters used in audio visualization.

---

## Scale and Pad Filter

Scales image to target resolution while maintaining aspect ratio, then pads with black to fill frame.

```
scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black
```

**Parameters:**
- `force_original_aspect_ratio=decrease` - Shrink to fit, never stretch
- `pad` - Add black bars to reach target dimensions
- `(ow-iw)/2:(oh-ih)/2` - Center the image in the padded frame

---

## Showwaves Filter

Generates a video visualization of audio waveform.

```
showwaves=s={width}x{height}:mode=cline:colors=white@0.7:rate=25
```

**Parameters:**
- `s` - Size of output (width x height)
- `mode` - Drawing mode:
  - `point` - Draw dots
  - `line` - Draw vertical lines
  - `p2p` - Point to point connection
  - `cline` - Centered line (symmetric around center)
- `colors` - Waveform color with optional alpha (`white@0.7` = 70% opacity)
- `rate` - Frame rate for animation (typically 25 or 30)

**Recommended modes by use case:**
- `cline` - Music visualization (balanced, aesthetic)
- `line` - Podcast (simple, clear)
- `p2p` - Waveform analysis (shows peaks clearly)

---

## Showspectrum Filter

Generates a frequency spectrum visualization.

```
showspectrum=s={width}x{height}:mode=combined:color=intensity:scale=cbrt:slide=scroll
```

**Parameters:**
- `s` - Size of output
- `mode` - Channel handling:
  - `combined` - Both channels combined
  - `separate` - Stacked channels
- `color` - Color scheme:
  - `intensity` - Heat map (default, most readable)
  - `rainbow` - Full spectrum colors
  - `channel` - Color by stereo position
  - `fire` - Red/orange gradient
- `scale` - Frequency scale:
  - `lin` - Linear (bass heavy)
  - `sqrt` - Square root (balanced)
  - `cbrt` - Cube root (more treble detail)
  - `log` - Logarithmic (closest to human hearing)
- `slide` - Animation direction:
  - `scroll` - Scroll left (most common)
  - `replace` - Replace column by column
  - `fullframe` - Update entire frame

---

## Overlay Filter

Composites one video on top of another.

```
overlay=x:y
```

**Common positions:**
- `overlay=0:0` - Top left
- `overlay=0:H-h` - Bottom left
- `overlay=W-w:0` - Top right
- `overlay=W-w:H-h` - Bottom right
- `overlay=(W-w)/2:H-h` - Bottom center

**Special expressions:**
- `W`, `H` - Main (background) video dimensions
- `w`, `h` - Overlay video dimensions
- `H-h-20` - Bottom with 20px margin

---

## Complete Filter Graphs

### Static Mode
```
[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black[v]
```

### Waveform Mode
```
[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black[bg];
[1:a]showwaves=s=1920x270:mode=cline:colors=white@0.7:rate=25[wave];
[bg][wave]overlay=0:H-h-20[v]
```

### Spectrum Mode
```
[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black[bg];
[1:a]showspectrum=s=1920x360:mode=combined:color=intensity:scale=cbrt:slide=scroll[spec];
[bg][spec]overlay=0:H-h-10[v]
```

---

## Encoding Settings

### Video Codec (H.264)
```
-c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p
```

**Parameters:**
- `preset` - Speed/quality tradeoff:
  - `ultrafast` - Fastest encoding, largest file
  - `medium` - Balanced (default)
  - `slow` - Better compression, slower
- `crf` - Quality (0-51, lower is better):
  - `18` - Visually lossless
  - `23` - Default, good quality
  - `28` - Smaller file, visible artifacts
- `pix_fmt` - Pixel format (`yuv420p` for maximum compatibility)

### Audio Codec (AAC)
```
-c:a aac -b:a 192k
```

**Parameters:**
- `b:a` - Audio bitrate:
  - `128k` - Acceptable quality
  - `192k` - Good quality (default)
  - `256k` - High quality
  - `320k` - Maximum useful quality

---

## Common Issues

### Issue: "Could not find codec parameters"
**Cause:** Image format not supported
**Fix:** Convert to PNG or JPG first

### Issue: "Stream 1 incomplete"
**Cause:** Audio file is corrupted or format unsupported
**Fix:** Convert audio to MP3 or WAV with: `ffmpeg -i input.audio -acodec pcm_s16le output.wav`

### Issue: "Filter showwaves requires libavfilter"
**Cause:** FFmpeg compiled without filter support
**Fix:** Install full FFmpeg build: `brew install ffmpeg` or `apt install ffmpeg`

### Issue: Green/corrupt output
**Cause:** Pixel format incompatibility
**Fix:** Ensure `-pix_fmt yuv420p` is included

### Issue: "Error while opening encoder"
**Cause:** libx264 not available
**Fix:** Install with codec support: `apt install libx264-dev` then rebuild FFmpeg

---

## Alternative Visualization Filters

### Volume Bar (VU Meter)
```
showvolume=f=0.5:w=800:h=40:c=0xff0000
```

### Audio Vector Scope
```
avectorscope=s=800x800:zoom=1.5:rc=40:gc=160:bc=80
```

### Histogram
```
ahistogram=s=1920x540
```

These can be substituted in the filter graph for different visual effects.
