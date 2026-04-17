# Alt Text Examples

Reference for writing accessible, descriptive alt text for images.

---

## Purpose of Alt Text

Alt text serves three critical functions:

1. **Accessibility**: Screen readers announce alt text for visually impaired users
2. **Fallback**: Displays when images fail to load
3. **SEO**: Search engines use alt text to understand image content

---

## Alt Text Quality Levels

### FAIL: Missing or Empty

```markdown
<!-- Missing alt attribute -->
![](/images/screenshot.png)

<!-- Empty alt text -->
![](images/diagram.png)
```

**Impact:** Screen readers skip or announce only "image", providing no context.

---

### WARN: Too Generic

These patterns trigger warnings because they provide minimal value:

| Generic Term | Why It's Bad |
|--------------|--------------|
| "image" | States the obvious |
| "picture" | States the obvious |
| "photo" | Doesn't describe content |
| "screenshot" | What's in the screenshot? |
| "diagram" | What does the diagram show? |
| "figure" | Not descriptive |
| "img" | Meaningless |
| Single character | Not useful |

**Examples of generic alt text:**
```markdown
![image](/images/arch.png)
![screenshot](/images/terminal.png)
![diagram](/images/flow.svg)
![x](/images/icon.svg)
```

---

### PASS: Descriptive and Contextual

Good alt text describes the image content and provides context:

**Example 1: Screenshot**
```markdown
<!-- Bad -->
![screenshot](/images/terminal.png)

<!-- Good -->
![Terminal showing successful npm install with 0 vulnerabilities](/images/terminal.png)
```

**Example 2: Diagram**
```markdown
<!-- Bad -->
![diagram](/images/architecture.svg)

<!-- Good -->
![Three-tier architecture: React frontend, Node.js API, PostgreSQL database](/images/architecture.svg)
```

**Example 3: Photo**
```markdown
<!-- Bad -->
![photo](/images/team.jpg)

<!-- Good -->
![Development team collaborating around a whiteboard with system diagrams](/images/team.jpg)
```

---

## Alt Text by Image Type

### Screenshots

Describe what the screenshot demonstrates:

```markdown
<!-- Terminal/Command Line -->
![Git log showing three recent commits on the main branch](/images/git-log.png)

<!-- Application UI -->
![Settings panel with dark mode toggle enabled](/images/settings.png)

<!-- Error Messages -->
![TypeScript error TS2345: Argument of type string not assignable to number](/images/error.png)

<!-- Code Editor -->
![VS Code with Go file open showing syntax highlighting](/images/vscode.png)
```

### Diagrams

Summarize what the diagram illustrates:

```markdown
<!-- Flowcharts -->
![Request flow: user sends request to load balancer, which routes to one of three API servers](/images/flow.svg)

<!-- Architecture -->
![Microservices architecture with API gateway connecting to auth, users, and billing services](/images/microservices.svg)

<!-- Sequence Diagrams -->
![OAuth flow: client requests token, server validates, returns access token](/images/oauth-sequence.svg)

<!-- Charts -->
![Bar chart showing response times: Go 12ms, Rust 8ms, Python 45ms](/images/benchmark.png)
```

### Icons and Logos

Keep brief but specific:

```markdown
<!-- Company/Project Logos -->
![Kubernetes logo](/images/k8s-logo.svg)
![GitHub Octocat mascot](/images/github.svg)

<!-- UI Icons -->
![Search magnifying glass icon](/images/search.svg)
![Warning triangle icon](/images/warning.svg)
```

### Photos

Describe the scene and context:

```markdown
<!-- People -->
![Speaker presenting slides about API design at tech conference](/images/conference.jpg)

<!-- Products -->
![MacBook Pro with terminal window showing code](/images/laptop.jpg)

<!-- Abstract/Decorative -->
![Colorful gradient background for hero section](/images/hero-bg.jpg)
```

---

## Writing Guidelines

### DO

- **Describe the content**: What does the image show?
- **Provide context**: Why is this image here?
- **Be concise**: 10-125 characters is ideal
- **Use natural language**: Write as you'd describe to someone
- **Include relevant text**: If image contains important text, include it

### DON'T

- **Start with "Image of" or "Picture of"**: Redundant
- **Use file names**: "logo-v2-final.png" is not alt text
- **Be overly verbose**: Don't write paragraphs
- **Include "click here"**: Alt text isn't for instructions
- **Repeat caption content**: If caption says it, alt text can be brief

---

## Special Cases

### Decorative Images

If an image is purely decorative with no informational content, use empty alt:

```markdown
![](/images/decorative-divider.svg)
```

Or in HTML:
```html
<img src="/images/decorative.svg" alt="" role="presentation">
```

**When to use empty alt:**
- Decorative borders/dividers
- Background patterns
- Bullet point icons (if meaning conveyed elsewhere)
- Purely aesthetic elements

### Complex Diagrams

For complex diagrams, provide a brief alt text and longer description elsewhere:

```markdown
![System architecture overview - see detailed description below](/images/complex-arch.svg)

**Figure 1:** The system consists of three main components...
```

### Charts and Graphs

Include key data points in alt text:

```markdown
![Line graph showing memory usage increasing from 2GB to 8GB over 24 hours, with spike at 3PM](/images/memory.png)
```

### Code Screenshots

Mention the language and key content:

```markdown
![Python function definition for calculate_tax that takes income parameter and returns tax amount](/images/code.png)
```

---

## Alt Text Checklist

Before considering alt text complete:

- [ ] Does it describe what the image shows?
- [ ] Would someone who can't see the image understand its purpose?
- [ ] Is it concise (under 125 characters if possible)?
- [ ] Does it avoid starting with "Image of" or "Picture of"?
- [ ] Is it not just the filename?
- [ ] Does it provide context for why the image is included?

---

## Examples by Blog Post Type

### Tutorial Post

```markdown
![Terminal showing npm install express command and output](/images/npm-install.png)
![Code editor with server.js file containing Express route handlers](/images/express-code.png)
![Browser showing "Hello World" response at localhost:3000](/images/browser-output.png)
```

### Comparison Post

```markdown
![Side-by-side comparison: vim on left with modal editing, VS Code on right with GUI](/images/editors-comparison.png)
![Performance chart: vim uses 5MB RAM, VS Code uses 250MB RAM](/images/memory-usage.png)
```

### Debugging Post

```markdown
![Error message: ECONNREFUSED 127.0.0.1:5432 in terminal](/images/error.png)
![PostgreSQL service status showing inactive state](/images/pg-status.png)
![Successful database connection after starting PostgreSQL](/images/fixed.png)
```

### Architecture Post

```markdown
![High-level system diagram with frontend, API layer, and database](/images/architecture.svg)
![Detailed view of API layer showing authentication middleware](/images/api-detail.svg)
![Database schema with users, posts, and comments tables](/images/schema.svg)
```
