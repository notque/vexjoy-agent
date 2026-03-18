# PPTX Generator Design System

Color palettes, typography rules, and spacing guidelines for presentation generation.

## Color Palettes (8 Curated)

Each palette has 6 roles. All hex values are RGB. Use these exact values in python-pptx `RGBColor` objects.

### Corporate
**Use case**: Business presentations, finance decks, quarterly reports

| Role | Hex | RGB |
|------|-----|-----|
| Primary | #2C3E50 | (44, 62, 80) |
| Secondary | #34495E | (52, 73, 94) |
| Accent | #E74C3C | (231, 76, 60) |
| Background | #FFFFFF | (255, 255, 255) |
| Text | #2C3E50 | (44, 62, 80) |
| Muted | #BDC3C7 | (189, 195, 199) |

### Tech
**Use case**: Engineering talks, developer presentations, architecture reviews

| Role | Hex | RGB |
|------|-----|-----|
| Primary | #1A1A2E | (26, 26, 46) |
| Secondary | #16213E | (22, 33, 62) |
| Accent | #0F3460 | (15, 52, 96) |
| Background | #F5F5F5 | (245, 245, 245) |
| Text | #1A1A2E | (26, 26, 46) |
| Muted | #A0A0A0 | (160, 160, 160) |

### Warm
**Use case**: Creative pitches, education, workshops

| Role | Hex | RGB |
|------|-----|-----|
| Primary | #D4A574 | (212, 165, 116) |
| Secondary | #C68B59 | (198, 139, 89) |
| Accent | #8B4513 | (139, 69, 19) |
| Background | #FFF8F0 | (255, 248, 240) |
| Text | #3D2B1F | (61, 43, 31) |
| Muted | #D2B48C | (210, 180, 140) |

### Ocean
**Use case**: Healthcare, sustainability, environmental topics

| Role | Hex | RGB |
|------|-----|-----|
| Primary | #006994 | (0, 105, 148) |
| Secondary | #008B8B | (0, 139, 139) |
| Accent | #20B2AA | (32, 178, 170) |
| Background | #F0FFFF | (240, 255, 255) |
| Text | #003333 | (0, 51, 51) |
| Muted | #B0C4DE | (176, 196, 222) |

### Midnight
**Use case**: Dark theme presentations, tech keynotes, product launches

| Role | Hex | RGB |
|------|-----|-----|
| Primary | #1B1464 | (27, 20, 100) |
| Secondary | #2E1A47 | (46, 26, 71) |
| Accent | #7B2FBE | (123, 47, 190) |
| Background | #0D0D0D | (13, 13, 13) |
| Text | #E0E0E0 | (224, 224, 224) |
| Muted | #4A4A6A | (74, 74, 106) |

### Forest
**Use case**: Environmental topics, nonprofits, nature-related content

| Role | Hex | RGB |
|------|-----|-----|
| Primary | #2D5016 | (45, 80, 22) |
| Secondary | #3A6B1E | (58, 107, 30) |
| Accent | #7CB342 | (124, 179, 66) |
| Background | #F5F9F0 | (245, 249, 240) |
| Text | #1A2E0A | (26, 46, 10) |
| Muted | #A5D6A7 | (165, 214, 167) |

### Sunset
**Use case**: Startups, energy, bold creative presentations

| Role | Hex | RGB |
|------|-----|-----|
| Primary | #FF6B35 | (255, 107, 53) |
| Secondary | #F7931E | (247, 147, 30) |
| Accent | #FFD700 | (255, 215, 0) |
| Background | #FFF5E6 | (255, 245, 230) |
| Text | #333333 | (51, 51, 51) |
| Muted | #FFE0B2 | (255, 224, 178) |

### Minimal
**Use case**: Safe default for any context; clean, professional look

| Role | Hex | RGB |
|------|-----|-----|
| Primary | #333333 | (51, 51, 51) |
| Secondary | #666666 | (102, 102, 102) |
| Accent | #0066CC | (0, 102, 204) |
| Background | #FFFFFF | (255, 255, 255) |
| Text | #333333 | (51, 51, 51) |
| Muted | #CCCCCC | (204, 204, 204) |

---

## Palette Selection Heuristic

