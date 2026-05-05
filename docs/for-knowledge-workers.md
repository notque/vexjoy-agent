# For Knowledge Workers

## What This Gives You

This toolkit turns Claude Code into a multi-tool for knowledge work: writing, research, community moderation, data analysis, content publishing. Describe what you want in plain language. 110+ skills behind the scenes, but you just talk to it.

## Getting Started

Install the toolkit ([details here](start-here.md)) and open a terminal:

```bash
claude
```

Then type what you want:

```
/do write a blog post about remote work burnout
```

That's the interface. `/do` is the front door. You describe the work. The router reads your intent, picks the right agent and skill, and runs it. You don't pick from menus. You don't configure anything. You just say what you need.

A few more examples to show the range:

```
/do research the current state of supply chain AI
/do analyze this CSV and tell me what's driving churn
/do moderate my subreddit
/do brainstorm blog post ideas for next month
```

Every one of those hits a different specialized pipeline. But you don't need to know which one.

## Writing & Content

### Blog Posts

Say you want to write a blog post. Here's what happens when you type:

```
/do write a blog post about debugging production incidents
```

The voice-writer runs an 8-phase pipeline: Load → Ground → Generate → Validate → Refine → Joy-check → Output → Cleanup. Enforces banned-word lists and writes in Hugo-compatible format.

Want research baked in?

```
/do research then write an article about Kubernetes cost optimization
```

Research-to-article workflow: defines 6 research dimensions, launches 5 parallel agents, compiles findings, writes the article. Research informs the narrative but doesn't dominate it.

### Writing in Your Voice

Most AI writing sounds like AI. This toolkit's voice system fixes that:

```
/create-voice
```

Provide writing samples. The analyzer extracts quantitative metrics: sentence length, contraction rate, punctuation habits. Not vibes. Numbers. Once calibrated, content is written in your voice and validated deterministically, up to 3 revision iterations.

### Anti-AI Editing

Already have robotic content? `/do make this article sound more human` scans for 381 AI patterns across 30 categories, makes minimal targeted fixes, shows every edit with reasoning. Pipeline version (`de-ai-pipeline`) loops scan-fix-verify up to 3 iterations.

### Content Planning

For ongoing publishing, the content calendar tracks your editorial pipeline:

```
/do show my content calendar
/do add an idea about serverless cold starts
/do move the Kubernetes post to editing
```

Manages 6 stages (Ideas → Outlined → Drafted → Editing → Ready → Published) with timestamps, 14-day lookahead, stale content flags, duplicate warnings.

```
/do brainstorm blog post ideas
```

The topic brainstormer generates ideas through problem mining, gap analysis, and technology expansion -- not just random suggestions.

Planning a multi-part series?

```
/do plan a 5-part series on observability
```

The series planner structures it with cross-linking, publishing cadence, and navigation between parts.

## Research

### Research Pipelines

When you need actual research -- not just a quick answer, but a structured investigation with sources:

```
/do research the impact of LLMs on software development productivity
```

5-phase pipeline: **Scope** (primary question + sub-questions) → **Gather** (3+ parallel agents, distinct angles) → **Synthesize** (evidence quality ratings) → **Validate** (gap/bias check) → **Deliver** (`research/{topic}/report.md`).

Quick vs deep:

```
/do quick research on WebAssembly adoption trends
```

Quick mode runs fewer tool calls per agent. Deep mode does the opposite -- say "deep research" and each agent does roughly twice the work.

## Community Moderation

### Reddit Moderation

If you moderate a subreddit, this one's for you:

```
/reddit-moderate
```

Connects to Reddit via PRAW, fetches modqueue, classifies items against your subreddit's rules. Three modes: **Interactive** (confirm each action), **Dry-run** (recommendations only), **Auto** (high-confidence automated, ambiguous flagged).

Setup:

```bash
python3 skills/reddit-moderate/scripts/reddit-mod.py setup
```

Bootstraps subreddit data: rules files, mod log summaries, repeat offender list. Also does proactive scanning:

```
/do scan my subreddit for rule violations in the last 24 hours
```

Checks posts beyond what's reported. Pairs with `/loop 10m /reddit-moderate --auto` for hands-off monitoring every 10 minutes. First pass for obvious stuff, not a replacement for human judgment.

## Data Analysis

### Decision-First Analysis

When you drop a CSV or JSON file and ask a question:

```
/do analyze sales_data.csv -- what's driving the Q3 revenue drop?
```

Works backward from your question: starts with the decision, determines needed evidence, then touches data. Handles trend analysis, cohort comparison, A/B tests, distribution profiling, anomaly detection. Statistical rigor built in. Won't claim significance without running the test. Output: structured report tied to your original question.

## Content Publishing

### Pre-Publish Checks

Before you publish anything, run it through the checker:

```
/do check this post before publishing
```

Validates frontmatter, SEO fields, internal links, image paths, draft status, taxonomy. Classifies findings as blockers or suggestions. Won't modify files without asking.

### SEO

```
/do optimize this post for search
```

Analyzes keyword placement, density, generates alternative titles, discovers internal linking opportunities, suggests meta descriptions (150-160 chars). Voice preservation is a hard rule. No keyword-stuffing or clickbait.

### Link Auditing

```
/do audit links across my site
```

Scans content, builds internal link graph, finds orphan pages, broken links, and under-linked content.

## Automation

### Recurring Tasks

The `/loop` command runs any task on a schedule:

```
/loop 10m /reddit-moderate --auto
```

That runs reddit moderation every 10 minutes. Works with any command -- research checks, content calendar reviews, whatever you need on repeat.

### Condition-Based Waiting

Condition-based waiting with exponential backoff, timeouts, and error handling. Describe what you're waiting for.

## The Magic Command

`/do` handles everything. Describe work in plain language → router dispatches the right workflow. Research, voice profiles, parallel agents. All automatic. You think about your work, not the tool.
