# Plan 007: The WordPress converters escape link and image URLs

> **Executor instructions**: follow this plan step by step. Run every
> verification command and confirm the expected result before the next step.
> If a STOP condition occurs, stop and report. Do not improvise. Do not run
> any step marked OWNER-GATED. When done, update this plan's row in
> `plans/README.md`, unless a reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat 871f6499..HEAD -- skills/content/content/scripts/publish/wordpress-upload.py skills/content/content/scripts/publish/wordpress-edit-post.py`
> If an in-scope file changed, compare the "Current state" excerpts with the
> live code. A mismatch is a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: security
- **Kind**: fix
- **Planned at**: commit `871f6499`, 2026-11-16

## Why this matters

Two scripts turn markdown into HTML and publish it to a public WordPress site.
Both copy a markdown link target straight into an `href` or `src` attribute.
A URL that contains a double quote closes the attribute and adds new ones, and
any URL scheme is accepted. The markdown comes from an automated pipeline that
summarizes web sources, so a link target is not always text a person wrote.
After this plan, URLs are attribute-escaped, and only `http`, `https`,
`mailto`, and relative targets become links or images.

## Current state

- `skills/content/content/scripts/publish/wordpress-upload.py`: uploads a
  markdown file as a post. `_apply_inline_formatting` is called for
  paragraphs, headings, list items, and quotes (lines 539, 603, 611, 619, 658,
  671, 679).

  ```python
  # skills/content/content/scripts/publish/wordpress-upload.py:473-486
  def _apply_inline_formatting(text: str) -> str:
      """Apply inline markdown formatting (bold, italic, images, links).
      ...
      """
      text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
      text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
      text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1"/>', text)
      text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
      return text
  ```

  The same file already has `_html_escape_code` (line 489) for code blocks.

- `skills/content/content/scripts/publish/wordpress-edit-post.py`: edits an
  existing post. `markdown_to_html` (line 180) has the same two lines:

  ```python
  # skills/content/content/scripts/publish/wordpress-edit-post.py:207-208
      html = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1" class="aligncenter size-full" />', html)
      html = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', html)
  ```

- Both scripts have hyphenated file names, so a test loads them with
  `importlib`. Exemplar: `hooks/tests/test_posttool_security_scan.py:27-31`.
  `wordpress-edit-post.py` imports `requests` at module level (line 37);
  `wordpress-upload.py` has no top-level `requests` import.
  `requirements.lock:17` pins `requests`, so CI has it.
- Skill scripts keep tests beside them. Exemplar:
  `skills/content/content/scripts/reddit-moderate/tests/test_reddit_mod.py`.
- Neither script has a test today.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| New tests | `nice -n 10 python3 -m pytest skills/content/content/scripts/publish/tests/test_wordpress_inline_urls.py -q -n 0 -rs` | all pass, 0 skipped |
| Lint | `ruff check . --config pyproject.toml` | exit 0 |
| Format | `ruff format --check . --config pyproject.toml` | exit 0 |
| Doc and index gates | `bash scripts/ci-local.sh` | exit 0 |

## Scope

**In scope** (the only files to modify):
- `skills/content/content/scripts/publish/wordpress-upload.py`
- `skills/content/content/scripts/publish/wordpress-edit-post.py`
- `skills/content/content/scripts/publish/tests/test_wordpress_inline_urls.py` (create)

**Out of scope** (do not touch, though they look related):
- `wordpress-media-upload.py` and `wordpress-scraper.py` in the same
  directory: they have their own findings in `plans/README.md`.
- A shared helper module for the publish scripts: each script runs standalone
  today. Put the helper in both files.
- Bold, italic, heading, and list conversion: unchanged.
- Any network call. Do not run either script against a real site, and do not
  read `~/.env` or any credential file.

## Git workflow

- Branch: `fix/wordpress-link-url-escaping`.
- One commit. Message style: one lowercase past-tense sentence, no type prefix,
  no trailing period. Example from `git log`:
  `redacted credentials from search-engine-indexer dry-run output and error paths`
- Do not push, open a PR, merge, deploy, or tag.

## Steps

### Step 1: Write the failing tests

Create `skills/content/content/scripts/publish/tests/test_wordpress_inline_urls.py`.
Load `wordpress-upload.py` unconditionally with
`importlib.util.spec_from_file_location`. Load `wordpress-edit-post.py` the
same way inside a module-scoped fixture that first calls
`pytest.importorskip("requests")`, so only its cases can skip. If `requests`
is missing locally, install nothing: that is a STOP condition. Test
`_apply_inline_formatting` (upload) and `markdown_to_html` (edit-post) with
the cases in "Test plan".

**Verify**: the new-tests command → the quote-injection and scheme cases fail, the plain-link cases pass.

### Step 2: Add the URL helper and use it in `wordpress-upload.py`

Add `import html` to the imports. Add above `_apply_inline_formatting`:

```python
_ALLOWED_URL_SCHEMES = ("http://", "https://", "mailto:")


