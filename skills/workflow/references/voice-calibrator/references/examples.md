# Voice Calibration Examples

Real examples demonstrating calibration output and A/B comparisons.

---

## Example 1: Technical Blog Calibration

### Sample Input

Analyzed 4 posts totaling 5,234 words about DevOps topics.

### Extracted Profile Summary

```
Sentence Length:
  Short (3-10):   35%
  Medium (11-20): 45%
  Long (21+):     20%

Opening Pattern:
  Direct fact:    75%
  How/Why:        15%
  Story:          10%
  Question:        0%
  Preamble:        0%

Distinctive Elements:
  - Single-sentence paragraphs for impact
  - Colon usage for elaboration (not em dashes)
  - Specific numbers over vague quantities
  - Active voice almost exclusively
  - No hedging language
```

### A/B Comparison: "Debugging slow Docker builds"

**DEFAULT (Generic Claude):**

> In today's fast-paced development environment, Docker builds can become a significant bottleneck that impacts developer productivity and slows down the overall development cycle. There are various strategies and approaches that teams can employ to optimize their Docker build times and improve their workflow efficiency. Let's explore some of the key techniques that can help reduce build times and create a smoother development experience.

**CALIBRATED (Matching extracted voice):**

> Docker builds on this project took 8 minutes. That's too long.
>
> Here's how we got it under 90 seconds.
>
> The fix was straightforward: layer ordering was wrong. Every code change invalidated the dependency layer. Flipping two lines in the Dockerfile cut 6 minutes immediately.

**Key Differences:**

| Aspect | Default | Calibrated |
|--------|---------|------------|
| Opening | Preamble ("In today's...") | Direct fact with specific number |
| Sentence length | 25+ words average | Mixed short/medium |
| Specificity | "various strategies" | "90 seconds", "6 minutes" |
| Paragraphs | Dense | Single-sentence for impact |
| Voice | Passive tendencies | Active throughout |

---

## Example 2: Tutorial Content Calibration

### Sample Input

Analyzed 5 how-to posts totaling 8,412 words.

### Extracted Profile Summary

```
Sentence Length:
  Short:   20%
  Medium:  55%
  Long:    25%

Opening Pattern:
  How/Why:        60%
  Direct fact:    30%
  Question:       10%

Distinctive Elements:
  - Numbered steps with brief explanations
  - Code blocks every 3-4 paragraphs
  - "First... Then... Finally..." sequence markers
  - Avoids parenthetical asides
```

### A/B Comparison: "Setting up a local Kubernetes cluster"

**DEFAULT:**

> Kubernetes has become the de facto standard for container orchestration, and understanding how to set up and manage Kubernetes clusters is an essential skill for modern developers and DevOps engineers. In this guide, we'll walk through the process of setting up a local Kubernetes cluster using kind (Kubernetes in Docker), which provides a lightweight and convenient way to run Kubernetes locally for development and testing purposes.

**CALIBRATED:**

> Here's how to get a local Kubernetes cluster running in under 5 minutes.
>
> First, install kind:
>
> ```bash
> brew install kind
> ```
>
> Then create your cluster:
>
> ```bash
> kind create cluster --name dev
> ```
>
> Finally, verify it's running:
>
> ```bash
> kubectl cluster-info
> ```
>
> You now have a working Kubernetes cluster. The kubeconfig is already set.

---

## Example 3: Refinement Mode

### Initial Profile

```
Sentence length average: 18 words
List usage: frequent
Opening style: 50% direct fact, 50% how/why
```

### User Request

"Make sentences shorter and use fewer lists"

### Updated Profile

```
Sentence length average: 14 words (reduced from 18)
List usage: rare (changed from frequent)
Opening style: 50% direct fact, 50% how/why (unchanged)
```

### A/B Comparison Showing Refinement

**BEFORE REFINEMENT (18 words avg, frequent lists):**

> There are three main reasons why this approach works better than the alternatives:
>
> - It reduces complexity by eliminating unnecessary abstractions
> - It improves performance by avoiding the overhead of multiple layers
> - It makes debugging easier because there are fewer moving parts

**AFTER REFINEMENT (14 words avg, rare lists):**

> This approach works better. It reduces complexity. It improves performance. Debugging gets easier.
>
> No unnecessary abstractions. No layer overhead. Fewer moving parts.

---

## Example 4: Edge Cases

### Insufficient Samples

```
 ERROR: Insufficient samples for reliable calibration.

 Provided: 2 samples (1,247 words)
 Required: 3+ samples (3,000+ words recommended)

 Available posts in content/posts/:
   - 2024-12-24-first-post.md (83 words)
   - 2024-12-20-docker-builds.md (612 words)

 Options:
   1. Add more writing samples
   2. Include external samples (paste or file path)
   3. Proceed with low-confidence profile (not recommended)
```

### Highly Variable Samples

```
 WARNING: High variance detected in samples.

 Sentence length varies significantly:
   - sample-1.md: 12 words average
   - sample-2.md: 24 words average
   - sample-3.md: 18 words average

 This may indicate:
   - Topic-dependent style variation
   - Style evolution over time
   - Different purposes (tutorial vs opinion)

 Recommendation: Separate calibration for different content types.
```

---

## Example 5: Profile Application

### Existing Profile (from prior calibration)

```markdown
## Voice Profile: DevOps Author

Sentence avg: 14 words
Opening: 80% direct fact
Distinctive: Specific numbers, active voice, no hedging
```

### User Request

"Write an intro paragraph about GitHub Actions caching"

### Generated Content (applying profile)

> GitHub Actions without caching rebuilds dependencies every run. A Node.js project with 500 packages waits 3 minutes each time. Adding a cache line cuts this to 15 seconds. The fix takes 4 lines of YAML.

### Why This Matches Profile

- Opening: Direct fact ("GitHub Actions without caching...")
- Sentence length: 8, 12, 9, 8 words (avg 9.25, within short-medium range)
- Specificity: "500 packages", "3 minutes", "15 seconds", "4 lines"
- Voice: Active throughout
- No hedging: No "can", "might", "could", "potentially"
