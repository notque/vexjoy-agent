# Research Execution Patterns

> **Scope**: OODA-loop execution, budget management, tool selection strategy, and query optimization for subagent research tasks.
> **Version range**: all versions
> **Generated**: 2026-04-13

---

## Overview

This file covers the execution-level mechanics of systematic research: how to budget tool calls, structure OODA cycles, select the right tool for each phase, and detect diminishing returns before hitting hard limits. The most common failure mode is unstructured searching that burns budget on repeated queries or shallow snippets instead of using web_fetch to retrieve full content.

---

## Pattern Table

| Pattern | Use When | Avoid When |
|---------|----------|------------|
| `web_search` then `web_fetch` | Retrieving complete page content after a search hit | Snippets are sufficient for factual lookups |
| Parallel `web_search` calls | Querying multiple independent angles simultaneously | Queries depend on each other's results |
| Budget front-loading | Task is clearly complex (technical deep-dive, multi-source) | Simple factual lookups needing 2-3 calls |
| Bayesian narrowing | First queries return noisy/broad results | Initial queries are already targeted |

---

## Correct Patterns

### Budget Calculation Before Starting

Always determine the research budget (5-20 tool calls) before issuing any tool call.

```
Complexity signals → Budget:
  Simple factual (single source expected): 5 calls
  Moderate (2-3 sources, cross-reference): 8-10 calls
  Complex (multi-domain, conflicting sources): 15-20 calls
  Default when uncertain: 10 calls
```

**Why**: Starting without a budget leads to either under-researching (stopping at 3 calls when 10 are warranted) or over-running (hitting the hard 20-call limit mid-synthesis and losing findings).

---

### web_search → web_fetch Core Loop

Use web_search to identify candidates, then web_fetch to retrieve the full document for any result that looks like a primary source.

```
1. web_search("query under 5 words")
   → Scan snippets for primary/authoritative sources
   → Flag aggregator sites (listicles, forums) for lower priority
2. web_fetch(url) for top 1-2 authoritative hits
   → Extract specific data points, not just headlines
3. Repeat with narrowed/different query only if gaps remain
```

**Why**: Snippets contain 1-3 sentences of context stripped from the source. For any claim that will appear in the final report, the full page content prevents misquoting and reveals caveats that the snippet omits.

---

### Parallel Tool Invocation

Issue independent tool calls in the same turn to maximize parallelism.

```
Turn 1 (parallel):
  web_search("topic angle A")
  web_search("topic angle B")
  web_search("topic angle C")

Turn 2 (after reviewing results, parallel fetches):
  web_fetch(url_from_A)
  web_fetch(url_from_B)
```

**Why**: Sequential tool calls where results don't depend on each other waste wall-clock time. Parallel dispatch cuts research time proportionally to parallelism depth.

---

### Diminishing Returns Detection

Stop gathering when any of these conditions are met:

```
STOP if:
  - Three consecutive queries return no new facts (facts already in running list)
  - Sources begin repeating each other's claims without new citations
  - Tool call count reaches 15 (begin synthesis, don't start new queries)
  - Running list has 10+ high-quality data points and task requirements are met
```

**Why**: Continuing past diminishing returns consumes budget without improving the final report. The 20-call hard limit means hitting it mid-synthesis truncates output; stopping at 15 preserves capacity for complete_task.

---

## Anti-Pattern Catalog

### ❌ Repeating the Same Query

**Detection**:
```bash
# During a session: check if query text matches a prior call
# Pattern in agent output to look for:
grep -i "web_search" agent_log.txt | sort | uniq -d
```

**What it looks like**:
```
Turn 3: web_search("kubernetes pod crash loop")
Turn 7: web_search("kubernetes pod crash loop")  # exact repeat
```

**Why wrong**: Identical queries return identical results. Repeating them consumes budget with zero new information. The second call returns the same top-10 results as the first.

**Fix**: Vary query angle, add specificity, or add a version/date qualifier.
```
Turn 7: web_search("k8s CrashLoopBackOff OOMKilled 2024")
```

---

### ❌ Relying on Snippets for Factual Claims

**Detection**:
```bash
# Pattern: web_search call followed by direct claim, no web_fetch in between
grep -A5 "web_search" agent_log.txt | grep -v "web_fetch"
```

**What it looks like**:
```
web_search("Python 3.12 release date")
→ Snippet: "Python 3.12 was released..."
Report: "Python 3.12 was released on October 2, 2023"  # from snippet alone
```

**Why wrong**: Snippets are truncated, sometimes from outdated cached versions of pages. A claim sourced only from a snippet has no URL citation trail and may omit critical qualifiers ("Python 3.12.0 was released... but 3.12.1 patched a critical security issue two weeks later").

**Fix**: web_fetch the source page for any precise date, version, number, or specification claim.

---

### ❌ Starting Research Without a Budget

**What it looks like**:
```
Task received: "Research the state of WebAssembly tooling in 2025"
Turn 1: web_search("WebAssembly 2025")  # No budget stated
...
Turn 19: web_search("WASI spec status")  # About to hit hard limit
Turn 20: [forced termination]
```

**Why wrong**: Without a budget, the agent has no early-warning system. Hitting turn 20 mid-research produces an incomplete report with no synthesis. The coordinator receives a truncated artifact.

**Fix**: State the budget explicitly before turn 1.
```
Budget: 12 tool calls (moderate complexity — multiple competing toolchains, need cross-reference)
```

---

### ❌ Querying More Than 5 Words

**What it looks like**:
```
web_search("what are the best practices for configuring kubernetes resource limits in production")
```

**Why wrong**: Search engines perform better with short, keyword-dense queries. Long natural-language queries introduce stop words that dilute ranking signals. They also reduce result diversity (engine interprets as a phrase match).

**Fix**:
```
web_search("kubernetes resource limits production 2024")
```

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Running list has no new entries after 3 queries | Diminishing returns — topic is exhausted at this specificity | Broaden scope OR declare research complete |
| All top results are the same 2-3 articles | Query too narrow or topic too niche | Broaden query, try synonyms, check official docs directly |
| Budget exhausted, synthesis not started | No budget calculation, over-investigation | Next run: calculate budget first, stop at 15 for synthesis |
| Coordinator reports "no citations in findings" | Snippets used as sources, no web_fetch | web_fetch every primary source claim |
| Conflicting facts across sources | Sources have different publication dates or use different definitions | Note the conflict explicitly; include both with dates |

---

## OODA Cycle Structure

Each research session should follow this explicit loop:

```
OBSERVE:
  - Issue 2-4 parallel web_search calls
  - Scan all snippets for relevance and source quality

ORIENT:
  - Classify results: primary source / aggregator / speculation / outdated
  - Update running list with high-quality facts
  - Assess budget remaining vs. gaps still open

DECIDE:
  - If gaps remain AND budget > 5: continue with targeted web_fetch calls
  - If gaps remain AND budget <= 5: note gap in coverage assessment, stop
  - If no gaps remain: proceed to complete_task

ACT:
  - Execute decided tool calls in parallel
  - Return to OBSERVE with results
```

---

## Detection Commands Reference

```bash
# Find repeated queries in agent logs
grep "web_search" agent_log.txt | sort | uniq -d

# Find claims without fetch citations
grep -A3 "web_search" agent_log.txt | grep -v "web_fetch" | grep -v "^--$"

# Count tool calls in a session log
grep -c '"tool_name"' session_log.json
```

---

## See Also

- `source-quality-assessment.md` — Source credibility indicators, speculation detection, epistemic labeling
