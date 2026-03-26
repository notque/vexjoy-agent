# Remotion Scaffold Reference

Remotion renders React/TypeScript compositions to video. These templates are
copy-paste ready. Composition ID must match exactly between `registerRoot` and
the `npx remotion render` command.

---

## Project Setup

### Initialize new Remotion project

```bash
npm create video@latest
# Follow prompts: choose "Hello World" starter, TypeScript
```

### Add Remotion to existing project

```bash
npm install remotion @remotion/cli @remotion/player
```

### Project structure (minimal)

```
my-video/
  src/
    index.ts          -- registerRoot entry point
    Root.tsx          -- composition registration
    VideoComposition.tsx  -- main composition
  package.json
  tsconfig.json
```

---

## Basic Composition (Single Video)

### src/VideoComposition.tsx

```tsx
import { AbsoluteFill, Video, useVideoConfig } from "remotion";

interface Props {
  videoSrc: string;
}

export const VideoComposition: React.FC<Props> = ({ videoSrc }) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <Video src={videoSrc} style={{ width: "100%", height: "100%" }} />
    </AbsoluteFill>
  );
};
```

### src/Root.tsx

```tsx
import { Composition } from "remotion";
import { VideoComposition } from "./VideoComposition";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="VideoComposition"
        component={VideoComposition}
        durationInFrames={300}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          videoSrc: "./input.mp4",
        }}
      />
    </>
  );
};
```

### src/index.ts

```ts
import { registerRoot } from "remotion";
import { RemotionRoot } from "./Root";

registerRoot(RemotionRoot);
```

---

## Multi-Segment Composition (Sequence-Based)

Use `Sequence` to place each segment at a specific frame offset.
`from` is the start frame; `durationInFrames` is the segment length.

### src/VideoComposition.tsx (multi-segment)

```tsx
import { AbsoluteFill, Sequence, Video, useVideoConfig } from "remotion";

interface Segment {
  src: string;
  durationInFrames: number;
  label: string;
}

interface Props {
  segments: Segment[];
}

export const VideoComposition: React.FC<Props> = ({ segments }) => {
  let offset = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {segments.map((seg) => {
        const from = offset;
        offset += seg.durationInFrames;
        return (
          <Sequence
            key={seg.label}
            from={from}
            durationInFrames={seg.durationInFrames}
          >
            <AbsoluteFill>
              <Video
                src={seg.src}
                style={{ width: "100%", height: "100%" }}
              />
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
```

### src/Root.tsx (multi-segment with calculated total duration)

```tsx
import { Composition } from "remotion";
import { VideoComposition } from "./VideoComposition";

const SEGMENTS = [
  { src: "./segments/intro.mp4",        durationInFrames: 90,  label: "intro" },
  { src: "./segments/feature-demo.mp4", durationInFrames: 180, label: "feature-demo" },
  { src: "./segments/closing.mp4",      durationInFrames: 75,  label: "closing" },
];

const TOTAL_FRAMES = SEGMENTS.reduce((sum, s) => sum + s.durationInFrames, 0);

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="VideoComposition"
      component={VideoComposition}
      durationInFrames={TOTAL_FRAMES}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{ segments: SEGMENTS }}
    />
  );
};
```

---

## Overlay Components

### Title card overlay (centered text, timed with Sequence)

```tsx
import { AbsoluteFill, Sequence, useCurrentFrame, interpolate } from "remotion";

interface TitleCardProps {
  text: string;
  from: number;
  durationInFrames: number;
}

export const TitleCard: React.FC<TitleCardProps> = ({ text, from, durationInFrames }) => {
  const frame = useCurrentFrame();

  // Fade in over 15 frames, fade out over 15 frames
  const opacity = interpolate(
    frame,
    [0, 15, durationInFrames - 15, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <Sequence from={from} durationInFrames={durationInFrames}>
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          opacity,
        }}
      >
        <div
          style={{
            color: "white",
            fontSize: 72,
            fontWeight: "bold",
            textShadow: "2px 2px 8px rgba(0,0,0,0.8)",
            fontFamily: "sans-serif",
          }}
        >
          {text}
        </div>
      </AbsoluteFill>
    </Sequence>
  );
};
```

### Lower third (name/title bar)

