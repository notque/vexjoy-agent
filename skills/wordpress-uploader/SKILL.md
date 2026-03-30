---
name: wordpress-uploader
description: "WordPress REST API integration for posts and media uploads."
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
    - voice-writer
    - anti-ai-editor
  complexity: simple
  category: content-publishing
---

# WordPress Uploader Skill

## Overview

This skill provides WordPress REST API integration for posts and media uploads using deterministic Python scripts. **LJMs orchestrate. Scripts execute.** All WordPress operations go through the three provided Python scripts (`wordpress-upload.py`, `wordpress-media-upload.py`, `wordpress-edit-post.py`), never via curl or raw API calls. This approach ensures credential security, deterministic behavior, and proper markdown-to-Gutenberg conversion.

**Scope**: Create new posts, upload media, edit existing posts, manage featured images, handle categories/tags. Does not write article prose (use voice-writer) or edit prose style (use anti-ai-editor). Requires HTTPS-only connections and Application Password authentication configured in `~/.env`.

---

## Instructions

### Phase 1: VALIDATE ENVIRONMENT

**Goal**: Confirm credentials and target file exist before any API call.

Before executing any script, always complete these validation steps.

**Step 1: Check credentials**

Verify `~/.env` contains all required WordPress variables:

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

This check is mandatory — the most common upload failures stem from missing or misconfigured credentials. Never assume credentials are fine. Never log, display, or echo the Application Password value.

**Step 2: Verify source file**

If uploading content, confirm the markdown file exists and is non-empty using `ls -la <path>`. Check for typos in paths and verify file is not zero bytes.

**HTTPS Requirement**: Confirm `WORDPRESS_SITE` in `~/.env` uses HTTPS, not HTTP. The REST API will reject non-HTTPS connections.

**Gate**: All environment variables present AND non-empty, source file exists and has content, site URL is HTTPS. Proceed only when gate passes.

### Phase 2: UPLOAD / EXECUTE

**Goal**: Run the appropriate script for the requested operation.

Always use `--human` flag for all script invocations to get human-readable output. Always create posts as drafts unless explicitly told to publish. If publishing, ask for user confirmation before setting status to publish (confirm-before-publish default behavior).

**For new posts:**

```bash
python3 ~/.claude/scripts/wordpress-upload.py \
  --file <path-to-markdown> \
  --title "Post Title" \
  --human
```

The `--title` flag is optional. If omitted, the script extracts the title from markdown H1. If both `--title` AND H1 exist, this creates a duplicate title rendering in WordPress (anti-pattern). Use one or the other, not both.

**For media uploads:**

```bash
python3 ~/.claude/scripts/wordpress-media-upload.py \
  --file <path-to-image> \
  --alt "Descriptive alt text" \
  --human
```

Always provide descriptive alt text for accessibility.

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

Use `--get` to retrieve post details for review before making edits.

**Always execute scripts through these deterministic Python wrappers.** Never use curl or raw API calls. The scripts handle credential injection, error formatting, and markdown-to-Gutenberg conversion that manual requests would lose.

**Display complete script output**. Never summarize, truncate, or hide results. The full JSON response contains post IDs, URLs, and validation details the user needs.

**Gate**: Script returns `"status": "success"` with a valid post_id or media_id. Proceed only when gate passes.

### Phase 3: VERIFY

**Goal**: Confirm the operation succeeded and report results to the user.

**Step 1**: Parse script output for post_id, post_url, or media_id. Verify the returned ID is numeric and non-zero.

**Step 2**: Report the complete result with all relevant URLs. Include:
  - Post URL (for posts)
  - WordPress edit URL (`https://<site>/wp-admin/post.php?post=<id>&action=edit`)
  - Media URL (for media uploads)

**Step 3**: Post-upload verification. Confirm success by checking the returned URL and post ID — these prove the script succeeded. If this was a publish operation (not draft), verify the post is accessible at its public URL.

**Step 4**: Multi-step workflow confirmation. If part of a workflow (e.g., image upload + post creation + featured image attachment), confirm ALL steps completed. If any step failed, the workflow is incomplete.

**No partial success**. If a multi-step operation fails at step N, report which steps succeeded and which failed. Do not claim completion.

**Gate**: User has received confirmation with URLs and IDs, all steps in workflow completed (or explicit failure report). Operation is complete.

### Phase 4: POST-UPLOAD WORKFLOWS (Optional)

**Goal**: Handle multi-step workflows that combine operations.

**Featured Image Workflow** (upload image then attach to post):

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

**Batch upload** (multiple files in sequence):

Upload multiple files sequentially, confirming each completes before proceeding to the next. Do not assume concurrent uploads are safe — wait for each script to return.

**Draft cleanup workflow** (delete old drafts after replacement upload):

```bash
# 1. List existing drafts to find old version
python3 ~/.claude/scripts/wordpress-edit-post.py --list-drafts --human

# 2. Delete old draft
python3 ~/.claude/scripts/wordpress-edit-post.py \
  --id <old_post_id> \
  --delete \
  --human
```

**Always delete old drafts after uploading a replacement.** Multiple drafts of the same article accumulate in WordPress and cause confusion. This is mandatory cleanup, not optional.

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

## References

**Script Files**:
- `~/.claude/scripts/wordpress-upload.py`: Create new posts from markdown
- `~/.claude/scripts/wordpress-media-upload.py`: Upload images/media to library
- `~/.claude/scripts/wordpress-edit-post.py`: Edit existing posts (title, content, status, featured image)

**Environment Configuration**:
- File: `~/.env`
- Required variables: `WORDPRESS_SITE`, `WORDPRESS_USER`, `WORDPRESS_APP_PASSWORD`
- Must use HTTPS for the site URL

**Related Skills**:
- `voice-writer`: Use for writing articles (not uploading them)
- `anti-ai-editor`: Use for editing prose style (not publishing to WordPress)
