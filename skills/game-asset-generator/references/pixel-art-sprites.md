# Pixel Art Sprites — Code-Only Generation

Canvas-based sprite generation with no external API dependency. Works in any browser or Node.js (via `canvas` package). All output is PNG.

---

## Core Concept

Sprites are defined as a **pixel matrix** (2D array of palette indices) plus a **palette** (array of hex colors). Index 0 is always transparent. Render by mapping each non-zero index to its color.

```javascript
// Palette: index 0 = transparent, 1+ = colors
const PALETTE = {
  0: null,       // transparent
  1: '#1a1a2e',  // dark outline
  2: '#e94560',  // primary red
  3: '#f5a623',  // gold/yellow
  4: '#4a90d9',  // blue
  5: '#f8f8f8',  // near-white highlight
  6: '#7c5cbf',  // purple
  7: '#2ecc71',  // green
};

// 8x8 pixel matrix — each number is a palette index
const WARRIOR_SPRITE = [
  [0,0,1,1,1,1,0,0],  // row 0: helmet top
  [0,1,3,3,3,3,1,0],  // row 1: helmet gold
  [0,1,2,5,5,2,1,0],  // row 2: face
  [0,0,1,1,1,1,0,0],  // row 3: neck
  [1,2,2,2,2,2,2,1],  // row 4: body/armor
  [1,2,2,2,2,2,2,1],  // row 5: body
  [0,1,2,1,1,2,1,0],  // row 6: legs
  [0,1,1,0,0,1,1,0],  // row 7: feet
];
```

---

## Renderer

```javascript
function renderSprite(matrix, palette, scale = 4) {
  const rows = matrix.length;
  const cols = matrix[0].length;
  const canvas = document.createElement('canvas');
  canvas.width = cols * scale;
  canvas.height = rows * scale;
  const ctx = canvas.getContext('2d');

  // Clear to transparent
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const colorIndex = matrix[row][col];
      if (colorIndex === 0) continue; // transparent

      const color = palette[colorIndex];
      if (!color) continue;

      ctx.fillStyle = color;
      ctx.fillRect(col * scale, row * scale, scale, scale);
    }
  }

  return canvas;
}

// Usage
const canvas = renderSprite(WARRIOR_SPRITE, PALETTE, 4); // 4px per sprite pixel
document.body.appendChild(canvas);

// Export as PNG data URL
const dataURL = canvas.toDataURL('image/png');
```

---

## Standard Character Template (16x16)

Full character with head, torso, arms, legs. Designed for top-down or side-scroller games.

```javascript
// 16x16 character template — customize palette indices for different characters
const CHARACTER_16x16 = [
  [0,0,0,0,1,1,1,1,1,1,1,1,0,0,0,0],  // hair top
  [0,0,0,1,3,3,3,3,3,3,3,3,1,0,0,0],  // hair
  [0,0,1,3,2,2,2,2,2,2,2,2,3,1,0,0],  // face top
  [0,0,1,2,2,5,2,2,2,2,5,2,2,1,0,0],  // eyes
  [0,0,1,2,2,2,2,2,2,2,2,2,2,1,0,0],  // face
  [0,0,1,2,2,2,1,2,2,1,2,2,2,1,0,0],  // mouth/face
  [0,0,0,1,1,1,1,1,1,1,1,1,1,0,0,0],  // neck
  [0,1,4,4,4,4,4,4,4,4,4,4,4,4,1,0],  // shoulders
  [1,4,4,4,4,4,4,4,4,4,4,4,4,4,4,1],  // torso wide
  [1,4,4,4,4,4,4,4,4,4,4,4,4,4,4,1],  // torso
  [0,1,4,4,4,4,4,4,4,4,4,4,4,4,1,0],  // torso narrow
  [0,0,1,4,4,1,0,0,0,0,1,4,4,1,0,0],  // hip gap
  [0,0,1,4,4,1,0,0,0,0,1,4,4,1,0,0],  // upper legs
  [0,0,1,4,4,1,0,0,0,0,1,4,4,1,0,0],  // mid legs
  [0,0,1,4,4,1,0,0,0,0,1,4,4,1,0,0],  // lower legs
  [0,0,1,1,1,1,0,0,0,0,1,1,1,1,0,0],  // feet
];
```

---

## Palette System

```javascript
// Pre-built palettes for common character types
const PALETTES = {
  warrior: {
    0: null,
    1: '#1a1a2e',  // dark outline
    2: '#c4956a',  // skin tone (medium)
    3: '#8b0000',  // dark red armor
    4: '#cc2222',  // red armor highlight
    5: '#f5deb3',  // skin highlight
    6: '#808080',  // metal/grey
    7: '#c0c0c0',  // metal highlight
  },
  wizard: {
    0: null,
    1: '#1a1a2e',
    2: '#c4956a',  // skin
    3: '#4b0082',  // dark purple robe
    4: '#8a2be2',  // purple robe
    5: '#f5deb3',  // skin highlight
    6: '#ffd700',  // gold staff/accents
    7: '#e6e6fa',  // lavender robe highlight
  },
  goblin: {
    0: null,
    1: '#1a1a2e',
    2: '#228b22',  // green skin
    3: '#8b4513',  // leather armor
    4: '#a0522d',  // leather highlight
    5: '#90ee90',  // skin highlight
    6: '#ff4500',  // eyes
    7: '#654321',  // dark leather
  },
};

// Swap palette to create character variants
function tintSprite(matrix, basePalette, tintMap) {
  // tintMap: {oldIndex: newColor}
  const newPalette = { ...basePalette };
  Object.entries(tintMap).forEach(([idx, color]) => {
    newPalette[parseInt(idx)] = color;
  });
  return renderSprite(matrix, newPalette, 4);
}

// Example: Create blue-armored variant from warrior
const blueWarrior = tintSprite(CHARACTER_16x16, PALETTES.warrior, {
  3: '#00008b',  // replace dark red with dark blue
  4: '#1e90ff',  // replace red with blue
});
```

