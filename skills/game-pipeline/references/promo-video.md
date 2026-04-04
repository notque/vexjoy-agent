# Promo Video Reference

Record gameplay footage for social media using Playwright + FFmpeg. No paid screen capture tools needed.

---

## The Slow-Mo Trick

**Why it works**: Record at 0.5× game speed in Playwright (gives more time per frame), then use FFmpeg `setpts=0.5*PTS` to play it back at 2×. Result: smooth 50fps output from a 25fps capture.

```
Game speed: 0.5×  →  Playwright captures at normal wall-clock rate
FFmpeg 2× speed  →  Converts to smooth 50fps output
```

This sidesteps Playwright's screenshot rate limit (~15fps practical maximum) while producing fluid video.

---

## Step 1: Set Game Speed

Expose a speed multiplier in the game before recording:

```javascript
// src/main.js — test seam extension
if (window.__TEST__) {
  window.__TEST__.setSpeed = (s) => { game.speed = s; };
}

// In game loop, multiply delta:
const delta = rawDelta * (game.speed ?? 1.0);
```

---

## Step 2: Playwright Recording Script

```javascript
// scripts/record-promo.js
import { chromium } from 'playwright';
import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

const FRAMES_DIR = 'promo/frames';
const FPS        = 25;          // capture rate (wall clock)
const DURATION   = 30;          // seconds of captured footage
const GAME_SPEED = 0.5;         // slower = smoother video after FFmpeg 2×
const VIEWPORT   = { width: 1080, height: 1920 }; // 9:16 portrait for Reels/Shorts

async function record() {
  fs.mkdirSync(FRAMES_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const ctx     = await browser.newContext({ viewport: VIEWPORT });
  const page    = await ctx.newPage();

  await page.goto('http://localhost:3000?test=1&seed=42');
  await page.waitForFunction(() => typeof window.__TEST__ !== 'undefined');

  // Slow down game for smoother capture
  await page.evaluate((speed) => window.__TEST__.setSpeed(speed), GAME_SPEED);

  // Optional: script player actions for consistent footage
  await scriptPlayerActions(page);

  // Capture frames
  const totalFrames = FPS * DURATION;
  const frameInterval = 1000 / FPS;

  for (let i = 0; i < totalFrames; i++) {
    const framePath = path.join(FRAMES_DIR, `frame-${String(i).padStart(5, '0')}.png`);
    await page.screenshot({ path: framePath });
    await page.waitForTimeout(frameInterval);
  }

  await browser.close();
  console.log(`Captured ${totalFrames} frames`);
}

async function scriptPlayerActions(page) {
  // Simulate player for consistent, impressive footage
  // Example: click-to-fire pattern
  const { width, height } = VIEWPORT;

  for (let i = 0; i < 5; i++) {
    await page.click(`body`, {
      position: { x: width / 2 + (Math.random() - 0.5) * 200, y: height / 2 }
    });
    await page.waitForTimeout(500);
  }
}

record().catch(console.error);
```

---

## Step 3: CDP Screencast (Alternative to Screenshot Loop)

For smoother capture, use Chrome DevTools Protocol screencast instead of a screenshot loop. Requires `playwright-chromium` or raw CDP access:

```javascript
const client = await ctx.newCDPSession(page);
await client.send('Page.startScreencast', {
  format:        'png',
  everyNthFrame: 1,
});

const frames = [];
client.on('Page.screencastFrame', async ({ data, sessionId }) => {
  frames.push(Buffer.from(data, 'base64'));
  await client.send('Page.screencastFrameAck', { sessionId });
});

// Wait for desired duration...
await page.waitForTimeout(DURATION * 1000);
await client.send('Page.stopScreencast');

// Write frames to disk
frames.forEach((buf, i) => {
  fs.writeFileSync(path.join(FRAMES_DIR, `frame-${String(i).padStart(5, '0')}.png`), buf);
});
```

CDP screencast gives more consistent timing than a manual screenshot loop.

---

## Step 4: FFmpeg Assembly

```bash
#!/bin/bash
# assemble-promo.sh

FRAMES_DIR="promo/frames"
OUTPUT="promo/output.mp4"
AUDIO="assets/bgm-highlight.mp3"  # optional

# Step 1: Frames → video at 2× speed (the slow-mo reversal)
ffmpeg -y \
  -framerate 25 \
  -i "$FRAMES_DIR/frame-%05d.png" \
  -vf "setpts=0.5*PTS,fps=50" \
  -c:v libx264 \
  -preset slow \
  -crf 18 \
  -pix_fmt yuv420p \
  promo/video-only.mp4

# Step 2: Add audio track (optional)
if [ -f "$AUDIO" ]; then
  ffmpeg -y \
    -i promo/video-only.mp4 \
    -i "$AUDIO" \
    -c:v copy \
    -c:a aac \
    -b:a 192k \
    -shortest \
    "$OUTPUT"
else
  cp promo/video-only.mp4 "$OUTPUT"
fi

echo "Promo video: $OUTPUT"
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of default "$OUTPUT"
```

---

## Mobile Portrait Format (9:16)

Social platforms (TikTok, Instagram Reels, YouTube Shorts) prefer 9:16 vertical video.

| Platform | Resolution | Max Duration |
|---|---|---|
| TikTok | 1080×1920 | 10 min |
| Instagram Reels | 1080×1920 | 90 sec |
| YouTube Shorts | 1080×1920 | 60 sec |

Set Playwright viewport to `{ width: 1080, height: 1920 }`. If the game is landscape, add a letterbox:

```bash
# Letterbox landscape 1920×1080 into 1080×1920 portrait
ffmpeg -i landscape.mp4 \
  -vf "scale=1080:608,pad=1080:1920:0:656:black" \
  portrait.mp4
```

---

## Automated Gameplay Tips

Make the recorded gameplay look impressive without manual play:

```javascript
// Auto-play patterns for impressive footage
async function scriptPlayerActions(page) {
  const W = 1080, H = 1920;

  // Fire in a spread pattern
  for (let angle = 0; angle < Math.PI * 2; angle += Math.PI / 8) {
    const x = W/2 + Math.cos(angle) * 200;
    const y = H/2 + Math.sin(angle) * 200;
    await page.mouse.click(x, y);
    await page.waitForTimeout(200);
  }

  // Trigger level-up via keyboard (if game supports it)
  await page.keyboard.press('KeyL');
  await page.waitForTimeout(1000);
}
```

---

## Error Handling

### Error: Video Is Choppy Despite the Slow-Mo Trick
**Cause**: Screenshot loop timing is too inconsistent, or game runs heavy compute that delays captures
**Fix**: Switch to CDP screencast (Step 3). Use `--preset ultrafast` in FFmpeg to rule out encode bottleneck.

### Error: FFmpeg "Invalid frame count" Error
**Cause**: Frame numbering gap (missing frames from capture errors)
**Fix**: Check `ls promo/frames/ | wc -l` vs expected count. Re-run capture. If only a few frames are missing, duplicate neighboring frames to fill gaps.

### Error: Audio Desync in Final Video
**Cause**: Audio track length does not match video after 2× speed change
**Fix**: Use `-shortest` flag (already in script above). Or trim audio to match: `ffmpeg -i audio.mp3 -t 15 trimmed.mp3`.

### Error: Portrait Video Has Black Bars on YouTube
**Cause**: Metadata says landscape despite portrait resolution
**Fix**: Add `-metadata:s:v:0 rotate=0` to FFmpeg command, or force portrait via `-vf "transpose=1"` if frames were captured landscape.
