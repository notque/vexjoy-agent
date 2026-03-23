---
name: wordpress-uploader
description: |
  WordPress REST API integration for posts and media via deterministic Python
  scripts. Use when uploading articles, creating drafts, publishing posts,
  uploading images, editing existing posts, or managing WordPress content.
  Use for "upload to wordpress", "create wordpress draft", "publish to
  your-blog", "upload image", or "edit wordpress post". Do NOT use for
  writing articles (use blog-post-writer) or editing prose style (use
  anti-ai-editor).
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
command: /upload-wp
routing:
  triggers:
    - upload to wordpress
    - create wordpress draft
    - publish to your-blog
    - wordpress draft
    - upload article
    - post to wordpress
    - upload image to wordpress
    - edit wordpress post
    - update wordpress post
    - wordpress media
  pairs_with:
    - blog-post-writer
    - anti-ai-editor
  complexity: simple
  category: content-publishing
---

# WordPress Uploader Skill

## Operator Context

This skill operates as an operator for WordPress content publishing, configuring Claude's behavior for secure, deterministic REST API operations. It wraps three Python scripts that handle post creation, media uploads, and post editing. **LLMs orchestrate. Scripts execute.** All WordPress operations go through scripts, never raw API calls.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before any upload
- **Draft by Default**: Always create posts as drafts unless explicitly told to publish
- **Credential Security**: Never log, display, or echo the Application Password
- **HTTPS Required**: Only connect to WordPress sites over HTTPS
- **Script Execution Only**: All WordPress API calls go through the Python scripts, never via curl or raw requests
- **Show Full Output**: Display complete script output; never summarize or truncate results

### Default Behaviors (ON unless disabled)
- **Confirm Before Publish**: Ask for user confirmation before setting status to publish
- **Title Extraction**: Extract title from markdown H1 if `--title` is not provided
- **Human-Readable Mode**: Use `--human` flag for all script invocations
- **Post-Upload Verification**: Confirm success by checking the returned URL and post ID

### Optional Behaviors (OFF unless enabled)
- **Direct Publish**: Publish immediately instead of draft (requires explicit user request)
- **Batch Upload**: Upload multiple files in sequence
- **Featured Image Workflow**: Upload image then attach to post in a single workflow

## What This Skill CAN Do
- Create new WordPress posts from markdown files
- Upload images and media to the WordPress media library
- Edit existing posts (title, content, status, featured image, categories, tags)
- Convert markdown to HTML automatically during upload
- Generate Gutenberg blocks for: headings, paragraphs, lists (ordered and unordered), blockquotes, images, separators, fenced code blocks, and button links
- Validate Gutenberg block HTML for structural correctness (`--validate` flag)
- Set post status: draft, publish, pending, private
- Assign categories and tags by NAME (script looks up IDs via REST API)
- Create tags on the fly if they don't exist in WordPress
- Auto-parse YAML frontmatter for title, categories, tags, slug, excerpt
- Delete old drafts after replacement upload (`--delete` flag)
- List existing drafts (`--list-drafts` flag)
- Retrieve existing post details for inspection before editing

## What This Skill CANNOT Do
- Work without Application Password authentication configured in `~/.env`
- Connect to non-HTTPS WordPress sites
- Write or edit article prose (use blog-post-writer or anti-ai-editor)
- Upload to any CMS other than WordPress

---

## Instructions

### Phase 1: VALIDATE ENVIRONMENT

**Goal**: Confirm credentials and target file exist before any API call.

**Step 1: Check credentials**

Verify `~/.env` contains the required WordPress variables:

```bash
python3 -c "
import os
from pathlib import Path
env = Path(os.path.expanduser('~/.env')).read_text()
required = ['WORDPRESS_SITE', 'WORDPRESS_USER', 'WORDPRESS_APP_PASSWORD']
missing = [v for v in required if v + '=' not in env]
print('OK' if not missing else f'MISSING: {missing}')
"
```

**Step 2: Verify source file**

If uploading content, confirm the markdown file exists and is non-empty.

**Gate**: All environment variables present, source file exists. Proceed only when gate passes.

### Phase 2: UPLOAD / EXECUTE

**Goal**: Run the appropriate script for the requested operation.

**For new posts:**

```bash
python3 ~/.claude/scripts/wordpress-upload.py \
  --file <path-to-markdown> \
  --title "Post Title" \
  --human
```

**For media uploads:**

```bash
python3 ~/.claude/scripts/wordpress-media-upload.py \
  --file <path-to-image> \
  --alt "Descriptive alt text" \
  --human
```

**For editing existing posts:**

```bash
python3 ~/.claude/scripts/wordpress-edit-post.py \
  --id <post-id> \
  --human \
  [--title "New Title"] \
  [--content-file updated.md] \
  [--featured-image <media-id>] \
  [--status draft|publish|pending|private]
```

