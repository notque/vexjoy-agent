# WordPress Uploader Workflows

## Phase 4: POST-UPLOAD WORKFLOWS (Optional)

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
