# Visualization implementation notes

`scripts/image_to_video.py` is authoritative. All modes first fit the image without stretching and pad it black to the requested frame. Animated modes darken the background and blend a blurred duplicate of the visualization as a screen-mode glow.

| Mode | Repository-specific graph |
|---|---|
| `waveform` | `showwaves`, lower third, `p2p`, 30 fps, square-root scale, cyan/magenta, 40 px bottom offset |
| `spectrum` | `showspectrum`, lower third, combined channels, fire palette, log scale, scrolling, 20 px bottom offset |
| `cqt` | `showcqt=fullhd=1` with custom bar/sonogram gains, overlaid from the bottom |
| `bars` | `showfreqs`, lower half, separate-channel bars, logarithmic frequency and amplitude, cyan/magenta, Hann window size 2048 |

## CQT resolution caveat

`showcqt=fullhd=1` produces 1920x1080. The current graph does not rescale that CQT output before overlaying it, so CQT is only reliable with the `1080p` preset; other presets can crop or fail. Do not promise square, vertical, or 720p CQT output without changing and testing the graph.

## Failures that change the action

- The animated graphs require the named source filter plus `gblur`, `colorchannelmixer`, `blend`, and `overlay`. Minimal FFmpeg builds may lack them.
- `cqt` additionally requires `showcqt`; `bars` requires `showfreqs`.
- On a missing-filter error, offer `static` or installation of a full FFmpeg build. Never claim that a requested animation was produced by a static fallback.
- Green or broadly incompatible output should retain `yuv420p`; the wrapper already sets it.
- Diagnose an unreadable audio stream with `ffprobe` before transcoding it to a supported format.
