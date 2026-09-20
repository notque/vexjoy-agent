---
summary: "Non-developer intro: describe work in plain English, and let the router choose the workflow."
read_when:
  - "introducing the toolkit to a non-developer"
---

# For Knowledge Workers

You do not need to know which agent or skill to use. Describe the outcome after `/do`; the router chooses an appropriate workflow and its quality checks.

```
/do research the current state of supply chain AI
/do analyze this CSV and tell me what's driving churn
/do write a blog post about remote work burnout
```

Be as specific as you would be with a colleague: name the audience, source material, constraints, and desired output when they matter.

## Writing and Content

Use `/do` to draft, revise, plan, or repurpose content:

```
/do research then write an article about Kubernetes cost optimization
/do rewrite this article in the [voice-name] voice
/do make this draft sound more human
/do turn this article into posts for each platform
/do plan a five-part series on observability
```

Writing workflows can ground a draft in research, preserve a defined voice, and check the result before delivery. You can also manage a content calendar, brainstorm from gaps and audience problems, and prepare finished work for publication.

## Research

```
/do research the impact of LLMs on software development productivity
/do quick research on WebAssembly adoption trends
/do deep research on CQRS adoption patterns in fintech
```

Research workflows divide a broad question into useful angles, gather evidence in parallel, compare the quality of sources, and synthesize a report. Use `quick` for orientation and `deep` when the decision warrants broader investigation.

## Data Analysis

```
/do analyze sales_data.csv -- what's driving the Q3 revenue drop?
```

Start with the question you need answered, not a list of calculations. The workflow connects the analysis to that decision and can examine trends, cohorts, experiments, distributions, and anomalies. Its report distinguishes evidence from interpretation instead of presenting every computation as a finding.

## Reports, Decks, and Prototypes

Use `/html` when the result should be something people can open and share:

```
/html report on Q3 churn findings
/html pitch deck for the new onboarding flow
/do turn this document into an interactive prototype
```

The result is a self-contained HTML file that opens in a browser without hosting. It can take the form of a report, slide deck, prototype, visualization, or diagram. Use `/do` to develop the substance and `/html` to present it.

## Publishing and Site Maintenance

```
/do check this post before publishing
/do optimize this post for search without changing its voice
/do audit links across my site
```

These workflows can catch missing publishing fields, broken links, image problems, and other blockers. They can also suggest search improvements and internal links while keeping the intended voice and avoiding keyword stuffing.

## Community Moderation

```
/reddit-moderate
/do scan my subreddit for rule violations in the last 24 hours
```

Moderation compares queued or recent content with your community's rules. You can review each proposed action, run a recommendation-only dry run, or automate high-confidence cases while flagging ambiguous ones. Treat it as a first pass, not a substitute for human judgment.

## Recurring Work

Any command can run on a schedule:

```
/loop 10m /reddit-moderate --auto
```

Use automation only after you are comfortable with the underlying command and its boundaries.

## Start Here

Pick a real task and state the outcome plainly:

```
/do turn these interview notes into a concise findings report for leadership
```
