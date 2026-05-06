# Content Calendar File Format

## File Location

```
$HOME/your-project/content-calendar.md
```

This file is the single source of truth for all content pipeline state.

---

## Complete File Template

```markdown
# YourBlog Content Calendar

## Pipeline Overview
| Stage | Count |
|-------|-------|
| Ideas | 0 |
| Outlined | 0 |
| Drafted | 0 |
| Editing | 0 |
| Ready | 0 |
| Published (this month) | 0 |

## Ideas
<!-- Raw topic concepts, not yet developed -->

## Outlined
<!-- Structure defined, ready for writing -->

## Drafted
<!-- First draft complete -->

## Editing
<!-- In revision process -->

## Ready
<!-- Complete, waiting for publication date -->

## Published
<!-- Live on site this month -->

## Historical (Archive)
<!-- Past publications by month -->
```

---

## Section Formats

### Ideas Section

Simple checklist items, title only:

```markdown
## Ideas
- [ ] Hugo partial caching issues
- [ ] Git submodule pain
- [ ] Cloudflare env var confusion
- [ ] CSS custom properties in Hugo
- [ ] Tailwind with Hugo
```

### Outlined Section

Bold title with outline date:

```markdown
## Outlined
- [ ] **PaperMod customization** (outline: 2025-01-10)
- [ ] **Hugo debugging guide** (outline: 2025-01-08)
```

### Drafted Section

Bold title with draft date:

```markdown
## Drafted
- [ ] **Image optimization workflow** (draft: 2025-01-12)
```

### Editing Section

Bold title with editing date:

```markdown
## Editing
- [ ] **Advanced Hugo templating** (editing: 2025-01-13)
```

### Ready Section

Checked item with ready date and scheduled publication:

```markdown
## Ready
- [x] **Hugo build errors on Cloudflare** (ready: 2025-01-14)
  - Scheduled: 2025-01-20
- [x] **Another ready post** (ready: 2025-01-15)
  - Scheduled: 2025-01-27
```

### Published Section

Checked item with publication date:

```markdown
## Published
- [x] **First post** (published: 2025-01-01)
- [x] **Theme setup** (published: 2024-12-24)
```

### Historical Archive Section

Organized by year-month headers:

```markdown
## Historical (Archive)
### 2024-12
- First post (2024-12-24)
- Theme setup (2024-12-15)

### 2024-11
- Earlier post (2024-11-20)
```

---

## Pipeline Overview Table

Always keep counts synchronized with actual section contents:

```markdown
## Pipeline Overview
| Stage | Count |
|-------|-------|
| Ideas | 5 |
| Outlined | 2 |
| Drafted | 1 |
| Editing | 0 |
| Ready | 1 |
| Published (this month) | 3 |
```

**Rules**:
- Update counts whenever content moves between stages
- "Published (this month)" only counts current month's publications
- Historical items are not counted

---

## Date Formats

All dates use ISO 8601 format: `YYYY-MM-DD`

Examples:
- `2025-01-15`
- `2024-12-24`

**Date Fields**:
- `outline:` - When outline was completed
- `draft:` - When first draft was completed
- `editing:` - When editing began
- `ready:` - When editing was completed
- `Scheduled:` - Planned publication date
- `published:` - Actual publication date

---

## Checkbox States

- `- [ ]` - Not yet complete/published (Ideas through Editing)
- `- [x]` - Complete (Ready and Published stages)

The checkbox transition happens when moving from Editing to Ready.

---

## Parsing Notes

When parsing the calendar file:

1. **Find sections** by `## ` headers
2. **Count items** by counting lines starting with `- [`
3. **Extract titles** from between `**` markers (or plain text for Ideas)
4. **Extract dates** from parenthetical notation `(stage: YYYY-MM-DD)`
5. **Extract scheduled dates** from indented `- Scheduled:` lines
6. **Parse Historical** by `### YYYY-MM` subsection headers
