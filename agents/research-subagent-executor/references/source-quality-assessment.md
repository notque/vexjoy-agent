# Source Quality Assessment

> **Scope**: Identifying reliable vs. unreliable sources, detecting speculation and marketing language, and applying correct epistemic labels in research reports.
> **Version range**: all versions
> **Generated**: 2026-04-13

---

## Overview

Source quality assessment is the discipline of distinguishing facts from inferences before they reach the coordinator's synthesis. The central failure mode is presenting aggregator summaries, marketing claims, or undated community posts as authoritative facts. Every claim in a research report must carry an explicit epistemic label: FACT (sourced), INFERENCE (reasoned from facts), or SPECULATION (not grounded).

---

## Source Tier Classification

| Tier | Source Type | Weight | Example |
|------|-------------|--------|---------|
| 1 | Official docs, release notes, spec documents | High | docs.python.org, RFC, GitHub release page |
| 2 | Peer-reviewed papers, official blog posts from maintainers | High | engineering.atlasmedia.com, arxiv.org |
| 3 | Established technical publications with bylines | Medium | InfoQ, The New Stack, ACM |
| 4 | StackOverflow accepted answers with high votes | Medium-Low | Verify against Tier 1 before using |
| 5 | Community forums, Reddit, HackerNews | Low | Use only to identify what questions exist |
| 6 | Aggregator listicles, vendor marketing | Discard | "Top 10 Kubernetes Tools for 2025" |

---

## Correct Patterns

### Epistemic Labeling in Reports

Every factual claim must be labeled at its first appearance.

```markdown
## Key Facts

- FACT: Python 3.12.0 was released on October 2, 2023 [source: python.org/downloads]
- FACT: The GIL was not removed in 3.12 but made per-interpreter [source: PEP 684]
- INFERENCE: Based on PEP 703, GIL removal will likely ship in 3.13 (experimental flag)
- SPECULATION: Some commenters expect widespread adoption by Q4 2024 (no primary source)
```

**Why**: The coordinator synthesizes multiple subagent reports. Unlabeled inferences that look like facts will be treated as confirmed data points, producing false confidence in the final output.

---

### Detecting Outdated Sources

Before using a source, check for publication/modification date:

```
Freshness signals to look for on the page:
  - "Last updated: [date]" in page footer or header
  - Publication date in URL path (e.g., /2023/01/article)
  - "Published [date]" byline
  - Version number in page title (e.g., "v2.1 docs")

If no date is findable: treat as potentially outdated, note it explicitly.
```

**Why**: Technical documentation goes stale quickly. A Stack Overflow answer from 2019 about Kubernetes resource limits may describe a feature that was redesigned in 1.26.

---

### Primary vs. Aggregator Detection

```
Primary source signals:
  ✓ URL is the official project domain (github.com/org/repo, docs.example.com)
  ✓ Author is a named contributor to the project
  ✓ Contains specific version numbers, commit hashes, PR/issue numbers
  ✓ Includes technical detail that an aggregator wouldn't have (stack traces, config files)

Aggregator signals:
  ✗ Title pattern: "N best X for Y in [year]"
  ✗ Lists 5+ tools with equal-length summaries and no depth
  ✗ Author bio says "content writer" or "marketing specialist"
  ✗ No original analysis — rewrites what official docs say
  ✗ Same text appears on multiple domains (content farm syndication)
```

---

## Pattern Catalog

### ❌ Using Aggregator as Primary Source

**Detection**:
```bash
# In research logs, flag these URL patterns
grep -E "best-[0-9]|top-[0-9]|vs\.|comparison|alternative" urls.txt
rg "(best|top|vs|versus|comparison|alternative)" fetched_urls.txt -i
```

**What it looks like**:
```
web_fetch("https://www.toolscomparison.io/best-kubernetes-monitoring-tools-2024/")
→ Report: "According to industry experts, Prometheus is the leading monitoring tool..."
```

**Why wrong**: The aggregator's claim "according to industry experts" cites no specific expert. The actual source is likely a Prometheus marketing page or another aggregator. The fact launders through a middleman with no accountability.

