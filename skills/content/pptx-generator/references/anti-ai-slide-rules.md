# Anti-AI Slide Rules

Patterns that make a presentation look obviously AI-generated. The QA subagent checks for ALL of these. The generation phase must actively avoid them.

## Why This Matters

AI-generated slides have a distinctive "template pack" aesthetic that audiences recognize instantly. It undermines credibility. The goal is slides that look like a competent human made them with intention, not slides that look like they came from an AI tool.

---

## The Rules

### 1. No Accent Lines Under Titles

**What it is**: A thin decorative line (often colored) placed directly below the slide title.

**Why it screams AI**: Every AI slide generator and cheap template pack does this. It's the single most recognizable AI-slide tell. Real designers either skip it entirely or use more sophisticated visual hierarchy.

**Rule**: NEVER add a decorative line, rule, or separator below a title. Use font size, weight, and spacing to create hierarchy instead.

**Detection**: Any `Shape` of type `LINE` or thin `RECTANGLE` (height < 5pt) positioned within 20pt below a title text box.

### 2. No Gradient Backgrounds on Every Slide

**What it is**: Gradient fills (linear, radial) used as slide backgrounds across all or most slides.

**Why it screams AI**: Overuse of gradients is a hallmark of template-generated content. Real presentations use solid backgrounds with gradients reserved for the title slide at most.

**Rule**: Solid color backgrounds only. A gradient is permitted on the title slide ONLY, and only if the user explicitly requests it.

**Detection**: More than 1 slide with a gradient background fill.

### 3. No Stock Photo Placeholders

**What it is**: Empty rectangles with "Insert Image Here" text, or generic placeholder graphics.

**Why it screams AI**: Real presentations either have actual images or don't have image slots at all.

**Rule**: Either embed a real image provided by the user, or leave the space as clean white space. Never create placeholder boxes.

**Detection**: Any shape with placeholder-style text ("Insert image", "Your photo here", etc.) or empty picture placeholders.

### 4. Alternate Layout Types

**What it is**: Using the exact same layout (title + bullets) for every content slide.

**Why it screams AI**: AI generators default to repeating one layout. Real presentations have visual rhythm: content slides, full-bleed images, two-column comparisons, quote slides, etc.

**Rule**: Use at least 2-3 different layout types across the deck. For a 10+ slide deck, use at least 3 distinct layouts.

**Detection**: More than 3 consecutive slides with identical layout structure (same number of text boxes in same positions).

### 5. No Shadows on Everything

**What it is**: Drop shadows applied to every text box, shape, and image.

**Why it screams AI**: Universal shadow application is a "make it look designed" shortcut that achieves the opposite. Real designers use shadows purposefully or not at all.

**Rule**: No shadows by default. If shadows are used, apply them to ONE element type only (e.g., image frames) and keep them subtle (offset 2-3pt, 40% opacity, no blur > 4pt).

**Detection**: More than 2 elements per slide with shadow effects.

### 6. No Rounded Rectangle Everything

**What it is**: Every shape on the slide is a rounded rectangle (bullet containers, image frames, accent shapes).

**Why it screams AI**: Rounded rectangles are the universal "safe" shape. Using them for everything creates a toy-like aesthetic.

**Rule**: Use shapes purposefully. If containers are needed, use rectangles or no visible border. Rounded rectangles only when they serve a specific design intent.

**Detection**: More than 2 rounded rectangle shapes per slide that aren't content containers.

### 7. No Excessive Animations

**What it is**: Fly-in, fade-in, bounce, or appear animations on every bullet point and element.

**Why it screams AI**: Template-pack hallmark. Animations that don't serve a purpose distract from content.

**Rule**: No animations by default. If the user explicitly requests animations, use only "Appear" (instant) or "Fade" (0.3s) on bullet points. Never animate titles or images.

**Detection**: Any animation XML in the slide (python-pptx doesn't easily add animations, so this is mainly for edited templates).

### 8. No Word Art or Gradient Text

**What it is**: Text with gradient fills, outlines, glow effects, or other WordArt styling.

**Why it screams AI**: Dated aesthetic from the 2000s. Modern presentations use solid text colors.

**Rule**: All text uses solid colors from the palette. No gradient fills on text, no text outlines, no glow or reflection effects.

**Detection**: Text runs with non-solid color fills or effect XML.

### 9. Max 3 Colors Per Slide

**What it is**: Using 4+ different colors on a single slide.

**Why it screams AI**: AI generators often apply the full palette to every slide, creating a rainbow effect.

**Rule**: Each slide uses at most 3 colors from the palette: background, text, and one accent. The accent color should appear on no more than 1-2 elements per slide.

**Detection**: Count distinct non-background, non-text colors on a slide. More than 1 accent color = violation.

### 10. No Decorative Clip Art Icons

**What it is**: Generic geometric icons (lightbulb for "idea", gear for "process", people silhouettes for "team") placed next to bullet points.

**Why it screams AI**: These icons are the universal language of template-generated content. They add no information and signal "this was auto-generated."

**Rule**: No icons unless the user provides specific assets. If visual elements are needed, use simple shapes (colored squares, lines) as accent elements, not representational icons.

**Detection**: Small image or shape elements positioned consistently next to text (icon-like positioning pattern).

---

## Summary Checklist (For Quick Reference)

- [ ] No decorative lines under titles
- [ ] Solid backgrounds (gradient on title slide only, if at all)
- [ ] No placeholder image boxes
- [ ] At least 2-3 distinct layout types
- [ ] No universal shadows
- [ ] No rounded-rectangle-everything
- [ ] No animations (unless explicitly requested, then minimal only)
- [ ] Solid text colors only (no gradient/glow/outline on text)
- [ ] Max 3 colors per slide
- [ ] No decorative clip art icons
