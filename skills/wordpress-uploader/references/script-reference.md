# WordPress Uploader Script Reference

## wordpress-upload.py (Create Posts)

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

## wordpress-media-upload.py (Upload Media)

| Flag | Short | Description |
|------|-------|-------------|
| `--file` | `-f` | Path to media file (required) |
| `--title` | `-t` | Media title (defaults to filename) |
| `--alt` | | Alt text for accessibility |
| `--caption` | | Caption for the media |
| `--description` | | Description for the media |
| `--human` | | Human-readable output |

## wordpress-edit-post.py (Edit Posts)

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
