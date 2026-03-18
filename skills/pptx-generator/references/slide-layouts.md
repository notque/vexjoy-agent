# Slide Layout Patterns

Layout types available for the slide map. Each layout specifies the arrangement of text boxes, images, and shapes on a slide.

## Layout Types

### 1. Title Slide

**Purpose**: Opening slide with presentation title and subtitle/author.

**Structure**:
- Title: centered, 44pt bold, vertically centered in upper 60%
- Subtitle: centered, 22pt regular, below title
- Optional: date or author name, 14pt, bottom area

**When to use**: Always as the first slide.

**python-pptx approach**:
```python
slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout
# Add title text box, centered
title_box = slide.shapes.add_textbox(
    Inches(1), Inches(2), Inches(11.333), Inches(2)
)
# Add subtitle text box below
subtitle_box = slide.shapes.add_textbox(
    Inches(2), Inches(4.2), Inches(9.333), Inches(1)
)
```

**Why blank layout**: Using `slide_layouts[6]` (blank) instead of `slide_layouts[0]` (title) avoids inheriting template-specific formatting that may conflict with our design system. We control every element.

---

### 2. Section Divider

**Purpose**: Marks the start of a new section within the presentation.

**Structure**:
- Section title: left-aligned or centered, 36pt bold
- Optional: short description, 20pt regular, below title
- Background: may use a darker shade from palette for visual break

**When to use**: Before each major section in decks with 8+ slides.

**python-pptx approach**:
```python
slide = prs.slides.add_slide(prs.slide_layouts[6])
# Optional: darker background
bg = slide.background.fill
bg.solid()
bg.fore_color.rgb = palette['primary']

# Section title
title_box = slide.shapes.add_textbox(
    Inches(1), Inches(2.5), Inches(11.333), Inches(2)
)
tf = title_box.text_frame
p = tf.paragraphs[0]
p.text = "Section Title"
p.font.size = Pt(36)
p.font.bold = True
p.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)  # or palette text on light bg
```

---

### 3. Content - Bullets

**Purpose**: Standard content slide with headline and bullet points.

**Structure**:
- Headline: left-aligned, 28pt bold, top area
- Bullet list: left-aligned, 18-20pt regular, content area
- Max 6 bullets, max 10 words each

**When to use**: The workhorse layout. Use for most informational content.

**python-pptx approach**:
```python
slide = prs.slides.add_slide(prs.slide_layouts[6])
# Headline
title_box = slide.shapes.add_textbox(
    Inches(0.5), Inches(0.5), Inches(12.333), Inches(1)
)
tf = title_box.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "Slide Headline"
p.font.size = Pt(28)
p.font.bold = True

# Bullets
body_box = slide.shapes.add_textbox(
    Inches(0.5), Inches(1.8), Inches(12.333), Inches(5.2)
)
tf = body_box.text_frame
tf.word_wrap = True
for i, bullet in enumerate(bullets):
    if i == 0:
        p = tf.paragraphs[0]
    else:
        p = tf.add_paragraph()
    p.text = bullet
    p.font.size = Pt(18)
    p.level = 0  # or 1 for sub-bullets
    p.space_after = Pt(6)
```

---

### 4. Content - Two Column

**Purpose**: Side-by-side comparison, pros/cons, before/after.

**Structure**:
- Headline: full width, 28pt bold, top area
- Left column: content area left half, 18pt
- Right column: content area right half, 18pt
- Optional: column headers in bold

**When to use**: Comparisons, contrasts, two related but distinct lists.

**python-pptx approach**:
```python
slide = prs.slides.add_slide(prs.slide_layouts[6])
# Headline (full width)
title_box = slide.shapes.add_textbox(
    Inches(0.5), Inches(0.5), Inches(12.333), Inches(1)
)

# Left column
left_box = slide.shapes.add_textbox(
    Inches(0.5), Inches(1.8), Inches(5.9), Inches(5.2)
)

# Right column
right_box = slide.shapes.add_textbox(
    Inches(6.933), Inches(1.8), Inches(5.9), Inches(5.2)
)
```

---

### 5. Content - Image + Text

**Purpose**: Slide with a supporting image alongside text content.

**Structure**:
- Headline: full width, 28pt bold, top area
- Image: left or right half, vertically centered in content area
- Text: opposite half, 18pt with bullets or paragraph

**When to use**: When user provides an image to embed, or when a diagram/chart supplements text.

