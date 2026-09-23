# CSS Audit Patterns Reference

> **Scope**: grep/rg commands to audit existing frontend source for token drift, font choices, motion volume, and fallback gaps.
> **Version range**: CSS3+, all frameworks (Tailwind, CSS Modules, plain CSS/SCSS)

---

## Overview

Run these on an existing codebase before or after a restyle. Each command surfaces a signal to review, not a verdict. The judgment for what to do with a hit lives in `skills/shared-patterns/ui-design-judgment.md`; the generated-UI tells are in its section 9.

---

## Pattern Catalog
<!-- no-pair-required: section-header-only; pairs live in each sub-section below -->

### Check That Fonts Match the Surface

**Detection**:
```bash
# List every font family in use, with counts
rg -o "font-family:\s*[^;]+" -g "*.css" -g "*.scss" -g "*.tsx" -g "*.jsx" -g "*.html" | sort | uniq -c | sort -rn
rg -o "next/font/google.*" -g "*.tsx" -g "*.ts"
rg -o "fonts.googleapis.com/css2\?family=[^\"'&]+" -g "*.html" -g "*.tsx"
```

**Why this matters**: The question is fit, not a banned list. A neutral sans (system UI font, Inter, Geist) is the right default for tools. On a brand-led page, the same face picked by reflex makes the page look like a template. More than two families usually means nobody decided.

**Preferred action**: Tools: one neutral family, hierarchy from size and weight. Brand pages: a display and text pair chosen from `font-catalog.json` for the brand. Cut any third family unless it has a job (for example, mono for code).

---

### Define All Colors as CSS Custom Properties

**Detection**:
```bash
# Hardcoded hex values outside custom property definitions
grep -rn '#[0-9a-fA-F]\{3,6\}' --include="*.css" --include="*.scss" | grep -v '^\s*--'

# Hardcoded rgb/hsl in style rules
rg 'color:\s*(rgb|rgba|hsl|hsla)\(' --type css
rg 'background(-color)?:\s*(rgb|rgba|hsl|hsla)\(' --type css

# Tailwind arbitrary color values
rg 'text-\[#[0-9a-fA-F]+\]|bg-\[#[0-9a-fA-F]+\]|border-\[#[0-9a-fA-F]+\]' -g "*.tsx" -g "*.jsx"
```

**Signal**:
```css
.hero-title {
  color: #1a1a2e;           /* hardcoded: bypasses the token system */
  background: #4a90e2;
}
```

**Why this matters**: Scattered literals make contrast and dark mode impossible to audit, and palette changes need edits across many files.

**Preferred action**: Define semantic tokens once (background, surface, foreground, muted, border, primary) and reference them with `var()`:
```css
:root {
  --fg: #1a1a2e;
  --primary: #2f6fdb;
}
.hero-title { color: var(--fg); }
```

---

### Keep Motion Purposeful

**Detection**:
```bash
# All animation declarations
grep -rn '^\s*animation:' --include="*.css" --include="*.scss" --include="*.module.css"

# Framer Motion elements per file (review files with many)
rg 'motion\.(div|section|h[1-6]|p|span|article|header|footer)' -g "*.tsx" -g "*.jsx" -c

# Blanket transitions
grep -rn 'transition:\s*all' --include="*.css" --include="*.scss"
```

**Why this matters**: When everything moves, nothing stands out. `transition: all` also animates layout properties and costs frames.

**Preferred action**: Keep motion that explains a change (where something came from, what changed, what is loading). On landing pages, 2-3 intentional motions is a good budget. Name transitioned properties: `transition: opacity 200ms, transform 200ms`.

---

### Include a Named Fallback in Every Font Stack

**Detection**:
```bash
grep -rn "font-family:\s*sans-serif\b" --include="*.css" --include="*.scss"
grep -rn "font-family:\s*'[^']*'" --include="*.css" | grep -v ','
```

**Signal**:
```css
h1 { font-family: 'Outfit'; }   /* no fallback: invisible or shifting text while loading */
```

**Why this matters**: A web font with no fallback shows invisible or jumping text on slow connections.

**Preferred action**: End every web-font stack with a close system fallback and generic family: `font-family: 'Outfit', system-ui, sans-serif;`. For tools, `system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif` alone is a good stack.

---

## Error-Fix Mappings

| Warning (validate_design.py) | Root cause | Fix |
|---|---|---|
| `reflexive font pick` | Popular default face on a brand page | Keep it for tools; for brand pages, choose from the catalog or state the brand reason |
| `common default palette` | Palette matches a generic default (purple gradient, stock blue) | Source the accent from the brand, or state why it is the brand color |
| `hardcoded color values` | Hex/rgb outside `:root` | Move to a token; reference via `var()` |
| `font-family: bare sans-serif` | No named fallback | Add `system-ui` before the generic family |

---

## See Also

- `skills/shared-patterns/ui-design-judgment.md`: judgment, defaults, and the tells table
- `font-catalog.json`: fonts by category, including `product_ui_neutral`
- `animation-patterns.md`: motion patterns with timing values
