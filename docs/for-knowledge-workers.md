# For Knowledge Workers

## What This Gives You

This toolkit turns Claude Code into a multi-tool for knowledge work. Not just coding -- writing, research, community moderation, data analysis, content publishing. You describe what you want in plain language, and it figures out which specialized workflow to run. There are 130+ skills behind the scenes, but you don't need to know any of them. You just talk to it.

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

The router dispatches to the voice-writer skill, which runs a multi-phase workflow: Assess the topic, Decide on structure, Draft the content, Preview before saving. It picks a structure template, enforces banned-word lists (no "delve" or "leverage" slipping through), and writes the final post in Hugo-compatible format with proper frontmatter.

Want research baked in? Say so:

```
/do research then write an article about Kubernetes cost optimization
```

Now it hits the research-to-article pipeline -- a bigger workflow. It launches 5 parallel research agents that gather information simultaneously, compiles their findings, then writes the article grounded in what they found. Research informs the narrative but doesn't dominate it.

### Writing in Your Voice

Most AI writing tools produce content that sounds like AI. Same cadence, same word choices, same structural patterns. This toolkit has a voice system that fixes that.

First, you teach it your voice:

```
/create-voice
```

It asks for writing samples -- blog posts, emails, whatever represents how you actually write. Then it runs those through a voice analyzer that extracts quantitative metrics: your average sentence length, how often you use contractions, your punctuation habits, your paragraph structure. Not vibes. Numbers.

Once calibrated, every piece of content gets written in your voice and validated against your profile with a deterministic script. If it doesn't match, it revises -- up to 3 iterations until the voice validator says it's actually you.

### Anti-AI Editing

Already have content that sounds too robotic? The anti-AI editor catches it:

```
/do make this article sound more human
```

It scans for AI writing patterns -- cliches, passive voice, structural monotony, meta-commentary, the usual tells -- using a pattern database of 323 patterns across 24 categories. Then it makes minimal, targeted fixes. Changes the phrasing, not the meaning. Shows you every edit with a reason before applying.

There's also a full pipeline version (`de-ai-pipeline`) that runs scan-fix-verify in a loop, up to 3 iterations, until the content reads clean.

### Content Planning

For ongoing publishing, the content calendar tracks your editorial pipeline:

```
/do show my content calendar
/do add an idea about serverless cold starts
/do move the Kubernetes post to editing
```

It manages 6 stages -- Ideas, Outlined, Drafted, Editing, Ready, Published -- with timestamps on every transition. Highlights what's coming up in the next 14 days, flags stale content, warns about duplicate topics. One markdown file tracks everything.

Need topic ideas?

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

This triggers a formal 5-phase pipeline: SCOPE, GATHER, SYNTHESIZE, VALIDATE, DELIVER. Here's what each phase does.

**Scope** -- defines the primary question and 2-5 sub-questions. Writes a `scope.md` file before any research begins. No gathering without a defined question.

**Gather** -- dispatches 3+ parallel research agents, each assigned a distinct angle. They work simultaneously. Each agent writes its own raw findings file, preserving distinct perspectives instead of mushing everything together.

**Synthesize** -- compiles the raw findings into a structured synthesis. Every claim gets an evidence quality rating: Strong, Moderate, or Weak, based on source specificity.

**Validate** -- checks whether the synthesis actually answers every sub-question from the scope. Looks for gaps and bias.

**Deliver** -- produces a `report.md` with the complete findings. This is the artifact -- saved to `research/{topic}/` so you can reference it later, hand it to someone, or build on it in a future session.

Want a quick pass instead of the full treatment?

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

It connects to Reddit via PRAW, fetches your modqueue (items waiting for review), and classifies each one using LLM-powered analysis against your subreddit's actual rules. For every reported item, you get a recommendation -- approve, remove, lock -- with reasoning that explains why.

Three modes:

**Interactive** -- fetches the queue, classifies everything, presents recommendations with analysis, and waits for you to confirm each action. You stay in control.

