# Research Execution Patterns

> **Scope**: OODA-loop execution, budget management, tool selection, query optimization.
> **Version range**: all versions
> **Generated**: 2026-04-13

---

## Pattern Table

| Pattern | Use When | Avoid When |
|---------|----------|------------|
| `web_search` then `web_fetch` | Full page content needed | Snippets suffice for factual lookups |
| Parallel `web_search` | Multiple independent angles | Queries depend on each other |
| Budget front-loading | Complex technical deep-dive | Simple 2-3 call lookups |
| Bayesian narrowing | Broad/noisy first results | Already targeted queries |

---

## Correct Patterns

### Budget Calculation

```
Simple (single source): 5 calls
Moderate (2-3 sources, cross-ref): 8-10 calls
Complex (multi-domain, conflicts): 15-20 calls
Default: 10 calls
```

Starting without budget leads to under-researching or hitting 20-call limit mid-synthesis.

---

### web_search → web_fetch Core Loop

```
1. web_search("query under 5 words")
   → Scan for primary/authoritative sources
2. web_fetch(url) for top 1-2 hits
   → Extract data points, not just headlines
3. Repeat with different query if gaps remain
```

Snippets are 1-3 sentences, may omit caveats. Full page content prevents misquoting.

---

### Parallel Tool Invocation

```
Turn 1: web_search("topic A") + web_search("topic B") + web_search("topic C")
Turn 2: web_fetch(url_A) + web_fetch(url_B)
```

Sequential calls with no dependency waste wall-clock time.

---

### Diminishing Returns Detection

```
STOP if:
  - 3 consecutive queries return no new facts
  - Sources repeat each other's claims
  - Tool count reaches 15 (begin synthesis)
  - Running list has 10+ high-quality data points and requirements met
```

---

## Pattern Catalog

### Vary Query Angle on Each Search

**Signal**: Same query repeated. Returns identical results, zero new info.

**Preferred action**: Add specificity, synonyms, version/date qualifier.
```
Turn 7: web_search("k8s CrashLoopBackOff OOMKilled 2024")
```

---

### Fetch Full Pages for Factual Claims

**Signal**: Claim sourced from snippet alone. Snippets may be truncated or from cached versions.

**Preferred action**: web_fetch the source page for any precise date, version, number, or specification.

---

### Set Budget Before Starting

Starting without budget → no early-warning → hitting turn 20 mid-research → truncated output.

State budget explicitly before turn 1.

---

### Keep Queries Under 5 Words

Long natural-language queries dilute ranking signals and reduce result diversity.

```
Instead of: "what are the best practices for configuring kubernetes resource limits"
Use: "kubernetes resource limits production 2024"
```

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| No new entries after 3 queries | Diminishing returns | Broaden scope or declare complete |
| Same 2-3 articles in all results | Query too narrow | Broaden, try synonyms, check official docs |
| Budget exhausted, no synthesis | No budget calculation | Calculate budget first, stop at 15 |
| "No citations" from coordinator | Snippets as sources | web_fetch every primary source |
| Conflicting facts | Different dates/definitions | Note conflict; include both with dates |

---

## OODA Cycle Structure

```
OBSERVE: 2-4 parallel web_search calls. Scan for relevance and quality.
ORIENT: Classify results (primary/aggregator/speculation/outdated). Update running list.
DECIDE: Gaps + budget > 5 → continue. Gaps + budget <= 5 → note gap, stop. No gaps → complete.
ACT: Execute, return to OBSERVE.
```

---

## Detection Commands Reference

```bash
grep "web_search" agent_log.txt | sort | uniq -d
grep -A3 "web_search" agent_log.txt | grep -v "web_fetch"
grep -c '"tool_name"' session_log.json
```

---

## See Also

- `source-quality-assessment.md` — Credibility, speculation detection, epistemic labeling
