# Image/audio visualization filter graphs

Scale without distortion and pad to the delivery frame:

```text
[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black[bg]
```

Waveform overlay:

```text
[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black[bg];
[1:a]showwaves=s=1920x270:mode=cline:colors=white@0.7:rate=25[wave];
[bg][wave]overlay=0:H-h-20[v]
```

Scrolling spectrum:

```text
[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black[bg];
[1:a]showspectrum=s=1920x360:mode=combined:color=intensity:scale=cbrt:slide=scroll[spec];
[bg][spec]overlay=0:H-h-10[v]
```

Map `[v]` plus the original audio and encode with `-c:v libx264 -pix_fmt yuv420p -c:a aac`. `yuv420p` avoids green/corrupt output on common players. Minimal FFmpeg builds may omit `showwaves`, `showspectrum`, or `showcqt`; use static mode or install a full build rather than silently changing the requested visualization.