**Fix**: Find the primary source the aggregator is summarizing. Search for the original study, official docs, or named expert directly.

---

### ❌ Treating Forum Speculation as Fact

**Detection**:
```bash
# Flag community site domains in source list
grep -E "(reddit\.com|news\.ycombinator\.com|stackoverflow\.com)" source_list.txt
```

**What it looks like**:
```
Source: HackerNews comment from user "fastdev99":
  "From what I've heard, they're planning to rewrite the scheduler in Rust next quarter"
Report: "The project plans to rewrite the scheduler in Rust next quarter"
```

**Why wrong**: HackerNews comments are unverified community speculation. Presenting them as planning facts will corrupt the coordinator's synthesis with rumors.

**Fix**: Label the claim "SPECULATION" and include the source URL so the coordinator can judge whether to use it.
```
SPECULATION: Some community members anticipate a Rust scheduler rewrite [hn.algolia.com/...] — no primary source found
```

---

### ❌ Missing Source Citation for Precise Numbers

**What it looks like**:
```
Report: "Kubernetes 1.28 reduced pod startup latency by 23%"
[No URL, no source cited]
```

**Why wrong**: Precise numbers (percentages, benchmarks, release dates, version numbers) are the most likely to be misremembered, misquoted, or context-dependent. Without a URL, the coordinator cannot verify or qualify the claim.

**Fix**: Every numeric claim gets a citation.
```
FACT: Kubernetes 1.28 release notes claim ~23% reduction in pod startup time for large clusters [source: kubernetes.io/blog/2023/08/15/kubernetes-1-28-release/]
```

---

### ❌ Accepting Marketing Language as Technical Fact

**Detection**:
```bash
# Scan fetched content for marketing signals
grep -iE "(industry.leading|best.in.class|enterprise.grade|cutting.edge|blazing.fast|seamless)" fetched_content.txt
```

**What it looks like**:
```
Source: vendor blog post
  "Our solution delivers enterprise-grade reliability with blazing-fast performance"
Report: "Tool X delivers enterprise-grade reliability"
```

**Why wrong**: Marketing superlatives have no technical definition. "Enterprise-grade" means nothing without benchmarks, SLA numbers, or comparative data. Including them in a research report reduces signal-to-noise ratio.

**Fix**: Discard marketing language. If the page contains actual benchmark numbers or SLA specs buried under the marketing text, extract those specifically.

---

## Error-Fix Mappings

| Symptom in Report | Root Cause | Fix |
|-------------------|------------|-----|
| Coordinator says "can't verify claim X" | Claim sourced from aggregator with no primary URL | Re-research using primary source; add direct URL |
| Coordinator says "conflicting data on X" | Different sources use different version contexts | Add version qualifier to each fact |
| Claim appears in final report with wrong number | Snippet misquoted — partial number visible | web_fetch the source; find the full sentence |
| Report contains "experts say" without named expert | Aggregator language laundered into report | Remove or label as SPECULATION |
| Coordinator asks "is this still current?" | No date on source | Find dated version or add "date unknown — verify" |

---

## Speculation Indicator Vocabulary

Flag any source sentence containing these phrases for manual review:

```
"reportedly"          → unverified third-party claim
"sources say"         → unnamed sources, no accountability
"is expected to"      → prediction, not confirmed
"plans to"            → future state, not current fact
"according to rumors" → speculation
"might"/"could"/"may" → conditional, not factual
"industry observers"  → unnamed, unverifiable
"it is believed"      → passive voice hiding the uncertainty
```

---

## Detection Commands Reference

```bash
# Find aggregator URL patterns in a source list
grep -E "(best-[0-9]|top-[0-9]|vs\.|comparison|alternative)" sources.txt

# Find marketing language in fetched content
grep -iE "(industry.leading|enterprise.grade|blazing.fast|seamless)" content.txt

# Find community domain sources
grep -E "(reddit|hackernews|stackoverflow|quora)" sources.txt

# Find claims without inline citations in a report
grep -E "^- (FACT|INFERENCE):" report.md | grep -v "\[source:"
```

---

## See Also

- `research-execution-patterns.md` — OODA cycle structure, budget management, query optimization
