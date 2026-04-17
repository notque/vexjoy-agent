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

**Goal**: Handle multi-step workflows that combine operations (featured image, batch upload, draft cleanup). See `${CLAUDE_SKILL_DIR}/references/wordpress-upload-workflows.md` for full command blocks.

**Always delete old drafts after uploading a replacement.** Multiple drafts of the same article accumulate in WordPress and cause confusion. This is mandatory cleanup, not optional.

---

## Script Reference

See `${CLAUDE_SKILL_DIR}/references/wordpress-upload-script-reference.md` for full flag tables for `wordpress-upload.py`, `wordpress-media-upload.py`, and `wordpress-edit-post.py`, including category/tag resolution and YAML frontmatter behavior.

---

## Content Formatting

**Do NOT include title or author in the article body.** WordPress manages these as metadata. Duplicating them in content creates inconsistency when editing in wp-admin.

See `${CLAUDE_SKILL_DIR}/references/wordpress-upload-content-formatting.md` for the full Gutenberg block type table, code block syntax, button links, and `--validate` output format.

---

## Error Handling

See `${CLAUDE_SKILL_DIR}/references/wordpress-upload-error-handling.md` for common errors: missing credentials, 401 Unauthorized, 403 Forbidden, file not found.

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
- `wordpress-live-validation`: Post-upload browser-based live validation
