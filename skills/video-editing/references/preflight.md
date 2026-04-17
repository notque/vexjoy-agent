# Video Editing Preflight

Verbatim preflight checks. Run before Phase 1.

**Hard requirements** (BLOCK if missing — halt immediately):
- `ffmpeg`: required for all phases
- `node`: required for Remotion and npx tooling

**Soft requirements** (WARN if missing — continue unless Layer 4 is needed):
- `remotion`: only required for Phase 4 (Remotion composition)

```bash
# Hard requirements — exit 1 if missing
which ffmpeg >/dev/null 2>&1 || {
  echo "ERROR: ffmpeg not found. Cannot continue."
  echo "Install: brew install ffmpeg  (macOS)  |  apt install ffmpeg  (Linux)"
  exit 1
}
which node >/dev/null 2>&1 || {
  echo "ERROR: node not found. Cannot continue."
  echo "Install: https://nodejs.org or via nvm"
  exit 1
}

# Soft requirement — warn only; continue unless Phase 4 is needed
npx remotion --version >/dev/null 2>&1 || {
  echo "WARNING: remotion CLI not found."
  echo "Layers 1-3 and 5-6 will proceed normally."
  echo "Phase 4 (Remotion composition) will be unavailable."
  echo "Install when needed: npm install @remotion/cli  (in your project directory)"
}

echo "Preflight: ffmpeg OK, node OK. (remotion optional — see above if warned)"
```