| Presentation Type | Recommended Palette | Fallback |
|-------------------|--------------------|---------|
| Business / Finance | Corporate | Minimal |
| Engineering / Dev talk | Tech | Minimal |
| Creative / Workshop | Warm | Sunset |
| Healthcare / Sustainability | Ocean | Forest |
| Dark theme keynote | Midnight | Tech |
| Environmental / Nonprofit | Forest | Ocean |
| Startup / Energy | Sunset | Warm |
| Unknown / General | Minimal | Corporate |

When in doubt, use **Minimal**. It works everywhere and offends nobody.

---

## Typography

### Font Selection

**Primary fonts**: Calibri, Arial

**Why only these two**: Presentations are shared documents. Custom fonts cause rendering failures on machines that don't have them installed. Calibri ships with Microsoft Office; Arial ships with every operating system. Portability trumps aesthetics.

### Size Guide

| Element | Font | Size (pt) | Weight | python-pptx Pt() |
|---------|------|-----------|--------|-------------------|
| Title slide headline | Calibri | 40-44 | Bold | Pt(44) |
| Section divider headline | Calibri | 36 | Bold | Pt(36) |
| Slide headline | Calibri | 28-32 | Bold | Pt(28) |
| Body text | Calibri | 18-22 | Regular | Pt(20) |
| Bullet points | Calibri | 18-20 | Regular | Pt(18) |
| Captions / footnotes | Calibri | 12-14 | Regular | Pt(12) |
| Slide number | Arial | 10 | Regular | Pt(10) |

### Font Weight Rules

- Headlines: **Bold** always
- Body text: Regular weight
- Emphasis within body: Bold for key terms only, not italic (italic renders poorly at presentation distance)
- Never use underline for emphasis (it looks like a hyperlink)

---

## Spacing Rules

### Margins

| Edge | Minimum | python-pptx Inches() |
|------|---------|----------------------|
| Left | 0.5 in | Inches(0.5) |
| Right | 0.5 in | Inches(0.5) |
| Top | 0.5 in | Inches(0.5) |
| Bottom | 0.5 in | Inches(0.5) |

### Content Area

Standard slide is 13.333 x 7.5 inches (widescreen 16:9).

| Zone | Left | Top | Width | Height |
|------|------|-----|-------|--------|
| Title area | 0.5 in | 0.5 in | 12.333 in | 1.2 in |
| Content area | 0.5 in | 1.8 in | 12.333 in | 5.2 in |
| Footer area | 0.5 in | 7.0 in | 12.333 in | 0.4 in |

### Line Spacing

| Element | Spacing | python-pptx |
|---------|---------|-------------|
| Headlines | 1.0x (single) | `paragraph.line_spacing = 1.0` |
| Body text | 1.2x | `paragraph.line_spacing = 1.2` |
| Bullet points | 1.15x | `paragraph.line_spacing = 1.15` |
| Space after paragraph | 6pt | `paragraph.space_after = Pt(6)` |

### Bullet Points

- Indent: 0.25 inches per level
- Maximum nesting: 2 levels deep
- Maximum bullets per slide: 6
- Maximum words per bullet: 8-10
- Bullet character: use default (filled circle for L1, dash for L2)

---

## Slide Density Rules

These limits exist because slides are projected at distance. Dense slides are unreadable.

| Metric | Maximum | Why |
|--------|---------|-----|
| Bullet points per slide | 6 | More than 6 = document, not slide |
| Words per bullet | 10 | Audience reads faster than speaker talks |
| Bullet nesting levels | 2 | Deep nesting = bad structure |
| Colors per slide | 3 from palette | More = visual noise |
| Images per content slide | 2 | More = cluttered |
| Text boxes per slide | 3 | Title + content + optional caption |

---

## python-pptx Color Usage

### Converting hex to RGBColor

```python
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor

# From hex string
def hex_to_rgb(hex_str):
    """Convert '#RRGGBB' to RGBColor."""
    hex_str = hex_str.lstrip('#')
    return RGBColor(
        int(hex_str[0:2], 16),
        int(hex_str[2:4], 16),
        int(hex_str[4:6], 16)
    )

# Direct construction
primary = RGBColor(0x2C, 0x3E, 0x50)  # Corporate primary
```

### Applying colors

```python
# Background
from pptx.util import Inches
slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout
background = slide.background
fill = background.fill
fill.solid()
fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

# Text color
run = paragraph.add_run()
run.text = "Hello"
run.font.color.rgb = RGBColor(0x2C, 0x3E, 0x50)

# Shape fill
shape.fill.solid()
shape.fill.fore_color.rgb = RGBColor(0xE7, 0x4C, 0x3C)
```