**For inspecting a post before editing:**

```bash
python3 ~/.claude/scripts/wordpress-edit-post.py \
  --id <post-id> \
  --get \
  --human
```

**Gate**: Script returns `"status": "success"` with a valid post/media ID. Proceed only when gate passes.

### Phase 3: VERIFY

**Goal**: Confirm the operation succeeded and report results to the user.

**Step 1**: Parse script output for post_id, post_url, or media_id
**Step 2**: Report the result with all relevant URLs (post URL, edit URL, media URL)
**Step 3**: If this was a publish operation, confirm the post is accessible
**Step 4**: If part of a multi-step workflow (e.g., image + post + featured image), confirm all steps completed

**Gate**: User has received confirmation with URLs and IDs. Operation is complete.

### Phase 4: POST-UPLOAD (Optional)

**Goal**: Handle multi-step workflows that combine operations.

**Full article with featured image workflow:**

```bash
# 1. Upload the featured image
python3 ~/.claude/scripts/wordpress-media-upload.py \
  --file images/photo.jpg \
  --alt "Description" \
  --human
# Note the media_id from output

# 2. Create the post (frontmatter auto-parsed for title, categories, tags, slug)
python3 ~/.claude/scripts/wordpress-upload.py \
  --file content/article.md \
  --category "News" \
  --tag "Example Tag" --tag "Example Event" \
  --status draft \
  --human
# Note the post_id from output

# 3. Attach featured image to post
python3 ~/.claude/scripts/wordpress-edit-post.py \
  --id <post_id> \
  --featured-image <media_id> \
  --human
```

**Draft cleanup workflow (delete old drafts after replacement upload):**

```bash
# 1. List existing drafts to find old version
python3 ~/.claude/scripts/wordpress-edit-post.py --list-drafts --human

# 2. Delete old draft
python3 ~/.claude/scripts/wordpress-edit-post.py \
  --id <old_post_id> \
  --delete \
  --human
```

**Important**: Always delete old drafts after uploading a replacement. Multiple drafts of the same article accumulate in WordPress and cause confusion.

---

## Script Reference

### wordpress-upload.py (Create Posts)

| Flag | Short | Description |
|------|-------|-------------|
| `--file` | `-f` | Path to markdown file (required). Auto-parses YAML frontmatter for title, categories, tags, slug, excerpt. |
| `--title` | `-t` | Post title (extracted from YAML frontmatter or H1 if omitted) |
| `--status` | `-s` | Post status: draft, publish, pending, private |
| `--category` | | Category by NAME, e.g. `--category "News"` (script looks up ID via REST API). Repeatable. |
| `--tag` | | Tag by NAME, e.g. `--tag "Example Tag"` (creates if missing). Repeatable. |
| `--author` | | Author user ID |
| `--validate` | | Convert to Gutenberg HTML, validate block structure, print results as JSON, and exit without uploading |
| `--human` | | Human-readable output |

**WordPress categories**: Look up your site's category IDs via the REST API or wp-admin. Use category names with `--category` and the script resolves IDs automatically.

**YAML frontmatter**: The upload script auto-strips frontmatter from the article body. No YAML should appear in the published content. If you see `---` or key-value pairs in the published article, the upload failed to strip it.

### wordpress-media-upload.py (Upload Media)

| Flag | Short | Description |
|------|-------|-------------|
| `--file` | `-f` | Path to media file (required) |
| `--title` | `-t` | Media title (defaults to filename) |
| `--alt` | | Alt text for accessibility |
| `--caption` | | Caption for the media |
| `--description` | | Description for the media |
| `--human` | | Human-readable output |

### wordpress-edit-post.py (Edit Posts)

| Flag | Short | Description |
|------|-------|-------------|
| `--id` | `-i` | Post ID to edit (required, except with `--list-drafts`) |
| `--get` | | Fetch post info without editing |
| `--title` | `-t` | New post title |
| `--content` | | New content as HTML string |
| `--content-file` | | New content from markdown file |
| `--status` | `-s` | New status: draft, publish, pending, private |
| `--featured-image` | | Featured image media ID. Use to attach uploaded image to post. |
| `--category` | | Category by NAME (replaces existing) |
| `--tag` | | Tag by NAME (replaces existing) |
| `--excerpt` | | Post excerpt |
| `--delete` | | Delete the specified post (use to clean up old drafts after replacement upload) |
| `--list-drafts` | | List all draft posts (no `--id` required). Use to find old versions before deletion. |
| `--human` | | Human-readable output |

---

## Content Formatting

**Do NOT include title or author in the article body.** WordPress manages these as metadata. Duplicating them in content creates inconsistency when editing in wp-admin.

### Supported Gutenberg Block Types