def _safe_url(url: str) -> str | None:
    """Attribute-safe URL, or None when its scheme is not allowed.

    Relative targets (/path, #anchor, ./x, ../x) pass. Everything else needs
    an allowed scheme. The result is HTML-escaped for use inside a
    double-quoted attribute.
    """
    url = url.strip()
    lowered = url.lower()
    relative = lowered.startswith(("/", "#", "./", "../"))
    if not relative and not lowered.startswith(_ALLOWED_URL_SCHEMES):
        return None
    return html.escape(url, quote=True)
```

Replace the image and link lines with function replacements:

```python
    def _image(match: re.Match[str]) -> str:
        url = _safe_url(match.group(2))
        alt = html.escape(match.group(1), quote=True)
        return f'<img src="{url}" alt="{alt}"/>' if url else alt

    def _link(match: re.Match[str]) -> str:
        url = _safe_url(match.group(2))
        return f'<a href="{url}">{match.group(1)}</a>' if url else match.group(1)

    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _image, text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", _link, text)
```

A rejected link keeps its text and loses the anchor. A rejected image becomes
its alt text.

**Verify**: the new-tests command → every `wordpress-upload.py` case passes.

### Step 3: Apply the same change in `wordpress-edit-post.py`

Add `import html as html_lib` (the function already has a local variable named
`html`). Add the same `_ALLOWED_URL_SCHEMES` and `_safe_url` above
`markdown_to_html`, using `html_lib.escape`. Replace lines 207-208 with the
same two function replacements. Keep `class="aligncenter size-full"` on the
image tag.

**Verify**: the new-tests command → all pass.

### Step 4: Lint and gates

**Verify**: `ruff check`, `ruff format --check`, and `bash scripts/ci-local.sh` each exit 0.

## Test plan

New file `skills/content/content/scripts/publish/tests/test_wordpress_inline_urls.py`,
each case run against both converters:

| Case | Input | Assert on output |
|---|---|---|
| Plain link | `[a](https://example.com/x)` | contains `<a href="https://example.com/x">a</a>` |
| Query string | `[a](https://example.com/?x=1&y=2)` | `href` holds `x=1&amp;y=2` |
| Quote in URL | a link whose URL contains a `"` followed by an attribute name | output has exactly one `"`-delimited `href` value, and the injected attribute name appears only inside it, with `&quot;` before it |
| Script scheme | `[a](javascript:void(0))` | no `<a `, text `a` kept |
| Data scheme image | `![alt](data:text/html;base64,AAAA)` | no `<img`, text `alt` kept |
| Relative link | `[a](/about)` and `[a](#top)` | anchors kept |
| Mailto | `[a](mailto:someone@example.com)` | anchor kept |
| Alt with quote | `![say "hi"](https://example.com/i.png)` | `alt` holds `&quot;hi&quot;` |

Model the loader on `hooks/tests/test_posttool_security_scan.py:27-31`.

## Done criteria

- [ ] The new-tests command exits 0 with at least 16 passed (8 per converter) and 0 skipped
- [ ] `grep -nF 'href="\2"' skills/content/content/scripts/publish/wordpress-upload.py skills/content/content/scripts/publish/wordpress-edit-post.py` returns no matches (it returns two before the fix)
- [ ] `grep -nF 'src="\2"' skills/content/content/scripts/publish/wordpress-upload.py skills/content/content/scripts/publish/wordpress-edit-post.py` returns no matches (it returns two before the fix)
- [ ] `ruff check . --config pyproject.toml` and `ruff format --check . --config pyproject.toml` exit 0
- [ ] `bash scripts/ci-local.sh` exits 0
- [ ] `git status --short` shows only the three in-scope files and `plans/README.md`
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report if:

- The code at the "Current state" locations does not match the excerpts.
- Either script cannot be imported in a test without a credential or a network call.
- Any new test reports as skipped: `requests` is missing, and a skipped test proves nothing.
- An existing published-content fixture or test depends on the unescaped output.
- A step's verification fails twice after a reasonable fix attempt.
- A step would need a request to a real WordPress site or a read of an env file.

## Maintenance notes

- Reviewer: check that `&` in a query string becomes `&amp;` inside the
  attribute. That is correct HTML; browsers decode it.
- A new allowed scheme (for example `tel:`) goes in `_ALLOWED_URL_SCHEMES` in
  both files.
- Deferred: the three publish scripts duplicate `load_env_file`, `get_config`,
  `validate_config`, and `_get_auth_headers`, and the helper added here makes
  a fourth duplicated piece. Extract a shared module in a separate plan.
- Deferred: `wordpress-media-upload.py:129` builds a `Content-Disposition`
  header from a raw file name, and `wordpress-scraper.py:524-525` writes post
  titles into frontmatter without stripping newlines.
