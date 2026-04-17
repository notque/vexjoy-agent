# Video Editing Error Handling

Verbatim error matrix.

### Error: "No such file or directory" on source file
**Cause**: Path in cuts.txt or command doesn't match actual filename.
**Solution**: Run `cat source-inventory.txt`. Check for spaces in filenames — quote all paths.

### Error: FFmpeg "Invalid option" or codec errors
**Cause**: Codec unavailable in this FFmpeg build, or flag syntax error.
**Solution**: Run `ffmpeg -codecs | grep libx264`. Fall back to `-c:v copy` if re-encoding not needed. See `references/ffmpeg-commands.md`.

### Error: Remotion "Could not find composition"
**Cause**: Composition ID in render command doesn't match the `id` prop in TSX.
**Solution**: Check `src/index.ts` for registered composition ID. Match exactly in render command. See `references/remotion-scaffold.md`.

### Error: Segments exist but concat produces wrong order
**Cause**: Shell glob `segments/*.mp4` sorts alphabetically, not by EDL order.
**Solution**: Generate concat-list.txt from cuts.txt order — Phase 3 Step 3 in this skill always reads from cuts.txt, not glob.

### Error: ElevenLabs API 401
**Cause**: `ELEVENLABS_API_KEY` not set.
**Solution**: `export ELEVENLABS_API_KEY=your_key` before running Phase 5.