The upload script automatically converts standard markdown to these Gutenberg block types:

| Markdown Syntax | Gutenberg Block | Notes |
|-----------------|-----------------|-------|
| `## Heading` | `wp:heading` | H2-H4 supported; H1 becomes post title |
| Regular text | `wp:paragraph` | Inline bold, italic, links supported |
| `- item` / `* item` | `wp:list` | Unordered list |
| `1. item` | `wp:list` (ordered) | Ordered list with `<ol>` |
| `> quote` | `wp:quote` | Blockquote |
| `![alt](url)` | `wp:image` | Standalone images |
| `---` / `***` / `___` | `wp:separator` | Horizontal rule |
| `` ```language `` | `wp:code` | Fenced code block with optional language |
| `[Text](url){.wp-button}` | `wp:buttons` + `wp:button` | Button link |

### Code Blocks

Fenced code blocks with optional language hints are converted to `wp:code` blocks:

````markdown
```python
def hello():
    print("Hello, World!")
```
````

### Button Links

Use the `{.wp-button}` attribute to create WordPress button blocks:

```markdown
[Download Now](https://example.com/download){.wp-button}
```

### Block Validation

Use `--validate` to check Gutenberg HTML structure without uploading:

```bash
python3 ~/.claude/scripts/wordpress-upload.py --file article.md --validate
```

Output is JSON: `{"status": "valid", "block_count": N}` or `{"status": "invalid", "errors": [...]}`.

For Gutenberg editor compatibility, you can also use raw WordPress block comments between sections:

```markdown
Your opening paragraph here.

<!-- wp:separator -->
<hr class="wp-block-separator has-alpha-channel-opacity"/>
<!-- /wp:separator -->

<!-- wp:heading -->
## Section Title
<!-- /wp:heading -->

Section content here.
```

---

## Error Handling

### Error: "WORDPRESS_SITE not set" or Missing Credentials
Cause: Environment variables not configured in `~/.env`
Solution:
1. Verify `~/.env` exists in the home directory
2. Check it contains WORDPRESS_SITE, WORDPRESS_USER, and WORDPRESS_APP_PASSWORD
3. Ensure no extra whitespace or quoting around values

### Error: "401 Unauthorized"
Cause: Invalid or expired Application Password
Solution:
1. Log into WordPress admin (wp-admin) > Users > Profile
2. Revoke the old Application Password
3. Generate a new one and update `~/.env`
4. Verify the username matches the WordPress account exactly

### Error: "403 Forbidden"
Cause: WordPress user lacks required capability (e.g., publish_posts, upload_files)
Solution:
1. Confirm the user has Editor or Administrator role
2. Check if a security plugin is blocking REST API access
3. Verify the site allows Application Password authentication

### Error: "File not found" or Empty Content
Cause: Incorrect file path or markdown file is empty
Solution:
1. Verify the file path with `ls -la <path>`
2. Confirm the file has content (not zero bytes)
3. Check for typos in the path, especially the content/ directory structure

---

## Anti-Patterns

### Anti-Pattern 1: Publishing Without Confirmation
**What it looks like**: Setting `--status publish` without asking the user first
**Why wrong**: Published posts are immediately visible to readers. Mistakes are public.
**Do instead**: Always create as draft. Ask for explicit confirmation before publishing.

### Anti-Pattern 2: Skipping Environment Validation
**What it looks like**: Running the upload script without checking credentials first
**Why wrong**: Produces confusing errors. Wastes time debugging API failures that are just config issues.
**Do instead**: Complete Phase 1 validation before any script execution.

### Anti-Pattern 3: Raw API Calls Instead of Scripts
**What it looks like**: Using curl or Python requests directly against the WordPress REST API
**Why wrong**: Bypasses credential handling, error formatting, and markdown conversion built into the scripts.
**Do instead**: Always use the three provided Python scripts for all WordPress operations.

### Anti-Pattern 4: Including Title in Article Body
**What it looks like**: Markdown file starts with `# Article Title` and `--title` is also set
**Why wrong**: Creates duplicate title in WordPress. The H1 renders inside the post body AND as the post title.
**Do instead**: Either use `--title` flag OR include H1 in markdown, never both.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Credentials are probably fine" | Config issues cause most upload failures | Run Phase 1 validation |
| "Draft is close enough to publish" | Draft and publish are different states | Confirm desired status explicitly |
| "I'll just curl the API directly" | Scripts handle auth, conversion, errors | Use the provided scripts |
| "Title in body is fine" | Creates duplicate rendering in WordPress | Use --title flag OR H1, not both |

### Script Files
- `scripts/wordpress-upload.py`: Create new posts from markdown
- `scripts/wordpress-media-upload.py`: Upload images/media to library
- `scripts/wordpress-edit-post.py`: Edit existing posts (title, content, status, featured image)
