# Structure Templates Reference

Complete template library for YourBlog post outlining.

---

## Primary Templates

### Problem-Solution

**When to use:** Debugging stories, workflow improvements, "how I fixed X"

**Signal words in topic:** "broke", "failed", "figured out", "finally worked", "hours debugging"

```markdown
1. The Vex [200-300 words]
   What: The frustration or problem encountered
   Include: Error messages, symptoms, context
   Avoid: Backstory that doesn't matter

2. Investigation [300-400 words]
   What: The debugging journey
   Include: Failed attempts (teaches readers what NOT to do)
   Include: Tools used, resources consulted
   Avoid: Every single thing tried (focus on instructive failures)

3. The Solution [400-500 words]
   What: What actually worked
   Include: Code/config with explanation
   Include: WHY it works (root cause)
   Avoid: Just the fix without understanding

4. Implications [200-300 words]
   What: Broader lessons
   Include: Prevention strategies
   Include: Related issues to watch for
   Avoid: Generic "always test" advice
```

**Example topic that fits:**
"Spent 3 hours debugging why my Hugo site built locally but failed on Cloudflare Pages. Turned out to be Hugo version mismatch."

---

### Technical Explainer

**When to use:** New technology explanations, concept deep-dives, "what is X and why care"

**Signal words in topic:** "explain", "how does", "what is", "understand", "works"

```markdown
1. What Changed [150-250 words]
   What: Direct statement of the concept/change
   Include: One clear definition
   Avoid: "In today's fast-paced world..."

2. Why It Matters [300-400 words]
   What: Impact and relevance
   Include: Who's affected
   Include: Concrete consequences
   Avoid: Hype without substance

3. How It Works [400-600 words]
   What: Technical mechanics
   Include: Diagrams if helpful
   Include: Code examples if applicable
   Avoid: Implementation details that aren't core

4. What's Next [200-300 words]
   What: Future implications
   Include: Open questions
   Include: Related developments
   Avoid: Vague predictions
```

**Example topic that fits:**
"Explaining how Go 1.22 changed loop variable semantics and why it matters for existing code."

---

### Walkthrough

**When to use:** Tutorials, setup guides, "how to do X step by step"

**Signal words in topic:** "setup", "configure", "install", "create", "build", "step by step"

```markdown
1. Goal [100-150 words]
   What: Clear end state
   Include: What you'll have when done
   Avoid: Why you might want this (put in intro if needed)

2. Prerequisites [150-250 words]
   What: Required before starting
   Include: Versions, tools, accounts
   Include: Knowledge assumed
   Avoid: Obvious things ("have a computer")

3. Steps [500-800 words]
   What: Numbered instructions
   Include: Expected output at each step
   Include: Verification points
   Avoid: Multiple options without recommendation

4. Gotchas [200-300 words]
   What: Common mistakes
   Include: "If you see X, try Y"
   Include: Platform-specific issues
   Avoid: Exhaustive edge case coverage

5. Result [100-150 words]
   What: Success verification
   Include: What to do next
   Avoid: "Congratulations!" fluff
```

**Example topic that fits:**
"Setting up a Hugo blog with PaperMod theme on Cloudflare Pages from scratch."

---

### Comparison

**When to use:** Tool comparisons, trade-off analysis, "X vs Y"

**Signal words in topic:** "vs", "versus", "compare", "choose between", "which is better"

```markdown
1. The Decision [150-250 words]
   What: The choice being faced
   Include: Why this matters
   Include: Context for decision
   Avoid: Obvious explanations of what each thing is

2. Contenders [400-600 words]
   What: Brief intro to each option
   Include: Key characteristics of each
   Include: Philosophy/approach differences
   Avoid: Marketing descriptions

3. Comparison Matrix [300-400 words]
   What: Specific criteria evaluated
   Include: Clear winner per criterion
   Include: Nuance where tied
   Avoid: Subjective "feel" comparisons

4. Recommendation [200-300 words]
   What: When to use which
   Include: Context-dependent guidance
   Include: Your actual choice and why
   Avoid: "It depends" without specifics
```

**Example topic that fits:**
"Choosing between Cloudflare Pages and Vercel for Hugo static site hosting."

---

## Hybrid Templates

### Investigation Report

Combines Problem-Solution investigation with Technical Explainer depth.

**When to use:** Complex bugs that require deep understanding of a system.

```markdown
1. The Symptom [150-200 words]
2. Initial Hypotheses [200-300 words]
3. Deep Dive: [System Component] [400-500 words]
4. Root Cause [300-400 words]
5. The Fix and Why It Works [300-400 words]
6. Lessons [200-300 words]
```

---

### Tutorial with Context

Combines Walkthrough structure with Why It Matters framing.

**When to use:** When the "why" is as important as the "how."

```markdown
1. Why This Approach [200-300 words]
2. Prerequisites [150-200 words]
3. Steps [500-700 words]
4. How It Works Under the Hood [300-400 words]
5. Gotchas and Result [200-300 words]
```

---

## Section Patterns

### Strong Opening Sections

**The Vex (Problem-Solution):**
> Start with the error message or moment of frustration. "Hugo builds locally but Cloudflare says 'theme not found.'" Immediate context, no preamble.

**What Changed (Technical Explainer):**
> Lead with the change itself. "Go 1.22 captures loop variables by value instead of by reference." Definition first, context second.

**Goal (Walkthrough):**
> State the end state. "You'll have a Hugo blog deployed to Cloudflare Pages with automatic builds on push." Concrete and verifiable.

---

### Strong Closing Sections

**Implications (Problem-Solution):**
> Generalize the lesson. "Version-lock all build tools in CI/CD. Document local vs deployed environment differences."

**What's Next (Technical Explainer):**
> Point forward. "Watch for similar changes in the sync package. Consider running go vet with the new loop variable check."

**Result (Walkthrough):**
> Verify success. "Visit your-site.pages.dev and confirm the homepage loads. Check Cloudflare dashboard for build status."

---

## Template Selection Flowchart

```
Did something break/fail?
├── Yes -> Problem-Solution
└── No
    ├── Teaching a process? -> Walkthrough
    ├── Explaining a concept? -> Technical Explainer
    ├── Comparing options? -> Comparison
    └── Multiple aspects? -> Hybrid
```
