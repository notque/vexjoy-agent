# Remotion integration contracts

Use Remotion only when a plain FFmpeg assembly cannot express the requested timed graphics.

- `registerRoot` must register the root containing `<Composition>`.
- The `<Composition id>` must exactly equal the ID passed to `npx remotion render`.
- `durationInFrames`, `Sequence.from`, and `Sequence.durationInFrames` are frames. Convert probed seconds using the composition FPS and define a rounding policy once.
- Imported media paths must be resolvable by Remotion; prefer `staticFile()` for files under `public/` rather than incidental working-directory paths.
- Sum segment frame durations for the composition duration. A `Sequence` offset advances by the preceding segment's frame count.
- `useCurrentFrame()` inside a `Sequence` is sequence-relative; avoid subtracting the sequence start a second time.

Minimal registration:

```tsx
import {Composition, registerRoot} from 'remotion';
import {VideoComposition} from './VideoComposition';

const Root = () => <Composition id="VideoComposition" component={VideoComposition}
  durationInFrames={300} fps={30} width={1920} height={1080} />;
registerRoot(Root);
```

Render with the same ID:

```bash
npx remotion render src/index.ts VideoComposition assembled/remotion-output.mp4
```

Probe the render; a successful command does not validate editorial timing or stream compatibility.
