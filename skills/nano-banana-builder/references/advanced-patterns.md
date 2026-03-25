# Advanced Patterns for Nano Banana Builder

Complete implementations for production-ready Nano Banana web applications.

## Server Actions

### Image Generation with Model Selection

```typescript
// app/actions/generate.ts
'use server'

import { google } from '@ai-sdk/google'
import { generateText } from 'ai'
import { put } from '@vercel/blob'

interface GenerateConfig {
  prompt: string
  model: 'nano' | 'pro'
  aspectRatio?: '1:1' | '2:3' | '3:2' | '3:4' | '4:3' | '4:5' | '5:4' | '9:16' | '16:9' | '21:9'
  storeImage?: boolean
}

export async function generateImage(config: GenerateConfig) {
  const { prompt, model, aspectRatio = '1:1', storeImage = true } = config

  const modelName = model === 'pro'
    ? 'gemini-3-pro-image-preview'
    : 'gemini-2.5-flash-image'

  const result = await generateText({
    model: google(modelName),
    prompt,
    providerOptions: {
      google: {
        responseModalities: ['IMAGE'],
        imageConfig: {
          aspectRatio,
          ...(model === 'pro' && { imageSize: '2K' })
        }
      }
    }
  })

  const imageFile = result.files[0]

  if (storeImage && imageFile?.base64) {
    const buffer = Buffer.from(imageFile.base64, 'base64')
    const blob = await put(`generated/${Date.now()}.png`, buffer, {
      access: 'public'
    })
    return { url: blob.url, base64: imageFile.base64 }
  }

  return { url: `data:${imageFile.mediaType};base64,${imageFile.base64}` }
}
```

### Iterative Editing (Multi-Turn)

```typescript
// app/actions/edit.ts
'use server'

import { google } from '@ai-sdk/google'
import { generateText } from 'ai'

interface EditConfig {
  imageBase64: string
  editPrompt: string
  model: 'nano' | 'pro'
  history?: Array<{role: string; content: any}>
}

export async function editImage(config: EditConfig) {
  const { imageBase64, editPrompt, model, history = [] } = config

  const modelName = model === 'pro'
    ? 'gemini-3-pro-image-preview'
    : 'gemini-2.5-flash-image'

  // Build conversation with image as first message
  const contents = [
    { role: 'user', content: [
      { type: 'image', image: imageBase64 },
      { type: 'text', text: editPrompt }
    ]}
  ]

  const result = await generateText({
    model: google(modelName),
    messages: [...history, ...contents],
    providerOptions: {
      google: {
        responseModalities: ['IMAGE']
      }
    }
  })

  return {
    url: `data:${result.files[0].mediaType};base64,${result.files[0].base64}`,
    newHistory: [...history, ...contents, {
      role: 'assistant',
      content: result.files[0]
    }]
  }
}
```

### API Route with Streaming

```typescript
// app/api/generate/route.ts
import { google } from '@ai-sdk/google'
import { streamText } from 'ai'

export const maxDuration = 30

export async function POST(req: Request) {
  const { prompt, model = 'nano' } = await req.json()

  const result = streamText({
    model: google(model === 'pro' ? 'gemini-3-pro-image-preview' : 'gemini-2.5-flash-image'),
    prompt,
    providerOptions: {
      google: {
        responseModalities: ['IMAGE', 'TEXT']
      }
    }
  })

  return result.toDataStreamResponse()
}
```

### Reference Image for Style Matching

```typescript
// app/actions/generate-with-reference.ts
'use server'

import { google } from '@ai-sdk/google'
import { generateText } from 'ai'
interface StyleTransferConfig {
  prompt: string
  referenceImageBase64: string
  model: 'nano' | 'pro'
  aspectRatio?: '1:1' | '16:9' | '9:16' | '3:2' | '2:3' | '4:3' | '3:4' | '4:5' | '5:4' | '21:9'
}

export async function generateWithReference(config: StyleTransferConfig) {
  const { prompt, referenceImageBase64, model, aspectRatio = '1:1' } = config

  const modelName = model === 'pro'
    ? 'gemini-3-pro-image-preview'
    : 'gemini-2.5-flash-image'

  const result = await generateText({
    model: google(modelName),
    messages: [{
      role: 'user',
      content: [
        {
          type: 'image',
          image: referenceImageBase64,
          mimeType: 'image/png'
        },
        {
          type: 'text',
          text: `Use this image as a style reference. ${prompt}`
        }
      ]
    }],
    providerOptions: {
      google: {
        responseModalities: ['IMAGE'],
        imageConfig: {
          aspectRatio,
          ...(model === 'pro' && { imageSize: '2K' })
        }
      }
    }
  })

  return result.files[0]
}
```

