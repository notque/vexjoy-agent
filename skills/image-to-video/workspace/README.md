# Image-to-Video Workspace

This directory manages the workflow for image-to-video conversions.

## Directory Structure

```
workspace/
├── input/      # Place image + audio pairs here
├── output/     # Generated videos appear here
└── completed/  # Processed input files moved here
```

## Workflow

1. **Add files to `input/`**
   - Place your image file (PNG, JPG)
   - Place your audio file (MP3, WAV)
   - Files are matched by name (e.g., `song.png` + `song.mp3`)

2. **Run the script**
   ```bash
   python3 skills/image-to-video/scripts/image_to_video.py --process-workspace
   ```

3. **Find output in `output/`**
   - Generated MP4 files appear here
   - Named after the input pair (e.g., `song.mp4`)

4. **Input files move to `completed/`**
   - After successful conversion, inputs are archived
   - Prevents re-processing

## File Matching

The script matches files by base name:
- `cover.png` + `cover.mp3` → `cover.mp4`
- `podcast_ep1.jpg` + `podcast_ep1.wav` → `podcast_ep1.mp4`

## Quick Start

```bash
# Copy your files
cp ~/my-cover.png skills/image-to-video/workspace/input/song.png
cp ~/my-song.mp3 skills/image-to-video/workspace/input/song.mp3

# Process all pairs
python3 skills/image-to-video/scripts/image_to_video.py --process-workspace

# Check output
ls skills/image-to-video/workspace/output/
```
