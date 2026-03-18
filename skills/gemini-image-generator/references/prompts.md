# Example Prompts for Gemini Image Generation

Categorized prompts that work well with Gemini's image generation models.

---

## Prompt Structure

Effective prompts follow this pattern:

```
[Subject] [Style] [Background] [Constraints]
```

**Key principles:**
- Be specific about what you want
- Specify background type for easier post-processing
- Include negative constraints ("no text", "no labels")
- Describe composition ("centered", "full body")

---

## Game Art

### Character Sprites

```
Full body character sprite, 2D game art style,
solid dark gray background, pixel-perfect edges,
centered in frame, facing forward,
character only, no text, no UI elements
```

### Enemy Designs (Slay the Spire Style)

```
Full body fantasy character art, Slay the Spire card game style,
solid dark gray background color only, absolutely no background objects,
golden glowing outline around character, clean digital hand-painted style,
heavy ink outlines, character art only, no text, no labels
```

### Item Icons

```
Game item icon, flat design style,
transparent background, centered composition,
clean vector edges, single object only,
no text, no numbers, no UI frame
```

### Weapon Art

```
Fantasy sword weapon art, painterly game style,
solid black background, dramatic lighting,
detailed metal textures, centered composition,
weapon only, no hands, no text
```

---

## Character Art

### Portrait Style

```
Character portrait, digital painting style,
soft gradient background, dramatic lighting,
expressive face, high detail,
bust shot, centered, no text
```

### Full Body (Transparent Background Ready)

```
Full body character illustration, anime art style,
solid uniform gray background (#3a3a3a),
dynamic pose, clean line art with cel shading,
head to feet visible, centered in frame,
character only, no floor, no shadows on ground
```

### Action Pose

```
Dynamic action character art, comic book style,
solid color background, motion lines optional,
exaggerated perspective, high energy pose,
full body visible, centered, no text or logos
```

---

## Product Photography

### Clean Product Shot

```
Professional product photography, pure white background,
soft studio lighting, sharp focus on product details,
commercial quality, centered composition,
product only, no props, no text overlays
```

### Lifestyle Context

```
Product photography with lifestyle context,
minimalist background, natural lighting,
product in use scenario, clean aesthetic,
high resolution, commercial quality
```

### Tech Product

```
Technology product photography, gradient dark background,
dramatic rim lighting, reflective surface hints,
centered composition, premium aesthetic,
product only, no hands, no text
```

---

## Pixel Art

### 16-bit Style

```
16-bit pixel art sprite, retro SNES era style,
transparent background, centered in frame,
clean pixel edges, limited color palette (16 colors),
no anti-aliasing, crisp pixels
```

### 8-bit Style

```
8-bit pixel art character, NES era aesthetic,
solid color background, 4-color palette,
blocky pixels, small sprite size,
centered, no gradients
```

### Isometric

```
Isometric pixel art building, simulation game style,
transparent background, 32x32 grid aligned,
clean isometric perspective, detailed textures,
single building only, no ground shadows
```

---

## Icons and UI

### App Icon

```
Mobile app icon, modern flat design,
gradient background, simple geometric shape,
clean edges, vibrant colors,
centered composition, no text
```

### Emoji Style

```
Emoji style icon, rounded friendly shapes,
solid color or simple gradient background,
expressive and readable at small sizes,
single element, centered, no text
```

### System Icon

```
System UI icon, minimal line style,
transparent background, consistent stroke width,
simple geometric shapes, monochrome,
centered, no fills
```

---

## Abstract and Patterns

### Seamless Texture

```
Seamless tileable texture pattern,
uniform lighting, no visible seams,
high resolution, clean repeating pattern,
organic/geometric elements
```

### Abstract Background

```
Abstract digital art background,
flowing organic shapes, gradient colors,
high resolution, no focal point,
suitable for wallpaper or banner
```

---

## Tips for Better Results

### For Transparent Backgrounds

Use these phrases:
- "solid dark gray background"
- "solid uniform gray background (#3a3a3a)"
- "no background elements or scenery"
- "no ground shadows"

### For Clean Edges

Use these phrases:
- "clean edges"
- "no anti-aliasing on edges"
- "sharp outlines"
- "heavy ink outlines"

### To Avoid Unwanted Elements

Always include:
- "no text"
- "no labels"
- "no watermarks"
- "no UI elements"
- "character/object only"

### For Consistent Style

Reference specific games or artists:
- "Slay the Spire card game style"
- "Studio Ghibli aesthetic"
- "Borderlands cel-shaded style"
- "Hollow Knight art style"

---

## Model-Specific Tips

### gemini-2.5-flash-image

Best for:
- Rapid iterations
- Testing prompt variations
- Batch generation
- Simpler compositions

Prompt adjustments:
- Keep prompts shorter
- Focus on key elements
- Accept more variation

### gemini-3-pro-image-preview

Best for:
- Final quality output
- Complex compositions
- Text in images
- Detailed textures

Prompt adjustments:
- Can handle longer, detailed prompts
- Request specific details
- Good for typography
