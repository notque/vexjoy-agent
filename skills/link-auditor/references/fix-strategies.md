# Fix Strategies

How to address each type of link issue identified by the auditor.

---

## Orphan Pages

**Issue**: Page has 0 inbound internal links.

### Strategy 1: Add Contextual Link from Related Content

Find a related post and add a natural link:

```markdown
<!-- In related post -->
For more details on debugging Kubernetes networking,
see [my previous deep-dive on the topic](/posts/2024-03-k8s-networking/).
```

**Best for**: Content that naturally relates to existing posts.

### Strategy 2: Create a "Related Posts" Section

Add a section at the end of related content:

```markdown
## Related Posts

- [Kubernetes Networking Deep Dive](/posts/2024-03-k8s-networking/)
- [Debugging Container Issues](/posts/2024-04-containers/)
```

**Best for**: Multiple orphan pages in same topic.

### Strategy 3: Build a Pillar/Hub Page

Create a comprehensive page linking to subtopics:

```markdown
# Complete Guide to Kubernetes Troubleshooting

## Networking Issues
- [Debugging Kubernetes Networking](/posts/2024-03-k8s-networking/)

## Container Issues
- [Debugging Container Issues](/posts/2024-04-containers/)
```

**Best for**: Multiple related orphan pages, topic cluster strategy.

### Strategy 4: Add to Navigation

Include in site navigation or category index:

```toml
# In hugo.toml or navigation config
[[menus.main]]
  name = "Deep Dives"
  pageRef = "/categories/deep-dives"
  weight = 20
```

**Best for**: Important content that deserves navigation visibility.

### Strategy 5: Remove Content

If content is truly outdated or irrelevant:

```bash
git rm content/posts/2024-03-outdated-post.md
```

**Best for**: Content no longer accurate or valuable.

---

## Broken Internal Links

**Issue**: Link points to non-existent internal page.

### Strategy 1: Fix the Path

Common path issues:

```markdown
<!-- Wrong: Missing extension -->
[Link text](/posts/my-post)

<!-- Correct: Hugo handles both, but be consistent -->
[Link text](/posts/my-post/)
[Link text](/posts/my-post.md)  <!-- Using Hugo ref is better -->
```

### Strategy 2: Use Hugo ref Shortcode

More robust than hardcoded paths:

```markdown
<!-- Hardcoded (fragile) -->
[Link text](/posts/2024-03-my-post/)

<!-- Hugo ref (validates at build time) -->
[Link text]({{< ref "posts/2024-03-my-post.md" >}})
```

Hugo will fail the build if the ref target doesn't exist.

### Strategy 3: Update After Rename

When you rename a post:

```bash
# After renaming file
git mv content/posts/old-name.md content/posts/new-name.md

# Search and replace in all content
grep -r "old-name" content/
# Update each occurrence
```

### Strategy 4: Create Alias for Moved Content

If you must change a URL, add alias in front matter:

```yaml
---
title: "New Post Title"
aliases:
  - /posts/old-url/
  - /posts/another-old-url/
---
```

Hugo will create redirects from old URLs.

### Strategy 5: Remove Dead Link

If target content is gone and shouldn't return:

```markdown
<!-- Before -->
See [the old tutorial](/posts/deprecated-tutorial/) for details.

<!-- After -->
See the documentation for details.
```

---

## Broken External Links

**Issue**: External URL returns error (404, 500, etc.)

### Strategy 1: Find Updated URL

Use Wayback Machine to find:
- Original content at new location
- Archived version if removed

```
https://web.archive.org/web/*/original-url
```

### Strategy 2: Link to Alternative Source

Find same content elsewhere:

```markdown
<!-- Before: Original source gone -->
[React Docs](https://old-react-site.com/docs)

<!-- After: Updated to current -->
[React Docs](https://react.dev/reference)
```

### Strategy 3: Link to Archive

If no alternative exists:

```markdown
[Original Article](https://web.archive.org/web/20230615/https://original-url.com)
```

### Strategy 4: Remove Link

If content is no longer available anywhere:

```markdown
<!-- Before -->
According to [this study](https://broken-link.com)...

<!-- After -->
According to research published in 2023...
```

### Strategy 5: Add Context for Paywall Content

For paywall sites that appear broken:

```markdown
[WSJ Article](https://wsj.com/article-slug) (subscription required)
```

---

## Missing Images

**Issue**: Image file not found in static/ directory.

### Strategy 1: Add Missing Image

```bash
# Copy image to correct location
cp ~/Downloads/diagram.png static/images/diagram.png
```

### Strategy 2: Fix Path

Common path issues:

```markdown
<!-- Wrong: Missing leading slash -->
![Alt text](images/photo.png)

<!-- Correct: Absolute path from static/ -->
![Alt text](/images/photo.png)
```

### Strategy 3: Use Hugo Shortcode

More control over image rendering:

```markdown
<!-- Standard markdown -->
![Alt text](/images/photo.png)

<!-- Hugo figure (more options) -->
{{< figure src="/images/photo.png" alt="Alt text" caption="Photo caption" >}}
```

### Strategy 4: Remove Image Reference

If image is lost and can't be recovered:

```markdown
<!-- Before -->
See the diagram below:
![Architecture diagram](/images/missing.png)

<!-- After -->
The architecture consists of three layers...
```

---

## Link Sinks

**Issue**: Page receives links but has no outbound internal links.

### Strategy 1: Add "Further Reading" Section

```markdown
## Further Reading

- [Related Topic 1](/posts/related-1/)
- [Related Topic 2](/posts/related-2/)
```

### Strategy 2: Add Contextual Links

Within the content body:

```markdown
This technique builds on the concepts from
[my earlier post on fundamentals](/posts/fundamentals/).
```

### Strategy 3: Link to Next/Previous in Series

```markdown
---
title: "Part 2: Advanced Topics"
---

In [Part 1](/posts/series-part-1/), we covered the basics.
Next, continue to [Part 3](/posts/series-part-3/).
```

### Strategy 4: Accept as Intentional

Some pages legitimately don't need outbound links:
- Comprehensive reference pages
- Landing pages
- Pages with only external references

---

## Under-Linked Pages

**Issue**: Page has fewer than N inbound links.

### Strategy 1: Identify Topic Clusters

Group related content:

```
Topic Cluster: Kubernetes
  - Pillar: /posts/kubernetes-guide/
  - Related: /posts/k8s-networking/  (link from pillar)
  - Related: /posts/k8s-debugging/   (link from pillar)
  - Related: /posts/k8s-security/    (link from pillar)
```

### Strategy 2: Cross-Link Within Clusters

Each page in cluster links to others:

```markdown
<!-- In k8s-networking.md -->
For deployment issues, see [Kubernetes Debugging](/posts/k8s-debugging/).

<!-- In k8s-debugging.md -->
Network-specific issues are covered in [Kubernetes Networking](/posts/k8s-networking/).
```

### Strategy 3: Update Old Content

Revisit old posts to add links to new content:

```markdown
<!-- Adding to old post -->
**Update**: I've written a more detailed follow-up on
[advanced techniques](/posts/new-advanced-post/).
```

---

## Verification After Fixes

Always re-run the auditor after making fixes:

```bash
# TODO: scripts/link_scanner.py not yet implemented
# Re-run manual link extraction to verify fixes
```

Check that:
- Orphan count decreased
- Broken link count decreased
- No new issues introduced

---

## Related

- `link-graph-metrics.md` - Understanding the metrics
- `false-positives.md` - Sites that block validation