**Dry-run** -- same classification, same recommendations, but takes no action. Good for seeing what it would do before trusting it.

**Auto** -- for recurring use. High-confidence items get actioned automatically. Anything ambiguous gets flagged for you.

Before first use, run the setup:

```bash
python3 scripts/reddit_mod.py setup
```

This bootstraps your subreddit data -- auto-generates rules files, pulls mod log summaries, builds a repeat offender list. The classifier uses all of this for context when evaluating reports.

It also does proactive scanning:

```
/do scan my subreddit for rule violations in the last 24 hours
```

This checks recent posts beyond just what's been reported. Useful for catching things that slip through -- like covert vendor marketing that nobody flagged but clearly breaks the rules.

The auto mode pairs with `/loop` for hands-off monitoring:

```
/loop 10m /reddit-moderate --auto
```

That checks the modqueue every 10 minutes, handles clear-cut cases, and flags edge cases for your next review. Not a replacement for human judgment -- a first pass that handles the obvious stuff.

The architecture isn't Reddit-specific. The classification-and-action pattern works for any community with rules and a queue of content to review.

## Data Analysis

### Decision-First Analysis

When you drop a CSV or JSON file and ask a question:

```
/do analyze sales_data.csv -- what's driving the Q3 revenue drop?
```

The data-analysis skill works backward from your question. It starts with the decision you're trying to make, figures out what evidence you need, and only then touches the data. This prevents the common failure where analysis produces impressive charts that answer the wrong question.

It handles: trend analysis, cohort comparison, A/B test evaluation, distribution profiling, anomaly detection. Statistical rigor is built in -- it won't tell you two numbers are "significantly different" without actually running the test.

The output is a structured report with findings tied to your original question. It answers what you asked, with the evidence that supports it -- not a data dump, not a column-by-column summary.

## Content Publishing

### Pre-Publish Checks

Before you publish anything, run it through the checker:

```
/do check this post before publishing
```

The pre-publish checker validates frontmatter, SEO fields, internal links, image paths, draft status, and taxonomy. It classifies findings as blockers (must fix) or suggestions (nice to fix) and gives you a clear report. It won't modify your files without asking.

### SEO

```
/do optimize this post for search
```

The SEO optimizer analyzes keyword placement across titles, headers, and body content. Calculates keyword density. Generates alternative titles. Discovers internal linking opportunities by scanning your other posts. Suggests meta descriptions within the 150-160 character target.

It won't keyword-stuff or write clickbait. Voice preservation is a hard rule -- it won't suggest changes that make your writing sound generic.

### Link Auditing

```
/do audit links across my site
```

The link auditor scans all your content, builds an internal link graph, finds orphan pages (nothing links to them), identifies broken links, and flags under-linked content. Useful for sites that have grown organically and need a structural review.

## Automation

### Recurring Tasks

The `/loop` command runs any task on a schedule:

```
/loop 10m /reddit-moderate --auto
```

That runs reddit moderation every 10 minutes. Works with any command -- research checks, content calendar reviews, whatever you need on repeat.

### Condition-Based Waiting

For tasks that need to wait for something before proceeding -- a service to come up, an API rate limit to reset, a deploy to finish -- the toolkit has condition-based waiting patterns with exponential backoff, timeouts, and proper error handling. You don't write the retry logic. You describe what you're waiting for.

## The Magic Command

You've seen it throughout this doc. `/do` handles everything. Describe what you want in plain language and it routes to the right workflow.

```
/do research quantum computing trends and write a summary report
/do write a blog post about the hidden costs of microservices
/do moderate my subreddit
/do analyze this CSV and find the outliers
/do brainstorm content ideas for Q2
/do check my latest post for SEO issues
/do plan a 4-part series on platform engineering
```

You don't memorize commands. You don't pick from menus. You describe the work, and the router figures out what to dispatch. If it needs research first, it researches. If it needs your voice profile, it loads it. If it needs parallel agents, it launches them.

The whole point is that you think about your work, not the tool.
