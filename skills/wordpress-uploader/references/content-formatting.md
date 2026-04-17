# WordPress Uploader Content Formatting

**Do NOT include title or author in the article body.** WordPress manages these as metadata. Duplicating them in content creates inconsistency when editing in wp-admin.

## Supported Gutenberg Block Types

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

## Code Blocks

Fenced code blocks with optional language hints are converted to `wp:code` blocks:

````markdown
```python
def hello():
    print("Hello, World!")
```
````

## Button Links

Use the `{.wp-button}` attribute to create WordPress button blocks:

```markdown
[Download Now](https://example.com/download){.wp-button}
```

## Block Validation

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
