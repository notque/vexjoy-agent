# your blog Filter Reference

## Core Identity

your blog documents "the specific satisfaction found in solving deeply frustrating technical problems."

This means every post must have:
1. **A vex**: Real frustration, time lost, blocked progress
2. **A joy**: Satisfying resolution, understanding gained
3. **Value**: Helps others avoid the same struggle

---

## The Three-Question Test

Apply these questions to every topic candidate. All three must be YES.

### Question 1: Was there genuine frustration?

**YES signals:**
- "I spent 3 hours on this"
- "The error message was useless"
- "The docs said X but reality was Y"
- "It worked locally but failed in CI"
- "I tried 5 different approaches"
- "I almost gave up"

**NO signals:**
- "I wanted to learn about X"
- "This seemed interesting"
- "I read that Y is popular"
- "Someone asked me about Z"

**Examples:**

| Candidate | Frustration? | Verdict |
|-----------|--------------|---------|
| "Hugo hot reload stopped working" | YES - broke workflow | PASS |
| "How to use Hugo partials" | NO - just learning | FAIL |
| "DNS propagation took 48 hours" | YES - delayed launch | PASS |
| "DNS basics explained" | NO - educational | FAIL |

### Question 2: Is there a satisfying resolution?

**YES signals:**
- "Fixed by changing one config line"
- "The root cause was X"
- "Now I understand why it happened"
- "Here's how to prevent this"
- "The solution is elegant"

**NO signals:**
- "Still not sure why it works now"
- "I just kept trying things"
- "The workaround is ugly"
- "I gave up and used a different approach"
- "It's still broken"

**Examples:**

| Candidate | Resolution? | Verdict |
|-----------|-------------|---------|
| "Cache TTL was exactly 168 hours" | YES - root cause found | PASS |
| "Restarting fixed it somehow" | NO - no understanding | FAIL |
| "Env var order matters in shell" | YES - clear insight | PASS |
| "Some race condition I think" | NO - uncertain | FAIL |

### Question 3: Would this help others solve the same struggle?

**YES signals:**
- Problem is common (not unique to your setup)
- Solution is reproducible
- Error message is searchable
- Technology is widely used
- Pattern appears in other contexts

**NO signals:**
- Problem was caused by your typo
- Solution requires your specific infrastructure
- No one else uses this obscure tool
- Problem was already fixed in next version
- Too simple (covered in official docs)

**Examples:**

| Candidate | Helps others? | Verdict |
|-----------|---------------|---------|
| "Cloudflare env vars at build vs runtime" | YES - common confusion | PASS |
| "My server's disk was full" | NO - ops issue, not insight | FAIL |
| "Go 1.22 loop variable change" | YES - affects many codebases | PASS |
| "Typo in my config file" | NO - not transferable | FAIL |

---

## Topic Categories

### GREEN (Strong your blog Fit)

These topic patterns consistently pass the filter:

**Debugging Stories**
- "Why X failed only in Y condition"
- "The bug that appeared after N days"
- "Tracing an error through 5 services"

**Configuration Gotchas**
- "The one setting that breaks everything"
- "Default values that bite you"
- "Config options the docs don't explain"

**Integration Pain**
- "Making A work with B"
- "When version X meets version Y"
- "The hidden dependency you didn't know about"

**Documentation Gaps**
- "What the docs assume you know"
- "The step they forgot to mention"
- "Translating docs into reality"

**Migration Stories**
- "Moving from X to Y: the real challenges"
- "Upgrade paths and their pitfalls"
- "What broke when we upgraded"

### RED (Likely Fails Filter)

These topic patterns usually fail:

**Pure Tutorials**
- "How to install X"
- "Getting started with Y"
- "A beginner's guide to Z"

Why: No frustration, just learning.

**Opinion Pieces**
- "Why I prefer X over Y"
- "The case for Z"
- "My favorite tools"

Why: No specific problem solved.

**News Commentary**
- "New release of X announced"
- "What Y means for the industry"
- "Predictions for Z"

Why: No hands-on experience.

**List Posts**
- "10 tips for better X"
- "5 things to know about Y"
- "Top Z tools for A"

Why: Usually shallow, no narrative.

**Meta Content**
- "How I set up my blog"
- "My writing process"
- "Why I started blogging"

Why: Navel-gazing, not problem-solving.

### YELLOW (Needs Angle)

These can work with the right framing:

**Comparisons** (needs hands-on context)
- BAD: "X vs Y: which is better?"
- GOOD: "I migrated from X to Y and here's what broke"

**Explainers** (needs friction point)
- BAD: "Understanding how X works"
- GOOD: "Understanding why X failed in my case"

**Best Practices** (needs failure story)
- BAD: "Best practices for X"
- GOOD: "The best practice I ignored and regretted"

---

## Filter Application Checklist

For each topic candidate:

```
TOPIC: [title]

1. FRUSTRATION CHECK
   [ ] Real time lost? (not just "I was curious")
   [ ] Multiple attempts? (not first-try success)
   [ ] Blocked progress? (not optional exploration)
   --> Frustration: YES / NO

2. RESOLUTION CHECK
   [ ] Root cause identified? (not "it just started working")
   [ ] Solution understood? (not cargo-culting)
   [ ] Insight gained? (not just workaround)
   --> Resolution: YES / NO

3. VALUE CHECK
   [ ] Common enough? (not unique to your setup)
   [ ] Reproducible? (others can hit this)
   [ ] Searchable? (people will look for this)
   --> Value: YES / NO

FILTER RESULT: [PASS / FAIL / NEEDS ANGLE]
```

---

## Salvaging Failed Topics

When a topic fails the filter, try these transformations:

**Failed: Tutorial-only**
- Find the gotcha: "What mistake does everyone make?"
- Find the edge case: "When does this break?"
- Find the integration: "What conflicts with this?"

**Failed: Opinion-only**
- Add measurement: "I measured X and found Y"
- Add failure: "I tried the opposite and here's what happened"
- Add migration: "I switched and here's what broke"

**Failed: Too broad**
- Narrow to one failure mode
- Focus on one specific scenario
- Pick one moment of frustration

**Failed: No resolution**
- Wait until problem is solved
- Document the investigation as "what I tried"
- Frame as "open question" only if the journey itself has value

---

## Examples: Before and After

### Example 1: Tutorial to Debugging Story

**Before (FAIL):**
```
Topic: "How to use Git submodules"
The Vex: Learning submodules
The Joy: Submodules work now
```

**After (PASS):**
```
Topic: "Git Submodule Breaks Hugo Build with Detached HEAD"
The Vex: Theme updates fail silently, stuck on old version
The Joy: Understanding submodule update workflow
```

### Example 2: Opinion to Experience

**Before (FAIL):**
```
Topic: "Why static sites are better than dynamic"
The Vex: Dynamic sites are slow
The Joy: Static is fast
```

**After (PASS):**
```
Topic: "Migrating from WordPress to Hugo Cut Load Time by 8x"
The Vex: 2.3 second page loads, $40/month hosting
The Joy: 280ms loads, free hosting, understanding why
```

### Example 3: Broad to Specific

**Before (FAIL):**
```
Topic: "Kubernetes networking problems"
The Vex: Networking is hard
The Joy: Understanding networking
```

**After (PASS):**
```
Topic: "Pod DNS Resolution Fails After Node Reboot"
The Vex: Services unreachable, CoreDNS not responding
The Joy: Understanding kubelet restart order
```
