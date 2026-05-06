# Capacitor iOS Reference

Export a browser-based game (Three.js or Phaser) to iOS via Capacitor 5+. Capacitor wraps your `dist/` output in a native WKWebView and handles the bridge to iOS APIs.

---

## Setup

```bash
# Install Capacitor
npm install @capacitor/core @capacitor/ios

# Initialize (run once per project)
# web-dir must match your build output directory
npx cap init "My Game" com.yourname.mygame --web-dir dist

# Add iOS platform
npx cap add ios
```

---

## capacitor.config.ts

```typescript
import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId:   'com.yourname.mygame',
  appName: 'My Game',
  webDir:  'dist',
  server: {
    androidScheme: 'https',  // use https for consistency
  },
  ios: {
    contentInset: 'automatic',
    scrollEnabled: false,  // prevent scroll on game canvas
  },
};

export default config;
```

---

## Build Cycle

Every time you change web code, repeat this cycle:

```bash
# 1. Build web output
npm run build

# 2. Sync web assets to native project
npx cap sync

# 3. Open Xcode (do the actual iOS build from there)
npx cap open ios
```

`npx cap sync` copies `dist/` to `ios/App/App/public/` and updates Capacitor plugin configurations. Run it every time you change web output.

---

## SPM (Swift Package Manager)

Capacitor 5+ uses SPM by default — no CocoaPods needed.

If you see a `Podfile`, you're using an older Capacitor version. Migrate:

```bash
npx cap migrate  # upgrades to latest Capacitor
```

To verify SPM is in use:
```bash
ls ios/App/         # Should NOT contain Podfile (or Podfile.lock)
ls ios/App/Packages # Should contain Package.swift references
```

---

## Asset Contract

The `assets_index.json` manifest must exist and use only relative paths. Both the web game and the native wrapper read from it.

```json
{
  "version": "1.0",
  "assets": {
    "player":      "assets/player.png",
    "enemy":       "assets/enemy.png",
    "tileset":     "assets/tileset.png",
    "bgm":         "assets/music.ogg",
    "hit":         "assets/hit.wav"
  }
}
```

**Critical rule**: All paths must be relative, never absolute. In a WKWebView, `/assets/player.png` resolves to the iOS filesystem root, not the app bundle. Use `assets/player.png` (no leading slash).

Check for violations:
```bash
grep -r '"/' dist/ --include="*.json" --include="*.js" | grep -v "http" | grep -v "https"
```

---

## Touch Controls

Map touch events to game input. The game canvas receives touch events; map them to virtual input.

```javascript
// src/input/TouchControls.js
import { emit } from '../EventBus.js';

export function initTouchControls(canvas) {
  // Virtual joystick (left side of screen)
  let joystickOrigin = null;

  canvas.addEventListener('touchstart', (e) => {
    for (const touch of e.changedTouches) {
      if (touch.clientX < canvas.width / 2) {
        joystickOrigin = { x: touch.clientX, y: touch.clientY, id: touch.identifier };
      } else {
        // Right side = action button
        emit('PLAYER_ACTION', { x: touch.clientX, y: touch.clientY });
      }
    }
    e.preventDefault();
  }, { passive: false });

  canvas.addEventListener('touchmove', (e) => {
    for (const touch of e.changedTouches) {
      if (joystickOrigin && touch.identifier === joystickOrigin.id) {
        const dx = touch.clientX - joystickOrigin.x;
        const dy = touch.clientY - joystickOrigin.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const deadzone = 10;
        if (dist > deadzone) {
          emit('PLAYER_MOVE', { dx: dx / 60, dy: dy / 60 }); // normalized -1 to 1
        }
      }
    }
    e.preventDefault();
  }, { passive: false });

  canvas.addEventListener('touchend', (e) => {
    for (const touch of e.changedTouches) {
      if (joystickOrigin && touch.identifier === joystickOrigin.id) {
        joystickOrigin = null;
        emit('PLAYER_MOVE', { dx: 0, dy: 0 });
      }
    }
  });
}
```

**Phaser-specific**: Phaser's Input Manager already handles multi-touch. Enable it:
```javascript
new Phaser.Game({
  input: {
    activePointers: 3,  // support 3 simultaneous touches
  },
});
```

---

## Debugging on iOS

**Safari Web Inspector** (best tool for native WebView debugging):

1. On iOS device: Settings → Safari → Advanced → Web Inspector → On
2. On Mac: Safari → Develop → [Your iPhone] → [App name]
3. Full JS console, DOM inspector, and network tab work in WKWebView

**Common issues visible in Web Inspector**:
- Absolute path 404s
- AudioContext creation failures (autoplay policy on iOS is stricter than desktop)
- Canvas context loss (iOS terminates background WebGL contexts aggressively)

**Console log forwarding** (alternative if Safari Web Inspector not available):
```javascript
// Forward console.log to Capacitor logger
if (window.Capacitor) {
  const orig = console.log;
  console.log = (...args) => {
    orig(...args);
    // Appears in Xcode output
    window.webkit?.messageHandlers?.log?.postMessage(args.join(' '));
  };
}
```

---

## iOS-Specific Gotchas

| Issue | Cause | Fix |
|---|---|---|
| AudioContext muted on load | iOS autoplay policy is stricter | First AudioContext creation must be inside touchstart/touchend handler |
| WebGL context lost on background | iOS kills background GPU contexts | Listen for `webglcontextlost`, restore on `webglcontextrestored` |
| Canvas is blurry on Retina | Missing `devicePixelRatio` scaling | `canvas.width = width * devicePixelRatio; ctx.scale(dpr, dpr)` |
| Touch events fire with 300ms delay | Legacy click delay | Add `<meta name="viewport" content="... touch-action: none">` or use `pointer` events |
| Assets load from wrong path | Absolute paths in WKWebView | All paths relative, verify with pre-deploy checklist |

---

## App Store Submission Checklist

- [ ] Build and run on physical device (not just simulator)
- [ ] App icon provided at all required sizes (use `capacitor-assets` tool)
- [ ] Launch screen configured (no blank white flash)
- [ ] Privacy manifest included (required for iOS 17+ for apps using APIs)
- [ ] Info.plist has required usage descriptions for any hardware APIs used
- [ ] Game tested offline (no localhost fetches in production build)
- [ ] Version and build number set in Xcode project settings

---

## Error Handling

### Error: npx cap sync Fails with "Cannot find module"
**Cause**: Capacitor CLI version mismatch between project and global
**Fix**: Use local CLI: `npx cap sync` (not `cap sync`). Ensure `@capacitor/cli` is in `devDependencies`.

### Error: App Shows White Screen in Simulator
**Cause**: `webDir` in `capacitor.config.ts` does not match actual build output directory, or `npm run build` was not run before `cap sync`
**Fix**: Check `dist/` contains `index.html`. Verify `webDir: 'dist'` in config. Run `npm run build` then `npx cap sync` again.

### Error: Audio Plays on Simulator But Not Device
**Cause**: iOS audio session not configured, or AudioContext created outside gesture
**Fix**: AudioContext creation must be inside `touchstart` or `touchend` handler — iOS is stricter than macOS. Add `@capacitor/haptics` if you also want haptic feedback on hit events.

### Error: CocoaPods Errors After Adding Plugin
**Cause**: Some older Capacitor plugins still use CocoaPods
**Fix**: Install CocoaPods as fallback: `sudo gem install cocoapods && cd ios/App && pod install`. Then open `ios/App/App.xcworkspace` (not `.xcodeproj`).
