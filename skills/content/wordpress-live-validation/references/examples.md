# WordPress Live Validation — Examples

### Example 1: Post-Upload Validation
User says: "Upload this article and check if it looks right"
1. wordpress-uploader creates the post, returns post_url
2. NAVIGATE: Load post_url, wait for content area
3. VALIDATE: Run all 7 checks
4. RESPONSIVE: Screenshots at 375/768/1440px
5. REPORT: Structured output with pass/fail and screenshots

### Example 2: Standalone Live Check
User says: "Check if https://your-blog.com/posts/my-latest/ looks right"
1. NAVIGATE: Load the URL
2. VALIDATE: All checks run without expected title/H2 (reports rendered values as INFO)
3. RESPONSIVE: Screenshots at all breakpoints
4. REPORT: Structured output

### Example 3: OG Tag Verification
User says: "Check the OG tags on my latest post"
1. NAVIGATE: Load the URL
2. VALIDATE: Full check suite (user focuses on SEO/SOCIAL section)
3. RESPONSIVE: Run for completeness
4. REPORT: Full report

---

## Integration with wordpress-uploader

When invoked after `wordpress-uploader`, this skill acts as an optional **Phase 5: POST-PUBLISH VALIDATION**. The wordpress-uploader output provides:

- `post_url` – the navigation target
- `post_id` – for constructing draft preview URLs (`{WORDPRESS_SITE}/?p={post_id}&preview=true`)
- The `--title` value or extracted H1 – the expected title for comparison

The validation is **non-blocking by default**: a FAIL result produces a report for the user but does not revert the upload. The user decides whether to act on findings.

**Example integration flow**:
```
wordpress-uploader Phase 4 completes
  -> post_url = "https://example.com/my-post/"
  -> post_title = "My Post Title"
  -> invoke wordpress-live-validation with post_url and expected title
  -> report generated
  -> user reviews and decides next action
```