```tsx
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame } from "remotion";

interface LowerThirdProps {
  name: string;
  title: string;
  from: number;
  durationInFrames?: number;
}

export const LowerThird: React.FC<LowerThirdProps> = ({
  name,
  title,
  from,
  durationInFrames = 90,
}) => {
  const frame = useCurrentFrame();
  const slideIn = interpolate(frame, [0, 20], [-200, 0], {
    extrapolateRight: "clamp",
  });

  return (
    <Sequence from={from} durationInFrames={durationInFrames}>
      <AbsoluteFill style={{ justifyContent: "flex-end", padding: 60 }}>
        <div
          style={{
            transform: `translateX(${slideIn}px)`,
            background: "rgba(0,0,0,0.75)",
            padding: "12px 24px",
            borderLeft: "4px solid #0af",
          }}
        >
          <div style={{ color: "white", fontSize: 28, fontWeight: "bold" }}>
            {name}
          </div>
          <div style={{ color: "#aaa", fontSize: 20 }}>{title}</div>
        </div>
      </AbsoluteFill>
    </Sequence>
  );
};
```

### Usage in main composition

```tsx
export const VideoComposition: React.FC<Props> = ({ segments }) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {/* Video segments */}
      <Sequence from={0} durationInFrames={90}>
        <Video src="./segments/intro.mp4" style={{ width: "100%", height: "100%" }} />
      </Sequence>

      {/* Overlays */}
      <TitleCard text="Product Demo" from={10} durationInFrames={60} />
      <LowerThird name="Jane Smith" title="Lead Engineer" from={95} durationInFrames={90} />
    </AbsoluteFill>
  );
};
```

---

## Render Commands

### Basic render

```bash
npx remotion render src/index.ts VideoComposition assembled/remotion-output.mp4
```

The third argument (`VideoComposition`) must exactly match the `id` prop in `<Composition>`.

### Render with quality settings

```bash
npx remotion render src/index.ts VideoComposition assembled/remotion-output.mp4 \
  --codec=h264 \
  --crf=23 \
  --scale=1
```

### Render a frame range (faster for testing)

```bash
npx remotion render src/index.ts VideoComposition assembled/test-render.mp4 \
  --frames=0-90
```

### Render still (single frame as PNG)

```bash
npx remotion still src/index.ts VideoComposition thumbnail.png --frame=30
```

### Preview in browser (live reload)

```bash
npx remotion studio src/index.ts
```

### List registered compositions

```bash
npx remotion compositions src/index.ts
```

---

## Converting Segment Duration to Frames

When building `SEGMENTS` array, convert from seconds to frames:

```ts
const FPS = 30;

// Duration in seconds -> frames
const secondsToFrames = (seconds: number): number => Math.round(seconds * FPS);

// Example: segment that is 2 minutes 45 seconds = 165 seconds = 4950 frames
const durationInFrames = secondsToFrames(165); // 4950
```

### Get duration of a segment file (for use in Remotion durationInFrames)

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 segments/intro.mp4
# Output: 3.033333
# Multiply by fps (30) and round: 91 frames
```

---

## Reuse Patterns

### Shared video player component

Extract Video + sizing into a reusable component to avoid repetition across sequences:

```tsx
const FullscreenVideo: React.FC<{ src: string }> = ({ src }) => (
  <AbsoluteFill>
    <Video src={src} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
  </AbsoluteFill>
);
```

### Dynamic composition from cuts.txt data

Load EDL data at build time and generate the Remotion composition programmatically:

```ts
// scripts/edl-to-remotion.ts — run before render to generate segments config
import * as fs from "fs";

const cuts = fs.readFileSync("cuts.txt", "utf-8")
  .split("\n")
  .filter((line) => line && !line.startsWith("#"))
  .map((line) => {
    const [start, end, label] = line.split(",");
    return { start, end, label };
  });

// Write to src/segments-config.ts for import in Root.tsx
const config = cuts.map((c) => {
  const durationSec = timeToSeconds(c.end) - timeToSeconds(c.start);
  return `  { src: "./segments/${c.label}.mp4", durationInFrames: ${Math.round(durationSec * 30)}, label: "${c.label}" }`;
});

fs.writeFileSync(
  "src/segments-config.ts",
  `export const SEGMENTS = [\n${config.join(",\n")}\n];\n`
);

function timeToSeconds(t: string): number {
  const parts = t.split(":").map(Number);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return parts[0];
}
```
