# Pipeline Stage Definitions

## Stage Workflow

```
Ideas --> Outlined --> Drafted --> Editing --> Ready --> Published --> Archive
```

---

## Ideas

**Purpose**: Capture raw topic concepts before any development work.

**Entry Criteria**:
- A topic title exists
- Topic is relevant to YourBlog's focus (technical problem-solving, developer experience)

**Exit Criteria**:
- Topic has been researched enough to outline
- Clear understanding of what the post will cover
- Estimated length/depth decided

**Format in Calendar**:
```markdown
- [ ] Hugo partial caching issues
- [ ] Git submodule pain
```

**Typical Duration**: Days to weeks (ideas can incubate)

---

## Outlined

**Purpose**: Structure defined, ready for actual writing.

**Entry Criteria**:
- Main sections/headers defined
- Key points to cover identified
- Any code examples planned
- Research complete

**Exit Criteria**:
- Outline is detailed enough to write from
- No major unknowns remain

**Format in Calendar**:
```markdown
- [ ] **PaperMod customization** (outline: 2025-01-10)
```

**Typical Duration**: 1-3 days

---

## Drafted

**Purpose**: First draft complete, raw content exists.

**Entry Criteria**:
- All sections written
- Code examples included (even if rough)
- Post is readable end-to-end

**Exit Criteria**:
- Self-review complete
- Major content issues identified
- Ready for detailed editing

**Format in Calendar**:
```markdown
- [ ] **Image optimization workflow** (draft: 2025-01-12)
```

**Typical Duration**: 1-5 days

---

## Editing

**Purpose**: In active revision process.

**Entry Criteria**:
- First draft complete
- Editing session started

**Exit Criteria**:
- Grammar and spelling checked
- Code examples verified/tested
- Links validated
- Images optimized
- SEO metadata complete

**Format in Calendar**:
```markdown
- [ ] **Hugo debugging guide** (editing: 2025-01-13)
```

**Typical Duration**: 1-3 days

---

## Ready

**Purpose**: Complete and waiting for scheduled publication.

**Entry Criteria**:
- All editing complete
- Pre-publish checklist passed
- Publication date scheduled

**Exit Criteria**:
- Publication date reached
- Post published

**Format in Calendar**:
```markdown
- [x] **Hugo build errors on Cloudflare** (ready: 2025-01-14)
  - Scheduled: 2025-01-20
```

**Typical Duration**: 0-14 days (scheduled wait)

---

## Published

**Purpose**: Live on site, recent publication.

**Entry Criteria**:
- Post is live on your-blog.com
- Verified accessible

**Exit Criteria**:
- Month ends (archive to Historical)

**Format in Calendar**:
```markdown
- [x] **First post** (published: 2025-01-01)
```

**Typical Duration**: Until end of month

---

## Historical (Archive)

**Purpose**: Long-term record of published content.

**Entry Criteria**:
- Published content from previous months

**Format in Calendar**:
```markdown
## Historical (Archive)
### 2024-12
- First post (2024-12-24)
- Theme setup (2024-12-15)

### 2024-11
- Earlier post (2024-11-20)
```

---

## Stage Transition Summary

| From | To | Trigger | Date Added |
|------|----|---------|------------|
| Ideas | Outlined | Outline complete | outline: |
| Outlined | Drafted | Draft complete | draft: |
| Drafted | Editing | Editing started | editing: |
| Editing | Ready | Editing complete | ready: + Scheduled: |
| Ready | Published | Post goes live | published: |
| Published | Archive | Month ends | (auto-archive) |