---

## Animation Frames

Generate a sprite sheet from multiple frames for walking, attacking, etc.

```javascript
// Walk cycle: 4 frames (shift legs/arms slightly each frame)
const WALK_FRAMES = {
  // Frame 0: neutral stance
  frame0: [
    // ... same as CHARACTER_16x16 above
  ],
  // Frame 1: right foot forward
  frame1: [
    [0,0,0,0,1,1,1,1,1,1,1,1,0,0,0,0],
    [0,0,0,1,3,3,3,3,3,3,3,3,1,0,0,0],
    [0,0,1,3,2,2,2,2,2,2,2,2,3,1,0,0],
    [0,0,1,2,2,5,2,2,2,2,5,2,2,1,0,0],
    [0,0,1,2,2,2,2,2,2,2,2,2,2,1,0,0],
    [0,0,1,2,2,2,1,2,2,1,2,2,2,1,0,0],
    [0,0,0,1,1,1,1,1,1,1,1,1,1,0,0,0],
    [0,1,4,4,4,4,4,4,4,4,4,4,4,4,1,0],
    [1,4,4,4,4,4,4,4,4,4,4,4,4,4,4,1],
    [1,4,4,4,4,4,4,4,4,4,4,4,4,4,4,1],
    [0,1,4,4,4,4,4,4,4,4,4,4,4,4,1,0],
    [0,0,1,4,4,1,0,0,0,0,1,4,4,1,0,0],
    [0,0,0,4,4,1,0,0,0,0,1,4,4,0,0,0],  // right leg back
    [0,0,0,4,4,1,0,0,0,1,4,4,0,0,0,0],  // legs spread
    [0,0,0,4,4,0,0,0,0,1,4,4,0,0,0,0],
    [0,0,0,1,1,0,0,0,0,1,1,1,0,0,0,0],  // foot positions
  ],
  // Frame 2: neutral (same as frame0, creates smooth loop)
  frame2: null, // <- reuse frame0
  // Frame 3: left foot forward (mirror of frame1)
  frame3: null, // <- mirror frame1 horizontally
};

// Render sprite sheet (all frames side by side)
function renderSpriteSheet(frames, palette, scale = 4) {
  const frameCount = frames.length;
  const frameW = frames[0][0].length;
  const frameH = frames[0].length;

  const canvas = document.createElement('canvas');
  canvas.width = frameW * scale * frameCount;
  canvas.height = frameH * scale;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  frames.forEach((frame, i) => {
    const frameCanvas = renderSprite(frame, palette, scale);
    ctx.drawImage(frameCanvas, i * frameW * scale, 0);
  });

  return canvas;
}

// Mirror a frame horizontally (for left/right walk variants)
function mirrorFrame(matrix) {
  return matrix.map(row => [...row].reverse());
}
```

---

## Canvas Texture for Three.js

Use sprite canvas directly as a Three.js texture for game objects.

```javascript
const spriteCanvas = renderSprite(WARRIOR_SPRITE, PALETTES.warrior, 4);

const texture = new THREE.CanvasTexture(spriteCanvas);
texture.magFilter = THREE.NearestFilter; // Crisp pixels, no blur
texture.minFilter = THREE.NearestFilter;

const mat = new THREE.SpriteMaterial({ map: texture, transparent: true });
const sprite = new THREE.Sprite(mat);
sprite.scale.set(1, 1, 1);
scene.add(sprite);
```

`THREE.NearestFilter` is essential — without it, Three.js bilinearly interpolates the sprite and it looks blurry.

---

## Node.js Export (No Browser)

For server-side generation or build pipelines:

```javascript
// npm install canvas
import { createCanvas } from 'canvas';
import { writeFileSync } from 'fs';

function renderSpriteNode(matrix, palette, scale = 4) {
  const rows = matrix.length;
  const cols = matrix[0].length;
  const canvas = createCanvas(cols * scale, rows * scale);
  const ctx = canvas.getContext('2d');

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const idx = matrix[row][col];
      if (idx === 0 || !palette[idx]) continue;
      ctx.fillStyle = palette[idx];
      ctx.fillRect(col * scale, row * scale, scale, scale);
    }
  }

  return canvas;
}

// Export to file
const canvas = renderSpriteNode(WARRIOR_SPRITE, PALETTES.warrior, 8);
const buffer = canvas.toBuffer('image/png');
writeFileSync('public/assets/warrior-sprite.png', buffer);
console.log('Sprite exported: public/assets/warrior-sprite.png');
```

---

## Quick Reference: Common Sprite Sizes

| Size | Use case | Three.js scale |
|------|----------|---------------|
| 8x8 | Icons, tiles, simple enemies | 0.5 |
| 16x16 | Standard characters, items | 1.0 |
| 32x32 | Detailed characters, bosses | 2.0 |
| 64x64 | Large sprites, cutscene art | 4.0 |

Scale at 4px per sprite-pixel for rendering (e.g., 16x16 sprite -> 64x64 canvas). Use `THREE.NearestFilter` always.
