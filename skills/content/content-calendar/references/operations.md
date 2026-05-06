# Content Calendar Operations

## Command Reference

| Command | Description |
|---------|-------------|
| `/content-calendar` | View current pipeline state |
| `/content-calendar view` | Same as above |
| `/content-calendar add "Topic"` | Add new idea to pipeline |
| `/content-calendar move "Topic" [stage]` | Move content to stage |
| `/content-calendar schedule "Topic" YYYY-MM-DD` | Set publication date |
| `/content-calendar archive` | Move old published to historical |

---

## View Operation

### Basic Usage

```
/content-calendar
```

### Output

```
===============================================================
 CONTENT CALENDAR: YourBlog
===============================================================

 PIPELINE STATUS:
   Ideas:     [filled][filled][filled][filled][filled][empty][empty][empty][empty][empty] 5 topics
   Outlined:  [filled][filled][empty][empty][empty][empty][empty][empty][empty][empty] 2 posts
   Drafted:   [filled][empty][empty][empty][empty][empty][empty][empty][empty][empty] 1 post
   Editing:   [empty][empty][empty][empty][empty][empty][empty][empty][empty][empty] 0 posts
   Ready:     [filled][empty][empty][empty][empty][empty][empty][empty][empty][empty] 1 post

 UPCOMING:
   Jan 20: "Hugo build errors on Cloudflare" (ready)

 IN PROGRESS:
   -> "Image optimization workflow" (drafted, needs editing)
   -> "PaperMod customization" (outlined, needs draft)

 RECENT (last 30 days):
   Jan 01: "First post" [checkmark]
   Dec 24: "Hello World" [checkmark]

===============================================================
 COMMANDS:
   /content-calendar add "Topic name"    -> Add to ideas
   /content-calendar move "Topic" drafted -> Move to stage
   /content-calendar schedule "Topic" YYYY-MM-DD -> Set date
===============================================================
```

### Progress Bar Scale

- Maximum count in any stage determines scale
- 10 characters total width
- Proportional fill based on count

---

## Add Operation

### Basic Usage

```
/content-calendar add "Hugo partial caching issues"
```

### Behavior

1. Reads calendar file
2. Adds to Ideas section: `- [ ] Hugo partial caching issues`
3. Increments Ideas count in overview
4. Confirms with brief status

### Edge Cases

**Duplicate title**:
```
Warning: Topic "Hugo partial caching issues" already exists in Ideas.
Add anyway? Proceeding will create duplicate.
```

**Empty title**:
```
Error: Topic name cannot be empty.
Usage: /content-calendar add "Topic name"
```

---

## Move Operation

### Basic Usage

```
/content-calendar move "Hugo partial caching issues" outlined
```

### Valid Stages

- `outlined` - Structure defined
- `drafted` - First draft complete
- `editing` - In revision
- `ready` - Complete, awaiting publication
- `published` - Live on site

### Behavior by Target Stage

**To Outlined**:
```markdown
- [ ] **Hugo partial caching issues** (outline: 2025-01-15)
```

**To Drafted**:
```markdown
- [ ] **Hugo partial caching issues** (draft: 2025-01-16)
```

**To Editing**:
```markdown
- [ ] **Hugo partial caching issues** (editing: 2025-01-17)
```

**To Ready** (prompts for date if not scheduled):
```markdown
- [x] **Hugo partial caching issues** (ready: 2025-01-18)
  - Scheduled: 2025-01-25
```

**To Published**:
```markdown
- [x] **Hugo partial caching issues** (published: 2025-01-25)
```

### Edge Cases

**Topic not found**:
```
Error: Topic "Hugi caching issues" not found.
Did you mean: "Hugo partial caching issues"?
```

**Invalid stage**:
```
Error: "drafted" is not a valid stage.
Valid stages: outlined, drafted, editing, ready, published
```

**Moving to ready without date**:
```
Moving "Hugo partial caching issues" to Ready.
When should this be published? (YYYY-MM-DD):
```

---

## Schedule Operation

### Basic Usage

```
/content-calendar schedule "Hugo build errors" 2025-01-25
```

### Behavior

1. Finds topic in Ready section
2. Updates or adds scheduled date
3. Confirms scheduling

### Edge Cases

**Topic not in Ready**:
```
Error: "Hugo build errors" is in Drafted stage.
Move to Ready first: /content-calendar move "Hugo build errors" ready
```

**Past date**:
```
Warning: 2025-01-01 is in the past.
Schedule anyway? (This will mark as ready for immediate publication)
```

**Invalid date format**:
```
Error: Invalid date format "Jan 25".
Use YYYY-MM-DD format: /content-calendar schedule "Topic" 2025-01-25
```

---

## Archive Operation

### Basic Usage

```
/content-calendar archive
```

### Behavior

1. Finds Published items from previous months
2. Moves to appropriate Historical subsection
3. Creates subsection if needed
4. Updates counts

### Example

Before (in January 2025):
```markdown
## Published
- [x] **Current month post** (published: 2025-01-15)
- [x] **December post** (published: 2024-12-24)

## Historical (Archive)
### 2024-11
- November post (2024-11-20)
```

After:
```markdown
## Published
- [x] **Current month post** (published: 2025-01-15)

## Historical (Archive)
### 2024-12
- December post (2024-12-24)

### 2024-11
- November post (2024-11-20)
```

---

## Partial Match Handling

When a topic title doesn't match exactly:

1. **Case-insensitive search**: "hugo build" matches "Hugo Build"
2. **Partial match**: "caching" might match "Hugo partial caching issues"
3. **Multiple matches**: List all and ask for clarification

```
Multiple matches found for "Hugo":
  1. Hugo partial caching issues (Ideas)
  2. Hugo debugging guide (Outlined)
  3. Hugo build errors on Cloudflare (Ready)

Which one? (1-3):
```

---

## Batch Operations

### Adding Multiple Ideas

```
/content-calendar add "Topic 1"
/content-calendar add "Topic 2"
/content-calendar add "Topic 3"
```

Or provide as list:
```
Add these ideas to the content calendar:
- Topic 1
- Topic 2
- Topic 3
```

### Moving Multiple Items

Handle sequentially, confirming each:
```
Moving "Topic 1" from Ideas to Outlined... done
Moving "Topic 2" from Ideas to Outlined... done
```