---

## Image Post-Processing

Production image generation almost always requires post-processing: cropping to exact dimensions, converting formats, removing artifacts, or making backgrounds transparent. These patterns use [sharp](https://sharp.pixelplumbing.com/) for TypeScript and [Pillow](https://pillow.readthedocs.io/) for Python.

**Install**: `npm install sharp` (TypeScript) or `pip install pillow` (Python)

### Save Originals Before Processing

Always save the raw Gemini output before any destructive processing. Re-generating costs money and API quota — re-cropping a saved original is free.

```typescript
// lib/post-process.ts
import sharp from 'sharp'
import { put } from '@vercel/blob'

export async function saveOriginalAndProcess(
  imageBase64: string,
  id: string,
  processFn: (buffer: Buffer) => Promise<Buffer>
) {
  const rawBuffer = Buffer.from(imageBase64, 'base64')

  // Save original — this is your insurance policy
  const original = await put(
    `originals/${id}.png`,
    await sharp(rawBuffer).png().toBuffer(),
    { access: 'public' }
  )

  // Process and save the working copy
  const processed = await processFn(rawBuffer)
  const result = await put(
    `processed/${id}.png`,
    processed,
    { access: 'public' }
  )

  return { originalUrl: original.url, processedUrl: result.url }
}
```

```python
# save_original.py — batch script pattern
from pathlib import Path
from PIL import Image

def save_original(img: Image.Image, item_id: str, originals_dir: Path) -> Path:
    """Save raw Gemini output BEFORE any cropping or processing."""
    originals_dir.mkdir(parents=True, exist_ok=True)
    original_path = originals_dir / f"{item_id}_original.png"

    img.save(original_path, "PNG")

    return original_path
```

### Smart Cropping

Center crop works for most cases, but cuts heads/feet off characters. Top-biased cropping keeps more of the top (heads) and crops more from the bottom.

```typescript
// lib/crop.ts
import sharp from 'sharp'

interface CropConfig {
  targetWidth: number
  targetHeight: number
  bias?: 'center' | 'top' | 'bottom'
  /** Fraction of excess removed from top. 0.0 = anchor top (crop bottom only), 0.35 = keep more top, 0.5 = center, 1.0 = anchor bottom (crop top only) */
  topRatio?: number
}

export async function smartCrop(
  buffer: Buffer,
  config: CropConfig
): Promise<Buffer> {
  const { targetWidth, targetHeight, bias = 'center', topRatio } = config
  const metadata = await sharp(buffer).metadata()
  const srcW = metadata.width!
  const srcH = metadata.height!

  const targetRatio = targetWidth / targetHeight
  const srcRatio = srcW / srcH

  let left = 0, top = 0, cropW = srcW, cropH = srcH

  if (srcRatio > targetRatio) {
    // Source is wider — crop sides (center is fine)
    cropW = Math.round(srcH * targetRatio)
    left = Math.round((srcW - cropW) / 2)
  } else if (srcRatio < targetRatio) {
    // Source is taller — crop top/bottom with bias
    cropH = Math.round(srcW / targetRatio)
    const totalCrop = srcH - cropH

    const ratio = topRatio ?? (bias === 'top' ? 0.35 : bias === 'bottom' ? 0.65 : 0.5)
    top = Math.round(totalCrop * ratio)
  }

  return sharp(buffer)
    .extract({ left, top, width: cropW, height: cropH })
    .resize(targetWidth, targetHeight, { fit: 'fill' })
    .toBuffer()
}
```

```python
# crop.py — PIL equivalent
from PIL import Image

def smart_crop(
    img: Image.Image,
    target_width: int,
    target_height: int,
    top_ratio: float = 0.5,
) -> Image.Image:
    """
    Crop to target dimensions with configurable vertical bias.

    Args:
        top_ratio: Fraction of excess removed from top.
                   0.0 = anchor top (crop bottom only), 0.35 = keep more top (good for characters),
                   0.5 = center, 1.0 = anchor bottom (crop top only)
    """
    width, height = img.size
    target_ratio = target_width / target_height
    current_ratio = width / height

    if current_ratio > target_ratio:
        # Too wide — center crop horizontally
        new_width = int(height * target_ratio)
        left = (width - new_width) // 2
        img = img.crop((left, 0, left + new_width, height))
    elif current_ratio < target_ratio:
        # Too tall — biased crop vertically
        new_height = int(width / target_ratio)
        total_crop = height - new_height
        top_crop = int(total_crop * top_ratio)
        img = img.crop((0, top_crop, width, top_crop + new_height))

    img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

    return img
```

### Background Removal / Transparency

For sprites, stickers, and overlays — remove a solid background color and make it transparent.

```typescript
// lib/background-removal.ts
import sharp from 'sharp'

interface RemoveBackgroundConfig {
  /** Target background color to remove [R, G, B] */
  bgColor: [number, number, number]
  /** How much color variance to allow (0-255). Default 30 */
  tolerance?: number
}

export async function removeBackground(
  buffer: Buffer,
  config: RemoveBackgroundConfig
): Promise<Buffer> {
  const { bgColor, tolerance = 30 } = config
  const [bgR, bgG, bgB] = bgColor

  const image = sharp(buffer).ensureAlpha()
  const { data, info } = await image.raw().toBuffer({ resolveWithObject: true })

  // Process pixels: make matching background transparent
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i], g = data[i + 1], b = data[i + 2]
    if (
      Math.abs(r - bgR) <= tolerance &&
      Math.abs(g - bgG) <= tolerance &&
      Math.abs(b - bgB) <= tolerance
    ) {
      data[i + 3] = 0 // Set alpha to transparent
    }
  }

  return sharp(data, {
    raw: { width: info.width, height: info.height, channels: 4 }
  }).png().toBuffer()
}
```

```python
# background_removal.py — PIL equivalent
from PIL import Image

def remove_background(
    img: Image.Image,
    bg_color: tuple[int, int, int] = (58, 58, 58),
    tolerance: int = 30,
) -> Image.Image:
    """Make pixels matching bg_color transparent."""
    img = img.convert("RGBA")
    pixels = img.load()
    width, height = img.size

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if (
                abs(r - bg_color[0]) <= tolerance
                and abs(g - bg_color[1]) <= tolerance
                and abs(b - bg_color[2]) <= tolerance
            ):
                pixels[x, y] = (r, g, b, 0)

    return img
```

**Common background colors for Gemini generation**:
- `[58, 58, 58]` (#3a3a3a) — dark gray (use with "solid dark gray background" in prompt)
- `[255, 255, 255]` — white (use with "solid white background" in prompt)
- `[0, 0, 0]` — black (use with "solid black background" in prompt)

### Watermark Removal

Gemini may add subtle watermarks in image corners. Remove them by detecting bright/anomalous pixels in corner regions.

```typescript
// lib/watermark-removal.ts
import sharp from 'sharp'

export async function removeCornerWatermarks(
  buffer: Buffer,
  /** Pixel margin from each corner to check. Default 40 */
  margin = 40,
  /** Brightness threshold (0-255) above which pixels are cleared. Default 180 */
  brightnessThreshold = 180,
  /** Color to replace watermark pixels with [R,G,B] */
  replaceColor: [number, number, number] = [58, 58, 58]
): Promise<Buffer> {
  const image = sharp(buffer).ensureAlpha()
  const { data, info } = await image.raw().toBuffer({ resolveWithObject: true })
  const { width, height } = info

  const corners = [
    [0, 0, margin, margin],                              // top-left
    [width - margin, 0, width, margin],                   // top-right
    [0, height - margin, margin, height],                 // bottom-left
    [width - margin, height - margin, width, height],     // bottom-right
  ]

  for (const [x1, y1, x2, y2] of corners) {
    for (let y = y1; y < y2; y++) {
      for (let x = x1; x < x2; x++) {
        const i = (y * width + x) * 4
        const brightness = (data[i] + data[i + 1] + data[i + 2]) / 3
        if (brightness > brightnessThreshold) {
          data[i] = replaceColor[0]
          data[i + 1] = replaceColor[1]
          data[i + 2] = replaceColor[2]
        }
      }
    }
  }

  return sharp(data, {
    raw: { width, height, channels: 4 }
  }).png().toBuffer()
}
```

### Full Post-Processing Pipeline

Combine the above into a single pipeline. Order matters: watermark removal → background removal → crop → format conversion.

```typescript
// lib/process-pipeline.ts
import { removeCornerWatermarks } from './watermark-removal'
import { removeBackground } from './background-removal'
import { smartCrop } from './crop'
import sharp from 'sharp'

interface ProcessConfig {
  /** Target dimensions after crop */
  targetWidth: number
  targetHeight: number
  /** Crop bias: 'top' for characters, 'center' for landscapes */
  cropBias?: 'center' | 'top' | 'bottom'
  /** Remove background color (null = skip) */
  bgRemoval?: { color: [number, number, number]; tolerance?: number } | null
  /** Remove corner watermarks */
  removeWatermarks?: boolean
  /** Output format */
  format?: 'png' | 'jpeg' | 'webp'
  /** JPEG/WebP quality (1-100) */
  quality?: number
}

export async function processImage(
  imageBase64: string,
  config: ProcessConfig
): Promise<Buffer> {
  let buffer = Buffer.from(imageBase64, 'base64')

  // Step 1: Watermark removal (before background removal)
  if (config.removeWatermarks) {
    buffer = await removeCornerWatermarks(buffer)
  }

  // Step 2: Background removal
  if (config.bgRemoval) {
    buffer = await removeBackground(buffer, {
      bgColor: config.bgRemoval.color,
      tolerance: config.bgRemoval.tolerance
    })
  }

  // Step 3: Smart crop to target dimensions
  buffer = await smartCrop(buffer, {
    targetWidth: config.targetWidth,
    targetHeight: config.targetHeight,
    bias: config.cropBias
  })

  // Step 4: Format conversion
  const fmt = config.format ?? (config.bgRemoval ? 'png' : 'jpeg')
  switch (fmt) {
    case 'jpeg':
      return sharp(buffer).jpeg({ quality: config.quality ?? 90 }).toBuffer()
    case 'webp':
      return sharp(buffer).webp({ quality: config.quality ?? 85 }).toBuffer()
    default:
      return sharp(buffer).png().toBuffer()
  }
}
```

```python
# process_pipeline.py — Python CLI equivalent
from pathlib import Path
from PIL import Image

def process_image(
    img: Image.Image,
    target_width: int,
    target_height: int,
    crop_bias: float = 0.5,
    bg_color: tuple[int, int, int] | None = None,
    bg_tolerance: int = 30,
    remove_watermarks: bool = False,
    watermark_margin: int = 40,
    output_format: str = "png",
    jpeg_quality: int = 90,
) -> Image.Image:
    """
    Full pipeline: watermark removal → background removal → smart crop → format conversion.

    Args:
        crop_bias: Fraction of excess removed from top.
                   0.0=anchor top, 0.35=keep top (characters), 0.5=center, 1.0=anchor bottom
        bg_color: Background color to make transparent (None=skip)
        remove_watermarks: Clear bright pixels in corner regions
        output_format: "png" (with alpha) or "jpeg" (no alpha, white fill)
    """
    # Watermark removal (before background removal)
    if remove_watermarks:
        img = img.convert("RGBA")
        pixels = img.load()
        w, h = img.size
        m = watermark_margin
        corners = [(0, 0, m, m), (w - m, 0, w, m), (0, h - m, m, h), (w - m, h - m, w, h)]
        for x1, y1, x2, y2 in corners:
            for y in range(y1, y2):
                for x in range(x1, x2):
                    if 0 <= x < w and 0 <= y < h:
                        r, g, b, a = pixels[x, y]
                        if (r + g + b) / 3 > 180:
                            pixels[x, y] = (bg_color[0] if bg_color else 58,
                                            bg_color[1] if bg_color else 58,
                                            bg_color[2] if bg_color else 58, 255)

    # Background removal (before crop to preserve edge detection)
    if bg_color is not None:
        img = img.convert("RGBA")
        pixels = img.load()
        w, h = img.size
        for y in range(h):
            for x in range(w):
                r, g, b, a = pixels[x, y]
                if (
                    abs(r - bg_color[0]) <= bg_tolerance
                    and abs(g - bg_color[1]) <= bg_tolerance
                    and abs(b - bg_color[2]) <= bg_tolerance
                ):
                    pixels[x, y] = (r, g, b, 0)

    # Smart crop
    width, height = img.size
    target_ratio = target_width / target_height
    current_ratio = width / height

    if current_ratio > target_ratio:
        new_width = int(height * target_ratio)
        left = (width - new_width) // 2
        img = img.crop((left, 0, left + new_width, height))
    elif current_ratio < target_ratio:
        new_height = int(width / target_ratio)
        total_crop = height - new_height
        top_crop = int(total_crop * crop_bias)
        img = img.crop((0, top_crop, width, top_crop + new_height))

    img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

    # Format preparation
    if output_format == "jpeg" and img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif output_format != "png" and img.mode != "RGB":
        img = img.convert("RGB")

    return img
```

---

## Client-Side Components

### Complete Image Generator Component

```typescript
// app/components/ImageGenerator.tsx
'use client'

import { useState } from 'react'
import { useChat } from '@ai-sdk/react'

type Model = 'nano' | 'pro'

export function ImageGenerator() {
  const [selectedModel, setSelectedModel] = useState<Model>('nano')
  const [prompt, setPrompt] = useState('')

  const { messages, append, isLoading } = useChat({
    api: '/api/generate',
    body: { model: selectedModel }
  })

  const handleGenerate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!prompt.trim()) return

    append({
      role: 'user',
      content: prompt,
      // @ts-ignore - custom body property
      model: selectedModel
    })
    setPrompt('')
  }

  return (
    <div className="max-w-2xl mx-auto p-6">
      {/* Model Selector */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setSelectedModel('nano')}
          className={`px-4 py-2 rounded ${selectedModel === 'nano'
            ? 'bg-blue-500 text-white'
            : 'bg-gray-200'}`}
        >
          Nano (Fast)
        </button>
        <button
          onClick={() => setSelectedModel('pro')}
          className={`px-4 py-2 rounded ${selectedModel === 'pro'
            ? 'bg-blue-500 text-white'
            : 'bg-gray-200'}`}
        >
          Pro (Quality)
        </button>
      </div>

      {/* Generated Images Gallery */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        {messages.map((m, i) =>
          m.parts?.map((part, j) =>
            part.type === 'image' && (
              <img
                key={`${i}-${j}`}
                src={part.url}
                alt="Generated"
                className="w-full rounded-lg shadow"
              />
            )
          )
        )}
      </div>

      {/* Prompt Input */}
      <form onSubmit={handleGenerate} className="flex gap-2">
        <input
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe your image..."
          className="flex-1 px-4 py-2 border rounded"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading || !prompt.trim()}
          className="px-6 py-2 bg-purple-500 text-white rounded disabled:opacity-50"
        >
          {isLoading ? 'Generating...' : 'Generate'}
        </button>
      </form>
    </div>
  )
}
```

### Iterative Editor Component

```typescript
// app/components/IterativeEditor.tsx
'use client'

import { useState } from 'react'

interface EditHistory {
  role: string
  content: any
}

export function IterativeEditor() {
  const [currentImage, setCurrentImage] = useState<string>('')
  const [editPrompt, setEditPrompt] = useState('')
  const [history, setHistory] = useState<EditHistory[]>([])
  const [isLoading, setIsLoading] = useState(false)

  const handleEdit = async () => {
    if (!editPrompt.trim() || !currentImage) return

    setIsLoading(true)

    const response = await fetch('/api/edit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        imageBase64: currentImage.split(',')[1],
        editPrompt,
        history
      })
    })

    const data = await response.json()
    setCurrentImage(data.url)
    setHistory(data.newHistory)
    setEditPrompt('')
    setIsLoading(false)
  }

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      {/* Image Display */}
      <div className="flex-1">
        {currentImage ? (
          <img src={currentImage} alt="Current" className="w-full rounded" />
        ) : (
          <div className="aspect-square bg-gray-100 rounded flex items-center justify-center">
            Upload or generate an image to start
          </div>
        )}
      </div>

      {/* Edit Controls */}
      <div className="flex-1">
        <textarea
          value={editPrompt}
          onChange={(e) => setEditPrompt(e.target.value)}
          placeholder="Describe your edit..."
          className="w-full h-32 p-3 border rounded mb-4"
        />

        <button
          onClick={handleEdit}
          disabled={isLoading || !editPrompt.trim()}
          className="w-full py-2 bg-green-500 text-white rounded disabled:opacity-50"
        >
          {isLoading ? 'Editing...' : 'Apply Edit'}
        </button>

        {/* History */}
        <div className="mt-4">
          <h3 className="font-bold mb-2">Edit History</h3>
          {history.slice(-5).map((h, i) => (
            <div key={i} className="text-sm text-gray-600 py-1">
              {h.role}: {typeof h.content === 'string'
                ? h.content
                : JSON.stringify(h.content).substring(0, 50)}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
```

---

## Advanced Patterns

### Multi-Image Composition

```typescript
// Combine multiple images into one generation
export async function compositeImages(
  images: string[],
  prompt: string
) {
  const imageParts = images.map(img => ({
    inlineData: {
      mimeType: 'image/png',
      data: img.split(',')[1]
    }
  }))

  const result = await generateText({
    model: google('gemini-3-pro-image-preview'),
    messages: [{
      role: 'user',
      content: [...imageParts, { text: prompt }]
    }],
    providerOptions: {
      google: { responseModalities: ['IMAGE'] }
    }
  })

  return result.files[0]
}
```

### Batch Generation with Skip-Existing, Variants, and Rate Control

```typescript
// app/actions/batch.ts
import { put, list } from '@vercel/blob'

interface BatchConfig {
  prompts: Array<{ id: string; prompt: string }>
  model: 'nano' | 'pro'
  /** Number of variants per prompt (1-5). Default 1 */
  variants?: number
  /** Delay between API calls in ms. Default 2000 */
  delayMs?: number
  /** Skip prompts that already have generated images */
  skipExisting?: boolean
  aspectRatio?: string
  onProgress?: (current: number, total: number, id: string) => void
}

export async function generateBatch(config: BatchConfig) {
  const {
    prompts,
    model,
    variants = 1,
    delayMs = 2000,
    skipExisting = true,
    aspectRatio = '1:1',
    onProgress
  } = config

  // Check existing images if skip mode enabled
  let existingIds = new Set<string>()
  if (skipExisting) {
    const blobs = await list({ prefix: 'generated/' })
    existingIds = new Set(
      blobs.blobs.map(b => b.pathname.split('/').pop()?.split('_v')[0] ?? '')
    )
  }

  const results = []
  let generated = 0
  let skipped = 0
  const total = prompts.length * variants

  for (const { id, prompt } of prompts) {
    for (let v = 1; v <= variants; v++) {
      const variantId = variants > 1 ? `${id}_v${v}` : id

      // Skip if already exists (single-variant mode only; multi-variant re-generates all)
      if (skipExisting && existingIds.has(id) && variants === 1) {
        skipped++
        onProgress?.(generated + skipped, total, `${id} (skipped)`)
        continue
      }

      const result = await generateImage({
        prompt,
        model,
        aspectRatio,
        storeImage: true
      })
      results.push({ id: variantId, ...result })
      generated++
      onProgress?.(generated + skipped, total, variantId)

      // Rate limit delay between calls
      if (delayMs > 0) {
        await new Promise(r => setTimeout(r, delayMs))
      }
    }
  }

  return { results, generated, skipped, total }
}
```

```python
# batch_generate.py — Python CLI equivalent
import time
from pathlib import Path
from google import genai
from google.genai import types
from PIL import Image
import io

def batch_generate(
    items: list[dict],
    output_dir: Path,
    originals_dir: Path | None = None,
    model: str = "gemini-2.5-flash-image",
    aspect_ratio: str = "16:9",
    variants: int = 1,
    delay: float = 2.0,
    skip_existing: bool = True,
    output_format: str = "png",
    jpeg_quality: int = 90,
) -> dict:
    """
    Batch generate images with skip-existing, variants, and rate control.

    Args:
        items: List of dicts with 'id' and 'prompt' keys
        output_dir: Where to save processed images
        originals_dir: Where to save raw Gemini output (None=skip)
        variants: Number of variants per item (1-5)
        delay: Seconds between API calls
        skip_existing: Skip items that already have output files
    """
    client = genai.Client()
    output_dir.mkdir(parents=True, exist_ok=True)
    if originals_dir:
        originals_dir.mkdir(parents=True, exist_ok=True)

    generated = 0
    skipped = 0
    failed = 0

    for item in items:
        item_id = item["id"]
        prompt = item["prompt"]

        for v in range(1, variants + 1):
            suffix = f"_v{v}" if variants > 1 else ""
            ext = "jpg" if output_format == "jpeg" else output_format
            out_path = output_dir / f"{item_id}{suffix}.{ext}"

            if skip_existing and out_path.exists():
                skipped += 1
                print(f"Skipping {item_id}{suffix} — already exists")
                continue

            try:
                response = client.models.generate_content(
                    model=model,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                        image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
                    ),
                )

                for part in response.candidates[0].content.parts:
                    if part.inline_data is not None:
                        img = Image.open(io.BytesIO(part.inline_data.data))

                        # Save original before any processing
                        if originals_dir:
                            orig = originals_dir / f"{item_id}{suffix}_original.png"
                            img.save(orig, "PNG")

                        # Save in requested format
                        if output_format == "jpeg":
                            if img.mode != "RGB":
                                img = img.convert("RGB")
                            img.save(out_path, "JPEG", quality=jpeg_quality)
                        else:
                            img.save(out_path, "PNG", optimize=True)

                        generated += 1
                        print(f"Generated {item_id}{suffix} ({img.size[0]}x{img.size[1]})")
                        break
                else:
                    print(f"No image in response for {item_id}{suffix}")
                    failed += 1

            except Exception as e:
                print(f"Error generating {item_id}{suffix}: {e}")
                failed += 1

            if delay > 0:
                time.sleep(delay)

    return {"generated": generated, "skipped": skipped, "failed": failed}
```

### Progressive Loading

```typescript
// Generate low-res first, then high-res
export async function generateProgressive(prompt: string) {
  // Fast preview
  const preview = await generateImage({
    prompt,
    model: 'nano',
    storeImage: false
  })

  // High-res final
  const final = await generateImage({
    prompt,
    model: 'pro',
    storeImage: true
  })

  return { preview, final }
}
```

---

## Usage Patterns

### Gallery with Infinite Scroll

```typescript
// app/components/ImageGallery.tsx
'use client'

import { useState, useEffect } from 'react'
import { useChat } from '@ai-sdk/react'

export function ImageGallery() {
  const { messages, append, isLoading } = useChat({
    api: '/api/generate'
  })

  const images = messages.flatMap(m =>
    m.parts?.filter(p => p.type === 'image') ?? []
  )

  return (
    <div className="grid grid-cols-3 gap-4">
      {images.map((part, i) => (
        <div key={i} className="aspect-square">
          <img src={part.url} alt="" className="w-full h-full object-cover rounded" />
        </div>
      ))}
    </div>
  )
}
```

### Error Handling with Retry

```typescript
// app/actions/generate.ts
export async function generateImageWithRetry(
  config: GenerateConfig,
  maxRetries = 3
) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await generateImage(config)
    } catch (error) {
      if (i === maxRetries - 1) throw error
      await new Promise(r => setTimeout(r, 1000 * (i + 1)))
    }
  }
}
```