**python-pptx approach**:
```python
slide = prs.slides.add_slide(prs.slide_layouts[6])
# Headline
title_box = slide.shapes.add_textbox(
    Inches(0.5), Inches(0.5), Inches(12.333), Inches(1)
)

# Image (left side)
slide.shapes.add_picture(
    image_path,
    Inches(0.5), Inches(1.8), Inches(5.9), Inches(5.2)
)

# Text (right side)
text_box = slide.shapes.add_textbox(
    Inches(6.933), Inches(1.8), Inches(5.9), Inches(5.2)
)
```

---

### 6. Quote / Callout

**Purpose**: Highlight a key quote, statistic, or takeaway.

**Structure**:
- Large quote text: centered, 28-32pt, italic (or regular for stats)
- Attribution: centered below quote, 16pt, muted color
- No headline — the quote IS the content

**When to use**: To break visual rhythm, emphasize a key point, or introduce a speaker's words.

**python-pptx approach**:
```python
slide = prs.slides.add_slide(prs.slide_layouts[6])
# Quote text (centered vertically)
quote_box = slide.shapes.add_textbox(
    Inches(1.5), Inches(2), Inches(10.333), Inches(3)
)
tf = quote_box.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = '"The quote goes here."'
p.font.size = Pt(28)
p.font.italic = True
p.alignment = PP_ALIGN.CENTER

# Attribution
attr_box = slide.shapes.add_textbox(
    Inches(2), Inches(5.2), Inches(9.333), Inches(0.8)
)
tf = attr_box.text_frame
p = tf.paragraphs[0]
p.text = "- Speaker Name, Title"
p.font.size = Pt(16)
p.font.color.rgb = palette['muted']
p.alignment = PP_ALIGN.CENTER
```

---

### 7. Data / Table

**Purpose**: Present structured data in a table format.

**Structure**:
- Headline: full width, 28pt bold, top area
- Table: centered in content area, sized to fit data
- Header row: bold, palette primary background with white text
- Data rows: alternating white/muted background for readability

**When to use**: Comparisons, feature matrices, data summaries.

**python-pptx approach**:
```python
slide = prs.slides.add_slide(prs.slide_layouts[6])
# Headline
title_box = slide.shapes.add_textbox(
    Inches(0.5), Inches(0.5), Inches(12.333), Inches(1)
)

# Table
rows, cols = len(data) + 1, len(headers)  # +1 for header row
table_shape = slide.shapes.add_table(
    rows, cols,
    Inches(0.5), Inches(1.8),
    Inches(12.333), Inches(5.0)
)
table = table_shape.table

# Style header row
for i, header in enumerate(headers):
    cell = table.cell(0, i)
    cell.text = header
    cell.fill.solid()
    cell.fill.fore_color.rgb = palette['primary']
    for paragraph in cell.text_frame.paragraphs:
        paragraph.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        paragraph.font.bold = True
        paragraph.font.size = Pt(14)
```

---

### 8. Closing Slide

**Purpose**: Final slide with thank-you, contact info, or call to action.

**Structure**:
- Main text: centered, 36pt bold ("Thank You", "Questions?", or custom CTA)
- Subtext: contact info, website, etc., 18pt, below main text
- Background: may use primary color for visual bookend with title slide

**When to use**: Always as the last slide.

**python-pptx approach**:
```python
slide = prs.slides.add_slide(prs.slide_layouts[6])
# Optional: colored background to match title slide
bg = slide.background.fill
bg.solid()
bg.fore_color.rgb = palette['primary']

# Main text
main_box = slide.shapes.add_textbox(
    Inches(1), Inches(2.5), Inches(11.333), Inches(2)
)
tf = main_box.text_frame
p = tf.paragraphs[0]
p.text = "Thank You"
p.font.size = Pt(36)
p.font.bold = True
p.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
p.alignment = PP_ALIGN.CENTER
```

---

## Layout Rhythm Guidelines

For visual variety, follow these rhythm patterns:

### Short Deck (5-8 slides)
```
Title → Content → Content → Two-Column → Content → Closing
```

### Medium Deck (8-12 slides)
```
Title → Content → Content → Quote → Section → Content → Two-Column → Content → Closing
```

### Long Deck (12+ slides)
```
Title → Content → Content → Quote → Section → Content → Image+Text → Content → Section → Two-Column → Table → Content → Closing
```

The key principle: **never use the same layout more than 3 times in a row**. Insert a different layout type (quote, two-column, section divider) to break the pattern.
